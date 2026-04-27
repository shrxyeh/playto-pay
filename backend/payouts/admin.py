from django.contrib import admin
from .models import Payout, LedgerEntry, IdempotencyRecord


@admin.register(Payout)
class PayoutAdmin(admin.ModelAdmin):
    list_display = ("id", "merchant", "amount_paise", "status", "retry_count", "created_at")
    list_filter = ("status",)
    readonly_fields = ("id", "created_at", "updated_at")
    search_fields = ("id", "merchant__email")


@admin.register(LedgerEntry)
class LedgerEntryAdmin(admin.ModelAdmin):
    list_display = ("id", "merchant", "amount", "entry_type", "reference_id", "created_at")
    list_filter = ("entry_type",)
    readonly_fields = ("id", "created_at")
    search_fields = ("merchant__email", "reference_id")

    def has_change_permission(self, request, obj=None):
        return False  # ledger is immutable

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(IdempotencyRecord)
class IdempotencyRecordAdmin(admin.ModelAdmin):
    list_display = ("id", "merchant", "idempotency_key", "created_at")
    readonly_fields = ("id", "created_at", "response_json")
