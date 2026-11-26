"""HTTP security hardening middleware (defense-in-depth beyond Django defaults)."""

from __future__ import annotations


class SecurityHeadersMiddleware:
    """
    Adds browser security headers on every response.
    Complements django.middleware.security.SecurityMiddleware.
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        response.setdefault("X-Content-Type-Options", "nosniff")
        response.setdefault("X-Frame-Options", "DENY")
        response.setdefault("Referrer-Policy", "same-origin")
        response.setdefault(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=()",
        )
        response.setdefault("Cross-Origin-Opener-Policy", "same-origin")
        # API responses should not be sniffed as navigable HTML documents.
        if request.path.startswith("/api/"):
            response.setdefault("X-XSS-Protection", "0")
            ctype = response.get("Content-Type", "")
            if "text/html" in ctype.lower():
                response["Content-Type"] = "application/json; charset=utf-8"
        return response
