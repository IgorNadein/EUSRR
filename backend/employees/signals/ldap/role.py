"""LDAP signals для DepartmentRole и RoleAssignment."""

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
from employees.signals.ldap._queue import _enqueue

logger = logging.getLogger(__name__)


def _is_ldap_enabled():
    return getattr(settings, "LDAP_ENABLED", False)


@receiver(post_save, sender="employees.DepartmentRole")
def sync_department_role_to_ldap_on_save(sender, instance, created, **kwargs):
    del sender, created, kwargs

    if not _is_ldap_enabled():
        return

    if getattr(instance, "_skip_ldap_sync", False):
        return

    try:
        DepartmentService().sync_role_state(instance)
    except (DirectoryLdapError, DirectoryServiceError, DirectoryDbError) as e:
        logger.error(
            "LDAP sync failed for DepartmentRole %s: %s",
            instance.pk,
            e,
            exc_info=True,
        )
        _enqueue(
            "department_role_save",
            "department_role",
            instance.pk,
            {"role_pk": str(instance.pk)},
        )
    except Exception as e:
        logger.error(
            "Unexpected LDAP sync error for DepartmentRole %s: %s",
            instance.pk,
            e,
            exc_info=True,
        )
    finally:
        if hasattr(instance, "_skip_ldap_sync"):
            delattr(instance, "_skip_ldap_sync")


@receiver(post_delete, sender="employees.DepartmentRole")
def sync_department_role_to_ldap_on_delete(sender, instance, **kwargs):
    del sender, kwargs

    if not _is_ldap_enabled():
        return

    try:
        DepartmentService().sync_role_delete(
            instance.department,
            role_group_dn=(instance.ldap_group_dn or "").strip() or None,
        )
    except (DirectoryLdapError, DirectoryServiceError, DirectoryDbError) as e:
        logger.error(
            "LDAP delete failed for DepartmentRole %s: %s",
            instance.pk,
            e,
            exc_info=True,
        )
        _enqueue(
            "department_role_delete",
            "department_role",
            instance.pk,
            {
                "department_pk": str(instance.department_id),
                "role_group_dn": (instance.ldap_group_dn or "").strip(),
            },
        )
    except Exception as e:
        logger.error(
            "Unexpected LDAP delete error for DepartmentRole %s: %s",
            instance.pk,
            e,
            exc_info=True,
        )


@receiver(post_save, sender="employees.RoleAssignment")
def sync_role_assignment_to_ldap_on_save(sender, instance, created, **kwargs):
    del sender, created, kwargs

    if not _is_ldap_enabled():
        return

    if getattr(instance, "_skip_ldap_sync", False):
        return

    try:
        DepartmentService().sync_role_assignment_state(
            instance.employee,
            instance.role,
            is_active=instance.is_active,
        )
    except (DirectoryLdapError, DirectoryServiceError, DirectoryDbError) as e:
        logger.error(
            "LDAP sync failed for RoleAssignment %s: %s",
            instance.pk,
            e,
            exc_info=True,
        )
        _enqueue(
            "role_assignment",
            "role_assignment",
            instance.pk,
            {
                "employee_pk": str(instance.employee_id),
                "role_pk": str(instance.role_id),
                "is_active": bool(instance.is_active),
            },
        )
    except Exception as e:
        logger.error(
            "Unexpected LDAP sync error for RoleAssignment %s: %s",
            instance.pk,
            e,
            exc_info=True,
        )
    finally:
        if hasattr(instance, "_skip_ldap_sync"):
            delattr(instance, "_skip_ldap_sync")


@receiver(post_delete, sender="employees.RoleAssignment")
def sync_role_assignment_to_ldap_on_delete(sender, instance, **kwargs):
    del sender, kwargs

    if not _is_ldap_enabled():
        return

    try:
        DepartmentService().sync_role_assignment_state(
            instance.employee,
            instance.role,
            is_active=False,
        )
    except (DirectoryLdapError, DirectoryServiceError, DirectoryDbError) as e:
        logger.error(
            "LDAP delete sync failed for RoleAssignment %s: %s",
            instance.pk,
            e,
            exc_info=True,
        )
        _enqueue(
            "role_assignment",
            "role_assignment",
            instance.pk,
            {
                "employee_pk": str(instance.employee_id),
                "role_pk": str(instance.role_id),
                "is_active": False,
            },
        )
    except Exception as e:
        logger.error(
            "Unexpected LDAP delete sync error for RoleAssignment %s: %s",
            instance.pk,
            e,
            exc_info=True,
        )
