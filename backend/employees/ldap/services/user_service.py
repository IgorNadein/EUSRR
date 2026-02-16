"""Сервис для управления пользователями в LDAP и Django.

Этот модуль содержит бизнес-логику для CRUD операций с пользователями,
включая синхронизацию между Active Directory и Django ORM.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from ldap3 import MODIFY_REPLACE, Connection

from ...models import Employee, LdapSyncState, Position
from ..domain.dtos import DirectoryUserDTO
from ..errors import (DirectoryDbError, DirectoryLdapError,
                      DirectoryServiceError)
from ..infrastructure.connections import _ldap
from ..repositories.ldap_repository import (ensure_container_exists, is_taken,
                                            ldap_modify_or_ignore,
                                            modify_user_attrs, read_attrs)
from ..utils.group_utils import sync_user_groups_by_cns
from ..utils.image_utils import normalize_avatar_to_jpeg
from ..utils.ldap_utils import (build_logins_for_user, cn_candidates,
                                get_guid_str)
from ..utils.text_utils import esc_rdn

# Константы UAC (User Account Control)
UAC_ENABLED = 512
UAC_DISABLED = 514


class UserService:
    """Сервис для управления пользователями в LDAP и Django."""

    def __init__(
        self,
        ldap_repository=None,
        employee_repository=None,
        sync_state_repository=None
    ):
        """
        Инициализация сервиса.

        Args:
            ldap_repository: Репозиторий для работы с LDAP (optional)
            employee_repository: Репозиторий для работы с Employee (optional)
            sync_state_repository: Репозиторий для LdapSyncState (optional)
        """
        self.ldap_repository = ldap_repository
        self.employee_repository = employee_repository
        self.sync_state_repository = sync_state_repository

    # ==================== NEW ARCHITECTURE: PURE LDAP METHODS ==================== #

    def create_user_in_ldap_only(self, dto: DirectoryUserDTO) -> dict[str, Any]:
        """Создаёт пользователя ТОЛЬКО в LDAP, возвращает данные для БД.

        Это новый метод для разделения ответственности:
        - View создает Employee в БД (в транзакции)
        - Затем вызывает этот метод для синхронизации в LDAP
        - View обрабатывает результат и откатывает БД при ошибке LDAP

        Args:
            dto (DirectoryUserDTO): Данные нового пользователя.

        Returns:
            dict: Данные для сохранения в БД:
                - 'dn': DN пользователя в LDAP
                - 'guid': GUID пользователя из LDAP
                - 'employee_pk': PK из employeeNumber (если был установлен)

        Raises:
            DirectoryLdapError: Ошибка на этапе создания/настройки LDAP.
        """
        with _ldap() as conn:
            try:
                # 1) Создаём пользователя в LDAP
                dn = self._create_user_in_ldap(conn, dto)

                # 2) Устанавливаем пароль
                self._set_password(conn, dn, dto.initial_password)

                # 3) Активируем если нужно
                if dto.is_active:
                    self._enable_user(conn, dn)

                # 4) Читаем GUID для синхронизации
                attrs = read_attrs(conn, dn, ["objectGUID"])
                guid = get_guid_str(attrs)

                # 5) Post-actions (best effort) - группы и аватар
                if dto.group_cns:
                    try:
                        sync_user_groups_by_cns(
                            conn, dn, set(dto.group_cns), do_write=True)
                    except Exception:
                        pass

                if dto.avatar_bytes:
                    try:
                        avatar = normalize_avatar_to_jpeg(
                            dto.avatar_bytes, size_px=384, max_kb=100
                        )
                        if avatar:
                            modify_user_attrs(
                                conn, dn, {"thumbnailPhoto": avatar}, do_write=True
                            )
                    except Exception:
                        pass

                return {
                    'dn': dn,
                    'guid': guid,
                }

            except Exception as e:
                raise DirectoryLdapError(f"LDAP create failed: {e}") from e

    def update_user_in_ldap_only(
        self,
        instance: Employee,
        changes: Dict[str, Any]
    ) -> dict[str, Any]:
        """Обновляет пользователя ТОЛЬКО в LDAP.

        Новая архитектура: View обновляет БД, затем синхронизирует в LDAP.

        Args:
            instance (Employee): Инстанс сотрудника с актуальными данными из БД.
            changes (Dict[str, Any]): Изменения из request.data для синхронизации в LDAP.

        Returns:
            dict: Данные для дополнительного обновления БД если нужно:
                - 'dn': новый DN если переместили пользователя

        Raises:
            DirectoryLdapError: Ошибка синхронизации с LDAP.
        """
        try:
            current_dn = self._get_employee_dn(instance)
        except DirectoryServiceError as e:
            raise DirectoryLdapError(f"Cannot get employee DN: {e}") from e

        with _ldap() as conn:
            ldap_changes = dict(changes)

            # Определяем куда переместить пользователя если меняется department
            move_to_department_dn = None
            if 'department' in changes or 'department_id' in changes:
                # Если передан department объект или ID, получаем его DN
                dept_val = changes.get(
                    'department') or changes.get('department_id')
                if dept_val:
                    from .department_service import DepartmentService
                    dept_svc = DepartmentService()
                    if isinstance(dept_val, int):
                        from employees.models import Department
                        dept = Department.objects.filter(id=dept_val).first()
                    else:
                        dept = dept_val

                    if dept:
                        try:
                            move_to_department_dn = dept_svc._get_department_dn(
                                dept)
                        except Exception:
                            pass

            # Определяем группы если нужно синхронизировать
            group_cns = None
            if 'groups' in changes:
                group_cns = changes.get('groups', [])

            try:
                result = self._update_user_in_ldap(
                    conn=conn,
                    current_dn=current_dn,
                    model_changes=ldap_changes,
                    move_to_department_dn=move_to_department_dn,
                    group_cns=group_cns,
                )

                # Распаковываем результат
                if isinstance(result, tuple):
                    new_dn, _ = result
                else:
                    new_dn = result

                # Если DN изменился - возвращаем для обновления БД
                if new_dn and new_dn != current_dn:
                    return {'dn': new_dn}

                return {}

            except Exception as e:
                raise DirectoryLdapError(f"LDAP update failed: {e}") from e

    def delete_user_in_ldap_only(self, instance: Employee) -> None:
        """Удаляет пользователя ТОЛЬКО из LDAP.

        Новая архитектура: View удаляет из БД, затем удаляет из LDAP.

        Args:
            instance (Employee): Сотрудник для удаления из LDAP.

        Raises:
            DirectoryLdapError: Ошибка удаления из LDAP.
        """
        try:
            dn = self._get_employee_dn(instance)
        except DirectoryServiceError:
            # Если нет DN - ничего удалять не нужно
            logger.warning(
                f"Cannot get DN for employee {instance.pk}, skipping LDAP delete")
            return

        with _ldap() as conn:
            try:
                # 1. Soft-disable перед удалением
                modify_user_attrs(conn, dn, {"userAccountControl": 0x0202})
            except Exception as e:
                logger.warning(f"LDAP soft-disable failed (continuing): {e}")

            try:
                # 2. Hard delete
                self._hard_delete_user_in_ldap(conn, dn)
            except Exception as e:
                raise DirectoryLdapError(
                    f"LDAP hard delete failed: {e}") from e

    # ==================== OLD ARCHITECTURE: LDAP + DB ==================== #

    def create_user(self, dto: DirectoryUserDTO) -> Employee:
        """Создаёт учётку в LDAP и запись в БД (DN/связь — только в LdapSyncState).

        Процесс:
            1) LDAP: create → set password → optional enable.
            2) DB (atomic): создаём Employee; фиксируем DN в LdapSyncState(model='employee').
            3) Post-actions: группы, аватар (best-effort).

        Args:
            dto (DirectoryUserDTO): Данные нового пользователя.

        Returns:
            Employee: Созданный сотрудник.

        Raises:
            DirectoryLdapError: Ошибка на этапе создания/настройки LDAP.
            DirectoryDbError: Ошибка записи в БД (выполняется компенсирующее удаление в LDAP).
        """
        with _ldap() as conn:
            dn: Optional[str] = None
            try:
                # 1) LDAP
                dn = self._create_user_in_ldap(conn, dto)
                self._set_password(conn, dn, dto.initial_password)
                if dto.is_active:
                    self._enable_user(conn, dn)
            except Exception as e:
                raise DirectoryLdapError(f"LDAP create failed: {e}") from e

            # 2) DB + sync-state
            try:
                with transaction.atomic():
                    emp = Employee.objects.create(
                        first_name=dto.first_name,
                        last_name=dto.last_name,
                        email=dto.email,
                        phone_number=dto.phone_e164,
                        is_active=dto.is_active,
                        is_ldap_managed=True,
                    )
                    if hasattr(emp, "set_unusable_password"):
                        emp.set_unusable_password()
                        emp.save(update_fields=["password"])

                    attrs = read_attrs(conn, dn, ["objectGUID"])
                    guid = get_guid_str(attrs)

                    self._touch_state(
                        model="employee",
                        object_pk=emp.pk,
                        ldap_dn=dn,
                        ldap_guid=guid,
                        sync_dir="ldap",
                        last_django_modify_ts=timezone.now(),
                    )

                    # Записываем Django PK в LDAP employeeNumber для связки
                    employee_id_attr = getattr(
                        settings, "LDAP_EMPLOYEE_ID_ATTR", "employeeNumber"
                    )
                    modify_user_attrs(
                        conn, dn, {employee_id_attr: str(emp.pk)}, do_write=True
                    )

                    # Временно импортируем для совместимости
                    # TODO: Убрать после полного рефакторинга
                    if dto.department_dn and hasattr(emp, "set_active_department"):
                        from ..directory_service import DirectoryService
                        svc = DirectoryService()
                        dept = svc._get_department_by_dn(dto.department_dn)
                        if dept:
                            emp.set_active_department(dept)
            except Exception as e:
                # компенсируем LDAP при падении БД
                try:
                    if dn:
                        self._hard_delete_user_in_ldap(conn, dn)
                finally:
                    pass
                raise DirectoryDbError(str(e)) from e

            # 3) Post-actions (best effort)
            try:
                if dto.group_cns:
                    sync_user_groups_by_cns(
                        conn, dn, set(dto.group_cns), do_write=True)
                if dto.avatar_bytes:
                    # Увеличен размер до 384px для максимального качества в LDAP
                    avatar = normalize_avatar_to_jpeg(
                        dto.avatar_bytes, size_px=384, max_kb=100
                    )
                    if avatar:
                        modify_user_attrs(
                            conn, dn, {"thumbnailPhoto": avatar}, do_write=True
                        )
            except Exception:
                pass

            return emp

    def update_user(
        self,
        emp: Employee,
        changes: Dict[str, Any],
        group_cns: Optional[List[str]] = None,
        move_to_department_dn: Optional[str] = None,
    ) -> Employee:
        """Обновляет пользователя: LDAP (пароль/MOVE/UAC/attrs/groups) → затем БД.

        Args:
            emp (Employee): Сотрудник, которого обновляем.
            changes (Dict[str, Any]): Поля модели (first_name, last_name, email, phone_number,
                is_active, password, avatar_bytes, display_name и т.п.).
            group_cns (Optional[List[str]]): Полный набор CN для синхронизации членства (или None).
            move_to_department_dn (Optional[str]): DN OU, куда переместить запись.

        Returns:
            Employee: Обновлённая модель.

        Raises:
            DirectoryLdapError: Ошибка применения изменений в LDAP.
            DirectoryDbError: Ошибка фиксации изменений в БД.
            DirectoryServiceError: Нет DN пользователя.
        """
        current_dn = self._get_employee_dn(emp)
        is_active_val: Optional[bool] = None
        if "is_active" in changes:
            try:
                is_active_val = bool(changes.get("is_active"))
            except Exception:
                is_active_val = None

        old_pos = getattr(emp, "position", None) if hasattr(
            emp, "position") else None
        new_pos = None
        pos_in_payload = False
        if "position" in changes or "position_id" in changes:
            pos_in_payload = True
            val = changes.pop("position", changes.pop("position_id", None))
            # Обработка пустой строки как None (снятие должности)
            if val == "":
                new_pos = None
            elif isinstance(val, Position) or val is None:
                new_pos = val
            elif isinstance(val, int):
                new_pos = Position.objects.filter(pk=val).first()
            else:
                try:
                    new_pos = Position.objects.filter(pk=int(val)).first()
                except Exception:
                    new_pos = None

        with _ldap() as conn:
            ldap_changes = dict(changes)
            try:
                result = self._update_user_in_ldap(
                    conn=conn,
                    current_dn=current_dn,
                    model_changes=ldap_changes,
                    move_to_department_dn=move_to_department_dn,
                    group_cns=group_cns,
                )
                # Распаковываем результат (dn, avatar_bytes или None)
                if isinstance(result, tuple):
                    new_dn, saved_avatar_bytes = result
                else:
                    # Обратная совместимость (если метод вернул только dn)
                    new_dn = result
                    saved_avatar_bytes = None
            except Exception as e:
                raise DirectoryLdapError(f"LDAP update failed: {e}") from e

            try:
                with transaction.atomic():
                    # обновим sync-state, если DN поменялся
                    if new_dn and new_dn != current_dn:
                        self._touch_state(
                            model="employee",
                            object_pk=emp.pk,
                            ldap_dn=new_dn,
                            sync_dir="ldap",
                            last_django_modify_ts=timezone.now(),
                        )
                        current_dn = new_dn

                    # синхронизация поля is_active
                    updated_fields: List[str] = []
                    if (
                        is_active_val is not None
                        and getattr(emp, "is_active", None) != is_active_val
                    ):
                        emp.is_active = is_active_val
                        updated_fields.append("is_active")

                    for k, v in changes.items():
                        if k in {"password", "avatar_bytes", "is_active"}:
                            continue
                        if hasattr(emp, k) and getattr(emp, k) != v:
                            setattr(emp, k, v)
                            updated_fields.append(k)

                    if pos_in_payload and hasattr(emp, "position"):
                        old_id = getattr(emp, "position_id", None)
                        new_id = new_pos.id if new_pos else None
                        if old_id != new_id:
                            emp.position = new_pos
                            updated_fields.append("position")

                    if move_to_department_dn and hasattr(emp, "set_active_department"):
                        from .department_service import DepartmentService
                        dept_svc = DepartmentService()
                        dept = dept_svc._get_department_by_dn(
                            move_to_department_dn)
                        if dept:
                            emp.set_active_department(dept)

                    # Сохраняем аватар в БД, если он был успешно записан в LDAP
                    if saved_avatar_bytes and hasattr(emp, "avatar"):
                        from django.core.files.base import ContentFile
                        filename = f"avatar_{emp.pk}.jpg"
                        emp.avatar.save(filename, ContentFile(
                            saved_avatar_bytes), save=False)
                        if "avatar" not in updated_fields:
                            updated_fields.append("avatar")

                    if updated_fields:
                        emp.save(update_fields=list(set(updated_fields)))
            except Exception as e:
                raise DirectoryDbError(str(e)) from e

            try:
                if pos_in_payload and (old_pos != new_pos):
                    # Используем PositionService для синхронизации должностей
                    import logging

                    from ..directory_service import DirectoryService
                    from .position_service import PositionService
                    logger = logging.getLogger(__name__)

                    pos_svc = PositionService()
                    dir_svc = DirectoryService()

                    if old_pos:
                        old_dn = (old_pos.ldap_group_dn or "").strip()
                        if not old_dn:
                            maybe = dir_svc.find_group_dn(
                                conn,
                                f"POS_{old_pos.name}",
                                bases=[dir_svc._positions_base()],
                            )
                            old_dn = maybe or ""
                        if old_dn:
                            try:
                                logger.info(
                                    f"Removing user {current_dn} "
                                    f"from position group {old_dn}"
                                )
                                dir_svc.remove_group_members(
                                    conn, old_dn, [current_dn]
                                )
                            except RuntimeError as e:
                                # Игнорируем unwillingToPerform
                                # (пользователь не в группе)
                                error_msg = str(e).lower()
                                if (
                                    "unwillingtoperform" in error_msg
                                    or "will_not_perform" in error_msg
                                ):
                                    logger.warning(
                                        f"LDAP refused to remove user "
                                        f"from group (possibly not a "
                                        f"member): {e}"
                                    )
                                else:
                                    raise

                    if new_pos:
                        pos_dn = pos_svc._ensure_position_group(conn, new_pos)
                        dir_svc.add_group_members(conn, pos_dn, [current_dn])
            except Exception as e:
                raise DirectoryLdapError(
                    f"LDAP position membership sync failed: {e}"
                ) from e

            return emp

    def delete_user(self, emp: Employee) -> None:
        """Удаляет пользователя: LDAP soft-disable → DB delete → LDAP hard delete.

        Args:
            emp (Employee): Удаляемый сотрудник.

        Raises:
            DirectoryLdapError: Ошибка при soft-disable/hard-delete в LDAP.
            DirectoryDbError: Ошибка при удалении записи в БД.
        """
        try:
            dn: Optional[str] = self._get_employee_dn(emp)
        except DirectoryServiceError:
            dn = None

        with _ldap() as conn:
            if dn:
                try:
                    modify_user_attrs(conn, dn, {"userAccountControl": 0x0202})
                except Exception as e:
                    raise DirectoryLdapError(
                        f"LDAP soft-disable failed: {e}") from e

            try:
                with transaction.atomic():
                    emp_pk = emp.pk
                    emp.delete()
                    LdapSyncState.objects.filter(
                        model="employee", object_pk=str(emp_pk)
                    ).delete()
            except Exception as e:
                raise DirectoryDbError(str(e)) from e

            if dn:
                try:
                    self._hard_delete_user_in_ldap(conn, dn)
                except Exception as e:
                    raise DirectoryLdapError(
                        f"LDAP hard delete failed: {e}") from e

    # ==================== DN ↔ ID Conversion Methods ==================== #

    def employee_ids_to_dns(self, ids: list[int]) -> list[str]:
        """Конвертирует ID сотрудников в их Distinguished Names.

        Args:
            ids: Список ID сотрудников.

        Returns:
            Список DN из LdapSyncState.
        """
        if not ids:
            return []
        id_strs = [str(i) for i in ids if isinstance(i, int)]
        return list(
            LdapSyncState.objects.filter(
                model="employee", object_pk__in=id_strs)
            .exclude(ldap_dn__isnull=True)
            .exclude(ldap_dn__exact="")
            .values_list("ldap_dn", flat=True)
        )

    def dns_to_employee_ids(self, dns: list[str]) -> list[int]:
        """Конвертирует Distinguished Names в ID сотрудников.

        Args:
            dns: Список Distinguished Names.

        Returns:
            Список ID сотрудников.
        """
        if not dns:
            return []
        ids = list(
            LdapSyncState.objects.filter(
                model="employee", ldap_dn__in=dns
            ).values_list("object_pk", flat=True)
        )
        # object_pk хранится как str
        return [int(x) for x in ids if str(x).isdigit()]

    def employees_brief_by_dns(self, dns: list[str]) -> list[dict]:
        """Получает краткую информацию о сотрудниках по их DN.

        Args:
            dns: Список Distinguished Names.

        Returns:
            Список словарей с полями: id, email, first_name, last_name.
        """
        ids = self.dns_to_employee_ids(dns)
        return list(
            Employee.objects.filter(id__in=ids).values(
                "id", "email", "first_name", "last_name"
            )
        )

    # ==================== Private Helper Methods ==================== #

    def _touch_state(
        self, *, model: str, object_pk: str | int, **touch_kwargs: Any
    ) -> LdapSyncState:
        """Унифицированная запись в LdapSyncState.touch(...).

        Args:
            model (str): Имя модели в sync-state (например, 'employee').
            object_pk (Union[str,int]): PK объекта в БД.
            **touch_kwargs: Параметры, передаваемые в touch(...).

        Returns:
            LdapSyncState: Обновлённая/созданная запись.
        """
        state, _ = LdapSyncState.objects.get_or_create(
            model=model, object_pk=str(object_pk)
        )
        state.touch(**touch_kwargs)
        return state

    def _set_password(self, conn: Connection, dn: str, new_password: str) -> None:
        """Меняет пароль пользователя в AD (control)."""
        ok = conn.extend.microsoft.modify_password(dn, new_password)
        if not ok:
            msg = conn.result or {}
            raw = (msg.get("message") or "").upper()
            if "0000052D" in raw:
                raise RuntimeError(
                    "Пароль не соответствует политике сложности AD")
            raise RuntimeError(f"LDAP set password failed: {msg}")

    def _enable_user(self, conn: Connection, dn: str) -> None:
        """Включает учётку (UAC=512)."""
        ldap_modify_or_ignore(
            conn, dn, {"userAccountControl": [
                (MODIFY_REPLACE, [UAC_ENABLED])]}, set()
        )

    def _unique_logins(
        self, conn: Connection, dto: DirectoryUserDTO, upn_suffix: str
    ) -> tuple[str, str]:
        """Генерирует уникальные sAMAccountName и UPN."""
        sam, upn = build_logins_for_user(
            first_name=dto.first_name,
            last_name=dto.last_name,
            email=dto.email,
            upn_suffix=upn_suffix,
            is_taken_sam=lambda s: is_taken(
                conn, attributes={"sAMAccountName": s}),
            is_taken_upn=lambda u: is_taken(
                conn, attributes={"userPrincipalName": u}),
            guid=getattr(dto, "ldap_guid", None),
        )
        if not sam or not upn:
            raise ValueError(
                "Не удалось сгенерировать уникальные sAMAccountName/UPN")
        return sam, upn

    def _phone_write_attr(self) -> str:
        """Возвращает имя телефонного атрибута для записи."""
        write_attr = getattr(settings, "LDAP_WRITE_PHONE_ATTR", None)
        if write_attr:
            return write_attr
        candidates = getattr(
            settings, "LDAP_PHONE_ATTRS", ("mobile", "telephoneNumber")
        )
        return candidates[0] if candidates else "telephoneNumber"

    def _build_user_attrs(
        self, dto: DirectoryUserDTO, sam: str, upn: str, cn_text: str
    ) -> Dict[str, Any]:
        """Собирает атрибуты для создания user в AD, отбрасывая пустые значения."""
        if not all(isinstance(x, str) for x in (sam, upn, cn_text)):
            raise TypeError("sam, upn и cn_text должны быть строками")

        base_attrs: Dict[str, Any] = {
            "cn": cn_text,
            "givenName": dto.first_name or None,
            "sn": dto.last_name or ".",  # sn не может быть пустым
            "displayName": cn_text or None,
            "mail": (dto.email or None),
            self._phone_write_attr(): (dto.phone_e164 or None),
            "sAMAccountName": sam,
            "userPrincipalName": upn,
            "userAccountControl": UAC_DISABLED,  # disabled до верификации email
        }
        return {k: v for k, v in base_attrs.items() if v not in (None, "", [])}

    def _try_add_with_cn_list(
        self,
        conn: Connection,
        base_dn: str,
        object_classes: List[str],
        dto: DirectoryUserDTO,
        sam: str,
        upn: str,
        cns: List[str],
    ) -> Optional[str]:
        """Пробует создать запись по списку CN-кандидатов."""
        if not isinstance(cns, list):
            raise TypeError("cns должен быть списком строк")
        for cn_txt in cns:
            rdn = f"CN={esc_rdn(cn_txt)}"
            dn_try = f"{rdn},{base_dn}"
            attrs = self._build_user_attrs(dto, sam, upn, cn_txt)
            if conn.add(dn_try, object_classes, attrs):
                return dn_try
        return None

    def _create_user_in_ldap(self, conn: Connection, dto: DirectoryUserDTO) -> str:
        """Создаёт объект user в LDAP (AD) и возвращает его DN."""
        base_dn = (
            dto.department_dn
            or getattr(settings, "LDAP_USERS_BASE", None)
            or getattr(settings, "LDAP_BASE_DN", None)
        )
        if not base_dn:
            raise RuntimeError(
                "Не задан контейнер для создания пользователя (department_dn / LDAP_USERS_BASE / LDAP_BASE_DN)."
            )
        ensure_container_exists(conn, base_dn)

        upn_suffix = getattr(settings, "LDAP_UPN_SUFFIX", "") or (
            dto.email.split(
                "@", 1)[1] if dto.email and "@" in dto.email else ""
        )
        if not upn_suffix:
            raise ValueError(
                "Не задан UPN-суффикс (LDAP_UPN_SUFFIX) и его нельзя вывести из email."
            )

        sam, upn = self._unique_logins(conn, dto, upn_suffix)
        pretty_cn = (
            " ".join(filter(None, [dto.first_name, dto.last_name])).strip()
        ) or sam
        safe_cn = sam
        cn_list = cn_candidates(pretty_cn, safe_cn)

        object_classes = ["top", "person", "organizationalPerson", "user"]
        dn = self._try_add_with_cn_list(
            conn, base_dn, object_classes, dto, sam, upn, cn_list
        )
        if dn:
            return dn
        raise RuntimeError(f"LDAP add user failed: {conn.result}")

    def _hard_delete_user_in_ldap(self, conn: Connection, dn: str) -> None:
        """Безусловное удаление user (ignore noSuchObject)."""
        ok = conn.delete(dn)
        if not ok and (conn.result or {}).get("description") not in {"noSuchObject"}:
            raise RuntimeError(f"LDAP delete failed for {dn}: {conn.result}")

    def _update_user_in_ldap(
        self,
        conn: Connection,
        current_dn: str,
        model_changes: Dict[str, Any],
        *,
        move_to_department_dn: Optional[str] = None,
        group_cns: Optional[Iterable[str]] = None,
    ) -> str:
        """Применяет LDAP-изменения к существующему пользователю и возвращает (возможный новый) DN.

        NOTE: Этот метод слишком большой (~150 строк) и должен быть рефакторен в будущем.
        Сейчас просто перенесём как есть для совместимости.
        """
        # Временно используем DirectoryService для _move_to_department
        from ..directory_service import DirectoryService
        svc = DirectoryService()

        if not isinstance(current_dn, str) or not current_dn.strip():
            raise TypeError("current_dn должен быть непустой строкой")
        if not isinstance(model_changes, dict):
            raise TypeError("model_changes должен быть словарём")

        dn = current_dn
        new_password = model_changes.pop("password", None)
        avatar_bytes = model_changes.pop("avatar_bytes", None)
        is_active_val = model_changes.pop("is_active", None)

        # 1) Пароль
        if new_password:
            self._set_password(conn, dn, new_password)

        # 2) Перемещение
        if move_to_department_dn:
            dn = svc._move_to_department(conn, dn, move_to_department_dn)

        # 3) UAC
        if is_active_val is not None:
            uac_val = UAC_ENABLED if is_active_val else UAC_DISABLED
            modify_user_attrs(
                conn, dn, {"userAccountControl": uac_val}, do_write=True)

        # 4) Прочие атрибуты
        ldap_attrs_map = {
            "first_name": "givenName",
            "last_name": "sn",
            "email": "mail",
            "phone_number": self._phone_write_attr(),
            "display_name": "displayName",
        }
        attrs_to_update = {}
        for model_key, ldap_attr in ldap_attrs_map.items():
            if model_key in model_changes:
                val = model_changes[model_key]
                if val or ldap_attr == "sn":
                    attrs_to_update[ldap_attr] = val if val else "."

        if attrs_to_update:
            modify_user_attrs(conn, dn, attrs_to_update, do_write=True)

        # 5) Аватар
        avatar_saved = False
        if avatar_bytes:
            # Увеличен размер до 384px для максимального качества в LDAP
            avatar = normalize_avatar_to_jpeg(
                avatar_bytes, size_px=384, max_kb=100
            )
            if avatar:
                modify_user_attrs(
                    conn, dn, {"thumbnailPhoto": avatar}, do_write=True)
                avatar_saved = True  # Флаг для сохранения в БД

        # 6) Группы
        if group_cns is not None:
            sync_user_groups_by_cns(conn, dn, set(group_cns), do_write=True)

        # Возвращаем dn и флаг сохранения аватара
        return (dn, avatar_bytes if avatar_saved else None)

    def _get_employee_dn(self, employee: Employee) -> str:
        """Возвращает DN сотрудника из LdapSyncState или модели.

        Args:
            employee: Экземпляр Employee.

        Returns:
            str: Полный DN пользователя в LDAP.

        Raises:
            DirectoryServiceError: Если DN не найден.
        """
        # Сначала проверяем LdapSyncState
        dn = (
            LdapSyncState.objects.filter(
                model="employee",
                object_pk=str(employee.pk)
            )
            .values_list("ldap_dn", flat=True)
            .first()
        )

        # Если не найден в LdapSyncState, проверяем поле модели
        if not dn and hasattr(employee, 'ldap_dn'):
            dn = employee.ldap_dn

        if not dn:
            raise DirectoryServiceError("Employee has no ldap_dn")
        return dn

    def _move_user_to_base(self, conn: Connection, user_dn: str, base_dn: str) -> str:
        """Перемещает пользовательский объект в указанный контейнер.

        Args:
            conn: LDAP соединение.
            user_dn: Текущий DN пользователя.
            base_dn: DN целевого контейнера.

        Returns:
            str: Новый DN пользователя после перемещения.

        Raises:
            RuntimeError: Если операция перемещения не удалась.
        """
        rdn = user_dn.split(",", 1)[0]
        ok = conn.modify_dn(user_dn, rdn, new_superior=base_dn)
        if not ok:
            raise RuntimeError(f"LDAP move user to base failed: {conn.result}")
        return f"{rdn},{base_dn}"


__all__ = ["UserService"]
