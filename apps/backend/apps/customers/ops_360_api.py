"""OPS Customer 360 read APIs — consents, contracts, audit, dashboard."""

from __future__ import annotations

from django.db.models import Q
from django.utils.dateparse import parse_datetime
from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.audit.api import serialize_ops_audit_log
from apps.audit.models import AuditLog
from apps.authorization.permissions import HasPortalPermission
from apps.commerce.models import CartRecoverySession
from apps.common.responses import envelope_response, paginated_envelope_response
from apps.consent.models import ConsentLog, ConsentPurpose, ConsentStatus
from apps.consent.services import has_active_consent, serialize_consent_log
from apps.contracts.models import ContractAcceptance, LegalDocument
from apps.contracts.services import serialize_contract_acceptance, serialize_legal_document
from apps.customers.api import _get_customer, serialize_ops_customer
from apps.customers.models import Customer


class OpsCustomerConsentsView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "GET": "consents:view",
    }

    @extend_schema(tags=["OPS - Customer 360"], summary="Müşteri izin kayıtları")
    def get(self, request: Request, customer_id: str):
        customer = _get_customer(customer_id)
        qs = ConsentLog.objects.filter(customer=customer).order_by("-created_at")
        items = [serialize_consent_log(x) for x in qs[:200]]
        active = {
            "commercialEmail": has_active_consent(
                customer=customer,
                purpose=ConsentPurpose.COMMERCIAL_EMAIL,
                channel="EMAIL",
            ),
            "kvkkNotice": has_active_consent(
                customer=customer,
                purpose=ConsentPurpose.KVKK_NOTICE,
                channel="WEB",
            ),
        }
        return envelope_response({"items": items, "active": active}, request)


class OpsCustomerContractsView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "contracts:view"

    @extend_schema(tags=["OPS - Customer 360"], summary="Müşteri sözleşme kabulleri")
    def get(self, request: Request, customer_id: str):
        customer = _get_customer(customer_id)
        qs = (
            ContractAcceptance.objects.filter(customer=customer)
            .select_related("order", "document")
            .order_by("-accepted_at")[:200]
        )
        return envelope_response([serialize_contract_acceptance(x) for x in qs], request)


class OpsCustomerAuditView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "audit:read"

    @extend_schema(tags=["OPS - Customer 360"], summary="Müşteri denetim kayıtları")
    def get(self, request: Request, customer_id: str):
        customer = _get_customer(customer_id)
        cid = str(customer.id)
        qs = (
            AuditLog.objects.select_related("actor", "organization")
            .filter(
                Q(entity_type="Customer", entity_id=cid)
                | Q(entity_type__in=["ConsentLog", "ContractAcceptance", "CustomerAddress"])
            )
            .order_by("-created_at")
        )
        # Narrow consent/contract rows to this customer via metadata when present
        matched_ids = []
        for log in qs[:300]:
            if log.entity_type == "Customer" and log.entity_id == cid:
                matched_ids.append(log.id)
                continue
            meta = log.metadata if isinstance(log.metadata, dict) else {}
            if meta.get("customer_id") == cid:
                matched_ids.append(log.id)
        qs = AuditLog.objects.select_related("actor", "organization").filter(id__in=matched_ids).order_by(
            "-created_at"
        )
        return paginated_envelope_response(qs, request, serialize_ops_audit_log)


class OpsCustomer360DetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "customers:manage"

    @extend_schema(tags=["OPS - Customer 360"], summary="Customer 360 özet")
    def get(self, request: Request, customer_id: str):
        customer = _get_customer(customer_id)
        base = serialize_ops_customer(customer, detail=True)
        base["segment"] = customer.segment
        base["externalId"] = customer.external_id
        base["emailVerified"] = customer.email_verified
        base["consents"] = {
            "commercialEmail": has_active_consent(
                customer=customer,
                purpose=ConsentPurpose.COMMERCIAL_EMAIL,
                channel="EMAIL",
            ),
        }
        base["contractAcceptanceCount"] = ContractAcceptance.objects.filter(
            customer=customer
        ).count()
        base["consentLogCount"] = ConsentLog.objects.filter(customer=customer).count()
        return envelope_response(base, request)


