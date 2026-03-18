"""Django signals для приложения employees.

Структура:
- common: общие сигналы (создание кадровых событий, чаты отделов)
- birthday: синхронизация дней рождений с django-scheduler
- ldap/: автоматическая синхронизация с LDAP
  - employee: Employee ↔ LDAP User
  - department: Department ↔ LDAP OU
  - group: Group ↔ LDAP Group
"""

from . import common, birthday
from .ldap import employee, department, group

__all__ = ['common', 'birthday', 'employee', 'department', 'group']
