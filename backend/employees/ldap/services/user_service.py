"""Сервис для управления пользователями в LDAP и Django.

Этот модуль содержит бизнес-логику для CRUD операций с пользователями,
включая синхронизацию между Active Directory и Django ORM.

Рефакторенная версия с улучшениями:
- Наследуется от BaseService (логирование, _touch_state)
- Делегирует работу подсервисам (Password, Login, Mapper)
- Использует константы из constants.py
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Iterable, List, Optional

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from ldap3 import Connection

from ...models import Employee, LdapSyncState
from ..domain.dtos import DirectoryUserDTO
from ..errors import (
    DirectoryDbError,
    DirectoryLdapError,
    DirectoryServiceError,
)
from ..orm_models import LdapUser
from ..utils.group_utils_orm import sync_user_groups_by_cns_orm
from ..infrastructure.connections import _ldap
from ..repositories.ldap_repository import (
    ensure_container_exists,
)
from ..utils.ldap_utils import cn_candidates, get_ldap_str
from ..utils.text_utils import esc_rdn
from .base_service import BaseService
from .constants import (
    UserAccountControl,
    LdapErrorCode,
    SyncDirection,
)
from .user_password_service import UserPasswordService
from .user_login_service import UserLoginService
from .user_mapper_service import UserMapperService

logger = logging.getLogger(__name__)


class UserService(BaseService):
    """Сервис для управления пользователями в LDAP и Django.

    Координирует работу подсервисов:
    - UserPasswordService — пароли
    - UserLoginService — генерация логинов
    - UserMapperService — маппинг атрибутов
    """

    def __init__(
        self,
        ldap_repository=None,
        employee_repository=None,
        sync_state_repository=None,
    ):
        """
        Инициализация сервиса.

        Args:
            ldap_repository: Репозиторий для работы с LDAP (optional)
            employee_repository: Репозиторий для работы с Employee (optional)
            sync_state_repository: Репозиторий для LdapSyncState (optional)
        """
        super().__init__()
        self.ldap_repository = ldap_repository
        self.employee_repository = employee_repository
        self.sync_state_repository = sync_state_repository

        # Подсервисы
        self._password_service = UserPasswordService()
        self._login_service = UserLoginService()
        self._mapper_service = UserMapperService()

    def create_user(self, dto: DirectoryUserDTO) -> Employee:
        """Создаёт учётку в LDAP и запись в БД.

        DN и связь с LDAP хранятся только в LdapSyncState.

        Процесс:
            1) LDAP: create → set password → optional enable.
            2) DB (atomic): создаём Employee и фиксируем DN
               в LdapSyncState(model='employee').
            3) Post-actions: группы, аватар (best-effort).

        Args:
            dto (DirectoryUserDTO): Данные нового пользователя.

        Returns:
            Employee: Созданный сотрудник.

        Raises:
            DirectoryLdapError: Ошибка на этапе создания
                или настройки LDAP.
            DirectoryDbError: Ошибка записи в БД.
                В этом случае выполняется компенсирующее удаление в LDAP.
        """
        with _ldap() as conn:
            dn: Optional[str] = None
            try:
                # 1) LDAP
                dn = self._create_user_in_ldap(conn, dto)
                self._password_service.set_password(
                    conn, dn, dto.initial_password
                )
                if dto.is_active:
                    self._enable_user(conn, dn)
            except Exception as e:
                raise DirectoryLdapError(f"LDAP create failed: {e}") from e

            # 2) DB + sync-state
            try:
                with transaction.atomic():
                    # Проверяем, существует ли уже пользователь с таким email
                    emp = Employee.objects.filter(email=dto.email).first()
                    if emp:
                        # Обновляем существующего пользователя
                        emp.first_name = dto.first_name
                        emp.last_name = dto.last_name
                        emp.phone_number = dto.phone_e164
                        emp.is_active = dto.is_active
                        emp.is_ldap_managed = True
                        emp._skip_ldap_sync = True
                        emp.save()
                    else:
                        # Создаем нового пользователя
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
                        emp._skip_ldap_sync = True
                        emp.save(update_fields=["password"])

                    # Запись employeeNumber в LDAP для связки через прямую
                    # модификацию. Используем ldap3 напрямую, так как ORM
                    # .save() пытается перестроить DN.
                    from ldap3 import MODIFY_REPLACE

                    conn.modify(
                        dn,
                        {"employeeNumber": [(MODIFY_REPLACE, [str(emp.pk)])]},
                    )
                    guid = None

                    self._touch_state(
                        model="employee",
                        object_pk=emp.pk,
                        ldap_dn=dn,
                        ldap_guid=guid,
                        sync_dir=SyncDirection.LDAP,
                        last_django_modify_ts=timezone.now(),
                    )

                    # TODO: Implement department assignment
                    # DirectoryService был удален, требуется рефакторинг
                    # if dto.department_dn and hasattr(
                    #     emp, "set_active_department"
                    # ):
                    #     dept = Department.objects.filter(
                    #         ldap_group_dn=dto.department_dn
                    #     ).first()
                    #     if dept:
                    #         emp.set_active_department(dept)

                    self._log_operation(
                        "create",
                        model="employee",
                        object_id=emp.pk,
                        dn=dn,
                        success=True,
                    )
            except Exception as e:
                try:
                    if dn:
                        self._hard_delete_user_in_ldap(conn, dn)
                finally:
                    pass
                raise DirectoryDbError(str(e)) from e

            # 3) Post-actions (best effort)
            try:
                if dto.group_cns:
                    sync_user_groups_by_cns_orm(dn, set(dto.group_cns))
                if dto.avatar_bytes:
                    avatar = self._mapper_service.process_avatar(
                        dto.avatar_bytes
                    )
                    if avatar:
                        ldap_user_av = LdapUser.objects.get(dn=dn)
                        ldap_user_av.thumbnail_photo = avatar
                        ldap_user_av.save()
            except Exception:
                self._logger.warning(
                    f"Post-actions failed for user {dn}",
                    exc_info=True,
                )

            return emp

    def update_user(
        self,
        emp: Employee,
        changes: Dict[str, Any],
        group_cns: Optional[List[str]] = None,
        move_to_department_dn: Optional[str] = None,
    ) -> Employee:
        """Обновляет пользователя: сначала LDAP, затем БД.

        Args:
            emp (Employee): Сотрудник, которого обновляем.
            changes (Dict[str, Any]): Поля модели: first_name,
                last_name, email, phone_number, is_active, password,
                avatar_bytes, display_name и т.п.
            group_cns (Optional[List[str]]): Полный набор CN для
                синхронизации членства или None.
            move_to_department_dn (Optional[str]): DN OU,
                куда переместить запись.

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

        # Извлекаем position из changes — обработаем отдельно
        new_position = changes.pop("position", None)
        new_position_id = changes.pop("position_id", None)
        old_position = emp.position

        with _ldap() as conn:
            ldap_changes = dict(changes)
            try:
                result = self._update_user_in_ldap(
                    conn=conn,
                    current_dn=current_dn,
                    model_changes=ldap_changes,
                    move_to_department_dn=move_to_department_dn,
                    group_cns=group_cns,
                    emp_pk=emp.pk,  # Передаём PK для поиска по employeeNumber
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
                            sync_dir=SyncDirection.LDAP,
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

                    # Обновляем position в DB
                    if new_position_id is not None:
                        if emp.position_id != new_position_id:
                            emp.position_id = new_position_id
                            updated_fields.append("position_id")
                    elif new_position is not None:
                        pid = new_position.pk if new_position else None
                        if emp.position_id != pid:
                            emp.position_id = pid
                            updated_fields.append("position_id")

                    if move_to_department_dn and hasattr(
                        emp, "set_active_department"
                    ):
                        from .department_service import DepartmentService

                        dept_svc = DepartmentService()
                        dept = dept_svc._get_department_by_dn(
                            move_to_department_dn
                        )
                        if dept:
                            emp.set_active_department(dept)

                    # Сохраняем аватар в БД, если он был успешно записан в LDAP
                    if saved_avatar_bytes and hasattr(emp, "avatar"):
                        from django.core.files.base import ContentFile

                        filename = f"avatar_{emp.pk}.jpg"
                        emp.avatar.save(
                            filename,
                            ContentFile(saved_avatar_bytes),
                            save=False,
                        )
                        if "avatar" not in updated_fields:
                            updated_fields.append("avatar")

                    if updated_fields:
                        # Устанавливаем флаг чтобы не запустить LDAP sync
                        # повторно
                        emp._skip_ldap_sync = True
                        emp.save(update_fields=list(set(updated_fields)))
            except Exception as e:
                raise DirectoryDbError(str(e)) from e

            # Position group membership sync (best-effort)
            self._sync_position_groups(
                emp,
                old_position,
                new_position,
                new_position_id,
            )

            return emp

    def delete_user(self, emp: Employee) -> None:
        """Удаляет пользователя.

        Порядок: LDAP soft-disable -> DB delete -> LDAP hard delete.

        Args:
            emp (Employee): Удаляемый сотрудник.

        Raises:
            DirectoryLdapError: Ошибка при soft-disable/hard-delete.
            DirectoryDbError: Ошибка при удалении записи в БД.
        """
        try:
            dn: Optional[str] = self._get_employee_dn(emp)
        except DirectoryServiceError:
            dn = None

        # ORM: soft-disable (UAC = disabled + password expired)
        if dn:
            try:
                ldap_user = LdapUser.objects.get(dn=dn)
                ldap_user.user_account_control = (
                    UserAccountControl.DISABLED_PASSWORD_EXPIRED
                )
                ldap_user.save()
                self._log_operation(
                    "soft_disable",
                    model="employee",
                    object_id=emp.pk,
                    dn=dn,
                    success=True,
                )
            except LdapUser.DoesNotExist:
                self._logger.warning(f"User already deleted from LDAP: {dn}")
            except Exception as e:
                raise DirectoryLdapError(
                    f"LDAP soft-disable failed: {e}"
                ) from e

        try:
            with transaction.atomic():
                emp_pk = emp.pk
                emp.delete()
                LdapSyncState.objects.filter(
                    model="employee", object_pk=str(emp_pk)
                ).delete()
                self._log_operation(
                    "delete",
                    model="employee",
                    object_id=emp_pk,
                    dn=dn,
                    success=True,
                )
        except Exception as e:
            raise DirectoryDbError(str(e)) from e

        # ORM: hard delete
        if dn:
            try:
                ldap_user = LdapUser.objects.get(dn=dn)
                ldap_user.delete()
                self._log_operation(
                    "hard_delete",
                    model="employee",
                    object_id=emp_pk,
                    dn=dn,
                    success=True,
                )
            except LdapUser.DoesNotExist:
                self._logger.info(
                    f"User already deleted from LDAP: {dn}"
                )
            except Exception as e:
                raise DirectoryLdapError(
                    f"LDAP hard delete failed: {e}"
                ) from e

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
                model="employee", object_pk__in=id_strs
            )
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

    def _set_password(
        self, conn: Connection, dn: str, new_password: str
    ) -> None:
        """Делегирует в UserPasswordService."""
        self._password_service.set_password(conn, dn, new_password)

    def _enable_user(self, conn: Connection, dn: str) -> None:
        """Включает учётку (UAC=ENABLED) через низкоуровневую модификацию."""
        from ldap3 import MODIFY_REPLACE

        conn.modify(
            dn,
            {
                "userAccountControl": [
                    (MODIFY_REPLACE, [str(UserAccountControl.ENABLED)])
                ]
            },
        )
        if not conn.result["result"] == 0:
            raise DirectoryLdapError(
                f"Failed to enable user {dn}: {conn.result['description']}"
            )

    def _unique_logins(
        self,
        conn: Connection,
        dto: DirectoryUserDTO,
        upn_suffix: str,
    ) -> tuple[str, str]:
        """Делегирует в UserLoginService."""
        return self._login_service.generate_unique_logins(
            first_name=dto.first_name,
            last_name=dto.last_name,
            email=dto.email,
            upn_suffix=upn_suffix,
            ldap_guid=getattr(dto, "ldap_guid", None),
        )

    def _phone_write_attr(self) -> str:
        """Делегирует в UserMapperService."""
        return self._mapper_service._get_phone_write_attribute()

    def _build_user_attrs(
        self,
        dto: DirectoryUserDTO,
        sam: str,
        upn: str,
        cn_text: str,
    ) -> Dict[str, Any]:
        """Делегирует в UserMapperService."""
        return self._mapper_service.build_creation_attributes(
            dto, sam, upn, cn_text
        )

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

    def _sync_position_groups(
        self,
        emp: Employee,
        old_position,
        new_position,
        new_position_id,
    ) -> None:
        """Синхронизирует членство в POS-группах при смене должности.

        Best-effort: ошибки логируются, но не прерывают
        обновление пользователя.
        """
        from ...models import Position
        from .position_service import PositionService
        from .group_service import GroupService

        # Определяем новую должность
        if new_position is None and new_position_id is not None:
            try:
                new_position = Position.objects.get(
                    pk=new_position_id,
                )
            except Position.DoesNotExist:
                new_position = None

        if new_position is None and new_position_id is None:
            # position не передавался в changes
            return

        if old_position == new_position:
            return

        try:
            pos_svc = PositionService(
                group_service=GroupService(),
                user_service=self,
            )
            if old_position and old_position.ldap_group_dn:
                pos_svc.unassign_position(emp, old_position)
            if new_position and new_position.ldap_group_dn:
                pos_svc.assign_position(emp, new_position)
        except Exception:
            logger.warning(
                f"Position group sync failed for employee #{emp.pk}",
                exc_info=True,
            )

    def _create_user_in_ldap(
        self, conn: Connection, dto: DirectoryUserDTO
    ) -> str:
        """Создаёт объект user в LDAP (AD) и возвращает его DN.

        NOTE: Используется low-level ldap3 (conn.add) из-за необходимости:
        - Перебора вариантов CN при коллизиях имён
        - Проверки/создания контейнера (ensure_container_exists)
        django-ldapdb ORM не поддерживает эти сценарии.
        """
        base_dn = (
            dto.department_dn
            or getattr(settings, "LDAP_USERS_BASE", None)
            or getattr(settings, "LDAP_BASE_DN", None)
        )
        if not base_dn:
            raise RuntimeError(
                "Не задан контейнер для создания пользователя "
                "(department_dn / LDAP_USERS_BASE / LDAP_BASE_DN)."
            )
        ensure_container_exists(conn, base_dn)

        upn_suffix = getattr(settings, "LDAP_UPN_SUFFIX", "") or (
            dto.email.split("@", 1)[1]
            if dto.email and "@" in dto.email
            else ""
        )
        if not upn_suffix:
            raise ValueError(
                "Не задан UPN-суффикс (LDAP_UPN_SUFFIX) и его нельзя "
                "вывести из email."
            )

        sam, upn = self._unique_logins(conn, dto, upn_suffix)
        pretty_cn = (
            " ".join(filter(None, [dto.first_name, dto.last_name])).strip()
        ) or sam
        safe_cn = sam
        cn_list = cn_candidates(pretty_cn, safe_cn)

        object_classes = self._mapper_service.get_object_classes_for_user()

        dn = self._try_add_with_cn_list(
            conn, base_dn, object_classes, dto, sam, upn, cn_list
        )
        if dn:
            return dn
        raise RuntimeError(f"LDAP add user failed: {conn.result}")

    def _hard_delete_user_in_ldap(self, conn: Connection, dn: str) -> None:
        """Безусловное удаление user (ignore noSuchObject)."""
        ok = conn.delete(dn)
        if not ok:
            desc = (conn.result or {}).get("description", "")
            if desc not in {LdapErrorCode.NO_SUCH_OBJECT}:
                raise RuntimeError(
                    f"LDAP delete failed for {dn}: {conn.result}"
                )
            self._logger.info(f"User already deleted from LDAP: {dn}")

    def _update_user_in_ldap(
        self,
        conn: Connection,
        current_dn: str,
        model_changes: Dict[str, Any],
        *,
        move_to_department_dn: Optional[str] = None,
        group_cns: Optional[Iterable[str]] = None,
        emp_pk: Optional[int] = None,
        # Employee PK для поиска по employeeNumber.
    ) -> str:
        """Применяет LDAP-изменения к существующему пользователю.

        Возвращает возможный новый DN.

        NOTE: Этот метод слишком большой (~150 строк) и должен быть
        рефакторен в будущем.
        Сейчас просто перенесём как есть для совместимости.

        Args:
            conn: LDAP соединение
            current_dn: Текущий DN пользователя (может быть устаревшим)
            model_changes: Изменения полей
            move_to_department_dn: DN для перемещения
            group_cns: Список групп
            emp_pk: PK Employee для поиска по employeeNumber если DN устарел
        """
        # TODO: DirectoryService был удален, требуется рефакторинг

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

        # 2) Перемещение между OU — обработается в ORM save(),
        #    см. шаг 3-5 ниже (ldap_user.base_dn = ...)

        # 3-5) ORM: UAC + Атрибуты + Аватар (batch через один save)
        try:
            ldap_user = LdapUser.objects.get(dn=dn)
        except LdapUser.DoesNotExist:
            # DN неверный - пытаемся найти пользователя по employeeNumber
            if emp_pk:
                logger.warning(
                    "User not found at DN="
                    f"{dn}, searching by employeeNumber={emp_pk}"
                )
                try:
                    # Поиск через filter с employeeNumber
                    users = LdapUser.objects.filter(
                        employee_number=str(emp_pk)
                    )
                    if users:
                        ldap_user = users[0]
                        dn = ldap_user.dn  # Обновляем DN на реальный
                        logger.info(
                            f"User found at corrected DN={dn}"
                        )
                    else:
                        raise DirectoryLdapError(
                            f"User not found by employeeNumber={emp_pk}. "
                            "User may have been deleted from LDAP."
                        )
                except Exception as e:
                    logger.error(f"Failed to find user by employeeNumber: {e}")
                    raise DirectoryLdapError(
                        "User not found at DN="
                        f"{dn} and search by employeeNumber failed"
                    ) from e
            else:
                raise DirectoryLdapError(
                    f"User not found at DN={dn}. DN in database doesn't "
                    "match LDAP. Please run LDAP sync to fix sync state."
                )

        orm_dirty = False

        # 2) Перемещение между OU через ORM
        # ModifyDnMixin.save() автоматически выполнит modify_dn
        if move_to_department_dn:
            ldap_user.base_dn = move_to_department_dn
            orm_dirty = True

        # 3) UAC
        if is_active_val is not None:
            uac_val = (
                UserAccountControl.ENABLED
                if is_active_val
                else UserAccountControl.DISABLED
            )
            ldap_user.user_account_control = uac_val
            orm_dirty = True

        # 4) Прочие атрибуты
        phone_write = self._phone_write_attr()
        orm_field_map = {
            "first_name": "given_name",
            "last_name": "sn",
            "email": "mail",
            "phone_number": (
                "mobile" if phone_write == "mobile" else "telephone_number"
            ),
            "display_name": "display_name",
        }

        # Запоминаем старый cn для проверки изменения
        old_cn = ldap_user.cn

        for model_key, orm_field in orm_field_map.items():
            if model_key in model_changes:
                val = model_changes[model_key]
                if val or orm_field == "sn":
                    setattr(ldap_user, orm_field, val if val else ".")
                    orm_dirty = True

        # Вычисляем новый cn если изменились имя/фамилия
        new_cn = None
        if "first_name" in model_changes or "last_name" in model_changes:
            parts = []
            given_name_str = get_ldap_str(ldap_user.given_name).strip()
            sn_str = get_ldap_str(ldap_user.sn).strip()

            if given_name_str:
                parts.append(given_name_str)
            if sn_str and sn_str != ".":
                parts.append(sn_str)

            new_cn = (
                " ".join(parts)
                if parts
                else get_ldap_str(ldap_user.sam_account_name)
            )

            if new_cn != old_cn:
                # Устанавливаем cn и displayName —
                # ModifyDnMixin.save() автоматически обработает
                # rename CN через modify_dn (не modify_s)
                ldap_user.cn = new_cn
                ldap_user.display_name = new_cn
                orm_dirty = True

        # 5) Аватар
        avatar_saved = False
        if avatar_bytes:
            avatar = self._mapper_service.process_avatar(avatar_bytes)
            if avatar:
                ldap_user.thumbnail_photo = avatar
                orm_dirty = True
                avatar_saved = True

        if orm_dirty:
            # ModifyDnMixin.save() автоматически:
            # 1) Откатит cn к старому значению
            # 2) Сохранит остальные атрибуты через modify_s
            # 3) Переименует DN через modify_dn
            ldap_user.save()
            # Обновляем dn после возможного rename
            dn = ldap_user.dn

        # 6) Группы (ORM)
        if group_cns is not None:
            sync_user_groups_by_cns_orm(dn, set(group_cns))

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
                model="employee", object_pk=str(employee.pk)
            )
            .values_list("ldap_dn", flat=True)
            .first()
        )

        # Если не найден в LdapSyncState, проверяем поле модели
        if not dn and hasattr(employee, "ldap_dn"):
            dn = employee.ldap_dn

        if not dn:
            raise DirectoryServiceError("Employee has no ldap_dn")
        return dn

    def _move_user_to_base(
        self, conn: Connection, user_dn: str, base_dn: str
    ) -> str:
        """Перемещает пользовательский объект в указанный контейнер.

        NOTE: Используется low-level ldap3 для атомарного move-only
        (без обновления атрибутов). ModifyDnMixin решает ту же задачу
        через ORM (user.base_dn = ...; user.save()), но совмещает
        move с обновлением атрибутов.

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
