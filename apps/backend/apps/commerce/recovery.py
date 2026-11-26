"""
Abandoned cart / B2B draft recovery — Faz 1 (email + in-app + OPS task).
"""

from __future__ import annotations

import hashlib
import logging
from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.notifications.models import Notification
from apps.pricing.services import get_active_price_lock

from .models import (
    B2bDraftLine,
    B2cCartItem,
    CartRecoveryAttempt,
    CartRecoverySession,
    OpsSalesTask,
)

logger = logging.getLogger(__name__)


def _q2(value: Decimal | float | int) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"))


def _threshold_b2b() -> Decimal:
    return _q2(getattr(settings, "CART_RECOVERY_B2B_OPS_THRESHOLD_TRY", 50_000))


def _threshold_b2c() -> Decimal:
    return _q2(getattr(settings, "CART_RECOVERY_B2C_OPS_THRESHOLD_TRY", 100_000))


def _cooldown_delta() -> timedelta:
    days = int(getattr(settings, "CART_RECOVERY_COOLDOWN_DAYS", 7))
    return timedelta(days=days)


def _stage_delays(segment: str) -> dict[str, timedelta]:
    if segment == CartRecoverySession.Segment.B2B:
        return {
            "T1": timedelta(seconds=int(getattr(settings, "CART_RECOVERY_B2B_T1_SECONDS", 3600))),
            "T2": timedelta(seconds=int(getattr(settings, "CART_RECOVERY_B2B_T2_SECONDS", 24 * 3600))),
            "T3": timedelta(seconds=int(getattr(settings, "CART_RECOVERY_B2B_T3_SECONDS", 48 * 3600))),
        }
    return {
        "T1": timedelta(seconds=int(getattr(settings, "CART_RECOVERY_B2C_T1_SECONDS", 3600))),
        "T2": timedelta(seconds=int(getattr(settings, "CART_RECOVERY_B2C_T2_SECONDS", 12 * 3600))),
        "T3": timedelta(seconds=int(getattr(settings, "CART_RECOVERY_B2C_T3_SECONDS", 24 * 3600))),
    }


def _next_stage(current: str) -> str | None:
    order = ["NONE", "T1", "T2", "T3"]
    try:
        idx = order.index(current)
    except ValueError:
        return "T1"
    if idx >= len(order) - 1:
        return None
    return order[idx + 1]


def _fingerprint(parts: list[str]) -> str:
    raw = "|".join(parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:64]


def _storefront_url() -> str:
    return (getattr(settings, "STOREFRONT_PUBLIC_URL", None) or "http://localhost:3000").rstrip("/")


def _b2b_url() -> str:
    return (getattr(settings, "B2B_PUBLIC_URL", None) or "http://localhost:3001").rstrip("/")


def _snapshot_b2c(user) -> dict[str, Any] | None:
    items = list(B2cCartItem.objects.filter(user=user).order_by("-updated_at"))
    if not items:
        return None
    value = sum((i.unit_final_price_try * i.qty for i in items), Decimal("0.00"))
    fp = _fingerprint([f"{i.sku}:{i.qty}:{i.size}:{i.metal_color}" for i in items])
    return {
        "fingerprint": fp,
        "value": _q2(value),
        "line_count": len(items),
        "has_stock_lines": any(i.stock_status == "Stokta" for i in items),
        "stock_line_count": sum(1 for i in items if i.stock_status == "Stokta"),
        "production_line_count": sum(1 for i in items if i.stock_status != "Stokta"),
        "first_item_title": items[0].title,
        "cart_updated_at": max(i.updated_at for i in items),
    }


def _snapshot_b2b(organization) -> dict[str, Any] | None:
    lines = list(B2bDraftLine.objects.filter(organization=organization).order_by("-updated_at"))
    if not lines:
        return None
    value = sum((l.unit_wholesale_try * l.qty for l in lines), Decimal("0.00"))
    fp = _fingerprint(
        [f"{l.sku}:{l.qty}:{l.size}:{l.supply_type}:{l.dealer_stamp_note}" for l in lines]
    )
    stock_n = sum(1 for l in lines if l.supply_type == "STOCK")
    prod_n = sum(1 for l in lines if l.supply_type != "STOCK")
    return {
        "fingerprint": fp,
        "value": _q2(value),
        "line_count": len(lines),
        "has_stock_lines": stock_n > 0,
        "stock_line_count": stock_n,
        "production_line_count": prod_n,
        "first_item_title": lines[0].title,
        "cart_updated_at": max(l.updated_at for l in lines),
    }


