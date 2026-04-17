from django.apps import AppConfig


class ChatConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'chat'
    verbose_name = 'Chat & Messaging'

    def ready(self):
        # Enable SQLite WAL mode to prevent database locking during SSE
        from django.db.backends.signals import connection_created
        from django.core.signals import request_started
        from django.dispatch import receiver

        @receiver(connection_created)
        def set_sqlite_pragma(sender, connection, **kwargs):
            if connection.vendor == 'sqlite':
                with connection.cursor() as cursor:
                    cursor.execute('PRAGMA journal_mode=WAL;')
                    cursor.execute('PRAGMA synchronous=NORMAL;')

        @receiver(request_started, dispatch_uid='chat.ensure_missed_message_schedule')
        def ensure_missed_message_schedule(sender, **kwargs):
            request_started.disconnect(
                ensure_missed_message_schedule,
                dispatch_uid='chat.ensure_missed_message_schedule',
            )
            try:
                from django_q.models import Schedule
                from django_q.tasks import schedule

                task_name = 'chat.tasks.send_missed_message_emails'
                if not Schedule.objects.filter(func=task_name).exists():
                    schedule(task_name, schedule_type=Schedule.HOURLY, repeats=-1)
            except Exception:
                pass
