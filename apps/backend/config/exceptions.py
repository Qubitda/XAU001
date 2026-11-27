import logging
from typing import Any

from django.conf import settings
from django.core.exceptions import ValidationError as DjangoValidationError
from rest_framework import status
from rest_framework.exceptions import APIException, Throttled
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger("taragold.security")


class DomainError(APIException):
    status_code = status.HTTP_400_BAD_REQUEST
    default_code = "DOMAIN_ERROR"
    default_detail = "İş kuralı doğrulaması başarısız oldu."

    def __init__(self, message: str, code: str = "DOMAIN_ERROR", status_code: int = 400):
        self.status_code = status_code
        self.error_code = code
        super().__init__(detail=message, code=code)


def taragold_exception_handler(exc: Exception, context: dict[str, Any]) -> Response | None:
    if isinstance(exc, DomainError):
        return Response(
            {"code": exc.error_code, "message": str(exc.detail)},
            status=exc.status_code,
        )

    if isinstance(exc, DjangoValidationError):
        details = exc.message_dict if hasattr(exc, "message_dict") else {"non_field": exc.messages}
        return Response(
            {
                "code": "VALIDATION_ERROR",
                "message": "Girilen veriler doğrulanamadı.",
                "details": details,
            },
            status=status.HTTP_400_BAD_REQUEST,
        )

    response = exception_handler(exc, context)
    if response is None:
        # Unhandled server errors: never leak internals to clients in production.
        logger.exception("Unhandled API exception", exc_info=exc)
        payload = {
            "code": "INTERNAL_ERROR",
            "message": "Beklenmeyen bir sunucu hatası oluştu.",
        }
        if settings.DEBUG:
            payload["debug"] = str(exc)
        return Response(payload, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    if isinstance(exc, Throttled):
        wait = getattr(exc, "wait", None)
        return Response(
            {
                "code": "RATE_LIMITED",
                "message": "İstek limiti aşıldı. Lütfen kısa süre sonra tekrar deneyin.",
                "retryAfterSeconds": int(wait) if wait is not None else None,
            },
            status=status.HTTP_429_TOO_MANY_REQUESTS,
            headers={"Retry-After": str(int(wait))} if wait is not None else None,
        )

    detail = response.data
    if isinstance(detail, dict) and "detail" in detail:
        message = str(detail["detail"])
        details = None
    elif isinstance(detail, dict):
        message = "İstek doğrulaması başarısız oldu."
        details = {k: [str(v)] if not isinstance(v, list) else [str(i) for i in v] for k, v in detail.items()}
    else:
        message = str(detail)
        details = None

    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        429: "RATE_LIMITED",
    }
    payload: dict[str, Any] = {
        "code": code_map.get(response.status_code, "HTTP_ERROR"),
        "message": message,
    }
    if details:
        payload["details"] = details
    elif details and response.status_code < 500:
        # Validation details are OK to return; strip unexpected nested dumps in prod.
        payload["details"] = details
    response.data = payload
    return response
