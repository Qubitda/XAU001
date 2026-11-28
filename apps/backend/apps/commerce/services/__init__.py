import logging
import uuid
from decimal import Decimal, ROUND_HALF_UP
from django.db import transaction
from django.utils import timezone
from apps.audit.services import record_audit
from apps.catalog.models import ProductModel, ProductVariant
from apps.customers.models import Customer
from apps.finance.models import DealerLedgerEntry
from apps.finance.services import reserve_organization_limits, reverse_organization_limits
from apps.inventory.services import (
    release_variant_stock,
    reserve_product_stock,
    reserve_variant_stock,
)
from apps.market.services import get_current_rate_snapshot
from apps.organizations.models import Branch, Organization
from apps.pricing.models import PriceLock
from apps.pricing.services import (
    compute_size_adjusted_gross_weight,
    create_live_quote,
    get_active_price_lock,
    get_or_refresh_price_lock,
    resolve_product_variant,
)
from apps.production.models import WorkOrder
from apps.webhooks.services import emit_webhook_event
from config.exceptions import DomainError
from ..models import B2bDraftLine, B2bOrder, B2bOrderLine, B2cCartItem, B2cOrder, B2cOrderItem

logger = logging.getLogger(__name__)


from .webhooks import (
    _schedule_b2c_order_created_webhook,
    _emit_b2c_payment_success_mail,
    _dispatch_in_app_order_notification,
    _emit_b2c_order_created_mail,
    _emit_b2b_order_created_mail,
    _emit_order_cancelled_notifications,
    _schedule_b2b_order_created_webhook,
    _schedule_b2b_order_status_webhook,
    _record_social_commerce_order_hooks,
)
from .cart import (
    refresh_b2c_cart_price_lock,
    add_b2c_cart_item,
    add_b2b_draft_lines,
)
from .transitions import (
    B2C_ALLOWED_TRANSITIONS,
    B2B_ALLOWED_TRANSITIONS,
    transition_b2c_order_status,
    transition_b2b_order_status,
)
from .b2c_orders import (
    submit_b2c_order,
    finalize_b2c_order_after_payment,
    fail_b2c_pending_payment_order,
)
from .helpers import (
    BANK_TRANSFER_DISCOUNT_RATE,
    GRAM_Q,
    MONEY_Q,
    VAT_DIVISOR,
    _b2c_order_needs_workshop,
    _build_line_sku,
    _create_work_orders_for_b2c_order,
    _q2,
    _q4,
    _resolve_product_and_variant,
    _resolve_size_unit_label,
)

# ── Centralized Order Status State Machines ──────────────────────────────



def _pick_org_address(organization: Organization, *, address_id=None, address_type: str | None = None):
    from apps.organizations.models import OrganizationAddress

    qs = OrganizationAddress.objects.filter(organization=organization, is_active=True)
    if address_id:
        return qs.filter(id=address_id).first()
    if address_type:
        preferred = qs.filter(address_type=address_type, is_default=True).first()
        if preferred:
            return preferred
        return qs.filter(address_type=address_type).first()
    return qs.filter(is_default=True).first() or qs.first()


def _resolve_b2b_address_snapshots(
    *,
    organization: Organization,
    branch: Branch | None,
    payload: dict,
    contact_person: str,
) -> tuple[dict, dict]:
    """Build immutable shipping/billing snapshots for a B2B order."""
    ship_addr = _pick_org_address(
        organization,
        address_id=payload.get("shippingAddressId"),
        address_type="SHIPPING",
    )
    bill_addr = _pick_org_address(
        organization,
        address_id=payload.get("billingAddressId"),
        address_type="BILLING",
    )
    if bill_addr is None:
        bill_addr = ship_addr

    branch_city = branch.city if branch else organization.city
    branch_line = (branch.address if branch and branch.address else "") or organization.city

    def pack(addr, *, title_key: str, city_key: str, line_key: str, fallback_title: str) -> dict:
        if addr is not None:
            return {
                "title": addr.title,
                "city": addr.city or branch_city or "",
                "line": addr.line,
                "contact": addr.contact_name or contact_person,
                "phone": addr.phone or organization.phone or "",
                "tax": organization.tax_office_and_no or "",
            }
        return {
            "title": (payload.get(title_key) or fallback_title).strip(),
            "city": payload.get(city_key) or branch_city or "",
            "line": payload.get(line_key) or branch_line or "",
            "contact": contact_person,
            "phone": organization.phone or "",
            "tax": organization.tax_office_and_no or "",
        }

    return (
        pack(
            ship_addr,
            title_key="shippingTitle",
            city_key="shippingCity",
            line_key="shippingAddress",
            fallback_title="Teslimat",
        ),
        pack(
            bill_addr,
            title_key="billingTitle",
            city_key="billingCity",
            line_key="billingAddress",
            fallback_title="Fatura",
        ),
    )


