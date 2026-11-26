from __future__ import annotations

from django.db.models import Count, Sum

from apps.common.responses import GRAM_Q, MONEY_Q, dec_str
from apps.organizations.models import (
    Organization,
    OrganizationAddress,
    OrganizationBankAccount,
    OrganizationDocument,
    OrganizationMembership,
)


def _logo_url(org: Organization, request=None) -> str | None:
    """Return auth-gated API URL — never raw /media/ paths."""
    if not org.logo:
        return None
    path = f"/api/v1/ops/organizations/{org.id}/logo"
    if request is not None:
        return request.build_absolute_uri(path)
    return path


def serialize_address(addr: OrganizationAddress) -> dict:
    return {
        "id": str(addr.id),
        "organizationId": str(addr.organization_id),
        "addressType": addr.address_type,
        "title": addr.title,
        "country": addr.country,
        "city": addr.city,
        "district": addr.district,
        "neighborhood": addr.neighborhood,
        "postalCode": addr.postal_code,
        "line": addr.line,
        "contactName": addr.contact_name,
        "phone": addr.phone,
        "isDefault": addr.is_default,
        "isActive": addr.is_active,
        "createdAt": addr.created_at.isoformat(),
        "updatedAt": addr.updated_at.isoformat(),
    }


def serialize_bank_account(acc: OrganizationBankAccount, *, reveal_iban: bool = True) -> dict:
    iban = acc.iban
    if not reveal_iban and iban:
        iban = f"{iban[:4]}****{iban[-4:]}" if len(iban) > 8 else "****"
    return {
        "id": str(acc.id),
        "organizationId": str(acc.organization_id),
        "bankName": acc.bank_name,
        "iban": iban,
        "currency": acc.currency,
        "accountHolder": acc.account_holder,
        "isDefault": acc.is_default,
        "isActive": acc.is_active,
        "createdAt": acc.created_at.isoformat(),
        "updatedAt": acc.updated_at.isoformat(),
    }


def serialize_document(doc: OrganizationDocument, request=None) -> dict:
    # Auth-gated download endpoint — do not expose FileField.url (/media/...).
    url = None
    if doc.file:
        path = f"/api/v1/ops/organizations/{doc.organization_id}/documents/{doc.id}/file"
        url = request.build_absolute_uri(path) if request is not None else path
    return {
        "id": str(doc.id),
        "organizationId": str(doc.organization_id),
        "name": doc.name,
        "docType": doc.doc_type,
        "fileUrl": url,
        "validUntil": doc.valid_until.isoformat() if doc.valid_until else None,
        "uploadedById": str(doc.uploaded_by_id) if doc.uploaded_by_id else None,
        "uploadedByEmail": doc.uploaded_by.email if doc.uploaded_by_id else None,
        "isActive": doc.is_active,
        "notes": doc.notes,
        "createdAt": doc.created_at.isoformat(),
        "updatedAt": doc.updated_at.isoformat(),
    }


def _partner_roles(org: Organization) -> list[str]:
    roles = org.partner_roles if isinstance(org.partner_roles, list) else []
    cleaned = [str(r).upper() for r in roles if str(r).strip()]
    if cleaned:
        return cleaned
    if org.org_type == Organization.OrgType.PLATFORM_OWNER:
        return ["PLATFORM", "BUYER"]
    if org.org_type == Organization.OrgType.SUPPLIER:
        return ["SUPPLIER"]
    return ["BUYER"]


