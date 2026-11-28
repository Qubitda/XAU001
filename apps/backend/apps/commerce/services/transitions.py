"""Centralized B2C and B2B order status state machines."""
import logging

from django.db import transaction

from apps.audit.services import record_audit
from apps.finance.models import DealerLedgerEntry
from apps.finance.services import reverse_organization_limits
from apps.inventory.services import release_variant_stock
from config.exceptions import DomainError

from ..models import B2bOrder, B2cOrder
from .webhooks import _emit_order_cancelled_notifications, _schedule_b2b_order_status_webhook

logger = logging.getLogger(__name__)


B2C_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    B2cOrder.Status.PENDING_PAYMENT: {
        B2cOrder.Status.CONFIRMED,
        B2cOrder.Status.WORKSHOP,
        B2cOrder.Status.CANCELLED,
    },
    B2cOrder.Status.CONFIRMED: {
        B2cOrder.Status.WORKSHOP,
        B2cOrder.Status.SHIPPED,
        B2cOrder.Status.CANCELLED,
    },
    B2cOrder.Status.WORKSHOP: {
        B2cOrder.Status.SHIPPED,
        B2cOrder.Status.CANCELLED,
    },
    B2cOrder.Status.SHIPPED: {
        B2cOrder.Status.REFUNDED,
    },
    B2cOrder.Status.CANCELLED: set(),
    B2cOrder.Status.REFUNDED: set(),
}

B2B_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    B2bOrder.Status.PROFORMA_CONFIRMED: {
        B2bOrder.Status.WORKSHOP_PLANNED,
        B2bOrder.Status.READY_FOR_DISPATCH,
        B2bOrder.Status.CANCELLED,
    },
    B2bOrder.Status.WORKSHOP_PLANNED: {
        B2bOrder.Status.READY_FOR_DISPATCH,
        B2bOrder.Status.CANCELLED,
    },
    B2bOrder.Status.READY_FOR_DISPATCH: {
        B2bOrder.Status.REFUNDED,
    },
    B2bOrder.Status.CANCELLED: set(),
    B2bOrder.Status.REFUNDED: set(),
}


@transaction.atomic
def transition_b2c_order_status(*, order_no: str, next_status: str, actor=None) -> B2cOrder:
    """
    Centralized B2C order status state machine.
    - Rejects invalid transitions with 409 INVALID_STATUS_TRANSITION.
    - Releases variant warehouse stock automatically on CANCELLED / REFUNDED.
    """
    if next_status not in B2cOrder.Status.values:
        raise DomainError("Geçersiz B2C sipariş durumu.", code="INVALID_STATUS", status_code=400)

    order = (
        B2cOrder.objects.select_for_update()
        .prefetch_related("items__variant")
        .filter(order_no=order_no)
        .first()
    )
    if order is None:
        raise DomainError("B2C sipariş bulunamadı.", code="ORDER_NOT_FOUND", status_code=404)

    if order.status == next_status:
        return order

    allowed = B2C_ALLOWED_TRANSITIONS.get(order.status, set())
    if next_status not in allowed:
        raise DomainError(
            f"B2C sipariş '{order.status}' durumundan '{next_status}' durumuna geçirilemez.",
            code="INVALID_STATUS_TRANSITION",
            status_code=409,
        )

    prev_status = order.status
    order.status = next_status
    order.save(update_fields=["status", "updated_at"])

    if next_status in (B2cOrder.Status.CANCELLED, B2cOrder.Status.REFUNDED):
        try:
            from apps.social_commerce.services import mark_affiliate_conversion_refunded

            mark_affiliate_conversion_refunded(order.order_no)
        except Exception:
            logger.exception("social_commerce refund hook failed order=%s", order.order_no)
        released_variant_ids: set = set()
        for item in order.items.all():
            if item.variant is not None:
                release_variant_stock(
                    variant=item.variant,
                    qty=item.qty,
                    reference_no=order.order_no,
                    actor=actor,
                )
                released_variant_ids.add(item.variant_id)
        # Fallback for legacy items whose variant FK was null when reserved via parent_sku
        from apps.inventory.models import StockMovement

        for mv in StockMovement.objects.select_related("variant").filter(
            reference_no=order.order_no,
            movement_type=StockMovement.MovementType.RESERVE,
            variant__isnull=False,
        ):
            if mv.variant_id not in released_variant_ids:
                release_variant_stock(
                    variant=mv.variant,
                    qty=abs(mv.quantity_delta),
                    reference_no=order.order_no,
                    actor=actor,
                )
                released_variant_ids.add(mv.variant_id)

    record_audit(
        action="B2C_ORDER_STATUS_UPDATED",
        entity_type="B2cOrder",
        entity_id=order.order_no,
        actor=actor,
        metadata={"from": prev_status, "to": next_status},
    )
    if next_status == B2cOrder.Status.CANCELLED:
        _emit_order_cancelled_notifications(
            order_no=order.order_no,
            recipient=(order.shipping_email or getattr(order.customer, "email", "") or ""),
            customer_name=order.shipping_full_name or getattr(order.customer, "full_name", "") or "",
            user_id=order.created_by_id,
        )
    return order