@transaction.atomic
def submit_b2b_order(
    *,
    user,
    organization: Organization,
    branch: Branch | None,
    payload: dict,
) -> B2bOrder:
    if branch is not None:
        if branch.organization_id != organization.id:
            raise DomainError(
                "Sipariş şubesi aktif firma kapsamında değil.",
                code="BRANCH_ORG_MISMATCH",
                status_code=400,
            )
        if not branch.is_active:
            raise DomainError(
                "Pasif şube ile sipariş oluşturulamaz.",
                code="BRANCH_INACTIVE",
                status_code=400,
            )

    draft_lines = list(
        B2bDraftLine.objects.select_for_update()
        .select_related("variant", "rate_snapshot", "price_quote")
        .filter(organization=organization)
    )
    if not draft_lines:
        raise DomainError("Sipariş fişi onaylamak için en az bir kalem eklemelisiniz.", code="EMPTY_B2B_ORDER", status_code=400)

    snap = get_current_rate_snapshot()
    usd_try = snap.live_usd_sell
    if usd_try <= 0:
        raise DomainError("Geçerli USD/TRY satış kuru bulunamadı.", code="INVALID_RATE", status_code=500)

    for line in draft_lines:
        if line.rate_snapshot_id != snap.id or line.price_quote_id is None:
            product = ProductModel.objects.filter(parent_sku=line.parent_sku).prefetch_related("stone_lines").first()
            if product is None:
                raise DomainError(f"Ürün bulunamadı: {line.parent_sku}", code="PRODUCT_NOT_FOUND", status_code=404)
            variant = line.variant or resolve_product_variant(
                product,
                purity_code=line.purity_code,
                metal_color=line.metal_color,
                size=line.size,
            )
            quote, output = create_live_quote(
                product=product,
                channel="B2B",
                variant=variant,
                organization=organization,
                snapshot=snap,
                size=line.size,
            )
            resolved_variant = quote.variant
            gross_gram = compute_size_adjusted_gross_weight(product, line.size, variant=resolved_variant)
            wholesale_try = _q2(quote.final_price_try)
            wholesale_usd = _q2(wholesale_try / usd_try)
            fire_included_fine = _q4(output.fire_included_fine_metal_gram)
            metal_value_try = fire_included_fine * snap.live_has_gold_try_sell
            labor_and_stone_usd = _q2(max(Decimal("0.00"), (wholesale_try - metal_value_try) / usd_try))

            line.variant = resolved_variant
            line.unit_gross_gram = gross_gram
            line.unit_net_metal_gram = _q4(output.net_metal_gram)
            line.unit_fire_included_fine_gram = fire_included_fine
            line.unit_labor_and_stone_usd = labor_and_stone_usd
            line.unit_wholesale_usd = wholesale_usd
            line.unit_wholesale_try = wholesale_try
            line.pricing_currency = output.lc_currency
            line.rate_snapshot = snap
            line.price_quote = quote
            line.snapshot_code = snap.snapshot_code

    order_no = f"TG-B2B-{timezone.now().year}-{uuid.uuid4().hex[:6].upper()}"

    total_pieces = sum(l.qty for l in draft_lines)
    total_gross = _q4(sum((l.unit_gross_gram * l.qty for l in draft_lines), Decimal("0")))
    total_has = _q4(sum((l.unit_fire_included_fine_gram * l.qty for l in draft_lines), Decimal("0")))
    total_labor_usd = _q2(sum((l.unit_labor_and_stone_usd * l.qty for l in draft_lines), Decimal("0")))
    total_wholesale_usd = _q2(sum((l.unit_wholesale_usd * l.qty for l in draft_lines), Decimal("0")))
    total_wholesale_try = _q2(sum((l.unit_wholesale_try * l.qty for l in draft_lines), Decimal("0")))

    # Concurrency-safe & idempotent credit & has-gold limit validation + reservation
    reserve_organization_limits(
        organization_id=organization.id,
        settlement_method=payload["settlementMethod"],
        total_has_gold_gram=total_has,
        total_labor_and_stone_usd=total_labor_usd,
        total_wholesale_usd=total_wholesale_usd,
        reference_no=order_no,
        actor=user,
    )

    has_production = any(l.supply_type == "PRODUCTION" for l in draft_lines)
    ship_snap, bill_snap = _resolve_b2b_address_snapshots(
        organization=organization,
        branch=branch,
        payload=payload,
        contact_person=payload["contactPerson"],
    )
    order = B2bOrder.objects.create(
        order_no=order_no,
        organization=organization,
        branch=branch,
        created_by=user,
        rate_snapshot=snap,
        usd_try_rate=snap.live_usd_sell,
        gold_rate_try_per_gram=snap.live_has_gold_try_sell,
        contact_person=payload["contactPerson"],
        settlement_method=payload["settlementMethod"],
        rate_lock_mode=payload["rateLockMode"],
        consignment_days=payload.get("consignmentDays"),
        delivery_method=payload["deliveryMethod"],
        order_note=payload.get("orderNote", ""),
        accepted_weight_tolerance=bool(payload.get("acceptedWeightTolerance", True)),
        shipping_title=ship_snap["title"],
        shipping_city=ship_snap["city"],
        shipping_address=ship_snap["line"],
        shipping_contact_name=ship_snap["contact"],
        shipping_phone=ship_snap["phone"],
        billing_title=bill_snap["title"],
        billing_city=bill_snap["city"],
        billing_address=bill_snap["line"],
        billing_contact_name=bill_snap["contact"],
        billing_phone=bill_snap["phone"],
        billing_tax_office_and_no=bill_snap["tax"],
        total_pieces=total_pieces,
        total_gross_gram=total_gross,
        total_has_gold_gram=total_has,
        total_labor_and_stone_usd=total_labor_usd,
        total_wholesale_usd=total_wholesale_usd,
        total_wholesale_try=total_wholesale_try,
        status=B2bOrder.Status.WORKSHOP_PLANNED if has_production else B2bOrder.Status.PROFORMA_CONFIRMED,
    )

    for idx, line in enumerate(draft_lines, start=1):
        resolved_variant = line.variant
        if line.supply_type == "STOCK":
            if resolved_variant is not None:
                reserve_variant_stock(variant=resolved_variant, qty=line.qty, reference_no=order_no, actor=user)
            else:
                mv = reserve_product_stock(parent_sku=line.parent_sku, qty=line.qty, reference_no=order_no, actor=user)
                if mv is not None and mv.variant is not None:
                    resolved_variant = mv.variant
        else:
            WorkOrder.objects.create(
                work_order_no=f"WO-{order_no}-{idx}",
                source_order_no=order_no,
                organization=organization,
                sku=line.sku,
                size=line.size,
                quantity=line.qty,
                engraving_or_stamp_note=line.dealer_stamp_note,
            )

        B2bOrderLine.objects.create(
            order=order,
            variant=resolved_variant,
            sku=line.sku,
            parent_sku=line.parent_sku,
            title=line.title,
            category=line.category,
            metal_color=line.metal_color,
            purity_code=line.purity_code,
            size=line.size,
            size_unit_label=line.size_unit_label,
            qty=line.qty,
            supply_type=line.supply_type,
            dealer_stamp_note=line.dealer_stamp_note,
            unit_gross_gram=line.unit_gross_gram,
            unit_net_metal_gram=line.unit_net_metal_gram,
            unit_fire_included_fine_gram=line.unit_fire_included_fine_gram,
            unit_labor_and_stone_usd=line.unit_labor_and_stone_usd,
            unit_wholesale_usd=line.unit_wholesale_usd,
            unit_wholesale_try=line.unit_wholesale_try,
            pricing_currency=line.pricing_currency,
            rate_snapshot=snap,
            price_quote=line.price_quote,
            snapshot_code=snap.snapshot_code,
        )

    B2bDraftLine.objects.filter(organization=organization).delete()
    from ..models import CartRecoverySession
    from ..recovery import suppress_b2b_draft

    suppress_b2b_draft(
        organization=organization, reason=CartRecoverySession.SuppressReason.CHECKOUT
    )
    record_audit(
        action="B2B_ORDER_CREATED",
        entity_type="B2bOrder",
        entity_id=order_no,
        actor=user,
        organization=organization,
        metadata={
            "total_wholesale_usd": str(order.total_wholesale_usd),
            "total_has_gram": str(order.total_has_gold_gram),
            "snapshot": snap.snapshot_code,
        },
    )
    _schedule_b2b_order_created_webhook(order)
    _emit_b2b_order_created_mail(order)
    return order


