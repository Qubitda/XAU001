"""
Canonical Role & Permission constants for Tara Gold.
Single source of truth imported by authorization.permissions, organizations.selectors,
accounts.api, and Django Admin access mixins.
"""

OPS_ROLES: frozenset[str] = frozenset({"SUPER_ADMIN", "OPS"})
B2B_ROLES: frozenset[str] = frozenset({"ORG_ADMIN", "B2B_BUYER"})
SUPPLIER_ROLES: frozenset[str] = frozenset({"SUPPLIER_ADMIN", "SUPPLIER_USER"})

ALL_PERMISSIONS: tuple[str, ...] = (
    "catalog:read",
    "catalog:write",
    "catalog:publish",
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
    "finance:read",
    "finance:manage",
    "notifications:manage",
    "mail:manage",
    "payments:manage",
    "audit:read",
    "api_keys:read",
    "api_keys:manage",
    "supplier_products:read",
    "supplier_products:write",
    "suppliers:manage",
    "supplier_identity:view",
    "quotes:request",
    "quotes:manage",
    "quotes:respond",
    "reports:read",
    "partner_api:manage",
)

ROLE_PERMISSIONS: dict[str, frozenset[str]] = {
    "SUPER_ADMIN": frozenset(ALL_PERMISSIONS),
    "OPS": frozenset(
        {
            "catalog:read",
            "catalog:write",
            "catalog:publish",
            "pricing:read",
            "pricing:edit",
            "rates:edit",
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
            "finance:read",
            "finance:manage",
            "notifications:manage",
            "mail:manage",
            "payments:manage",
            "audit:read",
            "api_keys:read",
            "api_keys:manage",
            "supplier_products:read",
            "supplier_products:write",
            "suppliers:manage",
            "supplier_identity:view",
            "quotes:request",
            "quotes:manage",
            "quotes:respond",
            "reports:read",
            "partner_api:manage",
        }
    ),
    "ORG_ADMIN": frozenset(
        {
            "catalog:read",
            "pricing:read",
            "b2b:order",
            "org:switch",
            "users:read",
            "users:manage",
            "quotes:request",
            "mail:manage",
            "payments:manage",
        }
    ),
    "B2B_BUYER": frozenset(
        {
            "catalog:read",
            "pricing:read",
            "b2b:order",
            "quotes:request",
            "org:switch",
        }
    ),
    "SUPPLIER_ADMIN": frozenset(
        {
            "catalog:read",
            "supplier_products:read",
            "supplier_products:write",
            "quotes:respond",
            "users:read",
            "users:manage",
            "org:switch",
        }
    ),
    "SUPPLIER_USER": frozenset(
        {
            "supplier_products:read",
            "quotes:respond",
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

_ALL_PERM_SET = frozenset(ALL_PERMISSIONS)
for _role_name, _role_perms in ROLE_PERMISSIONS.items():
    assert _role_perms.issubset(_ALL_PERM_SET), (
        f"ROLE_PERMISSIONS[{_role_name!r}] contains unknown permissions: "
        f"{sorted(_role_perms - _ALL_PERM_SET)}"
    )

__all__ = [
    "OPS_ROLES",
    "B2B_ROLES",
    "SUPPLIER_ROLES",
    "ALL_PERMISSIONS",
    "ROLE_PERMISSIONS",
]
