"""Celery задачи для отложенной LDAP-синхронизации.

При сбое соединения с LDAP операция сохраняется в LdapSyncQueue
и повторяется через эти задачи с экспоненциальным backoff.
"""

import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Исполнители отложенных LDAP-операций
# ---------------------------------------------------------------------------

def _execute_employee_save(payload: dict) -> None:
    """Повторяет синхронизацию Employee → LDAP."""
    from employees.ldap import UserService
    from employees.models import Employee

    emp = Employee.objects.get(pk=payload["object_pk"])
    svc = UserService()
    svc.update_user(
        emp=emp,
        changes=payload.get("changes", {}),
        group_cns=None,
        move_to_department_dn=None,
    )


def _execute_employee_delete(payload: dict) -> None:
    """Повторяет удаление Employee из LDAP."""
    from employees.ldap import UserService
    from employees.models import LdapSyncState

    sync_state = LdapSyncState.objects.filter(
        model="employee", object_pk=payload["object_pk"]
    ).first()
    if not sync_state or not sync_state.ldap_dn:
        logger.info(
            "Employee %s already removed from LDAP sync state, skipping",
            payload["object_pk"])
        return

    svc = UserService()
    # Создаём легковесный объект-заглушку для delete_user
    from types import SimpleNamespace
    emp_stub = SimpleNamespace(pk=payload["object_pk"], id=payload["object_pk"])
    svc.delete_user(emp_stub)


def _execute_department_save(payload: dict) -> None:
    """Повторяет синхронизацию Department → LDAP."""
    from employees.ldap.services.department_service import DepartmentService
    from employees.ldap.services.group_service import GroupService
    from employees.ldap.services.user_service import UserService
    from employees.models import Department

    dept = Department.objects.get(pk=payload["object_pk"])
    group_service = GroupService()
    user_service = UserService(group_service)
    dept_service = DepartmentService(group_service, user_service)

    if payload.get("created"):
        dept_service._ensure_department_ou(dept)
        if dept.description:
            dept_service._set_ou_description(dept, dept.description)
        if dept.head:
            dept_service._set_ou_managed_by(dept, dept.head)
    else:
        changes = payload.get("changes", {})
        if changes:
            svc = DepartmentService()
            svc.update_department(dept, changes)
        if dept.head_id:
            dept_service._set_ou_managed_by(dept, dept.head)


def _execute_department_delete(payload: dict) -> None:
    """Повторяет удаление Department OU из LDAP."""
    from employees.ldap import DepartmentService
    from employees.models import LdapSyncState

    sync_state = LdapSyncState.objects.filter(
        model="department", object_pk=payload["object_pk"]
    ).first()
    if not sync_state or not sync_state.ldap_dn:
        return

    from types import SimpleNamespace
    dept_stub = SimpleNamespace(pk=payload["object_pk"], id=payload["object_pk"])
    svc = DepartmentService()
    svc.delete_department(dept_stub)


def _execute_department_member(payload: dict) -> None:
    """Повторяет sync члена отдела → LDAP."""
    from employees.ldap.services.department_service import DepartmentService
    from employees.ldap.services.group_service import GroupService
    from employees.ldap.services.user_service import UserService
    from employees.models import Employee, Department

    emp = Employee.objects.get(pk=payload["employee_pk"])
    dept = Department.objects.get(pk=payload["department_pk"])

    group_service = GroupService()
    user_service = UserService(group_service)
    dept_service = DepartmentService(group_service, user_service)

    if payload.get("is_active"):
        dept_service._move_user_to_department(emp, dept)
        if payload.get("role"):
            dept_service.set_member_role(dept, emp, payload["role"])
    else:
        dept_service._move_user_to_base_ou(emp)


def _execute_group_save(payload: dict) -> None:
    """Повторяет синхронизацию Group → LDAP."""
    from django.contrib.auth.models import Group
    from employees.ldap import GroupService
    from employees.models import LdapSyncState

    group = Group.objects.get(pk=payload["object_pk"])
    svc = GroupService()

    if payload.get("created"):
        svc.create(
            cn=group.name,
            parent_dn=payload.get("parent_dn"),
            description=payload.get("description"),
            scope=payload.get("scope", "global"),
            security_enabled=payload.get("security_enabled", True),
        )
    else:
        dn = payload.get("dn")
        if not dn:
            sync_state = LdapSyncState.objects.filter(
                model="group", object_pk=str(group.pk)
            ).first()
            dn = sync_state.ldap_dn if sync_state else None
        if not dn:
            return

        if payload.get("old_name") and payload["old_name"] != group.name:
            new_dn = svc.rename(dn, group.name)
            sync_state = LdapSyncState.objects.filter(
                model="group", object_pk=str(group.pk)
            ).first()
            if sync_state:
                sync_state.ldap_dn = new_dn
                sync_state.save(update_fields=["ldap_dn"])
            dn = new_dn

        if "description" in payload:
            svc.set_description(dn, payload["description"] or None)


