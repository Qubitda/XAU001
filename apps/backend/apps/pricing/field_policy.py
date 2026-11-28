"""Policy defining which product PATCH fields affect live pricing."""
from __future__ import annotations

from collections.abc import Mapping
from typing import Any

PRICE_AFFECTING_FIELDS: frozenset[str] = frozenset(
    {
        "pricingMode",
        "ledger",
        "grossWeightGram",
        "fireRatePct",
        "purityCode",
        "stoneLines",
        "centerStoneCarat",
        "sideStoneCarat",
        "mountSpec",
        "productKind",
        "finishedDetail",
        "mountingDetail",
        "looseStoneDetail",
    }
)


def payload_affects_price(validated_data: Mapping[str, Any]) -> bool:
    """Return True if any key in the validated PATCH payload affects product pricing."""
    return any(key in validated_data for key in PRICE_AFFECTING_FIELDS)
