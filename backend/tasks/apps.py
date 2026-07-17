from django.apps import AppConfig


class TasksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "tasks"
    verbose_name = "Задачи"

    def ready(self):
        import tasks.notifications.signals  # noqa: F401
        import tasks.signals  # noqa: F401
