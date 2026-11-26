"""B2C storefront: payment summary, installment BIN, receipt upload, refund requests."""

from __future__ import annotations

from decimal import Decimal

from django.http import FileResponse
from rest_framework import serializers
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.api_keys.permissions import StorefrontScopedPermissionsMixin
from apps.commerce.models import B2cOrder
from apps.common.responses import envelope_response
from config.exceptions import DomainError

from .bank_transfer import (
    list_active_bank_accounts,
    serialize_bank_account,
    serialize_transfer_payment,
    upload_transfer_receipt,
)
from .iyzico_client import IyzicoNotConfigured, fetch_installment_info
from .models import PaymentTransaction, RefundRequest
from .services import create_refund_request


def _order_for_user(user, order_no: str) -> B2cOrder:
    order = (
        B2cOrder.objects.select_related("customer")
        .filter(order_no=order_no, created_by=user)
        .first()
    )
    if order is None:
        raise DomainError("Sipariş bulunamadı.", code="NOT_FOUND", status_code=404)
    return order


def _ser_tx(tx: PaymentTransaction) -> dict:
    data = serialize_transfer_payment(tx) if tx.provider == PaymentTransaction.Provider.BANK_TRANSFER else {
        "id": str(tx.id),
        "provider": tx.provider,
        "status": tx.status,
        "paidPrice": str(tx.paid_price),
        "basePrice": str(tx.base_price),
        "refundedAmount": str(tx.refunded_amount),
        "currency": tx.currency,
        "installment": tx.installment,
        "cardFamily": tx.card_family,
        "lastFourDigits": tx.last_four_digits,
        "cardAssociation": tx.card_association,
        "paymentId": tx.payment_id,
        "conversationId": tx.conversation_id,
        "createdAt": tx.created_at.isoformat(),
    }
    return data


def _ser_req(r: RefundRequest) -> dict:
    return {
        "id": str(r.id),
        "kind": r.kind,
        "status": r.status,
        "requestedAmount": str(r.requested_amount) if r.requested_amount is not None else None,
        "reason": r.reason,
        "adminNote": r.admin_note,
        "refundIban": r.refund_iban,
        "refundAccountHolder": r.refund_account_holder,
        "createdAt": r.created_at.isoformat(),
        "reviewedAt": r.reviewed_at.isoformat() if r.reviewed_at else None,
    }


class RefundRequestCreateSerializer(serializers.Serializer):
    kind = serializers.ChoiceField(choices=["CANCEL", "REFUND"], default="REFUND")
    reason = serializers.CharField(max_length=2000, required=False, allow_blank=True, default="")
    requestedAmount = serializers.DecimalField(
        max_digits=14, decimal_places=2, required=False, allow_null=True
    )
    refundIban = serializers.CharField(max_length=34, required=False, allow_blank=True, default="")
    refundAccountHolder = serializers.CharField(
        max_length=160, required=False, allow_blank=True, default=""
    )


class InstallmentInfoSerializer(serializers.Serializer):
    binNumber = serializers.CharField(min_length=6, max_length=8)
    price = serializers.DecimalField(max_digits=14, decimal_places=2)


class StorefrontBankAccountsView(StorefrontScopedPermissionsMixin, APIView):
    """GET /api/v1/storefront/payments/bank-accounts"""

    def get(self, request: Request):
        rows = [serialize_bank_account(a) for a in list_active_bank_accounts()]
        return envelope_response(rows, request)


class StorefrontInstallmentInfoView(StorefrontScopedPermissionsMixin, APIView):
    """POST /api/v1/storefront/payments/installments — BIN → taksit seçenekleri."""

    def post(self, request: Request):
        ser = InstallmentInfoSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        try:
            raw = fetch_installment_info(bin_number=d["binNumber"], price=d["price"])
        except IyzicoNotConfigured as exc:
            raise DomainError(str(exc), code="IYZICO_NOT_CONFIGURED", status_code=503) from exc
        except ValueError as exc:
            raise DomainError(str(exc), code="INVALID_BIN", status_code=400) from exc

        details = raw.get("installmentDetails") or raw.get("installment_details") or []
        options = []
        card_family = ""
        for detail in details if isinstance(details, list) else []:
            if not isinstance(detail, dict):
                continue
            card_family = card_family or (detail.get("cardFamilyName") or detail.get("cardFamily") or "")
            for price_row in detail.get("installmentPrices") or detail.get("installment_prices") or []:
                if not isinstance(price_row, dict):
                    continue
                count = int(price_row.get("installmentNumber") or price_row.get("installmentCount") or 1)
                total = price_row.get("totalPrice") or price_row.get("price")
                monthly = price_row.get("installmentPrice")
                options.append(
                    {
                        "installmentCount": count,
                        "monthlyAmount": str(monthly) if monthly is not None else None,
                        "totalAmount": str(total) if total is not None else None,
                    }
                )
        return envelope_response(
            {
                "binNumber": "".join(ch for ch in str(d["binNumber"]) if ch.isdigit())[:8],
                "cardFamily": card_family,
                "status": raw.get("status"),
                "options": options,
                "raw": raw if (raw.get("status") or "").lower() != "success" else None,
            },
            request,
        )


