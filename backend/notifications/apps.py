from django.apps import AppConfig


class NotificationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'notifications'
    verbose_name = 'Уведомления'

    def ready(self):
        # Загружаем сигналы (notify.send API)
        import notifications.signals  # noqa

        # Загружаем обработчики каналов (post_save → Celery tasks)
        import notifications.channels  # noqa

        # Загружаем Celery задачи
        import notifications.tasks  # noqa