class OpsLegalDocumentListCreateView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permissions_by_method = {
        "GET": "contracts:view",
        "POST": "legal_docs:manage",
    }

    @extend_schema(tags=["OPS - Legal CMS"], summary="Yasal belge listesi")
    def get(self, request: Request):
        qs = LegalDocument.objects.all().order_by("code", "-version")
        code = (request.query_params.get("code") or "").strip()
        if code:
            qs = qs.filter(code=code)
        published = request.query_params.get("isPublished")
        if published in ("1", "true", "True"):
            qs = qs.filter(is_published=True)
        return envelope_response(
            [serialize_legal_document(d, include_body=False) for d in qs[:200]],
            request,
        )

    @extend_schema(tags=["OPS - Legal CMS"], summary="Yasal belge oluştur")
    def post(self, request: Request):
        from rest_framework import serializers
        from django.utils.dateparse import parse_datetime as _parse

        class Ser(serializers.Serializer):
            code = serializers.ChoiceField(choices=LegalDocument.Code.values)
            version = serializers.CharField(max_length=32)
            title = serializers.CharField(max_length=200)
            bodyHtml = serializers.CharField(required=False, allow_blank=True, default="")
            bodyMd = serializers.CharField(required=False, allow_blank=True, default="")
            isPublished = serializers.BooleanField(required=False, default=False)
            audience = serializers.ChoiceField(
                choices=LegalDocument.Audience.values, required=False, default="ALL"
            )
            effectiveFrom = serializers.CharField(required=False, allow_blank=True, allow_null=True)

        ser = Ser(data=request.data)
        ser.is_valid(raise_exception=True)
        d = ser.validated_data
        doc = LegalDocument.objects.create(
            code=d["code"],
            version=d["version"],
            title=d["title"],
            body_html=d.get("bodyHtml") or "",
            body_md=d.get("bodyMd") or "",
            is_published=d.get("isPublished", False),
            audience=d.get("audience") or LegalDocument.Audience.ALL,
            effective_from=_parse(d["effectiveFrom"]) if d.get("effectiveFrom") else None,
        )
        return envelope_response(serialize_legal_document(doc), request, status=201)


class OpsCustomer360DashboardView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "customers:manage"

    @extend_schema(tags=["OPS - Customer 360"], summary="Customer 360 dashboard KPI")
    def get(self, request: Request):
        date_from = parse_datetime((request.query_params.get("from") or "").strip() or "")
        date_to = parse_datetime((request.query_params.get("to") or "").strip() or "")
        segment = (request.query_params.get("segment") or "").strip()

        customers = Customer.objects.filter(is_active=True)
        if segment:
            customers = customers.filter(segment=segment)
        if date_from:
            customers = customers.filter(created_at__gte=date_from)
        if date_to:
            customers = customers.filter(created_at__lte=date_to)

        total_b2c = customers.filter(segment=Customer.Segment.B2C).count()

        from apps.commerce.models import B2cCart

        recovery = CartRecoverySession.objects.filter(segment=CartRecoverySession.Segment.B2C)
        carts = B2cCart.objects.all()
        active_carts = carts.filter(status=B2cCart.Status.ACTIVE).count()
        abandoned = carts.filter(status=B2cCart.Status.ABANDONED).count()
        converted = carts.filter(status=B2cCart.Status.CONVERTED).count()
        recovered = recovery.filter(status=CartRecoverySession.Status.COMPLETED).count()

        # Customers with latest commercial email GRANTED
        commercial_granted = 0
        commercial_withdrawn = 0
        for cid in Customer.objects.filter(segment=Customer.Segment.B2C, is_active=True).values_list(
            "id", flat=True
        )[:5000]:
            c = Customer(id=cid)
            if has_active_consent(
                customer=c, purpose=ConsentPurpose.COMMERCIAL_EMAIL, channel="EMAIL"
            ):
                commercial_granted += 1
            else:
                latest = (
                    ConsentLog.objects.filter(
                        customer_id=cid,
                        purpose=ConsentPurpose.COMMERCIAL_EMAIL,
                        channel="EMAIL",
                    )
                    .order_by("-created_at")
                    .first()
                )
                if latest and latest.status == ConsentStatus.WITHDRAWN:
                    commercial_withdrawn += 1

        from apps.commerce.models import OpsSalesTask

        pending_comms = OpsSalesTask.objects.filter(status=OpsSalesTask.Status.OPEN).count()

        return envelope_response(
            {
                "totalB2cCustomers": total_b2c,
                "activeCartSessions": active_carts,
                "abandonedCartSessions": abandoned,
                "convertedCartSessions": converted,
                "recoveredCartSessions": recovered,
                "activeRecoverySessions": recovery.filter(
                    status=CartRecoverySession.Status.ACTIVE
                ).count(),
                "commercialEmailGranted": commercial_granted,
                "commercialEmailWithdrawn": commercial_withdrawn,
                "pendingCommunicationTasks": pending_comms,
            },
            request,
        )
