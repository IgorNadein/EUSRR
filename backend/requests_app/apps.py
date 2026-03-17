from django.apps import AppConfig


class RequestsAppConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'requests_app'
    
    def ready(self):
        # Подключаем модуль уведомлений (signals регистрируются автоматически)
        import requests_app.notifications.signals  # noqa
        # import requests_app.signals  # MOVED: Автоматическое создание EmployeeAction теперь в employees/signals.py
        import requests_app.rules  # django-rules: регистрация предикатов и правил доступа