def _apply_snapshot(session: CartRecoverySession, snap: dict[str, Any]) -> None:
    session.cart_fingerprint = snap["fingerprint"]
    session.cart_value_try = snap["value"]
    session.line_count = snap["line_count"]
    session.has_stock_lines = snap["has_stock_lines"]
    session.stock_line_count = snap["stock_line_count"]
    session.production_line_count = snap["production_line_count"]
    session.first_item_title = snap["first_item_title"]
    session.cart_updated_at = snap["cart_updated_at"]


def _find_active_b2c(user) -> CartRecoverySession | None:
    return (
        CartRecoverySession.objects.filter(
            user=user,
            segment=CartRecoverySession.Segment.B2C,
            status=CartRecoverySession.Status.ACTIVE,
        )
        .order_by("-cart_updated_at")
        .first()
    )


def _find_active_b2b(organization) -> CartRecoverySession | None:
    return (
        CartRecoverySession.objects.filter(
            organization=organization,
            segment=CartRecoverySession.Segment.B2B,
            status=CartRecoverySession.Status.ACTIVE,
        )
        .order_by("-cart_updated_at")
        .first()
    )


def _in_cooldown(session: CartRecoverySession, now=None) -> bool:
    now = now or timezone.now()
    if session.cooldown_until and session.cooldown_until > now:
        return True
    return False


@transaction.atomic
def touch_b2c_cart(*, user) -> CartRecoverySession | None:
    from .cart_sync import sync_user_cart

    sync_user_cart(user=user)

    snap = _snapshot_b2c(user)
    if snap is None:
        suppress_b2c_cart(user=user, reason=CartRecoverySession.SuppressReason.EMPTIED)
        return None

    session = _find_active_b2c(user)
    now = timezone.now()

    if session is None:
        # Reuse completed/cooldown only after cooldown ends
        recent = (
            CartRecoverySession.objects.filter(
                user=user, segment=CartRecoverySession.Segment.B2C
            )
            .exclude(status=CartRecoverySession.Status.ACTIVE)
            .order_by("-updated_at")
            .first()
        )
        if recent and _in_cooldown(recent, now):
            # Touch cart but do not restart outreach yet
            _apply_snapshot(recent, snap)
            recent.save(
                update_fields=[
                    "cart_fingerprint",
                    "cart_value_try",
                    "line_count",
                    "has_stock_lines",
                    "stock_line_count",
                    "production_line_count",
                    "first_item_title",
                    "cart_updated_at",
                    "updated_at",
                ]
            )
            return recent

        session = CartRecoverySession(
            segment=CartRecoverySession.Segment.B2C,
            user=user,
            status=CartRecoverySession.Status.ACTIVE,
            stage=CartRecoverySession.Stage.NONE,
        )

    fingerprint_changed = session.pk and session.cart_fingerprint != snap["fingerprint"]
    _apply_snapshot(session, snap)
    session.status = CartRecoverySession.Status.ACTIVE
    session.suppress_reason = ""
    if fingerprint_changed and session.stage != CartRecoverySession.Stage.NONE:
        # Content changed: keep stage (idempotent attempts) but refresh idle clock
        pass
    session.save()
    return session


@transaction.atomic
def touch_b2b_draft(*, user, organization) -> CartRecoverySession | None:
    snap = _snapshot_b2b(organization)
    if snap is None:
        suppress_b2b_draft(
            organization=organization, reason=CartRecoverySession.SuppressReason.EMPTIED
        )
        return None

    session = _find_active_b2b(organization)
    now = timezone.now()

    if session is None:
        recent = (
            CartRecoverySession.objects.filter(
                organization=organization, segment=CartRecoverySession.Segment.B2B
            )
            .exclude(status=CartRecoverySession.Status.ACTIVE)
            .order_by("-updated_at")
            .first()
        )
        if recent and _in_cooldown(recent, now):
            _apply_snapshot(recent, snap)
            recent.user = user
            recent.save(
                update_fields=[
                    "user",
                    "cart_fingerprint",
                    "cart_value_try",
                    "line_count",
                    "has_stock_lines",
                    "stock_line_count",
                    "production_line_count",
                    "first_item_title",
                    "cart_updated_at",
                    "updated_at",
                ]
            )
            return recent

        session = CartRecoverySession(
            segment=CartRecoverySession.Segment.B2B,
            user=user,
            organization=organization,
            status=CartRecoverySession.Status.ACTIVE,
            stage=CartRecoverySession.Stage.NONE,
        )

    _apply_snapshot(session, snap)
    session.user = user
    session.status = CartRecoverySession.Status.ACTIVE
    session.suppress_reason = ""
    session.save()
    return session


