from django.apps import AppConfig


class ProcurementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'procurement'
    verbose_name = 'Закупки и инвентаризация'

    def ready(self):
        """Подключение сигналов при загрузке приложения."""
        import procurement.notifications.signals  # noqa: F401
        # django-rules: регистрация предикатов и правил доступа
        import procurement.rules  # noqa: F401
