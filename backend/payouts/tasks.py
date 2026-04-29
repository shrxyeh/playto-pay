import random
import logging
from datetime import timedelta

from celery import shared_task
from django.db import transaction
from django.utils import timezone

from .models import Payout, InvalidTransitionError, LedgerEntry
from .services import finalize_success, finalize_failure, MAX_RETRIES, STUCK_THRESHOLD_SECONDS

logger = logging.getLogger(__name__)


def _simulate_bank_transfer() -> str:
    roll = random.random()
    if roll < 0.70:
        return "success"
    elif roll < 0.90:
        return "failure"
    return "stuck"


@shared_task(
    bind=True,
    max_retries=MAX_RETRIES,
    default_retry_delay=30,
    acks_late=True,
)
def process_payout(self, payout_id: str) -> None:
    logger.info("processing payout id=%s attempt=%d", payout_id, self.request.retries + 1)

    try:
        with transaction.atomic():
            payout = Payout.objects.select_for_update().get(id=payout_id)

            if payout.status in (Payout.Status.COMPLETED, Payout.Status.FAILED):
                return

            if payout.status == Payout.Status.PROCESSING:
                return

            payout.transition_to(Payout.Status.PROCESSING)
            payout.save(update_fields=["status", "updated_at"])

    except Payout.DoesNotExist:
        logger.error("payout not found id=%s", payout_id)
        return
    except InvalidTransitionError as e:
        logger.warning("invalid transition payout=%s: %s", payout_id, e)
        return

    # Commit 'processing' before calling the bank so reap_stuck_payouts
    # can recover this payout if the worker dies mid-flight.
    outcome = _simulate_bank_transfer()
    logger.info("payout %s outcome=%s", payout_id, outcome)

    if outcome == "success":
        finalize_success(payout_id)
    elif outcome == "failure":
        finalize_failure(payout_id)
    # "stuck" outcome: do nothing, reap_stuck_payouts handles the timeout


@shared_task
def dispatch_pending_payouts() -> None:
    pending_ids = list(
        Payout.objects.filter(status=Payout.Status.PENDING)
        .values_list("id", flat=True)
        .order_by("created_at")[:100]
    )
    for payout_id in pending_ids:
        process_payout.delay(str(payout_id))


@shared_task
def reap_stuck_payouts() -> None:
    cutoff = timezone.now() - timedelta(seconds=STUCK_THRESHOLD_SECONDS)
    stuck = Payout.objects.filter(
        status=Payout.Status.PROCESSING,
        updated_at__lt=cutoff,
    ).select_for_update(skip_locked=True)

    with transaction.atomic():
        for payout in stuck:
            if payout.retry_count < MAX_RETRIES:
                delay = 30 * (2 ** payout.retry_count)
                payout.status = Payout.Status.PENDING
                payout.retry_count += 1
                payout.save(update_fields=["status", "retry_count", "updated_at"])
                payout_id_str = str(payout.id)
                # Dispatch after commit so the worker sees the updated row.
                transaction.on_commit(
                    lambda pid=payout_id_str, d=delay: process_payout.apply_async(
                        args=[pid], countdown=d
                    )
                )
                logger.info("retrying payout %s attempt=%d in %ds", payout.id, payout.retry_count, delay)
            else:
                payout_id_str = str(payout.id)
                transaction.on_commit(lambda pid=payout_id_str: force_fail_payout.delay(pid))
                logger.warning("payout %s exhausted retries, forcing failure", payout.id)


@shared_task
def force_fail_payout(payout_id: str) -> None:
    try:
        with transaction.atomic():
            payout = Payout.objects.select_for_update().get(id=payout_id)
            if payout.status not in (Payout.Status.PENDING, Payout.Status.PROCESSING):
                return
            if payout.status == Payout.Status.PENDING:
                payout.status = Payout.Status.PROCESSING
            payout.transition_to(Payout.Status.FAILED)
            payout.save(update_fields=["status", "updated_at"])
            LedgerEntry.objects.create(
                merchant=payout.merchant,
                amount=payout.amount_paise,
                entry_type=LedgerEntry.EntryType.PAYOUT_REFUND,
                reference_id=payout.id,
            )
        logger.info("force-failed payout %s after retry exhaustion", payout_id)
    except Payout.DoesNotExist:
        logger.error("force_fail_payout: payout not found id=%s", payout_id)
