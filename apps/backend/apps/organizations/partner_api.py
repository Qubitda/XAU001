"""Nested Business Partner resources: addresses, bank accounts, documents, logo."""

from __future__ import annotations

import mimetypes

from django.db import transaction
from django.http import FileResponse, Http404
from django.utils import timezone
from drf_spectacular.utils import extend_schema
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.audit.services import record_audit
from apps.authorization.permissions import HasPortalPermission
from apps.common.responses import envelope_response
from config.exceptions import DomainError

from .models import Organization, OrganizationAddress, OrganizationBankAccount, OrganizationDocument
from .serialize import serialize_address, serialize_bank_account, serialize_document, serialize_ops_organization
from .serializers_partner import (
    AddressPatchSerializer,
    AddressWriteSerializer,
    BankAccountPatchSerializer,
    BankAccountWriteSerializer,
    DocumentWriteSerializer,
)


def _get_org(org_id: str) -> Organization:
    org = Organization.objects.filter(id=org_id).first()
    if org is None:
        raise DomainError("Organizasyon bulunamadı.", code="ORG_NOT_FOUND", status_code=404)
    return org


class OpsOrganizationDetailRichView(APIView):
    """GET rich partner dossier (overview + nested collections)."""

    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "orgs:manage"

    @extend_schema(tags=["OPS - Organizations"], summary="İş ortağı detay dosyası")
    def get(self, request: Request, org_id: str):
        org = (
            Organization.objects.prefetch_related("branches", "addresses", "bank_accounts", "documents")
            .filter(id=org_id)
            .first()
        )
        if org is None:
            raise DomainError("Organizasyon bulunamadı.", code="ORG_NOT_FOUND", status_code=404)
        return envelope_response(serialize_ops_organization(org, request, detail=True), request)


class OpsOrganizationLogoView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "orgs:manage"
    parser_classes = [MultiPartParser, FormParser]

    @extend_schema(tags=["OPS - Organizations"], summary="Firma logosunu indir (auth)")
    def get(self, request: Request, org_id: str):
        org = _get_org(org_id)
        if not org.logo:
            raise DomainError("Logo yok.", code="LOGO_NOT_FOUND", status_code=404)
        try:
            fh = org.logo.open("rb")
        except FileNotFoundError as exc:
            raise Http404("Logo dosyası bulunamadı.") from exc
        content_type = mimetypes.guess_type(org.logo.name)[0] or "application/octet-stream"
        return FileResponse(fh, as_attachment=False, filename=org.logo.name.split("/")[-1], content_type=content_type)

    @extend_schema(tags=["OPS - Organizations"], summary="Firma logosu yükle")
    @transaction.atomic
    def post(self, request: Request, org_id: str):
        org = Organization.objects.select_for_update().filter(id=org_id).first()
        if org is None:
            raise DomainError("Organizasyon bulunamadı.", code="ORG_NOT_FOUND", status_code=404)
        file = request.FILES.get("logo") or request.FILES.get("file")
        if file is None:
            raise DomainError("Logo dosyası gerekli.", code="LOGO_REQUIRED", status_code=400)
        if file.size > 2 * 1024 * 1024:
            raise DomainError("Logo en fazla 2 MB olabilir.", code="LOGO_TOO_LARGE", status_code=400)
        org.logo = file
        org.save(update_fields=["logo", "updated_at"])
        record_audit(
            action="OPS_ORGANIZATION_LOGO_UPDATED",
            entity_type="Organization",
            entity_id=str(org.id),
            actor=request.user,
            organization=org,
        )
        return envelope_response(serialize_ops_organization(org, request), request)


class OpsOrganizationAddressListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "orgs:manage"

    @extend_schema(tags=["OPS - Organizations"], summary="Firma adreslerini listele")
    def get(self, request: Request, org_id: str):
        org = _get_org(org_id)
        items = [serialize_address(a) for a in org.addresses.all()]
        return envelope_response(items, request)

    @extend_schema(tags=["OPS - Organizations"], summary="Firma adresi ekle")
    @transaction.atomic
    def post(self, request: Request, org_id: str):
        org = _get_org(org_id)
        ser = AddressWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        if d.get("isDefault"):
            OrganizationAddress.objects.filter(organization=org, is_default=True).update(is_default=False)
        addr = OrganizationAddress.objects.create(
            organization=org,
            address_type=d["addressType"],
            title=d["title"].strip(),
            country=d.get("country", "Türkiye").strip(),
            city=d.get("city", "").strip(),
            district=d.get("district", "").strip(),
            neighborhood=d.get("neighborhood", "").strip(),
            postal_code=d.get("postalCode", "").strip(),
            line=d["line"].strip(),
            contact_name=d.get("contactName", "").strip(),
            phone=d.get("phone", "").strip(),
            is_default=d.get("isDefault", False),
            is_active=d.get("isActive", True),
        )
        record_audit(
            action="OPS_ORGANIZATION_ADDRESS_CREATED",
            entity_type="OrganizationAddress",
            entity_id=str(addr.id),
            actor=request.user,
            organization=org,
            metadata={"title": addr.title, "type": addr.address_type},
        )
        return envelope_response(serialize_address(addr), request, status=201)


class OpsOrganizationAddressDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "orgs:manage"

    @extend_schema(tags=["OPS - Organizations"], summary="Firma adresini güncelle")
    @transaction.atomic
    def patch(self, request: Request, org_id: str, address_id: str):
        org = _get_org(org_id)
        addr = OrganizationAddress.objects.select_for_update().filter(id=address_id, organization=org).first()
        if addr is None:
            raise DomainError("Adres bulunamadı.", code="ADDRESS_NOT_FOUND", status_code=404)
        ser = AddressPatchSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        mapping = {
            "addressType": "address_type",
            "title": "title",
            "country": "country",
            "city": "city",
            "district": "district",
            "neighborhood": "neighborhood",
            "postalCode": "postal_code",
            "line": "line",
            "contactName": "contact_name",
            "phone": "phone",
            "isDefault": "is_default",
            "isActive": "is_active",
        }
        updated = []
        for api_key, field in mapping.items():
            if api_key in d:
                val = d[api_key].strip() if isinstance(d[api_key], str) else d[api_key]
                setattr(addr, field, val)
                updated.append(field)
        if d.get("isDefault"):
            OrganizationAddress.objects.filter(organization=org, is_default=True).exclude(id=addr.id).update(
                is_default=False
            )
        if updated:
            addr.save(update_fields=[*updated, "updated_at"])
            record_audit(
                action="OPS_ORGANIZATION_ADDRESS_UPDATED",
                entity_type="OrganizationAddress",
                entity_id=str(addr.id),
                actor=request.user,
                organization=org,
                metadata={"fields": updated},
            )
        return envelope_response(serialize_address(addr), request)

    @extend_schema(tags=["OPS - Organizations"], summary="Firma adresini pasifleştir")
    @transaction.atomic
    def delete(self, request: Request, org_id: str, address_id: str):
        org = _get_org(org_id)
        addr = OrganizationAddress.objects.select_for_update().filter(id=address_id, organization=org).first()
        if addr is None:
            raise DomainError("Adres bulunamadı.", code="ADDRESS_NOT_FOUND", status_code=404)
        addr.is_active = False
        addr.save(update_fields=["is_active", "updated_at"])
        record_audit(
            action="OPS_ORGANIZATION_ADDRESS_DEACTIVATED",
            entity_type="OrganizationAddress",
            entity_id=str(addr.id),
            actor=request.user,
            organization=org,
        )
        return envelope_response(serialize_address(addr), request)


class OpsOrganizationBankListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "GET": "finance:manage",
        "POST": "finance:manage",
    }

    @extend_schema(tags=["OPS - Organizations"], summary="Firma banka hesaplarını listele")
    def get(self, request: Request, org_id: str):
        org = _get_org(org_id)
        items = [serialize_bank_account(a) for a in org.bank_accounts.all()]
        return envelope_response(items, request)

    @extend_schema(tags=["OPS - Organizations"], summary="Firma banka hesabı ekle")
    @transaction.atomic
    def post(self, request: Request, org_id: str):
        org = _get_org(org_id)
        ser = BankAccountWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        iban = d["iban"].strip().replace(" ", "").upper()
        if d.get("isDefault"):
            OrganizationBankAccount.objects.filter(organization=org, is_default=True).update(is_default=False)
        acc = OrganizationBankAccount.objects.create(
            organization=org,
            bank_name=d["bankName"].strip(),
            iban=iban,
            currency=(d.get("currency") or "TRY").strip().upper(),
            account_holder=d.get("accountHolder", "").strip(),
            is_default=d.get("isDefault", False),
            is_active=d.get("isActive", True),
        )
        record_audit(
            action="OPS_ORGANIZATION_BANK_CREATED",
            entity_type="OrganizationBankAccount",
            entity_id=str(acc.id),
            actor=request.user,
            organization=org,
            metadata={"bank": acc.bank_name},
        )
        return envelope_response(serialize_bank_account(acc), request, status=201)


class OpsOrganizationBankDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "finance:manage"

    @extend_schema(tags=["OPS - Organizations"], summary="Banka hesabını güncelle")
    @transaction.atomic
    def patch(self, request: Request, org_id: str, account_id: str):
        org = _get_org(org_id)
        acc = OrganizationBankAccount.objects.select_for_update().filter(id=account_id, organization=org).first()
        if acc is None:
            raise DomainError("Banka hesabı bulunamadı.", code="BANK_NOT_FOUND", status_code=404)
        ser = BankAccountPatchSerializer(data=request.data, partial=True)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        if "bankName" in d:
            acc.bank_name = d["bankName"].strip()
        if "iban" in d:
            acc.iban = d["iban"].strip().replace(" ", "").upper()
        if "currency" in d:
            acc.currency = d["currency"].strip().upper()
        if "accountHolder" in d:
            acc.account_holder = d["accountHolder"].strip()
        if "isDefault" in d:
            acc.is_default = d["isDefault"]
            if d["isDefault"]:
                OrganizationBankAccount.objects.filter(organization=org, is_default=True).exclude(id=acc.id).update(
                    is_default=False
                )
        if "isActive" in d:
            acc.is_active = d["isActive"]
        acc.save()
        record_audit(
            action="OPS_ORGANIZATION_BANK_UPDATED",
            entity_type="OrganizationBankAccount",
            entity_id=str(acc.id),
            actor=request.user,
            organization=org,
        )
        return envelope_response(serialize_bank_account(acc), request)

    @extend_schema(tags=["OPS - Organizations"], summary="Banka hesabını pasifleştir")
    @transaction.atomic
    def delete(self, request: Request, org_id: str, account_id: str):
        org = _get_org(org_id)
        acc = OrganizationBankAccount.objects.select_for_update().filter(id=account_id, organization=org).first()
        if acc is None:
            raise DomainError("Banka hesabı bulunamadı.", code="BANK_NOT_FOUND", status_code=404)
        acc.is_active = False
        acc.save(update_fields=["is_active", "updated_at"])
        return envelope_response(serialize_bank_account(acc), request)


class OpsOrganizationDocumentListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "orgs:manage"
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    @extend_schema(tags=["OPS - Organizations"], summary="Firma belgelerini listele")
    def get(self, request: Request, org_id: str):
        org = _get_org(org_id)
        items = [serialize_document(d, request) for d in org.documents.select_related("uploaded_by").all()]
        return envelope_response(items, request)

    @extend_schema(tags=["OPS - Organizations"], summary="Firma belgesi yükle")
    @transaction.atomic
    def post(self, request: Request, org_id: str):
        org = _get_org(org_id)
        ser = DocumentWriteSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        file = request.FILES.get("file") or request.FILES.get("document")
        if file is None:
            raise DomainError("Belge dosyası gerekli.", code="DOCUMENT_FILE_REQUIRED", status_code=400)
        from apps.common.uploads import validate_uploaded_document

        validate_uploaded_document(file)
        doc = OrganizationDocument.objects.create(
            organization=org,
            name=d["name"].strip(),
            doc_type=d.get("docType", OrganizationDocument.DocType.OTHER),
            file=file,
            valid_until=d.get("validUntil"),
            uploaded_by=request.user,
            notes=d.get("notes", "").strip(),
        )
        record_audit(
            action="OPS_ORGANIZATION_DOCUMENT_UPLOADED",
            entity_type="OrganizationDocument",
            entity_id=str(doc.id),
            actor=request.user,
            organization=org,
            metadata={"name": doc.name, "doc_type": doc.doc_type},
        )
        return envelope_response(serialize_document(doc, request), request, status=201)


class OpsOrganizationDocumentDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "orgs:manage"

    @extend_schema(tags=["OPS - Organizations"], summary="Belgeyi pasifleştir")
    @transaction.atomic
    def delete(self, request: Request, org_id: str, document_id: str):
        org = _get_org(org_id)
        doc = OrganizationDocument.objects.select_for_update().filter(id=document_id, organization=org).first()
        if doc is None:
            raise DomainError("Belge bulunamadı.", code="DOCUMENT_NOT_FOUND", status_code=404)
        doc.is_active = False
        doc.save(update_fields=["is_active", "updated_at"])
        return envelope_response(serialize_document(doc, request), request)


class OpsOrganizationDocumentFileView(APIView):
    """Authenticated download — never expose raw /media/ URLs for partner documents."""

    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "orgs:manage"

    @extend_schema(tags=["OPS - Organizations"], summary="Firma belgesini indir (auth)")
    def get(self, request: Request, org_id: str, document_id: str):
        org = _get_org(org_id)
        doc = OrganizationDocument.objects.filter(id=document_id, organization=org, is_active=True).first()
        if doc is None or not doc.file:
            raise DomainError("Belge bulunamadı.", code="DOCUMENT_NOT_FOUND", status_code=404)
        try:
            fh = doc.file.open("rb")
        except FileNotFoundError as exc:
            raise Http404("Belge dosyası bulunamadı.") from exc
        content_type = mimetypes.guess_type(doc.file.name)[0] or "application/octet-stream"
        filename = doc.file.name.split("/")[-1]
        return FileResponse(fh, as_attachment=True, filename=filename, content_type=content_type)


class OpsOrganizationCreditReviewView(APIView):
    """Manual risk/credit review note — does not invent scores; uses Organization SSOT limits."""

    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "finance:manage"

    @extend_schema(tags=["OPS - Organizations"], summary="Kredibilite değerlendirmesi kaydet")
    @transaction.atomic
    def post(self, request: Request, org_id: str):
        org = Organization.objects.select_for_update().filter(id=org_id).first()
        if org is None:
            raise DomainError("Organizasyon bulunamadı.", code="ORG_NOT_FOUND", status_code=404)
        risk = (request.data.get("riskLevel") or "").strip().upper()
        if risk and risk not in Organization.RiskLevel.values:
            raise DomainError("Geçersiz risk seviyesi.", code="INVALID_RISK_LEVEL", status_code=400)
        if risk:
            org.risk_level = risk
        if "riskNote" in request.data:
            org.risk_note = str(request.data.get("riskNote") or "").strip()
        if "creditReviewNote" in request.data:
            org.credit_review_note = str(request.data.get("creditReviewNote") or "").strip()
        if "paymentTermDays" in request.data:
            try:
                org.payment_term_days = max(0, min(365, int(request.data.get("paymentTermDays"))))
            except (TypeError, ValueError):
                raise DomainError("Ödeme vadesi geçersiz.", code="INVALID_PAYMENT_TERM", status_code=400)
        org.credit_reviewed_at = timezone.now()
        org.credit_reviewed_by = request.user
        org.save(
            update_fields=[
                "risk_level",
                "risk_note",
                "credit_review_note",
                "payment_term_days",
                "credit_reviewed_at",
                "credit_reviewed_by",
                "updated_at",
            ]
        )
        record_audit(
            action="OPS_ORGANIZATION_CREDIT_REVIEWED",
            entity_type="Organization",
            entity_id=str(org.id),
            actor=request.user,
            organization=org,
            metadata={"risk_level": org.risk_level, "payment_term_days": org.payment_term_days},
        )
        return envelope_response(serialize_ops_organization(org, request, detail=True), request)
