from decimal import Decimal, ROUND_HALF_UP
from django.contrib.auth import authenticate, login, logout
from django.middleware.csrf import get_token
from drf_spectacular.utils import extend_schema
from rest_framework import permissions, serializers
from rest_framework.request import Request
from rest_framework.views import APIView
from apps.accounts.throttling import LoginRateThrottle
from apps.audit.services import record_audit
from apps.authorization.constants import OPS_ROLES, ROLE_PERMISSIONS
from apps.common.responses import envelope_response
from apps.common.security import sanitize_permissions
from apps.organizations.models import Branch, Organization, OrganizationMembership
from apps.organizations.selectors import get_authorized_branches, resolve_tenant_context
from config.exceptions import DomainError


MONEY_Q = Decimal("0.01")
GRAM_Q = Decimal("0.0001")


def _dec_str(value: Decimal, q: Decimal) -> str:
    return str(Decimal(value).quantize(q, rounding=ROUND_HALF_UP))


def _role_key_to_audience(role_key: str) -> str:
    if role_key in OPS_ROLES:
        return "erp"
    if role_key == OrganizationMembership.RoleKey.B2C_CUSTOMER:
        return "b2c"
    return "b2b"


def _serialize_session(request: Request) -> dict:
    csrf_token = get_token(request)
    user = request.user
    if not user or not user.is_authenticated:
        return {
            "authenticated": False,
            "id": "",
            "email": "",
            "fullName": "Misafir",
            "emailVerified": False,
            "role": "b2c",
            "roleKey": OrganizationMembership.RoleKey.B2C_CUSTOMER,
            "capabilities": sorted(ROLE_PERMISSIONS[OrganizationMembership.RoleKey.B2C_CUSTOMER]),
            "activeMembershipId": "",
            "activeOrganizationId": None,
            "activeBranchId": None,
            "memberships": [],
            "organizations": [],
            "csrfToken": csrf_token,
        }

    ctx = resolve_tenant_context(request)
    memberships = list(
        OrganizationMembership.objects.filter(user=user, is_active=True)
        .select_related("organization", "default_branch")
        .prefetch_related("branches")
        .order_by("created_at")
    )

    # Aggregate only explicitly authorized branches per organization across user memberships.
    org_map: dict[str, dict] = {}
    membership_payload: list[dict] = []
    for m in memberships:
        allowed_branches = get_authorized_branches(m)
        allowed_branch_ids = [str(b.id) for b in allowed_branches]
        default_branch_id = (
            str(m.default_branch_id)
            if m.default_branch_id and str(m.default_branch_id) in allowed_branch_ids
            else (allowed_branch_ids[0] if allowed_branch_ids else None)
        )
        from apps.authorization.permissions import resolve_membership_permissions

        effective_perms = resolve_membership_permissions(m)
        membership_payload.append(
            {
                "id": str(m.id),
                "organizationId": str(m.organization_id) if m.organization_id else None,
                "organizationName": m.organization.name if m.organization else "Bireysel Vitrin (B2C)",
                "organizationCode": m.organization.code if m.organization else "B2C",
                "organizationType": m.organization.org_type if m.organization else "INDIVIDUAL",
                "roleKey": m.role_key,
                "roleLabel": m.get_role_key_display(),
                "audience": _role_key_to_audience(m.role_key),
                "defaultBranchId": default_branch_id,
                "branchIds": allowed_branch_ids,
                "permissions": effective_perms,
            }
        )
        if m.organization is not None:
            org = m.organization
            org_id = str(org.id)
            if org_id not in org_map:
                org_map[org_id] = {
                    "id": org_id,
                    "code": org.code,
                    "name": org.name,
                    "type": org.org_type,
                    "orgType": org.org_type,
                    "taxOfficeAndNo": org.tax_office_and_no,
                    "contactName": org.contact_name,
                    "city": org.city,
                    "creditLimitUsd": _dec_str(org.credit_limit_usd, MONEY_Q),
                    "usedCreditUsd": _dec_str(org.used_credit_usd, MONEY_Q),
                    "hasLimitGram": _dec_str(org.has_limit_gram, GRAM_Q),
                    "usedHasGram": _dec_str(org.used_has_gram, GRAM_Q),
                    "defaultConsignmentDays": org.default_consignment_days,
                    "branches": [],
                    "_seen_branches": set(),
                }
            for b in allowed_branches:
                b_id = str(b.id)
                if b_id not in org_map[org_id]["_seen_branches"]:
                    org_map[org_id]["_seen_branches"].add(b_id)
                    org_map[org_id]["branches"].append(
                        {
                            "id": b_id,
                            "code": b.code,
                            "name": b.name,
                            "city": b.city,
                            "address": b.address,
                            "isDefault": b.is_default,
                        }
                    )

    organizations_payload = []
    for entry in org_map.values():
        entry.pop("_seen_branches", None)
        organizations_payload.append(entry)

    return {
        "authenticated": True,
        "id": str(user.id),
        "email": user.email,
        "fullName": user.full_name or user.email,
        "emailVerified": bool(user.email_verified_at),
        "role": _role_key_to_audience(ctx.role_key),
        "roleKey": ctx.role_key,
        "capabilities": sorted(ctx.permissions),
        "activeMembershipId": str(ctx.membership.id) if ctx.membership else "",
        "activeOrganizationId": str(ctx.organization.id) if ctx.organization else None,
        "activeBranchId": str(ctx.branch.id) if ctx.branch else None,
        "memberships": membership_payload,
        "organizations": organizations_payload,
        "csrfToken": csrf_token,
    }


class LoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)


class ContextSwitchSerializer(serializers.Serializer):
    membershipId = serializers.UUIDField(required=False)
    branchId = serializers.UUIDField(required=False)
    role = serializers.ChoiceField(choices=["erp", "b2b", "b2c"], required=False)


class SessionDetailView(APIView):
    permission_classes = [permissions.AllowAny]

    @extend_schema(tags=["Session"], summary="Aktif oturum ve tenant bağlamı")
    def get(self, request: Request):
        return envelope_response(_serialize_session(request), request)


class SessionLoginView(APIView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginRateThrottle]

    @extend_schema(tags=["Session"], summary="Oturum aç", request=LoginSerializer)
    def post(self, request: Request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = authenticate(
            request,
            email=serializer.validated_data["email"],
            password=serializer.validated_data["password"],
        )
        if user is None:
            # Uniform message + 401 — avoid user enumeration via distinct errors.
            raise DomainError("E-posta veya parola hatalı.", code="INVALID_CREDENTIALS", status_code=401)
        from django.conf import settings as dj_settings

        if getattr(dj_settings, "ENFORCE_EMAIL_VERIFICATION", False) and not user.email_verified_at:
            raise DomainError(
                "E-posta adresiniz doğrulanmamış. Gelen kutunuzdaki bağlantıyı kullanın.",
                code="EMAIL_NOT_VERIFIED",
                status_code=403,
            )
        login(request, user)
        memberships = list(
            OrganizationMembership.objects.filter(user=user, is_active=True).order_by("created_at")
        )
        # Prefer platform/ops membership so OPS portal login does not land on B2C context.
        first_membership = next(
            (
                m
                for m in memberships
                if m.role_key
                in (
                    OrganizationMembership.RoleKey.SUPER_ADMIN,
                    OrganizationMembership.RoleKey.OPS,
                )
            ),
            memberships[0] if memberships else None,
        )
        if first_membership is not None:
            request.session["active_membership_id"] = str(first_membership.id)
            allowed = get_authorized_branches(first_membership)
            if first_membership.default_branch_id and any(
                b.id == first_membership.default_branch_id for b in allowed
            ):
                request.session["active_branch_id"] = str(first_membership.default_branch_id)
            elif allowed:
                request.session["active_branch_id"] = str(allowed[0].id)
            else:
                request.session.pop("active_branch_id", None)
        record_audit(action="USER_LOGIN", entity_type="User", entity_id=str(user.id), actor=user)
        return envelope_response(_serialize_session(request), request)


class SessionLogoutView(APIView):
    @extend_schema(tags=["Session"], summary="Oturumu kapat")
    def post(self, request: Request):
        record_audit(action="USER_LOGOUT", entity_type="User", entity_id=str(request.user.id), actor=request.user)
        logout(request)
        return envelope_response({"loggedOut": True}, request)


class SessionContextSwitchView(APIView):
    @extend_schema(tags=["Session"], summary="Aktif üyelik/şube bağlamını değiştir", request=ContextSwitchSerializer)
    def patch(self, request: Request):
        serializer = ContextSwitchSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        memberships = list(
            OrganizationMembership.objects.filter(user=request.user, is_active=True)
            .select_related("organization", "default_branch")
            .prefetch_related("branches")
            .order_by("created_at")
        )
        target_membership: OrganizationMembership | None = None

        if "membershipId" in data:
            target_membership = next((m for m in memberships if m.id == data["membershipId"]), None)
            if target_membership is None:
                raise DomainError(
                    "Bu üyeliğe geçiş yetkiniz bulunmuyor.",
                    code="MEMBERSHIP_ACCESS_DENIED",
                    status_code=403,
                )
        elif "role" in data:
            desired_audience = data["role"]
            role_matches = [
                m for m in memberships if _role_key_to_audience(m.role_key) == desired_audience
            ]
            if not role_matches:
                raise DomainError(
                    f"Kullanıcının '{desired_audience}' rolünde aktif üyeliği yok.",
                    code="ROLE_NOT_ASSIGNED",
                    status_code=403,
                )
            # Prefer current session membership if it already matches the requested audience.
            current_session_id = str(request.session.get("active_membership_id", ""))
            target_membership = next(
                (m for m in role_matches if str(m.id) == current_session_id),
                role_matches[0],
            )

        if target_membership is not None:
            request.session["active_membership_id"] = str(target_membership.id)
            allowed = get_authorized_branches(target_membership)
            if target_membership.default_branch_id and any(
                b.id == target_membership.default_branch_id for b in allowed
            ):
                request.session["active_branch_id"] = str(target_membership.default_branch_id)
            elif allowed:
                request.session["active_branch_id"] = str(allowed[0].id)
            else:
                request.session.pop("active_branch_id", None)

        if "branchId" in data:
            ctx = resolve_tenant_context(request, require_organization=True)
            assert ctx.membership is not None
            allowed_branches = get_authorized_branches(ctx.membership)
            branch = next((b for b in allowed_branches if b.id == data["branchId"]), None)
            if branch is None:
                raise DomainError(
                    "Seçilen şube aktif üyeliğinize atanmamış.",
                    code="BRANCH_ACCESS_DENIED",
                    status_code=403,
                )
            request.session["active_branch_id"] = str(branch.id)

        request.session.modified = True
        return envelope_response(_serialize_session(request), request)


SessionView = SessionDetailView
LoginView = SessionLoginView
LogoutView = SessionLogoutView
SessionContextView = SessionContextSwitchView

