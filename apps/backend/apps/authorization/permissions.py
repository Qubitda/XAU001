from rest_framework.permissions import BasePermission
from rest_framework.request import Request
from rest_framework.views import APIView
from .constants import OPS_ROLES, ROLE_PERMISSIONS


def resolve_membership_permissions(membership) -> list[str]:
    from apps.common.security import sanitize_permissions

    base = set(ROLE_PERMISSIONS.get(membership.role_key, frozenset()))
    base.update(sanitize_permissions(membership.custom_permissions))
    return sorted(base)


class HasPortalPermission(BasePermission):
    """
    Permission-based gate driven by active OrganizationMembership permissions.
    Supports:
      - `required_permission = "pricing:edit"`
      - `required_permissions_by_method = {"GET": "users:read", "POST": "users:manage"}`
      - `ops_only = True` (also enforces active OPS/SUPER_ADMIN membership)
    """

    def has_permission(self, request: Request, view: APIView) -> bool:
        from apps.organizations.selectors import resolve_tenant_context

        if not request.user or not request.user.is_authenticated:
            return False

        # API keys authenticate as created_by but must not inherit portal RBAC
        # unless the view explicitly opts in via api_key_scopes.
        api_key = getattr(request, "api_key", None)
        if api_key is not None:
            allowed = getattr(view, "api_key_scopes", None)
            if not allowed:
                return False
            key_scopes = set(api_key.scopes or [])
            if not key_scopes.intersection(set(allowed)):
                return False

        ctx = resolve_tenant_context(request)
        if getattr(view, "ops_only", False) and not ctx.is_ops:
            return False

        by_method = getattr(view, "required_permissions_by_method", None)
        if isinstance(by_method, dict) and request.method in by_method:
            required = by_method[request.method]
        else:
            required = getattr(view, "required_permission", None)

        if required is None:
            return True
        return required in ctx.permissions


class IsOpsUser(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        from apps.organizations.selectors import resolve_tenant_context

        if not request.user or not request.user.is_authenticated:
            return False
        ctx = resolve_tenant_context(request)
        return ctx.is_ops


class IsSuperAdminUser(BasePermission):
    def has_permission(self, request: Request, view: APIView) -> bool:
        from apps.organizations.selectors import resolve_tenant_context

        if not request.user or not request.user.is_authenticated:
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
    "OPS_ROLES",
    "ROLE_PERMISSIONS",
    "resolve_membership_permissions",
    "HasPortalPermission",
    "IsOpsUser",
    "IsSuperAdminUser",
    "IsB2bOrganizationMember",
]
