"""Сервис для управления отделами в LDAP и Django.

Этот модуль содержит бизнес-логику для CRUD операций с отделами (Department),
включая синхронизацию между Active Directory OU и Django ORM.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from ldap3 import BASE, MODIFY_ADD, MODIFY_DELETE, MODIFY_REPLACE, Connection

from ...models import Department, Employee, EmployeeDepartment, LdapSyncState
from ..domain.dtos import DirectoryDepartmentDTO
from ..errors import (
    DirectoryDbError,
    DirectoryLdapError,
    DirectoryServiceError,
)
from ..utils.group_utils import sync_user_groups_by_cns
from ..infrastructure.connections import _ldap
from ..repositories.ldap_repository import (
    ensure_container_exists,
    ldap_modify_or_ignore,
)
from ..utils.dn_utils import _move_to_department
from ..utils.ldap_utils import group_type
from ..utils.text_utils import esc_filter, esc_rdn


class DepartmentService:
    """Сервис для управления отделами в LDAP и Django."""

    def __init__(self, group_service=None, user_service=None):
        """Инициализация сервиса.
        
        Args:
            group_service: Сервис для работы с группами (Dependency Injection)
            user_service: Сервис для работы с пользователями (Dependency Injection)
        """
        self._group_service = group_service
        self._user_service = user_service

    # ==================== Public API ==================== #

    def create_department(self, dto: DirectoryDepartmentDTO) -> Department:
        """Создаёт OU отдела в LDAP и согласованную запись Department в БД.

        Args:
            dto: Данные отдела.

        Returns:
            Department: Созданный отдел.

        Raises:
            DirectoryLdapError: Не удалось создать/настроить OU в LDAP.
            DirectoryDbError: Не удалось создать запись в БД (OU будет удалён).
        """
        # Используем GroupService через Dependency Injection
        if not self._group_service:
            raise RuntimeError("GroupService not initialized in DepartmentService")
        
        with _ldap() as conn:
            dept_dn: Optional[str] = None
            group_dn: Optional[str] = None
            try:
                dept_dn = self._ensure_department_ou(conn, dto.name)
                self._set_ou_description(conn, dept_dn, dto.description or "")
                head_dn = None
                if dto.head:
                    try:
                        head_dn = self._user_service._get_employee_dn(dto.head)
                    except Exception:
                        head_dn = None
                self._set_ou_managed_by(conn, dept_dn, head_dn)
                group_dn = self._group_service.create(
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
                        self._group_service.delete(conn, group_dn)
                    if dept_dn:
                        self._delete_department_ou(conn, dept_dn)
                finally:
                    pass
                raise DirectoryDbError(str(e)) from e

            return dept

    def update_department(
        self, dept: Department, changes: Dict[str, Any]
    ) -> Department:
        """Обновляет OU отдела, одноименную группу и запись Department.
        
        Args:
            dept: Модель отдела для обновления.
            changes: Словарь изменений (name, description, head).
            
        Returns:
            Department: Обновлённая модель отдела.
            
        Raises:
            DirectoryServiceError: Если не найден DN отдела.
            DirectoryLdapError: Ошибка при обновлении в LDAP.
            DirectoryDbError: Ошибка при сохранении в БД.
        """
        try:
            current_dn = self._get_department_dn(dept)
        except DirectoryServiceError as e:
            raise DirectoryServiceError(
                f"Не найден DN отдела (sync state): {e}"
            ) from e

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
                    self._set_ou_description(
                        conn, new_dn, changes.get("description")
                    )

                if "head" in changes:
                    head = changes.get("head")
                    head_dn = None
                    if head:
                        try:
                            head_dn = self._user_service._get_employee_dn(head)
                        except Exception:
                            head_dn = None
                    self._set_ou_managed_by(conn, new_dn, head_dn)

                # Переименуем одноименную группу, если меняем название отдела
                if name_changed:
                    try:
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
                                    new_group_dn = self._group_service.rename(
                                        conn, group_dn, new_cn=changes["name"]
                                    )
                                except Exception:
                                    desc = (
                                        getattr(conn, "result", {}) or {}
                                    ).get("description", "")
                                    if desc == "entryAlreadyExists":
                                        maybe = self._group_service.find_dn(
                                            conn, changes["name"], bases=[new_dn]
                                        )
                                        if maybe:
                                            new_group_dn = maybe
                                        else:
                                            raise
                            else:
                                group_dn = ""
                        if not group_dn:
                            ensured_dn = self._ensure_department_group(
                                conn, dept, new_dn
                            )
                            try:
                                dep_cn = f"DEP_{changes['name']}"
                                new_group_dn = self._group_service.rename(
                                    conn, ensured_dn, new_cn=dep_cn
                                )
                            except Exception:
                                desc = (
                                    getattr(conn, "result", {}) or {}
                                ).get("description", "")
                                if desc == "entryAlreadyExists":
                                    maybe = self._group_service.find_dn(
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
                    self._sync_descendant_dns_after_ou_rename(
                        old_dn=current_dn, new_dn=new_dn
                    )
                except Exception as e:
                    raise DirectoryDbError(
                        f"Cascade DN rewrite failed: {e}"
                    ) from e
            self._reconcile_department_group(conn, dept, new_dn)
            return dept

    def delete_department(self, dept: Department) -> None:
        """Удаляет отдел: исключает сотрудников → удаляет группу → OU → БД.
        
        Args:
            dept: Отдел для удаления.
            
        Raises:
            DirectoryLdapError: Ошибка при удалении в LDAP.
            DirectoryDbError: Ошибка при удалении из БД.
        """
        with _ldap() as conn:
            try:
                dept_dn = self._get_department_dn(dept)
            except DirectoryServiceError:
                dept_dn = None

            try:
                if dept.ldap_group_dn:
                    self._group_service.delete(conn, dept.ldap_group_dn)
            except Exception:
                pass

            if dept_dn:
                try:
                    self._evict_all_users_from_department_ou(conn, dept_dn)
                    self._delete_department_ou(conn, dept_dn)
                except Exception as e:
                    raise DirectoryLdapError(
                        f"LDAP delete OU failed: {e}"
                    ) from e

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
        """Добавляет сотрудника в OU отдела и в одноименную группу отдела.
        
        Args:
            dept: Отдел.
            employee: Сотрудник для добавления.
            
        Raises:
            DirectoryServiceError: Если сотрудник уже в другом отделе.
            DirectoryLdapError: Ошибка при добавлении в LDAP.
            DirectoryDbError: Ошибка при создании связи в БД.
        """
        existing_link = EmployeeDepartment.objects.filter(
            employee_id=employee.id, is_active=True
        ).first()
        if existing_link:
            raise DirectoryServiceError(
                f"Сотрудник уже состоит в отделе: {existing_link.department.name}"
            )

        emp_dn = self._user_service._get_employee_dn(employee)
        with _ldap() as conn:
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
                    f"LDAP ensure OU failed: {e}"
                ) from e

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
                    raise DirectoryDbError(
                        f"Failed to save new DN in DB: {e}"
                    ) from e

            try:
                group_dn = self._ensure_department_group(conn, dept, dept_dn)
                if not group_dn:
                    raise RuntimeError(
                        "_ensure_department_group returned empty DN"
                    )
                self._group_service.add_members(conn, group_dn, [emp_dn])
            except Exception as e:
                raise DirectoryLdapError(
                    f"LDAP add to department group failed: {e}"
                ) from e

            try:
                with transaction.atomic():
                    link, _ = EmployeeDepartment.objects.get_or_create(
                        employee_id=employee.id,
                        department_id=dept.id,
                        defaults={"is_active": True},
                    )
                    link.is_active = True
                    link.save(update_fields=["is_active"])
            except Exception as e:
                raise DirectoryDbError(str(e)) from e

    def remove_member(self, dept: Department, employee: Employee) -> None:
        """Удаляет сотрудника из отдела: из группы → MOVE в Users OU → удаление линка.
        
        Args:
            dept: Отдел.
            employee: Сотрудник для удаления.
            
        Raises:
            DirectoryServiceError: Если пытаемся удалить руководителя.
            DirectoryLdapError: Ошибка при удалении из LDAP.
            DirectoryDbError: Ошибка при удалении связи в БД.
        """
        if dept.head_id == employee.id:
            raise DirectoryServiceError(
                "Нельзя удалить руководителя отдела"
            )

        try:
            emp_dn = self._user_service._get_employee_dn(employee)
        except DirectoryServiceError:
            emp_dn = None

        with _ldap() as conn:
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
                        self._group_service.remove_members(conn, grp_dn, [emp_dn])
            except Exception:
                pass

            if emp_dn:
                users_base = getattr(
                    settings, "LDAP_USERS_BASE", None
                ) or getattr(settings, "LDAP_USER_BASE", None)
                if not users_base:
                    raise RuntimeError("LDAP_USERS_BASE is not configured")
                try:
                    ensure_container_exists(conn, users_base)
                    new_dn = self._user_service._move_user_to_base(
                        conn, emp_dn, users_base
                    )
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
            dept: Модель отдела.
            head: Новый руководитель или None (снятие).

        Returns:
            Department: Обновлённая модель отдела.

        Raises:
            DirectoryServiceError: Если не удаётся определить DN объекта.
            DirectoryLdapError: Ошибка при записи в LDAP.
            DirectoryDbError: Ошибка при сохранении в БД.
        """
        with _ldap() as conn:
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
                head_dn = self._user_service._get_employee_dn(head)
                if not head_dn:
                    raise DirectoryServiceError("Head has no ldap_dn")

            try:
                self._set_ou_managed_by(conn, dept_dn, head_dn)
            except Exception as e:
                raise DirectoryLdapError(
                    f"LDAP set managedBy failed: {e}"
                ) from e

            try:
                with transaction.atomic():
                    dept.head = head
                    dept.save(update_fields=["head"])
            except Exception as e:
                raise DirectoryDbError(str(e)) from e
            self._reconcile_department_group(conn, dept, dept_dn)

            return dept

    def set_member_role(
        self, dept: Department, employee: Employee, role
    ) -> None:
        """Меняет роль участника отдела с синхронизацией LDAP-групп Roles.

        Args:
            dept: Отдел.
            employee: Сотрудник.
            role: Новая роль или None.
            
        Raises:
            DirectoryDbError: Ошибка при обновлении БД.
            DirectoryLdapError: Ошибка при синхронизации групп.
        """
        try:
            with transaction.atomic():
                link = EmployeeDepartment.objects.get(
                    employee_id=employee.id, department_id=dept.id
                )
                link.role = role
                link.save(update_fields=["role"])
        except EmployeeDepartment.DoesNotExist as e:
            raise DirectoryDbError(
                "Employee is not a member of this department"
            ) from e
        except Exception as e:
            raise DirectoryDbError(str(e)) from e

        try:
            if role:
                user_dn = self._user_service._get_employee_dn(employee)
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
            pass
        except Exception as e:
            raise DirectoryLdapError(
                f"LDAP role sync failed: {e}"
            ) from e

    # ==================== DN/Lookup Methods ==================== #

    def _get_department_dn(self, dept: Department) -> str:
        """Возвращает DN OU отдела из LdapSyncState.

        Args:
            dept: Экземпляр отдела.

        Returns:
            str: Полный DN OU отдела.

        Raises:
            DirectoryServiceError: Если DN отсутствует.
        """
        dn = (
            LdapSyncState.objects.filter(
                model="department", object_pk=str(dept.pk)
            )
            .values_list("ldap_dn", flat=True)
            .first()
        )
        if not dn:
            raise DirectoryServiceError(
                "Department has no ldap_dn in sync state"
            )
        return dn

    def _get_department_by_dn(self, dept_dn: str) -> Optional[Department]:
        """Возвращает Department по DN из LdapSyncState.
        
        Args:
            dept_dn: DN OU отдела.
            
        Returns:
            Optional[Department]: Найденный отдел или None.
        """
        if not dept_dn:
            return None
        pk = (
            LdapSyncState.objects.filter(
                model="department", ldap_dn__iexact=dept_dn
            )
            .values_list("object_pk", flat=True)
            .first()
        )
        if not pk:
            return None
        return Department.objects.filter(pk=pk).first()

    # ==================== Private OU Methods ==================== #

    def _ensure_department_ou(self, conn: Connection, name: str) -> str:
        """Гарантирует наличие OU отдела + OU=Roles.
        
        Args:
            conn: LDAP соединение.
            name: Название отдела.
            
        Returns:
            str: DN созданного/существующего OU.
            
        Raises:
            RuntimeError: Если не настроен LDAP_DEPARTMENTS_BASE или ошибка создания.
        """
        base = getattr(settings, "LDAP_DEPARTMENTS_BASE", None)
        if not base:
            raise RuntimeError("LDAP_DEPARTMENTS_BASE is not configured")
        dn = f"OU={name},{base}"
        ok = conn.search(
            dn, "(objectClass=organizationalUnit)", search_scope=BASE
        )
        if ok and conn.entries:
            return dn
        ok = conn.add(dn, ["top", "organizationalUnit"])
        if not ok:
            raise RuntimeError(f"LDAP add OU failed: {conn.result}")
        conn.add(f"OU=Roles,{dn}", ["top", "organizationalUnit"])
        return dn

    def _rename_department_ou(
        self, conn: Connection, dept_dn: str, new_name: str
    ) -> str:
        """Переименовывает OU отдела и возвращает новый DN.
        
        Args:
            conn: LDAP соединение.
            dept_dn: Текущий DN OU.
            new_name: Новое имя отдела.
            
        Returns:
            str: Новый DN после переименования.
            
        Raises:
            RuntimeError: Если операция переименования не удалась.
        """
        cn = f"OU={new_name}"
        ok = conn.modify_dn(dept_dn, cn)
        if not ok:
            raise RuntimeError(f"LDAP rename OU failed: {conn.result}")
        base = ",".join(dept_dn.split(",")[1:])
        return f"{cn},{base}"

    def _set_ou_managed_by(
        self, conn: Connection, dept_dn: str, head_dn: Optional[str]
    ) -> None:
        """Устанавливает/очищает managedBy у OU в AD (идемпотентно).

        Args:
            conn: LDAP соединение.
            dept_dn: DN OU отдела.
            head_dn: DN руководителя или None.
            
        Raises:
            DirectoryServiceError: Если OU или head DN не найдены.
            RuntimeError: Если операция modify не удалась.
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
        current_vals = list(
            map(str, getattr(ou_entry, "managedBy", []) or [])
        )

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
            if res.get("result") == 16 and op == MODIFY_DELETE:
                return
            raise RuntimeError(f"LDAP modify managedBy failed: {res}")

    def _set_ou_description(
        self, conn: Connection, dept_dn: str, description: Optional[str]
    ) -> None:
        """Ставит/очищает description у OU.
        
        Args:
            conn: LDAP соединение.
            dept_dn: DN OU отдела.
            description: Описание или None для удаления.
        """
        changes = (
            {"description": [(MODIFY_REPLACE, [description])]}
            if description
            else {"description": [(MODIFY_DELETE, [])]}
        )
        ldap_modify_or_ignore(conn, dept_dn, changes, {"noSuchAttribute"})

    def _delete_department_ou(self, conn: Connection, dept_dn: str) -> None:
        """Удаляет OU (ignore noSuchObject).
        
        Args:
            conn: LDAP соединение.
            dept_dn: DN OU для удаления.
            
        Raises:
            RuntimeError: Если удаление не удалось (кроме noSuchObject).
        """
        ok = conn.delete(dept_dn)
        if not ok and (conn.result or {}).get("description") not in {
            "noSuchObject"
        }:
            raise RuntimeError(f"LDAP delete OU failed: {conn.result}")

    def _evict_all_users_from_department_ou(
        self, conn: Connection, dept_dn: str
    ) -> None:
        """Перемещает всех пользователей из OU отдела в Users base.
        
        Args:
            conn: LDAP соединение.
            dept_dn: DN OU отдела.
            
        Raises:
            RuntimeError: Если не настроен LDAP_USERS_BASE.
        """
        users_base = getattr(
            settings, "LDAP_USERS_BASE", None
        ) or getattr(settings, "LDAP_USER_BASE", None)
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
                new_dn = self._user_service._move_user_to_base(
                    conn, old_dn, users_base
                )
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

    # ==================== Private Group Methods ==================== #

    def _ensure_department_group(
        self, conn: Connection, dept: Department, dept_dn: str
    ) -> str:
        """Гарантирует наличие группы отдела с CN = 'DEP_<ИмяОтдела>'.
        
        При необходимости переименовывает/создаёт и синхронизирует dept.ldap_group_dn.
        
        Args:
            conn: LDAP соединение.
            dept: Модель отдела.
            dept_dn: DN OU отдела.
            
        Returns:
            str: DN группы отдела.
            
        Raises:
            ValueError: Если имя отдела пустое.
            RuntimeError: Если операции с группой не удались.
        """
        name = (dept.name or "").strip()
        if not name:
            raise ValueError("Department.name is empty")

        expected_cn = f"DEP_{name}"
        expected_rdn = f"CN={esc_rdn(expected_cn)}"

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
                        raise RuntimeError(
                            f"LDAP rename group failed: {conn.result}"
                        )
                    base = ",".join(saved_dn.split(",")[1:])
                    new_dn = f"{expected_rdn},{base}"
                else:
                    new_dn = saved_dn

                if new_dn != dept.ldap_group_dn:
                    Department.objects.filter(pk=dept.pk).update(
                        ldap_group_dn=new_dn
                    )
                    dept.ldap_group_dn = new_dn
                return new_dn

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
                        Department.objects.filter(pk=dept.pk).update(
                            ldap_group_dn=dn
                        )
                        dept.ldap_group_dn = dn
                        return dn

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
        self, conn: Connection, dept: Department, dept_dn: Optional[str]
    ) -> str:
        """Приводит состав группы отдела к активным EmployeeDepartment.
        
        Args:
            conn: LDAP соединение.
            dept: Модель отдела.
            dept_dn: DN OU отдела (если None, будет запрошен).
            
        Returns:
            str: DN группы отдела.
        """
        dept_dn = dept_dn or self._get_department_dn(dept)
        group_dn = self._ensure_department_group(conn, dept, dept_dn)

        active_emp_ids = list(
            EmployeeDepartment.objects.filter(
                department_id=dept.id, is_active=True
            ).values_list("employee_id", flat=True)
        )
        if not active_emp_ids:
            self._group_service.replace_members(conn, group_dn, [])
            return group_dn

        dn_map = dict(
            LdapSyncState.objects.filter(
                model="employee",
                object_pk__in=[str(i) for i in active_emp_ids],
            ).values_list("object_pk", "ldap_dn")
        )
        member_dns = [dn for dn in dn_map.values() if dn]

        self._group_service.replace_members(conn, group_dn, member_dns)
        return group_dn

    # ==================== Utility Methods ==================== #

    def _split_rdn_parent(self, dn: str) -> Tuple[str, str]:
        """Делит DN на (RDN, parentDN).
        
        Args:
            dn: Distinguished Name.
            
        Returns:
            Tuple[str, str]: (RDN, parent DN).
            
        Raises:
            DirectoryServiceError: Если DN некорректный.
        """
        parts = dn.split(",", 1)
        if len(parts) != 2:
            raise DirectoryServiceError(f"Malformed DN: {dn}")
        return parts[0], parts[1]

    def _sync_descendant_dns_after_ou_rename(
        self, *, old_dn: str, new_dn: str
    ) -> Tuple[int, int]:
        """Переписывает хвост DN у всех записей sync-state сотрудников.
        
        Вызывается после переименования OU отдела.
        
        Args:
            old_dn: Старый DN OU.
            new_dn: Новый DN OU.
            
        Returns:
            Tuple[int, int]: (обновлено в модели (всегда 0), обновлено состояний).
        """
        old_suffix = f",{old_dn}".lower()
        new_suffix = f",{new_dn}"

        states = list(
            LdapSyncState.objects.filter(
                model="employee", ldap_dn__iendswith=old_suffix
            )
        )
        if not states:
            return 0, 0

        now = timezone.now()
        updated_count = 0
        for st in states:
            old_st_dn = st.ldap_dn or ""
            if not old_st_dn.lower().endswith(old_suffix):
                continue
            rdn = old_st_dn[: -len(old_suffix)]
            new_st_dn = rdn + new_suffix
            st.touch(
                ldap_dn=new_st_dn,
                last_django_modify_ts=now,
                sync_dir="auto",
            )
            updated_count += 1
        return 0, updated_count

    def _touch_state(
        self,
        *,
        model: str,
        object_pk: int,
        ldap_dn: Optional[str] = None,
        last_django_modify_ts: Optional[Any] = None,
        sync_dir: Optional[str] = None,
    ) -> None:
        """Обновляет или создаёт запись в LdapSyncState.
        
        Args:
            model: Название модели ('employee', 'department').
            object_pk: PK объекта.
            ldap_dn: DN в LDAP (если нужно обновить).
            last_django_modify_ts: Временная метка последнего изменения из Django.
            sync_dir: Направление синхронизации ('django', 'ldap', 'auto').
        """
        state, _ = LdapSyncState.objects.get_or_create(
            model=model, object_pk=str(object_pk)
        )
        state.touch(
            ldap_dn=ldap_dn,
            last_django_modify_ts=last_django_modify_ts,
            sync_dir=sync_dir,
        )


__all__ = ["DepartmentService"]
