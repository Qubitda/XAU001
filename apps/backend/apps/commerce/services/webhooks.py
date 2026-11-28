"""Webhook, email, in-app notification, and social hook dispatchers for commerce."""
import logging

from django.db import transaction
from django.utils import timezone

from apps.webhooks.services import emit_webhook_event

from ..models import B2bOrder, B2cOrder

logger = logging.getLogger(__name__)


def _schedule_b2c_order_created_webhook(order: B2cOrder) -> None:
    order_no = order.order_no
    status = order.status
    total = str(order.grand_total_try)

    def _emit() -> None:
        # Platform-only: never fan out to dealer organization endpoints.
        emit_webhook_event(
            "b2c.order.created",
            {"orderNo": order_no, "status": status, "grandTotalTry": total},
            platform=True,
        )

    transaction.on_commit(_emit)


def _emit_b2c_payment_success_mail(order: B2cOrder) -> None:
    """Event-driven payment receipt — MailLog in same TX; Celery enqueue on commit."""
    from django.conf import settings as dj_settings

    from apps.mail.events import emit_payment_success

    recipient = (order.shipping_email or getattr(order.customer, "email", "") or "").strip()
    if not recipient:
        return
    base = (getattr(dj_settings, "FRONTEND_STOREFRONT_URL", "") or "http://localhost:3000").rstrip("/")
    emit_payment_success(
        recipient=recipient,
        customer_name=order.shipping_full_name or getattr(order.customer, "full_name", "") or "",
        order_no=order.order_no,
        amount=str(order.grand_total_try),
        currency="TRY",
        date=timezone.localtime(order.updated_at).strftime("%d.%m.%Y %H:%M"),
        order_url=f"{base}/hesabim/siparisler/{order.order_no}",
    )


def _dispatch_in_app_order_notification(*, user_id, title: str, body: str) -> None:
    if not user_id:
        return
    uid = str(user_id)

    def _enqueue() -> None:
        from django.conf import settings as dj_settings

        from apps.notifications.tasks import send_order_notification

        if getattr(dj_settings, "TESTING", False) or getattr(dj_settings, "CELERY_TASK_ALWAYS_EAGER", False):
            send_order_notification(uid, title, body)
            return
        try:
            send_order_notification.delay(uid, title, body)
        except Exception:
            logger.exception("send_order_notification.delay failed; falling back inline user=%s", uid)
            send_order_notification(uid, title, body)

    transaction.on_commit(_enqueue)


def _emit_b2c_order_created_mail(order: B2cOrder) -> None:
    try:
        from django.conf import settings as dj_settings

        from apps.mail.events import emit_order_created

        recipient = (order.shipping_email or getattr(order.customer, "email", "") or "").strip()
        if not recipient:
            return
        base = (getattr(dj_settings, "FRONTEND_STOREFRONT_URL", "") or "http://localhost:3000").rstrip("/")
        emit_order_created(
            recipient=recipient,
            customer_name=order.shipping_full_name or getattr(order.customer, "full_name", "") or "",
            order_no=order.order_no,
            amount=str(order.grand_total_try),
            currency="TRY",
            date=timezone.localtime(order.created_at).strftime("%d.%m.%Y %H:%M"),
            order_url=f"{base}/hesabim/siparisler/{order.order_no}",
        )
    except Exception:
        logger.exception("B2C order_created mail failed order=%s", order.order_no)


def _emit_b2b_order_created_mail(order: B2bOrder) -> None:
    try:
        from django.conf import settings as dj_settings

        from apps.mail.events import emit_order_created

        recipient = (
            getattr(order.created_by, "email", "")
            or getattr(order.organization, "email", "")
            or ""
        ).strip()
        if not recipient:
            return
        base = (getattr(dj_settings, "FRONTEND_STOREFRONT_URL", "") or "http://localhost:3001").rstrip("/")
        emit_order_created(
            recipient=recipient,
            customer_name=order.contact_person or getattr(order.organization, "name", "") or "",
            order_no=order.order_no,
            amount=str(order.total_wholesale_usd),
            currency="USD",
            date=timezone.localtime(order.created_at).strftime("%d.%m.%Y %H:%M"),
            order_url=f"{base}/b2b/siparisler",
            organization_id=str(order.organization_id),
        )
    except Exception:
        logger.exception("B2B order_created mail failed order=%s", order.order_no)


def _emit_order_cancelled_notifications(
    *,
    order_no: str,
    recipient: str,
    customer_name: str,
    user_id=None,
    organization_id: str | None = None,
) -> None:
    try:
        from apps.mail.events import emit_order_cancelled

        if (recipient or "").strip():
            emit_order_cancelled(
                recipient=recipient.strip(),
                customer_name=customer_name,
                order_no=order_no,
                organization_id=organization_id,
            )
        _dispatch_in_app_order_notification(
            user_id=user_id,
            title=f"Sipariş İptal Edildi · {order_no}",
            body=f"{order_no} numaralı siparişiniz iptal edilmiştir.",
        )
    except Exception:
        logger.exception("order_cancelled notification failed order=%s", order_no)


def _schedule_b2b_order_created_webhook(order: B2bOrder) -> None:
    order_no = order.order_no
    org_id = order.organization_id
    status = order.status
    total_usd = str(order.total_wholesale_usd)

    def _emit() -> None:
        emit_webhook_event(
            "b2b.order.created",
            {"orderNo": order_no, "status": status, "totalWholesaleUsd": total_usd},
            organization_id=org_id,
        )

    transaction.on_commit(_emit)


def _schedule_b2b_order_status_webhook(*, order: B2bOrder, previous: str, current: str) -> None:
    order_no = order.order_no
    org_id = order.organization_id

    def _emit() -> None:
        emit_webhook_event(
            "b2b.order.status",
            {"orderNo": order_no, "fromStatus": previous, "toStatus": current, "status": current},
            organization_id=org_id,
        )

    transaction.on_commit(_emit)


def _record_social_commerce_order_hooks(*, order: B2cOrder, payload: dict) -> None:
    """Non-blocking social attribution & affiliate conversion recording for confirmed B2C orders."""
    try:
        from apps.social_commerce.services import (
            record_affiliate_conversion,
            record_verified_order_attribution,
        )

        record_verified_order_attribution(
            order_no=order.order_no,
            revenue_try=order.grand_total_try,
            customer=order.customer,
            session_key=str(payload.get("sessionKey") or ""),
            platform=str(payload.get("utmPlatform") or payload.get("utmSource") or ""),
            utm_source=str(payload.get("utmSource") or ""),
            utm_medium=str(payload.get("utmMedium") or ""),
            utm_campaign=str(payload.get("utmCampaign") or ""),
            audience="B2C",
        )
        aff_code = str(payload.get("affiliateCode") or "").strip()
        if aff_code:
            record_affiliate_conversion(
                code_str=aff_code,
                order_no=order.order_no,
                gross_amount_try=order.subtotal_list_try,
                net_amount_try=order.grand_total_try,
                audience="B2C",
            )
    except Exception:
        logger.exception("social_commerce order hook failed order=%s", order.order_no)
