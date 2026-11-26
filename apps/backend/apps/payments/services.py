"""Orchestrate B2C iyzico Checkout Form: initiate → callback → cancel/refund → webhook."""

from __future__ import annotations

import logging
from decimal import Decimal
from typing import Any
from urllib.parse import urlencode

from django.conf import settings
from django.db import transaction
from django.http import HttpResponseRedirect
from django.utils import timezone

from apps.commerce.models import B2cOrder
from apps.commerce.services import (
    fail_b2c_pending_payment_order,
    finalize_b2c_order_after_payment,
    submit_b2c_order,
)
from config.exceptions import DomainError

from .iyzico_client import (
    IyzicoNotConfigured,
    cancel_payment,
    initialize_checkout_form,
    refund_payment_item,
    retrieve_checkout_form,
)
from .models import PaymentTransaction, RefundLog, RefundRequest
from .payload_builder import build_checkout_form_request

logger = logging.getLogger(__name__)


def _storefront_result_url(*, success: bool, order_no: str, reason: str = "") -> str:
    base = getattr(settings, "FRONTEND_STOREFRONT_URL", "http://localhost:3000").rstrip("/")
    path = "/odeme-basarili" if success else "/odeme-hatali"
    qs = urlencode({"orderNo": order_no, **({"reason": reason} if reason else {})})
    return f"{base}{path}?{qs}"


def _client_ip(request) -> str:
    forwarded = (request.META.get("HTTP_X_FORWARDED_FOR") or "").split(",")[0].strip()
    return forwarded or request.META.get("REMOTE_ADDR") or "127.0.0.1"


def _wrap_iyzico_call(fn, *args, **kwargs):
    try:
        return fn(*args, **kwargs)
    except IyzicoNotConfigured as exc:
        raise DomainError(str(exc), code="IYZICO_NOT_CONFIGURED", status_code=503) from exc


def _apply_card_fields(tx: PaymentTransaction, retrieve: dict[str, Any]) -> list[str]:
    fields: list[str] = []
    installment = retrieve.get("installment")
    if installment is not None:
        try:
            tx.installment = int(installment)
            fields.append("installment")
        except (TypeError, ValueError):
            pass
    for src, dest in (
        ("binNumber", "bin_number"),
        ("lastFourDigits", "last_four_digits"),
        ("authCode", "auth_code"),
        ("cardType", "card_type"),
        ("cardAssociation", "card_association"),
        ("cardFamily", "card_family"),
    ):
        val = retrieve.get(src)
        if val:
            setattr(tx, dest, str(val)[: getattr(tx._meta.get_field(dest), "max_length", 64)])
            fields.append(dest)
    if retrieve.get("price") is not None:
        try:
            tx.base_price = Decimal(str(retrieve.get("price")))
            fields.append("base_price")
        except Exception:
            pass
    items = retrieve.get("itemTransactions") or retrieve.get("paymentItems") or []
    if isinstance(items, list) and items:
        tx.item_transactions = items
        fields.append("item_transactions")
    err = retrieve.get("errorMessage") or retrieve.get("errorCode") or ""
    if err:
        tx.error_message = str(err)[:2000]
        fields.append("error_message")
    return fields


def _emit_payment_failed_mail(order: B2cOrder, *, reason: str = "") -> None:
    try:
        from apps.mail.events import emit_payment_failed

        emit_payment_failed(
            recipient=order.customer_email or "",
            customer_name=order.customer_name or "",
            order_no=order.order_no,
            amount=str(order.grand_total_try),
            currency="TRY",
            error_message=reason or "Ödeme tamamlanamadı",
        )
    except Exception:
        logger.exception("payment_failed mail emit failed for %s", order.order_no)


