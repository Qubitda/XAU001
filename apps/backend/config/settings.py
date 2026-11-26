import os
import secrets
import sys
from pathlib import Path
from urllib.parse import unquote, urlparse

BASE_DIR = Path(__file__).resolve().parent.parent

DEBUG = os.environ.get("DJANGO_DEBUG", "0") == "1"
TESTING = os.environ.get("DJANGO_TESTING", "0") == "1" or "test" in sys.argv

_env_secret = os.environ.get("DJANGO_SECRET_KEY", "").strip()
if _env_secret:
    SECRET_KEY = _env_secret
elif DEBUG or TESTING:
    SECRET_KEY = secrets.token_urlsafe(48)
else:
    raise RuntimeError("DJANGO_SECRET_KEY environment variable is required when DJANGO_DEBUG=0.")

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1").split(",")
    if h.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # Third-party
    "rest_framework",
    "corsheaders",
    "django_filters",
    "drf_spectacular",
    # Tara Gold Bounded Contexts
    "apps.common",
    "apps.accounts",
    "apps.organizations",
    "apps.authorization",
    "apps.customers",
    "apps.consent",
    "apps.contracts",
    "apps.integrations",
    "apps.messaging",
    "apps.market",
    "apps.catalog",
    "apps.definitions",
    "apps.pricing",
    "apps.inventory",
    "apps.finance",
    "apps.production",
    "apps.commerce",
    "apps.marketplace",
    "apps.audit",
    "apps.notifications",
    "apps.mail",
    "apps.api_keys",
    "apps.idempotency",
    "apps.webhooks",
]

# Optional commercial module: iyzico Checkout Form for B2C card payments.
# Off → payments app not loaded; storefront falls back to BANK_TRANSFER only.
ENABLE_IYZICO_PAYMENTS = os.environ.get("ENABLE_IYZICO_PAYMENTS", "1") == "1"
if ENABLE_IYZICO_PAYMENTS:
    INSTALLED_APPS.append("apps.payments")

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "apps.common.middleware.SecurityHeadersMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
AUTH_USER_MODEL = "accounts.User"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# Database:
# - Production (DJANGO_DEBUG=0 and not TESTING): DATABASE_URL with PostgreSQL is MANDATORY.
#   Never silently fall back to SQLite in production.
# - Local development / unit tests: supports DATABASE_URL, POSTGRES_* env vars, or SQLite.
_db_url = os.environ.get("DATABASE_URL", "").strip()
_pg_password = os.environ.get("POSTGRES_PASSWORD", "")
_pg_host = os.environ.get("POSTGRES_HOST", "").strip()
_pg_db = os.environ.get("POSTGRES_DB", "").strip()

if _db_url:
    if not _db_url.startswith(("postgres://", "postgresql://")):
        raise RuntimeError(
            "DATABASE_URL must use the postgres:// or postgresql:// scheme."
        )
    _parsed = urlparse(_db_url)
    _db_name = _parsed.path.lstrip("/")
    if not _parsed.hostname or not _db_name:
        raise RuntimeError(
            "DATABASE_URL is invalid: both host and database name are required."
        )
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _db_name,
            "USER": unquote(_parsed.username) if _parsed.username else os.environ.get("POSTGRES_USER", "taragold"),
            "PASSWORD": unquote(_parsed.password) if _parsed.password else _pg_password,
            "HOST": _parsed.hostname,
            "PORT": str(_parsed.port or os.environ.get("POSTGRES_PORT", "5432")),
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
        }
    }
elif not DEBUG and not TESTING:
    raise RuntimeError(
        "DATABASE_URL environment variable is required in production (DJANGO_DEBUG=0). "
        "Silent SQLite fallback is disabled."
    )
elif _pg_host or _pg_db:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": _pg_db or "taragold",
            "USER": os.environ.get("POSTGRES_USER", "taragold"),
            "PASSWORD": _pg_password,
            "HOST": _pg_host or "db",
            "PORT": str(os.environ.get("POSTGRES_PORT", "5432")),
            "CONN_MAX_AGE": 60,
            "CONN_HEALTH_CHECKS": True,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# Cache & Celery (Redis)
