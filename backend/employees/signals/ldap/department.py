"""Django signals для автоматической синхронизации Department с LDAP.

Файл: employees/signals/ldap/department.py
"""

import logging

from django.conf import settings
from django.db.models.signals import post_delete, post_save, m2m_changed
from django.dispatch import receiver
from django.utils import timezone

from employees.ldap import DepartmentService
from employees.ldap.domain.dtos import DirectoryDepartmentDTO
from employees.ldap.errors import DirectoryDbError, DirectoryLdapError, DirectoryServiceError
from employees.models import LdapSyncState
from employees.signals.ldap._queue import _enqueue

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
        svc = DepartmentService()

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
                _enqueue("department_save", "department", instance.pk, {
                    "object_pk": str(instance.pk),
                    "created": True,
                })
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
                    _enqueue("department_save", "department", instance.pk, {
                        "object_pk": str(instance.pk),
                        "created": False,
                        "changes": changes,
                    })

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
        svc = DepartmentService()
        svc.delete_department(instance)
        logger.info(f"Deleted Department {instance.id} from LDAP")
    except (DirectoryLdapError, DirectoryServiceError, DirectoryDbError) as e:
        logger.error(
            f"LDAP OU delete failed for Department {instance.id}: {e}",
            exc_info=True
        )
        _enqueue("department_delete", "department", instance.pk, {
            "object_pk": str(instance.pk),
        })
    except Exception as e:
        logger.error(
            f"Unexpected error in LDAP delete for Department {instance.id}: {e}",
            exc_info=True
        )


@receiver(post_save, sender='employees.EmployeeDepartment')
def sync_department_member_to_ldap(sender, instance, created, **kwargs):
    """Синхронизирует добавление/изменение члена отдела с LDAP.
    
    is_active=True  → перемещаем в OU отдела + добавляем в группу
    is_active=False → перемещаем в Users/Dismissed OU + убираем из группы
    """
    if not _is_ldap_enabled():
        return

    if getattr(instance, '_skip_ldap_sync', False):
        return

    try:
        from employees.ldap.infrastructure.connections import _ldap
        from employees.ldap.repositories.ldap_repository import ensure_container_exists
        from employees.ldap.services.department_service import DepartmentService
        from employees.ldap.services.group_service import GroupService
        from employees.ldap.services.user_service import UserService
        from employees.ldap.utils.dn_utils import _move_to_department
        from employees.ldap.utils.ldap_utils import get_base_dn_for_employee
        from employees.ldap.services.constants import SyncDirection

        group_service = GroupService()
        user_service = UserService(group_service)
        dept_service = DepartmentService(group_service, user_service)

        employee = instance.employee
        department = instance.department

        # Получаем DN сотрудника
        try:
            emp_dn = user_service._get_employee_dn(employee)
        except Exception:
            logger.debug(
                f"Employee {employee.id} has no LDAP DN, skipping member sync"
            )
            return

        if instance.is_active:
            # === Активация: перемещаем в OU отдела + добавляем в группу ===
            try:
                dept_dn = dept_service._get_department_dn(department)
            except Exception:
                dept_dn = None

            with _ldap() as conn:
                ensured_dn = dept_service._ensure_department_ou(conn, department.name)
                if not dept_dn or dept_dn != ensured_dn:
                    dept_service._touch_state(
                        model="department",
                        object_pk=department.pk,
                        ldap_dn=ensured_dn,
                        last_django_modify_ts=timezone.now(),
                        sync_dir=SyncDirection.AUTO,
                    )
                dept_dn = ensured_dn

                # Перемещаем пользователя в OU отдела
                new_dn = _move_to_department(conn, emp_dn, dept_dn)
                if new_dn != emp_dn:
                    dept_service._touch_state(
                        model="employee",
                        object_pk=employee.pk,
                        ldap_dn=new_dn,
                        sync_dir=SyncDirection.LDAP,
                    )

                # Добавляем в группу отдела
                group_dn = dept_service._ensure_department_group(conn, department, dept_dn)
                if group_dn:
                    group_service.add_members(group_dn, [new_dn])

            # Устанавливаем роль если есть
            if instance.role:
                dept_service.set_member_role(department, employee, instance.role)
        else:
            # === Деактивация: убираем из группы + перемещаем в Users/Dismissed OU ===
            with _ldap() as conn:
                # Убираем из группы отдела
                grp_dn = (department.ldap_group_dn or "").strip()
                if grp_dn:
                    try:
                        group_service.remove_members(grp_dn, [emp_dn])
                    except Exception as grp_err:
                        logger.warning(
                            f"Failed to remove {employee.id} "
                            f"from group {grp_dn}: {grp_err}"
                        )

                # Определяем целевой OU
                target_base = get_base_dn_for_employee(employee)

                # Проверяем: уже в целевом OU?
                parts = emp_dn.split(",", 1)
                already_there = (
                    len(parts) == 2
                    and parts[1].lower() == target_base.lower()
                )
                if not already_there:
                    ensure_container_exists(conn, target_base)
                    new_dn = user_service._move_user_to_base(
                        conn, emp_dn, target_base
                    )
                    dept_service._touch_state(
                        model="employee",
                        object_pk=employee.pk,
                        ldap_dn=new_dn,
                        sync_dir=SyncDirection.LDAP,
                    )
                    logger.info(
                        f"Moved employee {employee.id} "
                        f"from {emp_dn} to {new_dn}"
                    )

    except Exception as e:
        logger.error(
            f"LDAP member sync failed for EmployeeDepartment {instance.id}: {e}",
            exc_info=True
        )
        _enqueue("department_member", "employee_department", instance.pk, {
            "employee_pk": str(instance.employee_id),
            "department_pk": str(instance.department_id),
            "is_active": instance.is_active,
            "role": str(instance.role) if instance.role else None,
        })
