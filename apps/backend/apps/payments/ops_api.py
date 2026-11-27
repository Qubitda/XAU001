"""OPS / B2B payment provider settings, transactions, cancel/refund, refund requests."""

from __future__ import annotations

from decimal import Decimal

from django.utils import timezone
from rest_framework import serializers
from rest_framework.permissions import IsAuthenticated
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.authorization.permissions import HasPortalPermission
from apps.common.responses import envelope_response
from apps.mail.crypto import encrypt_secret
from apps.organizations.selectors import resolve_tenant_context
from config.exceptions import DomainError

from .bank_transfer import (
    approve_bank_transfer,
    complete_manual_bank_refund,
    reject_bank_transfer,
    serialize_bank_account,
)
from .models import (
    PaymentBankAccount,
    PaymentProviderSetting,
    PaymentTransaction,
    RefundLog,
    RefundRequest,
)
from .iyzico_client import test_iyzico_connection
from .services import cancel_payment_transaction, refund_payment_transaction


def _client_ip(request) -> str:
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    return forwarded or request.META.get("REMOTE_ADDR") or "127.0.0.1"


def _ser_provider(row: PaymentProviderSetting) -> dict:
    return {
        "id": str(row.id),
        "organizationId": str(row.organization_id) if row.organization_id else None,
        "provider": row.provider,
        "baseUrl": row.base_url,
        "callbackBaseUrl": row.callback_base_url,
        "isSandbox": row.is_sandbox,
        "passInstallmentFeeToCustomer": row.pass_installment_fee_to_customer,
        "isActive": row.is_active,
        "hasApiKey": bool(row.api_key_ciphertext),
        "hasSecretKey": bool(row.secret_key_ciphertext),
        "updatedAt": row.updated_at.isoformat(),
    }


def _ser_tx(tx: PaymentTransaction) -> dict:
    receipt_url = None
    if tx.receipt_file:
        receipt_url = f"/api/v1/ops/payments/transactions/{tx.id}/receipt"
    return {
        "id": str(tx.id),
        "orderNo": tx.order.order_no,
        "orderStatus": tx.order.status,
        "provider": tx.provider,
        "conversationId": tx.conversation_id,
        "paymentId": tx.payment_id,
        "status": tx.status,
        "price": str(tx.price),
        "basePrice": str(tx.base_price),
        "paidPrice": str(tx.paid_price),
        "refundedAmount": str(tx.refunded_amount),
        "refundableAmount": str(tx.refundable_amount),
        "currency": tx.currency,
        "installment": tx.installment,
        "binNumber": tx.bin_number,
        "lastFourDigits": tx.last_four_digits,
        "cardType": tx.card_type,
        "cardAssociation": tx.card_association,
        "cardFamily": tx.card_family,
        "authCode": tx.auth_code,
        "itemTransactions": tx.item_transactions or [],
        "transferReference": tx.transfer_reference,
        "bankName": tx.bank_name_snapshot,
        "iban": tx.iban_snapshot,
        "accountHolder": tx.account_holder_snapshot,
        "receiptStatus": tx.receipt_status,
        "receiptUrl": receipt_url,
        "refundIban": tx.refund_iban,
        "refundAccountHolder": tx.refund_account_holder,
        "errorMessage": tx.error_message,
        "createdAt": tx.created_at.isoformat(),
        "updatedAt": tx.updated_at.isoformat(),
    }


def _ser_refund_request(r: RefundRequest) -> dict:
    return {
        "id": str(r.id),
        "orderNo": r.order.order_no,
        "paymentId": str(r.payment_id) if r.payment_id else None,
        "kind": r.kind,
        "status": r.status,
        "requestedAmount": str(r.requested_amount) if r.requested_amount is not None else None,
        "reason": r.reason,
        "adminNote": r.admin_note,
        "createdAt": r.created_at.isoformat(),
        "reviewedAt": r.reviewed_at.isoformat() if r.reviewed_at else None,
    }


