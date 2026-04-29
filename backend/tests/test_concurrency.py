# TransactionTestCase required: TestCase never commits, so SELECT FOR UPDATE
# doesn't block across threads. These tests need real DB-level locking.
import uuid
import threading
from django.test import TransactionTestCase
from django.db.models import Sum

from merchants.models import Merchant
from payouts.models import LedgerEntry, Payout
from payouts.services import create_payout
from payouts.exceptions import InsufficientFundsError


class ConcurrentPayoutTest(TransactionTestCase):
    def setUp(self):
        self.merchant = Merchant.objects.create(
            name="Test Merchant", email="concurrent@test.com"
        )
        # Seed ₹100 = 10000 paise
        LedgerEntry.objects.create(
            merchant=self.merchant,
            amount=10000,
            entry_type=LedgerEntry.EntryType.CREDIT,
        )

    def test_only_one_of_two_concurrent_payouts_succeeds(self):
        """
        Two simultaneous requests for 6000p each against a 10000p balance.
        Exactly one must succeed and one must raise InsufficientFundsError.
        """
        results = []
        errors = []
        barrier = threading.Barrier(2)  # ensures both threads start together

        def attempt_payout():
            barrier.wait()  # both threads hit the DB at the same moment
            try:
                data = create_payout(
                    merchant_id=str(self.merchant.id),
                    amount_paise=6000,
                    bank_account_id="ACC-001",
                    idempotency_key=str(uuid.uuid4()),
                )
                results.append(data)
            except InsufficientFundsError as e:
                errors.append(e)

        threads = [threading.Thread(target=attempt_payout) for _ in range(2)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(
            len(results), 1,
            f"Expected 1 success, got {len(results)}. Errors: {errors}",
        )
        self.assertEqual(
            len(errors), 1,
            f"Expected 1 InsufficientFundsError, got {len(errors)}",
        )

        # Only one Payout row should exist
        self.assertEqual(Payout.objects.count(), 1)

        # Available balance should now be 10000 - 6000 = 4000
        remaining = (
            LedgerEntry.objects.filter(merchant=self.merchant)
            .aggregate(total=Sum("amount"))["total"] or 0
        )
        self.assertEqual(remaining, 4000)

    def test_same_merchant_multiple_sequential_payouts_respect_balance(self):
        """
        Three sequential 4000p payouts against 10000p balance.
        First two succeed, third fails.
        """
        key1, key2, key3 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())

        create_payout(
            merchant_id=str(self.merchant.id),
            amount_paise=4000,
            bank_account_id="ACC-001",
            idempotency_key=key1,
        )
        create_payout(
            merchant_id=str(self.merchant.id),
            amount_paise=4000,
            bank_account_id="ACC-001",
            idempotency_key=key2,
        )

        with self.assertRaises(InsufficientFundsError):
            create_payout(
                merchant_id=str(self.merchant.id),
                amount_paise=4000,
                bank_account_id="ACC-001",
                idempotency_key=key3,
            )

        self.assertEqual(Payout.objects.count(), 2)
