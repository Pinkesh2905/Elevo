from django.apps import AppConfig


class ChatConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chat'
    verbose_name = 'Chat & Messaging'

    def ready(self):
        # Enable SQLite WAL mode to prevent database locking during SSE
        from django.db.backends.signals import connection_created
        from django.dispatch import receiver

        @receiver(connection_created)
        def set_sqlite_pragma(sender, connection, **kwargs):
            if connection.vendor == 'sqlite':
                with connection.cursor() as cursor:
                    cursor.execute('PRAGMA journal_mode=WAL;')
                    cursor.execute('PRAGMA synchronous=NORMAL;')

        # Schedule the missed message email task if django_q is installed
        try:
            from django_q.models import Schedule
            from django_q.tasks import schedule
            
            task_name = 'chat.tasks.send_missed_message_emails'
            if not Schedule.objects.filter(func=task_name).exists():
                schedule(task_name, schedule_type=Schedule.HOURLY, repeats=-1)
        except:
            pass