REDIS_URL = os.environ.get("REDIS_URL", "").strip()
if REDIS_URL:
    CACHES = {
        "default": {
            "BACKEND": "django_redis.cache.RedisCache",
            "LOCATION": REDIS_URL,
            "OPTIONS": {
                "CLIENT_CLASS": "django_redis.client.DefaultClient",
                "SOCKET_CONNECT_TIMEOUT": 5,
                "SOCKET_TIMEOUT": 5,
            },
        }
    }
else:
    CACHES = {
        "default": {
            "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        }
    }

CELERY_BROKER_URL = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
CELERY_RESULT_BACKEND = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")
CELERY_TIMEZONE = "Europe/Istanbul"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_BROKER_CONNECTION_MAX_RETRIES = 10
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_TASK_SOFT_TIME_LIMIT = 60
CELERY_TASK_TIME_LIMIT = 120
DYO_STONE_LOCK_TTL_SECONDS = int(os.environ.get("DYO_STONE_LOCK_TTL_SECONDS", str(15 * 60)))

# Abandoned cart / B2B draft recovery (Faz 1)
CART_RECOVERY_B2C_T1_SECONDS = int(os.environ.get("CART_RECOVERY_B2C_T1_SECONDS", str(3600)))
CART_RECOVERY_B2C_T2_SECONDS = int(os.environ.get("CART_RECOVERY_B2C_T2_SECONDS", str(12 * 3600)))
CART_RECOVERY_B2C_T3_SECONDS = int(os.environ.get("CART_RECOVERY_B2C_T3_SECONDS", str(24 * 3600)))
CART_RECOVERY_B2B_T1_SECONDS = int(os.environ.get("CART_RECOVERY_B2B_T1_SECONDS", str(3600)))
CART_RECOVERY_B2B_T2_SECONDS = int(os.environ.get("CART_RECOVERY_B2B_T2_SECONDS", str(24 * 3600)))
CART_RECOVERY_B2B_T3_SECONDS = int(os.environ.get("CART_RECOVERY_B2B_T3_SECONDS", str(48 * 3600)))
CART_RECOVERY_COOLDOWN_DAYS = int(os.environ.get("CART_RECOVERY_COOLDOWN_DAYS", "7"))
CART_RECOVERY_B2B_OPS_THRESHOLD_TRY = os.environ.get("CART_RECOVERY_B2B_OPS_THRESHOLD_TRY", "50000")
CART_RECOVERY_B2C_OPS_THRESHOLD_TRY = os.environ.get("CART_RECOVERY_B2C_OPS_THRESHOLD_TRY", "100000")

# Faz D — SMS / WhatsApp (console stub by default; webhook when URL set)
MESSAGING_SMS_ENABLED = os.environ.get("MESSAGING_SMS_ENABLED", "0") == "1"
MESSAGING_WHATSAPP_ENABLED = os.environ.get("MESSAGING_WHATSAPP_ENABLED", "0") == "1"
MESSAGING_SMS_PROVIDER = os.environ.get("MESSAGING_SMS_PROVIDER", "console")
MESSAGING_WHATSAPP_PROVIDER = os.environ.get("MESSAGING_WHATSAPP_PROVIDER", "console")
MESSAGING_SMS_WEBHOOK_URL = os.environ.get("MESSAGING_SMS_WEBHOOK_URL", "").strip()
MESSAGING_WHATSAPP_WEBHOOK_URL = os.environ.get("MESSAGING_WHATSAPP_WEBHOOK_URL", "").strip()
MESSAGING_WEBHOOK_TIMEOUT = float(os.environ.get("MESSAGING_WEBHOOK_TIMEOUT", "8"))
STOREFRONT_PUBLIC_URL = os.environ.get("STOREFRONT_PUBLIC_URL", "http://localhost:3000")
B2B_PUBLIC_URL = os.environ.get("B2B_PUBLIC_URL", "http://localhost:3001")

CELERY_BEAT_SCHEDULE = {
    "release-expired-stone-locks": {
        "task": "commerce.release_expired_stone_locks",
        "schedule": 60.0,
    },
    "cleanup-expired-price-locks": {
        "task": "pricing.cleanup_expired_price_locks",
        "schedule": 300.0,
    },
    "scan-abandoned-carts": {
        "task": "commerce.scan_abandoned_carts",
        "schedule": 300.0,
    },
    "refresh-market-rates-snapshot": {
        "task": "market.refresh_rates_snapshot",
        # Placeholder until an external FX feed is wired; keeps beat ownership explicit.
        "schedule": 900.0,
    },
    "apply-document-retention": {
        "task": "organizations.apply_document_retention",
        "schedule": 86400.0,
    },
}

# Security, Sessions & CORS
# Separate local HTTP vs production HTTPS cookie security via DJANGO_SECURE_COOKIES.
# Defaults to False when DEBUG=1 (local HTTP) and True when DEBUG=0 (production HTTPS).
SECURE_COOKIES = os.environ.get("DJANGO_SECURE_COOKIES", "0" if DEBUG else "1") == "1"

CORS_ALLOW_CREDENTIALS = True
CORS_ALLOWED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CORS_ALLOWED_ORIGINS",
        "http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:3003",
    ).split(",")
    if o.strip()
]
CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CSRF_TRUSTED_ORIGINS",
        "http://localhost:3000,http://localhost:3001,http://localhost:3002,http://localhost:3003",
    ).split(",")
    if o.strip()
]
CORS_ALLOW_HEADERS = [
    "accept",
    "authorization",
    "content-type",
    "idempotency-key",
    "x-api-key",
    "x-csrftoken",
    "x-csrf-token",
    "x-organization-id",
    "x-branch-id",
    "x-membership-id",
    "x-requested-with",
]

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = SECURE_COOKIES
SESSION_COOKIE_SAMESITE = os.environ.get("DJANGO_SESSION_COOKIE_SAMESITE", "Lax")
SESSION_COOKIE_AGE = int(os.environ.get("DJANGO_SESSION_COOKIE_AGE", str(60 * 60 * 12)))
SESSION_EXPIRE_AT_BROWSER_CLOSE = os.environ.get("DJANGO_SESSION_EXPIRE_AT_BROWSER_CLOSE", "0") == "1"
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SECURE = SECURE_COOKIES
CSRF_COOKIE_SAMESITE = os.environ.get("DJANGO_CSRF_COOKIE_SAMESITE", "Lax")
CSRF_HEADER_NAME = "HTTP_X_CSRF_TOKEN"

