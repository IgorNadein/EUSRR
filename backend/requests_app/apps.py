from django.apps import AppConfig


class RequestsAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'requests_app'
    
    def ready(self):
        # Подключаем signals для уведомлений
        import requests_app.notification_signals  # noqa