def _emit_payment_refunded_mail(order: B2cOrder, *, refund_amount: Decimal, kind: str) -> None:
    try:
        from apps.mail.events import emit_payment_refunded

        emit_payment_refunded(
            recipient=order.customer_email or "",
            customer_name=order.customer_name or "",
            order_no=order.order_no,
            refund_amount=str(refund_amount),
            currency="TRY",
            kind=kind,
        )
    except Exception:
        logger.exception("payment_refunded mail emit failed for %s", order.order_no)


def _mark_order_refunded(order: B2cOrder, *, full: bool) -> None:
    if not full:
        return
    if order.status in (B2cOrder.Status.CANCELLED, B2cOrder.Status.REFUNDED):
        return
    order.status = B2cOrder.Status.REFUNDED
    order.save(update_fields=["status", "updated_at"])


@transaction.atomic
def initiate_iyzico_checkout(*, user, payload: dict, request) -> dict[str, Any]:
    if not getattr(settings, "ENABLE_IYZICO_PAYMENTS", False):
        raise DomainError(
            "iyzico ödeme modülü bu kurulumda etkin değil.",
            code="IYZICO_MODULE_DISABLED",
            status_code=503,
        )
    order = submit_b2c_order(user=user, payload=payload, awaiting_payment=True)
    tx = PaymentTransaction.objects.create(
        order=order,
        provider=PaymentTransaction.Provider.IYZICO,
        conversation_id=order.order_no,
        status=PaymentTransaction.Status.INIT,
        price=order.grand_total_try,
        paid_price=order.grand_total_try,
        currency="TRY",
    )

    body = build_checkout_form_request(order=order, buyer_ip=_client_ip(request))
    try:
        response = _wrap_iyzico_call(initialize_checkout_form, body)
    except DomainError:
        fail_b2c_pending_payment_order(order=order, actor=user)
        tx.status = PaymentTransaction.Status.FAILURE
        tx.error_message = "initialize_failed"
        tx.raw_initialize_response = {"error": "initialize_failed"}
        tx.save(update_fields=["status", "error_message", "raw_initialize_response", "updated_at"])
        _emit_payment_failed_mail(order, reason="Ödeme başlatılamadı")
        raise

    token = response.get("token") or ""
    payment_page_url = response.get("paymentPageUrl") or ""
    if not token or not payment_page_url:
        fail_b2c_pending_payment_order(order=order, actor=user)
        tx.status = PaymentTransaction.Status.FAILURE
        tx.raw_initialize_response = response
        tx.error_message = response.get("errorMessage") or "incomplete_init"
        tx.save(
            update_fields=["status", "raw_initialize_response", "error_message", "updated_at"]
        )
        _emit_payment_failed_mail(order, reason=tx.error_message)
        raise DomainError(
            "iyzico ödeme sayfası URL/token dönmedi.",
            code="IYZICO_INIT_INCOMPLETE",
            status_code=502,
        )

    tx.token = token
    tx.payment_page_url = payment_page_url
    tx.status = PaymentTransaction.Status.REDIRECTED
    tx.raw_initialize_response = response
    tx.save(
        update_fields=[
            "token",
            "payment_page_url",
            "status",
            "raw_initialize_response",
            "updated_at",
        ]
    )

    return {
        "orderNo": order.order_no,
        "conversationId": order.order_no,
        "token": token,
        "paymentPageUrl": payment_page_url,
        "checkoutFormContent": response.get("checkoutFormContent") or "",
        "tokenExpireTime": response.get("tokenExpireTime"),
    }


