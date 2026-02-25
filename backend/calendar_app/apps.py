# backend/calendar_app/apps.py
from __future__ import annotations

from django.apps import AppConfig
from django.apps import apps as django_apps
from django.db.models.signals import post_delete, post_save


class CalendarAppConfig(AppConfig):
    """Конфиг приложения календаря. Подключает сигналы к модели сотрудника."""
    name = "calendar_app"
    verbose_name = "Календарь"

    def ready(self) -> None:
        """Подключает обработчики сигналов к employees.Employee.

        Raises:
            LookupError: Если приложение 'employees' или модель 'Employee' не найдены.
        """
        import calendar_app.notification_signals  # noqa: F401
        from calendar_app import \
            signals  # noqa: F401 (гарантирует импорт модулей с хендлерами)

        try:
            Employee = django_apps.get_model("employees", "Employee")
        except LookupError:
            # Если в проекте иное имя модели — замените здесь.
            return

        # Явно подключаем наши функции только к Employee
        post_save.connect(
            signals.handle_employee_saved,
            sender=Employee,
            dispatch_uid="calendar_app.employee_saved_sync_birthday",
        )
        post_delete.connect(
            signals.handle_employee_deleted,
            sender=Employee,
            dispatch_uid="calendar_app.employee_deleted_remove_birthday",
        )
        dispatch_uid = "calendar_app.employee_deleted_remove_birthday",
        
