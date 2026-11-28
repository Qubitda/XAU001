import math
import uuid
from decimal import Decimal, ROUND_HALF_UP
from typing import Any, Callable
from django.db.models import QuerySet
from django.utils import timezone
from rest_framework import status as http_status
from rest_framework.request import Request
from rest_framework.response import Response


MONEY_Q = Decimal("0.01")
GRAM_Q = Decimal("0.0001")
CARAT_Q = Decimal("0.001")
RATE_Q = Decimal("0.0001")


def dec_str(value: Decimal | None, q: Decimal = MONEY_Q) -> str | None:
    if value is None:
        return None
    return str(Decimal(value).quantize(q, rounding=ROUND_HALF_UP))


def parse_bool_param(value: str | None) -> bool | None:
    if value is None or value == "":
        return None
    normalized = value.strip().lower()
    if normalized in ("1", "true", "yes", "evet"):
        return True
    if normalized in ("0", "false", "no", "hayir", "hayır"):
        return False
    return None


def apply_safe_ordering(
    qs: QuerySet,
    request: Request,
    *,
    allowed_fields: dict[str, str],
    default: str = "-created_at",
) -> QuerySet:
    """
    Safely applies ?ordering=<field> or ?ordering=-<field> using an explicit whitelist map
    (camelCase or snake_case API key -> ORM field name). Prevents arbitrary ORM field traversal.
    """
    raw = (request.query_params.get("ordering") or "").strip()
    if not raw:
        return qs.order_by(default)
    desc = raw.startswith("-")
    key = raw[1:] if desc else raw
    orm_field = allowed_fields.get(key)
    if not orm_field:
        return qs.order_by(default)
    return qs.order_by(f"-{orm_field}" if desc else orm_field)


def envelope_response(
    data: Any,
    request: Request | None = None,
    status: int = http_status.HTTP_200_OK,
    extra_meta: dict[str, Any] | None = None,
) -> Response:
    org_id = getattr(request, "active_organization_id", None) if request else None
    branch_id = getattr(request, "active_branch_id", None) if request else None
    meta: dict[str, Any] = {
        "requestId": f"req_{uuid.uuid4().hex[:8]}",
        "timestamp": timezone.now().isoformat(),
        "organizationId": str(org_id) if org_id else None,
        "branchId": str(branch_id) if branch_id else None,
    }
    if extra_meta:
        meta.update(extra_meta)
    return Response(
        {
            "data": data,
            "meta": meta,
        },
        status=status,
    )


def paginated_envelope_response(
    qs: QuerySet,
    request: Request,
    serializer_fn: Callable[[Any], dict[str, Any]],
    *,
    default_page_size: int = 25,
    max_page_size: int = 200,
    extra_meta: dict[str, Any] | None = None,
) -> Response:
    """
    Standardized pagination wrapper preserving the Tara Gold {data, meta} envelope.
    Supports ?page=1&page_size=25 (or ?pageSize=25).
    """
    try:
        page = max(1, int(request.query_params.get("page", 1)))
    except (TypeError, ValueError):
        page = 1

    raw_size = request.query_params.get("page_size") or request.query_params.get("pageSize")
    try:
        page_size = int(raw_size) if raw_size is not None else default_page_size
    except (TypeError, ValueError):
        page_size = default_page_size
    page_size = max(1, min(max_page_size, page_size))

    total = qs.count()
    total_pages = max(1, math.ceil(total / page_size)) if total > 0 else 1
    offset = (page - 1) * page_size
    rows = list(qs[offset : offset + page_size])
    items = [serializer_fn(obj) for obj in rows]

    meta_payload: dict[str, Any] = {
        "pagination": {
            "page": page,
            "pageSize": page_size,
            "total": total,
            "totalPages": total_pages,
            "hasNext": page < total_pages,
            "hasPrev": page > 1,
        }
    }
    if extra_meta:
        meta_payload.update(extra_meta)
    return envelope_response(
        items,
        request=request,
        extra_meta=meta_payload,
    )
