from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'
    verbose_name = "REST API layer"

    def ready(self):
        """Инициализация при загрузке приложения."""
        # Патч для django-scheduler теперь применяется в scheduling.apps.SchedulingConfig
        pass
