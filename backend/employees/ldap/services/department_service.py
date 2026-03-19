"""Сервис для управления отделами в LDAP и Django.

Этот модуль содержит бизнес-логику для CRUD операций с отделами (Department),
включая синхронизацию между Active Directory OU и Django ORM.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from ldap3 import BASE, Connection

from ...models import Department, DepartmentRole, Employee, EmployeeDepartment, LdapSyncState, RoleAssignment
from ..domain.dtos import DirectoryDepartmentDTO
from ..errors import (
    DirectoryDbError,
    DirectoryLdapError,
    DirectoryServiceError,
)
from ..orm_models import LdapOrganizationalUnit
from ..infrastructure.connections import _ldap
from ..repositories.ldap_repository import (
    ensure_container_exists,
)
from ..utils.dn_utils import _move_to_department
from ..utils.ldap_utils import group_type
from ..utils.text_utils import esc_filter, esc_rdn
from .base_service import BaseService
from .constants import SyncDirection


class DepartmentService(BaseService):
    """Сервис для управления отделами в LDAP и Django.
    
    Рефакторенная версия с улучшениями:
    - Наследуется от BaseService (логирование, _touch_state)
    - Использует константы вместо магических строк
    - Логирует все критические операции
    """

    def __init__(self, group_service=None, user_service=None):
        """Инициализация сервиса.
        
        Args:
            group_service: Сервис для работы с группами (Dependency Injection)
            user_service: Сервис для работы с пользователями (Dependency Injection)
        """
        super().__init__()
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
                        sync_dir=SyncDirection.DJANGO,
                    )
                    self._log_operation(
                        "create",
                        model="department",
                        object_id=dept.pk,
                        dn=dept_dn,
                        success=True,
                    )
            except Exception as e:
                try:
                    if group_dn:
                        self._group_service.delete(group_dn)
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
                                        group_dn, new_cn=changes["name"]
                                    )
                                except Exception:
                                    desc = (
                                        getattr(conn, "result", {}) or {}
                                    ).get("description", "")
                                    if desc == "entryAlreadyExists":
                                        maybe = self._group_service.find_dn(
                                            changes["name"], bases=[new_dn]
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
                                    ensured_dn, new_cn=dep_cn
                                )
                            except Exception:
                                desc = (
                                    getattr(conn, "result", {}) or {}
                                ).get("description", "")
                                if desc == "entryAlreadyExists":
                                    maybe = self._group_service.find_dn(
                                        dep_cn, bases=[new_dn]
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
                    self._group_service.delete(dept.ldap_group_dn)
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
                    dept_name = dept.name
                    dept.delete()
                    LdapSyncState.objects.filter(
                        model="department", object_pk=str(pk)
                    ).delete()
                    self._log_operation(
                        "delete",
                        model="department",
                        object_id=pk,
                        dn=dept_dn,
                        success=True,
                        extra={"name": dept_name},
                    )
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
                        sync_dir=SyncDirection.AUTO,
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
                        sync_dir=SyncDirection.LDAP,
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
                self._group_service.add_members(group_dn, [emp_dn])
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
                        self._group_service.remove_members(grp_dn, [emp_dn])
            except Exception:
                pass

            if emp_dn:
                from ..utils.ldap_utils import get_base_dn_for_employee
                
                try:
                    target_base = get_base_dn_for_employee(employee)
                except RuntimeError as e:
                    raise DirectoryLdapError(str(e)) from e
                
                try:
                    ensure_container_exists(conn, target_base)
                    new_dn = self._user_service._move_user_to_base(
                        conn, emp_dn, target_base
                    )
                    self._touch_state(
                        model="employee",
                        object_pk=employee.id,
                        ldap_dn=new_dn,
                        sync_dir=SyncDirection.LDAP,
                    )
                except Exception as e:
                    target_name = "Dismissed OU" if not employee.is_active else "Users OU"
                    raise DirectoryLdapError(
                        f"LDAP move to {target_name} failed: {e}"
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
                        sync_dir=SyncDirection.AUTO,
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

    # ==================== Role CRUD (LDAP → DB) ==================== #

    def create_role(
        self,
        department: Department,
        name: str,
        description: str = "",
        scoped_permissions: Optional[list] = None,
    ) -> DepartmentRole:
        """Создаёт роль: сначала группу в LDAP, затем запись в БД.
        
        Аналогично create_department — сначала LDAP, потом БД.
        При ошибке БД откатываем созданную группу в LDAP.
        
        Args:
            department: Отдел для роли.
            name: Название роли.
            description: Описание роли.
            scoped_permissions: Список DepartmentPermission для назначения.
            
        Returns:
            DepartmentRole: Созданная роль.
            
        Raises:
            DirectoryLdapError: Ошибка создания группы в LDAP.
            DirectoryDbError: Ошибка создания записи в БД.
        """
        # 1. Создаём группу в LDAP
        dept_dn = self._get_department_dn(department)
        role_name = self._sanitize_name(name)
        cn = f"ROLE_{role_name}"
        group_dn = f"CN={esc_rdn(cn)},{dept_dn}"
        
        with _ldap() as conn:
            try:
                attrs = {
                    "sAMAccountName": cn[:20],
                    "description": description or f"Role: {name} in {department.name}",
                    "groupType": group_type("global", security_enabled=True),
                }
                ok = conn.add(group_dn, ["top", "group"], attrs)
                if not ok:
                    if "entryAlreadyExists" not in str(conn.result):
                        raise DirectoryLdapError(
                            f"LDAP create role group failed: {conn.result}"
                        )
            except DirectoryLdapError:
                raise
            except Exception as e:
                raise DirectoryLdapError(f"LDAP create role group failed: {e}") from e
            
            # 2. Создаём запись в БД
            try:
                with transaction.atomic():
                    role = DepartmentRole.objects.create(
                        department=department,
                        name=name,
                        ldap_group_dn=group_dn,
                    )
                    if scoped_permissions:
                        role.scoped_permissions.set(scoped_permissions)
            except Exception as e:
                # Откатываем группу в LDAP
                try:
                    self._group_service.delete(group_dn)
                except Exception:
                    pass
                raise DirectoryDbError(str(e)) from e
            
            return role

    def update_role(
        self,
        role: DepartmentRole,
        changes: Dict[str, Any],
    ) -> DepartmentRole:
        """Обновляет роль: сначала в LDAP, затем в БД.
        
        Args:
            role: Роль для обновления.
            changes: Словарь изменений (name, scoped_permissions, scoped_permission_codes).
            
        Returns:
            DepartmentRole: Обновлённая роль.
            
        Raises:
            DirectoryLdapError: Ошибка обновления в LDAP.
            DirectoryDbError: Ошибка сохранения в БД.
        """
        new_name = changes.get("name")
        
        # Если меняется имя — переименовываем группу в LDAP
        if new_name and new_name != role.name:
            if role.ldap_group_dn:
                try:
                    new_role_name = self._sanitize_name(new_name)
                    new_cn = f"ROLE_{new_role_name}"
                    new_dn = self._group_service.rename(
                        role.ldap_group_dn, new_cn=new_cn
                    )
                    role.ldap_group_dn = new_dn
                except Exception as e:
                    raise DirectoryLdapError(
                        f"LDAP rename role group failed: {e}"
                    ) from e
            else:
                # Группы нет — создаём
                role.name = new_name
                self._ensure_role_group(role)
        
        # Обновляем БД
        try:
            with transaction.atomic():
                if new_name:
                    role.name = new_name
                role.save()
                
                # Обновляем права
                perms = changes.get("scoped_permissions")
                codes = changes.get("scoped_permission_codes")
                
                if perms is not None:
                    role.scoped_permissions.set(perms)
                elif codes is not None:
                    from employees.models import DepartmentPermission
                    qs = DepartmentPermission.objects.filter(code__in=codes)
                    role.scoped_permissions.set(list(qs))
        except Exception as e:
            raise DirectoryDbError(str(e)) from e
        
        return role

    def delete_role(self, role: DepartmentRole) -> None:
        """
        Args:
            role: Роль для удаления.
            
        Raises:
            DirectoryLdapError: Ошибка удаления группы из LDAP.
            DirectoryDbError: Ошибка удаления записи из БД.
        """
        # 1. Удаляем группу из LDAP
        if role.ldap_group_dn:
            try:
                self._group_service.delete(role.ldap_group_dn)
            except Exception as e:
                raise DirectoryLdapError(
                    f"LDAP delete role group failed: {e}"
                ) from e
        
        # 2. Удаляем запись из БД
        try:
            role.delete()
        except Exception as e:
            raise DirectoryDbError(str(e)) from e

    def set_member_role(
        self, dept: Department, employee: Employee, role
    ) -> None:
        """DEPRECATED: Используйте assign_role / revoke_role.
        
        Меняет роль участника отдела с синхронизацией LDAP-групп.
        Сохранена для обратной совместимости.

        Args:
            dept: Отдел.
            employee: Сотрудник.
            role: Новая роль или None.
            
        Raises:
            DirectoryDbError: Ошибка при обновлении БД.
            DirectoryLdapError: Ошибка при синхронизации групп.
        """
        # Обновляем EmployeeDepartment.role для обратной совместимости
        try:
            with transaction.atomic():
                link = EmployeeDepartment.objects.get(
                    employee_id=employee.id, department_id=dept.id
                )
                old_role = link.role
                link.role = role
                link.save(update_fields=["role"])
        except EmployeeDepartment.DoesNotExist as e:
            raise DirectoryDbError(
                "Employee is not a member of this department"
            ) from e
        except Exception as e:
            raise DirectoryDbError(str(e)) from e

        # Обновляем RoleAssignment
        if role:
            self.assign_role(employee, role, assigned_by=None)
        elif old_role:
            self.revoke_role(employee, old_role)

    def assign_role(
        self,
        employee: Employee,
        role: DepartmentRole,
        assigned_by: Optional[Employee] = None,
    ) -> RoleAssignment:
        """Назначает роль сотруднику (не требует членства в отделе).
        
        Логика: сначала LDAP, потом БД. При ошибке LDAP — операция отменяется.
        
        Args:
            employee: Сотрудник.
            role: Роль для назначения.
            assigned_by: Кто назначил (опционально).
            
        Returns:
            RoleAssignment: Созданное/обновлённое назначение.
            
        Raises:
            DirectoryLdapError: Ошибка LDAP.
            DirectoryDbError: Ошибка БД.
        """
        # 1. Сначала синхронизируем LDAP-группу роли
        try:
            self._sync_role_membership(employee, role, add=True)
        except Exception as e:
            raise DirectoryLdapError(f"LDAP role sync failed: {e}") from e
        
        # 2. Только при успехе LDAP — создаём/обновляем назначение в БД
        try:
            with transaction.atomic():
                assignment, created = RoleAssignment.objects.update_or_create(
                    employee=employee,
                    role=role,
                    defaults={
                        "is_active": True,
                        "assigned_by": assigned_by,
                    }
                )
        except Exception as e:
            # Откатываем LDAP — удаляем из группы
            try:
                self._sync_role_membership(employee, role, add=False)
            except Exception:
                pass  # Best effort rollback
            raise DirectoryDbError(str(e)) from e
        
        return assignment

    def revoke_role(
        self,
        employee: Employee,
        role: DepartmentRole,
    ) -> None:
        """Отзывает роль у сотрудника.
        
        Логика: сначала LDAP, потом БД. При ошибке LDAP — операция отменяется.
        
        Args:
            employee: Сотрудник.
            role: Роль для отзыва.
            
        Raises:
            DirectoryLdapError: Ошибка LDAP.
        """
        # 1. Сначала удаляем из LDAP-группы
        try:
            self._sync_role_membership(employee, role, add=False)
        except Exception as e:
            raise DirectoryLdapError(f"LDAP role revoke failed: {e}") from e
        
        # 2. Только при успехе LDAP — деактивируем назначение
        RoleAssignment.objects.filter(
            employee=employee,
            role=role
        ).update(is_active=False)

    def _sync_role_membership(
        self,
        employee: Employee,
        role: DepartmentRole,
        add: bool = True,
    ) -> None:
        """Синхронизирует членство сотрудника в группе роли LDAP.
        
        Args:
            employee: Сотрудник.
            role: Роль.
            add: True — добавить в группу, False — удалить.
        """
        # Создаём группу роли если нет
        if not role.ldap_group_dn:
            self._ensure_role_group(role)
        
        if not role.ldap_group_dn:
            return  # Не удалось создать группу
        
        user_dn = self._user_service._get_employee_dn(employee)
        
        with _ldap() as conn:
            if add:
                self._group_service.add_members(role.ldap_group_dn, [user_dn])
            else:
                self._group_service.remove_members(role.ldap_group_dn, [user_dn])

    def _ensure_role_group(self, role: DepartmentRole) -> str:
        """Гарантирует наличие группы роли ROLE_<Name> в OU отдела.
        
        Args:
            role: Роль отдела.
            
        Returns:
            str: DN группы роли.
        """
        dept = role.department
        dept_dn = self._get_department_dn(dept)
        
        # Формат: ROLE_<RoleName> (аналогично DEP_, POS_)
        role_name = self._sanitize_name(role.name)
        expected_cn = f"ROLE_{role_name}"
        expected_rdn = f"CN={esc_rdn(expected_cn)}"
        
        saved_dn = (role.ldap_group_dn or "").strip()
        
        with _ldap() as conn:
            # Проверяем существующую группу
            if saved_dn:
                ok = conn.search(
                    saved_dn,
                    "(objectClass=group)",
                    search_scope=BASE,
                    attributes=["distinguishedName"],
                )
                if ok and conn.entries:
                    # Группа существует — проверяем нужно ли переименовать
                    cur_rdn = saved_dn.split(",", 1)[0]
                    if cur_rdn != expected_rdn:
                        # Переименовываем
                        if not conn.modify_dn(saved_dn, expected_rdn):
                            raise RuntimeError(
                                f"LDAP rename role group failed: {conn.result}"
                            )
                        base = ",".join(saved_dn.split(",")[1:])
                        new_dn = f"{expected_rdn},{base}"
                    else:
                        new_dn = saved_dn
                    
                    if new_dn != role.ldap_group_dn:
                        DepartmentRole.objects.filter(pk=role.pk).update(
                            ldap_group_dn=new_dn
                        )
                        role.ldap_group_dn = new_dn
                    return new_dn
            
            # Создаём новую группу
            new_dn = f"{expected_rdn},{dept_dn}"
            attrs = {
                "sAMAccountName": expected_cn[:20],  # SAM ограничен 20 символами
                "description": f"Role: {role.name} in {dept.name}",
                "groupType": group_type("global", security_enabled=True),
            }
            ok = conn.add(new_dn, ["top", "group"], attrs)
            if not ok:
                if "entryAlreadyExists" in str(conn.result):
                    pass  # Уже существует
                else:
                    raise RuntimeError(f"LDAP add role group failed: {conn.result}")
            
            DepartmentRole.objects.filter(pk=role.pk).update(ldap_group_dn=new_dn)
            role.ldap_group_dn = new_dn
            return new_dn

    def rename_role_group(self, role: DepartmentRole, new_name: str) -> str:
        """Переименовывает группу роли в LDAP.
        
        Args:
            role: Роль.
            new_name: Новое название роли.
            
        Returns:
            str: Новый DN группы.
        """
        if not role.ldap_group_dn:
            # Группы нет — создаём с новым именем
            role.name = new_name
            return self._ensure_role_group(role)
        
        new_role_name = self._sanitize_name(new_name)
        new_cn = f"ROLE_{new_role_name}"
        
        with _ldap() as conn:
            new_dn = self._group_service.rename(role.ldap_group_dn, new_cn=new_cn)
        
        DepartmentRole.objects.filter(pk=role.pk).update(ldap_group_dn=new_dn)
        role.ldap_group_dn = new_dn
        return new_dn

    def delete_role_group(self, role: DepartmentRole) -> None:
        """Удаляет группу роли из LDAP.
        
        Args:
            role: Роль для удаления группы.
        """
        if not role.ldap_group_dn:
            return
        
        with _ldap() as conn:
            try:
                self._group_service.delete(role.ldap_group_dn)
            except Exception:
                pass  # Best effort
        
        DepartmentRole.objects.filter(pk=role.pk).update(ldap_group_dn="")
        role.ldap_group_dn = ""

    def _sanitize_name(self, name: str) -> str:
        """Очищает имя для использования в CN LDAP-группы.
        
        Args:
            name: Исходное имя.
            
        Returns:
            str: Очищенное имя.
        """
        import re
        # Убираем спецсимволы LDAP, заменяем пробелы на _
        clean = re.sub(r'[,=+<>#;\\"\']', '', name)
        clean = re.sub(r'\s+', '_', clean)
        return clean[:50]  # Ограничение длины

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
        """Гарантирует наличие OU отдела.
        
        Группы ролей (ROLE_*) создаются непосредственно в OU отдела,
        а не в отдельном OU=Roles (убрано для корректной работы GPO).
        
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
        # NOTE: OU=Roles больше не создаётся — группы ролей лежат прямо в OU отдела
        return dn

    def _rename_department_ou(
        self, conn: Connection, dept_dn: str, new_name: str
    ) -> str:
        """Переименовывает OU отдела и возвращает новый DN.
        
        TODO(ldap-orm): modify_dn — ldap3 навсегда.
        django-ldapdb не поддерживает переименование.
        
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
        """Устанавливает/очищает managedBy у OU в AD через ORM.

        Args:
            conn: LDAP соединение (не используется, ORM).
            dept_dn: DN OU отдела.
            head_dn: DN руководителя или None.
        """
        if not dept_dn:
            raise DirectoryServiceError("dept_dn пуст")

        try:
            ou = LdapOrganizationalUnit.objects.get(dn=dept_dn)
        except LdapOrganizationalUnit.DoesNotExist:
            raise DirectoryServiceError(f"OU not found: {dept_dn}")

        current = (ou.managed_by or "").strip().lower()
        target = (head_dn or "").strip().lower()

        if current == target:
            return

        ou.managed_by = head_dn or ""
        ou.save()

    def _set_ou_description(
        self, conn: Connection, dept_dn: str, description: Optional[str]
    ) -> None:
        """Ставит/очищает description у OU (ORM).
        
        Args:
            conn: LDAP соединение (не используется, ORM).
            dept_dn: DN OU отдела.
            description: Описание или None для удаления.
        """
        try:
            ou = LdapOrganizationalUnit.objects.get(dn=dept_dn)
            ou.description = description or ""
            ou.save()
        except LdapOrganizationalUnit.DoesNotExist:
            pass

    def _delete_department_ou(self, conn: Connection, dept_dn: str) -> None:
        """Удаляет OU (ORM, ignore DoesNotExist).
        
        Args:
            conn: LDAP соединение (не используется, ORM).
            dept_dn: DN OU для удаления.
        """
        try:
            ou = LdapOrganizationalUnit.objects.get(dn=dept_dn)
            ou.delete()
        except LdapOrganizationalUnit.DoesNotExist:
            pass

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
                            sync_dir=SyncDirection.LDAP,
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
            self._group_service.replace_members(group_dn, [])
            return group_dn

        dn_map = dict(
            LdapSyncState.objects.filter(
                model="employee",
                object_pk__in=[str(i) for i in active_emp_ids],
            ).values_list("object_pk", "ldap_dn")
        )
        member_dns = [dn for dn in dn_map.values() if dn]

        self._group_service.replace_members(group_dn, member_dns)
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
                sync_dir=SyncDirection.AUTO,
            )
            updated_count += 1
        return 0, updated_count


__all__ = ["DepartmentService"]
