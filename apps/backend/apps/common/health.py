from django.conf import settings
from django.core.cache import cache
from django.db import connection
from django.http import JsonResponse
from django.views import View


def _check_database() -> bool:
    try:
        connection.ensure_connection()
        return connection.is_usable()
    except Exception:
        return False


def _check_redis() -> bool | None:
    """Return True/False when Redis cache is configured; None when LocMem (local)."""
    backend = settings.CACHES.get("default", {}).get("BACKEND", "")
    if "redis" not in backend.lower():
        return None
    try:
        cache.set("healthcheck", "1", timeout=5)
        return cache.get("healthcheck") == "1"
    except Exception:
        return False


def _check_celery_broker() -> bool | None:
    broker = (getattr(settings, "CELERY_BROKER_URL", "") or "").strip()
    if not broker:
        return None
    if not broker.startswith("redis://"):
        # Avoid probing unknown broker types in the hot path.
        return None
    try:
        import redis
        from urllib.parse import urlparse

        parsed = urlparse(broker)
        client = redis.Redis(
            host=parsed.hostname or "localhost",
            port=parsed.port or 6379,
            db=int((parsed.path or "/0").lstrip("/") or "0"),
            socket_connect_timeout=2,
            socket_timeout=2,
        )
        return client.ping() is True
    except Exception:
        return False


class HealthView(View):
    """Unauthenticated liveness/readiness probe for load balancers."""

    def get(self, request):
        deep = request.GET.get("deep") in ("1", "true", "yes")
        db_ok = _check_database()
        checks = {"database": db_ok}

        if deep:
            redis_ok = _check_redis()
            broker_ok = _check_celery_broker()
            if redis_ok is not None:
                checks["redis"] = redis_ok
            if broker_ok is not None:
                checks["celery_broker"] = broker_ok

        critical_ok = db_ok and all(v is not False for v in checks.values())
        status = 200 if critical_ok else 503
        return JsonResponse(
            {
                "status": "ok" if critical_ok else "degraded",
                **checks,
            },
            status=status,
        )
