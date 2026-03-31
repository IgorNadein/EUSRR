from django.apps import AppConfig


class FeedConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'feed'

    def ready(self):
        # Подключаем модуль уведомлений (signals регистрируются автоматически)
        import feed.notifications  # noqa
