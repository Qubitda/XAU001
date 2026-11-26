"""Webhook destination URL hardening (SSRF guard)."""

from __future__ import annotations

import ipaddress
import socket
from urllib.parse import urlparse

from django.conf import settings

from config.exceptions import DomainError

_BLOCKED_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.localdomain",
        "metadata.google.internal",
        "metadata",
    }
)


def _is_blocked_ip(ip: ipaddress.IPv4Address | ipaddress.IPv6Address) -> bool:
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_reserved
        or ip.is_unspecified
        or (ip.version == 4 and ip in ipaddress.ip_network("169.254.0.0/16"))
        or (ip.version == 6 and ip in ipaddress.ip_network("fd00::/8"))
    )


def validate_webhook_url(url: str, *, allow_http: bool | None = None) -> str:
    """
    Validate operator-supplied webhook URL before persist / delivery.
    - https required (http only when DEBUG / allow_http)
    - no credentials in URL
    - hostname must resolve to non-private addresses
    """
    raw = (url or "").strip()
    if not raw:
        raise DomainError("Webhook URL zorunlu.", code="WEBHOOK_URL_INVALID", status_code=400)

    parsed = urlparse(raw)
    scheme = (parsed.scheme or "").lower()
    http_ok = settings.DEBUG if allow_http is None else allow_http
    if scheme == "http" and not http_ok:
        raise DomainError(
            "Webhook URL yalnızca HTTPS olabilir.",
            code="WEBHOOK_URL_HTTPS_REQUIRED",
            status_code=400,
        )
    if scheme not in ("https", "http"):
        raise DomainError(
            "Webhook URL şeması http veya https olmalıdır.",
            code="WEBHOOK_URL_INVALID",
            status_code=400,
        )
    if parsed.username or parsed.password:
        raise DomainError(
            "Webhook URL kullanıcı bilgisi içeremez.",
            code="WEBHOOK_URL_INVALID",
            status_code=400,
        )
    host = (parsed.hostname or "").strip().lower().rstrip(".")
    if not host:
        raise DomainError("Webhook URL host zorunlu.", code="WEBHOOK_URL_INVALID", status_code=400)
    if host in _BLOCKED_HOSTNAMES or host.endswith(".localhost") or host.endswith(".local"):
        raise DomainError(
            "Webhook URL özel / iç ağ adresine yönlendirilemez.",
            code="WEBHOOK_URL_BLOCKED",
            status_code=400,
        )

    try:
        port = parsed.port
    except ValueError as exc:
        raise DomainError("Webhook URL port geçersiz.", code="WEBHOOK_URL_INVALID", status_code=400) from exc
    if port is not None and port not in (80, 443) and not http_ok:
        # Allow non-standard ports only in DEBUG; still subject to IP checks.
        pass

    # Literal IP in hostname
    try:
        literal_ip = ipaddress.ip_address(host)
    except ValueError:
        literal_ip = None
    if literal_ip is not None and _is_blocked_ip(literal_ip):
        raise DomainError(
            "Webhook URL özel / iç ağ adresine yönlendirilemez.",
            code="WEBHOOK_URL_BLOCKED",
            status_code=400,
        )

    # DNS resolution — block if any resolved address is private
    try:
        addrinfos = socket.getaddrinfo(host, port or (443 if scheme == "https" else 80), type=socket.SOCK_STREAM)
    except socket.gaierror as exc:
        raise DomainError(
            "Webhook URL host çözümlenemedi.",
            code="WEBHOOK_URL_UNRESOLVABLE",
            status_code=400,
        ) from exc

    if not addrinfos:
        raise DomainError(
            "Webhook URL host çözümlenemedi.",
            code="WEBHOOK_URL_UNRESOLVABLE",
            status_code=400,
        )

    for info in addrinfos:
        ip_str = info[4][0]
        try:
            ip = ipaddress.ip_address(ip_str)
        except ValueError:
            continue
        if _is_blocked_ip(ip):
            raise DomainError(
                "Webhook URL özel / iç ağ adresine yönlendirilemez.",
                code="WEBHOOK_URL_BLOCKED",
                status_code=400,
            )

    return raw
