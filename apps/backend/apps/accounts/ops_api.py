from django.contrib.auth.password_validation import validate_password
from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.views import APIView
from apps.audit.services import record_audit
from apps.authorization.constants import ALL_PERMISSIONS, OPS_ROLES, ROLE_PERMISSIONS
from apps.authorization.permissions import HasPortalPermission
from apps.common.responses import (
    apply_safe_ordering,
    envelope_response,
    paginated_envelope_response,
    parse_bool_param,
)
from apps.common.security import sanitize_permissions
from apps.organizations.models import OrganizationMembership
from apps.organizations.selectors import resolve_tenant_context
from config.exceptions import DomainError
from .models import User


def serialize_ops_user(user: User) -> dict:
    memberships = list(user.memberships.all())
    return {
        "id": str(user.id),
        "email": user.email,
        "fullName": user.full_name,
        "phone": user.phone,
        "isActive": user.is_active,
        "isStaff": user.is_staff,
        "isSuperuser": user.is_superuser,
        "lastLogin": user.last_login.isoformat() if user.last_login else None,
        "createdAt": user.created_at.isoformat(),
        "updatedAt": user.updated_at.isoformat(),
        "memberships": [
            {
                "id": str(m.id),
                "organizationId": str(m.organization_id) if m.organization_id else None,
                "organizationCode": m.organization.code if m.organization else None,
                "organizationName": m.organization.name if m.organization else "Bireysel Vitrin (B2C)",
                "roleKey": m.role_key,
                "defaultBranchId": str(m.default_branch_id) if m.default_branch_id else None,
                "branchIds": [str(b.id) for b in m.branches.all()],
                "customPermissions": sanitize_permissions(m.custom_permissions),
                "isActive": m.is_active,
            }
            for m in memberships
        ],
    }


class OpsUserCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    fullName = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    password = serializers.CharField(write_only=True, min_length=8, required=False, allow_blank=False)
    isActive = serializers.BooleanField(required=False, default=True)
    isStaff = serializers.BooleanField(required=False, default=False)
    isSuperuser = serializers.BooleanField(required=False, default=False)

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value


class OpsUserUpdateSerializer(serializers.Serializer):
    email = serializers.EmailField(required=False)
    fullName = serializers.CharField(max_length=150, required=False)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    password = serializers.CharField(write_only=True, min_length=8, required=False)
    isActive = serializers.BooleanField(required=False)
    isStaff = serializers.BooleanField(required=False)
    isSuperuser = serializers.BooleanField(required=False)

    def validate_password(self, value: str) -> str:
        validate_password(value)
        return value


def _users_queryset():
    return User.objects.prefetch_related(
        "memberships__organization",
        "memberships__default_branch",
        "memberships__branches",
    )


class OpsUserListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "GET": "users:read",
        "POST": "users:manage",
    }

    @extend_schema(tags=["OPS - Users"], summary="Kullanıcıları listele, ara ve filtrele")
    def get(self, request: Request):
        qs = _users_queryset()
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(Q(email__icontains=q) | Q(full_name__icontains=q) | Q(phone__icontains=q))

        is_active = parse_bool_param(request.query_params.get("isActive") or request.query_params.get("is_active"))
        if is_active is not None:
            qs = qs.filter(is_active=is_active)

        is_staff = parse_bool_param(request.query_params.get("isStaff") or request.query_params.get("is_staff"))
        if is_staff is not None:
            qs = qs.filter(is_staff=is_staff)

        role_key = (request.query_params.get("roleKey") or request.query_params.get("role_key") or "").strip()
        if role_key:
            qs = qs.filter(memberships__role_key=role_key, memberships__is_active=True).distinct()

        org_id = (request.query_params.get("organizationId") or "").strip()
        if org_id:
            qs = qs.filter(memberships__organization_id=org_id).distinct()

        qs = apply_safe_ordering(
            qs,
            request,
            allowed_fields={
                "email": "email",
                "fullName": "full_name",
                "createdAt": "created_at",
                "lastLogin": "last_login",
            },
            default="-created_at",
        )
        return paginated_envelope_response(qs, request, serialize_ops_user)

    @extend_schema(tags=["OPS - Users"], summary="Yeni kullanıcı oluştur", request=OpsUserCreateSerializer)
    @transaction.atomic
    def post(self, request: Request):
        serializer = OpsUserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        if d.get("isSuperuser") and not request.user.is_superuser:
            raise DomainError(
                "Yalnızca süper yöneticiler superuser yetkisi atayabilir.",
                code="PRIVILEGE_ESCALATION_DENIED",
                status_code=403,
            )

        email = d["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise DomainError("Bu e-posta adresi ile kayıtlı bir kullanıcı zaten var.", code="DUPLICATE_EMAIL", status_code=409)

        user = User.objects.create_user(
            email=email,
            password=d.get("password"),
            full_name=d["fullName"].strip(),
            phone=d.get("phone", "").strip(),
            is_active=d.get("isActive", True),
            is_staff=d.get("isStaff", False),
            is_superuser=d.get("isSuperuser", False),
        )
        record_audit(
            action="OPS_USER_CREATED",
            entity_type="User",
            entity_id=str(user.id),
            actor=request.user,
            metadata={"email": user.email, "is_staff": user.is_staff, "is_superuser": user.is_superuser},
        )
        user = _users_queryset().get(id=user.id)
        return envelope_response(serialize_ops_user(user), request, status=201)


class OpsUserDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "GET": "users:read",
        "PATCH": "users:manage",
        "DELETE": "users:manage",
    }

    @extend_schema(tags=["OPS - Users"], summary="Kullanıcı detayını getir")
    def get(self, request: Request, user_id: str):
        user = _users_queryset().filter(id=user_id).first()
        if user is None:
            raise DomainError("Kullanıcı bulunamadı.", code="USER_NOT_FOUND", status_code=404)
        return envelope_response(serialize_ops_user(user), request)

    @extend_schema(tags=["OPS - Users"], summary="Kullanıcı bilgilerini güncelle", request=OpsUserUpdateSerializer)
    @transaction.atomic
    def patch(self, request: Request, user_id: str):
        user = User.objects.select_for_update().filter(id=user_id).first()
        if user is None:
            raise DomainError("Kullanıcı bulunamadı.", code="USER_NOT_FOUND", status_code=404)

        serializer = OpsUserUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        if "isSuperuser" in d and d["isSuperuser"] != user.is_superuser and not request.user.is_superuser:
            raise DomainError(
                "Yalnızca süper yöneticiler superuser yetkisini değiştirebilir.",
                code="PRIVILEGE_ESCALATION_DENIED",
                status_code=403,
            )
        if user.is_superuser and not request.user.is_superuser:
            raise DomainError(
                "Süper yönetici hesabı yalnızca başka bir süper yönetici tarafından düzenlenebilir.",
                code="PRIVILEGE_ESCALATION_DENIED",
                status_code=403,
            )

        changed_fields: list[str] = []
        if "email" in d:
            new_email = d["email"].strip().lower()
            if User.objects.filter(email__iexact=new_email).exclude(id=user.id).exists():
                raise DomainError("Bu e-posta adresi başka bir kullanıcı tarafından kullanılıyor.", code="DUPLICATE_EMAIL", status_code=409)
            user.email = new_email
            changed_fields.append("email")
        if "fullName" in d:
            user.full_name = d["fullName"].strip()
            changed_fields.append("full_name")
        if "phone" in d:
            user.phone = d["phone"].strip()
            changed_fields.append("phone")
        if "isActive" in d:
            if user.id == request.user.id and d["isActive"] is False:
                raise DomainError("Kendi oturumunuzu pasifleştiremezsiniz.", code="SELF_DEACTIVATE_FORBIDDEN", status_code=400)
            user.is_active = d["isActive"]
            changed_fields.append("is_active")
        if "isStaff" in d:
            user.is_staff = d["isStaff"]
            changed_fields.append("is_staff")
        if "isSuperuser" in d:
            user.is_superuser = d["isSuperuser"]
            changed_fields.append("is_superuser")
        if "password" in d:
            user.set_password(d["password"])
            changed_fields.append("password")

        if changed_fields:
            user.save(update_fields=[*changed_fields, "updated_at"])
            record_audit(
                action="OPS_USER_UPDATED",
                entity_type="User",
                entity_id=str(user.id),
                actor=request.user,
                metadata={"changed_fields": [f for f in changed_fields if f != "password"], "password_changed": "password" in changed_fields},
            )

        user = _users_queryset().get(id=user.id)
        return envelope_response(serialize_ops_user(user), request)

    @extend_schema(tags=["OPS - Users"], summary="Kullanıcıyı güvenli olarak pasifleştir (soft deactivate)")
    @transaction.atomic
    def delete(self, request: Request, user_id: str):
        user = User.objects.select_for_update().filter(id=user_id).first()
        if user is None:
            raise DomainError("Kullanıcı bulunamadı.", code="USER_NOT_FOUND", status_code=404)
        if user.id == request.user.id:
            raise DomainError("Kendi hesabınızı pasifleştiremezsiniz.", code="SELF_DEACTIVATE_FORBIDDEN", status_code=400)
        if user.is_superuser and not request.user.is_superuser:
            raise DomainError("Süper yönetici hesabı pasifleştirilemez.", code="PRIVILEGE_ESCALATION_DENIED", status_code=403)

        user.is_active = False
        user.save(update_fields=["is_active", "updated_at"])
        OrganizationMembership.objects.filter(user=user, is_active=True).update(is_active=False)
        record_audit(
            action="OPS_USER_DEACTIVATED",
            entity_type="User",
            entity_id=str(user.id),
            actor=request.user,
            metadata={"email": user.email},
        )
        return envelope_response({"id": str(user.id), "isActive": False, "deactivated": True}, request)


class OpsRolesMetadataView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "users:read"

    @extend_schema(tags=["OPS - Users"], summary="Sistemdeki roller ve izin matrisini getir")
    def get(self, request: Request):
        ctx = resolve_tenant_context(request)
        roles = [
            {
                "roleKey": choice_val,
                "label": choice_label,
                "isOps": choice_val in OPS_ROLES,
                "permissions": sorted(ROLE_PERMISSIONS.get(choice_val, frozenset())),
            }
            for choice_val, choice_label in OrganizationMembership.RoleKey.choices
        ]
        return envelope_response(
            {
                "roles": roles,
                "allPermissions": list(ALL_PERMISSIONS),
                "actorRoleKey": ctx.role_key,
            },
            request,
        )
