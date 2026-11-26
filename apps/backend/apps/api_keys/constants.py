KEY_PREFIX = "tg_live_"

DEFAULT_SCOPES: tuple[str, ...] = (
    "storefront:read",
    "storefront:write",
    "market:read",
)

# Integration keys may also request B2B commerce scopes (explicit opt-in at create time).
EXTRA_SCOPES: tuple[str, ...] = (
    "b2b:read",
    "b2b:write",
    "integrations:b2c:write",
)

VALID_SCOPES: frozenset[str] = frozenset((*DEFAULT_SCOPES, *EXTRA_SCOPES))