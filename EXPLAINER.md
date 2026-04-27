# EXPLAINER

---

## 1. The Ledger

Balance is never stored as a column. Every financial event (credit, hold, refund) is an immutable row in `ledger_entries` with a signed integer amount. The current balance is always `SUM(amount)` over all rows for that merchant.

The query (from `payouts/services.py`):

```python
LedgerEntry.objects.filter(merchant=merchant).aggregate(total=Sum("amount"))
```

Which PostgreSQL executes as:

```sql
SELECT COALESCE(SUM(amount), 0)
FROM ledger_entries
WHERE merchant_id = '<uuid>';
```

**Why not store balance as a column?** Because any UPDATE to a balance column creates a window where two concurrent transactions can read the same value, both decide they have enough funds, and both proceed. You can work around it with `UPDATE ... SET balance = balance - X WHERE balance >= X`, but then you've lost the audit trail and you're fighting the database instead of using it. With a ledger, the SUM *is* the balance, and the row history is your audit trail for free.

The model has four entry types:
- `credit`: funds arrive (simulated customer payment)
- `payout_hold`: funds reserved when a payout is requested (negative amount)
- `payout_refund`: hold reversed when a payout fails (positive amount)
- `payout_debit`: settlement marker on success (amount=0, audit only since the hold already did the work)

---

## 2. The Lock

The code that prevents overdraw (`payouts/services.py`):

```python
with transaction.atomic():
    merchant = Merchant.objects.select_for_update().get(id=merchant_id)

    expiry_cutoff = timezone.now() - timedelta(hours=24)
    try:
        existing = IdempotencyRecord.objects.get(
            merchant=merchant,
            idempotency_key=idempotency_key,
            created_at__gte=expiry_cutoff,
        )
        return existing.response_json
    except IdempotencyRecord.DoesNotExist:
        IdempotencyRecord.objects.filter(
            merchant=merchant,
            idempotency_key=idempotency_key,
            created_at__lt=expiry_cutoff,
        ).delete()

    available = get_balance(merchant)
    if available < amount_paise:
        raise InsufficientFundsError(available=available, requested=amount_paise)

    payout = Payout.objects.create(...)
    LedgerEntry.objects.create(amount=-amount_paise, ...)
```

The primitive is `SELECT ... FOR UPDATE`, a row-level exclusive lock in PostgreSQL. Once transaction T1 acquires it on the merchant row, any other transaction trying to lock the same row blocks at the database level until T1 commits.

For the ₹100 / two ₹60 scenario:

```
T1: SELECT merchants WHERE id=X FOR UPDATE  → acquires lock
T2: SELECT merchants WHERE id=X FOR UPDATE  → blocked, waiting

T1: SUM(ledger) → 10000 ≥ 6000 → ok
T1: INSERT payout + ledger_hold(-6000)
T1: COMMIT → releases lock

T2: unblocked, acquires lock
T2: SUM(ledger) → 4000 < 6000 → InsufficientFundsError
T2: ROLLBACK
```

The balance check, the payout insert, and the ledger hold are all in the same `atomic()` block. There is no window between reading and writing where another transaction can change the balance.

---

## 3. Idempotency

An `IdempotencyRecord` row stores the exact response JSON for each `(merchant_id, idempotency_key)` pair, with a `UniqueConstraint` as the DB-level backstop.

The first time a key arrives, no record exists so we proceed with the payout, then write the record inside the same transaction. The second time the same key arrives, we find the record and return the stored response immediately, without touching payouts or the ledger.

**Key expiry:** records older than 24 hours are treated as absent. When we don't find a valid record, we also delete any expired one with the same key before inserting a new record. Without that delete, the `UniqueConstraint` would reject the insert even though the key is considered expired.

**What happens if the first request is still in flight when the second arrives?**

Both requests go through the same `select_for_update()` on the merchant row, so they're serialized at the database. The second request blocks until the first commits. Once the first commits, it has written the idempotency record, and the second request finds it and returns the cached response. The idempotency check is deliberately inside the lock for this reason: if it were outside, both requests could pass the "key not found" check simultaneously and both proceed to create a payout.

---

## 4. The State Machine

`Payout.transition_to()` in `payouts/models.py`:

```python
_VALID_TRANSITIONS = {
    "pending":    {"processing"},
    "processing": {"completed", "failed"},
    "completed":  set(),
    "failed":     set(),
}

def transition_to(self, new_status: str) -> None:
    allowed = self._VALID_TRANSITIONS.get(self.status, set())
    if new_status not in allowed:
        raise InvalidTransitionError(
            f"Cannot move payout {self.id} from '{self.status}' to '{new_status}' "
            f"(allowed: {allowed or 'none, terminal state'})"
        )
    self.status = new_status
```

`failed → completed` is blocked because `_VALID_TRANSITIONS["failed"]` is an empty set. Any target status raises `InvalidTransitionError` immediately. Same for `completed → anything`. The only legal paths are `pending → processing → completed` and `pending → processing → failed`.

Every status change in the codebase goes through `transition_to()`. The one exception is in `reap_stuck_payouts`, which directly resets a stuck payout from `processing` back to `pending` for retry. This is an intentional system-level override, not a user-triggered transition, written explicitly rather than through the state machine to make the intent obvious.

The refund on failure happens atomically with the transition. `finalize_failure()` opens a single `transaction.atomic()` block, calls `transition_to(FAILED)`, saves the payout, and creates the `payout_refund` ledger entry. Either all three happen or none do.

---

## 5. AI Audit

While working on the initial implementation, I caught this pattern in my first draft of `create_payout`:

```python
# WRONG
def create_payout(merchant_id, amount_paise, ...):
    merchant = Merchant.objects.get(id=merchant_id)

    existing = IdempotencyRecord.objects.filter(
        merchant=merchant, idempotency_key=idempotency_key
    ).first()
    if existing:
        return existing.response_json

    credits = LedgerEntry.objects.filter(
        merchant=merchant, entry_type='credit'
    ).aggregate(Sum('amount'))['amount__sum'] or 0

    holds = LedgerEntry.objects.filter(
        merchant=merchant, entry_type='payout_hold'
    ).aggregate(Sum('amount'))['amount__sum'] or 0

    balance = credits - holds

    if balance < amount_paise:
        raise InsufficientFundsError(...)

    payout = Payout.objects.create(...)
    LedgerEntry.objects.create(amount=-amount_paise, ...)
```

Three things wrong with this:

First, no lock. Two threads call `Merchant.objects.get()` simultaneously, both read the same balance, both pass the check, both create payouts. The merchant is overdrafted.

Second, balance is computed from two separate queries (one for credits, one for holds) combined in Python. Even if we added a lock somewhere, a third concurrent transaction could insert a hold between the two queries, making the computed balance stale before we act on it. One `SUM(amount)` over all entry types eliminates this.

Third, the idempotency check is outside any transaction. Two requests with the same key can both see "no record" before either writes one. The `UniqueConstraint` will catch the second insert and raise `IntegrityError`, but at that point both requests have already created a payout and a ledger hold. The fix is to do the idempotency check inside the merchant lock, where both requests are serialized.

The corrected version acquires the lock first, checks idempotency inside that lock, then runs a single `SUM(amount)` across all entry types, and does all writes in the same `atomic()` block.
