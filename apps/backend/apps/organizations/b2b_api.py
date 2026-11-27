"""B2B dealer application, self-service organization profile & user management APIs."""

from __future__ import annotations

import secrets
import uuid

from django.contrib.auth import get_user_model
from django.db import transaction
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.permissions import AllowAny
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.audit.services import record_audit
from apps.authorization.permissions import IsB2bOrganizationMember
from apps.common.responses import envelope_response
from apps.organizations.models import Organization, OrganizationMembership as Membership
from apps.organizations.selectors import resolve_tenant_context
from config.exceptions import DomainError

User = get_user_model()


class B2bApplicationSerializer(serializers.Serializer):
    companyName = serializers.CharField(max_length=200)
    taxOfficeAndNo = serializers.CharField(max_length=120)
    city = serializers.CharField(max_length=100)
    contactName = serializers.CharField(max_length=120)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    email = serializers.EmailField(required=False, allow_blank=True, default="")


class B2bOrganizationPatchSerializer(serializers.Serializer):
    name = serializers.CharField(max_length=200, required=False)
    contactName = serializers.CharField(max_length=120, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True)
    website = serializers.URLField(required=False, allow_blank=True)
    city = serializers.CharField(max_length=100, required=False, allow_blank=True)
    taxOffice = serializers.CharField(max_length=120, required=False, allow_blank=True)
    taxNumber = serializers.CharField(max_length=32, required=False, allow_blank=True)


class B2bOrgUserCreateSerializer(serializers.Serializer):
    email = serializers.EmailField()
    fullName = serializers.CharField(max_length=150)
    phone = serializers.CharField(max_length=32, required=False, allow_blank=True, default="")
    roleKey = serializers.ChoiceField(choices=["ORG_ADMIN", "B2B_BUYER"], default="B2B_BUYER")
    jobTitle = serializers.CharField(max_length=80, required=False, allow_blank=True, default="")
    password = serializers.CharField(min_length=8, max_length=128, required=False, allow_blank=True)


class B2bOrgUserPatchSerializer(serializers.Serializer):
    roleKey = serializers.ChoiceField(choices=["ORG_ADMIN", "B2B_BUYER"], required=False)
    isActive = serializers.BooleanField(required=False)
    jobTitle = serializers.CharField(max_length=80, required=False, allow_blank=True)


def _require_org_admin(request: Request):
    ctx = resolve_tenant_context(request)
    if ctx is None or ctx.organization is None or ctx.membership is None:
        raise DomainError("Aktif bayi organizasyonu bulunamadı.", code="ORG_REQUIRED", status_code=400)
    if ctx.membership.role_key != "ORG_ADMIN":
        raise DomainError("Bu işlem için Firma Yöneticisi (ORG_ADMIN) yetkisi gereklidir.", code="FORBIDDEN", status_code=403)
    return ctx


def _serialize_org_member(m: Membership) -> dict:
    return {
        "id": str(m.id),
        "userId": str(m.user_id),
        "email": m.user.email,
        "fullName": getattr(m.user, "full_name", "") or m.user.email,
        "phone": getattr(m.user, "phone", "") or "",
        "roleKey": m.role_key,
        "jobTitle": m.job_title,
        "isActive": m.is_active,
        "createdAt": m.created_at.isoformat(),
    }


class B2bApplicationCreateView(APIView):
    permission_classes = [AllowAny]
    authentication_classes = []

    @extend_schema(tags=["B2B - Onboarding"], summary="Yeni bayilik başvurusu oluştur")
    @transaction.atomic
    def post(self, request: Request):
        ser = B2bApplicationSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        code = f"APP-{uuid.uuid4().hex[:8].upper()}"
        org = Organization.objects.create(
            code=code,
            name=d["companyName"].strip(),
            org_type=Organization.OrgType.DEALER,
            partner_roles=["BUYER"],
            approval_status=Organization.ApprovalStatus.PENDING,
            is_active=False,
            tax_office_and_no=d["taxOfficeAndNo"].strip(),
            city=d["city"].strip(),
            contact_name=d["contactName"].strip(),
            phone=(d.get("phone") or "").strip(),
            email=(d.get("email") or "").strip().lower(),
        )
        return envelope_response(
            {
                "id": str(org.id),
                "code": org.code,
                "companyName": org.name,
                "approvalStatus": org.approval_status,
            },
            request,
            status=201,
        )


