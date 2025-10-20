from __future__ import annotations

import logging
from typing import Iterable, List, Optional, Set, Tuple

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from ldap3 import BASE, Connection

from ..models import Department, Employee, EmployeeDepartment, LdapSyncState
from .config import SyncConfig
from .connections import _ldap
from .dn import _ensure_user_dn, _move_to_department, _target_department_ou_dn
from .dto import LdapPersonDTO, _entry_to_dto
from .groups import _desired_group_cns_for_employee, sync_user_groups_by_cns
from .helpers import is_taken, read_attrs, modify_user_attrs
from .repo_db import (
    _bind_user_department,
    _cleanup_absent_users,
    _find_user_for_dto,
    _load_existing_users_index,
    _touch_sync_state,
)
from .utils import (
    _paged_search,
    build_logins_for_user,
    extract_department_from_dn,
    get_attr_str,
    normalize_avatar_to_jpeg,
)

logger = logging.getLogger(__name__)


# ------------------------- ВСПОМОГАТЕЛЬНАЯ ИНФРАСТРУКТУРА ------------------------- #


def _employees_with_dn_qs():
    emp_ids = (
        LdapSyncState.objects.filter(model="employee")
        .exclude(ldap_dn="")
        .values_list("object_pk", flat=True)
    )
    return Employee.objects.filter(pk__in=list(emp_ids)).select_related()


def _ensure_and_persist_user_dn(conn, emp, *, do_write):
    user_dn = _ensure_user_dn(conn, emp)
    if do_write:
        st, _ = LdapSyncState.objects.get_or_create(
            model="employee", object_pk=str(emp.pk)
        )
        if (st.ldap_dn or "") != user_dn:
            st.touch(ldap_dn=user_dn, sync_dir="ldap")
    return user_dn


def _validate_bases(*, cfg: SyncConfig) -> Tuple[str, str]:
    """Возвращает пары базовых DN для пользователей и отделов, валидирует наличие.

    Args:
        cfg (SyncConfig): Конфигурация синхронизации.

    Returns:
        Tuple[str, str]: (base_users, base_deps).

    Raises:
        RuntimeError: Если не заданы базовые DN.
    """
    base_users = (cfg.users_base_dn or getattr(settings, "LDAP_USERS_BASE", "")).strip()
    base_deps = (
        cfg.departments_base_dn or getattr(settings, "LDAP_DEPARTMENTS_BASE", "")
    ).strip()
    if not (base_users and base_deps):
        raise RuntimeError("LDAP_USERS_BASE/LDAP_DEPARTMENTS_BASE не заданы.")
    return base_users, base_deps


def _collect_ldap_entries(conn: Connection, base_users: str, base_deps: str) -> List:
    """Читает все записи user из OU пользователей и OU отделов.

    Args:
        conn (Connection): Readonly-подключение.
        base_users (str): База пользователей.
        base_deps (str): База отделов.

    Returns:
        List: Список ldap3 entries.
    """
    flt = "(&(objectCategory=person)(objectClass=user))"
    return _paged_search(conn, base_users, flt) + _paged_search(conn, base_deps, flt)


# ----------------------------- IMPORT: DEPARTMENTS ----------------------------- #


