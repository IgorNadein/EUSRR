# employees/apps.py
from django.apps import AppConfig


class EmployeesConfig(AppConfig):
    name = 'employees'

    def ready(self):
        import employees.signals
        import employees.signals_birthday  # Сигналы для синхронизации дней рождений с django-scheduler
        import employees.signals_ldap  # Сигналы для автоматической синхронизации Employee с LDAP
        import employees.signals_department  # Сигналы для автоматической синхронизации Department с LDAP
        import employees.signals_group  # Сигналы для автоматической синхронизации Group с LDAP
        import employees.rules  # django-rules: регистрация предикатов и правил доступа