@transaction.atomic
def suppress_b2c_cart(*, user, reason: str) -> None:
    CartRecoverySession.objects.filter(
        user=user,
        segment=CartRecoverySession.Segment.B2C,
        status=CartRecoverySession.Status.ACTIVE,
    ).update(
        status=CartRecoverySession.Status.SUPPRESSED,
        suppress_reason=reason,
        updated_at=timezone.now(),
    )


@transaction.atomic
def suppress_b2b_draft(*, organization, reason: str) -> None:
    CartRecoverySession.objects.filter(
        organization=organization,
        segment=CartRecoverySession.Segment.B2B,
        status=CartRecoverySession.Status.ACTIVE,
    ).update(
        status=CartRecoverySession.Status.SUPPRESSED,
        suppress_reason=reason,
        updated_at=timezone.now(),
    )


def _attempt_exists(session: CartRecoverySession, stage: str, channel: str) -> bool:
    return CartRecoveryAttempt.objects.filter(
        session=session, stage=stage, channel=channel
    ).exists()


def _record_attempt(
    *,
    session: CartRecoverySession,
    stage: str,
    channel: str,
    template_key: str = "",
    provider_ref: str = "",
    status: str = CartRecoveryAttempt.Status.SENT,
    skip_reason: str = "",
) -> CartRecoveryAttempt:
    return CartRecoveryAttempt.objects.create(
        session=session,
        stage=stage,
        channel=channel,
        template_key=template_key,
        provider_ref=provider_ref or "",
        status=status,
        skip_reason=skip_reason or "",
    )


def _status_from_channel_result(skip_reason: str) -> str:
    """Map channel send outcome to attempt status. SEND_FAILED is FAILED, not SKIPPED."""
    if not skip_reason:
        return CartRecoveryAttempt.Status.SENT
    if skip_reason == "SEND_FAILED":
        return CartRecoveryAttempt.Status.FAILED
    return CartRecoveryAttempt.Status.SKIPPED


def _b2c_customer(session: CartRecoverySession):
    from apps.customers.models import Customer

    if session.user_id:
        return (
            Customer.objects.filter(user_id=session.user_id, is_active=True)
            .order_by("-updated_at")
            .first()
        )
    guest = (session.guest_email or "").strip()
    if guest:
        return (
            Customer.objects.filter(email__iexact=guest, is_active=True)
            .order_by("-updated_at")
            .first()
        )
    return None


def _b2c_channel_consent_ok(session: CartRecoverySession, channel: str) -> bool:
    """TOCTOU-safe commercial consent check for B2C recovery channels."""
    from apps.messaging.services import channel_consent_ok

    if session.segment != CartRecoverySession.Segment.B2C:
        return True
    return channel_consent_ok(
        channel=channel,
        customer=_b2c_customer(session),
        guest_email=(session.guest_email or "").strip(),
    )


def _b2c_email_consent_ok(session: CartRecoverySession) -> bool:
    return _b2c_channel_consent_ok(session, "EMAIL")


def _recipient_phone(session: CartRecoverySession) -> str:
    from apps.messaging.services import resolve_customer_phone

    customer = _b2c_customer(session)
    return resolve_customer_phone(user=session.user, customer=customer)


def _send_sms(session: CartRecoverySession, stage: str, template_key: str) -> tuple[str, str]:
    """Returns (provider_ref, skip_reason)."""
    from apps.messaging.providers import sms_enabled
    from apps.messaging.services import enqueue_channel_message

    if not sms_enabled():
        return "", "CHANNEL_DISABLED"
    if not _b2c_channel_consent_ok(session, "SMS"):
        return "", "NO_CONSENT"
    phone = _recipient_phone(session)
    if not phone:
        return "", "NO_PHONE"
    ctx = _build_context(session)
    body = (
        f"TARA DIAMOND: Sepetinizde {ctx.get('first_item_title') or 'ürün'} sizi bekliyor. "
        f"{ctx.get('cart_url') or _storefront_url()}"
    )
    log = enqueue_channel_message(
        channel="SMS",
        recipient=phone,
        body=body,
        template_key=template_key,
        context=ctx,
        correlation_id=str(session.id),
    )
    if log.status == "SKIPPED":
        return "", log.skip_reason or "SKIPPED"
    if log.status == "FAILED":
        return log.provider_ref or "", "SEND_FAILED"
    return log.provider_ref or str(log.id), ""


