import uuid
from django.db import models
from merchants.models import Merchant


class InvalidTransitionError(Exception):
    pass


class Payout(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        PROCESSING = "processing", "Processing"
        COMPLETED = "completed", "Completed"
        FAILED = "failed", "Failed"

    _VALID_TRANSITIONS = {
        Status.PENDING: {Status.PROCESSING},
        Status.PROCESSING: {Status.COMPLETED, Status.FAILED},
        Status.COMPLETED: set(),
        Status.FAILED: set(),
    }

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name="payouts")
    amount_paise = models.BigIntegerField()
    bank_account_id = models.CharField(max_length=255)
    status = models.CharField(
        max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True
    )
    retry_count = models.PositiveSmallIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "payouts"
        indexes = [
            models.Index(fields=["merchant", "status"]),
            models.Index(fields=["status", "updated_at"]),
        ]

    def transition_to(self, new_status: str) -> None:
        """Raises InvalidTransitionError for any move not in _VALID_TRANSITIONS."""
        allowed = self._VALID_TRANSITIONS.get(self.status, set())
        if new_status not in allowed:
            raise InvalidTransitionError(
                f"Cannot move payout {self.id} from '{self.status}' to '{new_status}' "
                f"(allowed: {allowed or 'none — terminal state'})"
            )
        self.status = new_status

    def __str__(self):
        return f"Payout({self.id}, {self.amount_paise}p, {self.status})"


class LedgerEntry(models.Model):
    """
    Append-only ledger. Positive = credit, negative = debit.
    Balance is always derived via SUM — never stored as a column.
    """

    class EntryType(models.TextChoices):
        CREDIT = "credit", "Credit"
        PAYOUT_HOLD = "payout_hold", "Payout Hold"
        PAYOUT_DEBIT = "payout_debit", "Payout Debit"
        PAYOUT_REFUND = "payout_refund", "Payout Refund"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name="ledger_entries")
    amount = models.BigIntegerField()
    entry_type = models.CharField(max_length=20, choices=EntryType.choices)
    reference_id = models.UUIDField(null=True, blank=True, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)

    class Meta:
        db_table = "ledger_entries"
        indexes = [
            models.Index(fields=["merchant", "entry_type"]),
        ]

    def __str__(self):
        return f"LedgerEntry({self.entry_type}, {self.amount}p, merchant={self.merchant_id})"


class IdempotencyRecord(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    merchant = models.ForeignKey(Merchant, on_delete=models.PROTECT, related_name="idempotency_records")
    idempotency_key = models.UUIDField(db_index=True)
    response_json = models.JSONField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "idempotency_records"
        constraints = [
            models.UniqueConstraint(
                fields=["merchant", "idempotency_key"],
                name="unique_merchant_idempotency_key",
            )
        ]

    def __str__(self):
        return f"IdempotencyRecord({self.idempotency_key}, merchant={self.merchant_id})"
