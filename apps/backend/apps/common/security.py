"""
Shared security helpers: permission sanitization, safe identifiers, output guards.

Designed to reduce classic AI-codegen failure modes:
- privilege escalation via free-form custom_permissions
- SQL identifier injection in admin/maintenance tooling
- accidental shell/eval execution from agent tooling
"""

from __future__ import annotations

import re
from typing import Iterable

from apps.authorization.constants import ALL_PERMISSIONS, OPS_ROLES

ALLOWED_PERMISSION_SET: frozenset[str] = frozenset(ALL_PERMISSIONS)

# Permissions that must NEVER be granted to customer (B2B/B2C) or supplier roles via custom_permissions.
OPS_ONLY_PERMISSIONS: frozenset[str] = frozenset(
    {
        "catalog:write",
        "catalog:publish",
        "catalog:delete",
        "pricing:edit",
        "rates:edit",
        "orders:manage",
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
        "audit:read",
        "api_keys:read",
        "api_keys:manage",
        "suppliers:manage",
        "supplier_identity:view",
        "quotes:manage",
    }
)

_SAFE_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def sanitize_permissions(
    raw: Iterable[str] | None,
    *,
    role_key: str | None = None,
) -> list[str]:
    """
    Keep only known permission codes; drop unknowns and enforce role-based ceiling
    so customer/supplier roles can never receive ops-only permissions (e.g. supplier_identity:view).
    """
    if not raw:
        return []
    is_ops_role = role_key in OPS_ROLES if role_key else True
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        code = item.strip()
        if code not in ALLOWED_PERMISSION_SET or code in seen:
            continue
        if not is_ops_role and code in OPS_ONLY_PERMISSIONS:
            continue
        seen.add(code)
        out.append(code)
    return out


def can_grant(
    granter_permissions: Iterable[str],
    requested: Iterable[str] | None,
    *,
    is_super_admin: bool = False,
) -> bool:
    """
    Privilege-escalation guard: a user may only grant or deny permissions
    that they themselves possess (SUPER_ADMIN is exempt).
    """
    if is_super_admin:
        return True
    req_set = {p.strip() for p in (requested or []) if isinstance(p, str) and p.strip()}
    if not req_set:
        return True
    granter_set = set(granter_permissions or ())
    return req_set.issubset(granter_set)


def assert_safe_sql_identifier(name: str) -> str:
    """Reject non-identifier strings before interpolating into DDL/DML tooling."""
    if not _SAFE_IDENT.match(name or ""):
        raise ValueError(f"Unsafe SQL identifier rejected: {name!r}")
    return name


def refuse_shell_execution(*_args, **_kwargs):
    """
    Hard stop for agent/tooling paths that might try to run shell commands.
    Import and call this instead of subprocess/os.system in any AI-assisted runtime.
    """
    raise RuntimeError(
        "Shell execution is disabled by Tara Gold security policy (excessive agency guard)."
    )


def refuse_dynamic_code_execution(*_args, **_kwargs):
    """Hard stop for eval/exec/pickle.loads style dynamic execution."""
    raise RuntimeError(
        "Dynamic code execution is disabled by Tara Gold security policy (insecure output handling)."
    )
