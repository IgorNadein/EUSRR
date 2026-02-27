# employees/apps.py
from django.apps import AppConfig


class EmployeesConfig(AppConfig):
    name = 'employees'

    def ready(self):
        import employees.signals
        import employees.signals_birthday  # Сигналы для синхронизации дней рождений с django-scheduler
        import employees.rules  # django-rules: регистрация предикатов и правил доступа
