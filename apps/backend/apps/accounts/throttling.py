from rest_framework.throttling import AnonRateThrottle, SimpleRateThrottle


class LoginRateThrottle(AnonRateThrottle):
    """Brute-force guard for /api/v1/session/login."""

    scope = "login"


class BurstAnonRateThrottle(AnonRateThrottle):
    scope = "anon"


class BurstUserRateThrottle(SimpleRateThrottle):
    scope = "user"

    def get_cache_key(self, request, view):
        if request.user and request.user.is_authenticated:
            return self.cache_format % {
                "scope": self.scope,
                "ident": request.user.pk,
            }
        return None