@transaction.atomic
def transition_b2b_order_status(*, order_no: str, next_status: str, actor=None) -> B2bOrder:
    """
    Centralized B2B order status state machine.
    - Rejects invalid transitions with 409 INVALID_STATUS_TRANSITION.
    - On CANCELLED / REFUNDED: idempotently releases reserved variant stock AND reverses dealer finance ledger limits.
    """
    if next_status not in B2bOrder.Status.values:
        raise DomainError("Geçersiz B2B sipariş durumu.", code="INVALID_STATUS", status_code=400)

    order = (
        B2bOrder.objects.select_for_update()
        .select_related("organization")
        .prefetch_related("lines__variant")
        .filter(order_no=order_no)
        .first()
    )
    if order is None:
        raise DomainError("B2B sipariş bulunamadı.", code="ORDER_NOT_FOUND", status_code=404)

    if order.status == next_status:
        return order

    allowed = B2B_ALLOWED_TRANSITIONS.get(order.status, set())
    if next_status not in allowed:
        raise DomainError(
            f"B2B sipariş '{order.status}' durumundan '{next_status}' durumuna geçirilemez.",
            code="INVALID_STATUS_TRANSITION",
            status_code=409,
        )

    prev_status = order.status
    order.status = next_status
    order.save(update_fields=["status", "updated_at"])

    if next_status in (B2bOrder.Status.CANCELLED, B2bOrder.Status.REFUNDED):
        released_variant_ids: set = set()
        for line in order.lines.all():
            if line.supply_type == "STOCK" and line.variant is not None:
                release_variant_stock(
                    variant=line.variant,
                    qty=line.qty,
                    reference_no=order.order_no,
                    actor=actor,
                )
                released_variant_ids.add(line.variant_id)
        from apps.inventory.models import StockMovement

        for mv in StockMovement.objects.select_related("variant").filter(
            reference_no=order.order_no,
            movement_type=StockMovement.MovementType.RESERVE,
            variant__isnull=False,
        ):
            if mv.variant_id not in released_variant_ids:
                release_variant_stock(
                    variant=mv.variant,
                    qty=abs(mv.quantity_delta),
                    reference_no=order.order_no,
                    actor=actor,
                )
                released_variant_ids.add(mv.variant_id)
        reversal_type = (
            DealerLedgerEntry.EntryType.ORDER_REVERSAL
            if next_status == B2bOrder.Status.CANCELLED
            else DealerLedgerEntry.EntryType.REFUND_CREDIT
        )
        reverse_organization_limits(
            organization_id=order.organization_id,
            reference_no=order.order_no,
            entry_type=reversal_type,
            note=f"B2B sipariş {next_status} ters kaydı",
            actor=actor,
        )

    record_audit(
        action="B2B_ORDER_STATUS_UPDATED",
        entity_type="B2bOrder",
        entity_id=order.order_no,
        actor=actor,
        organization=order.organization,
        metadata={"from": prev_status, "to": next_status},
    )
    _schedule_b2b_order_status_webhook(order=order, previous=prev_status, current=next_status)
    if next_status == B2bOrder.Status.CANCELLED:
        _emit_order_cancelled_notifications(
            order_no=order.order_no,
            recipient=(getattr(order.created_by, "email", "") or getattr(order.organization, "email", "") or ""),
            customer_name=order.contact_person or getattr(order.organization, "name", "") or "",
            user_id=order.created_by_id,
            organization_id=str(order.organization_id),
        )
    return order
