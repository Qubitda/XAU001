"""Havale / EFT: bank accounts, pending payment, receipt approve/reject, manual refund."""

from __future__ import annotations

import logging
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from apps.commerce.models import B2cOrder
from apps.commerce.services import (
    fail_b2c_pending_payment_order,
    finalize_b2c_order_after_payment,
    submit_b2c_order,
)
from config.exceptions import DomainError

from .models import PaymentBankAccount, PaymentTransaction, RefundLog, RefundRequest

logger = logging.getLogger(__name__)


def serialize_bank_account(acc: PaymentBankAccount) -> dict:
    return {
        "id": str(acc.id),
        "organizationId": str(acc.organization_id) if acc.organization_id else None,
        "bankName": acc.bank_name,
        "accountHolder": acc.account_holder,
        "iban": acc.iban,
        "branchCode": acc.branch_code,
        "accountNumber": acc.account_number,
        "currency": acc.currency,
        "logoUrl": acc.logo_url,
        "isActive": acc.is_active,
        "sortOrder": acc.sort_order,
        "updatedAt": acc.updated_at.isoformat(),
    }


def list_active_bank_accounts(*, organization_id: str | None = None) -> list[PaymentBankAccount]:
    qs = PaymentBankAccount.objects.filter(is_active=True)
    if organization_id:
        org_rows = list(qs.filter(organization_id=organization_id).order_by("sort_order", "bank_name"))
        if org_rows:
            return org_rows
    return list(qs.filter(organization__isnull=True).order_by("sort_order", "bank_name"))


def serialize_transfer_payment(tx: PaymentTransaction) -> dict:
    receipt_url = None
    if tx.receipt_file:
        receipt_url = f"/api/v1/ops/payments/transactions/{tx.id}/receipt"
    return {
        "id": str(tx.id),
        "provider": tx.provider,
        "status": tx.status,
        "transferReference": tx.transfer_reference,
        "paidPrice": str(tx.paid_price),
        "currency": tx.currency,
        "bankName": tx.bank_name_snapshot,
        "iban": tx.iban_snapshot,
        "accountHolder": tx.account_holder_snapshot,
        "receiptStatus": tx.receipt_status,
        "receiptUrl": receipt_url,
        "installment": tx.installment,
        "cardFamily": tx.card_family,
        "lastFourDigits": tx.last_four_digits,
        "basePrice": str(tx.base_price),
        "createdAt": tx.created_at.isoformat(),
    }


@transaction.atomic
def initiate_bank_transfer_checkout(*, user, payload: dict, request=None) -> dict:
    """
    Create B2C order in ODEME_BEKLIYOR + BANK_TRANSFER PaymentTransaction.
    Returns serialized order fields + bankAccounts + transferReference.
    """
    accounts = list_active_bank_accounts()
    if not accounts:
        raise DomainError(
            "Aktif havale hesabı tanımlı değil. OPS → Sistem Ayarları → Banka Hesapları.",
            code="NO_BANK_ACCOUNTS",
            status_code=503,
        )

    # Reuse awaiting_payment path so WorkOrders / webhook defer until OPS approve.
    order = submit_b2c_order(user=user, payload={**payload, "paymentMethod": "BANK_TRANSFER"}, awaiting_payment=True)

    preferred_id = (payload.get("bankAccountId") or "").strip()
    bank = None
    if preferred_id:
        bank = next((a for a in accounts if str(a.id) == preferred_id), None)
    if bank is None:
        bank = accounts[0]

    reference = order.order_no
    tx = PaymentTransaction.objects.create(
        order=order,
        provider=PaymentTransaction.Provider.BANK_TRANSFER,
        conversation_id=f"BT-{order.order_no}",
        status=PaymentTransaction.Status.PENDING,
        price=order.grand_total_try,
        base_price=order.grand_total_try,
        paid_price=order.grand_total_try,
        currency="TRY",
        transfer_reference=reference,
        bank_account=bank,
        bank_name_snapshot=bank.bank_name,
        iban_snapshot=bank.iban,
        account_holder_snapshot=bank.account_holder,
    )

    try:
        from apps.mail.events import emit_bank_transfer_pending

        emit_bank_transfer_pending(
            recipient=order.shipping_email or order.customer.email,
            customer_name=order.shipping_full_name or order.customer.full_name,
            order_no=order.order_no,
            amount=str(order.grand_total_try),
            currency="TRY",
            bank_name=bank.bank_name,
            iban=bank.iban,
            account_holder=bank.account_holder,
            transfer_reference=reference,
        )
    except Exception:
        logger.exception("bank_transfer_pending mail failed for %s", order.order_no)

    from apps.commerce.api import _serialize_b2c_order

    data = _serialize_b2c_order(order)
    data["transferReference"] = reference
    data["bankAccounts"] = [serialize_bank_account(a) for a in accounts]
    data["selectedBankAccountId"] = str(bank.id)
    data["payment"] = serialize_transfer_payment(tx)
    return data


