"""Celery задачи для отложенной LDAP-синхронизации.

При сбое соединения с LDAP операция сохраняется в LdapSyncQueue
и повторяется через эти задачи с экспоненциальным backoff.
"""

import logging

from celery import shared_task
from django.conf import settings
from django.utils import timezone

logger = logging.getLogger(__name__)


def _require_payload_value(payload: dict, key: str):
    """Возвращает обязательное поле payload или поднимает ValueError."""
    value = payload.get(key)
    if value in (None, ""):
        raise ValueError(f"LDAP queue payload missing required field: {key}")
    return value


def _payload_changes(payload: dict) -> dict:
    """Нормализует поле changes и валидирует его тип."""
    changes = payload.get("changes") or {}
    if not isinstance(changes, dict):
        raise ValueError("LDAP queue payload field 'changes' must be a dict")
    return changes


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
            payload["object_pk"],
        )
        return

    svc = UserService()
    # Создаём легковесный объект-заглушку для delete_user
    from types import SimpleNamespace

    emp_stub = SimpleNamespace(pk=payload["object_pk"], id=payload["object_pk"])
    svc.delete_user(emp_stub)


def _execute_department_save(payload: dict) -> None:
    """Повторяет синхронизацию Department → LDAP."""
    from employees.ldap import DepartmentService
    from employees.models import Department

    object_pk = _require_payload_value(payload, "object_pk")
    dept = Department.objects.filter(pk=object_pk).first()
    if dept is None:
        logger.info(
            "Department %s no longer exists, skipping queued sync",
            object_pk,
        )
        return

    DepartmentService().sync_department_state(
        dept,
        created=bool(payload.get("created")),
        changes=_payload_changes(payload),
        sync_head=bool(payload.get("sync_head")),
    )


def _execute_department_delete(payload: dict) -> None:
    """Повторяет удаление Department OU из LDAP."""
    from employees.ldap import DepartmentService

    DepartmentService().sync_department_delete(
        object_pk=_require_payload_value(payload, "object_pk"),
        dept_dn=payload.get("dept_dn"),
    )


def _execute_department_member(payload: dict) -> None:
    """Повторяет sync члена отдела → LDAP."""
    from employees.ldap import DepartmentService
    from employees.models import Department, Employee, EmployeeDepartment

    employee_pk = _require_payload_value(payload, "employee_pk")
    department_pk = _require_payload_value(payload, "department_pk")

    emp = Employee.objects.filter(pk=employee_pk).first()
    if emp is None:
        logger.info(
            "Employee %s no longer exists, skipping queued department member sync",
            employee_pk,
        )
        return

    dept = Department.objects.filter(pk=department_pk).first()
    if dept is None:
        logger.info(
            "Department %s no longer exists, skipping queued member sync",
            department_pk,
        )
        return

    link = (
        EmployeeDepartment.objects.filter(
            employee_id=employee_pk,
            department_id=department_pk,
        )
        .select_related("role")
        .first()
    )

    is_active = bool(payload.get("is_active"))
    role_hint = payload.get("role")
    if link is not None:
        is_active = link.is_active
        role_hint = link.role or role_hint
    else:
        logger.warning(
            "EmployeeDepartment link missing for employee=%s department=%s, "
            "falling back to queued payload state",
            employee_pk,
            department_pk,
        )

    DepartmentService().sync_member_state(
        emp,
        dept,
        is_active=is_active,
        role=role_hint,
    )


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


def _execute_department_role_save(payload: dict) -> None:
    """Повторяет синхронизацию роли отдела → LDAP."""
    from employees.ldap import DepartmentService
    from employees.models import DepartmentRole

    role_pk = _require_payload_value(payload, "role_pk")
    role = DepartmentRole.objects.filter(pk=role_pk).select_related(
        "department"
    ).first()
    if role is None:
        logger.info(
            "DepartmentRole %s no longer exists, skipping queued role sync",
            role_pk,
        )
        return

    DepartmentService().sync_role_state(role)


def _execute_department_role_delete(payload: dict) -> None:
    """Повторяет удаление LDAP-следов роли отдела."""
    from employees.ldap import DepartmentService
    from employees.models import Department

    department_pk = _require_payload_value(payload, "department_pk")
    dept = Department.objects.filter(pk=department_pk).first()
    if dept is None:
        logger.info(
            "Department %s no longer exists, skipping queued role delete sync",
            department_pk,
        )
        return

    DepartmentService().sync_role_delete(
        dept,
        role_group_dn=payload.get("role_group_dn"),
    )


def _execute_role_assignment(payload: dict) -> None:
    """Повторяет синхронизацию назначения роли → LDAP."""
    from employees.ldap import DepartmentService
    from employees.models import DepartmentRole, Employee

    employee_pk = _require_payload_value(payload, "employee_pk")
    role_pk = _require_payload_value(payload, "role_pk")

    employee = Employee.objects.filter(pk=employee_pk).first()
    if employee is None:
        logger.info(
            "Employee %s no longer exists, skipping queued role assignment sync",
            employee_pk,
        )
        return

    role = DepartmentRole.objects.filter(pk=role_pk).first()
    if role is None:
        logger.info(
            "DepartmentRole %s no longer exists, skipping queued role assignment sync",
            role_pk,
        )
        return

    DepartmentService().sync_role_assignment_state(
        employee,
        role,
        is_active=bool(payload.get("is_active")),
    )


def _execute_guest_operation(payload: dict) -> None:
    """Повторяет синхронизацию гостевой LDAP-учетки."""
    from guests.tasks import execute_guest_queue_operation

    operation = payload.get("_operation") or payload.get("operation") or "guest_sync"
    execute_guest_queue_operation(operation, payload)


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
    "department_role_save": _execute_department_role_save,
    "department_role_delete": _execute_department_role_delete,
    "role_assignment": _execute_role_assignment,
    "guest_sync": _execute_guest_operation,
    "guest_disable": _execute_guest_operation,
    "guest_delete": _execute_guest_operation,
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
        LdapSyncQueue.Status.IN_PROGRESS,
    ):
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
        payload = dict(item.payload or {})
        payload.setdefault("object_pk", item.object_pk)
        executor(payload)
        item.mark_completed()
        logger.info(
            "LDAP queue item %d (%s %s:%s) completed on attempt %d",
            item.pk,
            item.operation,
            item.model_name,
            item.object_pk,
            item.attempts + 1,
        )
    except Exception as e:
        logger.error(
            "LDAP queue item %d (%s) failed [attempt %d/%d]: %s",
            item.pk,
            item.operation,
            item.attempts + 1,
            item.max_attempts,
            e,
            exc_info=True,
        )
        item.schedule_retry(str(e))


@shared_task(ignore_result=True)
def process_ldap_queue():
    """Periodic task для обработки pending-элементов очереди.

    Берет только записи, у которых наступил next_retry_at.
    """
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
