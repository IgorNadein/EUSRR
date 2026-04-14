"""LDAP signals для автоматической синхронизации моделей с Active Directory."""

from . import employee, department, group, position, role

__all__ = ['employee', 'department', 'group', 'position', 'role']
