from dataclasses import dataclass
from django.db.models import Q
from apps.authorization.constants import OPS_ROLES, ROLE_PERMISSIONS
from config.exceptions import DomainError
from .models import Branch, Organization, OrganizationMembership


@dataclass(frozen=True)
class TenantContext:
    user: object
    membership: OrganizationMembership | None
    organization: Organization | None
    branch: Branch | None
    role_key: str
    permissions: frozenset[str]
    is_ops: bool


def get_authorized_branches(membership: OrganizationMembership) -> list[Branch]:
    """
    Strict branch authorization: a membership ONLY grants access to branches explicitly
    assigned to `membership.branches` within the same organization. Never auto-opens
    all organization branches when no branch is assigned.
    """
    if membership.organization_id is None:
        return []
    return list(
        membership.branches.filter(
            organization_id=membership.organization_id,
            is_active=True,
        ).order_by("-is_default", "name")
    )


def resolve_tenant_context(
    request,
    *,
    require_organization: bool = False,
    require_branch: bool = False,
) -> TenantContext:
    """
    Resolves active OrganizationMembership, Organization, Branch, and Role Permissions
    deterministically from session + optional X-Membership-Id / X-Organization-Id / X-Branch-Id headers.
    - Never grants unassigned branches.
    - Rejects ambiguous organization memberships when a user holds multiple roles in the same org.
    """
    api_key = getattr(request, "api_key", None)
    if api_key is not None:
        user = getattr(request, "user", None)
        if user is None or not user.is_authenticated:
            raise DomainError("Bu işlem için oturum açmalısınız.", code="UNAUTHENTICATED", status_code=401)

        org = api_key.organization
        if require_organization and org is None:
            raise DomainError(
                "Bu B2B işlemi için aktif bir bayi/firma üyeliği seçilmelidir.",
                code="ORGANIZATION_REQUIRED",
                status_code=403,
            )

        membership = (
            OrganizationMembership.objects.filter(
                user=user,
                organization=org,
                is_active=True,
            )
            .select_related("organization", "default_branch")
            .prefetch_related("branches")
            .first()
        )
        if membership is None and require_organization:
            raise DomainError(
                "API anahtarı sahibi bu firmaya ait aktif üyelik bulundurmalıdır.",
                code="NO_ORGANIZATION",
                status_code=403,
            )

        role_key = (
            membership.role_key
            if membership is not None
            else OrganizationMembership.RoleKey.B2C_CUSTOMER
        )
        branch: Branch | None = None
        if membership is not None and org is not None:
            allowed_branches = get_authorized_branches(membership)
            if allowed_branches:
                branch = allowed_branches[0]

        if membership is not None:
            from apps.authorization.permissions import resolve_membership_permissions

            perms = frozenset(resolve_membership_permissions(membership))
        else:
            perms = ROLE_PERMISSIONS[OrganizationMembership.RoleKey.B2C_CUSTOMER]

        return TenantContext(
            user=user,
            membership=membership,
            organization=org,
            branch=branch,
            role_key=role_key,
            permissions=perms,
            is_ops=False,
        )

    user = getattr(request, "user", None)
    if user is None or not user.is_authenticated:
        if require_organization:
            raise DomainError("Bu işlem için oturum açmalısınız.", code="UNAUTHENTICATED", status_code=401)
        return TenantContext(
            user=user,
            membership=None,
            organization=None,
            branch=None,
            role_key=OrganizationMembership.RoleKey.B2C_CUSTOMER,
            permissions=ROLE_PERMISSIONS[OrganizationMembership.RoleKey.B2C_CUSTOMER],
            is_ops=False,
        )

    memberships = list(
        OrganizationMembership.objects.filter(user=user, is_active=True)
        .select_related("organization", "default_branch")
        .prefetch_related("branches")
        .order_by("created_at")
    )

    if not memberships:
        if require_organization:
            raise DomainError("Aktif firma üyeliğiniz bulunmuyor.", code="NO_ORGANIZATION", status_code=403)
        return TenantContext(
            user=user,
            membership=None,
            organization=None,
            branch=None,
            role_key=OrganizationMembership.RoleKey.B2C_CUSTOMER,
            permissions=ROLE_PERMISSIONS[OrganizationMembership.RoleKey.B2C_CUSTOMER],
            is_ops=False,
        )

    header_membership_id = (request.headers.get("X-Membership-Id") or "").strip()
    header_org_id = (request.headers.get("X-Organization-Id") or "").strip()
    header_branch_id = (request.headers.get("X-Branch-Id") or "").strip()
    session_membership_id = str(request.session.get("active_membership_id", "")).strip()
    session_branch_id = str(request.session.get("active_branch_id", "")).strip()

    active: OrganizationMembership | None = None

    if header_membership_id:
        active = next((m for m in memberships if str(m.id) == header_membership_id), None)
        if active is None:
            raise DomainError(
                "Belirtilen üyelik bağlamına erişim yetkiniz bulunmuyor.",
                code="MEMBERSHIP_ACCESS_DENIED",
                status_code=403,
            )
        if header_org_id and str(active.organization_id or "") != header_org_id:
            raise DomainError(
                "X-Membership-Id ile X-Organization-Id başlıkları birbiriyle uyuşmuyor.",
                code="MEMBERSHIP_ORG_MISMATCH",
                status_code=400,
            )
    elif header_org_id:
        org_matches = [m for m in memberships if str(m.organization_id or "") == header_org_id]
        if not org_matches:
            raise DomainError(
                "Belirtilen firmaya erişim yetkiniz bulunmuyor.",
                code="ORG_ACCESS_DENIED",
                status_code=403,
            )
        if len(org_matches) == 1:
            active = org_matches[0]
        else:
            session_match = next(
                (m for m in org_matches if str(m.id) == session_membership_id),
                None,
            )
            if session_match is None:
                raise DomainError(
                    "Bu firma için birden fazla aktif rolünüz var; lütfen X-Membership-Id veya oturum bağlamını belirtin.",
                    code="AMBIGUOUS_MEMBERSHIP",
                    status_code=400,
                )
            active = session_match
    elif session_membership_id:
        active = next((m for m in memberships if str(m.id) == session_membership_id), None)
        if active is None:
            raise DomainError(
                "Oturumdaki aktif üyelik kaydı geçersiz veya pasif. Lütfen bağlamınızı yeniden seçin.",
                code="INVALID_SESSION_MEMBERSHIP",
                status_code=403,
            )

    if active is None:
        if len(memberships) == 1:
            active = memberships[0]
        else:
            b2c_memberships = [m for m in memberships if m.organization_id is None]
            if len(b2c_memberships) == 1 and not require_organization:
                active = b2c_memberships[0]
            elif require_organization:
                org_memberships = [m for m in memberships if m.organization_id is not None]
                if len(org_memberships) == 1:
                    active = org_memberships[0]
                else:
                    raise DomainError(
                        "Birden fazla firma üyeliğiniz bulunuyor; aktif firma veya üyelik bağlamı seçilmelidir.",
                        code="AMBIGUOUS_MEMBERSHIP",
                        status_code=400,
                    )
            else:
                active = memberships[0]

    org = active.organization
    if require_organization and org is None:
        raise DomainError(
            "Bu B2B işlemi için aktif bir bayi/firma üyeliği seçilmelidir.",
            code="ORGANIZATION_REQUIRED",
            status_code=403,
        )

    branch: Branch | None = None
    if org is not None:
        allowed_branches = get_authorized_branches(active)
        allowed_by_id = {str(b.id): b for b in allowed_branches}

        if header_branch_id:
            branch = allowed_by_id.get(header_branch_id)
            if branch is None:
                raise DomainError(
                    "Bu şubeye erişim yetkiniz bulunmuyor.",
                    code="BRANCH_ACCESS_DENIED",
                    status_code=403,
                )
        elif session_branch_id and session_branch_id in allowed_by_id:
            branch = allowed_by_id[session_branch_id]
        elif active.default_branch_id and str(active.default_branch_id) in allowed_by_id:
            branch = allowed_by_id[str(active.default_branch_id)]
        elif allowed_branches:
            branch = allowed_branches[0]

        if require_branch and branch is None:
            raise DomainError(
                "Bu işlem için yetkili olduğunuz bir şube atanmış olmalıdır.",
                code="BRANCH_REQUIRED",
                status_code=403,
            )

    from apps.authorization.permissions import resolve_membership_permissions

    perms = frozenset(resolve_membership_permissions(active))
    return TenantContext(
        user=user,
        membership=active,
        organization=org,
        branch=branch,
        role_key=active.role_key,
        permissions=perms,
        is_ops=active.role_key in OPS_ROLES,
    )