def import_departments(*, cfg: SyncConfig) -> tuple[int, int, int]:
    """Импорт OU отделов из LDAP в Django в режиме «зеркала» (пропуская корневой контейнер).

    Args:
        cfg (SyncConfig): Конфигурация синхронизации.

    Returns:
        tuple[int, int, int]: (created, updated, deleted).

    Raises:
        RuntimeError: Если не задана база отделов.
    """
    raw_base = cfg.departments_base_dn or getattr(settings, "LDAP_DEPARTMENTS_BASE", "")
    base = raw_base.strip().strip('"').strip("'")
    created_names: list[str] = []
    updated_heads: list[tuple[str, str]] = []  # (dept, head_email/ID)
    deleted_names: list[str] = []
    if not base:
        raise RuntimeError("departments_base_dn не задан.")

    with _ldap() as conn, transaction.atomic():
        entries = _paged_search(conn, base, "(objectClass=organizationalUnit)")
        base_dn_lower = base.lower()
        root_ou_name = (
            base.split(",", 1)[0][3:].strip()
            if base.upper().startswith("OU=")
            else None
        )

        created = updated = deleted = 0
        seen_names: set[str] = set()

        for e in entries:
            a = getattr(e, "entry_attributes_as_dict", {}) or {}
            dn: str = str(getattr(e, "entry_dn", "")) or get_attr_str(
                a, "distinguishedName"
            )
            dn = (dn or "").strip()
            if not dn or dn.lower() == base_dn_lower:
                continue

            name: str = (get_attr_str(a, "ou") or get_attr_str(a, "name")).strip()
            if not name:
                continue
            # Страховка от совпадения имени с корневым OU
            if (
                root_ou_name
                and name.lower() == root_ou_name.lower()
                and dn.lower() != base_dn_lower
            ):
                pass

            seen_names.add(name)
            dept, was_created = Department.objects.get_or_create(name=name)
            if was_created:
                created += 1
                if cfg.show_changes:
                    print(f"[CHG] + Dept: {name}  DN={dn}")

            head_dn: str = get_attr_str(a, "managedBy")
            head_obj = None
            if head_dn:
                head_pk = (
                    LdapSyncState.objects.filter(
                        model="employee", ldap_dn__iexact=head_dn
                    )
                    .values_list("object_pk", flat=True)
                    .first()
                )
                if head_pk:
                    head_obj = Employee.objects.filter(pk=head_pk).first()

            if head_obj and getattr(dept, "head_id", None) != head_obj.id:
                if not cfg.dry_run:
                    dept.head = head_obj
                    if hasattr(dept, "head_appointed_at"):
                        dept.head_appointed_at = timezone.now()
                        dept.save(update_fields=["head", "head_appointed_at"])
                    else:
                        dept.save(update_fields=["head"])
                updated += 1
                if cfg.show_changes:
                    who = head_obj.email or f"id={head_obj.id}"
                    print(f"[CHG] ~ Dept head: {name} -> {who}")

            state, _ = LdapSyncState.objects.get_or_create(
                model="department", object_pk=str(dept.pk)
            )
            state.touch(
                ldap_dn=dn,
                last_ldap_modify_ts=None,
                last_django_modify_ts=timezone.now(),
                sync_dir="ldap",
            )

        to_delete_qs = Department.objects.exclude(name__in=seen_names)
        if cfg.show_changes:
            deleted_names = list(to_delete_qs.values_list("name", flat=True))
            for n in deleted_names:
                verb = "будет удалён" if cfg.dry_run else "удалён"
                print(f"[CHG] - Dept: {n} ({verb})")
        deleted_count = to_delete_qs.count()
        if cfg.dry_run:
            deleted = deleted_count
        else:
            Department.objects.filter(
                pk__in=to_delete_qs.values_list("pk", flat=True)
            ).update(head=None)
            to_delete_qs.delete()
            LdapSyncState.objects.filter(model="department").exclude(
                object_pk__in=Department.objects.values_list("pk", flat=True)
            ).delete()
            deleted = deleted_count

        return created, updated, deleted


# ----------------------------- IMPORT: USERS ----------------------------- #


def _create_user_from_dto(dto: LdapPersonDTO) -> Optional[Employee]:
    """Создаёт нового Employee по данным из LDAP с подготовкой контактов.

    Args:
        dto (LdapPersonDTO): Нормализованные данные из LDAP.

    Returns:
        Optional[Employee]: Созданный пользователь или None (если пропущен из-за валидации).

    Raises:
        django.db.DatabaseError: Ошибки сохранения в БД.
    """
    if not dto.phone_e164:
        logger.warning(
            "LDAP import: skip create for DN=%s, email=%s — no valid phone to satisfy model.clean()",
            dto.dn,
            dto.email,
        )
        return None

    user = Employee(
        email=dto.email,
        first_name=dto.given,
        last_name=dto.sn,
        is_active=dto.is_active,
        is_ldap_managed=True,
    )
    # Контакты
    user.phone_number = dto.phone_e164
    if not (
        getattr(user, "whatsapp", None)
        or getattr(user, "telegram", None)
        or getattr(user, "wechat", None)
    ):
        user.whatsapp = dto.phone_e164

    try:
        user.full_clean(exclude=["password"])
    except ValidationError as exc:
        logger.warning(
            "LDAP import: skip create for DN=%s, email=%s — %s", dto.dn, dto.email, exc
        )
        return None

    user.save()
    return user