def _ser_refund_log(log: RefundLog) -> dict:
    return {
        "id": str(log.id),
        "action": log.action,
        "status": log.status,
        "amount": str(log.amount),
        "paymentTransactionId": log.payment_transaction_id,
        "errorMessage": log.error_message,
        "createdAt": log.created_at.isoformat(),
    }


class ProviderSettingSerializer(serializers.Serializer):
    organizationId = serializers.UUIDField(required=False, allow_null=True)
    apiKey = serializers.CharField(max_length=512, required=False, allow_blank=True, default="")
    secretKey = serializers.CharField(max_length=512, required=False, allow_blank=True, default="")
    baseUrl = serializers.CharField(max_length=255, required=False, allow_blank=True, default="")
    callbackBaseUrl = serializers.URLField(required=False, allow_blank=True, default="")
    isSandbox = serializers.BooleanField(default=True)
    passInstallmentFeeToCustomer = serializers.BooleanField(default=True)
    isActive = serializers.BooleanField(default=True)


class BankAccountSerializer(serializers.Serializer):
    organizationId = serializers.UUIDField(required=False, allow_null=True)
    bankName = serializers.CharField(max_length=120)
    accountHolder = serializers.CharField(max_length=160)
    iban = serializers.CharField(max_length=34)
    branchCode = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    accountNumber = serializers.CharField(max_length=64, required=False, allow_blank=True, default="")
    currency = serializers.CharField(max_length=8, default="TRY")
    logoUrl = serializers.URLField(required=False, allow_blank=True, default="")
    isActive = serializers.BooleanField(default=True)
    sortOrder = serializers.IntegerField(required=False, default=0)


class RefundActionSerializer(serializers.Serializer):
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    paymentTransactionId = serializers.CharField(
        max_length=64, required=False, allow_blank=True, default=""
    )


class OpsPaymentProviderSettingsView(APIView):
    permission_classes = [IsAuthenticated, HasPortalPermission]
    required_permission = "payments:manage"

    def get(self, request: Request):
        ctx = resolve_tenant_context(request)
        qs = PaymentProviderSetting.objects.select_related("organization").filter(provider="IYZICO")
        if not ctx.is_ops:
            if ctx.organization is None:
                raise DomainError("Organizasyon gerekli.", code="ORG_REQUIRED", status_code=403)
            qs = qs.filter(organization=ctx.organization)
        else:
            scope = (request.query_params.get("scope") or "platform").lower()
            if scope == "platform":
                qs = qs.filter(organization__isnull=True)
            elif scope == "org" and request.query_params.get("organizationId"):
                qs = qs.filter(organization_id=request.query_params.get("organizationId"))
        return envelope_response([_ser_provider(r) for r in qs[:50]], request)

    def post(self, request: Request):
        ctx = resolve_tenant_context(request)
        ser = ProviderSettingSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        org_id = d.get("organizationId")
        if not ctx.is_ops:
            if ctx.organization is None:
                raise DomainError("Organizasyon gerekli.", code="ORG_REQUIRED", status_code=403)
            org_id = ctx.organization.id
        else:
            # Super Admin default: platform (null org) unless explicitly set
            if "organizationId" not in request.data:
                org_id = None

        base_url = (d.get("baseUrl") or "").strip()
        is_sandbox = d.get("isSandbox", True)
        if not base_url:
            base_url = "sandbox-api.iyzipay.com" if is_sandbox else "api.iyzipay.com"

        if d.get("isActive"):
            PaymentProviderSetting.objects.filter(
                provider="IYZICO", organization_id=org_id, is_active=True
            ).update(is_active=False)

        row = PaymentProviderSetting(
            organization_id=org_id,
            provider="IYZICO",
            base_url=base_url,
            callback_base_url=d.get("callbackBaseUrl") or "",
            is_sandbox=is_sandbox,
            pass_installment_fee_to_customer=d.get("passInstallmentFeeToCustomer", True),
            is_active=d.get("isActive", True),
        )
        if d.get("apiKey"):
            row.api_key_ciphertext = encrypt_secret(d["apiKey"])
        if d.get("secretKey"):
            row.secret_key_ciphertext = encrypt_secret(d["secretKey"])

        # Upsert: keep latest keys if blank on update of existing
        existing = (
            PaymentProviderSetting.objects.filter(provider="IYZICO", organization_id=org_id)
            .order_by("-updated_at")
            .first()
        )
        if existing and not d.get("apiKey"):
            row.api_key_ciphertext = existing.api_key_ciphertext
        if existing and not d.get("secretKey"):
            row.secret_key_ciphertext = existing.secret_key_ciphertext
        row.save()
        return envelope_response(_ser_provider(row), request, status=201)


