from django.apps import AppConfig


class OrganizationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'organizations'
    verbose_name = 'Organizations & Subscriptions'

    def ready(self):
        # Register signal handlers for compliance/audit logging.
        from . import signals  # noqa: F401
