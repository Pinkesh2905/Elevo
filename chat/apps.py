from django.apps import AppConfig


class ChatConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chat'
    verbose_name = 'Chat & Messaging'

    def ready(self):
        # Schedule the missed message email task if django_q is installed
        try:
            from django_q.models import Schedule
            from django_q.tasks import schedule
            
            # Use a unique name to avoid duplicate schedules
            task_name = 'chat.tasks.send_missed_message_emails'
            
            if not Schedule.objects.filter(func=task_name).exists():
                schedule(
                    task_name,
                    schedule_type=Schedule.HOURLY,
                    repeats=-1  # Infinite
                )
        except (ImportError, Exception):
            # Fail silently if django-q is not set up correctly or during migrations
            pass
