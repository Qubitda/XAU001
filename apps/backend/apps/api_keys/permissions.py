from rest_framework.permissions import BasePermission, IsAuthenticated
from rest_framework.request import Request
from rest_framework.views import APIView


def require_api_scope(scope: str) -> type[BasePermission]:
    class _ScopedPermission(BasePermission):
        def has_permission(self, request: Request, view: APIView) -> bool:
            if not request.user or not request.user.is_authenticated:
                return False
            api_key = getattr(request, "api_key", None)
            if api_key is None:
                return True
            return scope in (api_key.scopes or [])

    _ScopedPermission.__name__ = f"HasApiScope_{scope.replace(':', '_')}"
    _ScopedPermission.__qualname__ = _ScopedPermission.__name__
    return _ScopedPermission


def require_any_api_scope(*scopes: str) -> type[BasePermission]:
    wanted = frozenset(scopes)

    class _AnyScopedPermission(BasePermission):
        def has_permission(self, request: Request, view: APIView) -> bool:
            if not request.user or not request.user.is_authenticated:
                return False
            api_key = getattr(request, "api_key", None)
            if api_key is None:
                return True
            key_scopes = set(api_key.scopes or [])
            return bool(key_scopes.intersection(wanted))

    _AnyScopedPermission.__name__ = "HasAnyApiScope_" + "_".join(s.replace(":", "_") for s in scopes)
    _AnyScopedPermission.__qualname__ = _AnyScopedPermission.__name__
    return _AnyScopedPermission


HasApiScopeRead = require_api_scope("storefront:read")
HasApiScopeWrite = require_api_scope("storefront:write")
HasApiScopeMarketRead = require_api_scope("market:read")
HasApiScopeB2bRead = require_api_scope("b2b:read")
HasApiScopeB2bWrite = require_api_scope("b2b:write")
HasApiScopeB2bReadOrWrite = require_any_api_scope("b2b:read", "b2b:write")


class StorefrontScopedPermissionsMixin:
    """GET/HEAD/OPTIONS → storefront:read; mutating methods → storefront:write."""

    def get_permissions(self):
        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsAuthenticated(), HasApiScopeRead()]
        return [IsAuthenticated(), HasApiScopeWrite()]


class B2bScopedPermissionsMixin:
    """GET/HEAD/OPTIONS → b2b:read; mutating → b2b:write (session users skip scope)."""

    def get_permissions(self):
        from apps.authorization.permissions import IsB2bOrganizationMember

        if self.request.method in ("GET", "HEAD", "OPTIONS"):
            return [IsB2bOrganizationMember(), HasApiScopeB2bReadOrWrite()]
        return [IsB2bOrganizationMember(), HasApiScopeB2bWrite()]