def _send_whatsapp(session: CartRecoverySession, stage: str, template_key: str) -> tuple[str, str]:
    """Returns (provider_ref, skip_reason)."""
    from apps.messaging.providers import whatsapp_enabled
    from apps.messaging.services import enqueue_channel_message

    if not whatsapp_enabled():
        return "", "CHANNEL_DISABLED"
    if not _b2c_channel_consent_ok(session, "WHATSAPP"):
        return "", "NO_CONSENT"
    phone = _recipient_phone(session)
    if not phone:
        return "", "NO_PHONE"
    ctx = _build_context(session)
    body = (
        f"Merhaba {ctx.get('customer_name') or ''}, "
        f"sepetinizdeki {ctx.get('first_item_title') or 'ürün'} için stok ve kur güncel. "
        f"Devam: {ctx.get('cart_url') or _storefront_url()}"
    ).strip()
    log = enqueue_channel_message(
        channel="WHATSAPP",
        recipient=phone,
        body=body,
        template_key=template_key,
        context=ctx,
        correlation_id=str(session.id),
    )
    if log.status == "SKIPPED":
        return "", log.skip_reason or "SKIPPED"
    if log.status == "FAILED":
        return log.provider_ref or "", "SEND_FAILED"
    return log.provider_ref or str(log.id), ""


def _recipient_email(session: CartRecoverySession) -> str:
    if session.user_id:
        return session.user.email
    return (session.guest_email or "").strip()


def _build_context(session: CartRecoverySession) -> dict[str, Any]:
    user = session.user
    ctx: dict[str, Any] = {
        "customer_name": (getattr(user, "full_name", "") if user else "") or "",
        "email": _recipient_email(session),
        "line_count": session.line_count,
        "cart_value_try": str(session.cart_value_try),
        "first_item_title": session.first_item_title,
        "stock_line_count": session.stock_line_count,
        "production_line_count": session.production_line_count,
    }
    if session.segment == CartRecoverySession.Segment.B2C:
        ctx["cart_url"] = f"{_storefront_url()}/"
        if user:
            lock = get_active_price_lock(user)
            if lock and lock.expires_at and lock.expires_at > timezone.now():
                ctx["price_locked_until"] = lock.expires_at.isoformat()
                ctx["price_lock_active"] = True
            else:
                ctx["price_lock_active"] = False
                ctx["price_locked_until"] = ""
        else:
            ctx["price_lock_active"] = False
            ctx["price_locked_until"] = ""
    else:
        org = session.organization
        ctx["org_name"] = getattr(org, "name", "") or getattr(org, "code", "") or "Bayi"
        ctx["draft_url"] = f"{_b2b_url()}/b2b/siparis-fisi"
        ctx["draft_pdf_url"] = f"{_b2b_url()}/b2b/siparis-fisi?pdf=1"
    return ctx


def _send_email(session: CartRecoverySession, stage: str, template_key: str) -> str | None:
    from apps.mail.events import emit_mail_event

    recipient = _recipient_email(session)
    if not recipient:
        return None
    ctx = _build_context(session)
    org_id = str(session.organization_id) if session.organization_id else None
    return emit_mail_event(
        template_key=template_key,
        recipient=recipient,
        context=ctx,
        organization_id=org_id,
    )


def _send_in_app(session: CartRecoverySession, title: str, body: str) -> str:
    if not session.user_id:
        return ""
    notif = Notification.objects.create(
        recipient=session.user,
        channel=Notification.Channel.IN_APP,
        title=title,
        body=body,
    )
    return str(notif.id)


def _should_create_ops_task(session: CartRecoverySession) -> bool:
    if session.segment == CartRecoverySession.Segment.B2B:
        return session.cart_value_try >= _threshold_b2b() or session.has_stock_lines
    return session.cart_value_try >= _threshold_b2c()


