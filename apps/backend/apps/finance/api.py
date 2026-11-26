from decimal import Decimal
from django.db.models import Q
from drf_spectacular.utils import extend_schema
from rest_framework import serializers
from rest_framework.request import Request
from rest_framework.views import APIView
from apps.authorization.permissions import HasPortalPermission
from apps.idempotency.mixins import IdempotentCreateMixin
from apps.common.responses import (
    GRAM_Q,
    MONEY_Q,
    apply_safe_ordering,
    dec_str,
    envelope_response,
    paginated_envelope_response,
)
from config.exceptions import DomainError
from .models import DealerLedgerEntry
from .services import record_dealer_ledger_settlement


def serialize_ops_ledger_entry(entry: DealerLedgerEntry) -> dict:
    return {
        "id": str(entry.id),
        "organizationId": str(entry.organization_id),
        "organizationCode": entry.organization.code,
        "organizationName": entry.organization.name,
        "entryType": entry.entry_type,
        "referenceNo": entry.reference_no,
        "amountUsd": dec_str(entry.amount_usd, MONEY_Q),
        "hasGoldGram": dec_str(entry.has_gold_gram, GRAM_Q),
        "note": entry.note,
        "createdById": str(entry.created_by_id) if entry.created_by_id else None,
        "createdByEmail": entry.created_by.email if entry.created_by else None,
        "createdAt": entry.created_at.isoformat(),
    }


class OpsLedgerCreateSerializer(serializers.Serializer):
    organizationId = serializers.UUIDField()
    entryType = serializers.ChoiceField(
        choices=[
            DealerLedgerEntry.EntryType.PAYMENT_CREDIT,
            DealerLedgerEntry.EntryType.HAS_DELIVERY,
            DealerLedgerEntry.EntryType.ORDER_REVERSAL,
            DealerLedgerEntry.EntryType.REFUND_CREDIT,
        ]
    )
    referenceNo = serializers.CharField(max_length=64)
    amountUsd = serializers.DecimalField(max_digits=14, decimal_places=2, min_value=Decimal("0"), required=False, default=Decimal("0.00"))
    hasGoldGram = serializers.DecimalField(max_digits=12, decimal_places=4, min_value=Decimal("0"), required=False, default=Decimal("0.0000"))
    note = serializers.CharField(max_length=240, required=False, allow_blank=True, default="")


class OpsDealerLedgerListCreateView(IdempotentCreateMixin, APIView):
    """
    Immutable dealer financial ledger API.
    Supports listing/filtering and idempotent credit/has-gold settlement posting via finance.services.
    """

    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "finance:manage"

    @extend_schema(tags=["OPS - Finance"], summary="Bayi cari defter kayıtlarını listele")
    def get(self, request: Request):
        qs = DealerLedgerEntry.objects.select_related("organization", "created_by")
        org_id = (request.query_params.get("organizationId") or "").strip()
        if org_id:
            qs = qs.filter(organization_id=org_id)
        entry_type = (request.query_params.get("entryType") or "").strip().upper()
        if entry_type:
            qs = qs.filter(entry_type=entry_type)
        q = (request.query_params.get("q") or "").strip()
        if q:
            qs = qs.filter(
                Q(reference_no__icontains=q)
                | Q(organization__code__icontains=q)
                | Q(organization__name__icontains=q)
                | Q(note__icontains=q)
            )
        qs = apply_safe_ordering(
            qs,
            request,
            allowed_fields={"createdAt": "created_at", "amountUsd": "amount_usd", "hasGoldGram": "has_gold_gram"},
            default="-created_at",
        )
        return paginated_envelope_response(qs, request, serialize_ops_ledger_entry)

    @extend_schema(tags=["OPS - Finance"], summary="Tahsilat, Has Altın teslimi veya ters kayıt işle (idempotent)", request=OpsLedgerCreateSerializer)
    def post(self, request: Request):
        serializer = OpsLedgerCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        d = serializer.validated_data

        entry, created = record_dealer_ledger_settlement(
            organization_id=d["organizationId"],
            entry_type=d["entryType"],
            reference_no=d["referenceNo"],
            amount_usd=d["amountUsd"],
            has_gold_gram=d["hasGoldGram"],
            note=d.get("note", ""),
            actor=request.user,
        )
        entry = DealerLedgerEntry.objects.select_related("organization", "created_by").get(id=entry.id)
        return envelope_response(serialize_ops_ledger_entry(entry), request, status=201 if created else 200)


class OpsDealerLedgerDetailView(APIView):
    permission_classes = [HasPortalPermission]
    ops_only = True
    required_permission = "finance:manage"

    @extend_schema(tags=["OPS - Finance"], summary="Cari hareket kaydı detayını getir")
    def get(self, request: Request, entry_id: str):
        entry = DealerLedgerEntry.objects.select_related("organization", "created_by").filter(id=entry_id).first()
        if entry is None:
            raise DomainError("Cari hesap hareketi bulunamadı.", code="LEDGER_ENTRY_NOT_FOUND", status_code=404)
        return envelope_response(serialize_ops_ledger_entry(entry), request)
