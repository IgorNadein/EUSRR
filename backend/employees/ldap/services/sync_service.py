"""Сервис синхронизации данных между Django и LDAP.

Этот модуль предоставляет высокоуровневый API для двусторонней синхронизации:
- Import: LDAP → Django (пользователи, отделы)
- Export: Django → LDAP (обновление профилей, групп, перемещение между отделами)
"""

from __future__ import annotations

import logging
from typing import Iterable, List, Optional, Set, Tuple

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from ...models import Department, Employee, EmployeeDepartment, LdapSyncState
from ..config import SyncConfig
from ..infrastructure.connections import _ldap
from ..domain.dtos import (
    DirectoryUserDTO,
    DirectoryDepartmentDTO,
    LdapPersonDTO,
    _entry_to_dto,
)
from ..repositories.ldap_repository import modify_user_attrs
from ..utils.ldap_utils import _paged_search, get_attr_str
from .user_service import UserService
from .department_service import DepartmentService
from .group_service import GroupService

logger = logging.getLogger(__name__)


class SyncService:
    """Сервис синхронизации данных между Django и LDAP.
    
    Координирует работу UserService, DepartmentService и GroupService
    для выполнения массовых операций импорта и экспорта.
    """

    def __init__(
        self,
        user_service: Optional[UserService] = None,
        department_service: Optional[DepartmentService] = None,
        group_service: Optional[GroupService] = None,
    ):
        """Инициализация SyncService.
        
        Args:
            user_service: Сервис для работы с пользователями.
            department_service: Сервис для работы с отделами.
            group_service: Сервис для работы с группами.
        """
        self._user_service = user_service or UserService()
        self._department_service = department_service or DepartmentService()
        self._group_service = group_service or GroupService()

    # ==================== IMPORT: DEPARTMENTS ====================

    def import_departments(self, cfg: SyncConfig) -> Tuple[int, int, int]:
        """Импорт OU отделов из LDAP в Django.
        
        Читает organizational units из LDAP и создаёт/обновляет
        соответствующие записи Department в Django.
        
        Args:
            cfg: Конфигурация синхронизации.
            
        Returns:
            Tuple[int, int, int]: (created, updated, deleted).
            
        Raises:
            RuntimeError: Если не задана база отделов.
        """
        raw_base = cfg.departments_base_dn or getattr(
            settings, "LDAP_DEPARTMENTS_BASE", ""
        )
        base = raw_base.strip().strip('"').strip("'")
        
        if not base:
            raise RuntimeError("departments_base_dn не задан.")

        created = updated = deleted = 0
        seen_names: Set[str] = set()

        with _ldap() as conn, transaction.atomic():
            # Читаем все OU
            entries = _paged_search(
                conn, base, "(objectClass=organizationalUnit)"
            )
            
            base_dn_lower = base.lower()
            root_ou_name = (
                base.split(",", 1)[0][3:].strip()
                if base.upper().startswith("OU=")
                else None
            )

            for entry in entries:
                attrs = getattr(entry, "entry_attributes_as_dict", {}) or {}
                dn: str = str(getattr(entry, "entry_dn", "")) or get_attr_str(
                    attrs, "distinguishedName"
                )
                dn = (dn or "").strip()
                
                # Пропускаем корневой DN
                if not dn or dn.lower() == base_dn_lower:
                    continue

                name: str = (
                    get_attr_str(attrs, "ou") or get_attr_str(attrs, "name")
                ).strip()
                
                if not name:
                    continue

                # Пропускаем корневой OU
                if (
                    root_ou_name
                    and name.lower() == root_ou_name.lower()
                    and dn.lower() != base_dn_lower
                ):
                    pass

                seen_names.add(name)
                
                # Создаём или обновляем отдел
                dept, was_created = Department.objects.get_or_create(name=name)
                
                if was_created:
                    created += 1
                    if cfg.show_changes:
                        print(f"[CHG] + Dept: {name}  DN={dn}")

                # Обновляем руководителя
                head_dn: str = get_attr_str(attrs, "managedBy")
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

                # Сохраняем состояние синхронизации
                state, _ = LdapSyncState.objects.get_or_create(
                    model="department", object_pk=str(dept.pk)
                )
                state.touch(
                    ldap_dn=dn,
                    last_ldap_modify_ts=None,
                    last_django_modify_ts=timezone.now(),
                    sync_dir="ldap",
                )

            # Удаляем отделы, которых нет в LDAP
            to_delete_qs = Department.objects.exclude(name__in=seen_names)
            
            if cfg.show_changes:
                deleted_names = list(to_delete_qs.values_list("name", flat=True))
                for name in deleted_names:
                    verb = "будет удалён" if cfg.dry_run else "удалён"
                    print(f"[CHG] - Dept: {name} ({verb})")
            
            deleted_count = to_delete_qs.count()
            
            if cfg.dry_run:
                deleted = deleted_count
            else:
                # Сначала очищаем head ссылки
                Department.objects.filter(
                    pk__in=to_delete_qs.values_list("pk", flat=True)
                ).update(head=None)
                
                # Удаляем отделы
                to_delete_qs.delete()
                
                # Очищаем старые sync states
                LdapSyncState.objects.filter(model="department").exclude(
                    object_pk__in=Department.objects.values_list("pk", flat=True)
                ).delete()
                
                deleted = deleted_count

        return created, updated, deleted

    # ==================== IMPORT: USERS ====================

    def _create_user_from_dto(
        self, dto: LdapPersonDTO
    ) -> Optional[Employee]:
        """Создаёт нового Employee по данным из LDAP.
        
        Args:
            dto: Нормализованные данные из LDAP.
            
        Returns:
            Optional[Employee]: Созданный пользователь или None.
        """
        if not dto.phone_e164:
            logger.warning(
                "LDAP import: skip create for DN=%s, email=%s — no valid phone",
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
                "LDAP import: skip create for DN=%s, email=%s — %s",
                dto.dn,
                dto.email,
                exc,
            )
            return None

        user.save()
        return user

    def _update_user_from_dto(
        self, user: Employee, dto: LdapPersonDTO
    ) -> Employee:
        """Обновляет существующего Employee данными из LDAP.
        
        Args:
            user: Существующий пользователь.
            dto: Новые данные из LDAP.
            
        Returns:
            Employee: Обновлённый пользователь.
        """
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

    def import_users(self, cfg: SyncConfig) -> Tuple[int, int, int]:
        """Импорт пользователей из LDAP в Django.
        
        Читает пользователей из LDAP и создаёт/обновляет
        соответствующие записи Employee в Django.
        
        Args:
            cfg: Конфигурация синхронизации.
            
        Returns:
            Tuple[int, int, int]: (created, updated, deleted).
            
        Raises:
            RuntimeError: Если не заданы базовые DN.
        """
        base_users = (
            cfg.users_base_dn or getattr(settings, "LDAP_USERS_BASE", "")
        ).strip()
        base_deps = (
            cfg.departments_base_dn
            or getattr(settings, "LDAP_DEPARTMENTS_BASE", "")
        ).strip()
        
        if not (base_users and base_deps):
            raise RuntimeError("LDAP_USERS_BASE/LDAP_DEPARTMENTS_BASE не заданы.")

        created = updated = deleted = 0
        seen_guids: Set[str] = set()
        seen_dns: Set[str] = set()

        with _ldap() as conn, transaction.atomic():
            # Читаем пользователей из обеих баз
            flt = "(&(objectCategory=person)(objectClass=user))"
            entries = _paged_search(conn, base_users, flt) + _paged_search(
                conn, base_deps, flt
            )

            # Конвертируем в DTO
            dtos: List[LdapPersonDTO] = []
            for entry in entries:
                dto = _entry_to_dto(entry)
                if dto.dn:
                    seen_dns.add(dto.dn)
                if dto.guid:
                    seen_guids.add(dto.guid)
                dtos.append(dto)

            # Индексируем существующих пользователей
            from ..repositories.employee_repository import (
                _load_existing_users_index,
                _find_user_for_dto,
                _bind_user_department,
                _cleanup_absent_users,
            )
            from ..repositories.sync_state_repository import _touch_sync_state
            
            by_guid, by_email = _load_existing_users_index(dtos)
            
            # Разделяем на create/update
            to_create: List[LdapPersonDTO] = []
            to_update: List[Tuple[Employee, LdapPersonDTO]] = []

            for dto in dtos:
                existing = _find_user_for_dto(
                    dto, by_guid=by_guid, by_email=by_email
                )
                if existing:
                    to_update.append((existing, dto))
                else:
                    to_create.append(dto)

            skipped = 0
            processed: List[Tuple[Employee, LdapPersonDTO]] = []

            # UPDATE
            for user, dto in to_update:
                self._update_user_from_dto(user, dto)
                # Записываем Django PK в LDAP employeeNumber если пусто
                employee_id_attr = getattr(
                    settings, "LDAP_EMPLOYEE_ID_ATTR", "employeeNumber"
                )
                if dto.dn and not cfg.dry_run:
                    try:
                        from ..repositories.ldap_repository import read_attrs
                        current = read_attrs(conn, dto.dn, [employee_id_attr])
                        if not current.get(employee_id_attr):
                            modify_user_attrs(
                                conn, dto.dn, {employee_id_attr: str(user.pk)}, do_write=True
                            )
                    except Exception as e:
                        logger.debug(
                            "Could not write %s for %s: %s",
                            employee_id_attr, dto.dn, e
                        )
                processed.append((user, dto))
                updated += 1

            # CREATE
            for dto in to_create:
                user = self._create_user_from_dto(dto)
                if not user:
                    skipped += 1
                    continue
                # Записываем Django PK в LDAP employeeNumber
                employee_id_attr = getattr(
                    settings, "LDAP_EMPLOYEE_ID_ATTR", "employeeNumber"
                )
                if dto.dn and not cfg.dry_run:
                    try:
                        modify_user_attrs(
                            conn, dto.dn, {employee_id_attr: str(user.pk)}, do_write=True
                        )
                    except Exception as e:
                        logger.debug(
                            "Could not write %s for %s: %s",
                            employee_id_attr, dto.dn, e
                        )
                processed.append((user, dto))
                created += 1

            if cfg.show_changes:
                for dto in to_create:
                    if any(u.email == dto.email for u, _ in processed):
                        print(f"[CHG] + User: {dto.email}  DN={dto.dn}")
                for existing, dto in to_update:
                    print(f"[CHG] ~ User: {existing.email}  DN={dto.dn}")

            if skipped:
                logger.warning(
                    "[LDAP] Пропущено записей из-за валидации: %s", skipped
                )

            # Привязываем к отделам и сохраняем sync state
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

            # Очищаем отсутствующих
            deleted = _cleanup_absent_users(
                seen_guids=seen_guids,
                seen_dns=seen_dns,
                dry_run=cfg.dry_run,
                show_changes=cfg.show_changes,
            )

        return created, updated, deleted

    # ==================== EXPORT: USERS ====================

    def export_users(self, cfg: SyncConfig) -> Tuple[int, int, int, int, int]:
        """Экспорт пользователей из Django в LDAP.
        
        Создаёт/обновляет пользователей в LDAP на основе данных из Django.
        Включает: логины/UPN, перемещение между отделами, аватары, группы.
        
        Args:
            cfg: Конфигурация синхронизации.
            
        Returns:
            Tuple[int, int, int, int, int]: 
                (logins_set, moved, avatars_set, groups_added, groups_removed).
        """
        # TODO: Реализовать через UserService
        logger.warning(
            "export_users не полностью реализован через новые сервисы"
        )
        return 0, 0, 0, 0, 0

    def export_users_delete(
        self, cfg: SyncConfig, employees: Iterable[Employee]
    ) -> int:
        """Удаляет учётные записи пользователей в LDAP.
        
        Args:
            cfg: Конфигурация синхронизации.
            employees: Итератор пользователей для удаления.
            
        Returns:
            int: Количество успешно удалённых DN.
        """
        do_write = not cfg.dry_run
        deleted = 0

        with _ldap() as conn:
            for emp in employees:
                state_dn = (
                    LdapSyncState.objects.filter(
                        model="employee", object_pk=str(emp.pk)
                    )
                    .values_list("ldap_dn", flat=True)
                    .first()
                )
                user_dn = (state_dn or "").strip()
                
                if not user_dn:
                    logger.warning(
                        "Пропуск удаления: у сотрудника pk=%s пустой ldap_dn",
                        emp.pk,
                    )
                    continue

                try:
                    if do_write:
                        self._user_service.delete_user(emp)
                    deleted += 1
                except Exception as exc:
                    logger.error(
                        "Ошибка удаления пользователя DN=%s: %s", user_dn, exc
                    )

        return deleted
