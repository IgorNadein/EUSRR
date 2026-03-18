"""Сервис для управления группами Active Directory.

Этот модуль содержит бизнес-логику для операций с группами AD,
включая создание, удаление, переименование и управление членством.
"""

from __future__ import annotations

import time
from typing import Any, Dict, List, Optional, Set

from django.conf import settings
from django.contrib.auth.models import Group
from django.core.cache import cache
from django.utils import timezone
from employees.models import LdapSyncState
from ldap3 import BASE, MODIFY_ADD, MODIFY_DELETE, MODIFY_REPLACE, SUBTREE, Connection

from ..infrastructure.connections import _ldap
from ..orm_models import LdapGroup
from ..repositories.ldap_repository import ldap_modify_or_ignore
from ..utils.text_utils import esc_filter, esc_rdn
from ..utils.ldap_utils import get_guid_str, group_type


class GroupService:
    """Сервис для управления группами Active Directory."""

    def __init__(self, directory_service=None):
        """Инициализирует GroupService.
        
        Args:
            directory_service: Опциональная ссылка на DirectoryService для _touch_state
        """
        self._directory_service = directory_service

    def _touch_state(
        self,
        *,
        model: str,
        object_pk: int | str,
        ldap_dn: Optional[str] = None,
        ldap_guid: Optional[str] = None,
        last_django_modify_ts: Optional[Any] = None,
        sync_dir: Optional[str] = None,
    ) -> None:
        """Обновляет запись LdapSyncState для модели.
        
        Делегирует в DirectoryService, если доступен, иначе работает напрямую.
        """
        if self._directory_service:
            self._directory_service._touch_state(
                model=model,
                object_pk=object_pk,
                ldap_dn=ldap_dn,
                ldap_guid=ldap_guid,
                last_django_modify_ts=last_django_modify_ts,
                sync_dir=sync_dir,
            )
        else:
            # Fallback - прямая работа с LdapSyncState
            state, created = LdapSyncState.objects.get_or_create(
                model=model, object_pk=str(object_pk)
            )
            if ldap_dn is not None:
                state.ldap_dn = ldap_dn
            if ldap_guid is not None:
                state.ldap_guid = ldap_guid
            if last_django_modify_ts is not None:
                state.last_django_modify_ts = last_django_modify_ts
            if sync_dir is not None:
                state.sync_dir = sync_dir
            state.save()

    # ======================== Core CRUD Operations ======================== #

    def create(
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

        TODO(ldap-orm): conn.add() + groupType — ldap3 навсегда.
        LdapGroup не имеет поля groupType, нужно добавить в модель.

        Args:
            conn: Подключение LDAP.
            cn: Имя группы (CN).
            parent_dn: Контейнер для группы; если None — settings.LDAP_GROUPS_BASE.
            description: Описание.
            scope: 'global' | 'domain_local' | 'universal'.
            security_enabled: Флаг безопасности.

        Returns:
            DN созданной (или существующей) группы.

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

    def delete(self, conn: Connection, group_dn: str) -> None:
        """Удаляет группу по DN (игнорирует noSuchObject)."""
        ok = conn.delete(group_dn)
        if not ok and (conn.result or {}).get("description") not in {"noSuchObject"}:
            raise RuntimeError(f"LDAP delete group failed: {conn.result}")

    def rename(self, conn: Connection, group_dn: str, new_cn: str) -> str:
        """Переименовывает группу (modify_dn).
        
        TODO(ldap-orm): modify_dn — ldap3 навсегда.
        django-ldapdb не поддерживает переименование.
        """
        new_rdn = f"CN={esc_rdn(new_cn)}"
        ok = conn.modify_dn(group_dn, new_rdn)
        if not ok:
            raise RuntimeError(f"LDAP rename group failed: {conn.result}")
        base = ",".join(group_dn.split(",")[1:])
        return f"{new_rdn},{base}"

    def set_description(
        self, conn: Connection, group_dn: str, description: Optional[str]
    ) -> None:
        """Ставит/очищает description."""
        changes = (
            {"description": [(MODIFY_REPLACE, [description])]}
            if description
            else {"description": [(MODIFY_DELETE, [])]}
        )
        ldap_modify_or_ignore(conn, group_dn, changes, {"noSuchAttribute"})

    # ======================== Member Management ======================== #

    def _modify_members(
        self, conn: Connection, group_dn: str, op: int, members: List[str]
    ) -> None:
        """Применяет операцию к членству группы (DRY-хелпер).

        Args:
            conn: Подключение LDAP.
            group_dn: DN группы.
            op: MODIFY_ADD | MODIFY_DELETE | MODIFY_REPLACE.
            members: Список DN участников.

        Raises:
            RuntimeError: При ошибке modify вне допустимых кейсов.
        """
        if not members and op in (MODIFY_ADD, MODIFY_DELETE):
            return
        ignore = (
            {"typeOrValueExists", "entryAlreadyExists"}
            if op == MODIFY_ADD
            else (
                {"noSuchAttribute", "noSuchObject"}
                if op == MODIFY_DELETE
                else {"noSuchAttribute"}
            )
        )
        ldap_modify_or_ignore(conn, group_dn, {"member": [(op, members or [])]}, ignore)

    def add_members(
        self, conn: Connection, group_dn: str, member_dns: List[str]
    ) -> None:
        """Добавляет участников (member ADD)."""
        self._modify_members(conn, group_dn, MODIFY_ADD, member_dns)

    def remove_members(
        self, conn: Connection, group_dn: str, member_dns: List[str]
    ) -> None:
        """Удаляет участников (member DELETE)."""
        self._modify_members(conn, group_dn, MODIFY_DELETE, member_dns)

    def replace_members(
        self, conn: Connection, group_dn: str, exact_member_dns: List[str]
    ) -> None:
        """Полная замена состава группы."""
        self._modify_members(conn, group_dn, MODIFY_REPLACE, exact_member_dns)

    def list_members(self, conn: Connection, group_dn: str) -> List[str]:
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

    # ======================== Finding and Search ======================== #

    def find_dn(
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

    def groups_with_member(self, conn: Connection, member_dn: str) -> Set[str]:
        """Находит все группы, в которых состоит указанный DN.
        
        Args:
            conn: Подключение LDAP.
            member_dn: DN участника.
            
        Returns:
            Множество DN групп.
        """
        base = getattr(settings, "LDAP_GROUPS_BASE", None) or getattr(
            settings, "LDAP_BASE_DN", None
        )
        if not base:
            return set()
        
        ok = conn.search(
            search_base=base,
            search_filter=f"(&(objectClass=group)(member={esc_filter(member_dn)}))",
            search_scope=SUBTREE,
            attributes=["distinguishedName"],
        )
        if not ok:
            return set()
        return {str(e.entry_dn) for e in conn.entries}

    # ======================== Catalog Synchronization ======================== #

    def sync_catalog(
        self, *, throttle_seconds: int = 60, delete_absent: bool = False
    ) -> int:
        """
        Тянет группы из AD под LDAP_GROUPS_BASE и гарантирует их наличие в Django Group.

        TODO(ldap-orm): paged search — ldap3 навсегда.
        Массовый импорт с throttling и кешированием.
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
                    search_filter="(objectClass=group)",
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
                    # фиксируем DN/GUID в sync-state
                    self._touch_state(
                        model="group",
                        object_pk=g.pk,
                        ldap_dn=dn,
                        ldap_guid=guid,
                        sync_dir="ldap",
                        last_django_modify_ts=timezone.now(),
                    )

                if delete_absent:
                    # по умолчанию НЕ удаляем отсутствующие в AD
                    for key, g in list(existing.items()):
                        if key not in ad_index:
                            # например, можно только пометить/залогировать
                            pass

                cache.set("ad_groups_sync_last_ts", now, timeout=24 * 3600)
                return created
        finally:
            cache.delete("ad_groups_sync_lock")

    # ======================== Public API with Connection Management ======================== #

    def find_dn_wrapped(
        self, cn: str, bases: Optional[list[str]] = None
    ) -> Optional[str]:
        """Ищет DN группы по CN (ORM)."""
        try:
            group = LdapGroup.objects.get(cn=cn)
            return group.dn
        except LdapGroup.DoesNotExist:
            return None

    def create_wrapped(
        self,
        *,
        cn: str,
        parent_dn: Optional[str] = None,
        description: Optional[str] = None,
        scope: str = "global",
        security_enabled: bool = True,
    ) -> str:
        """Создает группу (ldap3 — нужен groupType).
        
        TODO(ldap-orm): conn.add() + groupType остаётся ldap3.
        """
        with _ldap() as conn:
            return self.create(
                conn,
                cn,
                parent_dn,
                description=description,
                scope=scope,
                security_enabled=security_enabled,
            )

    def delete_wrapped(self, group_dn: str) -> None:
        """Удаляет группу (ORM)."""
        try:
            group = LdapGroup.objects.get(dn=group_dn)
            group.delete()
        except LdapGroup.DoesNotExist:
            pass  # Уже удалена

    def rename_wrapped(self, group_dn: str, new_cn: str) -> str:
        """Переименовывает группу (ldap3 — modify_dn).
        
        TODO(ldap-orm): modify_dn — ldap3 навсегда.
        """
        with _ldap() as conn:
            return self.rename(conn, group_dn, new_cn)

    def set_description_wrapped(
        self, group_dn: str, description: Optional[str]
    ) -> None:
        """Устанавливает описание группы (ORM)."""
        try:
            group = LdapGroup.objects.get(dn=group_dn)
            group.description = description or ""
            group.save()
        except LdapGroup.DoesNotExist:
            pass

    def list_members_wrapped(self, group_dn: str) -> list[str]:
        """Список участников группы (ORM)."""
        try:
            group = LdapGroup.objects.get(dn=group_dn)
            return list(group.member or [])
        except LdapGroup.DoesNotExist:
            return []

    def add_members_wrapped(self, group_dn: str, member_dns: list[str]) -> None:
        """Добавляет участников (ORM)."""
        try:
            group = LdapGroup.objects.get(dn=group_dn)
        except LdapGroup.DoesNotExist:
            return
        members = list(group.member or [])
        changed = False
        for dn in member_dns:
            if dn not in members:
                members.append(dn)
                changed = True
        if changed:
            group.member = members
            group.save()

    def remove_members_wrapped(self, group_dn: str, member_dns: list[str]) -> None:
        """Удаляет участников (ORM)."""
        try:
            group = LdapGroup.objects.get(dn=group_dn)
        except LdapGroup.DoesNotExist:
            return
        members = list(group.member or [])
        changed = False
        for dn in member_dns:
            if dn in members:
                members.remove(dn)
                changed = True
        if changed:
            group.member = members
            group.save()

    def replace_members_wrapped(
        self, group_dn: str, exact_member_dns: list[str]
    ) -> None:
        """Заменяет участников (ORM)."""
        try:
            group = LdapGroup.objects.get(dn=group_dn)
        except LdapGroup.DoesNotExist:
            return
        group.member = exact_member_dns
        group.save()