def resolve_active_organization(organization_id) -> Organization:
    """Resolve an active Organization by id; raises DomainError if missing/inactive."""
    org = Organization.objects.filter(id=organization_id, is_active=True).first()
    if org is None:
        raise DomainError(
            "Belirtilen firma bulunamadı veya pasif.",
            code="ORG_NOT_FOUND",
            status_code=404,
        )
    return org


def resolve_active_branch(
    branch_id,
    *,
    organization: Organization | None = None,
    require_organization_match: bool = True,
) -> Branch:
    """
    Resolve an active Branch and enforce tenant scope:
    - Branch must be active and belong to an active organization.
    - When organization is provided (or require_organization_match), branch.organization must match.
    """
    branch = (
        Branch.objects.select_related("organization")
        .filter(id=branch_id, is_active=True)
        .first()
    )
    if branch is None:
        raise DomainError(
            "Bağlı şube bulunamadı veya pasif.",
            code="BRANCH_NOT_FOUND",
            status_code=404,
        )
    if not branch.organization.is_active:
        raise DomainError(
            "Şubenin bağlı olduğu firma pasif.",
            code="ORG_INACTIVE",
            status_code=400,
        )
    if organization is not None and branch.organization_id != organization.id:
        raise DomainError(
            "Şube, belirtilen firma kapsamında değil.",
            code="BRANCH_ORG_MISMATCH",
            status_code=400,
        )
    if require_organization_match and organization is None and branch.organization_id is None:
        raise DomainError(
            "Şube bir firmaya bağlı olmalıdır.",
            code="BRANCH_ORG_REQUIRED",
            status_code=400,
        )
    return branch


