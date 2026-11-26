"""
Event-driven mail dispatch.

Business code calls `emit_mail_event(...)` AFTER DB work; delivery is queued via
`transaction.on_commit` so SMTP failures never roll back the primary transaction.
"""

from __future__ import annotations

import logging
from typing import Any

from django.db import transaction

from .constants import (
    BANK_TRANSFER_PENDING,
    EMAIL_VERIFICATION,
    ORDER_CANCELLED,
    ORDER_CREATED,
    PASSWORD_RESET,
    PAYMENT_FAILED,
    PAYMENT_REFUNDED,
    PAYMENT_SUCCESS,
    WELCOME,
)
from .models import MailLog

logger = logging.getLogger(__name__)


def emit_mail_event(
    *,
    template_key: str,
    recipient: str,
    context: dict[str, Any] | None = None,
    organization_id: str | None = None,
) -> str | None:
    """
    Create a QUEUED MailLog and enqueue Celery delivery after commit.
    Returns mail_log id (str) or None if recipient empty.
    """
    recipient = (recipient or "").strip()
    if not recipient:
        logger.warning("emit_mail_event skipped: empty recipient key=%s", template_key)
        return None

    ctx = dict(context or {})
    log = MailLog.objects.create(
        organization_id=organization_id or None,
        recipient=recipient,
        template_key=template_key,
        status=MailLog.Status.QUEUED,
        context_snapshot=ctx,
    )
    mail_log_id = str(log.id)

    def _enqueue() -> None:
        from django.conf import settings

        from .service import MailService
        from .tasks import send_transactional_email_task

        # Unit tests / eager mode: deliver inline after commit (no broker required).
        if getattr(settings, "TESTING", False) or getattr(
            settings, "CELERY_TASK_ALWAYS_EAGER", False
        ):
            MailService().send(
                template_key=template_key,
                recipient=recipient,
                context=ctx,
                organization_id=organization_id,
                mail_log_id=mail_log_id,
            )
            return

        try:
            send_transactional_email_task.delay(
                template_key=template_key,
                recipient=recipient,
                context=ctx,
                organization_id=organization_id,
                mail_log_id=mail_log_id,
            )
        except Exception:
            # Broker down (common on local Windows Redis 3.x): sync fallback.
            logger.exception(
                "Celery enqueue failed; falling back to sync mail send log=%s", mail_log_id
            )
            MailService().send(
                template_key=template_key,
                recipient=recipient,
                context=ctx,
                organization_id=organization_id,
                mail_log_id=mail_log_id,
            )

    transaction.on_commit(_enqueue)
    return mail_log_id


# ── Typed helpers (listeners call these from domain services) ─────────────


def emit_welcome(*, recipient: str, customer_name: str, verify_url: str = "", organization_id: str | None = None) -> str | None:
    return emit_mail_event(
        template_key=WELCOME,
        recipient=recipient,
        organization_id=organization_id,
        context={
            "customer_name": customer_name,
            "verify_url": verify_url,
        },
    )


def emit_email_verification(*, recipient: str, customer_name: str, verify_url: str, organization_id: str | None = None) -> str | None:
    return emit_mail_event(
        template_key=EMAIL_VERIFICATION,
        recipient=recipient,
        organization_id=organization_id,
        context={
            "customer_name": customer_name,
            "verify_url": verify_url,
        },
    )


def emit_password_reset(*, recipient: str, customer_name: str, reset_url: str, organization_id: str | None = None) -> str | None:
    return emit_mail_event(
        template_key=PASSWORD_RESET,
        recipient=recipient,
        organization_id=organization_id,
        context={
            "customer_name": customer_name,
            "reset_url": reset_url,
        },
    )


def emit_payment_success(
    *,
    recipient: str,
    customer_name: str,
    order_no: str,
    amount: str,
    currency: str = "TRY",
    date: str = "",
    order_url: str = "",
    organization_id: str | None = None,
) -> str | None:
    return emit_mail_event(
        template_key=PAYMENT_SUCCESS,
        recipient=recipient,
        organization_id=organization_id,
        context={
            "customer_name": customer_name,
            "order_no": order_no,
            "amount": amount,
            "currency": currency,
            "date": date,
            "order_url": order_url,
        },
    )


def emit_order_created(
    *,
    recipient: str,
    customer_name: str,
    order_no: str,
    amount: str = "",
    currency: str = "TRY",
    date: str = "",
    order_url: str = "",
    organization_id: str | None = None,
) -> str | None:
    return emit_mail_event(
        template_key=ORDER_CREATED,
        recipient=recipient,
        organization_id=organization_id,
        context={
            "customer_name": customer_name,
            "order_no": order_no,
            "amount": amount,
            "currency": currency,
            "date": date,
            "order_url": order_url,
        },
    )


def emit_payment_failed(
    *,
    recipient: str,
    customer_name: str,
    order_no: str,
    amount: str = "",
    currency: str = "TRY",
    error_message: str = "",
    organization_id: str | None = None,
) -> str | None:
    return emit_mail_event(
        template_key=PAYMENT_FAILED,
        recipient=recipient,
        organization_id=organization_id,
        context={
            "customer_name": customer_name,
            "order_no": order_no,
            "amount": amount,
            "currency": currency,
            "error_message": error_message,
        },
    )


def emit_payment_refunded(
    *,
    recipient: str,
    customer_name: str,
    order_no: str,
    refund_amount: str,
    currency: str = "TRY",
    kind: str = "REFUND",
    organization_id: str | None = None,
) -> str | None:
    return emit_mail_event(
        template_key=PAYMENT_REFUNDED,
        recipient=recipient,
        organization_id=organization_id,
        context={
            "customer_name": customer_name,
            "order_no": order_no,
            "refund_amount": refund_amount,
            "amount": refund_amount,
            "currency": currency,
            "kind": kind,
        },
    )


def emit_bank_transfer_pending(
    *,
    recipient: str,
    customer_name: str,
    order_no: str,
    amount: str,
    currency: str = "TRY",
    bank_name: str = "",
    iban: str = "",
    account_holder: str = "",
    transfer_reference: str = "",
    organization_id: str | None = None,
) -> str | None:
    return emit_mail_event(
        template_key=BANK_TRANSFER_PENDING,
        recipient=recipient,
        organization_id=organization_id,
        context={
            "customer_name": customer_name,
            "order_no": order_no,
            "amount": amount,
            "currency": currency,
            "bank_name": bank_name,
            "iban": iban,
            "account_holder": account_holder,
            "transfer_reference": transfer_reference,
        },
    )


def emit_order_cancelled(
    *,
    recipient: str,
    customer_name: str,
    order_no: str,
    organization_id: str | None = None,
) -> str | None:
    return emit_mail_event(
        template_key=ORDER_CANCELLED,
        recipient=recipient,
        organization_id=organization_id,
        context={
            "customer_name": customer_name,
            "order_no": order_no,
        },
    )
