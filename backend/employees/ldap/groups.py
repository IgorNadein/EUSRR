from __future__ import annotations

from typing import Iterable, Optional

from django.conf import settings
from ldap3 import BASE, SUBTREE, Connection

from ..models import Employee
from .utils import esc_filter


def _read_user_memberof_dns(conn: Connection, user_dn: str) -> set[str]:
    """Возвращает текущее множество DN групп (memberOf) пользователя."""
    conn.search(user_dn, "(objectClass=*)", BASE, attributes=["memberOf"])
    if not conn.entries:
        return set()
    raw = getattr(conn.entries[0], "memberOf", [])
    vals = raw.values if hasattr(raw, "values") else raw
    return {str(x) for x in (vals or [])}


def _group_add_member(
    conn: Connection, group_dn: str, user_dn: str, *, do_write: bool
) -> None:
    """Добавляет пользователя в группу (или пропускает в dry-run)."""
    from ldap3 import MODIFY_ADD

    if not do_write:
        return
    ok = conn.modify(group_dn, {"member": [(MODIFY_ADD, [user_dn])]})
    if not ok and conn.result.get("description") not in {"typeOrValueExists"}:
        raise RuntimeError(f"Add member failed: {group_dn}: {conn.result}")


def _group_remove_member(
    conn: Connection, group_dn: str, user_dn: str, *, do_write: bool
) -> None:
    """Удаляет пользователя из группы (или пропускает в dry-run)."""
    from ldap3 import MODIFY_DELETE

    if not do_write:
        return
    ok = conn.modify(group_dn, {"member": [(MODIFY_DELETE, [user_dn])]})
    if not ok and conn.result.get("description") not in {"noSuchAttribute"}:
        raise RuntimeError(f"Remove member failed: {group_dn}: {conn.result}")


def _resolve_group_dns_by_cn(
    conn: Connection, cns: set[str], extra_bases: Optional[list[str]] = None
) -> dict[str, str]:
    """Ищет DN групп по их CN в OU=Groups и дополнительных базах (например, Roles отдела)."""
    if not cns:
        return {}
    bases = [getattr(settings, "LDAP_GROUPS_BASE", "")]
    if extra_bases:
        bases.extend(extra_bases)
    found: dict[str, str] = {}
    for base in bases:
        if not base:
            continue
        for cn in sorted(cns - set(found.keys())):
            conn.search(
                base,
                f"(&(objectClass=group)(cn={esc_filter(cn)}))",
                SUBTREE,
                attributes=["distinguishedName", "cn"],
            )
            if conn.entries:
                found[cn] = str(conn.entries[0].entry_dn)
    return found


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


def sync_user_groups_by_cns(
    conn: Connection,
    user_dn: str,
    target_cns: Iterable[str],
    *,
    extra_bases: list[str] | None = None,
    do_write: bool = True,
) -> tuple[int, int]:
    """Приводит memberOf пользователя к точному набору CN (добавляет/удаляет).

    Args:
        conn: соединение LDAP.
        user_dn: DN пользователя.
        target_cns: итоговый набор CN групп.
        extra_bases: доп. базы поиска групп (например, OU=Roles,<dept>).
        do_write: False => только расчёт.

    Returns:
        (added, removed).

    Raises:
        RuntimeError: если операции LDAP завершаются ошибкой.
    """
    desired_dns = set(
        _resolve_group_dns_by_cn(
            conn, set(target_cns), extra_bases=extra_bases
        ).values()
    )
    current_dns = _read_user_memberof_dns(conn, user_dn)

    # ограничим удаление только «наших» веток (Groups/OU=Roles),
    # как и в батч-логике
    groups_base = getattr(settings, "LDAP_GROUPS_BASE", "")
    to_add = desired_dns - current_dns
    to_del = {
        dn
        for dn in (current_dns - desired_dns)
        if (groups_base and dn.endswith(groups_base)) or "OU=Roles," in dn
    }

    added = removed = 0
    if do_write:
        for gdn in sorted(to_add):
            _group_add_member(conn, gdn, user_dn, do_write=True)
            added += 1
        for gdn in sorted(to_del):
            _group_remove_member(conn, gdn, user_dn, do_write=True)
            removed += 1
    else:
        added, removed = len(to_add), len(to_del)
    return added, removed