def scope_queryset_to_organization(
    qs,
    ctx: TenantContext,
    *,
    org_field: str = "organization",
    include_shared: bool = False,
):
    """
    Centralized organization tenant-scoping helper.
    - OPS (`ctx.is_ops=True`) sees the full queryset untouched.
    - Non-OPS with `ctx.organization is None` gets `qs.none()` (or shared-only when `include_shared=True`).
    - Non-OPS with an organization is restricted to `ctx.organization` (plus `org_field=None` if `include_shared=True`).
    """
    if ctx.is_ops:
        return qs
    if ctx.organization is None:
        if include_shared:
            return qs.filter(**{f"{org_field}__isnull": True})
        return qs.none()
    if include_shared:
        return qs.filter(Q(**{f"{org_field}__isnull": True}) | Q(**{org_field: ctx.organization}))
    return qs.filter(**{org_field: ctx.organization})


def scope_queryset_to_branch(
    qs,
    ctx: TenantContext,
    *,
    branch_field: str = "branch",
    include_unassigned: bool = False,
):
    """
    Centralized branch tenant-scoping helper.
    - OPS (`ctx.is_ops=True`) sees the full queryset untouched.
    - Non-OPS with `ctx.membership is None` gets `qs.none()`.
    - Restricts queryset to branches returned by `get_authorized_branches(ctx.membership)`.
    - When `include_unassigned=True`, nullable `branch_field=None` rows are also included.
    """
    if ctx.is_ops:
        return qs
    if ctx.membership is None:
        return qs.none()
    allowed_ids = [b.id for b in get_authorized_branches(ctx.membership)]
    if not allowed_ids:
        if include_unassigned:
            return qs.filter(**{f"{branch_field}__isnull": True})
        return qs.none()
    if include_unassigned:
        return qs.filter(Q(**{f"{branch_field}__isnull": True}) | Q(**{f"{branch_field}_id__in": allowed_ids}))
    return qs.filter(**{f"{branch_field}_id__in": allowed_ids})