class OpsPaymentProviderTestView(APIView):
    permission_classes = [IsAuthenticated, HasPortalPermission]
    required_permission = "payments:manage"

    def post(self, request: Request):
        ctx = resolve_tenant_context(request)
        org_id = None
        if not ctx.is_ops:
            if ctx.organization is None:
                raise DomainError("Organizasyon gerekli.", code="ORG_REQUIRED", status_code=403)
            org_id = str(ctx.organization.id)
        elif request.data.get("organizationId"):
            org_id = str(request.data.get("organizationId"))

        result = test_iyzico_connection(organization_id=org_id)
        return envelope_response(result, request)


class OpsPaymentTransactionsView(APIView):
    permission_classes = [IsAuthenticated, HasPortalPermission]
    required_permission = "payments:manage"

    def get(self, request: Request):
        ctx = resolve_tenant_context(request)
        qs = PaymentTransaction.objects.select_related("order").all()
        if not ctx.is_ops:
            # B2C iyzico is platform-scoped; B2B sees empty until submerchant linkage exists.
            return envelope_response([], request)
        status_f = (request.query_params.get("status") or "").strip().upper()
        if status_f:
            qs = qs.filter(status=status_f)
        provider_f = (request.query_params.get("provider") or "").strip().upper()
        if provider_f:
            qs = qs.filter(provider=provider_f)
        order_no = (request.query_params.get("orderNo") or "").strip()
        if order_no:
            qs = qs.filter(order__order_no__icontains=order_no)
        payment_id = (request.query_params.get("paymentId") or "").strip()
        if payment_id:
            qs = qs.filter(payment_id__icontains=payment_id)
        rows = [_ser_tx(t) for t in qs[:200]]
        return envelope_response(rows, request)


class OpsPaymentTransactionDetailView(APIView):
    permission_classes = [IsAuthenticated, HasPortalPermission]
    required_permission = "payments:manage"

    def get(self, request: Request, payment_id):
        ctx = resolve_tenant_context(request)
        if not ctx.is_ops:
            raise DomainError("OPS yetkisi gerekli.", code="OPS_ONLY", status_code=403)
        tx = (
            PaymentTransaction.objects.select_related("order")
            .filter(id=payment_id)
            .first()
        )
        if tx is None:
            raise DomainError("İşlem bulunamadı.", code="NOT_FOUND", status_code=404)
        logs = [_ser_refund_log(l) for l in tx.refund_logs.all()[:50]]
        reqs = [_ser_refund_request(r) for r in tx.refund_requests.select_related("order")[:20]]
        data = _ser_tx(tx)
        data["refundLogs"] = logs
        data["refundRequests"] = reqs
        return envelope_response(data, request)


class OpsPaymentCancelView(APIView):
    permission_classes = [IsAuthenticated, HasPortalPermission]
    required_permission = "payments:manage"

    def post(self, request: Request, payment_id):
        ctx = resolve_tenant_context(request)
        if not ctx.is_ops:
            raise DomainError("OPS yetkisi gerekli.", code="OPS_ONLY", status_code=403)
        tx = PaymentTransaction.objects.select_related("order").filter(id=payment_id).first()
        if tx is None:
            raise DomainError("İşlem bulunamadı.", code="NOT_FOUND", status_code=404)
        log = cancel_payment_transaction(
            payment=tx, actor=request.user, ip=_client_ip(request)
        )
        return envelope_response(
            {"transaction": _ser_tx(PaymentTransaction.objects.get(pk=tx.pk)), "log": _ser_refund_log(log)},
            request,
        )


