# employees/apps.py
from django.apps import AppConfig


class EmployeesConfig(AppConfig):
    name = 'employees'

    def ready(self):
        import employees.signals  # Все сигналы (common, birthday, ldap)
        import employees.rules    # django-rules: регистрация предикатов и правил доступа
