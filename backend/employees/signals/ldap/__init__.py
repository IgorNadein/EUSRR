"""LDAP signals для автоматической синхронизации моделей с Active Directory."""

from . import employee, department, group

__all__ = ['employee', 'department', 'group']
