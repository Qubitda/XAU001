from rest_framework import status
from rest_framework.response import Response
from config.exceptions import DomainError

from .services import (
    PENDING_STATUS,
    abandon_idempotency_claim,
    build_idempotency_scope,
    claim_idempotency_slot,
    finalize_idempotency_record,
    hash_request_body,
)

IDEMPOTENCY_HEADER = "Idempotency-Key"


class IdempotentCreateMixin:
    """
    Wraps POST/PATCH: optional Idempotency-Key header replays stored envelope for 24h.
    Same key + scope with a different body → 409.
    Claim-before-work prevents double side effects under concurrency.
    """

    idempotent_methods = frozenset({"POST", "PATCH"})

    def dispatch(self, request, *args, **kwargs):
        if request.method not in self.idempotent_methods:
            return super().dispatch(request, *args, **kwargs)

        idem_key = (request.headers.get(IDEMPOTENCY_HEADER) or "").strip()
        if not idem_key:
            return super().dispatch(request, *args, **kwargs)

        scope = self.build_idempotency_scope(request)
        body_hash = hash_request_body(request)
        record, claimed = claim_idempotency_slot(scope=scope, key=idem_key, request_hash=body_hash)

        if not claimed:
            if record.request_hash and record.request_hash != body_hash:
                raise DomainError(
                    "Idempotency-Key bu istek gövdesiyle eşleşmiyor.",
                    code="IDEMPOTENCY_CONFLICT",
                    status_code=status.HTTP_409_CONFLICT,
                )
            if record.response_status == PENDING_STATUS:
                raise DomainError(
                    "Aynı Idempotency-Key ile istek hâlen işleniyor.",
                    code="IDEMPOTENCY_IN_PROGRESS",
                    status_code=status.HTTP_409_CONFLICT,
                )
            return Response(record.response_body, status=record.response_status)

        try:
            response = super().dispatch(request, *args, **kwargs)
        except Exception:
            abandon_idempotency_claim(record=record)
            raise

        if response.status_code >= 500:
            abandon_idempotency_claim(record=record)
            return response

        if hasattr(response, "data") and isinstance(response.data, dict):
            finalize_idempotency_record(
                record=record,
                request_hash=body_hash,
                response_status=response.status_code,
                response_body=response.data,
            )
        else:
            # Non-envelope success — still finalize to block replays with empty body marker.
            finalize_idempotency_record(
                record=record,
                request_hash=body_hash,
                response_status=response.status_code,
                response_body={"status": "ok"},
            )
        return response

    def build_idempotency_scope(self, request):
        return build_idempotency_scope(request)
