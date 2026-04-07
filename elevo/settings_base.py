import os
from pathlib import Path
from urllib.parse import urlparse

import environ
import nltk


BASE_DIR = Path(__file__).resolve().parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(os.path.join(BASE_DIR, ".env"))

# Core security/runtime
SECRET_KEY = env("SECRET_KEY")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=[])

RENDER_EXTERNAL_HOSTNAME = env("RENDER_EXTERNAL_HOSTNAME", default=None)
if RENDER_EXTERNAL_HOSTNAME and RENDER_EXTERNAL_HOSTNAME not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(RENDER_EXTERNAL_HOSTNAME)

CSRF_TRUSTED_ORIGINS = []


def _normalize_host(value):
    if not value:
        return None

    candidate = value.strip()
    if not candidate or candidate == "*":
        return None

    if "://" in candidate:
        parsed = urlparse(candidate)
        candidate = parsed.netloc or parsed.path

    candidate = candidate.lstrip(".").rstrip("/")
    return candidate or None


def _append_unique(values, item):
    if item and item not in values:
        values.append(item)


DOMAIN_NAME = env("DOMAIN_NAME", default="localhost:8000")

trusted_hosts = []
for host in ALLOWED_HOSTS:
    _append_unique(trusted_hosts, _normalize_host(host))

_append_unique(trusted_hosts, _normalize_host(RENDER_EXTERNAL_HOSTNAME))
_append_unique(trusted_hosts, _normalize_host(DOMAIN_NAME))

for origin in env.list("CSRF_TRUSTED_ORIGINS", default=[]):
    _append_unique(CSRF_TRUSTED_ORIGINS, origin.rstrip("/"))

for host in trusted_hosts:
    _append_unique(CSRF_TRUSTED_ORIGINS, f"https://{host}")
    if host.startswith("localhost") or host.startswith("127.0.0.1"):
        _append_unique(CSRF_TRUSTED_ORIGINS, f"http://{host}")

# Product scope flags (Week 1 B2B MVP shaping)
B2B_MVP_MODULES = ["organizations", "practice", "aptitude", "mock_interview", "chat"]
SALES_DEMO_MODE = env.bool("SALES_DEMO_MODE", default=False)
SHOW_SOCIAL_IN_SALES_DEMO = env.bool("SHOW_SOCIAL_IN_SALES_DEMO", default=False)
ENABLE_CHAT = env.bool("ENABLE_CHAT", default=True)
SERVE_MEDIA_INSECURE = env.bool("SERVE_MEDIA_INSECURE", default=False)


INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "rest_framework",
    "django_filters",
    "corsheaders",
    "django.contrib.humanize",
    "crispy_forms",
    "crispy_bootstrap5",
    "core",
    "users",
    "practice",
    "aptitude",
    "mock_interview",
    "posts",
    "tutor",
    "chat",
    "organizations.apps.OrganizationsConfig",
    "django_q",
]

CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
CRISPY_TEMPLATE_PACK = "bootstrap5"

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "organizations.middleware.PremiumAccessMiddleware",
]

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.BasicAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticatedOrReadOnly",
    ],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_FILTER_BACKENDS": [
        "django_filters.rest_framework.DjangoFilterBackend",
        "rest_framework.filters.SearchFilter",
        "rest_framework.filters.OrderingFilter",
    ],
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
        "rest_framework.renderers.BrowsableAPIRenderer",
    ],
}

ROOT_URLCONF = "elevo.urls"

CORS_ALLOWED_ORIGINS = env.list(
    "CORS_ALLOWED_ORIGINS",
    default=[
        "http://localhost:3000",
        "http://localhost:8080",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
    ],
)
CORS_ALLOW_CREDENTIALS = True

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [os.path.join(BASE_DIR, "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.product_flags",
            ],
        },
    },
]

WSGI_APPLICATION = "elevo.wsgi.application"
ASGI_APPLICATION = "elevo.asgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL", default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}")
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = env("TIME_ZONE", default="Asia/Kolkata")
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATICFILES_DIRS = [os.path.join(BASE_DIR, "core/static")]
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

EMAIL_BACKEND = env("EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST", default="smtp.gmail.com")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="webmaster@localhost")

NLTK_DATA_DIR = os.path.join(BASE_DIR, "nltk_data")
if os.path.exists(NLTK_DATA_DIR):
    nltk.data.path.append(NLTK_DATA_DIR)

JDOODLE_CLIENT_ID = env("JDOODLE_CLIENT_ID", default="")
JDOODLE_CLIENT_SECRET = env("JDOODLE_CLIENT_SECRET", default="")

AI_PROVIDER = env("AI_PROVIDER", default="gemini")
OPENAI_API_KEY = env("OPENAI_API_KEY", default="")
GEMINI_API_KEY = env("GEMINI_API_KEY", default="")

USE_MOCK_EXECUTOR = os.environ.get("USE_MOCK_EXECUTOR", "False") == "True"

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
        "LOCATION": "unique-snowflake",
    }
}

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "home"
LOGOUT_REDIRECT_URL = "home"

# ---------- Django-Q2 (async task queue) ----------
Q_CLUSTER = {
    "name": "elevo",
    "workers": 2,
    "recycle": 500,
    "timeout": 60,          # hard kill after 60s
    "retry": 90,            # re-queue if no ack within 90s
    "queue_limit": 50,
    "bulk": 10,
    "orm": "default",       # use DB as broker — no Redis needed
    "catch_up": False,
    "max_attempts": 3,
    "ack_failures": True,
}

# ---------- AI Cost Tracking ----------
AI_COST_PER_1K_TOKENS = {
    "gemini": {"input": 0.00010, "output": 0.00040},
    "openai": {"input": 0.00015, "output": 0.00060},
}

# ---------- File Upload Configuration ----------
# Increased limits for high-resolution images and videos (10MB)
DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760
FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760
DATA_UPLOAD_MAX_NUMBER_FIELDS = 1000