class StorefrontOrderPaymentsView(StorefrontScopedPermissionsMixin, APIView):
    """GET /api/v1/storefront/orders/<order_no>/payments"""

    def get(self, request: Request, order_no: str):
        order = _order_for_user(request.user, order_no)
        txs = [_ser_tx(t) for t in PaymentTransaction.objects.filter(order=order).order_by("-created_at")[:10]]
        reqs = [_ser_req(r) for r in RefundRequest.objects.filter(order=order).order_by("-created_at")[:20]]
        banks = []
        if order.payment_method == "BANK_TRANSFER":
            banks = [serialize_bank_account(a) for a in list_active_bank_accounts()]
        return envelope_response(
            {
                "orderNo": order.order_no,
                "orderStatus": order.status,
                "paymentMethod": order.payment_method,
                "transactions": txs,
                "refundRequests": reqs,
                "bankAccounts": banks,
            },
            request,
        )


class StorefrontReceiptUploadView(StorefrontScopedPermissionsMixin, APIView):
    """POST /api/v1/storefront/orders/<order_no>/receipt — multipart file."""

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request: Request, order_no: str):
        order = _order_for_user(request.user, order_no)
        uploaded = request.FILES.get("file") or request.FILES.get("receipt")
        if uploaded is None:
            raise DomainError("Dekont dosyası gerekli (PDF/JPG/PNG).", code="FILE_REQUIRED", status_code=400)
        name = (uploaded.name or "").lower()
        if not any(name.endswith(ext) for ext in (".pdf", ".jpg", ".jpeg", ".png")):
            raise DomainError("Yalnızca PDF, JPG veya PNG.", code="INVALID_FILE_TYPE", status_code=400)
        if uploaded.size and uploaded.size > 8 * 1024 * 1024:
            raise DomainError("Dosya en fazla 8 MB olabilir.", code="FILE_TOO_LARGE", status_code=400)
        tx = upload_transfer_receipt(user=request.user, order=order, uploaded_file=uploaded)
        return envelope_response(_ser_tx(tx), request, status=201)


class StorefrontRefundRequestCreateView(StorefrontScopedPermissionsMixin, APIView):
    """POST /api/v1/storefront/orders/<order_no>/refund-requests"""

    parser_classes = [JSONParser, MultiPartParser, FormParser]

    def post(self, request: Request, order_no: str):
        order = _order_for_user(request.user, order_no)
        ser = RefundRequestCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        if order.payment_method == "BANK_TRANSFER":
            if not (d.get("refundIban") or "").strip() or not (d.get("refundAccountHolder") or "").strip():
                raise DomainError(
                    "Havale iadesi için IBAN ve hesap sahibi zorunludur.",
                    code="REFUND_IBAN_REQUIRED",
                    status_code=400,
                )
        amount = d.get("requestedAmount")
        row = create_refund_request(
            user=request.user,
            order=order,
            kind=d["kind"],
            reason=d.get("reason") or "",
            requested_amount=Decimal(str(amount)) if amount is not None else None,
        )
        if d.get("refundIban"):
            row.refund_iban = d["refundIban"].replace(" ", "").upper()
            row.refund_account_holder = d.get("refundAccountHolder") or ""
            row.save(update_fields=["refund_iban", "refund_account_holder", "updated_at"])
            if row.payment_id:
                PaymentTransaction.objects.filter(id=row.payment_id).update(
                    refund_iban=row.refund_iban,
                    refund_account_holder=row.refund_account_holder,
                )
        return envelope_response(_ser_req(row), request, status=201)


class StorefrontReceiptFileView(StorefrontScopedPermissionsMixin, APIView):
    """GET own receipt file (customer)."""

    def get(self, request: Request, order_no: str):
        order = _order_for_user(request.user, order_no)
        tx = (
            PaymentTransaction.objects.filter(
                order=order, provider=PaymentTransaction.Provider.BANK_TRANSFER
            )
            .order_by("-created_at")
            .first()
        )
        if tx is None or not tx.receipt_file:
            raise DomainError("Dekont yok.", code="NOT_FOUND", status_code=404)
        return FileResponse(tx.receipt_file.open("rb"), as_attachment=False, filename=tx.receipt_file.name)
