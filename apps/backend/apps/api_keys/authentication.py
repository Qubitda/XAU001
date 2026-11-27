from rest_framework.authentication import BaseAuthentication, get_authorization_header
from rest_framework.exceptions import AuthenticationFailed

from .services import verify_api_key


class ApiKeyAuthentication(BaseAuthentication):
    """
    Bearer token or X-Api-Key header. Does not enforce CSRF (stateless external integrations).
    Sets ``request.api_key`` on success; ``request.user`` is the key's ``created_by``.
    """

    www_authenticate_realm = "api"

    def authenticate(self, request):
        raw_key = self._extract_raw_key(request)
        if not raw_key:
            return None

        api_key = verify_api_key(raw_key)
        if api_key is None:
            raise AuthenticationFailed("Geçersiz veya süresi dolmuş API anahtarı.")

        setattr(request, "api_key", api_key)
        return (api_key.created_by, api_key)

    def authenticate_header(self, request):
        return 'Bearer realm="api"'

    @staticmethod
    def _extract_raw_key(request) -> str | None:
        header_api_key = (request.headers.get("X-Api-Key") or "").strip()
        if header_api_key:
            return header_api_key

        auth = get_authorization_header(request).split()
        if len(auth) == 2 and auth[0].lower() == b"bearer":
            try:
                return auth[1].decode("utf-8").strip()
            except UnicodeDecodeError:
                return None
        return None


try:
    from drf_spectacular.extensions import OpenApiAuthenticationExtension

    class ApiKeyAuthenticationScheme(OpenApiAuthenticationExtension):
        target_class = "apps.api_keys.authentication.ApiKeyAuthentication"
        name = "ApiKeyAuth"

        def get_security_definition(self, auto_schema):
            return {
                "type": "apiKey",
                "in": "header",
                "name": "X-Api-Key",
            }
except ImportError:
    pass
