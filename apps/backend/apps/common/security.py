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

from apps.authorization.constants import ALL_PERMISSIONS

ALLOWED_PERMISSION_SET: frozenset[str] = frozenset(ALL_PERMISSIONS)

_SAFE_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def sanitize_permissions(raw: Iterable[str] | None) -> list[str]:
    """Keep only known permission codes; drop unknowns (anti privilege-escalation)."""
    if not raw:
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in raw:
        if not isinstance(item, str):
            continue
        code = item.strip()
        if code in ALLOWED_PERMISSION_SET and code not in seen:
            seen.add(code)
            out.append(code)
    return out


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
