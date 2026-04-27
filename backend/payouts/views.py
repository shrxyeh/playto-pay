import uuid
import logging
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .serializers import PayoutRequestSerializer
from .services import (
    create_payout,
    get_payout_list,
    get_merchant_balance_summary,
    get_ledger_history,
)
from .exceptions import InsufficientFundsError, PayoutNotFoundError

logger = logging.getLogger(__name__)

MERCHANT_ID_HEADER = "X-Merchant-Id"
IDEMPOTENCY_KEY_HEADER = "Idempotency-Key"


def _get_merchant_id(request) -> str | None:
    return request.headers.get(MERCHANT_ID_HEADER)


def _require_merchant_id(request):
    mid = _get_merchant_id(request)
    if not mid:
        return None, Response(
            {"error": f"Missing {MERCHANT_ID_HEADER} header"},
            status=status.HTTP_400_BAD_REQUEST,
        )
    return mid, None


class PayoutListCreateView(APIView):
    def post(self, request):
        merchant_id, err = _require_merchant_id(request)
        if err:
            return err

        idempotency_key = request.headers.get(IDEMPOTENCY_KEY_HEADER)
        if not idempotency_key:
            return Response(
                {"error": f"Missing {IDEMPOTENCY_KEY_HEADER} header"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            uuid.UUID(idempotency_key)
        except ValueError:
            return Response(
                {"error": "Idempotency-Key must be a valid UUID"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = PayoutRequestSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        try:
            data = create_payout(
                merchant_id=merchant_id,
                amount_paise=serializer.validated_data["amount_paise"],
                bank_account_id=serializer.validated_data["bank_account_id"],
                idempotency_key=idempotency_key,
            )
            return Response(data, status=status.HTTP_201_CREATED)
        except InsufficientFundsError as e:
            return Response(
                {"error": "insufficient_funds", "detail": str(e)},
                status=status.HTTP_422_UNPROCESSABLE_ENTITY,
            )
        except PayoutNotFoundError as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception:
            logger.exception("unexpected error creating payout")
            return Response({"error": "internal_error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def get(self, request):
        merchant_id, err = _require_merchant_id(request)
        if err:
            return err
        try:
            return Response(get_payout_list(merchant_id))
        except Exception:
            logger.exception("error fetching payout list")
            return Response({"error": "internal_error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class BalanceSummaryView(APIView):
    def get(self, request):
        merchant_id, err = _require_merchant_id(request)
        if err:
            return err
        try:
            return Response(get_merchant_balance_summary(merchant_id))
        except PayoutNotFoundError as e:
            return Response({"error": str(e)}, status=status.HTTP_404_NOT_FOUND)
        except Exception:
            logger.exception("error fetching balance")
            return Response({"error": "internal_error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class LedgerHistoryView(APIView):
    def get(self, request):
        merchant_id, err = _require_merchant_id(request)
        if err:
            return err
        try:
            return Response(get_ledger_history(merchant_id))
        except Exception:
            logger.exception("error fetching ledger history")
            return Response({"error": "internal_error"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


class CreditView(APIView):
    def post(self, request):
        from merchants.models import Merchant
        from .models import LedgerEntry

        merchant_id, err = _require_merchant_id(request)
        if err:
            return err

        amount = request.data.get("amount_paise")
        if not amount or not isinstance(amount, int) or amount <= 0:
            return Response(
                {"error": "amount_paise must be a positive integer"},
                status=status.HTTP_400_BAD_REQUEST,
            )
        try:
            merchant = Merchant.objects.get(id=merchant_id)
        except Merchant.DoesNotExist:
            return Response({"error": "merchant not found"}, status=status.HTTP_404_NOT_FOUND)

        LedgerEntry.objects.create(
            merchant=merchant,
            amount=amount,
            entry_type=LedgerEntry.EntryType.CREDIT,
        )
        return Response({"credited_paise": amount}, status=status.HTTP_201_CREATED)


class MerchantCreateView(APIView):
    def post(self, request):
        from merchants.models import Merchant

        name = request.data.get("name")
        email = request.data.get("email")
        if not name or not email:
            return Response({"error": "name and email required"}, status=status.HTTP_400_BAD_REQUEST)

        merchant, created = Merchant.objects.get_or_create(email=email, defaults={"name": name})
        return Response(
            {"id": str(merchant.id), "name": merchant.name, "email": merchant.email},
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
