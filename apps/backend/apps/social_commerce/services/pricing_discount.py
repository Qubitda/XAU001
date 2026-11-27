from __future__ import annotations

from decimal import Decimal, ROUND_HALF_UP
from typing import Any

from django.db.models import Q
from django.utils import timezone

from ..models import AffiliateCode, SocialCampaign

MAX_SOCIAL_DISCOUNT_PCT = Decimal("30.00")


def _q2(val: Decimal) -> Decimal:
    return val.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def resolve_social_checkout_discount(
    *,
    subtotal_final_try: Decimal,
    campaign_code: str = "",
    affiliate_code: str = "",
    audience: str = "B2C",
    organization=None,
    now=None,
) -> dict[str, Any]:
    """
    Resolve active SocialCampaign / AffiliateCode discount for checkout without bypassing
    central pricing engine rules:
    - Validates active status, date window (starts_at / ends_at), audience, and organization scope.
    - Never stacks campaign + affiliate discounts; applies the higher single eligible discount.
    - Enforces MAX_SOCIAL_DISCOUNT_PCT safety cap (30.00%).
    """
    if subtotal_final_try <= Decimal("0.00"):
        return {
            "discountPct": Decimal("0.00"),
            "discountTry": Decimal("0.00"),
            "sourceCode": "",
            "sourceType": "",
        }

    ts = now or timezone.now()
    best_pct = Decimal("0.00")
    source_code = ""
    source_type = ""

    aff_clean = (affiliate_code or "").strip()
    if aff_clean:
        ac = (
            AffiliateCode.objects.select_related("influencer", "campaign")
            .filter(code__iexact=aff_clean, is_active=True, influencer__is_active=True)
            .first()
        )
        if ac is not None:
            camp_ok = True
            if ac.campaign is not None:
                c = ac.campaign
                camp_ok = (
                    c.is_active
                    and c.audience == audience
                    and (c.starts_at is None or c.starts_at <= ts)
                    and (c.ends_at is None or c.ends_at >= ts)
                    and (organization is None or c.organization_id in (None, organization.id))
                )
            if camp_ok:
                pct = ac.discount_pct
                if pct <= Decimal("0.00") and ac.campaign is not None:
                    pct = ac.campaign.discount_pct
                if pct > best_pct:
                    best_pct = pct
                    source_code = ac.code
                    source_type = "AFFILIATE"

    camp_clean = (campaign_code or "").strip()
    if camp_clean:
        qs = (
            SocialCampaign.objects.filter(code__iexact=camp_clean, is_active=True, audience=audience)
            .filter(Q(starts_at__isnull=True) | Q(starts_at__lte=ts))
            .filter(Q(ends_at__isnull=True) | Q(ends_at__gte=ts))
        )
        if audience == "B2C":
            qs = qs.filter(organization__isnull=True)
        elif organization is not None:
            qs = qs.filter(Q(organization__isnull=True) | Q(organization=organization))
        camp = qs.first()
        if camp is not None and camp.discount_pct > best_pct:
            best_pct = camp.discount_pct
            source_code = camp.code
            source_type = "CAMPAIGN"

    applied_pct = min(max(best_pct, Decimal("0.00")), MAX_SOCIAL_DISCOUNT_PCT)
    discount_try = (
        _q2(subtotal_final_try * (applied_pct / Decimal("100.00")))
        if applied_pct > Decimal("0.00")
        else Decimal("0.00")
    )
    return {
        "discountPct": applied_pct,
        "discountTry": discount_try,
        "sourceCode": source_code,
        "sourceType": source_type,
    }