class OpsPaymentRefundView(APIView):
    permission_classes = [IsAuthenticated, HasPortalPermission]
    required_permission = "payments:manage"

    def post(self, request: Request, payment_id):
        ctx = resolve_tenant_context(request)
        if not ctx.is_ops:
            raise DomainError("OPS yetkisi gerekli.", code="OPS_ONLY", status_code=403)
        tx = PaymentTransaction.objects.select_related("order").filter(id=payment_id).first()
        if tx is None:
            raise DomainError("İşlem bulunamadı.", code="NOT_FOUND", status_code=404)
        ser = RefundActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        log = refund_payment_transaction(
            payment=tx,
            amount=d.get("amount"),
            payment_transaction_id=d.get("paymentTransactionId") or "",
            actor=request.user,
            ip=_client_ip(request),
        )
        return envelope_response(
            {"transaction": _ser_tx(PaymentTransaction.objects.get(pk=tx.pk)), "log": _ser_refund_log(log)},
            request,
        )


class OpsRefundRequestsView(APIView):
    permission_classes = [IsAuthenticated, HasPortalPermission]
    required_permission = "payments:manage"

    def get(self, request: Request):
        ctx = resolve_tenant_context(request)
        if not ctx.is_ops:
            raise DomainError("OPS yetkisi gerekli.", code="OPS_ONLY", status_code=403)
        qs = RefundRequest.objects.select_related("order", "payment").all()
        status_f = (request.query_params.get("status") or "").strip().upper()
        if status_f:
            qs = qs.filter(status=status_f)
        return envelope_response([_ser_refund_request(r) for r in qs[:100]], request)


class OpsRefundRequestActionSerializer(serializers.Serializer):
    action = serializers.ChoiceField(choices=["APPROVE", "REJECT"])
    adminNote = serializers.CharField(required=False, allow_blank=True, default="")
    amount = serializers.DecimalField(max_digits=14, decimal_places=2, required=False)
    paymentTransactionId = serializers.CharField(
        max_length=64, required=False, allow_blank=True, default=""
    )
    useCancel = serializers.BooleanField(default=False)


class OpsRefundRequestActionView(APIView):
    permission_classes = [IsAuthenticated, HasPortalPermission]
    required_permission = "payments:manage"

    def post(self, request: Request, request_id):
        ctx = resolve_tenant_context(request)
        if not ctx.is_ops:
            raise DomainError("OPS yetkisi gerekli.", code="OPS_ONLY", status_code=403)
        row = (
            RefundRequest.objects.select_related("order", "payment")
            .filter(id=request_id)
            .first()
        )
        if row is None:
            raise DomainError("Talep bulunamadı.", code="NOT_FOUND", status_code=404)
        if row.status != RefundRequest.Status.PENDING:
            raise DomainError("Talep zaten işlenmiş.", code="ALREADY_PROCESSED", status_code=400)

        ser = OpsRefundRequestActionSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        row.admin_note = d.get("adminNote") or ""
        row.reviewed_by = request.user
        row.reviewed_at = timezone.now()

        if d["action"] == "REJECT":
            row.status = RefundRequest.Status.REJECTED
            row.save(
                update_fields=["status", "admin_note", "reviewed_by", "reviewed_at", "updated_at"]
            )
            return envelope_response(_ser_refund_request(row), request)

        row.status = RefundRequest.Status.APPROVED
        row.save(
            update_fields=["status", "admin_note", "reviewed_by", "reviewed_at", "updated_at"]
        )
        if row.payment is None:
            raise DomainError(
                "Talebe bağlı başarılı ödeme kaydı yok.",
                code="NO_PAYMENT",
                status_code=400,
            )
        if row.payment.provider == PaymentTransaction.Provider.BANK_TRANSFER:
            log = complete_manual_bank_refund(
                payment=row.payment,
                actor=request.user,
                amount=d.get("amount") or row.requested_amount,
                refund_iban=row.refund_iban or row.payment.refund_iban,
                refund_account_holder=row.refund_account_holder
                or row.payment.refund_account_holder,
                refund_request=row,
            )
        elif d.get("useCancel") or row.kind == RefundRequest.Kind.CANCEL:
            log = cancel_payment_transaction(
                payment=row.payment,
                actor=request.user,
                ip=_client_ip(request),
                refund_request=row,
            )
        else:
            amount = d.get("amount") or row.requested_amount
            log = refund_payment_transaction(
                payment=row.payment,
                amount=amount,
                payment_transaction_id=d.get("paymentTransactionId") or "",
                actor=request.user,
                ip=_client_ip(request),
                refund_request=row,
            )
        row.refresh_from_db()
        return envelope_response(
            {"request": _ser_refund_request(row), "log": _ser_refund_log(log)}, request
        )