@transaction.atomic
def upload_transfer_receipt(*, user, order: B2cOrder, uploaded_file) -> PaymentTransaction:
    owner_id = order.created_by_id or getattr(order.customer, "user_id", None)
    if owner_id != getattr(user, "id", None):
        raise DomainError("Bu siparişe erişim yok.", code="FORBIDDEN", status_code=403)
    if order.payment_method != "BANK_TRANSFER":
        raise DomainError("Bu sipariş havale değil.", code="NOT_BANK_TRANSFER", status_code=400)
    if order.status != B2cOrder.Status.PENDING_PAYMENT:
        raise DomainError(
            "Yalnızca havale bekleyen siparişlere dekont yüklenebilir.",
            code="INVALID_STATUS",
            status_code=400,
        )
    tx = (
        PaymentTransaction.objects.select_for_update()
        .filter(order=order, provider=PaymentTransaction.Provider.BANK_TRANSFER)
        .order_by("-created_at")
        .first()
    )
    if tx is None:
        raise DomainError("Havale kaydı bulunamadı.", code="NOT_FOUND", status_code=404)

    tx.receipt_file = uploaded_file
    tx.receipt_status = PaymentTransaction.ReceiptStatus.UPLOADED
    tx.receipt_uploaded_at = timezone.now()
    tx.status = PaymentTransaction.Status.RECEIPT_UPLOADED
    tx.save(
        update_fields=[
            "receipt_file",
            "receipt_status",
            "receipt_uploaded_at",
            "status",
            "updated_at",
        ]
    )
    return tx


@transaction.atomic
def approve_bank_transfer(*, payment: PaymentTransaction, actor=None) -> PaymentTransaction:
    payment = (
        PaymentTransaction.objects.select_for_update()
        .select_related("order")
        .get(pk=payment.pk)
    )
    if payment.provider != PaymentTransaction.Provider.BANK_TRANSFER:
        raise DomainError("Kart ödemesi değil, havale onayı kullanın.", code="WRONG_PROVIDER", status_code=400)
    if payment.status not in (
        PaymentTransaction.Status.PENDING,
        PaymentTransaction.Status.RECEIPT_UPLOADED,
    ):
        raise DomainError("Bu işlem onaylanamaz.", code="INVALID_STATUS", status_code=400)

    payment.status = PaymentTransaction.Status.SUCCESS
    payment.receipt_status = PaymentTransaction.ReceiptStatus.APPROVED
    payment.receipt_reviewed_at = timezone.now()
    payment.receipt_reviewed_by = actor
    payment.save(
        update_fields=[
            "status",
            "receipt_status",
            "receipt_reviewed_at",
            "receipt_reviewed_by",
            "updated_at",
        ]
    )
    finalize_b2c_order_after_payment(order=payment.order, actor=actor)
    return payment


