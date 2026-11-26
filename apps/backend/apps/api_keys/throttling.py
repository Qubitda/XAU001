from rest_framework.throttling import SimpleRateThrottle


class ApiKeyRateThrottle(SimpleRateThrottle):
    """Per-API-key rate limit for external integrations (session users bypass)."""

    scope = "api_key"

    def get_cache_key(self, request, view):
        api_key = getattr(request, "api_key", None)
        if api_key is None:
            return None
        return self.cache_format % {"scope": self.scope, "ident": str(api_key.id)}
