"""DEPRECATED: Этот модуль сохранён для обратной совместимости.

Используйте вместо него:
    from employees.ldap.services.sync_service import SyncService
    
Функции в этом модуле являются обёртками над новым SyncService.
"""

from __future__ import annotations

import logging
from typing import Iterable, Tuple

from django.conf import settings
from ldap3 import BASE

from ..models import Employee, EmployeeDepartment, LdapSyncState
from .config import SyncConfig
from .infrastructure.connections import _ldap
from .utils.dn_utils import (
    _ensure_user_dn,
    _move_to_department,
    _target_department_ou_dn,
    extract_department_from_dn,
)
from .utils.group_utils import (
    _desired_group_cns_for_employee,
    sync_user_groups_by_cns,
)
from .repositories.ldap_repository import (
    is_taken,
    read_attrs,
    modify_user_attrs,
)

from .utils.ldap_utils import (

    build_logins_for_user,

)
from .utils.image_utils import normalize_avatar_to_jpeg
from .services.sync_service import SyncService

logger = logging.getLogger(__name__)

# Создаём глобальный экземпляр для backward compatibility
_sync_service = SyncService()


# ==================== WRAPPER FUNCTIONS ====================


def import_departments(*, cfg: SyncConfig) -> Tuple[int, int, int]:
    """DEPRECATED: Используйте SyncService().import_departments().

    Импорт OU отделов из LDAP в Django.

    Args:
        cfg: Конфигурация синхронизации.

    Returns:
        Tuple[int, int, int]: (created, updated, deleted).
    """
    return _sync_service.import_departments(cfg)


def import_users(*, cfg: SyncConfig) -> Tuple[int, int, int]:
    """DEPRECATED: Используйте SyncService().import_users().

    Импорт пользователей из LDAP в Django.

    Args:
        cfg: Конфигурация синхронизации.

    Returns:
        Tuple[int, int, int]: (created, updated, deleted).
    """
    return _sync_service.import_users(cfg)


def export_users(*, cfg: SyncConfig) -> Tuple[int, int, int, int, int]:
    """DEPRECATED: Используйте SyncService().export_users().

    Полный экспорт пользователей из Django в LDAP.

    Args:
        cfg: Конфигурация синхронизации.

    Returns:
        Tuple[int, int, int, int, int]: 
            (logins_set, moved, avatars_set, groups_added, groups_removed).
    """
    return _export_users_legacy(cfg=cfg)


def export_users_delete(
    *, cfg: SyncConfig, employees: Iterable[Employee]
) -> int:
    """DEPRECATED: Используйте SyncService().export_users_delete().

    Удаляет учётные записи пользователей в LDAP.

    Args:
        cfg: Конфигурация синхронизации.
        employees: Итератор пользователей для удаления.

    Returns:
        int: Количество успешно удалённых DN.
    """
    return _sync_service.export_users_delete(cfg, employees)


# ==================== LEGACY IMPLEMENTATIONS ====================
# Эти функции сохранены для сложной логики export_users,
# которая ещё не полностью перенесена в новые сервисы


def _employees_with_dn_qs():
    """Возвращает QuerySet сотрудников с LDAP DN."""
    emp_ids = (
        LdapSyncState.objects.filter(model="employee")
        .exclude(ldap_dn="")
        .values_list("object_pk", flat=True)
    )
    return Employee.objects.filter(pk__in=list(emp_ids)).select_related()


def _ensure_and_persist_user_dn(conn, emp, *, do_write):
    """Обеспечивает наличие DN и сохраняет в LdapSyncState."""
    user_dn = _ensure_user_dn(conn, emp)
    if do_write:
        st, _ = LdapSyncState.objects.get_or_create(
            model="employee", object_pk=str(emp.pk)
        )
        if (st.ldap_dn or "") != user_dn:
            st.touch(ldap_dn=user_dn, sync_dir="ldap")
    return user_dn


def _active_dept_name(emp: Employee) -> str | None:
    """Имя активного отдела сотрудника."""
    link = (
        EmployeeDepartment.objects.filter(employee=emp, is_active=True)
        .select_related("department")
        .first()
    )
    return link.department.name if link and link.department_id else None


def export_users_create_attrs(*, cfg: SyncConfig) -> int:
    """Создаёт недостающие sAMAccountName/UPN и базовые ФИО-атрибуты."""
    upn_suffix: str = getattr(settings, "LDAP_UPN_SUFFIX", "robotail.local")
    do_write = not cfg.dry_run
    assigned = 0

    with _ldap() as conn:
        for emp in _employees_with_dn_qs():
            try:
                user_dn = _ensure_and_persist_user_dn(
                    conn, emp, do_write=do_write
                )
            except RuntimeError as e:
                logger.warning("[WARN] %s", e)
                continue

            cur = read_attrs(
                conn, user_dn, ["sAMAccountName", "userPrincipalName"]
            )
            if cur["sAMAccountName"] and cur["userPrincipalName"]:
                continue

            guid = (
                LdapSyncState.objects.filter(
                    model="employee", object_pk=str(emp.pk)
                )
                .values_list("ldap_guid", flat=True)
                .first()
            )

            sam, upn = build_logins_for_user(
                first_name=emp.first_name or "",
                last_name=emp.last_name or "",
                email=emp.email or "",
                upn_suffix=upn_suffix,
                is_taken_sam=lambda s: is_taken(
                    conn, attributes={"sAMAccountName": s}
                ),
                is_taken_upn=lambda u: is_taken(
                    conn, attributes={"userPrincipalName": u}
                ),
                guid=guid,
            )
            modify_user_attrs(
                conn,
                user_dn,
                {
                    "sAMAccountName": sam,
                    "userPrincipalName": upn,
                    "givenName": emp.first_name or None,
                    "sn": emp.last_name or None,
                    "displayName": (
                        f"{emp.first_name} {emp.last_name}".strip() or None
                    ),
                },
                do_write=do_write,
            )
            assigned += 1

    return assigned