class B2bOrganizationPatchView(APIView):
    permission_classes = [IsB2bOrganizationMember]

    @extend_schema(tags=["B2B - Account"], summary="Aktif bayi firma bilgilerini güncelle")
    @transaction.atomic
    def patch(self, request: Request):
        ctx = _require_org_admin(request)
        org = ctx.organization
        ser = B2bOrganizationPatchSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        field_map = {
            "name": "name",
            "contactName": "contact_name",
            "email": "email",
            "phone": "phone",
            "website": "website",
            "city": "city",
            "taxOffice": "tax_office",
            "taxNumber": "tax_number",
        }
        for api_key, attr in field_map.items():
            if api_key in d:
                val = d[api_key]
                setattr(org, attr, val.strip() if isinstance(val, str) else val)
        org.save()
        record_audit(
            action="B2B_ORGANIZATION_UPDATED",
            entity_type="Organization",
            entity_id=str(org.id),
            actor=request.user,
            organization=org,
            metadata={"fields": list(d.keys())},
            request=request,
        )
        return envelope_response(
            {
                "id": str(org.id),
                "code": org.code,
                "name": org.name,
                "contactName": org.contact_name,
                "email": org.email,
                "phone": org.phone,
                "website": org.website,
                "city": org.city,
                "taxOffice": org.tax_office,
                "taxNumber": org.tax_number,
            },
            request,
        )


class B2bOrganizationUsersView(APIView):
    permission_classes = [IsB2bOrganizationMember]

    @extend_schema(tags=["B2B - Account"], summary="Bayi firması kullanıcılarını listele")
    def get(self, request: Request):
        ctx = resolve_tenant_context(request)
        if ctx is None or ctx.organization is None:
            raise DomainError("Aktif bayi organizasyonu bulunamadı.", code="ORG_REQUIRED", status_code=400)
        members = (
            Membership.objects.filter(organization=ctx.organization)
            .select_related("user")
            .order_by("-created_at")
        )
        return envelope_response([_serialize_org_member(m) for m in members], request)

    @extend_schema(tags=["B2B - Account"], summary="Bayi firmasına yeni kullanıcı ekle")
    @transaction.atomic
    def post(self, request: Request):
        ctx = _require_org_admin(request)
        org = ctx.organization
        ser = B2bOrgUserCreateSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        email = d["email"].strip().lower()
        user = User.objects.filter(email__iexact=email).first()
        if user is None:
            user = User.objects.create_user(
                email=email,
                password=d.get("password") or secrets.token_urlsafe(12),
                full_name=d["fullName"].strip(),
                phone=(d.get("phone") or "").strip(),
                is_active=True,
            )
        existing = Membership.objects.filter(user=user, organization=org).first()
        if existing is not None:
            raise DomainError("Bu kullanıcı zaten firmanıza tanımlı.", code="MEMBERSHIP_EXISTS", status_code=409)
        membership = Membership.objects.create(
            user=user,
            organization=org,
            role_key=d["roleKey"],
            job_title=(d.get("jobTitle") or "").strip(),
            is_active=True,
        )
        return envelope_response(_serialize_org_member(membership), request, status=201)


class B2bOrganizationUserDetailView(APIView):
    permission_classes = [IsB2bOrganizationMember]

    @extend_schema(tags=["B2B - Account"], summary="Bayi firma kullanıcısını güncelle")
    @transaction.atomic
    def patch(self, request: Request, membership_id: str):
        ctx = _require_org_admin(request)
        membership = (
            Membership.objects.select_related("user")
            .filter(id=membership_id, organization=ctx.organization)
            .first()
        )
        if membership is None:
            raise DomainError("Üyelik bulunamadı.", code="NOT_FOUND", status_code=404)
        ser = B2bOrgUserPatchSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        if "roleKey" in d:
            membership.role_key = d["roleKey"]
        if "isActive" in d:
            membership.is_active = d["isActive"]
        if "jobTitle" in d:
            membership.job_title = d["jobTitle"].strip()
        membership.save()
        return envelope_response(_serialize_org_member(membership), request)