class OpsBankAccountsView(APIView):
    permission_classes = [IsAuthenticated, HasPortalPermission]
    required_permission = "payments:manage"

    def get(self, request: Request):
        ctx = resolve_tenant_context(request)
        qs = PaymentBankAccount.objects.all()
        if not ctx.is_ops:
            if ctx.organization is None:
                raise DomainError("Organizasyon gerekli.", code="ORG_REQUIRED", status_code=403)
            qs = qs.filter(organization=ctx.organization)
        else:
            scope = (request.query_params.get("scope") or "platform").lower()
            if scope == "platform":
                qs = qs.filter(organization__isnull=True)
        return envelope_response([serialize_bank_account(r) for r in qs[:100]], request)

    def post(self, request: Request):
        ctx = resolve_tenant_context(request)
        ser = BankAccountSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        org_id = d.get("organizationId")
        if not ctx.is_ops:
            if ctx.organization is None:
                raise DomainError("Organizasyon gerekli.", code="ORG_REQUIRED", status_code=403)
            org_id = ctx.organization.id
        else:
            if "organizationId" not in request.data:
                org_id = None
        iban = d["iban"].strip().replace(" ", "").upper()
        row = PaymentBankAccount.objects.create(
            organization_id=org_id,
            bank_name=d["bankName"],
            account_holder=d["accountHolder"],
            iban=iban,
            branch_code=d.get("branchCode") or "",
            account_number=d.get("accountNumber") or "",
            currency=d.get("currency") or "TRY",
            logo_url=d.get("logoUrl") or "",
            is_active=d.get("isActive", True),
            sort_order=d.get("sortOrder") or 0,
        )
        return envelope_response(serialize_bank_account(row), request, status=201)


class OpsBankAccountDetailView(APIView):
    permission_classes = [IsAuthenticated, HasPortalPermission]
    required_permission = "payments:manage"

    def patch(self, request: Request, account_id):
        ctx = resolve_tenant_context(request)
        row = PaymentBankAccount.objects.filter(id=account_id).first()
        if row is None:
            raise DomainError("Hesap bulunamadı.", code="NOT_FOUND", status_code=404)
        if not ctx.is_ops and (
            ctx.organization is None or row.organization_id != ctx.organization.id
        ):
            raise DomainError("Yetkisiz.", code="FORBIDDEN", status_code=403)
        ser = BankAccountSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        for src, dest in (
            ("bankName", "bank_name"),
            ("accountHolder", "account_holder"),
            ("branchCode", "branch_code"),
            ("accountNumber", "account_number"),
            ("currency", "currency"),
            ("logoUrl", "logo_url"),
            ("isActive", "is_active"),
            ("sortOrder", "sort_order"),
        ):
            if src in d:
                setattr(row, dest, d[src])
        if "iban" in d:
            row.iban = d["iban"].strip().replace(" ", "").upper()
        row.save()
        return envelope_response(serialize_bank_account(row), request)

    def delete(self, request: Request, account_id):
        ctx = resolve_tenant_context(request)
        row = PaymentBankAccount.objects.filter(id=account_id).first()
        if row is None:
            raise DomainError("Hesap bulunamadı.", code="NOT_FOUND", status_code=404)
        if not ctx.is_ops and (
            ctx.organization is None or row.organization_id != ctx.organization.id
        ):
            raise DomainError("Yetkisiz.", code="FORBIDDEN", status_code=403)
        deleted_id = str(row.id)
        row.delete()
        return envelope_response({"id": deleted_id, "deleted": True}, request)