@transaction.atomic
def handle_iyzico_callback(*, token: str, raw_payload: dict | None = None) -> HttpResponseRedirect:
    if not token:
        return HttpResponseRedirect(_storefront_result_url(success=False, order_no="", reason="missing_token"))

    tx = (
        PaymentTransaction.objects.select_for_update()
        .select_related("order")
        .filter(token=token, provider=PaymentTransaction.Provider.IYZICO)
        .first()
    )
    if tx is None:
        logger.warning("iyzico callback token not found: %s", token)
        return HttpResponseRedirect(
            _storefront_result_url(success=False, order_no="", reason="unknown_token")
        )

    if raw_payload is not None:
        tx.raw_callback_payload = raw_payload
        tx.save(update_fields=["raw_callback_payload", "updated_at"])

    if tx.status == PaymentTransaction.Status.SUCCESS:
        return HttpResponseRedirect(
            _storefront_result_url(success=True, order_no=tx.order.order_no)
        )
    if tx.status in (
        PaymentTransaction.Status.FAILURE,
        PaymentTransaction.Status.CANCELLED,
        PaymentTransaction.Status.REFUNDED,
    ):
        return HttpResponseRedirect(
            _storefront_result_url(success=False, order_no=tx.order.order_no, reason="failed")
        )

    try:
        retrieve = _wrap_iyzico_call(retrieve_checkout_form, token)
    except DomainError as exc:
        logger.exception("iyzico retrieve failed for %s", tx.conversation_id)
        tx.raw_retrieve_response = {"error": str(exc)}
        tx.status = PaymentTransaction.Status.FAILURE
        tx.error_message = str(exc)
        tx.save(update_fields=["raw_retrieve_response", "status", "error_message", "updated_at"])
        fail_b2c_pending_payment_order(order=tx.order)
        _emit_payment_failed_mail(tx.order, reason=str(exc))
        return HttpResponseRedirect(
            _storefront_result_url(success=False, order_no=tx.order.order_no, reason="retrieve_error")
        )

    resp_conversation = retrieve.get("conversationId") or ""
    if resp_conversation and resp_conversation != tx.conversation_id:
        logger.error(
            "iyzico conversationId mismatch: stored=%s got=%s",
            tx.conversation_id,
            resp_conversation,
        )
        tx.raw_retrieve_response = retrieve
        tx.status = PaymentTransaction.Status.FAILURE
        tx.save(update_fields=["raw_retrieve_response", "status", "updated_at"])
        fail_b2c_pending_payment_order(order=tx.order)
        _emit_payment_failed_mail(tx.order, reason="conversation_mismatch")
        return HttpResponseRedirect(
            _storefront_result_url(success=False, order_no=tx.order.order_no, reason="mismatch")
        )

    payment_status = (retrieve.get("paymentStatus") or "").upper()
    payment_id = str(retrieve.get("paymentId") or "")
    paid_price = retrieve.get("paidPrice")
    tx.raw_retrieve_response = retrieve
    tx.payment_id = payment_id
    card_fields = _apply_card_fields(tx, retrieve)
    if paid_price is not None:
        try:
            tx.paid_price = Decimal(str(paid_price))
        except Exception:
            pass

    update_fields = [
        "raw_retrieve_response",
        "payment_id",
        "paid_price",
        "status",
        "updated_at",
        *card_fields,
    ]

    if payment_status == "SUCCESS" and (retrieve.get("status") or "").lower() == "success":
        tx.status = PaymentTransaction.Status.SUCCESS
        tx.save(update_fields=update_fields)
        finalize_b2c_order_after_payment(order=tx.order)
        return HttpResponseRedirect(
            _storefront_result_url(success=True, order_no=tx.order.order_no)
        )

    tx.status = PaymentTransaction.Status.FAILURE
    tx.save(update_fields=update_fields)
    fail_b2c_pending_payment_order(order=tx.order)
    _emit_payment_failed_mail(tx.order, reason=payment_status or tx.error_message or "failure")
    return HttpResponseRedirect(
        _storefront_result_url(
            success=False,
            order_no=tx.order.order_no,
            reason=payment_status or "failure",
        )
    )


