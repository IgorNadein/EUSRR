from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Set, Tuple

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.db import transaction
from django.utils import timezone
from employees.models import LdapSyncState
from ldap3 import BASE, MODIFY_ADD, MODIFY_DELETE, MODIFY_REPLACE, SUBTREE, Connection

from ..models import Department, DepartmentRole, Employee, EmployeeDepartment, Position
from .connections import _ldap
from .dn import _move_to_department
from .errors import DirectoryDbError, DirectoryLdapError, DirectoryServiceError
from .groups import sync_user_groups_by_cns
from .helpers import (
    ensure_container_exists,
    is_taken,
    ldap_modify_or_ignore,
    modify_user_attrs,
    read_attrs,
)
from .utils import (
    cn_candidates,
    esc_filter,
    esc_rdn,
    get_guid_str,
    group_type,
    normalize_avatar_to_jpeg,
    rewrite_dn_suffix,
)

UAC_ENABLED = 512
UAC_DISABLED = 514
# ---------------------------- DTOs ---------------------------- #


@dataclass(frozen=True)
class DirectoryUserDTO:
    """DTO для создания пользователя через сервис.

    Attributes:
        first_name (str): Имя.
        last_name (str): Фамилия.
        email (str): Email.
        phone_e164 (Optional[str]): Телефон в формате E.164 или None.
        department_dn (Optional[str]): DN целевого отдела (куда поместить объект).
        group_cns (List[str]): CN групп для членства.
        initial_password (str): Пароль (только в LDAP).
        avatar_bytes (Optional[bytes]): Байты оригинального аватара.
        is_active (bool): Флаг активности (влияет на userAccountControl).
    """

    first_name: str
    last_name: str
    email: str
    phone_e164: Optional[str]
    department_dn: Optional[str]
    group_cns: List[str]
    initial_password: str
    avatar_bytes: Optional[bytes] = None
    is_active: bool = True


@dataclass(frozen=True)
class DirectoryDepartmentDTO:
    """Данные для создания/обновления отдела (OU)."""

    name: str
    description: Optional[str] = None
    head: Optional[Employee] = None


# ------------------------- Сервис LDAP → DB ------------------------- #


