# flake8: noqa: F401
"""Реэкспорт permissions из api.v1.permissions для обратной совместимости.

Модуль views/ стал пакетом, и относительный импорт ``..permissions``
из его подмодулей резолвится сюда (api.v1.employees.permissions).
"""

from api.v1.permissions import (
    AdminOrActionOrModelPerms,
    AdminOrDeptAllowed,
    IsSelfOrStaff,
    has_dept_perm,
)

__all__ = [
    "AdminOrActionOrModelPerms",
    "AdminOrDeptAllowed",
    "IsSelfOrStaff",
    "has_dept_perm",
]