@transaction.atomic
def reorder_b2b_order(
    *,
    order_no: str,
    organization: Organization,
    user,
    is_ops: bool = False,
    authorized_branch_ids: list | None = None,
) -> list[B2bDraftLine]:
    order = B2bOrder.objects.filter(order_no=order_no).prefetch_related("lines").first()
    if order is None:
        raise DomainError(f"Sipariş bulunamadı: {order_no}", code="ORDER_NOT_FOUND", status_code=404)
    if not is_ops and order.organization_id != organization.id:
        raise DomainError("Başka firmaya ait sipariş kaydına erişilemez.", code="TENANT_ISOLATION_VIOLATION", status_code=403)
    if not is_ops and authorized_branch_ids is not None and order.branch_id is not None:
        if order.branch_id not in authorized_branch_ids:
            raise DomainError(
                "Başka şubeye ait sipariş kaydına erişilemez.",
                code="BRANCH_ACCESS_DENIED",
                status_code=403,
            )

    items_payload = [
        {
            "parentSku": line.parent_sku,
            "variantId": str(line.variant_id) if line.variant_id else None,
            "purityCode": line.purity_code,
            "metalColor": line.metal_color,
            "size": line.size,
            "qty": line.qty,
            "supplyType": line.supply_type,
            "dealerStampNote": line.dealer_stamp_note,
        }
        for line in order.lines.all()
    ]
    return add_b2b_draft_lines(user=user, organization=organization, items=items_payload, is_ops=is_ops)
