"""Django signals для автоматической синхронизации Group с LDAP.

Файл: employees/signals/ldap/group.py
"""

import logging

from django.conf import settings
from django.contrib.auth.models import Group
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from employees.ldap import GroupService
from employees.ldap.errors import (
    DirectoryDbError,
    DirectoryLdapError,
    DirectoryServiceError,
)
from employees.models import LdapSyncState
from employees.signals.ldap._queue import _enqueue

logger = logging.getLogger(__name__)


def _is_ldap_enabled():
    """Проверяет, включена ли интеграция с LDAP."""
    return getattr(settings, "LDAP_ENABLED", False)


def _resolve_group_dn(group: Group) -> str | None:
    """Возвращает DN группы из LdapSyncState."""
    sync_state = LdapSyncState.objects.filter(
        model="group", object_pk=str(group.pk)
    ).first()
    if not sync_state or not sync_state.ldap_dn:
        return None
    return sync_state.ldap_dn


@receiver(post_save, sender=Group)
def sync_group_to_ldap_on_save(sender, instance, created, **kwargs):
    """Синхронизирует изменения Group с LDAP.

    При создании: создает LdapGroup
    При обновлении: синхронизирует имя и описание

    Использует временные атрибуты для передачи LDAP-специфичных данных:
    - _ldap_parent_dn: родительский DN для новой группы
    - _ldap_description: описание группы
    - _ldap_scope: scope ('global', 'universal', 'domainlocal')
    - _ldap_security_enabled: security enabled флаг
    """
    if not _is_ldap_enabled():
        return

    if getattr(instance, "_skip_ldap_sync", False):
        return

    try:
        svc = GroupService()

        if created:
            # Создание новой LDAP группы
            parent_dn = getattr(instance, "_ldap_parent_dn", None) or getattr(
                settings, "LDAP_GROUPS_BASE", None
            )
            description = getattr(instance, "_ldap_description", None)
            scope = getattr(instance, "_ldap_scope", "global")
            security_enabled = getattr(instance, "_ldap_security_enabled", True)

            try:
                svc.create(
                    cn=instance.name,
                    parent_dn=parent_dn,
                    description=description,
                    scope=scope,
                    security_enabled=security_enabled,
                )
                logger.info(f"Created LDAP group: {instance.name}")
            except Exception as e:
                logger.error(
                    f"Failed to create LDAP group {instance.name}: {e}",
                    exc_info=True,
                )
                _enqueue(
                    "group_save",
                    "group",
                    instance.pk,
                    {
                        "object_pk": str(instance.pk),
                        "created": True,
                        "parent_dn": parent_dn,
                        "description": description,
                        "scope": scope,
                        "security_enabled": security_enabled,
                    },
                )
        else:
            # Обновление существующей группы
            dn = _resolve_group_dn(instance)
            if not dn:
                logger.debug(
                    f"Group {instance.id} has no LDAP DN, skipping sync"
                )
                return

            # Проверяем, было ли переименование
            old_name = getattr(instance, "_ldap_old_name", None)
            if old_name and old_name != instance.name:
                try:
                    new_dn = svc.rename(dn, instance.name)
                    # Обновляем DN в LdapSyncState
                    sync_state = LdapSyncState.objects.filter(
                        model="group", object_pk=str(instance.pk)
                    ).first()
                    if sync_state:
                        sync_state.ldap_dn = new_dn
                        sync_state.save(update_fields=["ldap_dn"])
                    dn = new_dn
                    logger.info(
                        f"Renamed LDAP group from {old_name} to {instance.name}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to rename LDAP group {old_name}: {e}",
                        exc_info=True,
                    )
                    _enqueue(
                        "group_save",
                        "group",
                        instance.pk,
                        {
                            "object_pk": str(instance.pk),
                            "created": False,
                            "old_name": old_name,
                            "dn": dn,
                        },
                    )

            # Проверяем, было ли изменение описания
            new_description = getattr(
                instance, "_ldap_description", "__NO_CHANGE__"
            )
            if new_description != "__NO_CHANGE__":
                try:
                    svc.set_description(dn, new_description or None)
                    logger.info(
                        f"Updated description for LDAP group {instance.name}"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to set description for LDAP group {
                            instance.name
                        }: {e}",
                        exc_info=True,
                    )
                    _enqueue(
                        "group_save",
                        "group",
                        instance.pk,
                        {
                            "object_pk": str(instance.pk),
                            "created": False,
                            "description": new_description,
                            "dn": dn,
                        },
                    )

    except (DirectoryLdapError, DirectoryServiceError, DirectoryDbError) as e:
        logger.error(
            f"LDAP sync failed for Group {instance.id} (created={created}): {
                e
            }",
            exc_info=True,
        )
    except Exception as e:
        logger.error(
            f"Unexpected error in LDAP sync for Group {instance.id}: {e}",
            exc_info=True,
        )
    finally:
        # Очищаем временные атрибуты
        for attr in [
            "_skip_ldap_sync",
            "_ldap_parent_dn",
            "_ldap_description",
            "_ldap_scope",
            "_ldap_security_enabled",
            "_ldap_old_name",
        ]:
            if hasattr(instance, attr):
                delattr(instance, attr)


