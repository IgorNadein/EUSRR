"""Репозиторий для работы с сотрудниками в Django ORM.

Предоставляет функции для поиска, создания и управления объектами Employee,
а также их связями с отделами.
"""

from __future__ import annotations

from typing import Dict, Iterable, Optional, Set, Tuple


from employees.models import (
    Department,
    Employee,
    EmployeeDepartment,
    LdapSyncState,
)

from ..domain.dtos import LdapPersonDTO
from ..utils.dn_utils import extract_department_from_dn


def load_users_index(
    dtos: Iterable[LdapPersonDTO],
) -> Tuple[Dict[str, Employee], Dict[str, Employee]]:
    """Строит индексы существующих пользователей по GUID и email.

    Args:
        dtos: Итератор DTO пользователей из LDAP.

    Returns:
        Кортеж (by_guid, by_email) - словари для поиска.
    """
    guids: Set[str] = {d.guid.strip() for d in dtos if getattr(d, "guid", None)}
    emails_lower: Set[str] = {
        d.email.strip().lower() for d in dtos if getattr(d, "email", None)
    }

    by_email: Dict[str, Employee] = {}
    if emails_lower:
        qs = Employee.objects.filter(email__in=list(emails_lower)).only(
            "id", "email"
        )
        for u in qs:
            if u.email:
                by_email[u.email.lower()] = u

    by_guid: Dict[str, Employee] = {}
    if guids:
        states = LdapSyncState.objects.filter(
            model="employee",
            ldap_guid__in=guids,
        ).values("ldap_guid", "object_pk")
        emp_map = {
            str(e.pk): e
            for e in Employee.objects.filter(
                pk__in={str(s["object_pk"]) for s in states}
            )
        }
        for s in states:
            emp = emp_map.get(str(s["object_pk"]))
            if emp:
                by_guid[str(s["ldap_guid"])] = emp

    return by_guid, by_email


def find_user_for_dto(
    dto: LdapPersonDTO,
    *,
    by_guid: Dict[str, Employee],
    by_email: Dict[str, Employee],
) -> Optional[Employee]:
    """Находит пользователя по GUID, иначе по e-mail (lower).

    Args:
        dto: DTO пользователя из LDAP.
        by_guid: Индекс пользователей по GUID.
        by_email: Индекс пользователей по email.

    Returns:
        Employee или None, если не найден.
    """
    if dto.guid and dto.guid in by_guid:
        return by_guid[dto.guid]
    if dto.email:
        return by_email.get(dto.email.lower())
    return None


def bind_user_department(user: Employee, dn: str) -> None:
    """Привязывает пользователя к отделу на основе DN.

    Извлекает название отдела из DN и создаёт/обновляет связь
    EmployeeDepartment, деактивируя старые связи.

    Args:
        user: Пользователь.
        dn: Distinguished Name пользователя в LDAP.
    """
    dept_name = extract_department_from_dn(dn)
    if dept_name:
        dept_obj, _ = Department.objects.get_or_create(name=dept_name)
        EmployeeDepartment.objects.filter(
            employee=user, is_active=True
        ).exclude(department=dept_obj).update(is_active=False)
        link, made = EmployeeDepartment.objects.get_or_create(
            employee=user,
            department=dept_obj,
            defaults={"is_active": True},
        )
        if not made and not link.is_active:
            link.is_active = True
            link.save(update_fields=["is_active"])
    else:
        EmployeeDepartment.objects.filter(employee=user, is_active=True).update(
            is_active=False
        )


def get_stale_employee_ids(
    *,
    seen_guids: Set[str],
    seen_dns: Set[str],
) -> list[str]:
    """Находит PK сотрудников, отсутствующих в LDAP (по sync-state).

    Args:
        seen_guids: Множество GUID, найденных в LDAP.
        seen_dns: Множество DN, найденных в LDAP.

    Returns:
        Список PK сотрудников, отсутствующих в LDAP.
    """
    st_qs = LdapSyncState.objects.filter(model="employee")

    stale_states = st_qs
    if seen_guids:
        stale_states = (
            stale_states.exclude(ldap_guid__in=seen_guids)
            .exclude(ldap_guid__isnull=True)
            .exclude(ldap_guid="")
        )
    if seen_dns:
        stale_states = stale_states.exclude(ldap_dn__in=seen_dns).exclude(
            ldap_dn=""
        )

    return list(stale_states.values_list("object_pk", flat=True))


__all__ = [
    "load_users_index",
    "find_user_for_dto",
    "bind_user_department",
    "get_stale_employee_ids",
]
