from django.urls import path
from .views import (
    PayoutListCreateView,
    BalanceSummaryView,
    CreditView,
    MerchantCreateView,
    LedgerHistoryView,
)

urlpatterns = [
    path("payouts", PayoutListCreateView.as_view(), name="payout-list-create"),
    path("balance", BalanceSummaryView.as_view(), name="balance-summary"),
    path("ledger", LedgerHistoryView.as_view(), name="ledger-history"),
    path("credits", CreditView.as_view(), name="credit-add"),
    path("merchants", MerchantCreateView.as_view(), name="merchant-create"),
]