def export_users_update_profile(
    *, cfg: SyncConfig
) -> Tuple[int, int]:
    """Обновляет профильные данные: перемещение между отделами и аватары."""
    do_write = not cfg.dry_run
    moved = avatars_set = 0

    with _ldap() as conn:
        for emp in _employees_with_dn_qs():
            try:
                user_dn = _ensure_and_persist_user_dn(
                    conn, emp, do_write=do_write
                )
            except RuntimeError as e:
                logger.warning("[WARN] %s", e)
                continue

            # MOVE между отделами
            current_dept = extract_department_from_dn(user_dn)
            target_dept = _active_dept_name(emp)
            if target_dept and current_dept != target_dept:
                if do_write:
                    _move_to_department(conn, user_dn, target_dept)
                else:
                    target_ou = _target_department_ou_dn(target_dept)
                    if not (
                        conn.search(
                            target_ou,
                            "(objectClass=organizationalUnit)",
                            BASE,
                            attributes=["ou"],
                        )
                        and conn.entries
                    ):
                        logger.warning(
                            "[WARN] Целевой OU не найден: %s", target_ou
                        )
                        continue
                moved += 1

            # avatar -> thumbnailPhoto
            avatar_bytes: bytes | None = None
            avatar_field = getattr(emp, "avatar", None)
            if avatar_field and hasattr(avatar_field, "read"):
                avatar_bytes = avatar_field.read()
            if avatar_bytes:
                try:
                    # Увеличен размер до 384px для максимального качества в LDAP
                    avatar_bytes = normalize_avatar_to_jpeg(
                        avatar_bytes, size_px=384, max_kb=100
                    )
                except Exception as exc:
                    logger.warning(
                        "[WARN] avatar: не удалось нормализовать для %s: %s",
                        user_dn,
                        exc,
                    )
                else:
                    modify_user_attrs(
                        conn,
                        user_dn,
                        {"thumbnailPhoto": avatar_bytes},
                        do_write=do_write,
                    )
                    avatars_set += 1

    return moved, avatars_set


def export_users_sync_groups(*, cfg: SyncConfig) -> Tuple[int, int]:
    """Приводит членства пользователей в LDAP-группах к целевому набору."""
    do_write = not cfg.dry_run
    groups_added = groups_removed = 0

    with _ldap() as conn:
        for emp in _employees_with_dn_qs():
            try:
                user_dn = _ensure_and_persist_user_dn(
                    conn, emp, do_write=do_write
                )
            except RuntimeError as e:
                logger.warning("[WARN] %s", e)
                continue

            current_dept = extract_department_from_dn(user_dn)
            target_dept = _active_dept_name(emp)

            desired_cns = _desired_group_cns_for_employee(emp)

            extra_bases: list[str] = []
            dept_for_roles = target_dept or current_dept
            if dept_for_roles:
                dept_base = getattr(settings, "LDAP_DEPARTMENTS_BASE", "")
                extra_bases.append(f"OU=Roles,OU={dept_for_roles},{dept_base}")

            added, removed = sync_user_groups_by_cns(
                conn,
                user_dn,
                desired_cns,
                extra_bases=extra_bases,
                do_write=do_write,
            )
            groups_added += added
            groups_removed += removed

    return groups_added, groups_removed


def _export_users_legacy(*, cfg: SyncConfig) -> Tuple[int, int, int, int, int]:
    """Legacy реализация export_users через старые функции."""
    from django.utils import timezone

    logins_set = export_users_create_attrs(cfg=cfg)
    moved, avatars_set = export_users_update_profile(cfg=cfg)
    groups_added, groups_removed = export_users_sync_groups(cfg=cfg)

    do_write = not cfg.dry_run
    with _ldap() as conn:
        from django.db import transaction

        with transaction.atomic():
            now = timezone.now()
            for emp in _employees_with_dn_qs().only("pk"):
                try:
                    user_dn = _ensure_and_persist_user_dn(
                        conn, emp, do_write=do_write
                    )
                except RuntimeError as e:
                    logger.warning("[WARN] state.touch пропущен: %s", e)
                    continue
                state, _ = LdapSyncState.objects.get_or_create(
                    model="employee", object_pk=str(emp.pk)
                )
                state.touch(
                    ldap_dn=user_dn,
                    last_django_modify_ts=now,
                    sync_dir="django",
                )

    return logins_set, moved, avatars_set, groups_added, groups_removed
