"""Утилиты для работы с Distinguished Names (DN).

Функции для парсинга, преобразования и манипуляций с LDAP Distinguished Names.
"""

from __future__ import annotations

from typing import Optional, Sequence

from django.conf import settings
from ldap3 import BASE, SUBTREE, Connection

from ..errors import DirectoryLdapError, DirectoryServiceError
from employees.models import Employee, LdapSyncState


def extract_department_from_dn(
    dn: str, *, departments_anchor: str = "OU=Departments"
) -> Optional[str]:
    """Возвращает имя отдела из DN при контейнерной модели.

    Ищет сегмент OU=Departments и берёт OU слева от него как название отдела.

    Args:
        dn (str): Distinguished Name пользователя.
        departments_anchor (str): Маркер корневого OU отделов.

    Returns:
        Optional[str]: Имя отдела или None, если пользователь не под
            OU=Departments.

    Raises:
        TypeError: Если dn не строка.
        ValueError: Если dn пустой.
    """
    if not isinstance(dn, str):
        raise TypeError("dn должен быть строкой")
    dn = dn.strip()
    if not dn:
        raise ValueError("пустой DN")

    parts: Sequence[str] = [p.strip() for p in dn.split(",") if p.strip()]
    # точное совпадение полного сегмента
    try:
        idx = parts.index(departments_anchor)
    except ValueError:
        # fallback: искать просто 'OU=Departments' без хвоста
        try:
            idx = next(
                i
                for i, p in enumerate(parts)
                if p.strip().lower() == "ou=departments"
            )
        except StopIteration:
            return None

    dept_idx = idx - 1
    if dept_idx < 0 or not parts[dept_idx].startswith("OU="):
        return None
    value = parts[dept_idx][3:].strip()
    return value or None


def rewrite_dn_suffix(dn: str, old_suffix: str, new_suffix: str) -> str:
    """Заменяет хвост DN c old_suffix на new_suffix.

    Args:
        dn (str): Distinguished Name.
        old_suffix (str): Старый суффикс (например, "DC=old,DC=com").
        new_suffix (str): Новый суффикс (например, "DC=new,DC=com").

    Returns:
        str: DN с новым суффиксом или исходный DN, если не найдено совпадение.
    """
    if not dn or not dn.lower().endswith(old_suffix.lower()):
        return dn
    return dn[: -len(old_suffix)] + new_suffix


def _target_department_ou_dn(dept_name: str) -> str:
    """Строит DN OU отдела: OU=<dept>,<DEPARTMENTS_BASE>.

    Args:
        dept_name (str): Имя отдела.

    Returns:
        str: Полный DN отдела.
    """
    base = getattr(settings, "LDAP_DEPARTMENTS_BASE", "")
    return f"OU={dept_name},{base}"


def _ensure_user_dn(conn: Connection, emp: Employee) -> str:
    """Находит DN пользователя в LDAP по различным идентификаторам.

    Алгоритм:
        1) Проверяет DN из LdapSyncState
        2) Ищет по email, UPN, sAMAccountName
        3) Ищет по givenName+sn, displayName

    Args:
        conn (Connection): LDAP-соединение.
        emp (Employee): Объект сотрудника Django.

    Returns:
        str: DN пользователя в LDAP.

    Raises:
        RuntimeError: Если DN не найден.
    """
    from .text_utils import esc_filter

    # 0) валидируем DN из LdapSyncState
    st = (
        LdapSyncState.objects.filter(model="employee", object_pk=str(emp.pk))
        .values("ldap_dn", "ldap_guid")
        .first()
    ) or {}
    state_dn = (st.get("ldap_dn") or "").strip()
    if state_dn:
        conn.search(
            state_dn,
            "(objectClass=user)",
            BASE,
            attributes=["distinguishedName"],
        )
        if conn.entries:
            return state_dn

    # 1) собираем базы
    bases: list[str] = []
    for key in ("LDAP_USERS_BASE", "LDAP_DEPARTMENTS_BASE", "LDAP_BASE_DN"):
        val = getattr(settings, key, "")
        if val and val not in bases:
            bases.append(val)

    # 2) строим фильтры (mail, upn, sam, cn из state_dn, given+sn, displayName)
    filters: list[str] = []
    if emp.email:
        filters.append(
            f"(&(objectCategory=person)(objectClass=user)"
            f"(mail={esc_filter(emp.email)}))"
        )
        filters.append(
            f"(&(objectCategory=person)(objectClass=user)"
            f"(userPrincipalName={esc_filter(emp.email)}))"
        )
        local = emp.email.split("@", 1)[0]
        if local:
            filters.append(
                f"(&(objectCategory=person)(objectClass=user)"
                f"(sAMAccountName={esc_filter(local)}))"
            )

    # CN из DN sync-state (если он был)
    if state_dn:
        cn_part = state_dn.split(",", 1)[0]
        if cn_part.upper().startswith("CN="):
            cn_val = cn_part[3:]
            filters.append(
                f"(&(objectCategory=person)(objectClass=user)"
                f"(cn={esc_filter(cn_val)}))"
            )

    if emp.first_name and emp.last_name:
        filters.append(
            f"(&(objectCategory=person)(objectClass=user)"
            f"(givenName={esc_filter(emp.first_name)})"
            f"(sn={esc_filter(emp.last_name)}))"
        )
        disp = f"{emp.first_name} {emp.last_name}".strip()
        filters.append(
            f"(&(objectCategory=person)(objectClass=user)"
            f"(displayName={esc_filter(disp)}))"
        )

    # 3) поиск
    for flt in filters:
        for base in bases:
            if (
                conn.search(
                    base, flt, SUBTREE, attributes=["distinguishedName"]
                )
                and conn.entries
            ):
                return str(conn.entries[0].entry_dn)

    raise RuntimeError(
        f"LDAP DN не найден для employee id={emp.pk}, email={emp.email!r}. "
        "Обновите DN импортом из LDAP или скорректируйте идентификаторы "
        "(mail/UPN/sAM/cn)."
    )


