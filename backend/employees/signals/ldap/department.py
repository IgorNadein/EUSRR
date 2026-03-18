"""Django signals для автоматической синхронизации Department с LDAP.

Файл: employees/signals/ldap/department.py
"""

import logging

from django.conf import settings
from django.db.models.signals import post_delete, post_save, m2m_changed
from django.dispatch import receiver

from employees.ldap.directory_service import DirectoryService, DirectoryDepartmentDTO
from employees.ldap.errors import DirectoryDbError, DirectoryLdapError, DirectoryServiceError
from employees.models import LdapSyncState

logger = logging.getLogger(__name__)


def _is_ldap_enabled():
    """Проверяет, включена ли интеграция с LDAP."""
    return getattr(settings, "LDAP_ENABLED", False)


@receiver(post_save, sender='employees.Department')
def sync_department_to_ldap_on_save(sender, instance, created, **kwargs):
    """Синхронизирует отдел с LDAP при создании/обновлении.
    
    ВАЖНО: Создание/обновление LDAP OU происходит автоматически при сохранении Department.
    """
    if not _is_ldap_enabled():
        return

    # Игнорируем вспомогательные сохранения
    if getattr(instance, '_skip_ldap_sync', False):
        return

    try:
        svc = DirectoryService()

        if created:
            # Создание OU в LDAP
            dto = DirectoryDepartmentDTO(
                name=instance.name,
                description=instance.description or "",
                head=instance.head,
            )
            # DirectoryService.create_department создаст OU и вернет обновленный Department
            # Но мы уже в post_save, поэтому просто создаем OU
            try:
                # Проверяем, есть ли уже LDAP sync state
                sync_state = LdapSyncState.objects.filter(
                    model='department',
                    object_pk=str(instance.pk)
                ).first()
                
                if not sync_state or not sync_state.ldap_dn:
                    # Создаем OU в LDAP
                    from employees.ldap.services.department_service import DepartmentService
                    from employees.ldap.services.group_service import GroupService
                    from employees.ldap.services.user_service import UserService
                    
                    group_service = GroupService()
                    user_service = UserService(group_service)
                    dept_service = DepartmentService(group_service, user_service)
                    
                    dept_service._ensure_department_ou(instance)
                    
                    if instance.description:
                        dept_service._set_ou_description(instance, instance.description)
                    
                    if instance.head:
                        dept_service._set_ou_managed_by(instance, instance.head)
                        
            except Exception as e:
                logger.error(
                    f"LDAP OU creation failed for Department {instance.id}: {e}",
                    exc_info=True
                )
        else:
            # Обновление OU в LDAP
            # Проверяем что изменилось
            changes = {}
            
            # Проверим, есть ли изменения в name/description
            old_instance = sender.objects.filter(pk=instance.pk).first()
            if old_instance:
                if instance.name != old_instance.name:
                    changes['name'] = instance.name
                if instance.description != old_instance.description:
                    changes['description'] = instance.description
                    
            if changes or instance.head_id:
                # Есть изменения - синхронизируем
                try:
                    if changes:
                        svc.update_department(instance, changes)
                    
                    # Обновляем managedBy если изменился head
                    if instance.head_id:
                        from employees.ldap.services.department_service import DepartmentService
                        from employees.ldap.services.group_service import GroupService
                        from employees.ldap.services.user_service import UserService
                        
                        group_service = GroupService()
                        user_service = UserService(group_service)
                        dept_service = DepartmentService(group_service, user_service)
                        dept_service._set_ou_managed_by(instance, instance.head)
                        
                except Exception as e:
                    logger.error(
                        f"LDAP OU update failed for Department {instance.id}: {e}",
                        exc_info=True
                    )

    except Exception as e:
        logger.error(
            f"Unexpected error in LDAP sync for Department {instance.id}: {e}",
            exc_info=True
        )


@receiver(post_delete, sender='employees.Department')
def sync_department_to_ldap_on_delete(sender, instance, **kwargs):
    """Удаляет OU из LDAP при удалении Department."""
    if not _is_ldap_enabled():
        return

    try:
        svc = DirectoryService()
        svc.delete_department(instance)
        logger.info(f"Deleted Department {instance.id} from LDAP")
    except (DirectoryLdapError, DirectoryServiceError, DirectoryDbError) as e:
        logger.error(
            f"LDAP OU delete failed for Department {instance.id}: {e}",
            exc_info=True
        )
    except Exception as e:
        logger.error(
            f"Unexpected error in LDAP delete for Department {instance.id}: {e}",
            exc_info=True
        )


@receiver(post_save, sender='employees.EmployeeDepartment')
def sync_department_member_to_ldap(sender, instance, created, **kwargs):
    """Синхронизирует добавление/изменение члена отдела с LDAP."""
    if not _is_ldap_enabled():
        return

    if getattr(instance, '_skip_ldap_sync', False):
        return

    try:
        from employees.ldap.services.department_service import DepartmentService
        from employees.ldap.services.group_service import GroupService
        from employees.ldap.services.user_service import UserService
        
        group_service = GroupService()
        user_service = UserService(group_service)
        dept_service = DepartmentService(group_service, user_service)

        if instance.is_active:
            # Добавляем/перемещаем пользователя в OU отдела
            dept_service._move_user_to_department(instance.employee, instance.department)
            
            # Устанавливаем роль если есть
            if instance.role:
                dept_service.set_member_role(instance.department, instance.employee, instance.role)
        else:
            # Перемещаем обратно в Users OU
            dept_service._move_user_to_base_ou(instance.employee)

    except Exception as e:
        logger.error(
            f"LDAP member sync failed for EmployeeDepartment {instance.id}: {e}",
            exc_info=True
        )