def _create_ops_task(session: CartRecoverySession) -> OpsSalesTask | None:
    if not _should_create_ops_task(session):
        return None
    if OpsSalesTask.objects.filter(
        recovery_session=session, status=OpsSalesTask.Status.OPEN
    ).exists():
        return None

    ctx = _build_context(session)
    if session.segment == CartRecoverySession.Segment.B2B:
        kind = OpsSalesTask.Kind.ABANDONED_DRAFT_CALL
        script_key = "ops_call_b2b_draft_t3"
        ctx["call_script"] = (
            "Taslakta bekleyen kalemler var; stok ayırma proforma onayında yapılıyor. "
            "Yönetici onayı veya limit/vade için yardımcı olabileceğim bir belge var mı?"
        )
        title = f"Bayi taslağı bekliyor — {ctx.get('org_name', '')}"
        body = (
            f"{ctx.get('org_name')} · {session.cart_value_try} TRY · "
            f"{session.stock_line_count} stok / {session.production_line_count} üretim"
        )
    else:
        kind = OpsSalesTask.Kind.ABANDONED_CART_CALL
        script_key = "ops_call_b2c_cart_t3"
        ctx["call_script"] = (
            "Yüksek tutarlı sepetiniz bekliyor; sigortalı teslimat ve ödeme seçeneklerinde "
            "yardımcı olabilirim. Devam etmek ister misiniz?"
        )
        title = "Yüksek tutarlı sepet bekliyor"
        body = (
            f"{_recipient_email(session)} · {session.cart_value_try} TRY · "
            f"{session.line_count} kalem"
        )

    task = OpsSalesTask.objects.create(
        kind=kind,
        segment=session.segment,
        user=session.user,
        guest_email=session.guest_email or "",
        organization=session.organization,
        recovery_session=session,
        cart_value_try=session.cart_value_try,
        due_at=timezone.now(),
        script_key=script_key,
        context_snapshot=ctx,
    )

    # Notify OPS users with orders:manage if available; else skip silently
    try:
        from django.contrib.auth import get_user_model

        User = get_user_model()
        ops_users = User.objects.filter(is_staff=True, is_active=True)[:20]
        for ops_user in ops_users:
            Notification.objects.create(
                recipient=ops_user,
                channel=Notification.Channel.IN_APP,
                title=title[:200],
                body=body,
            )
    except Exception:  # pragma: no cover
        logger.exception("OPS in-app notify failed for recovery task %s", task.id)

    return task


