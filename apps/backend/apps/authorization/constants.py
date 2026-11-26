"""
Canonical Role & Permission constants for Tara Gold.
Single source of truth imported by authorization.permissions, organizations.selectors,
accounts.api, and Django Admin access mixins.
"""

OPS_ROLES: frozenset[str] = frozenset({"SUPER_ADMIN", "OPS"})
B2B_ROLES: frozenset[str] = frozenset({"ORG_ADMIN", "B2B_BUYER"})

ALL_PERMISSIONS: tuple[str, ...] = (
    "catalog:read",
    "catalog:write",
    "catalog:delete",
    "pricing:read",
    "pricing:edit",
    "rates:edit",
    "b2b:order",
    "b2c:order",
    "orders:manage",
    "org:switch",
    "users:read",
    "users:manage",
    "orgs:manage",
    "customers:manage",
    "carts:view",
    "consents:view",
    "consents:manage",
    "contracts:view",
    "legal_docs:manage",
    "inventory:manage",
    "production:manage",
    "finance:manage",
    "notifications:manage",
    "mail:manage",
    "payments:manage",
    "audit:read",
    "api_keys:read",
    "api_keys:manage",
)

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "SUPER_ADMIN": frozenset(ALL_PERMISSIONS),
    "OPS": frozenset(
        {
            "catalog:read",
            "catalog:write",
            "pricing:read",
            "pricing:edit",
            "rates:edit",
            "orders:manage",
            "org:switch",
            "users:read",
            "orgs:manage",
            "customers:manage",
            "carts:view",
            "consents:view",
            "consents:manage",
            "contracts:view",
            "legal_docs:manage",
            "inventory:manage",
            "production:manage",
            "finance:manage",
            "notifications:manage",
            "mail:manage",
            "payments:manage",
            "audit:read",
            "api_keys:read",
            "api_keys:manage",
        }
    ),
    "ORG_ADMIN": frozenset(
        {
            "catalog:read",
            "pricing:read",
            "b2b:order",
            "org:switch",
            "mail:manage",
            "payments:manage",
        }
    ),
    "B2B_BUYER": frozenset(
        {
            "catalog:read",
            "pricing:read",
            "b2b:order",
            "org:switch",
        }
    ),
    "B2C_CUSTOMER": frozenset(
        {
            "catalog:read",
            "pricing:read",
            "b2c:order",
            "org:switch",
        }
    ),
}
