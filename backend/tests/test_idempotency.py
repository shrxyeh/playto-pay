import uuid
from django.test import TestCase, TransactionTestCase
import threading

from merchants.models import Merchant
from payouts.models import LedgerEntry, Payout, IdempotencyRecord
from payouts.services import create_payout
from payouts.exceptions import InsufficientFundsError


class IdempotencyTest(TestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(
            name="Idempotency Merchant", email="idempotent@test.com"
        )
        LedgerEntry.objects.create(
            merchant=self.merchant,
            amount=50000,
            entry_type=LedgerEntry.EntryType.CREDIT,
        )

    def test_same_key_returns_same_payout(self):
        """Calling create_payout twice with the same key creates one payout."""
        key = str(uuid.uuid4())

        response1 = create_payout(
            merchant_id=str(self.merchant.id),
            amount_paise=10000,
            bank_account_id="BANK-001",
            idempotency_key=key,
        )
        response2 = create_payout(
            merchant_id=str(self.merchant.id),
            amount_paise=10000,
            bank_account_id="BANK-001",
            idempotency_key=key,
        )

        self.assertEqual(response1["id"], response2["id"])
        self.assertEqual(Payout.objects.count(), 1)

    def test_same_key_creates_only_one_hold_entry(self):
        """Duplicate requests must not create duplicate ledger hold entries."""
        key = str(uuid.uuid4())

        create_payout(
            merchant_id=str(self.merchant.id),
            amount_paise=10000,
            bank_account_id="BANK-001",
            idempotency_key=key,
        )
        create_payout(
            merchant_id=str(self.merchant.id),
            amount_paise=10000,
            bank_account_id="BANK-001",
            idempotency_key=key,
        )

        hold_count = LedgerEntry.objects.filter(
            merchant=self.merchant,
            entry_type=LedgerEntry.EntryType.PAYOUT_HOLD,
        ).count()
        self.assertEqual(hold_count, 1)

    def test_same_key_creates_only_one_idempotency_record(self):
        key = str(uuid.uuid4())

        for _ in range(3):
            create_payout(
                merchant_id=str(self.merchant.id),
                amount_paise=5000,
                bank_account_id="BANK-001",
                idempotency_key=key,
            )

        self.assertEqual(
            IdempotencyRecord.objects.filter(
                merchant=self.merchant, idempotency_key=key
            ).count(),
            1,
        )

    def test_different_keys_create_separate_payouts(self):
        """Two requests with different keys are independent operations."""
        key1, key2 = str(uuid.uuid4()), str(uuid.uuid4())

        r1 = create_payout(
            merchant_id=str(self.merchant.id),
            amount_paise=5000,
            bank_account_id="BANK-001",
            idempotency_key=key1,
        )
        r2 = create_payout(
            merchant_id=str(self.merchant.id),
            amount_paise=5000,
            bank_account_id="BANK-001",
            idempotency_key=key2,
        )

        self.assertNotEqual(r1["id"], r2["id"])
        self.assertEqual(Payout.objects.count(), 2)

    def test_balance_deducted_once_despite_repeated_calls(self):
        """Balance must reflect only ONE hold regardless of retry count."""
        key = str(uuid.uuid4())

        for _ in range(5):
            create_payout(
                merchant_id=str(self.merchant.id),
                amount_paise=10000,
                bank_account_id="BANK-001",
                idempotency_key=key,
            )

        from django.db.models import Sum
        balance = (
            LedgerEntry.objects.filter(merchant=self.merchant)
            .aggregate(total=Sum("amount"))["total"] or 0
        )
        # 50000 credited - 10000 held = 40000
        self.assertEqual(balance, 40000)


class ConcurrentIdempotencyTest(TransactionTestCase):
    """
    Two threads sending the same idempotency key simultaneously.
    Only one payout should be created.
    """

    def setUp(self):
        self.merchant = Merchant.objects.create(
            name="Race Merchant", email="race@test.com"
        )
        LedgerEntry.objects.create(
            merchant=self.merchant,
            amount=100000,
            entry_type=LedgerEntry.EntryType.CREDIT,
        )

    def test_concurrent_same_key_creates_one_payout(self):
        key = str(uuid.uuid4())
        results = []
        barrier = threading.Barrier(2)

        def attempt():
            barrier.wait()
            try:
                data = create_payout(
                    merchant_id=str(self.merchant.id),
                    amount_paise=10000,
                    bank_account_id="BANK-X",
                    idempotency_key=key,
                )
                results.append(data)
            except Exception as e:
                results.append({"error": str(e)})

        threads = [threading.Thread(target=attempt) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Both threads should have gotten a response
        self.assertEqual(len(results), 2)

        # But only one payout should exist
        self.assertEqual(Payout.objects.count(), 1)

        # Both responses must reference the same payout id
        ids = {r.get("id") for r in results if "id" in r}
        self.assertEqual(len(ids), 1, f"Expected 1 unique payout id, got: {ids}")