@transaction.atomic
def handle_iyzico_webhook(*, payload: dict) -> dict[str, Any]:
    """
    Secondary confirmation + panel-side cancel/refund sync.
    Primary authority for first-time success remains CF retrieve on callback.
    """
    payment_id = str(payload.get("paymentId") or "")
    conversation_id = str(
        payload.get("paymentConversationId") or payload.get("conversationId") or ""
    )
    status = (payload.get("status") or payload.get("iyziEventType") or "").upper()
    event_type = (payload.get("iyziEventType") or payload.get("eventType") or "").upper()

    tx = None
    if payment_id:
        tx = (
            PaymentTransaction.objects.select_for_update()
            .select_related("order")
            .filter(payment_id=payment_id, provider=PaymentTransaction.Provider.IYZICO)
            .first()
        )
    if tx is None and conversation_id:
        tx = (
            PaymentTransaction.objects.select_for_update()
            .select_related("order")
            .filter(conversation_id=conversation_id, provider=PaymentTransaction.Provider.IYZICO)
            .first()
        )

    if tx is None:
        logger.info("iyzico webhook for unknown payment: %s", payload)
        return {"ok": True, "matched": False}

    tx.raw_webhook_payload = payload
    update_fields = ["raw_webhook_payload", "updated_at"]

    # Panel refund / cancel notifications
    if any(k in event_type or k in status for k in ("REFUND", "CANCEL", "CHARGEBACK")):
        amount_raw = payload.get("refundPrice") or payload.get("price") or payload.get("paidPrice")
        try:
            amount = Decimal(str(amount_raw)) if amount_raw is not None else tx.paid_price
        except Exception:
            amount = tx.refundable_amount
        if "CANCEL" in event_type or "CANCEL" in status:
            tx.status = PaymentTransaction.Status.CANCELLED
            tx.refunded_amount = tx.paid_price
        else:
            tx.refunded_amount = min(tx.paid_price, tx.refunded_amount + amount)
            tx.status = (
                PaymentTransaction.Status.REFUNDED
                if tx.refunded_amount >= tx.paid_price
                else PaymentTransaction.Status.PARTIAL_REFUNDED
            )
        update_fields.extend(["status", "refunded_amount"])
        tx.save(update_fields=update_fields)
        _mark_order_refunded(tx.order, full=tx.status in (
            PaymentTransaction.Status.REFUNDED,
            PaymentTransaction.Status.CANCELLED,
        ))
        _emit_payment_refunded_mail(tx.order, refund_amount=amount, kind=event_type or status)
        return {"ok": True, "matched": True, "synced": "refund_or_cancel"}

    if status == "SUCCESS" and tx.status != PaymentTransaction.Status.SUCCESS:
        if tx.token:
            try:
                retrieve = _wrap_iyzico_call(retrieve_checkout_form, tx.token)
                tx.raw_retrieve_response = retrieve
                update_fields.append("raw_retrieve_response")
                update_fields.extend(_apply_card_fields(tx, retrieve))
                if (retrieve.get("paymentStatus") or "").upper() == "SUCCESS":
                    tx.status = PaymentTransaction.Status.SUCCESS
                    if retrieve.get("paymentId"):
                        tx.payment_id = str(retrieve["paymentId"])
                        update_fields.append("payment_id")
                    update_fields.append("status")
                    tx.save(update_fields=list(dict.fromkeys(update_fields)))
                    finalize_b2c_order_after_payment(order=tx.order)
                    return {"ok": True, "matched": True, "finalized": True}
            except DomainError:
                logger.exception("webhook retrieve failed for %s", tx.conversation_id)
        tx.save(update_fields=update_fields)
        return {"ok": True, "matched": True, "finalized": False}

    if status == "FAILURE" and tx.status not in (
        PaymentTransaction.Status.SUCCESS,
        PaymentTransaction.Status.FAILURE,
        PaymentTransaction.Status.CANCELLED,
        PaymentTransaction.Status.REFUNDED,
    ):
        tx.status = PaymentTransaction.Status.FAILURE
        update_fields.append("status")
        tx.save(update_fields=update_fields)
        fail_b2c_pending_payment_order(order=tx.order)
        _emit_payment_failed_mail(tx.order, reason="webhook_failure")
        return {"ok": True, "matched": True, "failed": True}

    tx.save(update_fields=update_fields)
    return {"ok": True, "matched": True}


