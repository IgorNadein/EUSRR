from django.apps import AppConfig


class DocumentsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "documents"

    def ready(self):
        # Модуль уведомлений (signals регистрируются автоматически)
        import documents.notifications  # noqa
        import documents.rules  # django-rules: регистрация предикатов и правил доступа