@transaction.atomic
def reject_bank_transfer(
    *, payment: PaymentTransaction, actor=None, reason: str = ""
) -> PaymentTransaction:
    payment = (
        PaymentTransaction.objects.select_for_update()
        .select_related("order")
        .get(pk=payment.pk)
    )
    if payment.provider != PaymentTransaction.Provider.BANK_TRANSFER:
        raise DomainError("Yanlış sağlayıcı.", code="WRONG_PROVIDER", status_code=400)

    payment.status = PaymentTransaction.Status.REJECTED
    payment.receipt_status = PaymentTransaction.ReceiptStatus.REJECTED
    payment.error_message = reason or "Havale reddedildi"
    payment.receipt_reviewed_at = timezone.now()
    payment.receipt_reviewed_by = actor
    payment.save(
        update_fields=[
            "status",
            "receipt_status",
            "error_message",
            "receipt_reviewed_at",
            "receipt_reviewed_by",
            "updated_at",
        ]
    )
    fail_b2c_pending_payment_order(order=payment.order, actor=actor)
    return payment


@transaction.atomic
def complete_manual_bank_refund(
    *,
    payment: PaymentTransaction,
    actor=None,
    amount: Decimal | None = None,
    refund_iban: str = "",
    refund_account_holder: str = "",
    receipt_file=None,
    refund_request: RefundRequest | None = None,
) -> RefundLog:
    payment = (
        PaymentTransaction.objects.select_for_update()
        .select_related("order")
        .get(pk=payment.pk)
    )
    if payment.provider != PaymentTransaction.Provider.BANK_TRANSFER:
        raise DomainError("Manuel iade yalnızca havale için.", code="WRONG_PROVIDER", status_code=400)
    if payment.status != PaymentTransaction.Status.SUCCESS:
        raise DomainError("Yalnızca onaylı havaleler iade edilir.", code="INVALID_STATUS", status_code=400)

    amt = Decimal(str(amount if amount is not None else payment.refundable_amount)).quantize(
        Decimal("0.01")
    )
    if amt <= 0 or amt > payment.refundable_amount:
        raise DomainError("İade tutarı geçersiz.", code="INVALID_AMOUNT", status_code=400)

    if refund_iban:
        payment.refund_iban = refund_iban.replace(" ", "").upper()
    if refund_account_holder:
        payment.refund_account_holder = refund_account_holder
    if receipt_file:
        payment.manual_refund_receipt = receipt_file

    payment.refunded_amount = (payment.refunded_amount + amt).quantize(Decimal("0.01"))
    payment.status = (
        PaymentTransaction.Status.REFUNDED
        if payment.refunded_amount >= payment.paid_price
        else PaymentTransaction.Status.PARTIAL_REFUNDED
    )
    payment.save(
        update_fields=[
            "refund_iban",
            "refund_account_holder",
            "manual_refund_receipt",
            "refunded_amount",
            "status",
            "updated_at",
        ]
    )

    if payment.status == PaymentTransaction.Status.REFUNDED:
        order = payment.order
        if order.status not in (B2cOrder.Status.CANCELLED, B2cOrder.Status.REFUNDED):
            order.status = B2cOrder.Status.REFUNDED
            order.save(update_fields=["status", "updated_at"])

    log = RefundLog.objects.create(
        payment=payment,
        refund_request=refund_request,
        action=RefundLog.Action.MANUAL_BANK_REFUND,
        status=RefundLog.Status.SUCCESS,
        amount=amt,
        raw_response={
            "refundIban": payment.refund_iban,
            "refundAccountHolder": payment.refund_account_holder,
        },
        actor=actor,
    )
    if refund_request:
        refund_request.status = RefundRequest.Status.COMPLETED
        refund_request.reviewed_by = actor
        refund_request.reviewed_at = timezone.now()
        refund_request.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])

    try:
        from apps.mail.events import emit_payment_refunded

        emit_payment_refunded(
            recipient=payment.order.shipping_email or payment.order.customer.email,
            customer_name=payment.order.shipping_full_name or "",
            order_no=payment.order.order_no,
            refund_amount=str(amt),
            currency="TRY",
            kind="IBAN_REFUND",
        )
    except Exception:
        logger.exception("manual refund mail failed")

    return log