def _assert_cancellable(tx: PaymentTransaction) -> None:
    if tx.status != PaymentTransaction.Status.SUCCESS:
        raise DomainError(
            "Yalnızca başarılı ödemeler iptal/iade edilebilir.",
            code="PAYMENT_NOT_REFUNDABLE",
            status_code=400,
        )
    if not tx.payment_id:
        raise DomainError(
            "iyzico paymentId eksik; iptal/iade yapılamaz.",
            code="PAYMENT_ID_MISSING",
            status_code=400,
        )


@transaction.atomic
def cancel_payment_transaction(
    *,
    payment: PaymentTransaction,
    actor=None,
    ip: str = "127.0.0.1",
    refund_request: RefundRequest | None = None,
) -> RefundLog:
    payment = (
        PaymentTransaction.objects.select_for_update()
        .select_related("order")
        .get(pk=payment.pk)
    )
    _assert_cancellable(payment)
    if payment.refunded_amount > 0:
        raise DomainError(
            "Kısmi iade yapılmış işlemde Cancel kullanılamaz; Refund kullanın.",
            code="USE_REFUND_API",
            status_code=400,
        )

    response = _wrap_iyzico_call(
        cancel_payment,
        payment_id=payment.payment_id,
        ip=ip,
        conversation_id=payment.conversation_id,
    )
    ok = (response.get("status") or "").lower() == "success"
    log = RefundLog.objects.create(
        payment=payment,
        refund_request=refund_request,
        action=RefundLog.Action.CANCEL,
        status=RefundLog.Status.SUCCESS if ok else RefundLog.Status.FAILURE,
        amount=payment.paid_price,
        iyzico_payment_id=payment.payment_id,
        raw_response=response,
        error_message="" if ok else (response.get("errorMessage") or "cancel_failed"),
        actor=actor,
    )
    if not ok:
        raise DomainError(
            log.error_message or "iyzico iptal reddetti.",
            code="IYZICO_CANCEL_FAILED",
            status_code=502,
        )

    payment.status = PaymentTransaction.Status.CANCELLED
    payment.refunded_amount = payment.paid_price
    payment.save(update_fields=["status", "refunded_amount", "updated_at"])
    _mark_order_refunded(payment.order, full=True)
    if refund_request:
        refund_request.status = RefundRequest.Status.COMPLETED
        refund_request.reviewed_by = actor
        refund_request.reviewed_at = timezone.now()
        refund_request.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
    _emit_payment_refunded_mail(payment.order, refund_amount=payment.paid_price, kind="CANCEL")
    return log


