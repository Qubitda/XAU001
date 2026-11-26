from decimal import Decimal
from django.db import transaction
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.views import APIView
from apps.accounts.models import User
from apps.audit.services import record_audit
from apps.authorization.constants import ALL_PERMISSIONS
from apps.authorization.permissions import HasPortalPermission
from apps.common.responses import (
    apply_safe_ordering,
    envelope_response,
    paginated_envelope_response,
    parse_bool_param,
)
from apps.common.security import sanitize_permissions
from apps.organizations.selectors import resolve_tenant_context
from config.exceptions import DomainError
from .models import Branch, Organization, OrganizationMembership
from .serialize import serialize_ops_organization
from .serializers_partner import OpsOrganizationCreateSerializer, OpsOrganizationUpdateSerializer


def serialize_ops_branch(branch: Branch) -> dict:
    return {
        "id": str(branch.id),
        "organizationId": str(branch.organization_id),
        "organizationCode": branch.organization.code,
        "organizationName": branch.organization.name,
        "code": branch.code,
        "name": branch.name,
        "city": branch.city,
        "address": branch.address,
        "isDefault": branch.is_default,
        "isActive": branch.is_active,
        "createdAt": branch.created_at.isoformat(),
        "updatedAt": branch.updated_at.isoformat(),
    }


def serialize_ops_membership(m: OrganizationMembership) -> dict:
    return {
        "id": str(m.id),
        "userId": str(m.user_id),
        "userEmail": m.user.email,
        "userFullName": m.user.full_name,
        "organizationId": str(m.organization_id) if m.organization_id else None,
        "organizationCode": m.organization.code if m.organization else None,
        "organizationName": m.organization.name if m.organization else "Bireysel Vitrin (B2C)",
        "roleKey": m.role_key,
        "jobTitle": m.job_title,
        "audience": m.audience,
        "defaultBranchId": str(m.default_branch_id) if m.default_branch_id else None,
        "branches": [
            {"id": str(b.id), "code": b.code, "name": b.name, "city": b.city}
            for b in m.branches.all()
        ],
        "customPermissions": sanitize_permissions(m.custom_permissions),
        "isActive": m.is_active,
        "createdAt": m.created_at.isoformat(),
        "updatedAt": m.updated_at.isoformat(),
    }


class OpsBranchCreateSerializer(serializers.Serializer):
    organizationId = serializers.UUIDField()
    code = serializers.CharField(max_length=32)
    name = serializers.CharField(max_length=160)
    city = serializers.CharField(max_length=100)
    address = serializers.CharField(required=False, allow_blank=True, default="")
    isDefault = serializers.BooleanField(default=False)
    isActive = serializers.BooleanField(default=True)


class OpsBranchUpdateSerializer(serializers.Serializer):
    code = serializers.CharField(max_length=32, required=False)
    name = serializers.CharField(max_length=160, required=False)
    city = serializers.CharField(max_length=100, required=False)
    address = serializers.CharField(required=False, allow_blank=True)
    isDefault = serializers.BooleanField(required=False)
    isActive = serializers.BooleanField(required=False)


class OpsMembershipCreateSerializer(serializers.Serializer):
    userId = serializers.UUIDField()
    organizationId = serializers.UUIDField(required=False, allow_null=True)
    roleKey = serializers.ChoiceField(choices=OrganizationMembership.RoleKey.values)
    jobTitle = serializers.CharField(max_length=120, required=False, allow_blank=True, default="")
    branchIds = serializers.ListField(child=serializers.UUIDField(), required=False, default=list)
    defaultBranchId = serializers.UUIDField(required=False, allow_null=True)
    customPermissions = serializers.ListField(child=serializers.ChoiceField(choices=ALL_PERMISSIONS), required=False, default=list)
    isActive = serializers.BooleanField(default=True)


class OpsMembershipUpdateSerializer(serializers.Serializer):
    roleKey = serializers.ChoiceField(choices=OrganizationMembership.RoleKey.values, required=False)
    jobTitle = serializers.CharField(max_length=120, required=False, allow_blank=True)
    branchIds = serializers.ListField(child=serializers.UUIDField(), required=False)
    defaultBranchId = serializers.UUIDField(required=False, allow_null=True)
    customPermissions = serializers.ListField(child=serializers.ChoiceField(choices=ALL_PERMISSIONS), required=False)
    isActive = serializers.BooleanField(required=False)