def dispatch_stage(session: CartRecoverySession, stage: str) -> list[CartRecoveryAttempt]:
    """Send channel actions for a stage; idempotent per (session, stage, channel)."""
    created: list[CartRecoveryAttempt] = []
    ctx_preview = _build_context(session)

    if session.segment == CartRecoverySession.Segment.B2C:
        if stage == "T1":
            key = "cart_recovery_b2c_t1"
            if not _attempt_exists(session, stage, CartRecoveryAttempt.Channel.EMAIL):
                if not _b2c_email_consent_ok(session):
                    created.append(
                        _record_attempt(
                            session=session,
                            stage=stage,
                            channel=CartRecoveryAttempt.Channel.EMAIL,
                            template_key=key,
                            status=CartRecoveryAttempt.Status.SKIPPED,
                            skip_reason="NO_CONSENT",
                        )
                    )
                else:
                    ref = _send_email(session, stage, key)
                    created.append(
                        _record_attempt(
                            session=session,
                            stage=stage,
                            channel=CartRecoveryAttempt.Channel.EMAIL,
                            template_key=key,
                            provider_ref=ref or "",
                        )
                    )
        elif stage == "T2":
            if session.user_id and not _attempt_exists(
                session, stage, CartRecoveryAttempt.Channel.IN_APP
            ):
                title = "Sepetiniz sizi bekliyor"
                body = (
                    f"Sepetinizdeki {session.first_item_title or 'ürün'} duruyor — "
                    "stok ve güncel kur için sepete dönün."
                )
                ref = _send_in_app(session, title, body)
                created.append(
                    _record_attempt(
                        session=session,
                        stage=stage,
                        channel=CartRecoveryAttempt.Channel.IN_APP,
                        template_key="in_app_b2c_t2",
                        provider_ref=ref,
                    )
                )
            elif not session.user_id and not _attempt_exists(
                session, stage, CartRecoveryAttempt.Channel.IN_APP
            ):
                # Guests have no in-app surface — mark skipped, T3 email continues funnel
                created.append(
                    _record_attempt(
                        session=session,
                        stage=stage,
                        channel=CartRecoveryAttempt.Channel.IN_APP,
                        template_key="in_app_b2c_t2",
                        status=CartRecoveryAttempt.Status.SKIPPED,
                        skip_reason="NO_USER",
                    )
                )
            # Faz D: B2C T2 SMS (only when channel enabled)
            from apps.messaging.providers import sms_enabled

            if sms_enabled() and not _attempt_exists(
                session, stage, CartRecoveryAttempt.Channel.SMS
            ):
                ref, skip = _send_sms(session, stage, "cart_recovery_b2c_t2_sms")
                created.append(
                    _record_attempt(
                        session=session,
                        stage=stage,
                        channel=CartRecoveryAttempt.Channel.SMS,
                        template_key="cart_recovery_b2c_t2_sms",
                        provider_ref=ref,
                        status=_status_from_channel_result(skip),
                        skip_reason=skip,
                    )
                )
        elif stage == "T3":
            key = "cart_recovery_b2c_t3"
            if not _attempt_exists(session, stage, CartRecoveryAttempt.Channel.EMAIL):
                if not _b2c_email_consent_ok(session):
                    created.append(
                        _record_attempt(
                            session=session,
                            stage=stage,
                            channel=CartRecoveryAttempt.Channel.EMAIL,
                            template_key=key,
                            status=CartRecoveryAttempt.Status.SKIPPED,
                            skip_reason="NO_CONSENT",
                        )
                    )
                else:
                    ref = _send_email(session, stage, key)
                    created.append(
                        _record_attempt(
                            session=session,
                            stage=stage,
                            channel=CartRecoveryAttempt.Channel.EMAIL,
                            template_key=key,
                            provider_ref=ref or "",
                        )
                    )
            # Faz D: B2C T3 WhatsApp (only when channel enabled)
            from apps.messaging.providers import whatsapp_enabled

            if whatsapp_enabled() and not _attempt_exists(
                session, stage, CartRecoveryAttempt.Channel.WHATSAPP
            ):
                ref, skip = _send_whatsapp(session, stage, "cart_recovery_b2c_t3_wa")
                created.append(
                    _record_attempt(
                        session=session,
                        stage=stage,
                        channel=CartRecoveryAttempt.Channel.WHATSAPP,
                        template_key="cart_recovery_b2c_t3_wa",
                        provider_ref=ref,
                        status=_status_from_channel_result(skip),
                        skip_reason=skip,
                    )
                )
            if _should_create_ops_task(session) and not _attempt_exists(
                session, stage, CartRecoveryAttempt.Channel.OPS_TASK
            ):
                task = _create_ops_task(session)
                created.append(
                    _record_attempt(
                        session=session,
                        stage=stage,
                        channel=CartRecoveryAttempt.Channel.OPS_TASK,
                        template_key="ops_call_b2c_cart_t3",
                        provider_ref=str(task.id) if task else "",
                        status=(
                            CartRecoveryAttempt.Status.SENT
                            if task
                            else CartRecoveryAttempt.Status.SKIPPED
                        ),
                    )
                )
    else:
        if stage == "T1":
            key = "cart_recovery_b2b_t1"
            if not _attempt_exists(session, stage, CartRecoveryAttempt.Channel.EMAIL):
                ref = _send_email(session, stage, key)
                created.append(
                    _record_attempt(
                        session=session,
                        stage=stage,
                        channel=CartRecoveryAttempt.Channel.EMAIL,
                        template_key=key,
                        provider_ref=ref or "",
                    )
                )
        elif stage == "T2":
            if not _attempt_exists(session, stage, CartRecoveryAttempt.Channel.IN_APP):
                org_name = ctx_preview.get("org_name", "Bayi")
                title = "Taslak sipariş fişiniz bekliyor"
                body = (
                    f"{org_name} taslak fişiniz bekliyor — kur politikası ve "
                    "stok/üretim seçimini kontrol edin."
                )
                ref = _send_in_app(session, title, body)
                created.append(
                    _record_attempt(
                        session=session,
                        stage=stage,
                        channel=CartRecoveryAttempt.Channel.IN_APP,
                        template_key="in_app_b2b_t2",
                        provider_ref=ref,
                    )
                )
            key = "cart_recovery_b2b_t2"
            if not _attempt_exists(session, stage, CartRecoveryAttempt.Channel.EMAIL):
                ref = _send_email(session, stage, key)
                created.append(
                    _record_attempt(
                        session=session,
                        stage=stage,
                        channel=CartRecoveryAttempt.Channel.EMAIL,
                        template_key=key,
                        provider_ref=ref or "",
                    )
                )
        elif stage == "T3":
            if _should_create_ops_task(session) and not _attempt_exists(
                session, stage, CartRecoveryAttempt.Channel.OPS_TASK
            ):
                task = _create_ops_task(session)
                created.append(
                    _record_attempt(
                        session=session,
                        stage=stage,
                        channel=CartRecoveryAttempt.Channel.OPS_TASK,
                        template_key="ops_call_b2b_draft_t3",
                        provider_ref=str(task.id) if task else "",
                        status=(
                            CartRecoveryAttempt.Status.SENT
                            if task
                            else CartRecoveryAttempt.Status.SKIPPED
                        ),
                    )
                )
            elif not _should_create_ops_task(session) and not _attempt_exists(
                session, stage, CartRecoveryAttempt.Channel.OPS_TASK
            ):
                created.append(
                    _record_attempt(
                        session=session,
                        stage=stage,
                        channel=CartRecoveryAttempt.Channel.OPS_TASK,
                        template_key="ops_call_b2b_draft_t3",
                        status=CartRecoveryAttempt.Status.SKIPPED,
                    )
                )

    return created