class OpsBankTransferApproveView(APIView):
    permission_classes = [IsAuthenticated, HasPortalPermission]
    required_permission = "payments:manage"

    def post(self, request: Request, payment_id):
        ctx = resolve_tenant_context(request)
        if not ctx.is_ops:
            raise DomainError("OPS yetkisi gerekli.", code="OPS_ONLY", status_code=403)
        tx = PaymentTransaction.objects.filter(id=payment_id).first()
        if tx is None:
            raise DomainError("İşlem bulunamadı.", code="NOT_FOUND", status_code=404)
        tx = approve_bank_transfer(payment=tx, actor=request.user)
        return envelope_response(_ser_tx(tx), request)


class OpsBankTransferRejectView(APIView):
    permission_classes = [IsAuthenticated, HasPortalPermission]
    required_permission = "payments:manage"

    def post(self, request: Request, payment_id):
        ctx = resolve_tenant_context(request)
        if not ctx.is_ops:
            raise DomainError("OPS yetkisi gerekli.", code="OPS_ONLY", status_code=403)
        tx = PaymentTransaction.objects.filter(id=payment_id).first()
        if tx is None:
            raise DomainError("İşlem bulunamadı.", code="NOT_FOUND", status_code=404)
        reason = (request.data.get("reason") or "").strip()
        tx = reject_bank_transfer(payment=tx, actor=request.user, reason=reason)
        return envelope_response(_ser_tx(tx), request)


class OpsPaymentReceiptFileView(APIView):
    permission_classes = [IsAuthenticated, HasPortalPermission]
    required_permission = "payments:manage"

    def get(self, request: Request, payment_id):
        from django.http import FileResponse

        ctx = resolve_tenant_context(request)
        if not ctx.is_ops:
            raise DomainError("OPS yetkisi gerekli.", code="OPS_ONLY", status_code=403)
        tx = PaymentTransaction.objects.filter(id=payment_id).first()
        if tx is None or not tx.receipt_file:
            raise DomainError("Dekont yok.", code="NOT_FOUND", status_code=404)
        return FileResponse(tx.receipt_file.open("rb"), as_attachment=False, filename=tx.receipt_file.name)


class OpsManualBankRefundView(APIView):
    permission_classes = [IsAuthenticated, HasPortalPermission]
    required_permission = "payments:manage"

    def post(self, request: Request, payment_id):
        ctx = resolve_tenant_context(request)
        if not ctx.is_ops:
            raise DomainError("OPS yetkisi gerekli.", code="OPS_ONLY", status_code=403)
        tx = PaymentTransaction.objects.filter(id=payment_id).first()
        if tx is None:
            raise DomainError("İşlem bulunamadı.", code="NOT_FOUND", status_code=404)
        amount = request.data.get("amount")
        log = complete_manual_bank_refund(
            payment=tx,
            actor=request.user,
            amount=Decimal(str(amount)) if amount not in (None, "") else None,
            refund_iban=request.data.get("refundIban") or "",
            refund_account_holder=request.data.get("refundAccountHolder") or "",
            receipt_file=request.FILES.get("file") or request.FILES.get("receipt"),
        )
        return envelope_response(
            {"transaction": _ser_tx(PaymentTransaction.objects.get(pk=tx.pk)), "log": _ser_refund_log(log)},
            request,
        )
