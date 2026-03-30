"""Django signals для приложения employees.

Структура:
- common: общие сигналы (создание кадровых событий, чаты отделов)
- birthday: синхронизация дней рождений с django-scheduler
- ldap/: автоматическая синхронизация с LDAP (подключается при LDAP_ENABLED)
  - employee: Employee ↔ LDAP User
  - department: Department ↔ LDAP OU
  - group: Group ↔ LDAP Group
"""

from django.conf import settings

from . import common, birthday

if getattr(settings, 'LDAP_ENABLED', False):
    from .ldap import employee, department, group
    __all__ = ['common', 'birthday', 'employee', 'department', 'group']
else:
    __all__ = ['common', 'birthday']
