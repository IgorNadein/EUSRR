"""Django signals для автоматической синхронизации Employee с LDAP.

Файл: employees/signals/ldap/employee.py
"""

import logging

from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from employees.ldap import UserService
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


@receiver(post_save, sender='employees.Employee')
def sync_employee_to_ldap_on_save(sender, instance, created, **kwargs):
    """Синхронизирует изменения Employee с существующим LDAP пользователем.

    ВАЖНО: Создание LDAP пользователей происходит в RegisterAPIView.
    Этот сигнал ТОЛЬКО синхронизирует изменения существующих пользователей.

    Использует временные атрибуты _ldap_changes, _ldap_avatar для передачи данных.
    """
    if not _is_ldap_enabled():
        return

    if not instance.is_ldap_managed:
        return

    # Игнорируем вспомогательные сохранения и новые записи без LDAP
    if getattr(instance, '_skip_ldap_sync', False):
        return

    # Проверяем, существует ли пользователь в LDAP
    sync_state = LdapSyncState.objects.filter(
        model='employee',
        object_pk=str(instance.pk)
    ).first()

    if not sync_state or not (sync_state.ldap_dn or sync_state.ldap_guid):
        # Пользователь не существует в LDAP - пропускаем синхронизацию
        # Создание LDAP пользователей - ответственность RegisterAPIView
        logger.debug(f"Employee {instance.id} has no LDAP sync state, skipping sync")
        return

    # Собираем данные до try-блока (avatar — file-like, конвертируем заранее)
    ldap_changes = {}
    if not created:
        changes = getattr(instance, '_ldap_changes', {})
        if not changes:
            return

        avatar_file = getattr(instance, '_ldap_avatar', None)
        if avatar_file and hasattr(avatar_file, 'read'):
            try:
                if hasattr(avatar_file, 'seek'):
                    avatar_file.seek(0)
                changes['avatar_bytes'] = avatar_file.read()
            except Exception:
                pass

        for field in [
            'first_name',
            'last_name',
            'email',
            'phone_number',
            'is_active',
                'password']:
            if field in changes:
                ldap_changes[field] = changes[field]

        if 'avatar_bytes' in changes:
            ldap_changes['avatar_bytes'] = changes['avatar_bytes']

        if not ldap_changes:
            return

    try:
        svc = UserService()

        if created:
            # Новая запись с существующим LDAP DN (импорт из LDAP)
            try:
                from employees.ldap.orm_models import LdapUser
                ldap_user = LdapUser.objects.get(dn=sync_state.ldap_dn)
                ldap_user.employee_number = str(instance.pk)
                ldap_user.save()
            except Exception as e:
                logger.warning(f"Failed to set employeeNumber: {e}")
        else:
            svc.update_user(
                emp=instance,
                changes=ldap_changes,
                group_cns=None,
                move_to_department_dn=None,
            )

    except (DirectoryLdapError, DirectoryServiceError, DirectoryDbError) as e:
        logger.error(
            f"LDAP sync failed for Employee {instance.id} "
            f"(created={created}): {e}",
            exc_info=True
        )
        # Ставим в очередь для повторной попытки
        serializable_changes = {
            k: v for k, v in ldap_changes.items() if k != 'avatar_bytes'
        } if ldap_changes else {}
        _enqueue("employee_save", "employee", instance.pk, {
            "object_pk": str(instance.pk),
            "created": created,
            "changes": serializable_changes,
        })
    except Exception as e:
        logger.error(
            f"Unexpected error in LDAP sync for Employee {instance.id}: {e}",
            exc_info=True
        )
    finally:
        # Очищаем временные атрибуты
        if hasattr(instance, '_ldap_avatar'):
            delattr(instance, '_ldap_avatar')
        if hasattr(instance, '_ldap_changes'):
            delattr(instance, '_ldap_changes')
        if hasattr(instance, '_skip_ldap_sync'):
            delattr(instance, '_skip_ldap_sync')


@receiver(post_delete, sender='employees.Employee')
def sync_employee_to_ldap_on_delete(sender, instance, **kwargs):
    """Удаляет пользователя из LDAP при удалении Employee."""
    if not _is_ldap_enabled():
        return

    if not instance.is_ldap_managed:
        return

    try:
        svc = UserService()
        svc.delete_user(instance)
        logger.info(f"Deleted Employee {instance.id} from LDAP")
    except (DirectoryLdapError, DirectoryServiceError, DirectoryDbError) as e:
        logger.error(
            f"LDAP delete failed for Employee {instance.id}: {e}",
            exc_info=True
        )
        _enqueue("employee_delete", "employee", instance.pk, {
            "object_pk": str(instance.pk),
        })
    except Exception as e:
        logger.error(
            f"Unexpected error in LDAP delete for Employee {instance.id}: {e}",
            exc_info=True
        )