@receiver(post_delete, sender=Group)
def sync_group_to_ldap_on_delete(sender, instance, **kwargs):
    """Удаляет LDAP группу при удалении Group."""
    if not _is_ldap_enabled():
        return

    try:
        dn = _resolve_group_dn(instance)
        if not dn:
            logger.debug(f"Group {instance.id} has no LDAP DN, skipping delete")
            return

        svc = GroupService()
        svc.delete(dn)
        logger.info(f"Deleted LDAP group: {instance.name}")
    except (DirectoryLdapError, DirectoryServiceError, DirectoryDbError) as e:
        logger.error(
            f"LDAP delete failed for Group {instance.id}: {e}", exc_info=True
        )
        _enqueue(
            "group_delete",
            "group",
            instance.pk,
            {
                "dn": dn,
            },
        )
    except Exception as e:
        logger.error(
            f"Unexpected error in LDAP delete for Group {instance.id}: {e}",
            exc_info=True,
        )


@receiver(m2m_changed, sender=Group.user_set.through)
def sync_group_members_to_ldap(sender, instance, action, pk_set, **kwargs):
    """Синхронизирует изменения участников группы с LDAP.

    Реагирует на post_add, post_remove, post_clear
    для синхронизации member в LdapGroup.
    """
    if not _is_ldap_enabled():
        return

    if action not in ["post_add", "post_remove", "post_clear"]:
        return

    if getattr(instance, "_skip_ldap_sync", False):
        return

    try:
        dn = _resolve_group_dn(instance)
        if not dn:
            logger.debug(
                f"Group {instance.id} has no LDAP DN, skipping member sync"
            )
            return

        svc = GroupService()

        if action == "post_add" and pk_set:
            # Добавление участников
            from employees.models import Employee

            users = Employee.objects.filter(pk__in=pk_set, is_ldap_managed=True)
            if not users:
                return

            member_dns = []
            for user in users:
                sync_state = LdapSyncState.objects.filter(
                    model="employee", object_pk=str(user.pk)
                ).first()
                if sync_state and sync_state.ldap_dn:
                    member_dns.append(sync_state.ldap_dn)

            if member_dns:
                try:
                    svc.add_members(dn, member_dns)
                    logger.info(
                        f"Added {len(member_dns)} members to LDAP group {
                            instance.name
                        }"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to add members to LDAP group {instance.name}: {
                            e
                        }",
                        exc_info=True,
                    )
                    _enqueue(
                        "group_members",
                        "group",
                        instance.pk,
                        {
                            "dn": dn,
                            "action": "add",
                            "member_dns": member_dns,
                        },
                    )

        elif action == "post_remove" and pk_set:
            # Удаление участников
            from employees.models import Employee

            users = Employee.objects.filter(pk__in=pk_set, is_ldap_managed=True)
            if not users:
                return

            member_dns = []
            for user in users:
                sync_state = LdapSyncState.objects.filter(
                    model="employee", object_pk=str(user.pk)
                ).first()
                if sync_state and sync_state.ldap_dn:
                    member_dns.append(sync_state.ldap_dn)

            if member_dns:
                try:
                    svc.remove_members(dn, member_dns)
                    logger.info(
                        f"Removed {len(member_dns)} members from LDAP group {
                            instance.name
                        }"
                    )
                except Exception as e:
                    logger.error(
                        f"Failed to remove members from LDAP group {
                            instance.name
                        }: {e}",
                        exc_info=True,
                    )
                    _enqueue(
                        "group_members",
                        "group",
                        instance.pk,
                        {
                            "dn": dn,
                            "action": "remove",
                            "member_dns": member_dns,
                        },
                    )

        elif action == "post_clear":
            # Очистка всех участников
            try:
                svc.replace_members(dn, [])
                logger.info(
                    f"Cleared all members from LDAP group {instance.name}"
                )
            except Exception as e:
                logger.error(
                    f"Failed to clear members from LDAP group {instance.name}: {
                        e
                    }",
                    exc_info=True,
                )
                _enqueue(
                    "group_members",
                    "group",
                    instance.pk,
                    {
                        "dn": dn,
                        "action": "clear",
                        "member_dns": [],
                    },
                )

    except (DirectoryLdapError, DirectoryServiceError, DirectoryDbError) as e:
        logger.error(
            f"LDAP member sync failed for Group {instance.id}: {e}",
            exc_info=True,
        )
    except Exception as e:
        logger.error(
            f"Unexpected error in LDAP member sync for Group {instance.id}: {
                e
            }",
            exc_info=True,
        )
