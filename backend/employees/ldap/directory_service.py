from __future__ import annotations

from typing import Any, Dict, List, Optional, Set

from employees.models import LdapSyncState
from ldap3 import Connection

from ..models import Department, DepartmentRole, Employee, Position
from .domain.dtos import DirectoryDepartmentDTO, DirectoryUserDTO

# ------------------------- Сервис LDAP → DB ------------------------- #


class DirectoryService:
    """Высокоуровневый сервис синхронизации LDAP ↔ DB.

    Правило порядка операций:
        1) LDAP
        2) DB (transaction.atomic)
        3) Post-actions (best effort)

    В случае падения БД выполняется best-effort компенсация LDAP, где разумно.

    NOTE: Этот класс постепенно рефакторится. Методы работы с пользователями
    делегируются к UserService (см. services/user_service.py).
    """

    def __init__(self):
        """Инициализация сервиса и подсервисов."""
        from .services.department_service import DepartmentService
        from .services.group_service import GroupService
        from .services.position_service import PositionService
        from .services.user_service import UserService

        self._user_service = UserService()
        self._group_service = GroupService(directory_service=self)
        self._department_service = DepartmentService(
            group_service=self._group_service, user_service=self._user_service
        )
        self._position_service = PositionService(
            group_service=self._group_service, user_service=self._user_service
        )

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

    # ==================== NEW ARCHITECTURE: PURE LDAP METHODS ==================== #

    def create_user_in_ldap_only(self, dto: DirectoryUserDTO, password: str = None) -> dict[str, Any]:
        """Создаёт пользователя ТОЛЬКО в LDAP, возвращает данные для БД.

        Новая архитектура для разделения ответственности:
        - View создает Employee в БД (в транзакции)
        - Затем вызывает этот метод для синхронизации в LDAP
        - View обрабатывает результат и откатывает БД при ошибке LDAP

        Args:
            dto (DirectoryUserDTO): Данные нового пользователя.
            password (str, optional): Пароль пользователя для LDAP.

        Returns:
            dict: Данные для сохранения в БД:
                - ldap_dn (str): DN пользователя в LDAP
                - ldap_guid (str): GUID пользователя в LDAP

        Raises:
            DirectoryLdapError: Ошибка на этапе создания/настройки LDAP.
        """
        # Если передан пароль, устанавливаем его в DTO
        if password and not dto.initial_password:
            dto.initial_password = password

        return self._user_service.create_user_in_ldap_only(dto)

    def update_user_in_ldap_only(
        self,
        instance: Employee,
        changes: Dict[str, Any],
        move_to_department_dn: Optional[str] = None,
        group_cns: Optional[List[str]] = None
    ) -> dict[str, Any]:
        """Обновляет пользователя ТОЛЬКО в LDAP.

        Новая архитектура: View обновляет БД, затем синхронизирует в LDAP.

        Args:
            instance (Employee): Инстанс сотрудника с актуальными данными из БД.
            changes (Dict[str, Any]): Изменения из request.data для синхронизации в LDAP.
            move_to_department_dn (Optional[str]): DN отдела для перемещения.
            group_cns (Optional[List[str]]): Список CN групп для синхронизации.

        Returns:
            dict: Пустой dict или данные для дополнительного обновления БД.

        Raises:
            DirectoryLdapError: Ошибка синхронизации с LDAP.
        """
        return self._user_service.update_user_in_ldap_only(
            instance, changes, move_to_department_dn, group_cns
        )

    def delete_user_in_ldap_only(self, instance: Employee) -> None:
        """Удаляет пользователя ТОЛЬКО из LDAP.

        Новая архитектура: View удаляет из БД, затем удаляет из LDAP.

        Args:
            instance (Employee): Сотрудник для удаления из LDAP.

        Raises:
            DirectoryLdapError: Ошибка удаления из LDAP.
        """
        return self._user_service.delete_user_in_ldap_only(instance)

    # ==================== OLD ARCHITECTURE: LDAP + DB ==================== #

    def create_user(self, dto: DirectoryUserDTO) -> Employee:
        """Создаёт учётку в LDAP и запись в БД (DN/связь — только в LdapSyncState).

        NOTE: Метод делегирует к UserService для выполнения операции.

        Args:
            dto (DirectoryUserDTO): Данные нового пользователя.

        Returns:
            Employee: Созданный сотрудник.

        Raises:
            DirectoryLdapError: Ошибка на этапе создания/настройки LDAP.
            DirectoryDbError: Ошибка записи в БД.
        """
        return self._user_service.create_user(dto)

    def update_user(
        self,
        emp: Employee,
        changes: Dict[str, Any],
        group_cns: Optional[List[str]] = None,
        move_to_department_dn: Optional[str] = None,
    ) -> Employee:
        """Обновляет пользователя: LDAP (пароль/MOVE/UAC/attrs/groups) → затем БД.

        NOTE: Метод делегирует к UserService для выполнения операции.

        Args:
            emp (Employee): Сотрудник, которого обновляем.
            changes (Dict[str, Any]): Поля модели для обновления.
            group_cns (Optional[List[str]]): Полный набор CN для синхронизации.
            move_to_department_dn (Optional[str]): DN OU, куда переместить.

        Returns:
            Employee: Обновлённая модель.

        Raises:
            DirectoryLdapError: Ошибка применения изменений в LDAP.
            DirectoryDbError: Ошибка фиксации изменений в БД.
            DirectoryServiceError: Нет DN пользователя.
        """
        return self._user_service.update_user(
            emp, changes, group_cns, move_to_department_dn
        )

    def delete_user(self, emp: Employee) -> None:
        """Удаляет пользователя: LDAP soft-disable → DB delete → LDAP hard delete.

        NOTE: Метод делегирует к UserService для выполнения операции.

        Args:
            emp (Employee): Удаляемый сотрудник.

        Raises:
            DirectoryLdapError: Ошибка при soft-disable/hard-delete в LDAP.
            DirectoryDbError: Ошибка при удалении записи в БД.
        """
        return self._user_service.delete_user(emp)

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
        return self._department_service.create_department(dto)

    def update_department(
        self, dept: Department, changes: Dict[str, Any]
    ) -> Department:
        """Обновляет OU отдела, одноименную группу и запись Department."""
        return self._department_service.update_department(dept, changes)

    def delete_department(self, dept: Department) -> None:
        """Удаляет отдел: исключает сотрудников → удаляет группу → OU → БД."""
        return self._department_service.delete_department(dept)

    def add_member(self, dept: Department, employee: Employee) -> None:
        """Добавляет сотрудника в OU отдела и в одноименную группу отдела."""
        return self._department_service.add_member(dept, employee)

    def remove_member(self, dept: Department, employee: Employee) -> None:
        """Удаляет сотрудника из отдела: из группы → MOVE → удаление линка."""
        return self._department_service.remove_member(dept, employee)

    def set_head(self, dept: Department, head: Optional[Employee]) -> Department:
        """Назначает/снимает руководителя отдела: LDAP managedBy → DB.head."""
        return self._department_service.set_head(dept, head)

    def set_member_role(
        self, dept: Department, employee: Employee, role: Optional[DepartmentRole]
    ) -> None:
        """Меняет роль участника с синхронизацией LDAP-групп Roles."""
        return self._department_service.set_member_role(dept, employee, role)

    def assign_role(
        self,
        employee: Employee,
        role: DepartmentRole,
        assigned_by: Optional[Employee] = None,
    ):
        """Назначает роль сотруднику (не требует членства в отделе).

        NOTE: Метод делегирует к DepartmentService.

        Args:
            employee: Сотрудник.
            role: Роль для назначения.
            assigned_by: Кто назначил (опционально).

        Returns:
            RoleAssignment: Созданное/обновлённое назначение.
        """
        return self._department_service.assign_role(employee, role, assigned_by)

    def revoke_role(self, employee: Employee, role: DepartmentRole) -> None:
        """Отзывает роль у сотрудника.

        NOTE: Метод делегирует к DepartmentService.

        Args:
            employee: Сотрудник.
            role: Роль для отзыва.
        """
        return self._department_service.revoke_role(employee, role)

    def create_role(
        self,
        dept: Department,
        name: str,
        permission_codes: Optional[List[str]] = None,
    ) -> DepartmentRole:
        """Создаёт роль отдела с LDAP-группой.

        NOTE: Метод делегирует к DepartmentService.

        Args:
            dept: Отдел.
            name: Название роли.
            permission_codes: Коды прав (опционально).

        Returns:
            DepartmentRole: Созданная роль.
        """
        from employees.models import DepartmentPermission

        scoped_permissions = None
        if permission_codes:
            scoped_permissions = list(
                DepartmentPermission.objects.filter(code__in=permission_codes)
            )

        return self._department_service.create_role(
            department=dept,
            name=name,
            scoped_permissions=scoped_permissions,
        )

    def update_role(
        self, role: DepartmentRole, name: Optional[str] = None
    ) -> DepartmentRole:
        """Обновляет роль (переименование LDAP-группы + БД).

        NOTE: Метод делегирует к DepartmentService.

        Args:
            role: Роль.
            name: Новое название (опционально).

        Returns:
            DepartmentRole: Обновлённая роль.
        """
        changes = {}
        if name:
            changes["name"] = name

        return self._department_service.update_role(role, changes)

    def delete_role(self, role: DepartmentRole) -> None:
        """Удаляет роль: LDAP-группу + БД.

        NOTE: Метод делегирует к DepartmentService.

        Args:
            role: Роль для удаления.
        """
        return self._department_service.delete_role(role)

    def move_user_to_base(self, employee: Employee, base_dn: str) -> str:
        """Перемещает пользователя в указанный базовый OU.

        NOTE: Метод делегирует к UserService.

        Args:
            employee: Сотрудник для перемещения.
            base_dn: DN базового OU.

        Returns:
            str: Новый DN пользователя.

        Raises:
            DirectoryLdapError: Ошибка LDAP.
            DirectoryServiceError: Пользователь не имеет DN.
        """
        from .infrastructure.connections import _ldap

        sync_state = LdapSyncState.objects.filter(
            model="employee", object_pk=str(employee.pk)
        ).first()

        if not sync_state or not sync_state.ldap_dn:
            from .errors import DirectoryServiceError
            raise DirectoryServiceError(
                f"Employee {employee.pk} has no LDAP DN")

        with _ldap() as conn:
            new_dn = self._user_service._move_user_to_base(
                conn, sync_state.ldap_dn, base_dn
            )
            sync_state.touch(ldap_dn=new_dn, sync_dir="ldap")
            return new_dn

    # =========================== POSITIONS =========================== #

    def reconcile_position(self, pos: Position) -> str:
        """Публичный метод — открыть соединение и привести POS к консистентности."""
        return self._position_service.reconcile_position(pos)

    def assign_position(self, employee: Employee, position: Position) -> None:
        """
        Добавляет сотрудника в POS-группу должности и убеждается, что вложения POS в целевые группы актуальны.
        """
        self._position_service.assign_position(employee, position)

    def unassign_position(self, employee: Employee, position: Position) -> None:
        """
        Удаляет сотрудника из POS-группы должности.
        """
        self._position_service.unassign_position(employee, position)

    def delete_position_group(self, position: Position) -> None:
        """
        Best-effort: снять POS-группу из всех правовых групп и удалить её.
        """
        self._position_service.delete_position_group(position)

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
        """Создаёт группу в LDAP под указанным контейнером."""
        return self._group_service.create(
            conn,
            cn,
            parent_dn,
            description=description,
            scope=scope,
            security_enabled=security_enabled,
        )

    def delete_group(self, conn: Connection, group_dn: str) -> None:
        """Удаляет группу по DN (игнорирует noSuchObject)."""
        self._group_service.delete(conn, group_dn)

    def rename_group(self, conn: Connection, group_dn: str, new_cn: str) -> str:
        """Переименовывает группу (modify_dn)."""
        return self._group_service.rename(conn, group_dn, new_cn)

    def set_group_description(
        self, conn: Connection, group_dn: str, description: Optional[str]
    ) -> None:
        """Ставит/очищает description."""
        self._group_service.set_description(conn, group_dn, description)

    def sync_groups_catalog(
        self, *, throttle_seconds: int = 60, delete_absent: bool = False
    ) -> int:
        """
        Тянет группы из AD под LDAP_GROUPS_BASE и гарантирует их наличие в Django Group.
        Возвращает количество созданных групп. Обновляет LdapSyncState(model='group').
        Троттлит запросы к AD не чаще, чем раз в throttle_seconds.
        """
        return self._group_service.sync_catalog(
            throttle_seconds=throttle_seconds, delete_absent=delete_absent
        )

    def _modify_group_members(
        self, conn: Connection, group_dn: str, op: int, members: List[str]
    ) -> None:
        """Применяет операцию к членству группы (DRY-хелпер)."""
        self._group_service._modify_members(conn, group_dn, op, members)

    def add_group_members(
        self, conn: Connection, group_dn: str, member_dns: List[str]
    ) -> None:
        """Добавляет участников (member ADD)."""
        self._group_service.add_members(conn, group_dn, member_dns)

    def remove_group_members(
        self, conn: Connection, group_dn: str, member_dns: List[str]
    ) -> None:
        """Удаляет участников (member DELETE)."""
        self._group_service.remove_members(conn, group_dn, member_dns)

    def replace_group_members(
        self, conn: Connection, group_dn: str, exact_member_dns: List[str]
    ) -> None:
        """Полная замена состава группы."""
        self._group_service.replace_members(conn, group_dn, exact_member_dns)

    def list_group_members(self, conn: Connection, group_dn: str) -> List[str]:
        """Возвращает DN всех участников группы."""
        return self._group_service.list_members(conn, group_dn)

    def find_group_dn(
        self, conn: Connection, cn: str, bases: Optional[List[str]] = None
    ) -> Optional[str]:
        """Ищет DN группы по CN в заданных базах."""
        return self._group_service.find_dn(conn, cn, bases)

    # ============ LDAP HELPER METHODS (DEPARTMENT) ============ #

    def _ensure_department_ou(self, conn: Connection, name: str) -> str:
        """Гарантирует наличие OU отдела + OU=Roles."""
        return self._department_service._ensure_department_ou(conn, name)

    def _rename_department_ou(
        self, conn: Connection, dept_dn: str, new_name: str
    ) -> str:
        """Переименовывает OU отдела и возвращает новый DN."""
        return self._department_service._rename_department_ou(conn, dept_dn, new_name)

    def _set_ou_managed_by(
        self, conn: Connection, dept_dn: str, head_dn: Optional[str]
    ) -> None:
        """Устанавливает/очищает managedBy у OU в AD (идемпотентно и с no-op при пустом состоянии).

        Args:
            conn (Connection): LDAP соединение.
            dept_dn (str): DN OU отдела.
            head_dn (Optional[str]): DN руководителя или None.
        """
        return self._department_service._set_ou_managed_by(conn, dept_dn, head_dn)

    def _set_ou_description(
        self, conn: Connection, dept_dn: str, description: Optional[str]
    ) -> None:
        """Ставит/очищает description у OU."""
        return self._department_service._set_ou_description(conn, dept_dn, description)

    def _delete_department_ou(self, conn: Connection, dept_dn: str) -> None:
        """Удаляет OU (ignore noSuchObject)."""
        return self._department_service._delete_department_ou(conn, dept_dn)

    def _evict_all_users_from_department_ou(
        self, conn: Connection, dept_dn: str
    ) -> None:
        """Перемещает всех пользователей из OU отдела в Users base."""
        return self._department_service._evict_all_users_from_department_ou(
            conn, dept_dn
        )

    def _groups_with_member(self, conn: Connection, member_dn: str) -> Set[str]:
        """Возвращает множество DN групп, где member=member_dn."""
        return self._group_service.groups_with_member(conn, member_dn)

    def group_find_dn(
        self, cn: str, bases: Optional[list[str]] = None
    ) -> Optional[str]:
        from .infrastructure.connections import _ldap

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
        from .infrastructure.connections import _ldap

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
        from .infrastructure.connections import _ldap

        with _ldap() as conn:
            self.delete_group(conn, group_dn)

    def group_rename(self, group_dn: str, new_cn: str) -> str:
        from .infrastructure.connections import _ldap

        with _ldap() as conn:
            return self.rename_group(conn, group_dn, new_cn)

    def group_set_description(self, group_dn: str, description: Optional[str]) -> None:
        from .infrastructure.connections import _ldap

        with _ldap() as conn:
            self.set_group_description(conn, group_dn, description)

    def group_list_members(self, group_dn: str) -> list[str]:
        from .infrastructure.connections import _ldap

        with _ldap() as conn:
            return self.list_group_members(conn, group_dn)

    def group_add_members(self, group_dn: str, member_dns: list[str]) -> None:
        from .infrastructure.connections import _ldap

        with _ldap() as conn:
            self.add_group_members(conn, group_dn, member_dns)

    def group_remove_members(self, group_dn: str, member_dns: list[str]) -> None:
        from .infrastructure.connections import _ldap

        with _ldap() as conn:
            self.remove_group_members(conn, group_dn, member_dns)

    def group_replace_members(self, group_dn: str, exact_member_dns: list[str]) -> None:
        from .infrastructure.connections import _ldap

        with _ldap() as conn:
            self.replace_group_members(conn, group_dn, exact_member_dns)

    def employee_ids_to_dns(self, ids: list[int]) -> list[str]:
        """Конвертирует ID сотрудников в их Distinguished Names.

        NOTE: Метод делегирует к UserService.
        """
        return self._user_service.employee_ids_to_dns(ids)

    def dns_to_employee_ids(self, dns: list[str]) -> list[int]:
        """Конвертирует Distinguished Names в ID сотрудников.

        NOTE: Метод делегирует к UserService.
        """
        return self._user_service.dns_to_employee_ids(dns)

    def employees_brief_by_dns(self, dns: list[str]) -> list[dict]:
        """Получает краткую информацию о сотрудниках по их DN.

        NOTE: Метод делегирует к UserService.
        """
        return self._user_service.employees_brief_by_dns(dns)
