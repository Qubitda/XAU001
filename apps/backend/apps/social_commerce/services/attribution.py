from __future__ import annotations

from decimal import Decimal
from typing import Any

from django.db import IntegrityError, transaction
from django.db.models import Count, Q, Sum

from ..models import AffiliateConversion, SocialAttribution, SocialPlatform


@transaction.atomic
def record_verified_order_attribution(
    *,
    order_no: str,
    revenue_try: Decimal,
    customer=None,
    session_key: str = "",
    platform: str = "",
    utm_source: str = "",
    utm_medium: str = "",
    utm_campaign: str = "",
    audience: str = "B2C",
) -> SocialAttribution | None:
    """
    Server-side verified order attribution:
    - Idempotent per (event_type='ORDER', order_no).
    - Preserves FIRST_TOUCH / LAST_TOUCH / ASSISTED roles from prior traffic events.
    """
    if SocialAttribution.objects.filter(event_type="ORDER", order_no=order_no).exists():
        return None

    prior_qs = SocialAttribution.objects.exclude(event_type="ORDER")
    if session_key:
        prior_qs = prior_qs.filter(session_key=session_key)
    elif customer is not None:
        prior_qs = prior_qs.filter(customer=customer)
    else:
        prior_qs = prior_qs.none()

    first_touch = prior_qs.order_by("created_at").first()
    last_touch = prior_qs.order_by("-created_at").first()

    resolved_platform = (
        platform.upper()
        if platform and platform.upper() in SocialPlatform.values
        else (last_touch.platform if last_touch else "")
    )
    if not resolved_platform:
        return None

    if first_touch and last_touch and first_touch.id != last_touch.id:
        SocialAttribution.objects.filter(id=first_touch.id).update(
            touch_role=SocialAttribution.TouchRole.FIRST_TOUCH
        )
        SocialAttribution.objects.filter(
            id__in=prior_qs.exclude(id__in=[first_touch.id, last_touch.id]).values_list("id", flat=True)
        ).update(touch_role=SocialAttribution.TouchRole.ASSISTED)

    try:
        with transaction.atomic():
            return SocialAttribution.objects.create(
                platform=resolved_platform,
                touch_role=SocialAttribution.TouchRole.LAST_TOUCH,
                utm_source=(utm_source or (last_touch.utm_source if last_touch else ""))[:80],
                utm_medium=(utm_medium or (last_touch.utm_medium if last_touch else ""))[:80],
                utm_campaign=(utm_campaign or (last_touch.utm_campaign if last_touch else ""))[:120],
                customer=customer,
                session_key=session_key[:64],
                event_type="ORDER",
                order_no=order_no,
                revenue_try=revenue_try,
                audience=audience,
            )
    except IntegrityError:
        return None


def get_social_analytics_summary() -> dict[str, Any]:
    """Return real aggregated social commerce metrics (separating CLICK/VIEW/SHARE and excluding refunds)."""
    by_channel = list(
        SocialAttribution.objects.filter(event_type="ORDER")
        .values("platform")
        .annotate(
            orders=Count("id"),
            revenue_try=Sum("revenue_try"),
        )
        .order_by("platform")
    )
    traffic_by_channel = list(
        SocialAttribution.objects.exclude(event_type="ORDER")
        .values("platform")
        .annotate(
            clicks=Count("id", filter=Q(event_type="CLICK")),
            views=Count("id", filter=Q(event_type="VIEW")),
            shares=Count("id", filter=Q(event_type="SHARE")),
        )
        .order_by("platform")
    )
    traffic_map = {row["platform"]: row for row in traffic_by_channel}

    affiliate_totals = AffiliateConversion.objects.exclude(
        status=AffiliateConversion.Status.CANCELLED_REFUNDED
    ).aggregate(
        conversions=Count("id"),
        net_sales_try=Sum("net_amount_try"),
        commission_try=Sum("commission_amount_try"),
    )
    return {
        "channels": [
            {
                "platform": row["platform"],
                "orders": row["orders"],
                "clicks": traffic_map.get(row["platform"], {}).get("clicks", 0),
                "views": traffic_map.get(row["platform"], {}).get("views", 0),
                "shares": traffic_map.get(row["platform"], {}).get("shares", 0),
                "revenueTry": str((row["revenue_try"] or Decimal("0.00")).quantize(Decimal("0.01"))),
            }
            for row in by_channel
        ],
        "affiliate": {
            "conversions": affiliate_totals["conversions"] or 0,
            "netSalesTry": str((affiliate_totals["net_sales_try"] or Decimal("0.00")).quantize(Decimal("0.01"))),
            "commissionTry": str((affiliate_totals["commission_try"] or Decimal("0.00")).quantize(Decimal("0.01"))),
        },
    }
