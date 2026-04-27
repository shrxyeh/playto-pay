import uuid
from rest_framework import serializers
from .models import Payout, LedgerEntry


class PayoutRequestSerializer(serializers.Serializer):
    amount_paise = serializers.IntegerField(min_value=1)
    bank_account_id = serializers.CharField(max_length=255)

    def validate_amount_paise(self, value):
        if value <= 0:
            raise serializers.ValidationError("amount_paise must be positive")
        return value


class PayoutResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = Payout
        fields = [
            "id",
            "merchant_id",
            "amount_paise",
            "bank_account_id",
            "status",
            "retry_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class LedgerEntrySerializer(serializers.ModelSerializer):
    class Meta:
        model = LedgerEntry
        fields = ["id", "amount", "entry_type", "reference_id", "created_at"]
        read_only_fields = fields


class BalanceSummarySerializer(serializers.Serializer):
    merchant_id = serializers.UUIDField()
    available_paise = serializers.IntegerField()
    held_paise = serializers.IntegerField()
