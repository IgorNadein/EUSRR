from django.apps import AppConfig


class ProcurementConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'procurement'
    verbose_name = 'Закупки и инвентаризация'

    def ready(self):
        """Подключение сигналов при загрузке приложения."""
        import procurement.signals  # noqa: F401
