"""Canonical product kind codes mapped from urun_tipi labels/codes."""

from __future__ import annotations

FINISHED = "FINISHED"
MOUNTING = "MOUNTING"
LOOSE_STONE = "LOOSE_STONE"

PRODUCT_KINDS = (FINISHED, MOUNTING, LOOSE_STONE)

KIND_LABELS = {
    FINISHED: "Kuyum (Bitmiş Ürün)",
    MOUNTING: "Montür (Yarı Mamul)",
    LOOSE_STONE: "Taş (Karat / Adet Bazlı)",
}

_LABEL_TO_KIND = {
    KIND_LABELS[FINISHED].lower(): FINISHED,
    KIND_LABELS[MOUNTING].lower(): MOUNTING,
    KIND_LABELS[LOOSE_STONE].lower(): LOOSE_STONE,
    "kuyum": FINISHED,
    "bitmiş ürün": FINISHED,
    "finished": FINISHED,
    "montür": MOUNTING,
    "montur": MOUNTING,
    "yarı mamul": MOUNTING,
    "mounting": MOUNTING,
    "taş": LOOSE_STONE,
    "tas": LOOSE_STONE,
    "loose stone": LOOSE_STONE,
    "loose_stone": LOOSE_STONE,
}

_CODE_TO_KIND = {
    "KUYUM": FINISHED,
    "FINISHED": FINISHED,
    "MONTUR": MOUNTING,
    "MOUNTING": MOUNTING,
    "TAS": LOOSE_STONE,
    "LOOSE_STONE": LOOSE_STONE,
}


def normalize_product_kind(value: str | None, *, default: str = FINISHED) -> str:
    raw = (value or "").strip()
    if not raw:
        return default
    upper = raw.upper().replace(" ", "_")
    if upper in _CODE_TO_KIND:
        return _CODE_TO_KIND[upper]
    if upper in PRODUCT_KINDS:
        return upper
    mapped = _LABEL_TO_KIND.get(raw.lower())
    if mapped:
        return mapped
    # Partial contains
    low = raw.lower()
    if "montür" in low or "montur" in low:
        return MOUNTING
    if "taş" in low or "tas (" in low or low.startswith("taş"):
        return LOOSE_STONE
    if "kuyum" in low or "bitmiş" in low or "finished" in low:
        return FINISHED
    return default


def kind_to_product_type_label(kind: str) -> str:
    return KIND_LABELS.get(normalize_product_kind(kind), KIND_LABELS[FINISHED])
