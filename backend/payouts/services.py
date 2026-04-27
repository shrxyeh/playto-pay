import logging
from datetime import timedelta
from django.db import transaction
from django.db.models import Sum
from django.utils import timezone

from merchants.models import Merchant
from .models import LedgerEntry, Payout, IdempotencyRecord
from .exceptions import InsufficientFundsError, PayoutNotFoundError

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
STUCK_THRESHOLD_SECONDS = 30


def get_balance(merchant: Merchant) -> int:
    """Returns current balance in paise via DB SUM. Must be called inside a locked transaction."""
    result = LedgerEntry.objects.filter(merchant=merchant).aggregate(total=Sum("amount"))
    return result["total"] or 0


def get_held_amount(merchant: Merchant) -> int:
    result = Payout.objects.filter(
        merchant=merchant,
        status__in=[Payout.Status.PENDING, Payout.Status.PROCESSING],
    ).aggregate(total=Sum("amount_paise"))
    return result["total"] or 0


def create_payout(
    merchant_id: str,
    amount_paise: int,
    bank_account_id: str,
    idempotency_key: str,
) -> dict:
    if amount_paise <= 0:
        raise ValueError("amount_paise must be positive")

    with transaction.atomic():
        # Lock the merchant row first. This serializes all concurrent payout
        # requests for this merchant — the second request blocks here until
        # the first commits, then reads the already-updated ledger balance.
        try:
            merchant = Merchant.objects.select_for_update().get(id=merchant_id)
        except Merchant.DoesNotExist:
            raise PayoutNotFoundError(f"Merchant {merchant_id} not found")

        # Idempotency check happens inside the lock so two in-flight requests
        # with the same key can't both pass through and create duplicate payouts.
        expiry_cutoff = timezone.now() - timedelta(hours=24)
        try:
            existing = IdempotencyRecord.objects.get(
                merchant=merchant,
                idempotency_key=idempotency_key,
                created_at__gte=expiry_cutoff,
            )
            logger.info("idempotency hit merchant=%s key=%s", merchant_id, idempotency_key)
            return existing.response_json
        except IdempotencyRecord.DoesNotExist:
            # Clean up any expired record with this key; without this the
            # UniqueConstraint below would reject the insert even though
            # the old record is past its 24-hour window.
            IdempotencyRecord.objects.filter(
                merchant=merchant,
                idempotency_key=idempotency_key,
                created_at__lt=expiry_cutoff,
            ).delete()

        available = get_balance(merchant)
        if available < amount_paise:
            raise InsufficientFundsError(available=available, requested=amount_paise)

        payout = Payout.objects.create(
            merchant=merchant,
            amount_paise=amount_paise,
            bank_account_id=bank_account_id,
            status=Payout.Status.PENDING,
        )

        LedgerEntry.objects.create(
            merchant=merchant,
            amount=-amount_paise,
            entry_type=LedgerEntry.EntryType.PAYOUT_HOLD,
            reference_id=payout.id,
        )

        response_data = _build_payout_response(payout)
        IdempotencyRecord.objects.create(
            merchant=merchant,
            idempotency_key=idempotency_key,
            response_json=response_data,
        )

    logger.info("payout created id=%s merchant=%s amount=%sp", payout.id, merchant_id, amount_paise)
    return response_data


def finalize_success(payout_id: str) -> None:
    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(id=payout_id)
        payout.transition_to(Payout.Status.COMPLETED)
        payout.save(update_fields=["status", "updated_at"])

        # amount=0 because the hold already reduced the balance at request time;
        # this entry exists only for the audit trail.
        LedgerEntry.objects.create(
            merchant=payout.merchant,
            amount=0,
            entry_type=LedgerEntry.EntryType.PAYOUT_DEBIT,
            reference_id=payout.id,
        )
    logger.info("payout completed id=%s", payout_id)


def finalize_failure(payout_id: str) -> None:
    """Refund is atomic with the state transition — both commit or neither does."""
    with transaction.atomic():
        payout = Payout.objects.select_for_update().get(id=payout_id)
        payout.transition_to(Payout.Status.FAILED)
        payout.save(update_fields=["status", "updated_at"])

        LedgerEntry.objects.create(
            merchant=payout.merchant,
            amount=payout.amount_paise,
            entry_type=LedgerEntry.EntryType.PAYOUT_REFUND,
            reference_id=payout.id,
        )
    logger.info("payout failed and refunded id=%s", payout_id)


def get_payout_list(merchant_id: str) -> list[dict]:
    payouts = Payout.objects.filter(merchant_id=merchant_id).order_by("-created_at")
    return [_build_payout_response(p) for p in payouts]


def get_ledger_history(merchant_id: str, limit: int = 50) -> list[dict]:
    entries = (
        LedgerEntry.objects.filter(merchant_id=merchant_id)
        .order_by("-created_at")[:limit]
    )
    return [
        {
            "id": str(e.id),
            "amount": e.amount,
            "entry_type": e.entry_type,
            "reference_id": str(e.reference_id) if e.reference_id else None,
            "created_at": e.created_at.isoformat(),
        }
        for e in entries
    ]


def get_merchant_balance_summary(merchant_id: str) -> dict:
    try:
        merchant = Merchant.objects.get(id=merchant_id)
    except Merchant.DoesNotExist:
        raise PayoutNotFoundError(f"Merchant {merchant_id} not found")

    return {
        "merchant_id": str(merchant_id),
        "available_paise": get_balance(merchant),
        "held_paise": get_held_amount(merchant),
    }


def _build_payout_response(payout: Payout) -> dict:
    return {
        "id": str(payout.id),
        "merchant_id": str(payout.merchant_id),
        "amount_paise": payout.amount_paise,
        "bank_account_id": payout.bank_account_id,
        "status": payout.status,
        "retry_count": payout.retry_count,
        "created_at": payout.created_at.isoformat() if payout.created_at else None,
        "updated_at": payout.updated_at.isoformat() if payout.updated_at else None,
    }
