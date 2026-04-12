"""Рефакторенный сервис для управления группами Active Directory.

Улучшения:
- Наследуется от BaseService (общая логика _touch_state, логирование)
- Использует константы из constants.py
- Унифицированный API (без дублирования _wrapped методов)
- Добавлено логирование критических операций
- Упрощённый интерфейс (сервис сам управляет LDAP соединением)
"""

from __future__ import annotations

import time
from typing import List, Optional, Set

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.utils import timezone
from ldap3 import SUBTREE, Connection

from .base_service import BaseService
from .constants import (
    LdapFilter,
    LdapAttribute,
)
from ..infrastructure.connections import _ldap
from ..orm_models import LdapGroup, LdapUser
from ..utils.text_utils import esc_rdn
from ..utils.ldap_utils import get_guid_str


class GroupService(BaseService):
    """Сервис для управления группами Active Directory.

    Рефакторенная версия с улучшенной архитектурой:
    - Использует BaseService для общей логики
    - Константы вместо магических чисел
    - Логирование всех операций
    - Упрощённый API
    """

    # ======================== Core CRUD Operations ======================== #

    def create(
        self,
        cn: str,
        *,
        parent_dn: Optional[str] = None,
        description: Optional[str] = None,
        scope: str = "global",
        security_enabled: bool = True,
    ) -> str:
        """Создаёт группу в LDAP под указанным контейнером
        (с управлением соединением).

        Args:
            cn: Имя группы (CN).
            parent_dn: Контейнер для группы;
            если None — settings.LDAP_GROUPS_BASE.
            description: Описание.
            scope: 'global' | 'domain_local' | 'universal'.
            security_enabled: Флаг безопасности.

        Returns:
            DN созданной (или существующей) группы.

        Raises:
            RuntimeError: Если базовый контейнер не задан
            или операция add завершилась ошибкой.
        """
        with _ldap() as conn:
            return self._create_internal(
                conn,
                cn,
                parent_dn=parent_dn,
                description=description,
                scope=scope,
                security_enabled=security_enabled,
            )

    def _create_internal(
        self,
        conn: Connection,
        cn: str,
        *,
        parent_dn: Optional[str] = None,
        description: Optional[str] = None,
        scope: str = "global",
        security_enabled: bool = True,
    ) -> str:
        """Внутренний метод создания группы через ORM.

        Args:
            conn: LDAP соединение
            (сохраняется в сигнатуре для обратной совместимости).
            cn: Имя группы.
            parent_dn: Контейнер.
            description: Описание.
            scope: Тип группы.
            security_enabled: Флаг безопасности.
        """
        base = parent_dn or getattr(settings, "LDAP_GROUPS_BASE", None)
        if not base:
            raise RuntimeError(
                "LDAP_GROUPS_BASE is not configured "
                "and parent_dn is not provided"
            )

        dn = f"CN={esc_rdn(cn)},{base}"

        try:
            LdapGroup.objects.create(
                dn=dn,
                cn=cn,
                sam_account_name=cn,
                description=description or "",
            )
            self._log_operation("create", model="group", dn=dn, success=True)
        except Exception as e:
            err_str = str(e).lower()
            if "already exists" in err_str or "entryalreadyexists" in err_str:
                self._logger.info(f"Group already exists: {dn}")
            else:
                self._log_operation(
                    "create",
                    model="group",
                    dn=dn,
                    success=False,
                    error=e,
                )
                raise RuntimeError(f"LDAP add group failed: {e}") from e

        return dn

    def delete(self, group_dn: str) -> None:
        """Удаляет группу по DN через ORM (игнорирует DoesNotExist)."""
        self._delete_internal(group_dn)

    def _delete_internal(self, group_dn: str) -> None:
        """Внутренний метод удаления группы через ORM."""
        try:
            ldap_group = LdapGroup.objects.get(dn=group_dn)
            ldap_group.delete()
            self._log_operation(
                "delete", model="group", dn=group_dn, success=True
            )
        except LdapGroup.DoesNotExist:
            self._logger.info(f"Group already deleted or not found: {group_dn}")

    def rename(self, group_dn: str, new_cn: str) -> str:
        """Переименовывает группу (modify_dn)."""
        with _ldap() as conn:
            return self._rename_internal(conn, group_dn, new_cn)

    def _rename_internal(
        self, conn: Connection, group_dn: str, new_cn: str
    ) -> str:
        """Внутренний метод переименования группы."""
        new_rdn = f"CN={esc_rdn(new_cn)}"
        ok = conn.modify_dn(group_dn, new_rdn)

        if not ok:
            self._log_operation(
                "rename",
                model="group",
                dn=group_dn,
                success=False,
                error=RuntimeError(f"LDAP rename group failed: {conn.result}"),
                extra={"new_cn": new_cn},
            )
            raise RuntimeError(f"LDAP rename group failed: {conn.result}")

        base = ",".join(group_dn.split(",")[1:])
        new_dn = f"{new_rdn},{base}"

        self._log_operation(
            "rename",
            model="group",
            dn=group_dn,
            success=True,
            extra={"new_dn": new_dn},
        )

        return new_dn

    def set_description(
        self, group_dn: str, description: Optional[str]
    ) -> None:
        """Устанавливает или очищает description группы (ORM)."""
        try:
            group = LdapGroup.objects.get(dn=group_dn)
            group.description = description or ""
            group.save()
            self._log_operation(
                "set_description",
                model="group",
                dn=group_dn,
                success=True,
            )
        except LdapGroup.DoesNotExist:
            self._logger.warning(
                f"Group not found for set_description: {group_dn}"
            )

    # ======================== Member Management ======================== #

    def add_members(self, group_dn: str, member_dns: List[str]) -> None:
        """Добавляет участников в группу через high-level LDAP модель."""
        if not member_dns:
            return

        try:
            group = LdapGroup.objects.get(dn=group_dn)
        except LdapGroup.DoesNotExist:
            self._logger.warning(f"Group not found: {group_dn}")
            return

        added_count = 0
        for dn in member_dns:
            before = set(group.list_members())
            group.add_member(dn)
            after = set(LdapGroup.objects.get(dn=group_dn).list_members())
            if dn in after and dn not in before:
                added_count += 1

        if added_count:
            total = len(LdapGroup.objects.get(dn=group_dn).list_members())
            self._log_operation(
                "add_members",
                model="group",
                dn=group_dn,
                success=True,
                extra={"added": added_count, "total": total},
            )

    def remove_members(self, group_dn: str, member_dns: List[str]) -> None:
        """Удаляет участников из группы через high-level LDAP модель."""
        if not member_dns:
            return

        try:
            group = LdapGroup.objects.get(dn=group_dn)
        except LdapGroup.DoesNotExist:
            self._logger.warning(f"Group not found: {group_dn}")
            return

        removed_count = 0
        for dn in member_dns:
            before = set(group.list_members())
            group.remove_member(dn)
            after = set(LdapGroup.objects.get(dn=group_dn).list_members())
            if dn not in after and dn in before:
                removed_count += 1

        if removed_count:
            total = len(LdapGroup.objects.get(dn=group_dn).list_members())
            self._log_operation(
                "remove_members",
                model="group",
                dn=group_dn,
                success=True,
                extra={"removed": removed_count, "total": total},
            )

    def replace_members(
        self, group_dn: str, exact_member_dns: List[str]
    ) -> None:
        """Полная замена состава группы через high-level LDAP модель."""
        try:
            group = LdapGroup.objects.get(dn=group_dn)
        except LdapGroup.DoesNotExist:
            self._logger.warning(f"Group not found: {group_dn}")
            return

        old_count = len(group.list_members())
        diff = group.sync_members(exact_member_dns)

        self._log_operation(
            "replace_members",
            model="group",
            dn=group_dn,
            success=True,
            extra={
                "old_count": old_count,
                "new_count": len(exact_member_dns),
                **diff,
            },
        )

    def list_members(self, group_dn: str) -> List[str]:
        """Возвращает DN всех участников группы (ORM)."""
        try:
            group = LdapGroup.objects.get(dn=group_dn)
            return list(group.member or [])
        except LdapGroup.DoesNotExist:
            return []

    # ======================== Finding and Search ======================== #

    def find_dn(
        self, cn: str, bases: Optional[List[str]] = None
    ) -> Optional[str]:
        """Ищет DN группы по CN (ORM).

        Warning: Если есть несколько групп с одинаковым CN,
        вернёт первую найденную.
        """
        group = LdapGroup.objects.filter(cn=cn).first()
        return group.dn if group else None

    def groups_with_member(self, member_dn: str) -> Set[str]:
        """Находит все группы, в которых состоит DN (ORM через memberOf)."""
        # Пробуем получить memberOf пользователя
        try:
            user = LdapUser.objects.get(dn=member_dn)
            return set(user.member_of or [])
        except LdapUser.DoesNotExist:
            pass

        # Fallback: может быть группа вложена в группу
        try:
            group = LdapGroup.objects.get(dn=member_dn)
            return set(group.member_of or [])
        except LdapGroup.DoesNotExist:
            return set()

    # ======================== Catalog Sync ======================== #

    def sync_catalog(
        self, *, throttle_seconds: int = 60, delete_absent: bool = False
    ) -> int:
        """Синхронизирует группы из AD в Django Group.

        Тянет группы из AD под LDAP_GROUPS_BASE
        и гарантирует их наличие в Django Group.
        Возвращает количество созданных групп.
        Обновляет LdapSyncState(model='group').
        Троттлит запросы к AD не чаще, чем раз в throttle_seconds.

        Args:
            throttle_seconds: Минимальный интервал между синхронизациями
            delete_absent: Удалять ли группы, отсутствующие в AD

        Returns:
            Количество созданных групп
        """
        base = getattr(settings, "LDAP_GROUPS_BASE", None) or getattr(
            settings, "LDAP_BASE_DN", None
        )
        if not base:
            return 0

        # Простая защита от шторминга
        now = int(time.time())
        last = cache.get("ad_groups_sync_last_ts") or 0
        if throttle_seconds and now - last < throttle_seconds:
            self._logger.debug("Sync throttled, skipping")
            return 0

        if not cache.add(
            "ad_groups_sync_lock", "1", timeout=throttle_seconds or 30
        ):
            self._logger.debug("Sync already in progress, skipping")
            return 0

        created = 0
        try:
            with _ldap() as conn:
                ok = conn.search(
                    search_base=base,
                    search_filter=LdapFilter.ALL_GROUPS,
                    search_scope=SUBTREE,
                    attributes=[LdapAttribute.CN, LdapAttribute.OBJECT_GUID],
                )

                if not ok:
                    return 0

                # AD → {name_lower: (CN, DN, GUID)}
                ad_index = {}
                for e in conn.entries:
                    cn = str(getattr(e, LdapAttribute.CN, "")) or ""
                    if not cn:
                        continue
                    dn = str(e.entry_dn)
                    guid = get_guid_str(
                        {
                            LdapAttribute.OBJECT_GUID: getattr(
                                e, LdapAttribute.OBJECT_GUID, None
                            )
                        }
                    )
                    ad_index[cn.lower()] = (cn, dn, guid)

                # Существующие группы в Django
                existing = {g.name.lower(): g for g in Group.objects.all()}

                for key, (cn, dn, guid) in ad_index.items():
                    g = existing.get(key)
                    if not g:
                        g = Group.objects.create(name=cn)
                        created += 1
                        existing[key] = g
                        self._logger.info(f"Created Django group: {cn}")

                    # Фиксируем DN/GUID в sync-state
                    self._touch_state(
                        model="group",
                        object_pk=g.pk,
                        ldap_dn=dn,
                        ldap_guid=guid,
                        sync_dir="ldap",
                        last_django_modify_ts=timezone.now(),
                    )

                if delete_absent:
                    for key, g in list(existing.items()):
                        if key not in ad_index:
                            self._logger.info(f"Group absent in AD: {g.name}")
                            # Можно удалить или только пометить

                cache.set("ad_groups_sync_last_ts", now, timeout=24 * 3600)
                self._logger.info(
                    f"Group catalog sync completed: {created} created"
                )
                return created
        finally:
            cache.delete("ad_groups_sync_lock")

    # ======================== Low-Level Methods
    # for Internal Use ======================== #

    def _create_with_conn(
        self,
        conn: Connection,
        cn: str,
        parent_dn: Optional[str] = None,
        description: Optional[str] = None,
        scope: str = "global",
        security_enabled: bool = True,
    ) -> str:
        """Создаёт группу с существующим соединением.

        Для внутреннего использования.

        Используется другими сервисами, которые уже управляют conn.
        """
        return self._create_internal(
            conn,
            cn,
            parent_dn=parent_dn,
            description=description,
            scope=scope,
            security_enabled=security_enabled,
        )

    def _delete_with_conn(self, conn: Connection, group_dn: str) -> None:
        """Удаляет группу.

        Для совместимости с Legacy API, conn игнорируется.
        """
        self._delete_internal(group_dn)

    def _rename_with_conn(
        self, conn: Connection, group_dn: str, new_cn: str
    ) -> str:
        """Переименовывает группу с существующим соединением."""
        return self._rename_internal(conn, group_dn, new_cn)

    def _add_members_with_conn(
        self, conn: Connection, group_dn: str, member_dns: List[str]
    ) -> None:
        """Добавляет участников с существующим соединением.

        Просто вызывает ORM.
        """
        self.add_members(group_dn, member_dns)

    def _remove_members_with_conn(
        self, conn: Connection, group_dn: str, member_dns: List[str]
    ) -> None:
        """Удаляет участников с существующим соединением.

        Просто вызывает ORM.
        """
        self.remove_members(group_dn, member_dns)

    def _replace_members_with_conn(
        self, conn: Connection, group_dn: str, exact_member_dns: List[str]
    ) -> None:
        """Заменяет участников с существующим соединением.

        Просто вызывает ORM.
        """
        self.replace_members(group_dn, exact_member_dns)

    def _find_dn_with_conn(
        self, conn: Connection, cn: str, bases: Optional[List[str]] = None
    ) -> Optional[str]:
        """Ищет DN с существующим соединением.

        Просто вызывает ORM.
        """
        return self.find_dn(cn, bases)

    def _groups_with_member_with_conn(
        self, conn: Connection, member_dn: str
    ) -> Set[str]:
        """Находит группы с участником с существующим соединением."""
        return self.groups_with_member(member_dn)


__all__ = ["GroupService"]