def _validate_membership_branches(
    *, org: Organization | None, branch_ids: list | None, default_branch_id
) -> tuple[list[Branch], Branch | None]:
    if org is None:
        if branch_ids or default_branch_id:
            raise DomainError(
                "Organizasyonsuz (B2C) üyeliklere şube atanamaz.",
                code="BRANCH_ORG_REQUIRED",
                status_code=400,
            )
        return [], None

    branches: list[Branch] = []
    if branch_ids is not None:
        branches = list(Branch.objects.filter(id__in=branch_ids, organization=org))
        if len(branches) != len(set(branch_ids)):
            raise DomainError(
                "Seçilen şubelerden biri belirtilen organizasyona ait değil veya bulunamadı.",
                code="INVALID_BRANCH_ASSIGNMENT",
                status_code=400,
            )

    default_branch = None
    if default_branch_id is not None:
        default_branch = Branch.objects.filter(id=default_branch_id, organization=org).first()
        if default_branch is None:
            raise DomainError(
                "Varsayılan şube belirtilen organizasyona ait değil veya bulunamadı.",
                code="INVALID_DEFAULT_BRANCH",
                status_code=400,
            )
        if branch_ids is not None and not any(b.id == default_branch.id for b in branches):
            branches.append(default_branch)

    return branches, default_branch


class OpsOrganizationListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "orgs:manage"

    @extend_schema(tags=["OPS - Organizations"], summary="Organizasyon ve bayileri listele")
    def get(self, request: Request):
        from django.db.models import Count

        qs = Organization.objects.prefetch_related("branches").annotate(
            active_user_count=Count(
                "memberships__user_id",
                filter=Q(memberships__is_active=True),
                distinct=True,
            )
        )
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(code__icontains=q)
                | Q(name__icontains=q)
                | Q(legal_name__icontains=q)
                | Q(tax_office_and_no__icontains=q)
                | Q(tax_number__icontains=q)
                | Q(contact_name__icontains=q)
                | Q(city__icontains=q)
            )
        org_type = (request.query_params.get("orgType") or request.query_params.get("org_type") or "").strip()
        if org_type:
            qs = qs.filter(org_type=org_type)
        is_active = parse_bool_param(request.query_params.get("isActive") or request.query_params.get("is_active"))
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        approval = (request.query_params.get("approvalStatus") or "").strip().upper()
        if approval:
            qs = qs.filter(approval_status=approval)
        risk = (request.query_params.get("riskLevel") or "").strip().upper()
        if risk:
            qs = qs.filter(risk_level=risk)
        role = (request.query_params.get("partnerRole") or "").strip().upper()
        if role in ("BUYER", "SUPPLIER", "PLATFORM"):
            qs = qs.filter(partner_roles__contains=[role])
        city = (request.query_params.get("city") or "").strip()
        if city:
            qs = qs.filter(city__icontains=city)

        qs = apply_safe_ordering(
            qs,
            request,
            allowed_fields={
                "code": "code",
                "name": "name",
                "city": "city",
                "creditLimitUsd": "credit_limit_usd",
                "usedCreditUsd": "used_credit_usd",
                "createdAt": "created_at",
            },
            default="name",
        )

        def _ser(org):
            return serialize_ops_organization(org, request)

        return paginated_envelope_response(qs, request, _ser)

    @extend_schema(tags=["OPS - Organizations"], summary="Yeni organizasyon / bayi oluştur", request=OpsOrganizationCreateSerializer)
    @transaction.atomic
    def post(self, request: Request):
        serializer = OpsOrganizationCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data
        code = d["code"].strip().upper()
        if Organization.objects.filter(code__iexact=code).exists():
            raise DomainError(f"Organizasyon kodu zaten mevcut: {code}", code="DUPLICATE_ORG_CODE", status_code=409)

        tax_office = d.get("taxOffice", "").strip()
        tax_number = d.get("taxNumber", "").strip()
        tax_combined = d.get("taxOfficeAndNo", "").strip()
        if not tax_combined and (tax_office or tax_number):
            tax_combined = " / ".join(x for x in (tax_office, tax_number) if x)

        org = Organization.objects.create(
            code=code,
            name=d["name"].strip(),
            legal_name=(d.get("legalName") or d["name"]).strip(),
            org_type=d["orgType"],
            partner_roles=d.get("partnerRoles") or [],
            approval_status=d.get("approvalStatus", Organization.ApprovalStatus.APPROVED),
            tax_office_and_no=tax_combined,
            tax_office=tax_office,
            tax_number=tax_number,
            mersis_no=d.get("mersisNo", "").strip(),
            trade_registry_no=d.get("tradeRegistryNo", "").strip(),
            company_type=d.get("companyType", "").strip(),
            founded_on=d.get("foundedOn"),
            contact_name=d.get("contactName", "").strip(),
            email=d.get("email", "").strip(),
            phone=d.get("phone", "").strip(),
            fax=d.get("fax", "").strip(),
            website=d.get("website", "").strip(),
            city=d.get("city", "").strip(),
            description=d.get("description", "").strip(),
            default_consignment_days=d.get("defaultConsignmentDays", 45),
            payment_term_days=d.get("paymentTermDays", 30),
            risk_level=d.get("riskLevel", Organization.RiskLevel.LOW),
            risk_note=d.get("riskNote", "").strip(),
            commercial_notes=d.get("commercialNotes", "").strip(),
            supplier_code=d.get("supplierCode", "").strip(),
            supplier_lead_time_days=d.get("supplierLeadTimeDays"),
            supplier_notes=d.get("supplierNotes", "").strip(),
            credit_limit_usd=d.get("creditLimitUsd", Decimal("0.00")),
            has_limit_gram=d.get("hasLimitGram", Decimal("0.0000")),
            is_active=d.get("isActive", True),
        )
        record_audit(
            action="OPS_ORGANIZATION_CREATED",
            entity_type="Organization",
            entity_id=str(org.id),
            actor=request.user,
            organization=org,
            metadata={"code": org.code, "org_type": org.org_type, "partner_roles": org.partner_roles},
        )
        org = Organization.objects.prefetch_related("branches").get(id=org.id)
        return envelope_response(serialize_ops_organization(org, request), request, status=201)


class OpsOrganizationDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "orgs:manage"

    @extend_schema(tags=["OPS - Organizations"], summary="Organizasyon detayını getir")
    def get(self, request: Request, org_id: str):
        org = Organization.objects.prefetch_related("branches").filter(id=org_id).first()
        if org is None:
            raise DomainError("Organizasyon bulunamadı.", code="ORG_NOT_FOUND", status_code=404)
        rich = (request.query_params.get("detail") or "").lower() in ("1", "true", "yes")
        return envelope_response(serialize_ops_organization(org, request, detail=rich), request)

    @extend_schema(tags=["OPS - Organizations"], summary="Organizasyon ve limit bilgilerini güncelle", request=OpsOrganizationUpdateSerializer)
    @transaction.atomic
    def patch(self, request: Request, org_id: str):
        org = Organization.objects.select_for_update().filter(id=org_id).first()
        if org is None:
            raise DomainError("Organizasyon bulunamadı.", code="ORG_NOT_FOUND", status_code=404)
        serializer = OpsOrganizationUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        finance_fields = {"creditLimitUsd", "hasLimitGram"}
        if finance_fields & set(d.keys()):
            ctx = resolve_tenant_context(request)
            if "finance:manage" not in (ctx.permissions or []):
                raise DomainError(
                    "Kredi / has limiti değişikliği için finance:manage yetkisi gerekir.",
                    code="FINANCE_PERMISSION_REQUIRED",
                    status_code=403,
                )

        field_map = {
            "name": "name",
            "legalName": "legal_name",
            "orgType": "org_type",
            "partnerRoles": "partner_roles",
            "approvalStatus": "approval_status",
            "taxOfficeAndNo": "tax_office_and_no",
            "taxOffice": "tax_office",
            "taxNumber": "tax_number",
            "mersisNo": "mersis_no",
            "tradeRegistryNo": "trade_registry_no",
            "companyType": "company_type",
            "foundedOn": "founded_on",
            "contactName": "contact_name",
            "email": "email",
            "phone": "phone",
            "fax": "fax",
            "website": "website",
            "city": "city",
            "description": "description",
            "defaultConsignmentDays": "default_consignment_days",
            "paymentTermDays": "payment_term_days",
            "riskLevel": "risk_level",
            "riskNote": "risk_note",
            "creditReviewNote": "credit_review_note",
            "commercialNotes": "commercial_notes",
            "supplierCode": "supplier_code",
            "supplierLeadTimeDays": "supplier_lead_time_days",
            "supplierNotes": "supplier_notes",
            "creditLimitUsd": "credit_limit_usd",
            "hasLimitGram": "has_limit_gram",
            "isActive": "is_active",
        }
        updated: list[str] = []
        for api_key, model_field in field_map.items():
            if api_key in d:
                val = d[api_key].strip() if isinstance(d[api_key], str) else d[api_key]
                setattr(org, model_field, val)
                updated.append(model_field)

        if updated:
            # used_* counters are finance SSOT — never accept from client.
            org.save()
            record_audit(
                action="OPS_ORGANIZATION_UPDATED",
                entity_type="Organization",
                entity_id=str(org.id),
                actor=request.user,
                organization=org,
                metadata={"fields": updated},
            )
        org = Organization.objects.prefetch_related("branches").get(id=org.id)
        return envelope_response(serialize_ops_organization(org, request), request)

    @extend_schema(tags=["OPS - Organizations"], summary="Organizasyonu güvenli olarak pasifleştir")
    @transaction.atomic
    def delete(self, request: Request, org_id: str):
        org = Organization.objects.select_for_update().filter(id=org_id).first()
        if org is None:
            raise DomainError("Organizasyon bulunamadı.", code="ORG_NOT_FOUND", status_code=404)
        org.is_active = False
        org.save(update_fields=["is_active", "updated_at"])
        record_audit(
            action="OPS_ORGANIZATION_DEACTIVATED",
            entity_type="Organization",
            entity_id=str(org.id),
            actor=request.user,
            organization=org,
        )
        return envelope_response({"id": str(org.id), "isActive": False, "deactivated": True}, request)


class OpsBranchListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "orgs:manage"

    @extend_schema(tags=["OPS - Organizations"], summary="Şubeleri listele")
    def get(self, request: Request):
        qs = Branch.objects.select_related("organization")
        org_id = (request.query_params.get("organizationId") or "").strip()
        if org_id:
            qs = qs.filter(organization_id=org_id)
        is_active = parse_bool_param(request.query_params.get("isActive") or request.query_params.get("is_active"))
        if is_active is not None:
            qs = qs.filter(is_active=is_active)
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(code__icontains=q)
                | Q(name__icontains=q)
                | Q(city__icontains=q)
                | Q(organization__name__icontains=q)
            )
        qs = apply_safe_ordering(
            qs,
            request,
            allowed_fields={"code": "code", "name": "name", "city": "city", "createdAt": "created_at"},
            default="-is_default",
        )
        return paginated_envelope_response(qs, request, serialize_ops_branch)

    @extend_schema(tags=["OPS - Organizations"], summary="Yeni şube oluştur", request=OpsBranchCreateSerializer)
    @transaction.atomic
    def post(self, request: Request):
        serializer = OpsBranchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        org = Organization.objects.filter(id=d["organizationId"]).first()
        if org is None:
            raise DomainError("Organizasyon bulunamadı.", code="ORG_NOT_FOUND", status_code=404)

        code = d["code"].strip().upper()
        if Branch.objects.filter(organization=org, code__iexact=code).exists():
            raise DomainError(f"Bu organizasyonda '{code}' şube kodu zaten mevcut.", code="DUPLICATE_BRANCH_CODE", status_code=409)

        if d.get("isDefault"):
            Branch.objects.filter(organization=org, is_default=True).update(is_default=False)

        branch = Branch.objects.create(
            organization=org,
            code=code,
            name=d["name"].strip(),
            city=d["city"].strip(),
            address=d.get("address", "").strip(),
            is_default=d.get("isDefault", False),
            is_active=d.get("isActive", True),
        )
        record_audit(
            action="OPS_BRANCH_CREATED",
            entity_type="Branch",
            entity_id=str(branch.id),
            actor=request.user,
            organization=org,
            metadata={"code": branch.code, "name": branch.name},
        )
        branch = Branch.objects.select_related("organization").get(id=branch.id)
        return envelope_response(serialize_ops_branch(branch), request, status=201)


class OpsBranchDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "orgs:manage"

    @extend_schema(tags=["OPS - Organizations"], summary="Şube detayını getir")
    def get(self, request: Request, branch_id: str):
        branch = Branch.objects.select_related("organization").filter(id=branch_id).first()
        if branch is None:
            raise DomainError("Şube bulunamadı.", code="BRANCH_NOT_FOUND", status_code=404)
        return envelope_response(serialize_ops_branch(branch), request)

    @extend_schema(tags=["OPS - Organizations"], summary="Şube bilgilerini güncelle", request=OpsBranchUpdateSerializer)
    @transaction.atomic
    def patch(self, request: Request, branch_id: str):
        branch = Branch.objects.select_for_update().select_related("organization").filter(id=branch_id).first()
        if branch is None:
            raise DomainError("Şube bulunamadı.", code="BRANCH_NOT_FOUND", status_code=404)
        serializer = OpsBranchUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        if "code" in d:
            new_code = d["code"].strip().upper()
            if Branch.objects.filter(organization=branch.organization, code__iexact=new_code).exclude(id=branch.id).exists():
                raise DomainError(f"Bu organizasyonda '{new_code}' şube kodu zaten mevcut.", code="DUPLICATE_BRANCH_CODE", status_code=409)
            branch.code = new_code
        if "name" in d:
            branch.name = d["name"].strip()
        if "city" in d:
            branch.city = d["city"].strip()
        if "address" in d:
            branch.address = d["address"].strip()
        if "isDefault" in d:
            if d["isDefault"]:
                Branch.objects.filter(organization=branch.organization, is_default=True).exclude(id=branch.id).update(is_default=False)
            branch.is_default = d["isDefault"]
        if "isActive" in d:
            branch.is_active = d["isActive"]

        branch.save()
        record_audit(
            action="OPS_BRANCH_UPDATED",
            entity_type="Branch",
            entity_id=str(branch.id),
            actor=request.user,
            organization=branch.organization,
            metadata={"code": branch.code, "is_active": branch.is_active},
        )
        return envelope_response(serialize_ops_branch(branch), request)

    @extend_schema(tags=["OPS - Organizations"], summary="Şubeyi güvenli olarak pasifleştir")
    @transaction.atomic
    def delete(self, request: Request, branch_id: str):
        branch = Branch.objects.select_for_update().select_related("organization").filter(id=branch_id).first()
        if branch is None:
            raise DomainError("Şube bulunamadı.", code="BRANCH_NOT_FOUND", status_code=404)
        branch.is_active = False
        branch.save(update_fields=["is_active", "updated_at"])
        record_audit(
            action="OPS_BRANCH_DEACTIVATED",
            entity_type="Branch",
            entity_id=str(branch.id),
            actor=request.user,
            organization=branch.organization,
        )
        return envelope_response({"id": str(branch.id), "isActive": False, "deactivated": True}, request)


class OpsMembershipListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "GET": "orgs:manage",
        "POST": "users:manage",
    }

    @extend_schema(tags=["OPS - Organizations"], summary="Organizasyon üyelik ve rol atamalarını listele")
    def get(self, request: Request):
        qs = OrganizationMembership.objects.select_related(
            "user", "organization", "default_branch"
        ).prefetch_related("branches")
        org_id = (request.query_params.get("organizationId") or "").strip()
        if org_id:
            qs = qs.filter(organization_id=org_id)
        user_id = (request.query_params.get("userId") or "").strip()
        if user_id:
            qs = qs.filter(user_id=user_id)
        role_key = (request.query_params.get("roleKey") or request.query_params.get("role_key") or "").strip()
        if role_key:
            qs = qs.filter(role_key=role_key)
        is_active = parse_bool_param(request.query_params.get("isActive") or request.query_params.get("is_active"))
        if is_active is not None:
            qs = qs.filter(is_active=is_active)

        qs = apply_safe_ordering(
            qs,
            request,
            allowed_fields={"createdAt": "created_at", "roleKey": "role_key"},
            default="-created_at",
        )
        return paginated_envelope_response(qs, request, serialize_ops_membership)

    @extend_schema(tags=["OPS - Organizations"], summary="Kullanıcıya rol ve organizasyon/şube üyeliği ata", request=OpsMembershipCreateSerializer)
    @transaction.atomic
    def post(self, request: Request):
        serializer = OpsMembershipCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        ctx = resolve_tenant_context(request)
        if d["roleKey"] == OrganizationMembership.RoleKey.SUPER_ADMIN and not (
            request.user.is_superuser or ctx.role_key == OrganizationMembership.RoleKey.SUPER_ADMIN
        ):
            raise DomainError(
                "Yalnızca SUPER_ADMIN kullanıcılar SUPER_ADMIN rolü atayabilir.",
                code="PRIVILEGE_ESCALATION_DENIED",
                status_code=403,
            )

        user = User.objects.filter(id=d["userId"]).first()
        if user is None:
            raise DomainError("Kullanıcı bulunamadı.", code="USER_NOT_FOUND", status_code=404)

        org = None
        if d.get("organizationId") is not None:
            org = Organization.objects.filter(id=d["organizationId"]).first()
            if org is None:
                raise DomainError("Organizasyon bulunamadı.", code="ORG_NOT_FOUND", status_code=404)
        elif d["roleKey"] != OrganizationMembership.RoleKey.B2C_CUSTOMER:
            raise DomainError(
                "B2C_CUSTOMER dışındaki roller için bir organizasyon seçilmelidir.",
                code="ORG_REQUIRED_FOR_ROLE",
                status_code=400,
            )

        if OrganizationMembership.objects.filter(user=user, organization=org, role_key=d["roleKey"]).exists():
            raise DomainError("Bu kullanıcı için aynı organizasyon ve rol üyeliği zaten mevcut.", code="DUPLICATE_MEMBERSHIP", status_code=409)

        branches, default_branch = _validate_membership_branches(
            org=org,
            branch_ids=d.get("branchIds", []),
            default_branch_id=d.get("defaultBranchId"),
        )

        membership = OrganizationMembership.objects.create(
            user=user,
            organization=org,
            role_key=d["roleKey"],
            job_title=(d.get("jobTitle") or "").strip(),
            default_branch=default_branch,
            custom_permissions=sanitize_permissions(d.get("customPermissions", [])),
            is_active=d.get("isActive", True),
        )
        if branches:
            membership.branches.set(branches)

        record_audit(
            action="OPS_MEMBERSHIP_CREATED",
            entity_type="OrganizationMembership",
            entity_id=str(membership.id),
            actor=request.user,
            organization=org,
            metadata={"user_email": user.email, "role_key": membership.role_key},
        )
        membership = (
            OrganizationMembership.objects.select_related("user", "organization", "default_branch")
            .prefetch_related("branches")
            .get(id=membership.id)
        )
        return envelope_response(serialize_ops_membership(membership), request, status=201)


class OpsMembershipDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "GET": "orgs:manage",
        "PATCH": "users:manage",
        "DELETE": "users:manage",
    }

    @extend_schema(tags=["OPS - Organizations"], summary="Üyelik detayını getir")
    def get(self, request: Request, membership_id: str):
        m = (
            OrganizationMembership.objects.select_related("user", "organization", "default_branch")
            .prefetch_related("branches")
            .filter(id=membership_id)
            .first()
        )
        if m is None:
            raise DomainError("Üyelik kaydı bulunamadı.", code="MEMBERSHIP_NOT_FOUND", status_code=404)
        return envelope_response(serialize_ops_membership(m), request)

    @extend_schema(tags=["OPS - Organizations"], summary="Üyelik rolünü, şubelerini veya izinlerini güncelle", request=OpsMembershipUpdateSerializer)
    @transaction.atomic
    def patch(self, request: Request, membership_id: str):
        m = (
            OrganizationMembership.objects.select_for_update()
            .select_related("user", "organization", "default_branch")
            .filter(id=membership_id)
            .first()
        )
        if m is None:
            raise DomainError("Üyelik kaydı bulunamadı.", code="MEMBERSHIP_NOT_FOUND", status_code=404)

        serializer = OpsMembershipUpdateSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        ctx = resolve_tenant_context(request)
        if (
            d.get("roleKey") == OrganizationMembership.RoleKey.SUPER_ADMIN
            or m.role_key == OrganizationMembership.RoleKey.SUPER_ADMIN
        ) and not (request.user.is_superuser or ctx.role_key == OrganizationMembership.RoleKey.SUPER_ADMIN):
            raise DomainError(
                "SUPER_ADMIN üyelikleri yalnızca SUPER_ADMIN tarafından yönetilebilir.",
                code="PRIVILEGE_ESCALATION_DENIED",
                status_code=403,
            )

        if "roleKey" in d:
            if m.organization is None and d["roleKey"] != OrganizationMembership.RoleKey.B2C_CUSTOMER:
                raise DomainError(
                    "B2C_CUSTOMER dışındaki roller için bir organizasyon bağlantısı gereklidir.",
                    code="ORG_REQUIRED_FOR_ROLE",
                    status_code=400,
                )
            if (
                OrganizationMembership.objects.filter(
                    user=m.user, organization=m.organization, role_key=d["roleKey"]
                )
                .exclude(id=m.id)
                .exists()
            ):
                raise DomainError("Bu kullanıcıda hedef rol zaten tanımlı.", code="DUPLICATE_MEMBERSHIP", status_code=409)
            m.role_key = d["roleKey"]
        if "jobTitle" in d:
            m.job_title = (d.get("jobTitle") or "").strip()
        if "customPermissions" in d:
            m.custom_permissions = sanitize_permissions(d["customPermissions"])
        if "isActive" in d:
            m.is_active = d["isActive"]

        if "branchIds" in d or "defaultBranchId" in d:
            branch_ids = d.get("branchIds")
            if "defaultBranchId" in d:
                target_default_id = d["defaultBranchId"]
            elif branch_ids is not None:
                # Only keep existing default_branch if it remains within the new branchIds set
                target_default_id = m.default_branch_id if m.default_branch_id in set(branch_ids) else None
            else:
                target_default_id = m.default_branch_id

            branches, default_branch = _validate_membership_branches(
                org=m.organization,
                branch_ids=branch_ids,
                default_branch_id=target_default_id,
            )
            if branch_ids is not None:
                m.branches.set(branches)
                if "defaultBranchId" in d:
                    m.default_branch = default_branch
                else:
                    m.default_branch = default_branch or (branches[0] if branches else None)
            elif "defaultBranchId" in d:
                m.default_branch = default_branch
                if default_branch is not None:
                    m.branches.add(default_branch)

        m.save()
        record_audit(
            action="OPS_MEMBERSHIP_UPDATED",
            entity_type="OrganizationMembership",
            entity_id=str(m.id),
            actor=request.user,
            organization=m.organization,
            metadata={"role_key": m.role_key, "is_active": m.is_active},
        )
        m = (
            OrganizationMembership.objects.select_related("user", "organization", "default_branch")
            .prefetch_related("branches")
            .get(id=m.id)
        )
        return envelope_response(serialize_ops_membership(m), request)

    @extend_schema(tags=["OPS - Organizations"], summary="Üyeliği pasifleştir")
    @transaction.atomic
    def delete(self, request: Request, membership_id: str):
        m = OrganizationMembership.objects.select_for_update().select_related("organization").filter(id=membership_id).first()
        if m is None:
            raise DomainError("Üyelik kaydı bulunamadı.", code="MEMBERSHIP_NOT_FOUND", status_code=404)
        ctx = resolve_tenant_context(request)
        if m.role_key == OrganizationMembership.RoleKey.SUPER_ADMIN and not (
            request.user.is_superuser or ctx.role_key == OrganizationMembership.RoleKey.SUPER_ADMIN
        ):
            raise DomainError(
                "SUPER_ADMIN üyelikleri yalnızca SUPER_ADMIN tarafından pasifleştirilebilir.",
                code="PRIVILEGE_ESCALATION_DENIED",
                status_code=403,
            )
        m.is_active = False
        m.save(update_fields=["is_active", "updated_at"])
        record_audit(
            action="OPS_MEMBERSHIP_DEACTIVATED",
            entity_type="OrganizationMembership",
            entity_id=str(m.id),
            actor=request.user,
            organization=m.organization,
        )
        return envelope_response({"id": str(m.id), "isActive": False, "deactivated": True}, request)
