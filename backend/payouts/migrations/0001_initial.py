import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True
    dependencies = [
        ("merchants", "0001_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="Payout",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="payouts", to="merchants.merchant")),
                ("amount_paise", models.BigIntegerField()),
                ("bank_account_id", models.CharField(max_length=255)),
                ("status", models.CharField(
                    choices=[("pending", "Pending"), ("processing", "Processing"), ("completed", "Completed"), ("failed", "Failed")],
                    db_index=True, default="pending", max_length=20,
                )),
                ("retry_count", models.PositiveSmallIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={"db_table": "payouts"},
        ),
        migrations.CreateModel(
            name="LedgerEntry",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="ledger_entries", to="merchants.merchant")),
                ("amount", models.BigIntegerField()),
                ("entry_type", models.CharField(
                    choices=[("credit", "Credit"), ("payout_hold", "Payout Hold"), ("payout_debit", "Payout Debit"), ("payout_refund", "Payout Refund")],
                    max_length=20,
                )),
                ("reference_id", models.UUIDField(blank=True, db_index=True, null=True)),
                ("created_at", models.DateTimeField(auto_now_add=True, db_index=True)),
            ],
            options={"db_table": "ledger_entries"},
        ),
        migrations.CreateModel(
            name="IdempotencyRecord",
            fields=[
                ("id", models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ("merchant", models.ForeignKey(on_delete=django.db.models.deletion.PROTECT, related_name="idempotency_records", to="merchants.merchant")),
                ("idempotency_key", models.UUIDField(db_index=True)),
                ("response_json", models.JSONField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
            ],
            options={"db_table": "idempotency_records"},
        ),
        migrations.AddIndex(
            model_name="payout",
            index=models.Index(fields=["merchant", "status"], name="payout_merchant_status_idx"),
        ),
        migrations.AddIndex(
            model_name="payout",
            index=models.Index(fields=["status", "updated_at"], name="payout_status_updated_idx"),
        ),
        migrations.AddIndex(
            model_name="ledgerentry",
            index=models.Index(fields=["merchant", "entry_type"], name="ledger_merchant_type_idx"),
        ),
        migrations.AddConstraint(
            model_name="idempotencyrecord",
            constraint=models.UniqueConstraint(
                fields=["merchant", "idempotency_key"],
                name="unique_merchant_idempotency_key",
            ),
        ),
    ]