# Always-on baseline (even on local HTTP); HTTPS extras gated by SECURE_COOKIES.
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = "same-origin"
X_FRAME_OPTIONS = "DENY"
DATA_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get("DJANGO_DATA_UPLOAD_MAX_MEMORY_SIZE", str(2 * 1024 * 1024)))
DATA_UPLOAD_MAX_NUMBER_FIELDS = int(os.environ.get("DJANGO_DATA_UPLOAD_MAX_NUMBER_FIELDS", "1000"))
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get("DJANGO_FILE_UPLOAD_MAX_MEMORY_SIZE", str(2 * 1024 * 1024)))

if SECURE_COOKIES:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_SSL_REDIRECT = os.environ.get("DJANGO_SECURE_SSL_REDIRECT", "1") == "1"
    SECURE_HSTS_SECONDS = int(os.environ.get("DJANGO_SECURE_HSTS_SECONDS", "31536000"))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "tr-tr"
TIME_ZONE = "Europe/Istanbul"
USE_I18N = True
USE_TZ = True
STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

# Persistent media: local filesystem (Docker volume) by default; S3/MinIO when bucket is set.
_AWS_STORAGE_BUCKET_NAME = os.environ.get("AWS_STORAGE_BUCKET_NAME", "").strip()
if _AWS_STORAGE_BUCKET_NAME:
    AWS_ACCESS_KEY_ID = os.environ.get("AWS_ACCESS_KEY_ID", "")
    AWS_SECRET_ACCESS_KEY = os.environ.get("AWS_SECRET_ACCESS_KEY", "")
    AWS_STORAGE_BUCKET_NAME = _AWS_STORAGE_BUCKET_NAME
    AWS_S3_REGION_NAME = os.environ.get("AWS_S3_REGION_NAME", "eu-central-1")
    AWS_S3_ENDPOINT_URL = os.environ.get("AWS_S3_ENDPOINT_URL", "").strip() or None
    AWS_DEFAULT_ACL = None
    AWS_QUERYSTRING_AUTH = os.environ.get("AWS_QUERYSTRING_AUTH", "1") == "1"
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_S3_FILE_OVERWRITE = False
    STORAGES = {
        "default": {
            "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
            "OPTIONS": {
                "bucket_name": AWS_STORAGE_BUCKET_NAME,
                "region_name": AWS_S3_REGION_NAME,
                **({"endpoint_url": AWS_S3_ENDPOINT_URL} if AWS_S3_ENDPOINT_URL else {}),
            },
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
        },
    }
