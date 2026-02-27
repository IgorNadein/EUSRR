from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "documents"

    def ready(self):
        # импортируем сигналы, чтобы они подхватились
        import documents.notification_signals  # noqa
        import documents.rules  # django-rules: регистрация предикатов и правил доступа
