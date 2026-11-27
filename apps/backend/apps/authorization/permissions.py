from __future__ import annotations

from typing import TYPE_CHECKING

from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView

from .constants import ALL_PERMISSIONS, B2B_ROLES, OPS_ROLES, ROLE_PERMISSIONS, SUPPLIER_ROLES

if TYPE_CHECKING:
    from apps.organizations.models import OrganizationMembership


def resolve_membership_permissions(membership: "OrganizationMembership") -> list[str]:
    """
    Effective permissions = (role_permissions ∪ sanitized custom_permissions) − sanitized denied_permissions.
    """
    from apps.common.security import sanitize_permissions

    base = set(ROLE_PERMISSIONS.get(membership.role_key, frozenset()))
    base.update(sanitize_permissions(membership.custom_permissions, role_key=membership.role_key))
    denied = set(sanitize_permissions(getattr(membership, "denied_permissions", None)))
    base.difference_update(denied)
    return sorted(base)


def _check_api_key(request: Request, view: APIView) -> bool:
    """
    Enforce explicit api_key_scopes opt-in whenever a request authenticates via ApiKeyAuthentication.
    Returns True if no API key is present or if the key's scopes intersect view.api_key_scopes.
    """
    api_key = getattr(request, "api_key", None)
    if api_key is None:
        return True
    allowed = getattr(view, "api_key_scopes", None)
    if not allowed:
        return False
    key_scopes = set(api_key.scopes or [])
    return bool(key_scopes.intersection(set(allowed)))


class HasPortalPermission(BasePermission):
    """
    Fail-closed permission gate driven by active OrganizationMembership permissions.
    Supports:
      - `required_permission = "pricing:edit"`
      - `required_permissions_by_method = {"GET": "users:read", "POST": "users:manage"}`
      - `allow_any_authenticated = True` (explicit opt-in when no permission code is required)
      - `ops_only = True` (also enforces active OPS/SUPER_ADMIN membership)
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        from apps.organizations.selectors import resolve_tenant_context

        if not request.user or not request.user.is_authenticated:
            return False

        if not _check_api_key(request, view):
            return False

        ctx = resolve_tenant_context(request)
        if getattr(view, "ops_only", False) and not ctx.is_ops:
            return False

        by_method = getattr(view, "required_permissions_by_method", None)
        if isinstance(by_method, dict):
            if request.method in by_method:
                required = by_method[request.method]
            else:
                required = getattr(view, "required_permission", None)
        else:
            required = getattr(view, "required_permission", None)

        if required is None:
            return bool(getattr(view, "allow_any_authenticated", False))
        return required in ctx.permissions


class IsOpsUser(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        from apps.organizations.selectors import resolve_tenant_context

        if not request.user or not request.user.is_authenticated:
            return False
        if not _check_api_key(request, view):
            return False
        ctx = resolve_tenant_context(request)
        return ctx.is_ops


class IsSuperAdminUser(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        from apps.organizations.selectors import resolve_tenant_context

        if not request.user or not request.user.is_authenticated:
            return False
        if not _check_api_key(request, view):
            return False
        if request.user.is_superuser:
            return True
        ctx = resolve_tenant_context(request)
        return ctx.role_key == "SUPER_ADMIN"


class IsB2bOrganizationMember(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        from apps.organizations.selectors import resolve_tenant_context

        if not request.user or not request.user.is_authenticated:
            return False

        api_key = getattr(request, "api_key", None)
        if api_key is not None:
            key_scopes = set(api_key.scopes or [])
            # Read endpoints may use b2b:read; writes need b2b:write.
            if request.method in ("GET", "HEAD", "OPTIONS"):
                if not key_scopes.intersection({"b2b:read", "b2b:write"}):
                    return False
            elif "b2b:write" not in key_scopes:
                return False

        ctx = resolve_tenant_context(request, require_organization=True)
        return "b2b:order" in ctx.permissions


__all__ = [
    "ALL_PERMISSIONS",
    "B2B_ROLES",
    "OPS_ROLES",
    "ROLE_PERMISSIONS",
    "SUPPLIER_ROLES",
    "resolve_membership_permissions",
    "HasPortalPermission",
    "IsOpsUser",
    "IsSuperAdminUser",
    "IsB2bOrganizationMember",
]
