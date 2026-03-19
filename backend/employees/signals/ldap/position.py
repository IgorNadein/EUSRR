"""Django signals для автоматической синхронизации Position с LDAP.

Файл: employees/signals/ldap/position.py
Отвечает за синхронизацию POS-групп должностей с Active Directory при изменении Position.groups.
"""

import logging

from django.conf import settings
from django.db.models.signals import m2m_changed, post_delete, post_save
from django.dispatch import receiver

from employees.ldap import PositionService
from employees.ldap.errors import (
    DirectoryDbError,
    DirectoryLdapError,
    DirectoryServiceError,
)
from employees.models import Position
from employees.signals.ldap._queue import _enqueue

logger = logging.getLogger(__name__)


def _is_ldap_enabled():
    """Проверяет, включена ли интеграция с LDAP."""
    return getattr(settings, "LDAP_ENABLED", False)


@receiver(post_save, sender=Position)
def sync_position_to_ldap_on_save(sender, instance, created, **kwargs):
    """Создает/обновляет POS-группу должности в LDAP при сохранении Position.
    
    При создании: создает POS-группу (CN=POS_<name>)
    При обновлении: переименовывает POS-группу при изменении имени
    
    Использует временный атрибут _skip_ldap_sync для отключения синхронизации.
    """
    if not _is_ldap_enabled():
        return

    if getattr(instance, '_skip_ldap_sync', False):
        return

    try:
        svc = PositionService()
        
        # reconcile_position гарантирует наличие POS-группы и обновляет её при необходимости
        # Также синхронизирует вложенность в целевые группы и участников
        svc.reconcile_position(instance)
        
        logger.info(
            f"Synced position '{instance.name}' to LDAP (created={created})"
        )
    except (DirectoryLdapError, DirectoryServiceError, DirectoryDbError) as e:
        logger.error(
            f"LDAP sync failed for Position {instance.id} (created={created}): {e}",
            exc_info=True
        )
        _enqueue("position_save", "position", instance.pk, {
            "object_pk": str(instance.pk),
        })
    except Exception as e:
        logger.error(
            f"Unexpected error in LDAP sync for Position {instance.id}: {e}",
            exc_info=True
        )


@receiver(post_delete, sender=Position)
def sync_position_to_ldap_on_delete(sender, instance, **kwargs):
    """Удаляет POS-группу должности из LDAP при удалении Position."""
    if not _is_ldap_enabled():
        return

    try:
        svc = PositionService()
        svc.delete_position_group(instance)
        logger.info(f"Deleted LDAP POS-group for position '{instance.name}'")
    except (DirectoryLdapError, DirectoryServiceError, DirectoryDbError) as e:
        logger.error(
            f"LDAP delete failed for Position {instance.id}: {e}",
            exc_info=True
        )
        _enqueue("position_delete", "position", instance.pk, {
            "object_pk": str(instance.pk),
            "name": instance.name,
        })
    except Exception as e:
        logger.error(
            f"Unexpected error in LDAP delete for Position {instance.id}: {e}",
            exc_info=True
        )


@receiver(m2m_changed, sender=Position.groups.through)
def sync_position_groups_to_ldap(sender, instance, action, **kwargs):
    """Синхронизирует изменения Position.groups с LDAP.
    
    При изменении групп должности (add/remove/clear/set):
    - Обновляет вложенность POS-группы в целевые AD-группы
    - POS-группа добавляется в AD-группы, соответствующие Position.groups
    - POS-группа удаляется из AD-групп, не указанных в Position.groups
    
    Реагирует на post_add, post_remove, post_clear для синхронизации вложенности.
    """
    if not _is_ldap_enabled():
        return

    if action not in ['post_add', 'post_remove', 'post_clear']:
        return

    if getattr(instance, '_skip_ldap_sync', False):
        return

    try:
        svc = PositionService()
        
        # reconcile_position обновит вложенность POS-группы в целевые AD-группы
        # на основе текущего состояния Position.groups
        svc.reconcile_position(instance)
        
        logger.info(
            f"Synced position '{instance.name}' groups to LDAP (action={action})"
        )
    except (DirectoryLdapError, DirectoryServiceError, DirectoryDbError) as e:
        logger.error(
            f"LDAP groups sync failed for Position {instance.id} (action={action}): {e}",
            exc_info=True
        )
        _enqueue("position_save", "position", instance.pk, {
            "object_pk": str(instance.pk),
        })
    except Exception as e:
        logger.error(
            f"Unexpected error in LDAP groups sync for Position {instance.id}: {e}",
            exc_info=True
        )
