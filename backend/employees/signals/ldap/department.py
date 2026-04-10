"""Django signals для автоматической синхронизации Department с LDAP.

Файл: employees/signals/ldap/department.py
"""

import logging

from django.conf import settings
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from employees.ldap import DepartmentService
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


def _department_changes(instance) -> dict:
    """Возвращает временный diff для Department-синхронизации."""
    raw_changes = getattr(instance, "_ldap_changes", {}) or {}
    if not isinstance(raw_changes, dict):
        return {}
    return {
        key: value
        for key, value in raw_changes.items()
        if key in {"name", "description"}
    }


@receiver(post_save, sender="employees.Department")
def sync_department_to_ldap_on_save(sender, instance, created, **kwargs):
    """Синхронизирует отдел с LDAP при создании/обновлении."""
    if not _is_ldap_enabled():
        return

    if getattr(instance, "_skip_ldap_sync", False):
        return

    changes = {} if created else _department_changes(instance)
    sync_head = bool(getattr(instance, "_ldap_sync_head", False))

    if not created and not changes and not sync_head:
        return

    try:
        DepartmentService().sync_department_state(
            instance,
            created=created,
            changes=changes,
            sync_head=sync_head,
        )
    except (DirectoryLdapError, DirectoryServiceError, DirectoryDbError) as e:
        logger.error(
            "LDAP sync failed for Department %s (created=%s): %s",
            instance.id,
            created,
            e,
            exc_info=True,
        )
        payload = {
            "object_pk": str(instance.pk),
            "created": created,
            "changes": changes,
        }
        if sync_head:
            payload["sync_head"] = True
        _enqueue(
            "department_save",
            "department",
            instance.pk,
            payload,
        )
    except Exception as e:
        logger.error(
            "Unexpected error in LDAP sync for Department %s: %s",
            instance.id,
            e,
            exc_info=True,
        )
    finally:
        if hasattr(instance, "_ldap_changes"):
            delattr(instance, "_ldap_changes")
        if hasattr(instance, "_ldap_sync_head"):
            delattr(instance, "_ldap_sync_head")
        if hasattr(instance, "_skip_ldap_sync"):
            delattr(instance, "_skip_ldap_sync")


@receiver(post_delete, sender="employees.Department")
def sync_department_to_ldap_on_delete(sender, instance, **kwargs):
    """Удаляет LDAP-следы отдела при удалении Department."""
    if not _is_ldap_enabled():
        return

    dept_dn = (
        LdapSyncState.objects.filter(
            model="department", object_pk=str(instance.pk)
        )
        .values_list("ldap_dn", flat=True)
        .first()
    )

    try:
        DepartmentService().sync_department_delete(
            object_pk=instance.pk,
            dept_dn=dept_dn,
        )
        logger.info("Deleted Department %s from LDAP", instance.id)
    except (DirectoryLdapError, DirectoryServiceError, DirectoryDbError) as e:
        logger.error(
            "LDAP delete failed for Department %s: %s",
            instance.id,
            e,
            exc_info=True,
        )
        payload = {"object_pk": str(instance.pk)}
        if dept_dn:
            payload["dept_dn"] = dept_dn
        _enqueue(
            "department_delete",
            "department",
            instance.pk,
            payload,
        )
    except Exception as e:
        logger.error(
            "Unexpected error in LDAP delete for Department %s: %s",
            instance.id,
            e,
            exc_info=True,
        )


@receiver(post_save, sender="employees.EmployeeDepartment")
def sync_department_member_to_ldap(sender, instance, created, **kwargs):
    """Синхронизирует членство сотрудника в отделе с LDAP."""
    del created, sender, kwargs

    if not _is_ldap_enabled():
        return

    if getattr(instance, "_skip_ldap_sync", False):
        return

    try:
        DepartmentService().sync_member_state(
            instance.employee,
            instance.department,
            is_active=instance.is_active,
            role=instance.role,
        )
    except Exception as e:
        logger.error(
            "LDAP member sync failed for EmployeeDepartment %s: %s",
            instance.id,
            e,
            exc_info=True,
        )
        _enqueue(
            "department_member",
            "employee_department",
            instance.pk,
            {
                "employee_pk": str(instance.employee_id),
                "department_pk": str(instance.department_id),
                "is_active": instance.is_active,
                "role": str(instance.role) if instance.role else None,
            },
        )
    finally:
        if hasattr(instance, "_skip_ldap_sync"):
            delattr(instance, "_skip_ldap_sync")