@transaction.atomic
def process_session(session: CartRecoverySession, *, now=None) -> str | None:
    """Advance one stage if idle threshold met. Returns dispatched stage or None."""
    now = now or timezone.now()
    session = CartRecoverySession.objects.select_for_update().get(pk=session.pk)

    if session.status != CartRecoverySession.Status.ACTIVE:
        return None
    if _in_cooldown(session, now):
        return None

    # Refresh emptiness
    if session.segment == CartRecoverySession.Segment.B2C:
        if session.user_id:
            if not B2cCartItem.objects.filter(user_id=session.user_id).exists():
                session.status = CartRecoverySession.Status.SUPPRESSED
                session.suppress_reason = CartRecoverySession.SuppressReason.EMPTIED
                session.save(update_fields=["status", "suppress_reason", "updated_at"])
                return None
        else:
            items = (session.guest_cart_snapshot or {}).get("items") or []
            if not items:
                session.status = CartRecoverySession.Status.SUPPRESSED
                session.suppress_reason = CartRecoverySession.SuppressReason.EMPTIED
                session.save(update_fields=["status", "suppress_reason", "updated_at"])
                return None
    else:
        if not B2bDraftLine.objects.filter(organization_id=session.organization_id).exists():
            session.status = CartRecoverySession.Status.SUPPRESSED
            session.suppress_reason = CartRecoverySession.SuppressReason.EMPTIED
            session.save(update_fields=["status", "suppress_reason", "updated_at"])
            return None

    nxt = _next_stage(session.stage)
    if not nxt:
        return None

    delays = _stage_delays(session.segment)
    due_after = session.cart_updated_at + delays[nxt]
    if now < due_after:
        return None

    dispatch_stage(session, nxt)
    session.stage = nxt
    session.last_touch_at = now
    if nxt == CartRecoverySession.Stage.T3:
        session.status = CartRecoverySession.Status.COMPLETED
        session.cooldown_until = now + _cooldown_delta()
    session.save(
        update_fields=["stage", "last_touch_at", "status", "cooldown_until", "updated_at"]
    )

    # Mirror abandon on B2cCart header when outreach starts
    if session.segment == CartRecoverySession.Segment.B2C and nxt == "T1":
        from .cart_sync import mark_cart_abandoned
        from .models import B2cCart

        cart_qs = B2cCart.objects.filter(status=B2cCart.Status.ACTIVE)
        if session.user_id:
            cart = cart_qs.filter(user_id=session.user_id).first()
        else:
            cart = cart_qs.filter(
                guest_email__iexact=(session.guest_email or ""), user__isnull=True
            ).first()
        if cart is not None:
            mark_cart_abandoned(cart)
            if not cart.recovery_session_id:
                cart.recovery_session = session
                cart.save(update_fields=["recovery_session", "updated_at"])
    return nxt