else:
    STORAGES = {
        "default": {
            "BACKEND": "django.core.files.storage.FileSystemStorage",
        },
        "staticfiles": {
            "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
        },
    }
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
FILE_UPLOAD_MAX_MEMORY_SIZE = int(os.environ.get("DJANGO_FILE_UPLOAD_MAX_MEMORY_SIZE", str(5 * 1024 * 1024)))

_num_proxies_raw = os.environ.get("NUM_PROXIES", "").strip()
_NUM_PROXIES = int(_num_proxies_raw) if _num_proxies_raw.isdigit() else None

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "apps.api_keys.authentication.ApiKeyAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_THROTTLE_CLASSES": [
        "apps.accounts.throttling.BurstAnonRateThrottle",
        "apps.accounts.throttling.BurstUserRateThrottle",
        "apps.api_keys.throttling.ApiKeyRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {
        "anon": os.environ.get("DRF_THROTTLE_ANON", "60/min"),
        "user": os.environ.get("DRF_THROTTLE_USER", "300/min"),
        "login": os.environ.get("DRF_THROTTLE_LOGIN", "10/min"),
        "api_key": os.environ.get("DRF_THROTTLE_API_KEY", "120/min"),
    },
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    "EXCEPTION_HANDLER": "config.exceptions.taragold_exception_handler",
    # Never coerce financial Decimals into IEEE-754 floats on the wire.
    "COERCE_DECIMAL_TO_STRING": True,
    # Behind a reverse proxy, set NUM_PROXIES so anon throttle uses the real client IP.
    **({"NUM_PROXIES": _NUM_PROXIES} if _NUM_PROXIES is not None else {}),
}

# API key hash pepper (HMAC). Empty → SECRET_KEY. Set a dedicated value in production
# so rotating SECRET_KEY does not invalidate all integration keys.
API_KEY_HASH_PEPPER = os.environ.get("API_KEY_HASH_PEPPER", "").strip()

# Account lifecycle / B2C self-registration
ENABLE_B2C_SELF_REGISTER = os.environ.get("ENABLE_B2C_SELF_REGISTER", "1") == "1"
ENFORCE_EMAIL_VERIFICATION = os.environ.get("ENFORCE_EMAIL_VERIFICATION", "0") == "1"
FRONTEND_STOREFRONT_URL = os.environ.get(
    "FRONTEND_STOREFRONT_URL",
    os.environ.get("VITE_STOREFRONT_URL", "http://localhost:3000/"),
).rstrip("/")

# iyzico keys only matter when ENABLE_IYZICO_PAYMENTS=1 (optional commercial module).
_IYZICO_BASE_RAW = os.environ.get("IYZICO_BASE_URL", "sandbox-api.iyzipay.com").strip()
IYZICO_BASE_URL = _IYZICO_BASE_RAW.replace("https://", "").replace("http://", "").rstrip("/")
IYZICO_API_KEY = os.environ.get("IYZICO_API_KEY", "").strip()
IYZICO_SECRET_KEY = os.environ.get("IYZICO_SECRET_KEY", "").strip()
IYZICO_CALLBACK_BASE_URL = os.environ.get(
    "IYZICO_CALLBACK_BASE_URL",
    os.environ.get("APP_URL", "http://localhost:8000"),
).rstrip("/")

DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", "noreply@taragold.local")
SERVER_EMAIL = os.environ.get("SERVER_EMAIL", DEFAULT_FROM_EMAIL)
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.console.EmailBackend" if DEBUG else "django.core.mail.backends.smtp.EmailBackend",
)
EMAIL_HOST = os.environ.get("EMAIL_HOST", "localhost")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "1") == "1"
EMAIL_USE_SSL = os.environ.get("EMAIL_USE_SSL", "0") == "1"
# AES-256 key material for SMTP password encryption (falls back to SECRET_KEY).
MAIL_ENCRYPTION_KEY = os.environ.get("MAIL_ENCRYPTION_KEY", "").strip()
MAIL_DEFAULT_LOGO_URL = os.environ.get("MAIL_DEFAULT_LOGO_URL", "").strip()

# KVKK: soft-deactivate expired docs daily; hard-delete only when >0 days configured.
DOCUMENT_HARD_DELETE_DAYS = int(os.environ.get("DOCUMENT_HARD_DELETE_DAYS", "0") or "0")

# Market rate feed (JSON). Empty = beat task idles unless MARKET_RATES_REFRESH_CLONE=1.
MARKET_RATES_FEED_URL = os.environ.get("MARKET_RATES_FEED_URL", "").strip()
MARKET_RATES_REFRESH_CLONE = os.environ.get("MARKET_RATES_REFRESH_CLONE", "0") == "1"

# Core+detail product model migration flags
CATALOG_DUAL_WRITE_DETAILS = os.environ.get("CATALOG_DUAL_WRITE_DETAILS", "1") == "1"
PRICING_READ_FROM_DETAILS = os.environ.get("PRICING_READ_FROM_DETAILS", "0") == "1"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "%(asctime)s %(levelname)s [%(name)s] %(message)s",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("LOG_LEVEL", "INFO"),
    },
    "loggers": {
        "django.request": {"handlers": ["console"], "level": "WARNING", "propagate": False},
        "celery": {"handlers": ["console"], "level": "INFO", "propagate": False},
    },
}

_SENTRY_DSN = os.environ.get("SENTRY_DSN", "").strip()
if _SENTRY_DSN:
    try:
        import sentry_sdk
        from sentry_sdk.integrations.celery import CeleryIntegration
        from sentry_sdk.integrations.django import DjangoIntegration

        sentry_sdk.init(
            dsn=_SENTRY_DSN,
            integrations=[DjangoIntegration(), CeleryIntegration()],
            environment=os.environ.get("SENTRY_ENVIRONMENT", "production" if not DEBUG else "development"),
            traces_sample_rate=float(os.environ.get("SENTRY_TRACES_SAMPLE_RATE", "0.0")),
            send_default_pii=False,
        )
    except ImportError:
        pass


SPECTACULAR_SETTINGS = {
    "TITLE": "Tara Gold B2B/B2C Kuyumculuk API",
    "DESCRIPTION": (
        "Çok firmalı/şubeli kuyumculuk platformu — Storefront, B2B Bayi Portalı ve OPS. "
        "Harici entegrasyonlar: Authorization: Bearer tg_live_… veya X-Api-Key (OPS’ten üretilir)."
    ),
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Schema/docs are OPS-only in non-debug environments (reduce attack surface).
    "SERVE_PERMISSIONS": (
        ["rest_framework.permissions.AllowAny"]
        if DEBUG
        else ["apps.authorization.permissions.IsOpsUser"]
    ),
    "COMPONENT_SPLIT_REQUEST": True,
    "APPEND_COMPONENTS": {
        "securitySchemes": {
            "ApiKeyBearer": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "tg_live_",
                "description": "OPS’te üretilen API anahtarı (tg_live_…).",
            },
            "ApiKeyHeader": {
                "type": "apiKey",
                "in": "header",
                "name": "X-Api-Key",
            },
        }
    },
}
