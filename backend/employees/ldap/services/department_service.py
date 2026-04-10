"""Сервис для управления отделами в LDAP и Django.

Этот модуль содержит бизнес-логику для CRUD операций с отделами (Department),
включая синхронизацию между Active Directory OU и Django ORM.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from ...models import (
    Department,
    DepartmentRole,
    Employee,
    EmployeeDepartment,
    LdapSyncState,
    RoleAssignment,
)
from ..domain.dtos import DirectoryDepartmentDTO
from ..errors import (
    DirectoryDbError,
    DirectoryLdapError,
    DirectoryServiceError,
)
from ..orm_models import (
    LdapOrganizationalUnit,
    LdapOrganizationalUnitGroup,
    LdapUser,
)
from ..utils.ldap_utils import get_base_dn_for_employee
from ..utils.text_utils import esc_rdn
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
            user_service: Сервис для работы с пользователями
            (Dependency Injection)
        """
        super().__init__()
        self._group_service = group_service
        self._user_service = user_service

    def _ensure_runtime_services(self) -> None:
        """Ленивая инициализация зависимостей для sync/retry путей."""
        if self._group_service is None:
            from .group_service import GroupService

            self._group_service = GroupService()

        if self._user_service is None:
            from .user_service import UserService

            self._user_service = UserService(self._group_service)

    def _load_ldap_user(
        self,
        employee: Employee,
        *,
        expected_dn: Optional[str] = None,
    ) -> LdapUser:
        """Возвращает high-level LDAP модель пользователя.

        Ищет сначала по DN из sync state, затем по employeeNumber.
        Если объект найден не по ожидаемому DN, корректирует sync state.
        """
        candidate_dn = (expected_dn or "").strip()
        ldap_user: Optional[LdapUser] = None

        if candidate_dn:
            try:
                ldap_user = LdapUser.objects.get(dn=candidate_dn)
            except LdapUser.DoesNotExist:
                ldap_user = None

        if ldap_user is None:
            ldap_user = LdapUser.objects.filter(
                employee_number=str(employee.pk)
            ).first()

        if ldap_user is None:
            raise DirectoryServiceError(
                f"LDAP user not found for employee {employee.pk}"
            )

        actual_dn = str(ldap_user.dn)
        if actual_dn != candidate_dn:
            self._touch_state(
                model="employee",
                object_pk=employee.pk,
                ldap_dn=actual_dn,
                sync_dir=SyncDirection.AUTO,
            )

        return ldap_user

    def _move_employee_to_base_dn(
        self,
        employee: Employee,
        target_base_dn: str,
        *,
        current_dn: Optional[str] = None,
    ) -> str:
        """Перемещает сотрудника через ORM-модель LdapUser."""
        ldap_user = self._load_ldap_user(employee, expected_dn=current_dn)
        _, current_parent = self._split_rdn_parent(str(ldap_user.dn))
        if current_parent.lower() == target_base_dn.lower():
            return str(ldap_user.dn)

        ldap_user.base_dn = target_base_dn
        ldap_user.save()
        return str(ldap_user.dn)

    def _load_ou_group(self, group_dn: str) -> LdapOrganizationalUnitGroup:
        """Возвращает high-level LDAP модель группы внутри OU отдела."""
        try:
            return LdapOrganizationalUnitGroup.objects.get(dn=group_dn)
        except LdapOrganizationalUnitGroup.DoesNotExist as e:
            raise DirectoryServiceError(f"Group not found: {group_dn}") from e

    def _add_ou_group_member(self, group_dn: str, member_dn: str) -> None:
        """Добавляет DN в группу отдела/роли через ORM модель."""
        group = self._load_ou_group(group_dn)
        members = list(group.member or [])
        if member_dn not in members:
            members.append(member_dn)
            group.member = members
            group.save()

    def _remove_ou_group_member(self, group_dn: str, member_dn: str) -> None:
        """Удаляет DN из группы отдела/роли через ORM модель."""
        group = self._load_ou_group(group_dn)
        members = list(group.member or [])
        if member_dn in members:
            members.remove(member_dn)
            group.member = members
            group.save()

    # ==================== Public API ==================== #

    def sync_department_state(
        self,
        dept: Department,
        *,
        created: bool,
        changes: Optional[Dict[str, Any]] = None,
        sync_head: bool = False,
    ) -> str:
        """Приводит LDAP состояние отдела к текущему состоянию в Django.

        Метод предназначен для сигналов и retry-очереди: Django уже содержит
        истинное состояние, а здесь выполняется только LDAP reconcile.
        """
        self._ensure_runtime_services()

        normalized_changes = {
            key: value for key, value in (changes or {}).items() if key in {"name", "description"}
        }

        sync_state = LdapSyncState.objects.filter(
            model="department", object_pk=str(dept.pk)
        ).first()
        needs_bootstrap = created or not sync_state or not sync_state.ldap_dn

        if needs_bootstrap:
            dept_dn = self._ensure_department_ou(dept.name)
            self._touch_state(
                model="department",
                object_pk=dept.pk,
                ldap_dn=dept_dn,
                last_django_modify_ts=timezone.now(),
                sync_dir=SyncDirection.AUTO,
            )
            self._set_ou_description(dept_dn, dept.description or "")
            head_dn = None
            if dept.head_id:
                try:
                    head_dn = self._user_service._get_employee_dn(dept.head)
                except Exception:
                    head_dn = None
            self._set_ou_managed_by(dept_dn, head_dn)
            self._reconcile_department_group(dept, dept_dn)
            return dept_dn

        update_changes: Dict[str, Any] = {}
        if "name" in normalized_changes:
            update_changes["name"] = dept.name
        if "description" in normalized_changes:
            update_changes["description"] = dept.description
        if sync_head:
            update_changes["head"] = dept.head

        if update_changes:
            self.update_department(dept, update_changes)

        return self._get_department_dn(dept)

    def sync_department_delete(
        self,
        *,
        object_pk: str | int,
        dept_dn: Optional[str] = None,
    ) -> None:
        """Удаляет LDAP следы отдела после удаления Django-записи."""
        self._ensure_runtime_services()

        object_pk = str(object_pk)
        resolved_dept_dn = dept_dn or (
            LdapSyncState.objects.filter(
                model="department", object_pk=object_pk
            )
            .values_list("ldap_dn", flat=True)
            .first()
        )
        if not resolved_dept_dn:
            return

        self._evict_all_users_from_department_ou(resolved_dept_dn)

        for role in DepartmentRole.objects.filter(
            department_id=object_pk
        ).exclude(ldap_group_dn=""):
            self.delete_role_group(role)

        dept = Department.objects.filter(pk=object_pk).first()
        if dept and dept.ldap_group_dn:
            try:
                self._load_ou_group(dept.ldap_group_dn).delete()
            except Exception:
                pass

        self._delete_department_ou(resolved_dept_dn)

        LdapSyncState.objects.filter(
            model="department", object_pk=object_pk
        ).delete()

    def sync_member_state(
        self,
        employee: Employee,
        department: Department,
        *,
        is_active: bool,
        role: Any = None,
    ) -> None:
        """Приводит LDAP-состояние членства сотрудника в отделе к DB state."""
        self._ensure_runtime_services()

        try:
            emp_dn = self._user_service._get_employee_dn(employee)
        except Exception:
            self._logger.debug(
                "Employee %s has no LDAP DN, skipping member sync",
                employee.pk,
            )
            return

        if is_active:
            dept_dn = self.sync_department_state(
                department,
                created=False,
                changes=None,
                sync_head=False,
            )
            emp_dn = self._move_employee_to_base_dn(
                employee,
                dept_dn,
                current_dn=emp_dn,
            )
            group_dn = self._ensure_department_group(department, dept_dn)
            if group_dn:
                self._add_ou_group_member(group_dn, emp_dn)
        else:
            grp_dn = (department.ldap_group_dn or "").strip()
            if grp_dn:
                try:
                    self._remove_ou_group_member(grp_dn, emp_dn)
                except Exception:
                    pass

            target_base = get_base_dn_for_employee(employee)
            emp_dn = self._move_employee_to_base_dn(
                employee,
                target_base,
                current_dn=emp_dn,
            )

        self._reconcile_member_role_memberships(
            employee,
            department,
            is_active=is_active,
            role=role,
        )

    def create_department(self, dto: DirectoryDepartmentDTO) -> Department:
        """Создаёт OU отдела в LDAP и согласованную запись Department в БД.

        Args:
            dto: Данные отдела.

        Returns:
            Department: Созданный отдел.

        Raises:
            DirectoryLdapError: Не удалось создать/настроить OU в LDAP.
            DirectoryDbError: Не удалось создать запись в БД
            (OU будет удалён).
        """
        self._ensure_runtime_services()

        dept_dn: Optional[str] = None
        group_dn: Optional[str] = None
        try:
            dept_dn = self._ensure_department_ou(dto.name)
            self._set_ou_description(dept_dn, dto.description or "")
            head_dn = None
            if dto.head:
                try:
                    head_dn = self._user_service._get_employee_dn(dto.head)
                except Exception:
                    head_dn = None
            self._set_ou_managed_by(dept_dn, head_dn)
            group_dn = self._ensure_department_group(
                Department(name=dto.name, ldap_group_dn=""),
                dept_dn,
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
                self._reconcile_department_group(dept, dept_dn)
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
                    self._load_ou_group(group_dn).delete()
                if dept_dn:
                    self._delete_department_ou(dept_dn)
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
        self._ensure_runtime_services()

        try:
            current_dn = self._get_department_dn(dept)
        except DirectoryServiceError as e:
            raise DirectoryServiceError(
                f"Не найден DN отдела (sync state): {e}"
            ) from e

        new_dn = current_dn
        target_name = str(changes.get("name") or dept.name or "").strip()
        target_description = changes.get("description", dept.description)
        target_head = changes.get("head", dept.head)

        try:
            ou = self._get_department_ou(current_dn)
            desired_rdn = f"OU={target_name}" if target_name else ""
            current_rdn = current_dn.split(",", 1)[0]
            name_changed = bool(
                "name" in changes and target_name and current_rdn != desired_rdn
            )

            if name_changed:
                ou.ou = target_name
            if "description" in changes:
                ou.description = target_description or ""
            if "head" in changes:
                head_dn = None
                if target_head:
                    try:
                        head_dn = self._user_service._get_employee_dn(target_head)
                    except Exception:
                        head_dn = None
                ou.managed_by = head_dn or ""
            if name_changed or "description" in changes or "head" in changes:
                ou.save()
            new_dn = str(ou.dn)
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
        self._reconcile_department_group(dept, new_dn)
        return dept

    def delete_department(self, dept: Department) -> None:
        """Удаляет отдел: исключает сотрудников → удаляет группу → OU → БД.

        Args:
            dept: Отдел для удаления.

        Raises:
            DirectoryLdapError: Ошибка при удалении в LDAP.
            DirectoryDbError: Ошибка при удалении из БД.
        """
        self._ensure_runtime_services()

        try:
            dept_dn = self._get_department_dn(dept)
        except DirectoryServiceError:
            dept_dn = None

        try:
            if dept.ldap_group_dn:
                self._load_ou_group(dept.ldap_group_dn).delete()
        except Exception:
            pass

        if dept_dn:
            try:
                self._evict_all_users_from_department_ou(dept_dn)
                self._delete_department_ou(dept_dn)
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
        self._ensure_runtime_services()

        existing_link = EmployeeDepartment.objects.filter(
            employee_id=employee.id, is_active=True
        ).first()
        if existing_link:
            raise DirectoryServiceError(
                f"Сотрудник уже состоит в отделе: {
                    existing_link.department.name
                }"
            )

        emp_dn = self._user_service._get_employee_dn(employee)
        try:
            dept_dn = None
            try:
                dept_dn = self._get_department_dn(dept)
            except DirectoryServiceError:
                dept_dn = None
            ensured_dn = self._ensure_department_ou(dept.name)
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
            raise DirectoryLdapError(f"LDAP ensure OU failed: {e}") from e

        try:
            emp_dn = self._move_employee_to_base_dn(
                employee,
                dept_dn,
                current_dn=emp_dn,
            )
            group_dn = self._ensure_department_group(dept, dept_dn)
            if not group_dn:
                raise RuntimeError(
                    "_ensure_department_group returned empty DN"
                )
            self._add_ou_group_member(group_dn, emp_dn)
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
        """Удаляет сотрудника из отдела:
        из группы → MOVE в Users OU → удаление линка.

        Args:
            dept: Отдел.
            employee: Сотрудник для удаления.

        Raises:
            DirectoryServiceError: Если пытаемся удалить руководителя.
            DirectoryLdapError: Ошибка при удалении из LDAP.
            DirectoryDbError: Ошибка при удалении связи в БД.
        """
        self._ensure_runtime_services()

        if dept.head_id == employee.id:
            raise DirectoryServiceError("Нельзя удалить руководителя отдела")

        try:
            emp_dn = self._user_service._get_employee_dn(employee)
        except DirectoryServiceError:
            emp_dn = None

        try:
            grp_dn = (dept.ldap_group_dn or "").strip()
            if grp_dn and emp_dn:
                self._remove_ou_group_member(grp_dn, emp_dn)
        except Exception:
            pass

        if emp_dn:
            try:
                target_base = get_base_dn_for_employee(employee)
            except RuntimeError as e:
                raise DirectoryLdapError(str(e)) from e

            try:
                self._move_employee_to_base_dn(
                    employee,
                    target_base,
                    current_dn=emp_dn,
                )
            except Exception as e:
                target_name = (
                    "Dismissed OU" if not employee.is_active else "Users OU"
                )
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

    def set_head(
        self, dept: Department, head: Optional[Employee]
    ) -> Department:
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
        self._ensure_runtime_services()

        try:
            dept_dn = None
            try:
                dept_dn = self._get_department_dn(dept)
            except DirectoryServiceError:
                dept_dn = None
            ensured_dn = self._ensure_department_ou(dept.name)
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
            self._set_ou_managed_by(dept_dn, head_dn)
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
        self._reconcile_department_group(dept, dept_dn)

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
        self._ensure_runtime_services()

        # 1. Создаём группу в LDAP
        dept_dn = self._get_department_dn(department)
        role_name = self._sanitize_name(name)
        cn = f"ROLE_{role_name}"
        group_dn = f"CN={esc_rdn(cn)},{dept_dn}"

        try:
            if not LdapOrganizationalUnitGroup.objects.filter(dn=group_dn).exists():
                role_group = LdapOrganizationalUnitGroup(
                    dn=group_dn,
                    cn=cn,
                    sam_account_name=cn[:20],
                    description=description
                    or f"Role: {name} in {department.name}",
                )
                role_group.save()
        except Exception as e:
            raise DirectoryLdapError(
                f"LDAP create role group failed: {e}"
            ) from e

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
            try:
                self._load_ou_group(group_dn).delete()
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
            changes: Словарь изменений
            (name, scoped_permissions, scoped_permission_codes).

        Returns:
            DepartmentRole: Обновлённая роль.

        Raises:
            DirectoryLdapError: Ошибка обновления в LDAP.
            DirectoryDbError: Ошибка сохранения в БД.
        """
        self._ensure_runtime_services()

        new_name = changes.get("name")

        # Если меняется имя — переименовываем группу в LDAP
        if new_name and new_name != role.name:
            if role.ldap_group_dn:
                try:
                    new_role_name = self._sanitize_name(new_name)
                    new_cn = f"ROLE_{new_role_name}"
                    role_group = LdapOrganizationalUnitGroup.objects.get(
                        dn=role.ldap_group_dn
                    )
                    role_group.cn = new_cn
                    role_group.save()
                    new_dn = str(role_group.dn)
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
        self._ensure_runtime_services()

        # 1. Удаляем группу из LDAP
        if role.ldap_group_dn:
            try:
                self._load_ou_group(role.ldap_group_dn).delete()
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
        self._ensure_runtime_services()

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
        self._ensure_runtime_services()

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
                    },
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
        self._ensure_runtime_services()

        # 1. Сначала удаляем из LDAP-группы
        try:
            self._sync_role_membership(employee, role, add=False)
        except Exception as e:
            raise DirectoryLdapError(f"LDAP role revoke failed: {e}") from e

        # 2. Только при успехе LDAP — деактивируем назначение
        RoleAssignment.objects.filter(employee=employee, role=role).update(
            is_active=False
        )

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
        self._ensure_runtime_services()

        # Создаём группу роли если нет
        if not role.ldap_group_dn:
            self._ensure_role_group(role)

        if not role.ldap_group_dn:
            return  # Не удалось создать группу

        user_dn = self._user_service._get_employee_dn(employee)
        if add:
            self._add_ou_group_member(role.ldap_group_dn, user_dn)
        else:
            self._remove_ou_group_member(role.ldap_group_dn, user_dn)

    def _resolve_member_roles(
        self,
        employee: Employee,
        dept: Department,
        role_hint: Any = None,
    ) -> List[DepartmentRole]:
        """Собирает целевой набор ролей для LDAP sync в рамках одного отдела."""
        roles_by_id: Dict[int, DepartmentRole] = {}

        def add_role(role_obj: Optional[DepartmentRole]) -> None:
            if (
                role_obj is not None
                and role_obj.department_id == dept.id
                and role_obj.pk not in roles_by_id
            ):
                roles_by_id[role_obj.pk] = role_obj

        active_link = EmployeeDepartment.objects.filter(
            employee_id=employee.id,
            department_id=dept.id,
            is_active=True,
        ).select_related("role").first()
        if active_link and active_link.role_id:
            add_role(active_link.role)

        assigned_roles = DepartmentRole.objects.filter(
            department_id=dept.id,
            assignments__employee_id=employee.id,
            assignments__is_active=True,
        ).distinct()
        for assigned_role in assigned_roles:
            add_role(assigned_role)

        if isinstance(role_hint, DepartmentRole):
            add_role(role_hint)
        elif isinstance(role_hint, int) or (
            isinstance(role_hint, str) and role_hint.isdigit()
        ):
            role_obj = DepartmentRole.objects.filter(
                department_id=dept.id,
                pk=int(role_hint),
            ).first()
            add_role(role_obj)
        elif isinstance(role_hint, str) and role_hint.strip():
            hint = role_hint.strip()
            role_obj = DepartmentRole.objects.filter(
                department_id=dept.id,
                name=hint,
            ).first()
            if role_obj is None and ": " in hint:
                role_name = hint.split(": ", 1)[1].strip()
                role_obj = DepartmentRole.objects.filter(
                    department_id=dept.id,
                    name=role_name,
                ).first()
            add_role(role_obj)

        return list(roles_by_id.values())

    def _reconcile_member_role_memberships(
        self,
        employee: Employee,
        dept: Department,
        *,
        is_active: bool,
        role: Any = None,
    ) -> None:
        """Синхронизирует LDAP группы ролей сотрудника по текущему DB state."""
        self._ensure_runtime_services()

        desired_role_ids = {
            item.pk
            for item in (
                self._resolve_member_roles(employee, dept, role) if is_active else []
            )
        }
        dept_roles = list(
            DepartmentRole.objects.filter(department_id=dept.id).order_by("pk")
        )
        for dept_role in dept_roles:
            self._sync_role_membership(
                employee,
                dept_role,
                add=dept_role.pk in desired_role_ids,
            )

    def _ensure_role_group(self, role: DepartmentRole) -> str:
        """Гарантирует наличие группы роли ROLE_<Name> в OU отдела.

        Args:
            role: Роль отдела.

        Returns:
            str: DN группы роли.
        """
        self._ensure_runtime_services()

        dept = role.department
        dept_dn = self._get_department_dn(dept)

        role_name = self._sanitize_name(role.name)
        expected_cn = f"ROLE_{role_name}"
        expected_dn = f"CN={esc_rdn(expected_cn)},{dept_dn}"

        saved_dn = (role.ldap_group_dn or "").strip()
        role_group: Optional[LdapOrganizationalUnitGroup] = None

        for candidate_dn in (saved_dn, expected_dn):
            if not candidate_dn:
                continue
            try:
                role_group = LdapOrganizationalUnitGroup.objects.get(
                    dn=candidate_dn
                )
                break
            except LdapOrganizationalUnitGroup.DoesNotExist:
                continue

        if role_group is None:
            role_group = LdapOrganizationalUnitGroup(
                dn=expected_dn,
                cn=expected_cn,
                sam_account_name=expected_cn[:20],
                description=f"Role: {role.name} in {dept.name}",
            )
            role_group.save()
        else:
            group_changed = False
            _, current_parent = self._split_rdn_parent(str(role_group.dn))
            if current_parent.lower() != dept_dn.lower():
                role_group.base_dn = dept_dn
                group_changed = True
            if role_group.cn != expected_cn:
                role_group.cn = expected_cn
                group_changed = True
            expected_description = f"Role: {role.name} in {dept.name}"
            if (role_group.description or "") != expected_description:
                role_group.description = expected_description
                group_changed = True
            if group_changed:
                role_group.save()

        resolved_dn = str(role_group.dn)
        DepartmentRole.objects.filter(pk=role.pk).update(ldap_group_dn=resolved_dn)
        role.ldap_group_dn = resolved_dn
        return resolved_dn

    def rename_role_group(self, role: DepartmentRole, new_name: str) -> str:
        """Переименовывает группу роли в LDAP.

        Args:
            role: Роль.
            new_name: Новое название роли.

        Returns:
            str: Новый DN группы.
        """
        self._ensure_runtime_services()

        if not role.ldap_group_dn:
            # Группы нет — создаём с новым именем
            role.name = new_name
            return self._ensure_role_group(role)

        new_role_name = self._sanitize_name(new_name)
        new_cn = f"ROLE_{new_role_name}"

        role_group = LdapOrganizationalUnitGroup.objects.get(dn=role.ldap_group_dn)
        role_group.cn = new_cn
        role_group.save()
        new_dn = str(role_group.dn)

        DepartmentRole.objects.filter(pk=role.pk).update(ldap_group_dn=new_dn)
        role.ldap_group_dn = new_dn
        return new_dn

    def delete_role_group(self, role: DepartmentRole) -> None:
        """Удаляет группу роли из LDAP.

        Args:
            role: Роль для удаления группы.
        """
        self._ensure_runtime_services()

        if not role.ldap_group_dn:
            return

        try:
            role_group = LdapOrganizationalUnitGroup.objects.get(
                dn=role.ldap_group_dn
            )
            role_group.delete()
        except LdapOrganizationalUnitGroup.DoesNotExist:
            pass

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
        clean = re.sub(r'[,=+<>#;\\"\']', "", name)
        clean = re.sub(r"\s+", "_", clean)
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

    def _get_department_ou(self, dept_dn: str) -> LdapOrganizationalUnit:
        """Возвращает high-level LDAP модель OU отдела по DN."""
        try:
            return LdapOrganizationalUnit.objects.get(dn=dept_dn)
        except LdapOrganizationalUnit.DoesNotExist as e:
            raise DirectoryServiceError(f"OU not found: {dept_dn}") from e

    def _ensure_department_ou(self, name: str) -> str:
        """Гарантирует наличие OU отдела через ORM-модель."""
        base = getattr(settings, "LDAP_DEPARTMENTS_BASE", None)
        if not base:
            raise RuntimeError("LDAP_DEPARTMENTS_BASE is not configured")
        dn = f"OU={name},{base}"
        try:
            ou = LdapOrganizationalUnit.objects.get(dn=dn)
        except LdapOrganizationalUnit.DoesNotExist:
            ou = LdapOrganizationalUnit(
                dn=dn,
                ou=name,
                description="",
                managed_by="",
            )
            ou.save()
        return str(ou.dn)

    def _rename_department_ou(self, dept_dn: str, new_name: str) -> str:
        """Переименовывает OU отдела через ModifyDnMixin."""
        ou = self._get_department_ou(dept_dn)
        ou.ou = new_name
        ou.save()
        return str(ou.dn)

    def _set_ou_managed_by(self, dept_dn: str, head_dn: Optional[str]) -> None:
        """Устанавливает/очищает managedBy у OU в AD через ORM.

        Args:
            dept_dn: DN OU отдела.
            head_dn: DN руководителя или None.
        """
        if not dept_dn:
            raise DirectoryServiceError("dept_dn пуст")

        ou = self._get_department_ou(dept_dn)

        current = (ou.managed_by or "").strip().lower()
        target = (head_dn or "").strip().lower()

        if current == target:
            return

        ou.managed_by = head_dn or ""
        ou.save()

    def _set_ou_description(
        self, dept_dn: str, description: Optional[str]
    ) -> None:
        """Ставит/очищает description у OU (ORM).

        Args:
            dept_dn: DN OU отдела.
            description: Описание или None для удаления.
        """
        try:
            ou = LdapOrganizationalUnit.objects.get(dn=dept_dn)
            ou.description = description or ""
            ou.save()
        except LdapOrganizationalUnit.DoesNotExist:
            pass

    def _delete_department_ou(self, dept_dn: str) -> None:
        """Удаляет OU (ORM, ignore DoesNotExist).

        Args:
            dept_dn: DN OU для удаления.
        """
        try:
            ou = LdapOrganizationalUnit.objects.get(dn=dept_dn)
            ou.delete()
        except LdapOrganizationalUnit.DoesNotExist:
            pass

    def _evict_all_users_from_department_ou(self, dept_dn: str) -> None:
        """Перемещает всех пользователей из OU отдела через LdapUser ORM.

        Args:
            dept_dn: DN OU отдела.

        Raises:
            RuntimeError: Если не настроен LDAP_USERS_BASE.
        """
        self._ensure_runtime_services()

        suffix = f",{dept_dn}".lower()
        states = list(
            LdapSyncState.objects.filter(
                model="employee",
                ldap_dn__iendswith=suffix,
            ).exclude(ldap_dn="")
        )
        for state in states:
            employee = Employee.objects.filter(pk=state.object_pk).first()
            if employee is None:
                continue
            target_base = get_base_dn_for_employee(employee)
            self._move_employee_to_base_dn(
                employee,
                target_base,
                current_dn=state.ldap_dn,
            )

    # ==================== Private Group Methods ==================== #

    def _ensure_department_group(self, dept: Department, dept_dn: str) -> str:
        """Гарантирует наличие группы отдела через ORM-модель."""
        self._ensure_runtime_services()

        name = (dept.name or "").strip()
        if not name:
            raise ValueError("Department.name is empty")

        expected_cn = f"DEP_{name}"
        expected_dn = f"CN={esc_rdn(expected_cn)},{dept_dn}"
        expected_description = f"{name} department members"
        saved_dn = (dept.ldap_group_dn or "").strip()

        candidate_dns: List[str] = []
        for candidate in (
            saved_dn,
            (
                f"{saved_dn.split(',', 1)[0]},{dept_dn}"
                if saved_dn and "," in saved_dn
                else ""
            ),
            expected_dn,
        ):
            if candidate and candidate not in candidate_dns:
                candidate_dns.append(candidate)

        group: Optional[LdapOrganizationalUnitGroup] = None
        for candidate_dn in candidate_dns:
            try:
                group = LdapOrganizationalUnitGroup.objects.get(dn=candidate_dn)
                break
            except LdapOrganizationalUnitGroup.DoesNotExist:
                continue

        if group is None:
            group = LdapOrganizationalUnitGroup(
                dn=expected_dn,
                cn=expected_cn,
                sam_account_name=expected_cn[:20],
                description=expected_description,
            )
            group.save()
        else:
            group_changed = False
            _, current_parent = self._split_rdn_parent(str(group.dn))
            if current_parent.lower() != dept_dn.lower():
                group.base_dn = dept_dn
                group_changed = True
            if group.cn != expected_cn:
                group.cn = expected_cn
                group_changed = True
            if (group.description or "") != expected_description:
                group.description = expected_description
                group_changed = True
            if group_changed:
                group.save()

        group_dn = str(group.dn)
        if dept.pk:
            Department.objects.filter(pk=dept.pk).update(ldap_group_dn=group_dn)
        dept.ldap_group_dn = group_dn
        return group_dn

    def _reconcile_department_group(
        self, dept: Department, dept_dn: Optional[str]
    ) -> str:
        """Приводит состав группы отдела к активным EmployeeDepartment.

        Args:
            dept: Модель отдела.
            dept_dn: DN OU отдела (если None, будет запрошен).

        Returns:
            str: DN группы отдела.
        """
        self._ensure_runtime_services()

        dept_dn = dept_dn or self._get_department_dn(dept)
        group_dn = self._ensure_department_group(dept, dept_dn)
        group = LdapOrganizationalUnitGroup.objects.get(dn=group_dn)

        active_emp_ids = list(
            EmployeeDepartment.objects.filter(
                department_id=dept.id, is_active=True
            ).values_list("employee_id", flat=True)
        )
        if not active_emp_ids:
            group.member = []
            group.save()
            return group_dn

        dn_map = dict(
            LdapSyncState.objects.filter(
                model="employee",
                object_pk__in=[str(i) for i in active_emp_ids],
            ).values_list("object_pk", "ldap_dn")
        )
        member_dns = [dn for dn in dn_map.values() if dn]

        group.member = member_dns
        group.save()
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
        """Переписывает хвост DN у sync-state сотрудников и role group DN.

        Вызывается после переименования OU отдела.

        Args:
            old_dn: Старый DN OU.
            new_dn: Новый DN OU.

        Returns:
            Tuple[int, int]: (обновлено role group DN,
            обновлено employee sync-state).
        """
        old_suffix = f",{old_dn}".lower()
        new_suffix = f",{new_dn}"

        role_updated_count = 0
        roles = list(
            DepartmentRole.objects.filter(ldap_group_dn__iendswith=old_suffix)
        )
        for role in roles:
            old_role_dn = role.ldap_group_dn or ""
            if not old_role_dn.lower().endswith(old_suffix):
                continue
            rdn = old_role_dn[: -len(old_suffix)]
            role.ldap_group_dn = rdn + new_suffix
            role.save(update_fields=["ldap_group_dn"])
            role_updated_count += 1

        states = list(
            LdapSyncState.objects.filter(
                model="employee", ldap_dn__iendswith=old_suffix
            )
        )
        if not states:
            return role_updated_count, 0

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
        return role_updated_count, updated_count


__all__ = ["DepartmentService"]
