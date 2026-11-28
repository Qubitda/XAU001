import hashlib
import json
from datetime import timedelta

from django.db import IntegrityError, transaction
from django.utils import timezone

from .models import IdempotencyRecord

IDEMPOTENCY_TTL = timedelta(hours=24)
# Marker while the first request is still executing the handler.
PENDING_STATUS = 102


def hash_request_body(request) -> str:
    try:
        payload = request.data
    except Exception:
        payload = {}
    normalized = json.dumps(payload, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()


def build_idempotency_scope(request) -> str:
    path = request.path
    api_key = getattr(request, "api_key", None)
    if api_key is not None:
        return f"api_key:{api_key.id}:{path}"

    user = getattr(request, "user", None)
    uid = str(user.pk) if user and getattr(user, "is_authenticated", False) else "anon"
    org_id = getattr(request, "active_organization_id", None)
    org_part = f":org:{org_id}" if org_id else ""
    return f"user:{uid}{org_part}:{path}"


def get_valid_idempotency_record(*, scope: str, key: str) -> IdempotencyRecord | None:
    now = timezone.now()
    return (
        IdempotencyRecord.objects.filter(scope=scope, key=key, expires_at__gt=now)
        .order_by("-created_at")
        .first()
    )


def claim_idempotency_slot(*, scope: str, key: str, request_hash: str) -> tuple[IdempotencyRecord, bool]:
    """
    Atomically claim (scope, key) before running the handler.

    Returns (record, claimed):
      - claimed=True  → this request owns the work; must finalize or abandon
      - claimed=False → another request already holds/completed the key
    """
    expires_at = timezone.now() + IDEMPOTENCY_TTL
    try:
        with transaction.atomic():
            record = IdempotencyRecord.objects.create(
                scope=scope,
                key=key,
                request_hash=request_hash,
                response_status=PENDING_STATUS,
                response_body={"status": "processing"},
                expires_at=expires_at,
            )
        return record, True
    except IntegrityError:
        existing = get_valid_idempotency_record(scope=scope, key=key)
        if existing is None:
            # Expired unique row still blocking — replace it.
            with transaction.atomic():
                IdempotencyRecord.objects.filter(scope=scope, key=key).delete()
                record = IdempotencyRecord.objects.create(
                    scope=scope,
                    key=key,
                    request_hash=request_hash,
                    response_status=PENDING_STATUS,
                    response_body={"status": "processing"},
                    expires_at=expires_at,
                )
            return record, True
        return existing, False


def finalize_idempotency_record(
    *,
    record: IdempotencyRecord,
    request_hash: str,
    response_status: int,
    response_body: dict,
) -> IdempotencyRecord:
    record.request_hash = request_hash
    record.response_status = response_status
    record.response_body = response_body
    record.expires_at = timezone.now() + IDEMPOTENCY_TTL
    record.save(
        update_fields=["request_hash", "response_status", "response_body", "expires_at", "updated_at"]
    )
    return record


def abandon_idempotency_claim(*, record: IdempotencyRecord) -> None:
    """Drop a pending claim so a retry can succeed after a 5xx."""
    if record.response_status == PENDING_STATUS:
        IdempotencyRecord.objects.filter(pk=record.pk, response_status=PENDING_STATUS).delete()
