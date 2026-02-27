# flake8: noqa
"""
Пакет views для employees API.

Разбит из монолитного views.py на отдельные модули по ViewSet/области ответственности.
"""

from .actions import EmployeeActionViewSet
from .auth import RegisterAPIView, ResendEmailAPIView, VerifyEmailAPIView
from .departments import DepartmentViewSet
from .employees import EmployeeViewSet
from .groups import GroupViewSet
from .positions import PositionViewSet
from .roles import DepartmentRoleViewSet
from .skills import SkillViewSet

__all__ = [
    "DepartmentViewSet",
    "EmployeeViewSet",
    "PositionViewSet",
    "DepartmentRoleViewSet",
    "SkillViewSet",
    "EmployeeActionViewSet",
    "GroupViewSet",
    "RegisterAPIView",
    "VerifyEmailAPIView",
    "ResendEmailAPIView",
]
