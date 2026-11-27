"""B2B dealer ledger read endpoint."""

from __future__ import annotations

from drf_spectacular.utils import extend_schema
from rest_framework.request import Request
from rest_framework.views import APIView

from apps.authorization.permissions import IsB2bOrganizationMember
from apps.common.responses import GRAM_Q, MONEY_Q, dec_str, paginated_envelope_response
from apps.organizations.selectors import resolve_tenant_context
from config.exceptions import DomainError

from .api import serialize_ops_ledger_entry
from .models import DealerLedgerEntry


class B2bLedgerListView(APIView):
    permission_classes = [IsB2bOrganizationMember]

    @extend_schema(tags=["B2B - Finance"], summary="Bayi cari hesap ekstre hareketlerini listele")
    def get(self, request: Request):
        ctx = resolve_tenant_context(request)
        if ctx is None or ctx.organization is None:
            raise DomainError("Aktif bayi organizasyonu bulunamadı.", code="ORG_REQUIRED", status_code=400)
        org = ctx.organization
        qs = (
            DealerLedgerEntry.objects.filter(organization=org)
            .select_related("organization", "created_by")
            .order_by("-created_at")
        )
        entry_type = (request.query_params.get("entryType") or "").strip().upper()
        if entry_type:
            qs = qs.filter(entry_type=entry_type)
        return paginated_envelope_response(
            qs,
            request,
            serialize_ops_ledger_entry,
            extra_meta={
                "summary": {
                    "creditLimitUsd": dec_str(org.credit_limit_usd, MONEY_Q),
                    "usedCreditUsd": dec_str(org.used_credit_usd, MONEY_Q),
                    "hasLimitGram": dec_str(org.has_limit_gram, GRAM_Q),
                    "usedHasGram": dec_str(org.used_has_gram, GRAM_Q),
                }
            },
        )