def scan_abandoned_carts(*, limit: int = 200) -> dict[str, int]:
    now = timezone.now()
    qs = (
        CartRecoverySession.objects.filter(status=CartRecoverySession.Status.ACTIVE)
        .order_by("cart_updated_at")[:limit]
    )
    dispatched = 0
    scanned = 0
    for session in qs:
        scanned += 1
        try:
            if process_session(session, now=now):
                dispatched += 1
        except Exception:
            logger.exception("cart recovery process failed session=%s", session.id)
    return {"scanned": scanned, "dispatched": dispatched}


def serialize_ops_sales_task(task: OpsSalesTask) -> dict[str, Any]:
    return {
        "id": str(task.id),
        "kind": task.kind,
        "segment": task.segment,
        "status": task.status,
        "cartValueTry": str(task.cart_value_try),
        "dueAt": task.due_at.isoformat(),
        "scriptKey": task.script_key,
        "context": task.context_snapshot,
        "note": task.note,
        "customerEmail": task.user.email if task.user_id else (task.guest_email or ""),
        "customerName": getattr(task.user, "full_name", "") if task.user_id else "",
        "organizationId": str(task.organization_id) if task.organization_id else None,
        "organizationName": (
            getattr(task.organization, "name", None)
            or getattr(task.organization, "code", None)
            if task.organization_id
            else None
        ),
        "completedAt": task.completed_at.isoformat() if task.completed_at else None,
        "createdAt": task.created_at.isoformat(),
    }


@transaction.atomic
def capture_guest_cart_lead(*, email: str, items: list[dict[str, Any]]) -> CartRecoverySession | None:
    """
    Guest abandoned-cart capture: email + cart summary (no server cart rows).
    """
    email_n = (email or "").strip().lower()
    if not email_n or "@" not in email_n:
        return None
    cleaned: list[dict[str, Any]] = []
    value = Decimal("0.00")
    for raw in items[:40]:
        if not isinstance(raw, dict):
            continue
        title = str(raw.get("title") or raw.get("sku") or "Ürün")[:240]
        sku = str(raw.get("sku") or "")[:64]
        try:
            qty = max(1, min(10, int(raw.get("qty") or 1)))
        except (TypeError, ValueError):
            qty = 1
        try:
            unit = _q2(Decimal(str(raw.get("unitFinalPriceTry") or raw.get("unit_final_price_try") or 0)))
        except Exception:
            unit = Decimal("0.00")
        value += unit * qty
        cleaned.append(
            {
                "sku": sku,
                "title": title,
                "qty": qty,
                "unitFinalPriceTry": str(unit),
            }
        )
    if not cleaned:
        return None

    fp = _fingerprint([f"{c['sku']}:{c['qty']}:{c['unitFinalPriceTry']}" for c in cleaned])
    now = timezone.now()
    session = (
        CartRecoverySession.objects.filter(
            segment=CartRecoverySession.Segment.B2C,
            status=CartRecoverySession.Status.ACTIVE,
            user__isnull=True,
            guest_email__iexact=email_n,
        )
        .order_by("-cart_updated_at")
        .first()
    )
    if session is None:
        recent = (
            CartRecoverySession.objects.filter(
                segment=CartRecoverySession.Segment.B2C,
                user__isnull=True,
                guest_email__iexact=email_n,
            )
            .exclude(status=CartRecoverySession.Status.ACTIVE)
            .order_by("-updated_at")
            .first()
        )
        if recent and _in_cooldown(recent, now):
            session = recent
        else:
            session = CartRecoverySession(
                segment=CartRecoverySession.Segment.B2C,
                user=None,
                guest_email=email_n,
                status=CartRecoverySession.Status.ACTIVE,
                stage=CartRecoverySession.Stage.NONE,
            )

    session.guest_email = email_n
    session.guest_cart_snapshot = {"items": cleaned}
    session.cart_fingerprint = fp
    session.cart_value_try = _q2(value)
    session.line_count = len(cleaned)
    session.has_stock_lines = True
    session.stock_line_count = len(cleaned)
    session.production_line_count = 0
    session.first_item_title = cleaned[0]["title"]
    session.cart_updated_at = now
    if session.status != CartRecoverySession.Status.ACTIVE and not _in_cooldown(session, now):
        session.status = CartRecoverySession.Status.ACTIVE
        session.stage = CartRecoverySession.Stage.NONE
        session.suppress_reason = ""
        session.cooldown_until = None
    session.save()
    return session
