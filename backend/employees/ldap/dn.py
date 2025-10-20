from __future__ import annotations

from django.conf import settings

from employees.models import Employee, LdapSyncState
from ldap3 import BASE, SUBTREE, Connection

from .utils import esc_filter
from .errors import DirectoryLdapError, DirectoryDbError, DirectoryServiceError


def _ensure_user_dn(conn: Connection, emp: Employee) -> str:
    # 0) валидируем DN из LdapSyncState
    st = (
        LdapSyncState.objects.filter(model="employee", object_pk=str(emp.pk))
        .values("ldap_dn", "ldap_guid")
        .first()
    ) or {}
    state_dn = (st.get("ldap_dn") or "").strip()
    if state_dn:
        conn.search(
            state_dn, "(objectClass=user)", BASE, attributes=["distinguishedName"]
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
            f"(&(objectCategory=person)(objectClass=user)(mail={esc_filter(emp.email)}))"
        )
        filters.append(
            f"(&(objectCategory=person)(objectClass=user)(userPrincipalName={esc_filter(emp.email)}))"
        )
        local = emp.email.split("@", 1)[0]
        if local:
            filters.append(
                f"(&(objectCategory=person)(objectClass=user)(sAMAccountName={esc_filter(local)}))"
            )

    # CN из DN sync-state (если он был)
    if state_dn:
        cn_part = state_dn.split(",", 1)[0]
        if cn_part.upper().startswith("CN="):
            cn_val = cn_part[3:]
            filters.append(
                f"(&(objectCategory=person)(objectClass=user)(cn={esc_filter(cn_val)}))"
            )

    if emp.first_name and emp.last_name:
        filters.append(
            f"(&(objectCategory=person)(objectClass=user)"
            f"(givenName={esc_filter(emp.first_name)})(sn={esc_filter(emp.last_name)}))"
        )
        disp = f"{emp.first_name} {emp.last_name}".strip()
        filters.append(
            f"(&(objectCategory=person)(objectClass=user)(displayName={esc_filter(disp)}))"
        )

    # 3) поиск
    for flt in filters:
        for base in bases:
            if (
                conn.search(base, flt, SUBTREE, attributes=["distinguishedName"])
                and conn.entries
            ):
                return str(conn.entries[0].entry_dn)

    raise RuntimeError(
        f"LDAP DN не найден для employee id={emp.pk}, email={emp.email!r}. "
        "Обновите DN импортом из LDAP или скорректируйте идентификаторы (mail/UPN/sAM/cn)."
    )


def _target_department_ou_dn(dept_name: str) -> str:
    """Строит DN OU отдела: OU=<dept>,<DEPARTMENTS_BASE>."""
    base = getattr(settings, "LDAP_DEPARTMENTS_BASE", "")
    return f"OU={dept_name},{base}"


def _move_to_department(conn: Connection, emp_dn: str, dept: str) -> str:
    # допускаем и имя, и DN

    """Перемещает запись сотрудника в OU отдела с помощью LDAP ModifyDN.

    Алгоритм:
      1) Проверяем существование целевого OU (BASE-search по dept_dn).
      2) Если сотрудник уже под нужным OU — ничего не делаем.
      3) Вызываем modify_dn(dn, relative_dn=<старый RDN>, new_superior=<dept_dn>, delete_old_dn=True).
      4) Возвращаем новый DN ("<старый RDN>,<dept_dn>").

    Args:
        conn: Открытое LDAP-соединение (ldap3.Connection).
        emp_dn: Полный DN сотрудника (например, "CN=John Doe,OU=Users,DC=...").
        dept_dn: Полный DN OU отдела (например, "OU=IT,OU=Departments,DC=...").

    Returns:
        str: Новый DN сотрудника после перемещения.

    Raises:
        DirectoryLdapError: Если OU не найден или операция ModifyDN завершилась ошибкой.
        DirectoryServiceError: Если DN имеет неверный формат.
    """

    dept_dn = (
        dept
        if "=" in dept and dept.upper().startswith("OU=")
        else _target_department_ou_dn(dept)
    )
    print("[DEBUG:_move_to_department] emp_dn =", emp_dn, "dept_dn =", dept_dn)
    # 1) Проверяем, что целевой OU существует
    try:
        ok = conn.search(
            search_base=dept_dn,
            search_filter="(objectClass=organizationalUnit)",
            search_scope=BASE,
            attributes=["distinguishedName"],
        )
        print(
            "[DEBUG:_move_to_department] target OU search ok =",
            ok,
            "entries =",
            len(getattr(conn, "entries", [])),
        )
    except Exception as e:
        print("[ERROR:_move_to_department] target OU lookup failed:", repr(e))
        raise DirectoryLdapError(f"Failed to lookup target OU: {e}") from e

    if not ok or len(getattr(conn, "entries", [])) == 0:
        print("[ERROR:_move_to_department] target OU NOT FOUND:", dept_dn)
        raise DirectoryLdapError(f"Target OU not found: {dept_dn}")

    # 2) Разбираем DN сотрудника на RDN и родителя
    parts = emp_dn.split(",", 1)
    if len(parts) != 2:
        print("[ERROR:_move_to_department] malformed employee DN:", emp_dn)
        raise DirectoryServiceError(f"Malformed DN: {emp_dn}")
    emp_rdn, emp_parent = parts[0], parts[1]
    print("[DEBUG:_move_to_department] emp_rdn =", emp_rdn, "emp_parent =", emp_parent)

    # Уже под нужным OU?
    if emp_parent == dept_dn:
        print("[DEBUG:_move_to_department] already under target OU; skipping modifyDN")
        return emp_dn

    # 3) Делаем перемещение через ModifyDN
    try:
        print("[DEBUG:_move_to_department] issuing modify_dn(...)")
        res = conn.modify_dn(
            dn=emp_dn,
            relative_dn=emp_rdn,  # сохраняем тот же RDN (CN=..., uid=..., etc.)
            delete_old_dn=True,
            new_superior=dept_dn,  # новый родительский контейнер
        )
        print(
            "[DEBUG:_move_to_department] modify_dn returned:",
            res,
            "result:",
            getattr(conn, "result", None),
            "last_error:",
            getattr(conn, "last_error", None),
        )
        if not res:
            # ldap3 кладёт детали в conn.result / conn.last_error
            err = getattr(conn, "last_error", None) or getattr(conn, "result", None)
            raise RuntimeError(err)
    except Exception as e:
        print("[ERROR:_move_to_department] modify_dn failed:", repr(e))
        raise DirectoryLdapError(f"LDAP modifyDN (move) failed: {e}") from e

    # 4) Возвращаем новый DN
    new_dn = f"{emp_rdn},{dept_dn}"
    print("[DEBUG:_move_to_department] new_dn =", new_dn)
    return new_dn
