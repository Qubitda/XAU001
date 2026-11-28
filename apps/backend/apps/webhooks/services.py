import hashlib
import hmac
import http.client
import json
import logging
import socket
import ssl
from urllib import error as urlerror
from urllib import request as urlrequest

from django.utils import timezone

from .models import PLATFORM_WEBHOOK_EVENTS, WEBHOOK_EVENTS, WebhookEndpoint
from .url_safety import resolve_and_validate_webhook_url

logger = logging.getLogger(__name__)


class _NoRedirect(urlrequest.HTTPRedirectHandler):
    """Refuse redirects — prevents SSRF pivot after DNS/allowlist checks."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):  # noqa: ANN001
        raise urlerror.HTTPError(req.full_url, code, f"Redirect blocked ({code})", headers, fp)


def _build_pinned_opener(pinned_ip: str, original_host: str, port: int):
    """Build a urllib opener whose TCP socket connects strictly to `pinned_ip` (anti-DNS-rebinding)."""

    class _PinnedHTTPConnection(http.client.HTTPConnection):
        def connect(self):
            self.sock = socket.create_connection((pinned_ip, port), self.timeout, self.source_address)

    class _PinnedHTTPSConnection(http.client.HTTPSConnection):
        def connect(self):
            raw_sock = socket.create_connection((pinned_ip, port), self.timeout, self.source_address)
            ctx = self._context if hasattr(self, "_context") else ssl.create_default_context()
            self.sock = ctx.wrap_socket(raw_sock, server_hostname=original_host)

    class _PinnedHTTPHandler(urlrequest.HTTPHandler):
        def http_open(self, req):
            return self.do_open(_PinnedHTTPConnection, req)

    class _PinnedHTTPSHandler(urlrequest.HTTPSHandler):
        def https_open(self, req):
            return self.do_open(_PinnedHTTPSConnection, req, context=self._context)

    return urlrequest.build_opener(_NoRedirect, _PinnedHTTPHandler(), _PinnedHTTPSHandler())


_OPENER = urlrequest.build_opener(_NoRedirect)


def sign_webhook_body(secret: str, body: bytes) -> str:
    digest = hmac.new(secret.encode("utf-8"), body, hashlib.sha256).hexdigest()
    return f"sha256={digest}"


def _build_delivery_payload(event: str, data: dict) -> dict:
    return {
        "event": event,
        "data": data,
        "createdAt": timezone.now().isoformat(),
    }


def deliver_webhook_to_endpoint(*, endpoint: WebhookEndpoint, event: str, data: dict) -> None:
    # Re-validate at delivery time and pin resolved IP to eliminate DNS-rebinding TOCTOU.
    try:
        validated_url, pinned_ip, host, port = resolve_and_validate_webhook_url(endpoint.url)
    except Exception as exc:
        logger.warning("Webhook %s URL rejected at delivery: %s", endpoint.id, exc)
        return

    payload = _build_delivery_payload(event, data)
    body = json.dumps(payload, separators=(",", ":"), default=str).encode("utf-8")
    signature = sign_webhook_body(endpoint.secret, body)
    req = urlrequest.Request(
        validated_url,
        data=body,
        headers={
            "Content-Type": "application/json",
            "Host": host,
            "X-Tara-Signature": signature,
            "User-Agent": "TaraGold-Webhooks/1.0",
        },
        method="POST",
    )
    opener = _build_pinned_opener(pinned_ip, host, port)
    try:
        with opener.open(req, timeout=15) as resp:
            if resp.status >= 400:
                logger.warning(
                    "Webhook %s returned HTTP %s for event %s",
                    endpoint.id,
                    resp.status,
                    event,
                )
    except urlerror.HTTPError as exc:
        logger.warning("Webhook delivery HTTP error for %s: %s", endpoint.id, exc)
    except urlerror.URLError as exc:
        logger.warning("Webhook delivery failed for %s: %s", endpoint.id, exc)


def deliver_webhook(endpoint_id: str, event: str, data: dict) -> None:
    endpoint = (
        WebhookEndpoint.objects.filter(id=endpoint_id, is_active=True)
        .select_related("organization")
        .first()
    )
    if endpoint is None:
        return
    if event not in (endpoint.events or []):
        return
    deliver_webhook_to_endpoint(endpoint=endpoint, event=event, data=data)


def schedule_webhook_delivery(endpoint_id: str, event: str, data: dict) -> None:
    """Enqueue Celery delivery. Never block the request path with sync HTTP."""
    try:
        from .tasks import deliver_webhook_task

        deliver_webhook_task.delay(endpoint_id, event, data)
    except Exception:
        logger.exception(
            "Failed to enqueue webhook delivery for endpoint=%s event=%s (no sync fallback)",
            endpoint_id,
            event,
        )


def emit_webhook_event(
    event: str,
    data: dict,
    *,
    organization_id=None,
    platform: bool = False,
) -> None:
    """
    Fan-in to matching endpoints only.

    - platform=True or B2C events without org → only is_platform endpoints
    - organization_id set → only that organization's non-platform endpoints
    - otherwise → refuse (never broadcast to every dealer)
    """
    if event not in WEBHOOK_EVENTS:
        return

    is_platform_event = platform or event in PLATFORM_WEBHOOK_EVENTS
    qs = WebhookEndpoint.objects.filter(is_active=True)

    if is_platform_event:
        if organization_id is not None:
            logger.warning(
                "Ignoring organization_id=%s for platform event %s",
                organization_id,
                event,
            )
        qs = qs.filter(is_platform=True)
    elif organization_id is not None:
        qs = qs.filter(is_platform=False, organization_id=organization_id)
    else:
        logger.error(
            "emit_webhook_event refused cross-tenant fan-out for event=%s",
            event,
        )
        return

    for endpoint in qs.iterator():
        if event not in (endpoint.events or []):
            continue
        schedule_webhook_delivery(str(endpoint.id), event, data)