def _update_user_from_dto(user: Employee, dto: LdapPersonDTO) -> Employee:
    changed = False
    for field, val in (
        ("email", dto.email),
        ("first_name", dto.given),
        ("last_name", dto.sn),
        ("is_active", dto.is_active),
    ):
        if val is not None and getattr(user, field) != val:
            setattr(user, field, val)
            changed = True

    if dto.phone_e164:
        if user.phone_number != dto.phone_e164:
            user.phone_number = dto.phone_e164
            changed = True
        if not (user.whatsapp or user.telegram or user.wechat):
            user.whatsapp = dto.phone_e164
            changed = True

    if not user.is_ldap_managed:
        user.is_ldap_managed = True
        changed = True

    if changed:
        user.save()
    return user


def import_users(*, cfg: SyncConfig) -> tuple[int, int, int]:
    """Импорт пользователей из LDAP в Django в «зеркальном» режиме.

    Этапы:
        1) Чтение/нормализация LDAP → DTO.
        2) Разделение на update/create и применение в БД.
        3) Привязка к отделам.
        4) Фиксация состояния синхронизации.
        5) Очистка отсутствующих.

    Args:
        cfg (SyncConfig): Конфиг синхронизации.

    Returns:
        tuple[int, int, int]: (created, updated, deleted).
    """
    base_users, base_deps = _validate_bases(cfg=cfg)

    with _ldap() as conn, transaction.atomic():
        entries = _collect_ldap_entries(conn, base_users, base_deps)

        seen_guids: Set[str] = set()
        seen_dns: Set[str] = set()
        dtos: List[LdapPersonDTO] = []
        for e in entries:
            dto = _entry_to_dto(e)
            if dto.dn:
                seen_dns.add(dto.dn)
            if dto.guid:
                seen_guids.add(dto.guid)
            dtos.append(dto)

        by_guid, by_email = _load_existing_users_index(dtos)
        to_create: List[LdapPersonDTO] = []
        to_update: List[Tuple[Employee, LdapPersonDTO]] = []

        for dto in dtos:
            existing = _find_user_for_dto(dto, by_guid=by_guid, by_email=by_email)
            (to_update if existing else to_create).append(
                (existing, dto) if existing else dto
            )

        created = updated = skipped = 0
        processed: List[Tuple[Employee, LdapPersonDTO]] = []

        # UPDATE
        for user, dto in to_update:
            processed.append((_update_user_from_dto(user, dto), dto))
            updated += 1

        # CREATE
        for dto in to_create:
            user = _create_user_from_dto(dto)
            if not user:
                skipped += 1
                continue
            processed.append((user, dto))
            created += 1

        if cfg.show_changes:
            for dto in to_create:
                print(f"[CHG] + User: {dto.email or '(no email)'}  DN={dto.dn}")
            for existing, dto in to_update:
                print(f"[CHG] ~ User: {existing.email}  DN={dto.dn}")

        if skipped:
            logger.warning(
                "[LDAP] Пропущено записей из-за валидации/контактов: %s", skipped
            )

        # Bind departments + sync state
        for user, dto in processed:
            _bind_user_department(user, dto.dn)
            _touch_sync_state(
                user,
                dn=dto.dn,
                guid=dto.guid,
                last_ldap_modify_ts=dto.when_changed,
                sync_dir="ldap",
                dry_run=cfg.dry_run,
            )

        deleted = _cleanup_absent_users(
            seen_guids=seen_guids, seen_dns=seen_dns, dry_run=cfg.dry_run, show_changes=cfg.show_changes
        )

    return created, updated, deleted