def serialize_ops_organization(org: Organization, request=None, *, detail: bool = False) -> dict:
    branches = list(org.branches.all())
    active_users = getattr(org, "active_user_count", None)
    if active_users is None and detail:
        active_users = (
            OrganizationMembership.objects.filter(organization=org, is_active=True)
            .values("user_id")
            .distinct()
            .count()
        )
    elif active_users is None:
        active_users = 0
    payload = {
        "id": str(org.id),
        "code": org.code,
        "name": org.name,
        "legalName": org.legal_name or org.name,
        "orgType": org.org_type,
        "partnerRoles": _partner_roles(org),
        "isBuyer": "BUYER" in _partner_roles(org),
        "isSupplier": "SUPPLIER" in _partner_roles(org),
        "approvalStatus": org.approval_status,
        "taxOfficeAndNo": org.tax_office_and_no,
        "taxOffice": org.tax_office,
        "taxNumber": org.tax_number,
        "mersisNo": org.mersis_no,
        "tradeRegistryNo": org.trade_registry_no,
        "companyType": org.company_type,
        "foundedOn": org.founded_on.isoformat() if org.founded_on else None,
        "contactName": org.contact_name,
        "email": org.email,
        "phone": org.phone,
        "fax": org.fax,
        "website": org.website,
        "city": org.city,
        "description": org.description,
        "logoUrl": _logo_url(org, request),
        "defaultConsignmentDays": org.default_consignment_days,
        "paymentTermDays": org.payment_term_days,
        "riskLevel": org.risk_level,
        "riskNote": org.risk_note,
        "creditReviewNote": org.credit_review_note,
        "creditReviewedAt": org.credit_reviewed_at.isoformat() if org.credit_reviewed_at else None,
        "creditReviewedById": str(org.credit_reviewed_by_id) if org.credit_reviewed_by_id else None,
        "commercialNotes": org.commercial_notes,
        "supplierCode": org.supplier_code,
        "supplierLeadTimeDays": org.supplier_lead_time_days,
        "supplierNotes": org.supplier_notes,
        "isActive": org.is_active,
        "creditLimitUsd": dec_str(org.credit_limit_usd, MONEY_Q),
        "usedCreditUsd": dec_str(org.used_credit_usd, MONEY_Q),
        "remainingCreditUsd": dec_str(org.remaining_credit_usd, MONEY_Q),
        "hasLimitGram": dec_str(org.has_limit_gram, GRAM_Q),
        "usedHasGram": dec_str(org.used_has_gram, GRAM_Q),
        "remainingHasGram": dec_str(org.remaining_has_gram, GRAM_Q),
        "branchCount": len(branches),
        "activeUserCount": active_users,
        "branches": [
            {
                "id": str(b.id),
                "code": b.code,
                "name": b.name,
                "city": b.city,
                "address": b.address,
                "isDefault": b.is_default,
                "isActive": b.is_active,
            }
            for b in branches
        ],
        "createdAt": org.created_at.isoformat(),
        "updatedAt": org.updated_at.isoformat(),
    }

    if detail:
        from apps.commerce.models import B2bOrder
        from apps.finance.models import DealerLedgerEntry

        order_agg = B2bOrder.objects.filter(organization=org).aggregate(
            total=Count("id"),
            volume=Sum("total_wholesale_usd"),
        )
        recent_ledger = list(
            DealerLedgerEntry.objects.filter(organization=org)
            .select_related("created_by")
            .order_by("-created_at")[:15]
        )
        memberships = list(
            OrganizationMembership.objects.filter(organization=org)
            .select_related("user", "default_branch")
            .prefetch_related("branches")
            .order_by("-is_active", "role_key")
        )
        addresses = list(org.addresses.order_by("-is_default", "address_type", "title"))
        banks = list(org.bank_accounts.order_by("-is_default", "bank_name"))
        docs = list(org.documents.select_related("uploaded_by").order_by("-created_at")[:50])

        from apps.audit.models import AuditLog

        activities = list(
            AuditLog.objects.filter(organization=org)
            .select_related("actor")
            .order_by("-created_at")[:40]
        )

        payload["overview"] = {
            "totalOrders": order_agg["total"] or 0,
            "totalOrderVolumeUsd": dec_str(order_agg["volume"], MONEY_Q) if order_agg["volume"] is not None else None,
            "cariBalanceUsd": dec_str(org.used_credit_usd, MONEY_Q),
            "creditLimitUsd": dec_str(org.credit_limit_usd, MONEY_Q),
            "availableCreditUsd": dec_str(org.remaining_credit_usd, MONEY_Q),
            "activeUserCount": active_users,
            "branchCount": len(branches),
            "addressCount": len(addresses),
        }
        reveal_iban = False
        if request is not None:
            from apps.organizations.selectors import resolve_tenant_context

            try:
                ctx = resolve_tenant_context(request)
                reveal_iban = "finance:manage" in (ctx.permissions or [])
            except Exception:
                reveal_iban = False

        payload["addresses"] = [serialize_address(a) for a in addresses]
        # Bank IBAN only fully revealed with finance:manage; otherwise masked or omitted.
        if reveal_iban:
            payload["bankAccounts"] = [serialize_bank_account(b, reveal_iban=True) for b in banks]
        else:
            payload["bankAccounts"] = [serialize_bank_account(b, reveal_iban=False) for b in banks]
        payload["documents"] = [serialize_document(d, request) for d in docs]
        payload["memberships"] = [
            {
                "id": str(m.id),
                "userId": str(m.user_id),
                "userEmail": m.user.email,
                "userFullName": m.user.full_name,
                "userPhone": getattr(m.user, "phone", "") or "",
                "roleKey": m.role_key,
                "jobTitle": m.job_title,
                "defaultBranchId": str(m.default_branch_id) if m.default_branch_id else None,
                "branches": [
                    {"id": str(b.id), "code": b.code, "name": b.name} for b in m.branches.all()
                ],
                "isActive": m.is_active,
                "lastLogin": m.user.last_login.isoformat() if m.user.last_login else None,
                "createdAt": m.created_at.isoformat(),
            }
            for m in memberships
        ]
        payload["recentLedger"] = [
            {
                "id": str(e.id),
                "entryType": e.entry_type,
                "referenceNo": e.reference_no,
                "amountUsd": dec_str(e.amount_usd, MONEY_Q),
                "hasGoldGram": dec_str(e.has_gold_gram, GRAM_Q),
                "note": e.note,
                "createdByEmail": e.created_by.email if e.created_by_id else None,
                "createdAt": e.created_at.isoformat(),
            }
            for e in recent_ledger
        ]
        payload["activity"] = [
            {
                "id": str(a.id),
                "action": a.action,
                "entityType": a.entity_type,
                "entityId": a.entity_id,
                "actorEmail": a.actor.email if a.actor_id else None,
                "metadata": a.metadata or {},
                "createdAt": a.created_at.isoformat(),
            }
            for a in activities
        ]

    return payload