def _execute_group_delete(payload: dict) -> None:
    """Повторяет удаление Group из LDAP."""
    from employees.ldap import GroupService

    dn = payload.get("dn")
    if not dn:
        return
    svc = GroupService()
    svc.delete(dn)


def _execute_group_members(payload: dict) -> None:
    """Повторяет синхронизацию участников Group → LDAP."""
    from employees.ldap import GroupService

    dn = payload.get("dn")
    if not dn:
        return

    svc = GroupService()
    action = payload["action"]
    member_dns = payload.get("member_dns", [])

    if action == "add" and member_dns:
        svc.add_members(dn, member_dns)
    elif action == "remove" and member_dns:
        svc.remove_members(dn, member_dns)
    elif action == "clear":
        svc.replace_members(dn, [])


def _execute_position_save(payload: dict) -> None:
    """Повторяет синхронизацию Position → LDAP."""
    from employees.ldap import PositionService
    from employees.models import Position

    position = Position.objects.get(pk=payload["object_pk"])
    svc = PositionService()
    svc.reconcile_position(position)


def _execute_position_delete(payload: dict) -> None:
    """Повторяет удаление Position POS-группы из LDAP."""
    from employees.ldap import PositionService

    from types import SimpleNamespace
    pos_stub = SimpleNamespace(
        pk=payload["object_pk"],
        id=payload["object_pk"],
        name=payload.get("name", ""),
    )
    svc = PositionService()
    svc.delete_position_group(pos_stub)


# Реестр: operation → callable
_EXECUTORS = {
    "employee_save": _execute_employee_save,
    "employee_delete": _execute_employee_delete,
    "department_save": _execute_department_save,
    "department_delete": _execute_department_delete,
    "department_member": _execute_department_member,
    "group_save": _execute_group_save,
    "group_delete": _execute_group_delete,
    "group_members": _execute_group_members,
    "position_save": _execute_position_save,
    "position_delete": _execute_position_delete,
}


# ---------------------------------------------------------------------------
# Celery задачи
# ---------------------------------------------------------------------------

@shared_task(bind=True, max_retries=0, ignore_result=True)
def process_ldap_queue_item(self, queue_id: int):
    """Выполняет одну отложенную LDAP-операцию из очереди.

    При ошибке вызывает schedule_retry() с exponential backoff.
    Успешное выполнение отмечает запись как completed.
    """
    from employees.models import LdapSyncQueue

    if not getattr(settings, "LDAP_ENABLED", False):
        return

    try:
        item = LdapSyncQueue.objects.get(pk=queue_id)
    except LdapSyncQueue.DoesNotExist:
        logger.warning("LdapSyncQueue item %d not found", queue_id)
        return

    if item.status not in (
            LdapSyncQueue.Status.PENDING,
            LdapSyncQueue.Status.IN_PROGRESS):
        return

    executor = _EXECUTORS.get(item.operation)
    if not executor:
        logger.error("Unknown LDAP queue operation: %s", item.operation)
        item.status = LdapSyncQueue.Status.FAILED
        item.last_error = f"Unknown operation: {item.operation}"
        item.save(update_fields=["status", "last_error", "updated_at"])
        return

    item.status = LdapSyncQueue.Status.IN_PROGRESS
    item.save(update_fields=["status", "updated_at"])

    try:
        executor(item.payload)
        item.mark_completed()
        logger.info(
            "LDAP queue item %d (%s %s:%s) completed on attempt %d",
            item.pk, item.operation, item.model_name, item.object_pk, item.attempts + 1,
        )
    except Exception as e:
        logger.error(
            "LDAP queue item %d (%s) failed [attempt %d/%d]: %s",
            item.pk, item.operation, item.attempts + 1, item.max_attempts, e,
            exc_info=True,
        )
        item.schedule_retry(str(e))


@shared_task(ignore_result=True)
def process_ldap_queue():
    """Periodic task: обрабатывает все pending-элементы в очереди, у которых наступил next_retry_at."""
    from employees.models import LdapSyncQueue

    if not getattr(settings, "LDAP_ENABLED", False):
        return

    now = timezone.now()
    pending = LdapSyncQueue.objects.filter(
        status=LdapSyncQueue.Status.PENDING,
        next_retry_at__lte=now,
    ).values_list("pk", flat=True)[:100]

    for item_pk in pending:
        process_ldap_queue_item.delay(item_pk)

    # Также подхватываем новые элементы без next_retry_at
    new_items = LdapSyncQueue.objects.filter(
        status=LdapSyncQueue.Status.PENDING,
        next_retry_at__isnull=True,
    ).values_list("pk", flat=True)[:100]

    for item_pk in new_items:
        process_ldap_queue_item.delay(item_pk)

    total = len(pending) + len(new_items)
    if total:
        logger.info("Dispatched %d LDAP queue items for processing", total)
