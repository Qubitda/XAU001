"""
Hardcoded product sales channels — operational flow depends on these codes.
Not editable via Tanım Tabloları UI.

Deployment entitlement (what the customer purchased) is controlled by:
  ENABLED_SALES_CHANNELS=B2B,B2B_API
Omit B2C_API when the customer did not buy B2C API / storefront integration.
"""

from __future__ import annotations

import os

SALES_CHANNEL_B2B = "B2B"
SALES_CHANNEL_B2B_API = "B2B_API"
SALES_CHANNEL_B2C_API = "B2C_API"

SALES_CHANNELS: tuple[tuple[str, str], ...] = (
    (SALES_CHANNEL_B2B, "B2B (Bayi Portalı)"),
    (SALES_CHANNEL_B2B_API, "B2B API"),
    (SALES_CHANNEL_B2C_API, "B2C API"),
)

SALES_CHANNEL_CODES: frozenset[str] = frozenset(code for code, _ in SALES_CHANNELS)

# Legacy aliases accepted on read / resolve paths
SALES_CHANNEL_ALIASES: dict[str, str] = {
    "B2C": SALES_CHANNEL_B2C_API,
    "BOTH": SALES_CHANNEL_B2B,  # BOTH is invalid going forward; prefer explicit B2B
}


def _enabled_channel_codes() -> frozenset[str]:
    raw = os.environ.get("ENABLED_SALES_CHANNELS", "").strip()
    if not raw:
        return SALES_CHANNEL_CODES
    codes = {c.strip().upper().replace("-", "_") for c in raw.split(",") if c.strip()}
    return frozenset(c for c in codes if c in SALES_CHANNEL_CODES) or SALES_CHANNEL_CODES


def normalize_sales_channel(code: str) -> str | None:
    raw = (code or "").strip().upper().replace("-", "_").replace(" ", "_")
    if raw in SALES_CHANNEL_ALIASES:
        raw = SALES_CHANNEL_ALIASES[raw]
    if raw not in SALES_CHANNEL_CODES:
        return None
    if raw not in _enabled_channel_codes():
        return None
    return raw


def serialize_sales_channels() -> list[dict]:
    enabled = _enabled_channel_codes()
    return [
        {"code": code, "label": label, "isSystem": True}
        for code, label in SALES_CHANNELS
        if code in enabled
    ]
