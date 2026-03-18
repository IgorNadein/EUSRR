"""Django signals для автоматической синхронизации Employee с LDAP."""

import logging

from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver
from django.utils import timezone

from employees.ldap.directory_service import DirectoryService, DirectoryUserDTO
from employees.ldap.errors import (
    DirectoryDbError,
    DirectoryLdapError,
    DirectoryServiceError,
)
from employees.models import LdapSyncState

logger = logging.getLogger(__name__)


def _is_ldap_enabled():
    """Проверяет, включена ли интеграция с LDAP."""
    return getattr(settings, "LDAP_ENABLED", False)


@receiver(post_save, sender='employees.Employee')
def sync_employee_to_ldap_on_save(sender, instance, created, **kwargs):
    """Синхронизирует сотрудника с LDAP при создании/обновлении.

    Срабатывает после Employee.save(). Использует временные атрибуты
    _ldap_password, _ldap_avatar, _ldap_changes для передачи данных из ViewSet.
    """
    if not _is_ldap_enabled():
        return

    if not instance.is_ldap_managed:
        return

    # Игнорируем вспомогательные сохранения (например, set_unusable_password)
    if getattr(instance, '_skip_ldap_sync', False):
        return

    try:
        svc = DirectoryService()

        if created:
            # Создание в LDAP
            password = getattr(instance, '_ldap_password', None)
            avatar_file = getattr(instance, '_ldap_avatar', None)
            avatar_bytes = None

            if avatar_file and hasattr(avatar_file, 'read'):
                try:
                    if hasattr(avatar_file, 'seek'):
                        avatar_file.seek(0)
                    avatar_bytes = avatar_file.read()
                except Exception:
                    pass

            dto = DirectoryUserDTO(
                username=instance.username or None,
                first_name=instance.first_name,
                last_name=instance.last_name,
                email=instance.email,
                phone_e164=str(instance.phone_number) if instance.phone_number else '',
                department_dn=None,  # Пока не передаем
                group_cns=[],
                initial_password=password or 'ChangeMe123!',  # Fallback пароль
                avatar_bytes=avatar_bytes,
                is_active=instance.is_active,
            )

            # Создаём пользователя в LDAP
            emp = svc.create_user(dto)

            # Получаем DN из sync state
            sync_state = LdapSyncState.objects.filter(
                model='employee',
                object_pk=str(emp.pk)
            ).first()

            if sync_state and sync_state.ldap_dn:
                # Записываем employeeNumber
                try:
                    from employees.ldap.orm_models import LdapUser
                    ldap_user = LdapUser.objects.get(dn=sync_state.ldap_dn)
                    ldap_user.employee_number = str(emp.pk)
                    ldap_user.save()
                except Exception as e:
                    logger.warning(f"Failed to set employeeNumber: {e}")

                # Назначаем должность если есть
                if instance.position_id:
                    try:
                        svc.assign_position(instance, instance.position)
                    except Exception as e:
                        logger.warning(f"Failed to assign position in LDAP: {e}")

        else:
            # Обновление в LDAP
            changes = getattr(instance, '_ldap_changes', {})
            if not changes:
                # Если изменений нет - это вспомогательное save(), пропускаем
                return

            avatar_file = getattr(instance, '_ldap_avatar', None)
            if avatar_file and hasattr(avatar_file, 'read'):
                try:
                    if hasattr(avatar_file, 'seek'):
                        avatar_file.seek(0)
                    changes['avatar_bytes'] = avatar_file.read()
                except Exception:
                    pass

            # Минимальный набор изменений для LDAP
            ldap_changes = {}
            for field in ['first_name', 'last_name', 'email', 'phone_number', 'is_active', 'password']:
                if field in changes:
                    ldap_changes[field] = changes[field]

            if 'avatar_bytes' in changes:
                ldap_changes['avatar_bytes'] = changes['avatar_bytes']

            if ldap_changes:
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
        # Не прерываем операцию - БД уже сохранена
    except Exception as e:
        logger.error(
            f"Unexpected error in LDAP sync for Employee {instance.id}: {e}",
            exc_info=True
        )
    finally:
        # Очищаем временные атрибуты
        if hasattr(instance, '_ldap_password'):
            delattr(instance, '_ldap_password')
        if hasattr(instance, '_ldap_avatar'):
            delattr(instance, '_ldap_avatar')
        if hasattr(instance, '_ldap_changes'):
            delattr(instance, '_ldap_changes')


@receiver(post_delete, sender='employees.Employee')
def sync_employee_to_ldap_on_delete(sender, instance, **kwargs):
    """Удаляет пользователя из LDAP при удалении Employee."""
    if not _is_ldap_enabled():
        return

    if not instance.is_ldap_managed:
        return

    try:
        svc = DirectoryService()
        svc.delete_user(instance)
        logger.info(f"Deleted Employee {instance.id} from LDAP")
    except (DirectoryLdapError, DirectoryServiceError, DirectoryDbError) as e:
        logger.error(
            f"LDAP delete failed for Employee {instance.id}: {e}",
            exc_info=True
        )
        # Не прерываем - запись из БД уже удалена
    except Exception as e:
        logger.error(
            f"Unexpected error in LDAP delete for Employee {instance.id}: {e}",
            exc_info=True
        )