class DirectoryService:
    """Высокоуровневый сервис синхронизации LDAP ↔ DB.

    Правило порядка операций:
        1) LDAP
        2) DB (transaction.atomic)
        3) Post-actions (best effort)

    В случае падения БД выполняется best-effort компенсация LDAP, где разумно.
    """

    # ====================== ВСПОМОГАТЕЛЬНЫЕ ХЕЛПЕРЫ ====================== #

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
        st, _ = LdapSyncState.objects.get_or_create(
            model=model, object_pk=str(object_pk)
        )
        st.touch(**touch_kwargs)
        return st

    # ============================ USERS ============================ #

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

                    if dto.department_dn and hasattr(emp, "set_active_department"):
                        dept = self._get_department_by_dn(dto.department_dn)
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
                    sync_user_groups_by_cns(conn, dn, set(dto.group_cns), do_write=True)
                if dto.avatar_bytes:
                    avatar = normalize_avatar_to_jpeg(dto.avatar_bytes, max_kb=100)
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
        old_pos = getattr(emp, "position", None) if hasattr(emp, "position") else None
        new_pos = None
        pos_in_payload = False
        if "position" in changes or "position_id" in changes:
            pos_in_payload = True
            val = changes.pop("position", changes.pop("position_id", None))
            if isinstance(val, Position) or val is None:
                new_pos = val
            elif isinstance(val, int):
                new_pos = Position.objects.filter(pk=val).first()
            else:
                # попробуем id из строки
                try:
                    new_pos = Position.objects.filter(pk=int(val)).first()
                except Exception:
                    new_pos = None
        with _ldap() as conn:
            ldap_changes = dict(changes)
            try:
                new_dn = self._update_user_in_ldap(
                    conn=conn,
                    current_dn=current_dn,
                    model_changes=ldap_changes,
                    move_to_department_dn=move_to_department_dn,
                    group_cns=group_cns,
                )
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
                            emp.position = new_pos  # допускается и None
                            updated_fields.append("position")

                    if move_to_department_dn and hasattr(emp, "set_active_department"):
                        dept = self._get_department_by_dn(move_to_department_dn)
                        if dept:
                            emp.set_active_department(dept)

                    if updated_fields:
                        emp.save(update_fields=list(set(updated_fields)))
            except Exception as e:
                raise DirectoryDbError(str(e)) from e
            try:
                if pos_in_payload and (old_pos != new_pos):
                    # убрать из старой POS_*
                    if old_pos:
                        old_dn = (old_pos.ldap_group_dn or "").strip()
                        if not old_dn:
                            maybe = self.find_group_dn(
                                conn,
                                f"POS_{old_pos.name}",
                                bases=[self._positions_base()],
                            )
                            old_dn = maybe or ""
                        if old_dn:
                            self.remove_group_members(conn, old_dn, [current_dn])

                    # добавить в новую POS_*
                    if new_pos:
                        pos_dn = self._ensure_position_group(conn, new_pos)
                        self.add_group_members(conn, pos_dn, [current_dn])
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
                    raise DirectoryLdapError(f"LDAP soft-disable failed: {e}") from e

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
                    raise DirectoryLdapError(f"LDAP hard delete failed: {e}") from e

    # =========================== DEPARTMENTS =========================== #

    def create_department(self, dto: DirectoryDepartmentDTO) -> Department:
        """Создаёт OU отдела в LDAP и согласованную запись Department в БД.

        Args:
            dto (DirectoryDepartmentDTO): Данные отдела.

        Returns:
            Department: Созданный отдел.

        Raises:
            DirectoryLdapError: Не удалось создать/настроить OU в LDAP.
            DirectoryDbError: Не удалось создать запись в БД (OU будет удалён).
        """
        with _ldap() as conn:
            dept_dn: Optional[str] = None
            group_dn: Optional[str] = None
            try:
                dept_dn = self._ensure_department_ou(conn, dto.name)
                self._set_ou_description(conn, dept_dn, dto.description or "")
                head_dn = None
                if dto.head:
                    try:
                        head_dn = self._get_employee_dn(dto.head)
                    except Exception as e:
                        head_dn = None
                self._set_ou_managed_by(conn, dept_dn, head_dn)
                group_dn = self.create_group(
                    conn,
                    cn=dto.name,
                    parent_dn=dept_dn,
                    description=f"{dto.name} department members",
                    scope="global",
                    security_enabled=True,
                )
            except Exception as e:
                raise DirectoryLdapError(f"LDAP create OU failed: {e}") from e

            try:
                with transaction.atomic():
                    dept = Department.objects.create(
                        name=dto.name,
                        description=dto.description or "",
                        head=dto.head or None,
                        ldap_group_dn=group_dn or "",
                    )
                    self._reconcile_department_group(conn, dept, dept_dn)
                    self._touch_state(
                        model="department",
                        object_pk=dept.pk,
                        ldap_dn=dept_dn,
                        last_django_modify_ts=timezone.now(),
                        sync_dir="django",
                    )
            except Exception as e:
                try:
                    if group_dn:
                        self.delete_group(conn, group_dn)
                    if dept_dn:
                        self._delete_department_ou(conn, dept_dn)
                finally:
                    pass
                raise DirectoryDbError(str(e)) from e

            return dept

    def update_department(
        self, dept: Department, changes: Dict[str, Any]
    ) -> Department:
        """Обновляет OU отдела, одноименную группу (если меняется name) и запись Department."""
        try:
            current_dn = self._get_department_dn(dept)
        except DirectoryServiceError as e:
            raise DirectoryServiceError(f"Не найден DN отдела (sync state): {e}") from e

        new_dn = current_dn

        with _ldap() as conn:
            try:
                self._reconcile_department_group(conn, dept, new_dn)
                name_changed = bool(
                    "name" in changes
                    and changes["name"]
                    and changes["name"] != dept.name
                )
                if name_changed:
                    new_dn = self._rename_department_ou(
                        conn, current_dn, changes["name"]
                    )

                if "description" in changes:
                    self._set_ou_description(conn, new_dn, changes.get("description"))

                if "head" in changes:
                    head = changes.get("head")
                    head_dn = None
                    if head:
                        try:
                            head_dn = self._get_employee_dn(head)
                        except Exception as e:
                            head_dn = None
                    self._set_ou_managed_by(conn, new_dn, head_dn)

                # Переименуем одноименную группу, если меняем название отдела
                if name_changed:
                    try:
                        # 1) если знаем DN группы — переименуем её
                        group_dn = (dept.ldap_group_dn or "").strip()
                        if group_dn:
                            ok = conn.search(
                                group_dn,
                                "(objectClass=group)",
                                search_scope=BASE,
                                attributes=["distinguishedName"],
                            )
                            if ok and conn.entries:
                                try:
                                    new_group_dn = self.rename_group(
                                        conn, group_dn, new_cn=changes["name"]
                                    )
                                except Exception as e:
                                    desc = (getattr(conn, "result", {}) or {}).get(
                                        "description", ""
                                    )
                                    # если группа с новым именем уже есть — просто привяжемся к ней
                                    if desc == "entryAlreadyExists":
                                        maybe = self.find_group_dn(
                                            conn, changes["name"], bases=[new_dn]
                                        )
                                        if maybe:
                                            new_group_dn = maybe
                                        else:
                                            raise
                            else:
                                group_dn = ""  # упала/пропала — попробуем ensure ниже
                        # 2) иначе — ensure в новом OU и затем rename
                        if not group_dn:
                            ensured_dn = self._ensure_department_group(
                                conn, dept, new_dn
                            )
                            try:
                                dep_cn = f"DEP_{changes['name']}"
                                new_group_dn = self.rename_group(
                                    conn, ensured_dn, new_cn=dep_cn
                                )
                            except Exception as e:
                                desc = (getattr(conn, "result", {}) or {}).get(
                                    "description", ""
                                )
                                if desc == "entryAlreadyExists":
                                    maybe = self.find_group_dn(
                                        conn, dep_cn, bases=[new_dn]
                                    )
                                    if maybe:
                                        new_group_dn = maybe
                                    else:
                                        raise
                        if new_group_dn != dept.ldap_group_dn:
                            Department.objects.filter(pk=dept.pk).update(
                                ldap_group_dn=new_group_dn
                            )
                            dept.ldap_group_dn = new_group_dn
                    except Exception as e:
                        raise DirectoryLdapError(
                            f"LDAP rename department group failed: {e}"
                        ) from e

            except Exception as e:
                raise DirectoryLdapError(f"LDAP update OU failed: {e}") from e

            try:
                with transaction.atomic():
                    upd_fields: List[str] = []
                    for k, v in changes.items():
                        if hasattr(dept, k) and getattr(dept, k) != v:
                            setattr(dept, k, v)
                            upd_fields.append(k)
                    if upd_fields:
                        dept.save(update_fields=list(set(upd_fields)))

                    self._touch_state(
                        model="department",
                        object_pk=dept.pk,
                        **(
                            {
                                "ldap_dn": new_dn,
                                "last_django_modify_ts": timezone.now(),
                                "sync_dir": "django",
                            }
                            if new_dn != current_dn
                            else {
                                "last_django_modify_ts": timezone.now(),
                                "sync_dir": "django",
                            }
                        ),
                    )
            except Exception as e:
                raise DirectoryDbError(str(e)) from e

            if new_dn != current_dn:
                try:
                    emp_cnt, st_cnt = self._sync_descendant_dns_after_ou_rename(
                        old_dn=current_dn, new_dn=new_dn
                    )
                except Exception as e:
                    raise DirectoryDbError(f"Cascade DN rewrite failed: {e}") from e
            self._reconcile_department_group(conn, dept, new_dn)
            return dept

    def delete_department(self, dept: Department) -> None:
        """Удаляет отдел: исключает сотрудников из OU, удаляет одноименную группу → OU → запись в БД."""
        with _ldap() as conn:
            try:
                dept_dn = self._get_department_dn(dept)
            except DirectoryServiceError:
                dept_dn = None

            # Сначала — попытка удалить группу отдела
            try:
                if dept.ldap_group_dn:
                    self.delete_group(conn, dept.ldap_group_dn)
            except Exception:
                # не критично — продолжаем
                pass

            if dept_dn:
                try:
                    self._evict_all_users_from_department_ou(conn, dept_dn)
                    self._delete_department_ou(conn, dept_dn)
                except Exception as e:
                    raise DirectoryLdapError(f"LDAP delete OU failed: {e}") from e

            try:
                with transaction.atomic():
                    pk = dept.pk
                    dept.delete()
                    LdapSyncState.objects.filter(
                        model="department", object_pk=str(pk)
                    ).delete()
            except Exception as e:
                raise DirectoryDbError(str(e)) from e

    def add_member(self, dept: Department, employee: Employee) -> None:
        """Добавляет сотрудника в OU отдела и в одноименную группу отдела."""
        emp_dn = self._get_employee_dn(employee)
        with _ldap() as conn:
            # ensure dept OU
            try:
                dept_dn = None
                try:
                    dept_dn = self._get_department_dn(dept)
                except DirectoryServiceError:
                    dept_dn = None
                ensured_dn = self._ensure_department_ou(conn, dept.name)
                if not dept_dn or dept_dn != ensured_dn:
                    self._touch_state(
                        model="department",
                        object_pk=dept.pk,
                        ldap_dn=ensured_dn,
                        last_django_modify_ts=timezone.now(),
                        sync_dir="auto",
                    )
                dept_dn = ensured_dn
            except Exception as e:
                raise DirectoryLdapError(f"LDAP ensure OU failed: {e}") from e

            # MOVE, если нужно
            _, emp_parent = self._split_rdn_parent(emp_dn)
            if emp_parent != dept_dn:
                new_emp_dn = _move_to_department(conn, emp_dn, dept_dn)
                try:
                    self._touch_state(
                        model="employee",
                        object_pk=employee.pk,
                        ldap_dn=new_emp_dn,
                        sync_dir="ldap",
                    )
                    emp_dn = new_emp_dn
                except Exception as e:
                    raise DirectoryDbError(f"Failed to save new DN in DB: {e}") from e

            # ensure dept group & add member
            try:
                group_dn = self._ensure_department_group(conn, dept, dept_dn)
                if not group_dn:
                    raise RuntimeError("_ensure_department_group returned empty DN")

                self.add_group_members(conn, group_dn, [emp_dn])
            except Exception as e:
                raise DirectoryLdapError(
                    f"LDAP add to department group failed: {e}"
                ) from e

            # DB link
            try:
                with transaction.atomic():
                    link, _ = EmployeeDepartment.objects.get_or_create(
                        employee_id=employee.id,
                        department_id=dept.id,
                        defaults={
                            "is_active": True,
                            "date_from": timezone.now().date(),
                        },
                    )
                    self._reconcile_department_group(conn, dept)
                    updates = {}
                    if not link.is_active:
                        updates["is_active"] = True
                    if not link.date_from:
                        updates["date_from"] = timezone.now().date()
                    if updates:
                        EmployeeDepartment.objects.filter(pk=link.pk).update(**updates)
            except Exception as e:
                raise DirectoryDbError(str(e)) from e

    def remove_member(self, dept: Department, employee: Employee) -> None:
        """Удаляет сотрудника из отдела: исключение из группы отдела → MOVE в Users OU → удаление линка."""
        if dept.head_id == employee.id:
            raise DirectoryServiceError("Нельзя удалить руководителя отдела")

        try:
            emp_dn = self._get_employee_dn(employee)
        except DirectoryServiceError:
            emp_dn = None

        with _ldap() as conn:
            # попытаться снять членство в группе отдела (best-effort, без создания групп)
            try:
                grp_dn = (dept.ldap_group_dn or "").strip()
                if grp_dn and emp_dn:
                    ok = conn.search(
                        search_base=grp_dn,
                        search_filter="(objectClass=group)",
                        search_scope=BASE,
                        attributes=["distinguishedName"],
                    )
                    if ok and conn.entries:
                        self.remove_group_members(conn, grp_dn, [emp_dn])
            except Exception:
                pass  # идём дальше независимо от ошибок

            # MOVE в Users base
            if emp_dn:
                users_base = getattr(settings, "LDAP_USERS_BASE", None) or getattr(
                    settings, "LDAP_USER_BASE", None
                )
                if not users_base:
                    raise RuntimeError("LDAP_USERS_BASE is not configured")
                try:
                    ensure_container_exists(conn, users_base)
                    new_dn = self._move_user_to_base(conn, emp_dn, users_base)
                    self._touch_state(
                        model="employee",
                        object_pk=employee.id,
                        ldap_dn=new_dn,
                        sync_dir="ldap",
                    )
                except Exception as e:
                    raise DirectoryLdapError(
                        f"LDAP move to Users OU failed: {e}"
                    ) from e

            # DB unlink
            try:
                with transaction.atomic():
                    EmployeeDepartment.objects.filter(
                        employee_id=employee.id, department_id=dept.id
                    ).delete()
            except Exception as e:
                raise DirectoryDbError(str(e)) from e

    def set_head(self, dept: Department, head: Optional[Employee]) -> Department:
        """Назначает/снимает руководителя отдела: LDAP managedBy → DB.head.

        Args:
            dept (Department): Модель отдела.
            head (Optional[Employee]): Новый руководитель или None (снятие).

        Returns:
            Department: Обновлённая модель отдела.

        Raises:
            DirectoryServiceError: Если не удаётся определить DN объекта.
            DirectoryLdapError: Ошибка при записи в LDAP.
            DirectoryDbError: Ошибка при сохранении в БД.
        """
        with _ldap() as conn:
            # ensure/get dept OU + sync
            try:
                dept_dn = None
                try:
                    dept_dn = self._get_department_dn(dept)
                except DirectoryServiceError:
                    dept_dn = None
                ensured_dn = self._ensure_department_ou(conn, dept.name)
                if not dept_dn or dept_dn != ensured_dn:
                    self._touch_state(
                        model="department",
                        object_pk=dept.pk,
                        ldap_dn=ensured_dn,
                        last_django_modify_ts=timezone.now(),
                        sync_dir="auto",
                    )
                dept_dn = ensured_dn
            except Exception as e:
                raise DirectoryLdapError(
                    f"LDAP ensure/get department OU failed: {e}"
                ) from e

            head_dn: Optional[str] = None
            if head is not None:
                head_dn = self._get_employee_dn(head)
                if not head_dn:
                    raise DirectoryServiceError("Head has no ldap_dn")

            try:
                self._set_ou_managed_by(conn, dept_dn, head_dn)
            except Exception as e:
                raise DirectoryLdapError(f"LDAP set managedBy failed: {e}") from e

            try:
                with transaction.atomic():
                    dept.head = head
                    dept.save(update_fields=["head"])
            except Exception as e:
                raise DirectoryDbError(str(e)) from e
            self._reconcile_department_group(conn, dept, dept_dn)

            return dept

    def set_member_role(
        self, dept: Department, employee: Employee, role: Optional[DepartmentRole]
    ) -> None:
        """Меняет роль участника. (Опц.) синхронизирует LDAP-группы Roles.

        Args:
            dept (Department): Отдел.
            employee (Employee): Сотрудник.
            role (Optional[DepartmentRole]): Новая роль или None.
        """
        # DB
        try:
            with transaction.atomic():
                link = EmployeeDepartment.objects.get(
                    employee_id=employee.id, department_id=dept.id
                )
                link.role = role
                link.save(update_fields=["role"])
        except EmployeeDepartment.DoesNotExist as e:
            raise DirectoryDbError("Employee is not a member of this department") from e
        except Exception as e:
            raise DirectoryDbError(str(e)) from e

        # LDAP группы (best-effort с эскалацией ошибок по требованиям)
        try:
            if role:
                user_dn = self._get_employee_dn(employee)
                dept_dn = self._get_department_dn(dept)
                roles_base = f"OU=Roles,{dept_dn}"
                with _ldap() as conn:
                    sync_user_groups_by_cns(
                        conn,
                        user_dn,
                        {role.name},
                        extra_bases=[roles_base],
                        do_write=True,
                    )
        except DirectoryServiceError:
            # DN не найден — LDAP часть пропускаем; БД уже обновлена
            pass
        except Exception as e:
            raise DirectoryLdapError(f"LDAP roles sync failed: {e}") from e

    # =========================== POSITIONS =========================== #

    def reconcile_position(self, pos: Position) -> str:
        """Публичный метод — открыть соединение и привести POS к консистентности."""
        with _ldap() as conn:
            return self._reconcile_position(conn, pos)

    def assign_position(self, employee: Employee, position: Position) -> None:
        """
        Добавляет сотрудника в POS-группу должности и убеждается, что вложения POS в целевые группы актуальны.
        """
        emp_dn = self._get_employee_dn(employee)
        with _ldap() as conn:
            pos_dn = self._ensure_position_group(conn, position)
            self.add_group_members(conn, pos_dn, [emp_dn])
            # вложения можно обновлять best-effort, не обязательно каждый раз
            try:
                self._reconcile_position_nesting(conn, position)
            except Exception:
                pass

    def unassign_position(self, employee: Employee, position: Position) -> None:
        """
        Удаляет сотрудника из POS-группы должности.
        """
        try:
            emp_dn = self._get_employee_dn(employee)
        except DirectoryServiceError:
            emp_dn = None
        if not emp_dn:
            return
        with _ldap() as conn:
            pos_dn = self._ensure_position_group(conn, position)
            self.remove_group_members(conn, pos_dn, [emp_dn])

    def delete_position_group(self, position: Position) -> None:
        """
        Best-effort: снять POS-группу из всех правовых групп и удалить её.
        """
        with _ldap() as conn:
            dn = (position.ldap_group_dn or "").strip()
            if not dn:
                return
            # снять вложения
            bases = [
                b
                for b in [
                    getattr(settings, "LDAP_GROUPS_BASE", None),
                    getattr(settings, "LDAP_BASE_DN", None),
                ]
                if b
            ]
            for base in bases:
                ok = conn.search(
                    search_base=base,
                    search_filter=f"(&(objectClass=group)(member={esc_filter(dn)}))",
                    search_scope=SUBTREE,
                    attributes=["distinguishedName"],
                )
                if ok and conn.entries:
                    for e in conn.entries:
                        self.remove_group_members(conn, str(e.entry_dn), [dn])
            # удалить саму POS-группу
            try:
                self.delete_group(conn, dn)
            except Exception:
                pass

    # ======================== GROUPS (DRY-версия) ======================== #

    def create_group(
        self,
        conn: Connection,
        cn: str,
        parent_dn: Optional[str] = None,
        *,
        description: Optional[str] = None,
        scope: str = "global",
        security_enabled: bool = True,
    ) -> str:
        """Создаёт группу в LDAP под указанным контейнером.

        Args:
            conn (Connection): Подключение LDAP.
            cn (str): Имя группы (CN).
            parent_dn (Optional[str]): Контейнер для группы; если None — settings.LDAP_GROUPS_BASE.
            description (Optional[str]): Описание.
            scope (str): 'global' | 'domain_local' | 'universal'.
            security_enabled (bool): Флаг безопасности.

        Returns:
            str: DN созданной (или существующей) группы.

        Raises:
            RuntimeError: Если базовый контейнер не задан или операция add завершилась ошибкой.
        """
        base = parent_dn or getattr(settings, "LDAP_GROUPS_BASE", None)
        if not base:
            raise RuntimeError(
                "LDAP_GROUPS_BASE is not configured and parent_dn is not provided"
            )

        dn = f"CN={esc_rdn(cn)},{base}"
        attrs: Dict[str, Any] = {
            "cn": cn,
            "sAMAccountName": cn,
            "groupType": group_type(scope, security_enabled),
        }
        if description:
            attrs["description"] = description

        ok = conn.add(dn, ["top", "group"], attrs)
        if not ok and (conn.result or {}).get("description") != "entryAlreadyExists":
            raise RuntimeError(f"LDAP add group failed: {conn.result}")
        return dn

    def delete_group(self, conn: Connection, group_dn: str) -> None:
        """Удаляет группу по DN (игнорирует noSuchObject)."""
        ok = conn.delete(group_dn)
        if not ok and (conn.result or {}).get("description") not in {"noSuchObject"}:
            raise RuntimeError(f"LDAP delete group failed: {conn.result}")

    def rename_group(self, conn: Connection, group_dn: str, new_cn: str) -> str:
        """Переименовывает группу (modify_dn)."""
        new_rdn = f"CN={esc_rdn(new_cn)}"
        ok = conn.modify_dn(group_dn, new_rdn)
        if not ok:
            raise RuntimeError(f"LDAP rename group failed: {conn.result}")
        base = ",".join(group_dn.split(",")[1:])
        return f"{new_rdn},{base}"

    def set_group_description(
        self, conn: Connection, group_dn: str, description: Optional[str]
    ) -> None:
        """Ставит/очищает description."""
        changes = (
            {"description": [(MODIFY_REPLACE, [description])]}
            if description
            else {"description": [(MODIFY_DELETE, [])]}
        )
        ldap_modify_or_ignore(conn, group_dn, changes, {"noSuchAttribute"})

    def sync_groups_catalog(
        self, *, throttle_seconds: int = 60, delete_absent: bool = False
    ) -> int:
        """
        Тянет группы из AD под LDAP_GROUPS_BASE и гарантирует их наличие в Django Group.
        Возвращает количество созданных групп. Обновляет LdapSyncState(model='group').
        Троттлит запросы к AD не чаще, чем раз в throttle_seconds.
        """
        base = getattr(settings, "LDAP_GROUPS_BASE", None) or getattr(
            settings, "LDAP_BASE_DN", None
        )
        if not base:
            return 0

        # простая защита от шторминга
        now = int(time.time())
        last = cache.get("ad_groups_sync_last_ts") or 0
        if throttle_seconds and now - last < throttle_seconds:
            return 0
        if not cache.add("ad_groups_sync_lock", "1", timeout=throttle_seconds or 30):
            return 0

        created = 0
        try:
            with _ldap() as conn:
                ok = conn.search(
                    search_base=base,
                    search_filter="(objectClass=group)",  # при желании сузить до security: (groupType:1.2.840.113556.1.4.803:=2147483648)
                    search_scope=SUBTREE,
                    attributes=["cn", "objectGUID"],
                )
                if not ok:
                    return 0

                # AD → {name_lower: (CN, DN, GUID)}
                ad_index = {}
                for e in conn.entries:
                    cn = str(getattr(e, "cn", "")) or ""
                    if not cn:
                        continue
                    dn = str(e.entry_dn)
                    guid = get_guid_str({"objectGUID": getattr(e, "objectGUID", None)})
                    ad_index[cn.lower()] = (cn, dn, guid)

                # существующие группы в Django (без дублей по регистру)
                existing = {g.name.lower(): g for g in Group.objects.all()}

                for key, (cn, dn, guid) in ad_index.items():
                    g = existing.get(key)
                    if not g:
                        g = Group.objects.create(name=cn)
                        created += 1
                        existing[key] = g
                    # фиксируем DN/GUID в sync-state (не нужен отдельный столбец в Group)
                    self._touch_state(
                        model="group",
                        object_pk=g.pk,
                        ldap_dn=dn,
                        ldap_guid=guid,
                        sync_dir="ldap",
                        last_django_modify_ts=timezone.now(),
                    )

                if delete_absent:
                    # по умолчанию НЕ удаляем отсутствующие в AD, чтобы не снести права в Django
                    for key, g in list(existing.items()):
                        if key not in ad_index:
                            # например, можно только пометить/залогировать
                            pass

                cache.set("ad_groups_sync_last_ts", now, timeout=24 * 3600)
                return created
        finally:
            cache.delete("ad_groups_sync_lock")

    def _modify_group_members(
        self, conn: Connection, group_dn: str, op: int, members: List[str]
    ) -> None:
        """Применяет операцию к членству группы (DRY-хелпер).

        Args:
            conn (Connection): Подключение LDAP.
            group_dn (str): DN группы.
            op (int): MODIFY_ADD | MODIFY_DELETE | MODIFY_REPLACE.
            members (List[str]): Список DN участников.

        Raises:
            RuntimeError: При ошибке modify вне допустимых кейсов.
        """
        if not members and op in (MODIFY_ADD, MODIFY_DELETE):
            return
        ignore = (
            {"typeOrValueExists"}
            if op == MODIFY_ADD
            else (
                {"noSuchAttribute", "noSuchObject"}
                if op == MODIFY_DELETE
                else {"noSuchAttribute"}
            )
        )
        ldap_modify_or_ignore(conn, group_dn, {"member": [(op, members or [])]}, ignore)

    def add_group_members(
        self, conn: Connection, group_dn: str, member_dns: List[str]
    ) -> None:
        """Добавляет участников (member ADD)."""
        self._modify_group_members(conn, group_dn, MODIFY_ADD, member_dns)

    def remove_group_members(
        self, conn: Connection, group_dn: str, member_dns: List[str]
    ) -> None:
        """Удаляет участников (member DELETE)."""
        self._modify_group_members(conn, group_dn, MODIFY_DELETE, member_dns)

    def replace_group_members(
        self, conn: Connection, group_dn: str, exact_member_dns: List[str]
    ) -> None:
        """Полная замена состава группы."""
        self._modify_group_members(conn, group_dn, MODIFY_REPLACE, exact_member_dns)

    def list_group_members(self, conn: Connection, group_dn: str) -> List[str]:
        """Возвращает DN всех участников группы."""
        ok = conn.search(
            search_base=group_dn,
            search_filter="(objectClass=group)",
            search_scope=BASE,
            attributes=["member"],
        )
        if not ok or not conn.entries:
            return []
        entry = conn.entries[0]
        vals = getattr(getattr(entry, "member", None), "values", None)
        return list(vals) if vals else []

    def find_group_dn(
        self, conn: Connection, cn: str, bases: Optional[List[str]] = None
    ) -> Optional[str]:
        """Ищет DN группы по CN в заданных базах."""
        bases = list(bases or [])
        if not bases:
            gb = getattr(settings, "LDAP_GROUPS_BASE", None)
            if gb:
                bases.append(gb)
        for base in bases:
            ok = conn.search(
                search_base=base,
                search_filter=f"(cn={esc_filter(cn)})",
                search_scope=SUBTREE,
                attributes=["distinguishedName"],
            )
            if ok and conn.entries:
                return str(conn.entries[0].entry_dn)
        return None

    def _set_password(self, conn: Connection, dn: str, new_password: str) -> None:
        """Меняет пароль пользователя в AD (control)."""
        ok = conn.extend.microsoft.modify_password(dn, new_password)
        if not ok:
            msg = conn.result or {}
            raw = (msg.get("message") or "").upper()
            if "0000052D" in raw:
                raise RuntimeError("Пароль не соответствует политике сложности AD")
            raise RuntimeError(f"LDAP set password failed: {msg}")

    def _enable_user(self, conn: Connection, dn: str) -> None:
        """Включает учётку (UAC=512)."""
        ldap_modify_or_ignore(
            conn, dn, {"userAccountControl": [(MODIFY_REPLACE, [UAC_ENABLED])]}, set()
        )

    def _unique_logins(
        self, conn: Connection, dto: DirectoryUserDTO, upn_suffix: str
    ) -> tuple[str, str]:
        """Генерирует уникальные sAMAccountName и UPN."""
        from .utils import build_logins_for_user

        sam, upn = build_logins_for_user(
            first_name=dto.first_name,
            last_name=dto.last_name,
            email=dto.email,
            upn_suffix=upn_suffix,
            is_taken_sam=lambda s: is_taken(conn, attributes={"sAMAccountName": s}),
            is_taken_upn=lambda u: is_taken(conn, attributes={"userPrincipalName": u}),
            guid=getattr(dto, "ldap_guid", None),
        )
        if not sam or not upn:
            raise ValueError("Не удалось сгенерировать уникальные sAMAccountName/UPN")
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

    def _update_user_in_ldap(
        self,
        conn: Connection,
        current_dn: str,
        model_changes: Dict[str, Any],
        *,
        move_to_department_dn: Optional[str] = None,
        group_cns: Optional[Iterable[str]] = None,
    ) -> str:
        """Применяет LDAP-изменения к существующему пользователю и возвращает (возможный новый) DN."""
        if not isinstance(current_dn, str) or not current_dn.strip():
            raise TypeError("current_dn должен быть непустой строкой")
        if not isinstance(model_changes, dict):
            raise TypeError("model_changes должен быть словарём")

        dn = current_dn

        # 0) пароль
        new_password = model_changes.pop("password", None)
        if new_password:
            self._set_password(conn, dn, new_password)

        # 1) MOVE
        if move_to_department_dn:
            dn = _move_to_department(conn, dn, move_to_department_dn)

        # 2) is_active → UAC
        if "is_active" in model_changes:
            active = bool(model_changes.pop("is_active"))
            if active:
                self._enable_user(conn, dn)
            else:
                modify_user_attrs(
                    conn, dn, {"userAccountControl": UAC_DISABLED}, do_write=True
                )

        # 3) аватар
        ldap_attrs: Dict[str, Any] = {}
        avatar_bytes = model_changes.pop("avatar_bytes", None)
        if avatar_bytes:
            jpeg = normalize_avatar_to_jpeg(avatar_bytes, max_kb=100)
            if jpeg:
                ldap_attrs["thumbnailPhoto"] = jpeg

        # 4) маппинг полей
        given_attr = getattr(settings, "LDAP_ATTR_GIVENNAME", "givenName")
        sn_attr = getattr(settings, "LDAP_ATTR_SN", "sn")
        mail_attr = getattr(settings, "LDAP_ATTR_MAIL", "mail")
        disp_attr = getattr(settings, "LDAP_ATTR_DISPLAYNAME", "displayName")
        phone_attr = self._phone_write_attr()

        attr_map = {
            "first_name": given_attr,
            "last_name": sn_attr,
            "email": mail_attr,
            "phone_number": phone_attr,
            "display_name": disp_attr,
        }

        first_provided = "first_name" in model_changes
        last_provided = "last_name" in model_changes
        explicit_display = model_changes.get("display_name")

        for key in list(model_changes.keys()):
            if key in attr_map:
                val = model_changes.pop(key)
                if val not in (None, ""):
                    ldap_attrs[attr_map[key]] = val

        if not explicit_display and (first_provided or last_provided):
            need: List[str] = []
            if not first_provided:
                need.append(given_attr)
            if not last_provided:
                need.append(sn_attr)
            current_vals: Dict[str, Optional[str]] = (
                read_attrs(conn, dn, need) if need else {}
            )
            new_first = (
                ldap_attrs.get(given_attr)
                if first_provided
                else (current_vals.get(given_attr) or "")
            )
            new_last = (
                ldap_attrs.get(sn_attr)
                if last_provided
                else (current_vals.get(sn_attr) or "")
            )
            display_val = " ".join(
                p for p in (str(new_first).strip(), str(new_last).strip()) if p
            ).strip()
            if display_val:
                ldap_attrs[disp_attr] = display_val

        if ldap_attrs:
            modify_user_attrs(conn, dn, ldap_attrs, do_write=True)

        # 6) rename CN
        desired_cn: Optional[str] = None
        if isinstance(explicit_display, str) and explicit_display.strip():
            desired_cn = explicit_display.strip()
        elif first_provided or last_provided:
            if (
                disp_attr in ldap_attrs
                and isinstance(ldap_attrs[disp_attr], str)
                and ldap_attrs[disp_attr].strip()
            ):
                desired_cn = ldap_attrs[disp_attr].strip()
            else:
                cur_vals = read_attrs(conn, dn, [given_attr, sn_attr])
                f = ldap_attrs.get(given_attr) or (cur_vals.get(given_attr) or "")
                s = ldap_attrs.get(sn_attr) or (cur_vals.get(sn_attr) or "")
                desired_cn = (
                    " ".join(p for p in (str(f).strip(), str(s).strip()) if p).strip()
                    or None
                )

        if desired_cn:
            current_rdn = dn.split(",", 1)[0]
            current_cn = (
                current_rdn.split("=", 1)[1] if "=" in current_rdn else current_rdn
            )
            if desired_cn != current_cn:
                sam = (
                    read_attrs(conn, dn, ["sAMAccountName"]).get("sAMAccountName")
                    or desired_cn
                )
                candidates = cn_candidates(desired_cn, sam)
                base = ",".join(dn.split(",")[1:])
                for cn_txt in candidates:
                    new_rdn = f"CN={esc_rdn(cn_txt)}"
                    if conn.modify_dn(dn, new_rdn):
                        dn = f"{new_rdn},{base}"
                        break
                    desc = (conn.result or {}).get("description", "")
                    if desc not in {
                        "entryAlreadyExists",
                        "invalidDNSyntax",
                    } and "BAD_ATT_SYNTAX" not in (conn.result or {}).get(
                        "message", ""
                    ):
                        raise RuntimeError(
                            f"LDAP rename (modify_dn) failed: {conn.result}"
                        )
                else:
                    raise RuntimeError(
                        f"LDAP rename failed for all CN candidates: {conn.result}"
                    )

        # 7) группы
        if group_cns is not None:
            sync_user_groups_by_cns(conn, dn, set(group_cns), do_write=True)

        return dn

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
            dto.email.split("@", 1)[1] if dto.email and "@" in dto.email else ""
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

    def _ensure_department_ou(self, conn: Connection, name: str) -> str:
        """Гарантирует наличие OU отдела + OU=Roles."""
        base = getattr(settings, "LDAP_DEPARTMENTS_BASE", None)
        if not base:
            raise RuntimeError("LDAP_DEPARTMENTS_BASE is not configured")
        dn = f"OU={name},{base}"
        ok = conn.search(dn, "(objectClass=organizationalUnit)", search_scope=BASE)
        if ok and conn.entries:
            return dn
        ok = conn.add(dn, ["top", "organizationalUnit"])
        if not ok:
            raise RuntimeError(f"LDAP add OU failed: {conn.result}")
        conn.add(f"OU=Roles,{dn}", ["top", "organizationalUnit"])
        return dn

    def _split_rdn_parent(self, dn: str) -> Tuple[str, str]:
        """Делит DN на (RDN, parentDN)."""
        parts = dn.split(",", 1)
        if len(parts) != 2:
            raise DirectoryServiceError(f"Malformed DN: {dn}")
        return parts[0], parts[1]

    def _rename_department_ou(
        self, conn: Connection, dept_dn: str, new_name: str
    ) -> str:
        """Переименовывает OU отдела и возвращает новый DN."""
        cn = f"OU={new_name}"
        ok = conn.modify_dn(dept_dn, cn)
        if not ok:
            raise RuntimeError(f"LDAP rename OU failed: {conn.result}")
        base = ",".join(dept_dn.split(",")[1:])
        return f"{cn},{base}"

    def _set_ou_managed_by(
        self, conn: Connection, dept_dn: str, head_dn: Optional[str]
    ) -> None:
        """Устанавливает/очищает managedBy у OU в AD (идемпотентно и с no-op при пустом состоянии).

        Args:
            conn (Connection): LDAP соединение.
            dept_dn (str): DN OU отдела.
            head_dn (Optional[str]): DN руководителя или None.
        """
        if not dept_dn:
            raise DirectoryServiceError("dept_dn пуст")

        if not conn.search(
            search_base=dept_dn,
            search_filter="(objectClass=organizationalUnit)",
            search_scope=BASE,
            attributes=["managedBy", "allowedAttributes"],
        ):
            raise DirectoryServiceError(f"OU not found: {dept_dn}")

        ou_entry = conn.entries[0]
        current_vals = list(map(str, getattr(ou_entry, "managedBy", []) or []))

        if head_dn:
            if not conn.search(
                search_base=head_dn,
                search_filter="(objectClass=*)",
                search_scope=BASE,
                attributes=["distinguishedName"],
            ):
                raise DirectoryServiceError(f"Head DN not found: {head_dn}")

        def _norm(x: Optional[str]) -> str:
            return (x or "").strip().lower()

        target = _norm(head_dn)
        current = _norm(current_vals[0] if current_vals else None)
        if target == current:
            return

        if head_dn is None:
            if not current_vals:
                return
            op, values = MODIFY_DELETE, []
        else:
            op, values = (
                (MODIFY_ADD, [head_dn])
                if not current_vals
                else (MODIFY_REPLACE, [head_dn])
            )

        ok = conn.modify(dept_dn, {"managedBy": [(op, values)]})
        if not ok:
            res = dict(conn.result)
            if res.get("result") == 16 and op == MODIFY_DELETE:  # noSuchAttribute
                return
            raise RuntimeError(f"LDAP modify managedBy failed: {res}")

    def _set_ou_description(
        self, conn: Connection, dept_dn: str, description: Optional[str]
    ) -> None:
        """Ставит/очищает description у OU."""
        changes = (
            {"description": [(MODIFY_REPLACE, [description])]}
            if description
            else {"description": [(MODIFY_DELETE, [])]}
        )
        ldap_modify_or_ignore(conn, dept_dn, changes, {"noSuchAttribute"})

    def _delete_department_ou(self, conn: Connection, dept_dn: str) -> None:
        """Удаляет OU (ignore noSuchObject)."""
        ok = conn.delete(dept_dn)
        if not ok and (conn.result or {}).get("description") not in {"noSuchObject"}:
            raise RuntimeError(f"LDAP delete OU failed: {conn.result}")

    def _evict_all_users_from_department_ou(
        self, conn: Connection, dept_dn: str
    ) -> None:
        """Перемещает всех пользователей из OU отдела в Users base."""
        users_base = getattr(settings, "LDAP_USERS_BASE", None) or getattr(
            settings, "LDAP_USER_BASE", None
        )
        if not users_base:
            raise RuntimeError("LDAP_USERS_BASE is not configured")
        ok = conn.search(
            dept_dn,
            "(&(objectCategory=person)(objectClass=user))",
            attributes=["distinguishedName"],
        )
        if ok and conn.entries:
            for e in conn.entries:
                old_dn = str(e.entry_dn)
                new_dn = self._move_user_to_base(conn, old_dn, users_base)
                # best effort — обновляем sync-state, если найдём локальный PK
                try:
                    emp_pk = (
                        LdapSyncState.objects.filter(
                            model="employee", ldap_dn__iexact=old_dn
                        )
                        .values_list("object_pk", flat=True)
                        .first()
                    )
                    if emp_pk:
                        self._touch_state(
                            model="employee",
                            object_pk=emp_pk,
                            ldap_dn=new_dn,
                            sync_dir="ldap",
                        )
                except Exception:
                    pass

    def _move_user_to_base(self, conn: Connection, user_dn: str, base_dn: str) -> str:
        """Перемещает пользовательский объект в указанный контейнер."""
        rdn = user_dn.split(",", 1)[0]
        ok = conn.modify_dn(user_dn, rdn, new_superior=base_dn)
        if not ok:
            raise RuntimeError(f"LDAP move user to base failed: {conn.result}")
        return f"{rdn},{base_dn}"

    def _get_department_dn(self, dept: Department) -> str:
        """Возвращает DN OU отдела из LdapSyncState.

        Args:
            dept (Department): Экземпляр отдела.

        Returns:
            str: Полный DN OU отдела.

        Raises:
            DirectoryServiceError: Если DN отсутствует.
        """
        dn = (
            LdapSyncState.objects.filter(model="department", object_pk=str(dept.pk))
            .values_list("ldap_dn", flat=True)
            .first()
        )
        if not dn:
            raise DirectoryServiceError("Department has no ldap_dn in sync state")
        return dn

    def _get_department_by_dn(self, dept_dn: str) -> Optional[Department]:
        """Возвращает Department по DN из LdapSyncState."""
        if not dept_dn:
            return None
        pk = (
            LdapSyncState.objects.filter(model="department", ldap_dn__iexact=dept_dn)
            .values_list("object_pk", flat=True)
            .first()
        )
        if not pk:
            return None
        return Department.objects.filter(pk=pk).first()

    def _get_employee_dn(self, employee: Employee) -> str:
        """Возвращает DN сотрудника (из LdapSyncState)."""
        dn = (
            LdapSyncState.objects.filter(model="employee", object_pk=str(employee.pk))
            .values_list("ldap_dn", flat=True)
            .first()
        )
        if not dn:
            raise DirectoryServiceError("Employee has no ldap_dn")
        return dn

    def _sync_descendant_dns_after_ou_rename(
        self, *, old_dn: str, new_dn: str
    ) -> Tuple[int, int]:
        """Переписывает хвост DN у всех записей sync-state сотрудников после переименования OU.

        Returns:
            Tuple[int, int]: (updated_employees_in_model, updated_states). Первый элемент всегда 0.
        """
        updated_emp = 0
        updated_state = 0
        now = timezone.now()

        if old_dn.strip().lower() == new_dn.strip().lower():
            return updated_emp, updated_state

        qs = LdapSyncState.objects.filter(
            model="employee", ldap_dn__iendswith=old_dn
        ).only("id", "ldap_dn", "object_pk")
        for st in qs.iterator(chunk_size=1000):
            current_dn = st.ldap_dn or ""
            new_st_dn = rewrite_dn_suffix(current_dn, old_dn, new_dn)
            if new_st_dn and new_st_dn != current_dn:
                st.touch(ldap_dn=new_st_dn, last_django_modify_ts=now, sync_dir="auto")
                updated_state += 1
        return updated_emp, updated_state

    def _ensure_department_group(self, conn, dept: Department, dept_dn: str) -> str:
        """
        Гарантирует наличие группы отдела с CN = 'DEP_<ИмяОтдела>' внутри OU отдела.
        При необходимости переименовывает/создаёт и синхронизирует dept.ldap_group_dn.
        """
        name = (dept.name or "").strip()
        if not name:
            raise ValueError("Department.name is empty")

        expected_cn = f"DEP_{name}"
        expected_rdn = f"CN={esc_rdn(expected_cn)}"

        # 0) если в БД есть DN — проверим и при необходимости переименуем
        saved_dn = (dept.ldap_group_dn or "").strip()
        if saved_dn:
            ok = conn.search(
                search_base=saved_dn,
                search_filter="(objectClass=group)",
                search_scope=BASE,
                attributes=["distinguishedName"],
            )
            if ok and conn.entries:
                cur_rdn = saved_dn.split(",", 1)[0]
                if cur_rdn != expected_rdn:
                    if not conn.modify_dn(saved_dn, expected_rdn):
                        raise RuntimeError(f"LDAP rename group failed: {conn.result}")
                    base = ",".join(saved_dn.split(",")[1:])
                    new_dn = f"{expected_rdn},{base}"
                else:
                    new_dn = saved_dn

                if new_dn != dept.ldap_group_dn:
                    Department.objects.filter(pk=dept.pk).update(ldap_group_dn=new_dn)
                    dept.ldap_group_dn = new_dn
                return new_dn

        # 1) поиск по CN внутри OU отдела
        ok = conn.search(
            search_base=dept_dn,
            search_filter=f"(&(objectClass=group)(cn={esc_filter(expected_cn)}))",
            attributes=["distinguishedName"],
        )
        if ok and conn.entries:
            dn = str(conn.entries[0].entry_dn)
            if dn != saved_dn:
                Department.objects.filter(pk=dept.pk).update(ldap_group_dn=dn)
                dept.ldap_group_dn = dn
            return dn

        # 2) если осталась старая группа с «не тем» CN — найти и переименовать
        if saved_dn:
            old_rdn = saved_dn.split(",", 1)[0]
            if old_rdn.startswith("CN="):
                old_cn = old_rdn[3:]
                if old_cn and old_cn != expected_cn:
                    ok = conn.search(
                        search_base=dept_dn,
                        search_filter=f"(&(objectClass=group)(cn={esc_filter(old_cn)}))",
                        attributes=["distinguishedName"],
                    )
                    if ok and conn.entries:
                        old_dn = str(conn.entries[0].entry_dn)
                        if not conn.modify_dn(old_dn, expected_rdn):
                            raise RuntimeError(
                                f"LDAP rename group failed: {conn.result}"
                            )
                        base = ",".join(old_dn.split(",")[1:])
                        dn = f"{expected_rdn},{base}"
                        Department.objects.filter(pk=dept.pk).update(ldap_group_dn=dn)
                        dept.ldap_group_dn = dn
                        return dn

        # 3) не нашли — создаём новую DEP_ группу в OU отдела
        dn = f"{expected_rdn},{dept_dn}"
        attrs: Dict[str, Any] = {
            "cn": expected_cn,
            "sAMAccountName": expected_cn,
            "groupType": group_type("global", True),
            "description": f"{name} department members",
        }
        ok = conn.add(dn, ["top", "group"], attrs)
        if not ok:
            raise RuntimeError(f"LDAP add group failed: {conn.result}")

        Department.objects.filter(pk=dept.pk).update(ldap_group_dn=dn)
        dept.ldap_group_dn = dn
        return dn

    def _reconcile_department_group(
        self, conn, dept: Department, dept_dn: Optional[str] = None
    ) -> str:
        """
        Приводит состав группы отдела к активным EmployeeDepartment.
        Возвращает DN группы.
        """
        dept_dn = dept_dn or self._get_department_dn(dept)
        group_dn = self._ensure_department_group(conn, dept, dept_dn)

        active_emp_ids = list(
            EmployeeDepartment.objects.filter(
                department_id=dept.id, is_active=True
            ).values_list("employee_id", flat=True)
        )
        if not active_emp_ids:
            self.replace_group_members(conn, group_dn, [])
            return group_dn

        # тянем DN из sync-state за один запрос
        dn_map = dict(
            LdapSyncState.objects.filter(
                model="employee", object_pk__in=[str(i) for i in active_emp_ids]
            ).values_list("object_pk", "ldap_dn")
        )
        member_dns = [dn for dn in dn_map.values() if dn]

        self.replace_group_members(conn, group_dn, member_dns)
        return group_dn

    def _positions_base(self) -> str:
        base = getattr(settings, "LDAP_POSITIONS_BASE", None)
        if not base:
            raise RuntimeError("LDAP_POSITIONS_BASE is not configured")
        return base

    def _ensure_positions_base(self, conn: Connection) -> str:
        base = self._positions_base()
        ensure_container_exists(conn, base)
        return base

    def _ensure_position_group(self, conn: Connection, pos: Position) -> str:
        """
        Гарантирует наличие агрегаторной группы должности: CN=POS_<name>,OU=Positions,...
        Обновляет pos.ldap_group_dn при необходимости и возвращает DN.
        """
        ensure_container_exists(conn, self._positions_base())
        name = (pos.name or "").strip()
        if not name:
            raise ValueError("Position.name is empty")

        expected_cn = f"POS_{name}"
        expected_rdn = f"CN={esc_rdn(expected_cn)}"

        saved_dn = (pos.ldap_group_dn or "").strip()
        if saved_dn:
            ok = conn.search(
                saved_dn,
                "(objectClass=group)",
                search_scope=BASE,
                attributes=["distinguishedName"],
            )
            if ok and conn.entries:
                cur_rdn = saved_dn.split(",", 1)[0]
                if cur_rdn != expected_rdn:
                    if not conn.modify_dn(saved_dn, expected_rdn):
                        raise RuntimeError(
                            f"LDAP rename POS group failed: {conn.result}"
                        )
                    base = ",".join(saved_dn.split(",")[1:])
                    new_dn = f"{expected_rdn},{base}"
                else:
                    new_dn = saved_dn
                if new_dn != pos.ldap_group_dn:
                    Position.objects.filter(pk=pos.pk).update(ldap_group_dn=new_dn)
                    pos.ldap_group_dn = new_dn
                return new_dn

        # поиск по CN в OU=Positions
        ok = conn.search(
            self._positions_base(),
            f"(&(objectClass=group)(cn={esc_filter(expected_cn)}))",
            search_scope=SUBTREE,
            attributes=["distinguishedName"],
        )
        if ok and conn.entries:
            dn = str(conn.entries[0].entry_dn)
            if dn != saved_dn:
                Position.objects.filter(pk=pos.pk).update(ldap_group_dn=dn)
                pos.ldap_group_dn = dn
            return dn

        # создаём
        dn = f"{expected_rdn},{self._positions_base()}"
        attrs = {
            "cn": expected_cn,
            "sAMAccountName": expected_cn,
            "groupType": group_type("global", True),
            "description": f"{name} position members",
        }
        ok = conn.add(dn, ["top", "group"], attrs)
        if not ok:
            raise RuntimeError(f"LDAP add POS group failed: {conn.result}")
        Position.objects.filter(pk=pos.pk).update(ldap_group_dn=dn)
        pos.ldap_group_dn = dn
        return dn

    def _reconcile_position_nesting(self, conn: Connection, position: Position) -> str:
        """
        Делает так, чтобы POS-группа должности была участником ровно тех AD-групп,
        что привязаны к Position.groups.
        """
        pos_dn = self._ensure_position_group(conn, position)

        # желаемые группы (по именам Django Group -> CN в AD)
        desired_dns: Set[str] = set()
        for g in position.groups.all():
            dn = self.find_group_dn(
                conn,
                g.name,
                bases=[
                    getattr(settings, "LDAP_GROUPS_BASE", None)
                    or getattr(settings, "LDAP_BASE_DN", "")
                ],
            )
            if dn:
                desired_dns.add(dn)

        # текущие группы, где POS уже состоит
        current_dns: Set[str] = set()
        search_bases = [
            b
            for b in [
                getattr(settings, "LDAP_GROUPS_BASE", None),
                getattr(settings, "LDAP_BASE_DN", None),
            ]
            if b
        ]
        for base in search_bases:
            ok = conn.search(
                search_base=base,
                search_filter=f"(&(objectClass=group)(member={esc_filter(pos_dn)}))",
                search_scope=SUBTREE,
                attributes=["distinguishedName"],
            )
            if ok and conn.entries:
                current_dns.update(str(e.entry_dn) for e in conn.entries)

        # добавить недостающее
        for add_dn in desired_dns - current_dns:
            self.add_group_members(conn, add_dn, [pos_dn])

        # снять лишнее
        for rem_dn in current_dns - desired_dns:
            self.remove_group_members(conn, rem_dn, [pos_dn])

        return pos_dn

    def _reconcile_position(self, conn: Connection, pos: Position) -> str:
        """
        Приводит к консистентности:
        1) наличие POS_* группы,
        2) вложение POS_* в группы из pos.groups,
        3) состав участников POS_* = сотрудники с этой должностью.
        Возвращает DN POS_* группы.
        """
        pos_dn = self._ensure_position_group(conn, pos)

        # 2) вложение POS_* в target-группы
        expected_container_dns: Set[str] = set()
        for g in pos.groups.all():
            dn = self.find_group_dn(conn, g.name)  # ищем по CN группы
            if dn:
                expected_container_dns.add(dn)

        current_container_dns = self._groups_with_member(conn, pos_dn)
        to_add = expected_container_dns - current_container_dns
        to_del = current_container_dns - expected_container_dns

        for dn in to_add:
            self.add_group_members(conn, dn, [pos_dn])
        for dn in to_del:
            self.remove_group_members(conn, dn, [pos_dn])

        # 3) участники POS_* = сотрудники с этой позицией
        emp_ids = list(
            Employee.objects.filter(position_id=pos.id, is_active=True).values_list(
                "id", flat=True
            )
        )
        dn_map = dict(
            LdapSyncState.objects.filter(
                model="employee", object_pk__in=[str(i) for i in emp_ids]
            ).values_list("object_pk", "ldap_dn")
        )
        member_dns = [dn for dn in dn_map.values() if dn]
        self.replace_group_members(conn, pos_dn, member_dns)
        return pos_dn

    def _groups_with_member(self, conn: Connection, member_dn: str) -> Set[str]:
        """Возвращает множество DN групп, где member=member_dn."""
        base = getattr(settings, "LDAP_GROUPS_BASE", None) or ""
        if not base:
            return set()
        ok = conn.search(
            base,
            f"(&(objectClass=group)(member={esc_filter(member_dn)}))",
            search_scope=SUBTREE,
            attributes=["distinguishedName"],
        )
        if not ok or not conn.entries:
            return set()
        return {str(e.entry_dn) for e in conn.entries}

    def group_find_dn(
        self, cn: str, bases: Optional[list[str]] = None
    ) -> Optional[str]:
        from .connections import _ldap

        with _ldap() as conn:
            return self.find_group_dn(conn, cn, bases=bases)

    def group_create(
        self,
        *,
        cn: str,
        parent_dn: Optional[str] = None,
        description: Optional[str] = None,
        scope: str = "global",
        security_enabled: bool = True,
    ) -> str:
        from .connections import _ldap

        with _ldap() as conn:
            return self.create_group(
                conn,
                cn,
                parent_dn,
                description=description,
                scope=scope,
                security_enabled=security_enabled,
            )

    def group_delete(self, group_dn: str) -> None:
        from .connections import _ldap

        with _ldap() as conn:
            self.delete_group(conn, group_dn)

    def group_rename(self, group_dn: str, new_cn: str) -> str:
        from .connections import _ldap

        with _ldap() as conn:
            return self.rename_group(conn, group_dn, new_cn)

    def group_set_description(self, group_dn: str, description: Optional[str]) -> None:
        from .connections import _ldap

        with _ldap() as conn:
            self.set_group_description(conn, group_dn, description)

    def group_list_members(self, group_dn: str) -> list[str]:
        from .connections import _ldap

        with _ldap() as conn:
            return self.list_group_members(conn, group_dn)

    def group_add_members(self, group_dn: str, member_dns: list[str]) -> None:
        from .connections import _ldap

        with _ldap() as conn:
            self.add_group_members(conn, group_dn, member_dns)

    def group_remove_members(self, group_dn: str, member_dns: list[str]) -> None:
        from .connections import _ldap

        with _ldap() as conn:
            self.remove_group_members(conn, group_dn, member_dns)

    def group_replace_members(self, group_dn: str, exact_member_dns: list[str]) -> None:
        from .connections import _ldap

        with _ldap() as conn:
            self.replace_group_members(conn, group_dn, exact_member_dns)

    def employee_ids_to_dns(self, ids: list[int]) -> list[str]:
        if not ids:
            return []
        id_strs = [str(i) for i in ids if isinstance(i, int)]
        return list(
            LdapSyncState.objects.filter(model="employee", object_pk__in=id_strs)
            .exclude(ldap_dn__isnull=True)
            .exclude(ldap_dn__exact="")
            .values_list("ldap_dn", flat=True)
        )

    def dns_to_employee_ids(self, dns: list[str]) -> list[int]:
        if not dns:
            return []
        ids = list(
            LdapSyncState.objects.filter(model="employee", ldap_dn__in=dns).values_list(
                "object_pk", flat=True
            )
        )
        # object_pk хранится как str
        return [int(x) for x in ids if str(x).isdigit()]

    def employees_brief_by_dns(self, dns: list[str]) -> list[dict]:
        ids = self.dns_to_employee_ids(dns)
        return list(
            Employee.objects.filter(id__in=ids).values(
                "id", "email", "first_name", "last_name"
            )
        )