@transaction.atomic
def refund_payment_transaction(
    *,
    payment: PaymentTransaction,
    amount: Decimal | None = None,
    payment_transaction_id: str = "",
    actor=None,
    ip: str = "127.0.0.1",
    refund_request: RefundRequest | None = None,
) -> RefundLog:
    payment = (
        PaymentTransaction.objects.select_for_update()
        .select_related("order")
        .get(pk=payment.pk)
    )
    _assert_cancellable(payment)

    refund_amt = amount if amount is not None else payment.refundable_amount
    refund_amt = Decimal(str(refund_amt)).quantize(Decimal("0.01"))
    if refund_amt <= 0:
        raise DomainError("İade tutarı geçersiz.", code="INVALID_REFUND_AMOUNT", status_code=400)
    if refund_amt > payment.refundable_amount:
        raise DomainError(
            f"İade edilebilir tutar aşıldı (max {payment.refundable_amount}).",
            code="REFUND_EXCEEDS_BALANCE",
            status_code=400,
        )

    item_tx_id = (payment_transaction_id or "").strip()
    if not item_tx_id:
        items = payment.item_transactions or []
        if items and isinstance(items[0], dict):
            item_tx_id = str(
                items[0].get("paymentTransactionId")
                or items[0].get("payment_transaction_id")
                or ""
            )
    if not item_tx_id:
        raise DomainError(
            "Kırılımlı iade için paymentTransactionId gerekli. "
            "Ödeme kaydında itemTransactions bulunamadı.",
            code="PAYMENT_TX_ID_MISSING",
            status_code=400,
        )

    response = _wrap_iyzico_call(
        refund_payment_item,
        payment_transaction_id=item_tx_id,
        price=refund_amt,
        ip=ip,
        conversation_id=payment.conversation_id,
        currency=payment.currency or "TRY",
    )
    ok = (response.get("status") or "").lower() == "success"
    log = RefundLog.objects.create(
        payment=payment,
        refund_request=refund_request,
        action=RefundLog.Action.REFUND,
        status=RefundLog.Status.SUCCESS if ok else RefundLog.Status.FAILURE,
        amount=refund_amt,
        payment_transaction_id=item_tx_id,
        iyzico_payment_id=payment.payment_id,
        raw_response=response,
        error_message="" if ok else (response.get("errorMessage") or "refund_failed"),
        actor=actor,
    )
    if not ok:
        raise DomainError(
            log.error_message or "iyzico iade reddetti.",
            code="IYZICO_REFUND_FAILED",
            status_code=502,
        )

    payment.refunded_amount = (payment.refunded_amount + refund_amt).quantize(Decimal("0.01"))
    payment.status = (
        PaymentTransaction.Status.REFUNDED
        if payment.refunded_amount >= payment.paid_price
        else PaymentTransaction.Status.PARTIAL_REFUNDED
    )
    payment.save(update_fields=["refunded_amount", "status", "updated_at"])
    _mark_order_refunded(
        payment.order, full=payment.status == PaymentTransaction.Status.REFUNDED
    )
    if refund_request:
        refund_request.status = RefundRequest.Status.COMPLETED
        refund_request.reviewed_by = actor
        refund_request.reviewed_at = timezone.now()
        refund_request.save(update_fields=["status", "reviewed_by", "reviewed_at", "updated_at"])
    _emit_payment_refunded_mail(payment.order, refund_amount=refund_amt, kind="REFUND")
    return log


@transaction.atomic
def create_refund_request(
    *,
    user,
    order: B2cOrder,
    kind: str = "REFUND",
    reason: str = "",
    requested_amount: Decimal | None = None,
) -> RefundRequest:
    owner_id = order.created_by_id or getattr(order.customer, "user_id", None)
    if owner_id != getattr(user, "id", None):
        raise DomainError("Bu siparişe erişim yok.", code="FORBIDDEN", status_code=403)
    if order.status in (B2cOrder.Status.CANCELLED, B2cOrder.Status.REFUNDED):
        raise DomainError(
            "Bu sipariş için iade/iptal talebi açılamaz.",
            code="ORDER_NOT_ELIGIBLE",
            status_code=400,
        )
    if RefundRequest.objects.filter(
        order=order, status=RefundRequest.Status.PENDING
    ).exists():
        raise DomainError(
            "Bekleyen bir iade/iptal talebiniz zaten var.",
            code="REFUND_REQUEST_EXISTS",
            status_code=409,
        )
    payment = (
        PaymentTransaction.objects.filter(
            order=order, status=PaymentTransaction.Status.SUCCESS
        )
        .order_by("-created_at")
        .first()
    )
    return RefundRequest.objects.create(
        order=order,
        payment=payment,
        kind=kind if kind in RefundRequest.Kind.values else RefundRequest.Kind.REFUND,
        status=RefundRequest.Status.PENDING,
        requested_amount=requested_amount,
        reason=reason or "",
        requested_by=user,
    )
