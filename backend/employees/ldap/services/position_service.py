"""
Сервис для работы с должностями (Position) в Active Directory.

Обрабатывает создание, обновление, удаление POS-групп
(агрегаторных групп должностей), управление участниками
(сотрудники с должностью), вложение POS-групп в целевые группы.

Рефакторенная версия с улучшениями:
- Наследуется от BaseService (логирование, _touch_state)
- Использует константы вместо магических строк
- Логирует все критические операции
"""

from typing import Set

from django.conf import settings
from ldap3 import BASE, SUBTREE, Connection

from employees.models import Employee, Position, LdapSyncState

from ..errors import DirectoryServiceError
from ..repositories.ldap_repository import ensure_container_exists
from ..utils.text_utils import esc_filter, esc_rdn
from ..utils.ldap_utils import group_type
from .base_service import BaseService


class PositionService(BaseService):
    """
    Сервис для работы с должностями (Position) в Active Directory.

    Отвечает за:
    - Создание и управление POS-группами (CN=POS_<name>, OU=Positions)
    - Назначение/снятие должностей для сотрудников
    - Вложение POS-групп в целевые группы (из Position.groups)
    - Синхронизацию состава участников POS-группы

    Зависимости (через Dependency Injection):
        - GroupService: для операций с группами
            (add_members, remove_members, replace_members)
    - UserService: для получения DN сотрудника
    """

    def __init__(self, group_service=None, user_service=None):
        """
        Инициализация PositionService.

        Args:
            group_service: Сервис для работы с группами
            (для управления членством)
            user_service: Сервис для работы с пользователями (для получения DN)
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

    # ======================== PUBLIC API ======================== #

    def reconcile_position(self, pos: Position) -> str:
        """
        Публичный метод — открыть соединение и привести POS к консистентности.

        Приводит должность к консистентному состоянию:
        1) Создаёт/обновляет POS-группу (CN=POS_<name>)
        2) Вкладывает POS-группу в целевые группы (из pos.groups)
        3) Синхронизирует участников POS-группы (сотрудники с этой должностью)

        Args:
            pos: Должность для синхронизации

        Returns:
            DN POS-группы

        Raises:
            RuntimeError: Если LDAP_POSITIONS_BASE не настроен
            ValueError: Если имя должности пустое
        """
        self._ensure_runtime_services()
        from ..infrastructure.connections import _ldap

        with _ldap() as conn:
            return self._reconcile_position(conn, pos)

    def assign_position(self, employee: Employee, position: Position) -> None:
        """
        Добавляет сотрудника в POS-группу должности
        и убеждается, что вложения POS в целевые группы актуальны.

        Args:
            employee: Сотрудник
            position: Должность

        Raises:
            DirectoryServiceError: Если DN сотрудника не найден
            RuntimeError: Если операция LDAP не удалась
        """
        self._ensure_runtime_services()
        from ..infrastructure.connections import _ldap

        emp_dn = self._user_service._get_employee_dn(employee)
        with _ldap() as conn:
            pos_dn = self._ensure_position_group(conn, position)
            self._group_service.add_members(pos_dn, [emp_dn])
            self._log_operation(
                "assign_position",
                model="position",
                object_id=position.id,
                dn=pos_dn,
                success=True,
                extra={"employee_id": employee.id, "employee_dn": emp_dn},
            )
            # вложения можно обновлять best-effort, не обязательно каждый раз
            try:
                self._reconcile_position_nesting(conn, position)
            except Exception:
                pass

    def unassign_position(self, employee: Employee, position: Position) -> None:
        """
        Удаляет сотрудника из POS-группы должности.

        Args:
            employee: Сотрудник
            position: Должность
        """
        self._ensure_runtime_services()
        from ..infrastructure.connections import _ldap

        try:
            emp_dn = self._user_service._get_employee_dn(employee)
        except DirectoryServiceError:
            emp_dn = None
        if not emp_dn:
            return
        with _ldap() as conn:
            pos_dn = self._ensure_position_group(conn, position)
            self._group_service.remove_members(pos_dn, [emp_dn])
            self._log_operation(
                "unassign_position",
                model="position",
                object_id=position.id,
                dn=pos_dn,
                success=True,
                extra={"employee_id": employee.id, "employee_dn": emp_dn},
            )

    def delete_position_group(self, position: Position) -> None:
        """
        Best-effort: снять POS-группу из всех правовых групп и удалить её.

        Args:
            position: Должность с POS-группой для удаления
        """
        self._ensure_runtime_services()
        from ..infrastructure.connections import _ldap
        from ..orm_models import LdapGroup

        with _ldap():
            dn = (position.ldap_group_dn or "").strip()
            if not dn:
                return
            # снять вложения через ORM (groups_with_member)
            parent_groups = self._group_service.groups_with_member(dn)
            for parent_dn in parent_groups:
                self._group_service.remove_members(parent_dn, [dn])
            # удалить саму POS-группу (ORM)
            try:
                group = LdapGroup.objects.get(dn=dn)
                group.delete()
                self._log_operation(
                    "delete_position_group",
                    model="position",
                    object_id=position.id,
                    dn=dn,
                    success=True,
                )
            except LdapGroup.DoesNotExist:
                self._logger.warning(f"POS group already deleted: {dn}")

    # ======================== PRIVATE HELPERS ======================== #

    def _positions_base(self) -> str:
        """
        Получить базовый DN для контейнера должностей (OU=Positions).

        Returns:
            DN контейнера должностей из настроек LDAP_POSITIONS_BASE

        Raises:
            RuntimeError: Если LDAP_POSITIONS_BASE не настроен
        """
        base = getattr(settings, "LDAP_POSITIONS_BASE", None)
        if not base:
            raise RuntimeError("LDAP_POSITIONS_BASE is not configured")
        return base

    def _ensure_positions_base(self, conn: Connection) -> str:
        """
        Гарантировать наличие контейнера OU=Positions в AD.

        Args:
            conn: Открытое LDAP-соединение

        Returns:
            DN контейнера должностей

        Raises:
            RuntimeError: Если создание контейнера не удалось
        """
        base = self._positions_base()
        ensure_container_exists(conn, base)
        return base

    def _ensure_position_group(self, conn: Connection, pos: Position) -> str:
        """
          Гарантирует наличие агрегаторной группы должности:
          CN=POS_<name>,OU=Positions,...
        Обновляет pos.ldap_group_dn при необходимости и возвращает DN.

        Логика:
          1. Если pos.ldap_group_dn существует - проверить существование
              и актуальность CN
        2. Если нет - искать по CN=POS_<name> в OU=Positions
        3. Если не найдено - создать новую POS-группу
        4. Обновить pos.ldap_group_dn в БД при изменениях

        Args:
            conn: Открытое LDAP-соединение
            pos: Должность

        Returns:
            DN POS-группы должности

        Raises:
            ValueError: Если имя должности пустое
            RuntimeError: Если операция LDAP не удалась
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
                    Position.objects.filter(pk=pos.pk).update(
                        ldap_group_dn=new_dn
                    )
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

    def _reconcile_position_nesting(
        self, conn: Connection, position: Position
    ) -> str:
        """
        Делает так, чтобы POS-группа должности была участником
        ровно тех AD-групп,
        что привязаны к Position.groups.

        Логика:
          1. Получить список целевых групп из position.groups
              (Django Group -> DN в AD)
        2. Получить список текущих групп, где POS-группа уже состоит
        3. Добавить POS-группу в недостающие целевые группы
        4. Удалить POS-группу из лишних групп

        Args:
            conn: Открытое LDAP-соединение
            position: Должность

        Returns:
            DN POS-группы должности

        Raises:
            RuntimeError: Если операция LDAP не удалась
        """
        pos_dn = self._ensure_position_group(conn, position)

        # желаемые группы (по именам Django Group -> CN в AD)
        desired_dns: Set[str] = set()
        for g in position.groups.all():
            dn = self._group_service.find_dn(
                g.name,
                bases=[
                    getattr(settings, "LDAP_GROUPS_BASE", None)
                    or getattr(settings, "LDAP_BASE_DN", "")
                ],
            )
            if dn:
                desired_dns.add(dn)

        # текущие группы, где POS уже состоит (ORM)
        current_dns = self._group_service.groups_with_member(pos_dn)

        # добавить недостающее
        for add_dn in desired_dns - current_dns:
            self._group_service.add_members(add_dn, [pos_dn])

        # снять лишнее
        for rem_dn in current_dns - desired_dns:
            self._group_service.remove_members(rem_dn, [pos_dn])

        return pos_dn

    def _reconcile_position(self, conn: Connection, pos: Position) -> str:
        """
        Приводит к консистентности:
        1) наличие POS_* группы,
        2) вложение POS_* в группы из pos.groups,
        3) состав участников POS_* = сотрудники с этой должностью.
        Возвращает DN POS_* группы.

        Args:
            conn: Открытое LDAP-соединение
            pos: Должность для синхронизации

        Returns:
            DN POS-группы должности

        Raises:
            RuntimeError: Если операция LDAP не удалась
        """
        pos_dn = self._ensure_position_group(conn, pos)

        # 2) вложение POS_* в target-группы
        expected_container_dns: Set[str] = set()
        for g in pos.groups.all():
            dn = self._group_service.find_dn(g.name)  # ищем по CN группы
            if dn:
                expected_container_dns.add(dn)

        current_container_dns = self._group_service.groups_with_member(pos_dn)
        to_add = expected_container_dns - current_container_dns
        to_del = current_container_dns - expected_container_dns

        for dn in to_add:
            self._group_service.add_members(dn, [pos_dn])
        for dn in to_del:
            self._group_service.remove_members(dn, [pos_dn])

        # 3) участники POS_* = сотрудники с этой позицией
        emp_ids = list(
            Employee.objects.filter(
                position_id=pos.id, is_active=True
            ).values_list("id", flat=True)
        )
        dn_map = dict(
            LdapSyncState.objects.filter(
                model="employee", object_pk__in=[str(i) for i in emp_ids]
            ).values_list("object_pk", "ldap_dn")
        )
        member_dns = [dn for dn in dn_map.values() if dn]
        self._group_service.replace_members(pos_dn, member_dns)
        return pos_dn
