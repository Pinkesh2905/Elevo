from django.apps import AppConfig


class PracticeConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'practice'
    verbose_name = 'Practice Problems'
    
    def ready(self):
        """
        Import signals here if needed in the future
        Example: import practice.signals
        """
        pass