def _move_to_department(conn: Connection, emp_dn: str, dept: str) -> str:
    """Перемещает запись сотрудника в OU отдела с помощью LDAP ModifyDN.

    Алгоритм:
      1) Проверяем существование целевого OU (BASE-search по dept_dn).
      2) Если сотрудник уже под нужным OU — ничего не делаем.
      3) Вызываем modify_dn(dn, relative_dn=<старый RDN>,
         new_superior=<dept_dn>, delete_old_dn=True).
      4) Возвращаем новый DN ("<старый RDN>,<dept_dn>").

    Args:
        conn: Открытое LDAP-соединение (ldap3.Connection).
        emp_dn: Полный DN сотрудника (например,
            "CN=John Doe,OU=Users,DC=...").
        dept: Имя отдела или полный DN OU отдела (например,
            "OU=IT,OU=Departments,DC=...").

    Returns:
        str: Новый DN сотрудника после перемещения.

    Raises:
        DirectoryLdapError: Если OU не найден или операция ModifyDN
            завершилась ошибкой.
        DirectoryServiceError: Если DN имеет неверный формат.
    """
    dept_dn = (
        dept
        if "=" in dept and dept.upper().startswith("OU=")
        else _target_department_ou_dn(dept)
    )

    # 1) Проверяем, что целевой OU существует
    try:
        ok = conn.search(
            search_base=dept_dn,
            search_filter="(objectClass=organizationalUnit)",
            search_scope=BASE,
            attributes=["distinguishedName"],
        )
    except Exception as e:
        raise DirectoryLdapError(f"Failed to lookup target OU: {e}") from e

    if not ok or len(getattr(conn, "entries", [])) == 0:
        raise DirectoryLdapError(f"Target OU not found: {dept_dn}")

    # 2) Разбираем DN сотрудника на RDN и родителя
    parts = emp_dn.split(",", 1)
    if len(parts) != 2:
        raise DirectoryServiceError(f"Malformed DN: {emp_dn}")
    emp_rdn, emp_parent = parts[0], parts[1]

    # Уже под нужным OU?
    if emp_parent == dept_dn:
        return emp_dn

    # 3) Делаем перемещение через ModifyDN
    try:
        res = conn.modify_dn(
            dn=emp_dn,
            relative_dn=emp_rdn,
            delete_old_dn=True,
            new_superior=dept_dn,
        )
        if not res:
            err = getattr(conn, "last_error", None) or getattr(
                conn, "result", None
            )
            raise RuntimeError(err)
    except Exception as e:
        raise DirectoryLdapError(f"LDAP modifyDN (move) failed: {e}") from e

    # 4) Возвращаем новый DN
    new_dn = f"{emp_rdn},{dept_dn}"
    return new_dn


__all__ = [
    "extract_department_from_dn",
    "rewrite_dn_suffix",
    "_target_department_ou_dn",
    "_ensure_user_dn",
    "_move_to_department",
]
