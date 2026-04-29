from django.core.management.base import BaseCommand
from django.db import transaction

from merchants.models import Merchant
from payouts.models import LedgerEntry


MERCHANTS = [
    {
        "name": "Priya Designs",
        "email": "priya@designs.in",
        "credits": [
            {"amount": 250000, "note": "Client payment – March invoice"},
            {"amount": 180000, "note": "Client payment – April invoice"},
            {"amount": 90000, "note": "Rush delivery bonus"},
        ],
    },
    {
        "name": "Kiran Dev Studio",
        "email": "kiran@devstudio.in",
        "credits": [
            {"amount": 500000, "note": "Retainer – Q1"},
            {"amount": 500000, "note": "Retainer – Q2"},
            {"amount": 125000, "note": "Feature add-on"},
        ],
    },
    {
        "name": "Ananya Translations",
        "email": "ananya@translations.in",
        "credits": [
            {"amount": 75000, "note": "Document batch #1"},
            {"amount": 60000, "note": "Document batch #2"},
        ],
    },
]


class Command(BaseCommand):
    help = "Seed database with sample merchants and credit history"

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete all existing seed merchants before re-seeding",
        )

    @transaction.atomic
    def handle(self, *args, **options):
        seed_emails = {m["email"] for m in MERCHANTS}

        if options["reset"]:
            deleted, _ = Merchant.objects.filter(email__in=seed_emails).delete()
            self.stdout.write(f"Deleted {deleted} existing seed records.")

        for data in MERCHANTS:
            merchant, created = Merchant.objects.get_or_create(
                email=data["email"],
                defaults={"name": data["name"]},
            )
            action = "Created" if created else "Found existing"
            self.stdout.write(f"{action} merchant: {merchant.name} (id={merchant.id})")

            if created:
                for credit in data["credits"]:
                    LedgerEntry.objects.create(
                        merchant=merchant,
                        amount=credit["amount"],
                        entry_type=LedgerEntry.EntryType.CREDIT,
                    )
                self.stdout.write(
                    f"  → Added {len(data['credits'])} credit entries"
                )

            total = sum(c["amount"] for c in data["credits"])
            self.stdout.write(
                self.style.SUCCESS(
                    f"  → Balance: ₹{total / 100:.2f} "
                    f"({total} paise)"
                )
            )

        self.stdout.write(self.style.SUCCESS("\nSeed complete."))
