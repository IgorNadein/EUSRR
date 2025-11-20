from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "documents"

    def ready(self):
        # импортируем сигналы, чтобы они подхватились
        import documents.signals  # noqa
        import documents.notification_signals  # noqa