# ----------------------------- EXPORT: LOGINS/UPN ----------------------------- #


def export_users_create_attrs(*, cfg: SyncConfig) -> int:
    """Создаёт недостающие sAMAccountName/UPN и базовые ФИО-атрибуты.

    Args:
        cfg (SyncConfig): Конфиг (используется `dry_run` и `settings.LDAP_UPN_SUFFIX`).

    Returns:
        int: Кол-во пользователей, для которых были выставлены логины/UPN.
    """
    upn_suffix: str = getattr(settings, "LDAP_UPN_SUFFIX", "robotail.local")
    do_write = not cfg.dry_run
    assigned = 0

    with _ldap() as conn:
        for emp in _employees_with_dn_qs():
            try:
                user_dn = _ensure_and_persist_user_dn(conn, emp, do_write=do_write)
            except RuntimeError as e:
                logger.warning("[WARN] %s", e)
                continue

            cur = read_attrs(conn, user_dn, ["sAMAccountName", "userPrincipalName"])
            if cur["sAMAccountName"] and cur["userPrincipalName"]:
                continue

            guid = (
                LdapSyncState.objects.filter(model="employee", object_pk=str(emp.pk))
                .values_list("ldap_guid", flat=True)
                .first()
            )

            sam, upn = build_logins_for_user(
                first_name=emp.first_name or "",
                last_name=emp.last_name or "",
                email=emp.email or "",
                upn_suffix=upn_suffix,
                is_taken_sam=lambda s: is_taken(conn, attributes={"sAMAccountName": s}),
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
                    "displayName": f"{emp.first_name} {emp.last_name}".strip() or None,
                },
                do_write=do_write,
            )
            assigned += 1

    return assigned


# ----------------------------- EXPORT: PROFILE (MOVE + AVATAR) ----------------------------- #


def _active_dept_name(emp: Employee) -> Optional[str]:
    """Имя активного отдела сотрудника по таблице связей.

    Args:
        emp (Employee): Сотрудник.

    Returns:
        Optional[str]: Название отдела или None.
    """
    link = (
        EmployeeDepartment.objects.filter(employee=emp, is_active=True)
        .select_related("department")
        .first()
    )
    return link.department.name if link and link.department_id else None


def export_users_update_profile(*, cfg: SyncConfig) -> Tuple[int, int]:
    """Обновляет профильные данные пользователей: перемещение между отделами и аватары.

    Args:
        cfg (SyncConfig): Конфиг (используется `dry_run`).

    Returns:
        Tuple[int, int]: (moved, avatars_set).
    """
    do_write = not cfg.dry_run
    moved = avatars_set = 0

    with _ldap() as conn:
        for emp in _employees_with_dn_qs():
            try:
                user_dn = _ensure_and_persist_user_dn(conn, emp, do_write=do_write)
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
                            "[WARN] Целевой OU отдела не найден: %s", target_ou
                        )
                        continue  # не считаем такой MOVE
                moved += 1

            # avatar -> thumbnailPhoto
            avatar_bytes: Optional[bytes] = None
            avatar_field = getattr(emp, "avatar", None)
            if avatar_field and hasattr(avatar_field, "read"):
                avatar_bytes = avatar_field.read()
            if avatar_bytes:
                try:
                    avatar_bytes = normalize_avatar_to_jpeg(avatar_bytes)
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


# ----------------------------- EXPORT: GROUPS SYNC ----------------------------- #


