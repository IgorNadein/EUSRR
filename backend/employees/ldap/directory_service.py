from __future__ import annotations

from typing import Any, Dict, List, Optional

from employees.models import LdapSyncState

from ..models import Department, Employee
from .domain.dtos import DirectoryUserDTO, DirectoryDepartmentDTO

# ------------------------- Сервис LDAP → DB ------------------------- #


class DirectoryService:
    """Высокоуровневый сервис синхронизации LDAP ↔ DB.

    Правило порядка операций:
        1) LDAP
        2) DB (transaction.atomic)
        3) Post-actions (best effort)

    В случае падения БД выполняется best-effort компенсация LDAP, где разумно.
    """

    def __init__(self):
        """Инициализация сервиса и подсервисов."""
        from .services.department_service import DepartmentService
        from .services.user_service import UserService
        from .services.group_service import GroupService

        self._user_service = UserService()
        self._group_service = GroupService(directory_service=self)
        self._department_service = DepartmentService(
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

    # ======================== GROUPS ======================== #

    # --- Conn-based методы (используются внутри services) ---

    def find_group_dn(
        self, conn, cn: str, bases: Optional[List[str]] = None
    ) -> Optional[str]:
        """Ищет DN группы по CN в заданных базах."""
        return self._group_service.find_dn(conn, cn, bases)

    def add_group_members(
        self, conn, group_dn: str, member_dns: List[str]
    ) -> None:
        """Добавляет участников (member ADD)."""
        self._group_service.add_members(conn, group_dn, member_dns)

    def remove_group_members(
        self, conn, group_dn: str, member_dns: List[str]
    ) -> None:
        """Удаляет участников (member DELETE)."""
        self._group_service.remove_members(conn, group_dn, member_dns)

    # --- Высокоуровневые методы (используются в сигналах) ---

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
            return self._group_service.create(
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
            self._group_service.delete(conn, group_dn)

    def group_rename(self, group_dn: str, new_cn: str) -> str:
        from .infrastructure.connections import _ldap

        with _ldap() as conn:
            return self._group_service.rename(conn, group_dn, new_cn)

    def group_set_description(self, group_dn: str, description: Optional[str]) -> None:
        from .infrastructure.connections import _ldap

        with _ldap() as conn:
            self._group_service.set_description(conn, group_dn, description)

    def group_list_members(self, group_dn: str) -> list[str]:
        from .infrastructure.connections import _ldap

        with _ldap() as conn:
            return self._group_service.list_members(conn, group_dn)

    def group_add_members(self, group_dn: str, member_dns: list[str]) -> None:
        from .infrastructure.connections import _ldap

        with _ldap() as conn:
            self._group_service.add_members(conn, group_dn, member_dns)

    def group_remove_members(self, group_dn: str, member_dns: list[str]) -> None:
        from .infrastructure.connections import _ldap

        with _ldap() as conn:
            self._group_service.remove_members(conn, group_dn, member_dns)

    def group_replace_members(self, group_dn: str, exact_member_dns: list[str]) -> None:
        from .infrastructure.connections import _ldap

        with _ldap() as conn:
            self._group_service.replace_members(conn, group_dn, exact_member_dns)
