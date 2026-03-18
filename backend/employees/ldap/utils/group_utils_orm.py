"""ORM-версии утилит для работы с группами LDAP через django-ldapdb.

Замена низкоуровневых ldap3 операций для управления memberOf.
"""

from __future__ import annotations

import logging
from typing import Iterable, Optional, Set

from django.conf import settings

from employees.models import Employee
from ..orm_models import LdapUser, LdapGroup
from .text_utils import esc_filter

logger = logging.getLogger(__name__)


def read_user_memberof_dns(user_dn: str) -> set[str]:
    """Возвращает множество DN групп (memberOf) пользователя через ORM."""
    try:
        user = LdapUser.objects.get(dn=user_dn)
        return set(user.member_of or [])
    except LdapUser.DoesNotExist:
        return set()


def group_add_member_orm(group_dn: str, member_dn: str) -> None:
    """Добавляет пользователя в группу через ORM."""
    try:
        group = LdapGroup.objects.get(dn=group_dn)
    except LdapGroup.DoesNotExist:
        raise ValueError(f"LDAP group not found: {group_dn}")
    
    members = list(group.member or [])
    if member_dn not in members:
        members.append(member_dn)
        group.member = members
        group.save()


def group_remove_member_orm(group_dn: str, member_dn: str) -> None:
    """Удаляет пользователя из группы через ORM."""
    try:
        group = LdapGroup.objects.get(dn=group_dn)
    except LdapGroup.DoesNotExist:
        raise ValueError(f"LDAP group not found: {group_dn}")
    
    members = list(group.member or [])
    if member_dn in members:
        members.remove(member_dn)
        group.member = members
        group.save()


def resolve_group_dns_by_cn_orm(cns: set[str]) -> dict[str, str]:
    """Ищет DN групп по их CN через ORM."""
    if not cns:
        return {}
    found: dict[str, str] = {}
    for cn in sorted(cns):
        try:
            group = LdapGroup.objects.get(cn=cn)
            found[cn] = group.dn
        except LdapGroup.DoesNotExist:
            continue
    return found


def sync_user_groups_by_cns_orm(
    user_dn: str,
    target_cns: Iterable[str],
    *,
    do_write: bool = True,
) -> tuple[int, int]:
    """Приводит memberOf пользователя к набору CN через ORM.

    Args:
        user_dn: DN пользователя.
        target_cns: итоговый набор CN групп.
        do_write: False => только расчёт.

    Returns:
        (added, removed).
    """
    desired_dns = set(resolve_group_dns_by_cn_orm(set(target_cns)).values())
    current_dns = read_user_memberof_dns(user_dn)

    groups_base = getattr(settings, "LDAP_GROUPS_BASE", "")
    depts_base = getattr(settings, "LDAP_DEPARTMENTS_BASE", "")

    to_add = desired_dns - current_dns
    to_del = {
        dn
        for dn in (current_dns - desired_dns)
        if (groups_base and dn.endswith(groups_base)) 
           or (depts_base and dn.endswith(depts_base) and "CN=ROLE_" in dn)
    }

    added = removed = 0
    if do_write:
        for gdn in sorted(to_add):
            group_add_member_orm(gdn, user_dn)
            added += 1
        for gdn in sorted(to_del):
            group_remove_member_orm(gdn, user_dn)
            removed += 1
    else:
        added, removed = len(to_add), len(to_del)
    return added, removed


def _desired_group_cns_for_employee(emp: "Employee") -> set[str]:
    """Возвращает целевые CN групп для сотрудника из Django (Position/DeptRole/Direct)."""
    cns: set[str] = set()
    pos = getattr(emp, "position", None)
    if pos is not None and hasattr(pos, "groups"):
        cns |= {g.name for g in pos.groups.all()}
    user_obj = getattr(emp, "user", None) or emp
    if hasattr(user_obj, "groups"):
        cns |= {g.name for g in user_obj.groups.all()}
    dept_roles = getattr(emp, "department_roles", None)
    if dept_roles is not None and hasattr(dept_roles, "all"):
        for dr in dept_roles.all():
            if hasattr(dr, "groups"):
                cns |= {g.name for g in dr.groups.all()}
    return cns


__all__ = [
    'read_user_memberof_dns',
    'group_add_member_orm',
    'group_remove_member_orm',
    'resolve_group_dns_by_cn_orm',
    'sync_user_groups_by_cns_orm',
    '_desired_group_cns_for_employee',
]