def export_users_sync_groups(*, cfg: SyncConfig) -> Tuple[int, int]:
    """Приводит членства пользователей в LDAP-группах к целевому набору.

    Args:
        cfg (SyncConfig): Конфиг синхронизации.

    Returns:
        Tuple[int, int]: (groups_added, groups_removed).
    """
    do_write = not cfg.dry_run
    groups_added = groups_removed = 0

    with _ldap() as conn:
        for emp in _employees_with_dn_qs():
            try:
                user_dn = _ensure_and_persist_user_dn(conn, emp, do_write=do_write)
            except RuntimeError as e:
                logger.warning("[WARN] %s", e)
                continue

            current_dept = extract_department_from_dn(user_dn)
            target_dept = _active_dept_name(emp)

            desired_cns = _desired_group_cns_for_employee(emp)

            extra_bases: list[str] = []
            dept_for_roles = target_dept or current_dept
            if dept_for_roles:
                extra_bases.append(
                    f"OU=Roles,OU={dept_for_roles},{getattr(settings, 'LDAP_DEPARTMENTS_BASE', '')}"
                )

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


# ----------------------------- EXPORT: DELETE ACCOUNTS ----------------------------- #


def _ldap_delete_dn(conn: Connection, dn: str, *, do_write: bool) -> None:
    """Удаляет объект по DN в LDAP.

    Args:
        conn (Connection): RW-подключение.
        dn (str): DN удаляемого объекта.
        do_write (bool): Если False — noop.

    Raises:
        RuntimeError: Если сервер вернул ошибку удаления.
    """
    if not do_write:
        return
    if not conn.delete(dn):
        raise RuntimeError(f"LDAP delete failed for {dn}: {conn.result}")


def export_users_delete(*, cfg: SyncConfig, employees: Iterable[Employee]) -> int:
    """Удаляет учётные записи пользователей в LDAP по их DN.

    ⚠️ Передайте конкретный набор `employees` (уволенные и т.п.).

    Args:
        cfg (SyncConfig): Конфиг (`dry_run`).
        employees (Iterable[Employee]): Кого удалять.

    Returns:
        int: Количество успешно удалённых DN (включая dry-run).
    """
    do_write = not cfg.dry_run
    deleted = 0

    with _ldap() as conn:
        for emp in employees:
            state_dn = (
                LdapSyncState.objects.filter(model="employee", object_pk=str(emp.pk))
                .values_list("ldap_dn", flat=True)
                .first()
            )
            user_dn = (state_dn or "").strip()
            if not user_dn:
                logger.warning(
                    "[WARN] Пропуск удаления: у сотрудника pk=%s пустой ldap_dn", emp.pk
                )
                continue
            if not (
                conn.search(user_dn, "(objectClass=*)", BASE, attributes=["dn"])
                and conn.entries
            ):
                logger.warning("[WARN] DN не найден в LDAP, пропуск: %s", user_dn)
                continue
            _ldap_delete_dn(conn, user_dn, do_write=do_write)
            deleted += 1

    return deleted


# ----------------------------- ОРКЕСТРАТОР: ПОЛНАЯ СИНХРОНИЗАЦИЯ ----------------------------- #


def export_users(*, cfg: SyncConfig) -> tuple[int, int, int, int, int]:
    """Полный экспорт пользователей из Django в LDAP (логины/UPN, MOVE, avatar, группы) + фиксация LdapSyncState.

    Args:
        cfg (SyncConfig): Конфиг синхронизации.

    Returns:
        tuple[int, int, int, int, int]: (logins_set, moved, avatars_set, groups_added, groups_removed).
    """
    logins_set = export_users_create_attrs(cfg=cfg)
    moved, avatars_set = export_users_update_profile(cfg=cfg)
    groups_added, groups_removed = export_users_sync_groups(cfg=cfg)

    do_write = not cfg.dry_run
    with _ldap() as conn, transaction.atomic():
        now = timezone.now()
        for emp in _employees_with_dn_qs().only("pk"):
            try:
                user_dn = _ensure_and_persist_user_dn(conn, emp, do_write=do_write)
            except RuntimeError as e:
                logger.warning("[WARN] state.touch пропущен: %s", e)
                continue
            state, _ = LdapSyncState.objects.get_or_create(
                model="employee", object_pk=str(emp.pk)
            )
            state.touch(ldap_dn=user_dn, last_django_modify_ts=now, sync_dir="django")

    return logins_set, moved, avatars_set, groups_added, groups_removed
