from django.contrib import admin
from apps.authorization.constants import OPS_ROLES
from apps.organizations.models import OrganizationMembership


def configure_admin_site() -> None:
    admin.site.site_header = "Tara Gold — Operasyon & PIM Yönetimi"
    admin.site.site_title = "Tara Gold Admin"
    admin.site.index_title = "Kuyumculuk ERP, Katalog, Fiyatlama & Finans Yönetimi"


def user_is_ops_admin(user) -> bool:
    """
    Strict Django Admin access check:
    - Superusers always have OPS admin access.
    - Non-superuser staff MUST hold an active SUPER_ADMIN or OPS OrganizationMembership.
    - Dealer / B2C / unassigned staff accounts are strictly blocked from viewing tenant data.
    """
    if not user or not user.is_authenticated or not user.is_active:
        return False
    if user.is_superuser:
        return True
    if not user.is_staff:
        return False
    return OrganizationMembership.objects.filter(
        user=user,
        is_active=True,
        role_key__in=OPS_ROLES,
    ).exists()


class OpsRestrictedAdminMixin:
    """
    Base security mixin applied to every Tara Gold Django Admin ModelAdmin.
    Enforces OPS-only visibility across modules, changelists, objects, and querysets.
    """

    def _is_authorized(self, request) -> bool:
        return user_is_ops_admin(request.user)

    def get_queryset(self, request):
        qs = super().get_queryset(request)  # type: ignore[misc]
        if not self._is_authorized(request):
            return qs.none()
        return qs

    def has_module_permission(self, request) -> bool:
        return self._is_authorized(request)

    def has_view_permission(self, request, obj=None) -> bool:
        return self._is_authorized(request)

    def has_add_permission(self, request) -> bool:
        return self._is_authorized(request)

    def has_change_permission(self, request, obj=None) -> bool:
        return self._is_authorized(request)

    def has_delete_permission(self, request, obj=None) -> bool:
        return self._is_authorized(request)


class NoDeleteAdminMixin(OpsRestrictedAdminMixin):
    """Prevents destructive deletion of financial, order, or master tenant records in Admin."""

    def has_delete_permission(self, request, obj=None) -> bool:
        return False

    def get_actions(self, request):
        actions = super().get_actions(request)  # type: ignore[misc]
        actions.pop("delete_selected", None)
        return actions


class ImmutableAdminMixin(NoDeleteAdminMixin):
    """
    Strictly read-only Admin mixin for immutable historical records:
    AuditLog, RateSnapshot, PriceQuote, StockMovement, DealerLedgerEntry, Order lines.
    """

    def has_add_permission(self, request) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False


class ReadOnlyInlineMixin:
    """Read-only TabularInline for immutable child rows (e.g. Order items/lines)."""

    can_delete = False
    extra = 0

    def has_add_permission(self, request, obj=None) -> bool:
        return False

    def has_change_permission(self, request, obj=None) -> bool:
        return False

    def has_delete_permission(self, request, obj=None) -> bool:
        return False
