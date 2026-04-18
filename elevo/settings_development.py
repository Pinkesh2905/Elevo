from .settings_base import *  # noqa


DEBUG = True

# Development convenience defaults
# Respect EMAIL_BACKEND from env (handled in settings_base)
# EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"
SECURE_SSL_REDIRECT = False
SESSION_COOKIE_SECURE = False
CSRF_COOKIE_SECURE = False
