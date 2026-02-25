from django.apps import AppConfig


class ApiConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'api'
    verbose_name = "REST API layer"

    def ready(self):
        """Инициализация при загрузке приложения."""
        # Применяем патч для django-scheduler (исправление бага с byweekday)
        print("🔧 ApiConfig.ready() - применение патча django-scheduler")
        import schedule_patch
        schedule_patch.apply_patch()
