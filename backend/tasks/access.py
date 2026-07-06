from django.db.models import Q
from documents.models import Document
from employees.models import Department, EmployeeDepartment, RoleAssignment
from requests_app.enums import RequestStatus
from requests_app.models import Request as EmployeeRequest
from schedule.models import Event
from scheduling.services import user_can_view_calendar

from .models import TaskBoard


def get_user_department_ids(user) -> list[int]:
    if not user or not user.is_authenticated:
        return []

    department_ids = set(
        EmployeeDepartment.objects.filter(
            employee_id=user.id,
            is_active=True,
        ).values_list("department_id", flat=True)
    )
    department_ids.update(
        Department.objects.filter(head_id=user.id).values_list("id", flat=True)
    )
    department_ids.update(
        RoleAssignment.objects.filter(
            employee_id=user.id,
            is_active=True,
        ).values_list("role__department_id", flat=True)
    )
    return sorted(department_ids)


def task_board_access_q(user):
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return Q()

    department_ids = get_user_department_ids(user)
    q = Q(created_by=user)
    q |= Q(members=user)
    if department_ids:
        q |= Q(departments__in=department_ids)
    q |= Q(members__isnull=True, departments__isnull=True)
    return q


def user_can_access_task_board(user, board: TaskBoard | None) -> bool:
    if not user or not user.is_authenticated or board is None:
        return False
    if user.is_staff or user.is_superuser:
        return True
    if board.created_by_id == user.id:
        return True
    if board.members.filter(id=user.id).exists():
        return True
    department_ids = get_user_department_ids(user)
    if department_ids and board.departments.filter(id__in=department_ids).exists():
        return True
    return (
        not board.members.exists()
        and not board.departments.exists()
    )


def user_can_access_calendar_event(user, event: Event | None) -> bool:
    if not user or not user.is_authenticated or event is None:
        return False
    return user_can_view_calendar(user, event.calendar)


def user_can_access_document(user, document: Document | None) -> bool:
    if not user or not user.is_authenticated or document is None:
        return False
    if user.is_staff or user.is_superuser:
        return True
    if (
        user.has_perm("documents.view_document")
        or user.has_perm("documents.add_document")
        or user.has_perm("documents.change_document")
        or user.has_perm("documents.delete_document")
    ):
        return True
    if document.sent_to_all and user.is_active:
        return True
    if document.uploaded_by_id == user.id:
        return True
    if document.recipients.filter(id=user.id, is_active=True).exists():
        return True
    return document.departments.filter(
        employeedepartment__employee=user,
        employeedepartment__is_active=True,
    ).exists()


def user_can_access_employee_request(
    user,
    request_obj: EmployeeRequest | None,
) -> bool:
    if not user or not user.is_authenticated or request_obj is None:
        return False

    if request_obj.status == RequestStatus.DRAFT:
        return request_obj.employee_id == user.id

    if request_obj.employee_id == user.id:
        return True
    if request_obj.recipients.filter(id=user.id).exists():
        return True
    return request_obj.cc_users.filter(id=user.id).exists()


def user_can_access_procurement_request(user, procurement_request) -> bool:
    if not user or not user.is_authenticated or procurement_request is None:
        return False

    from procurement.constants import ProcurementStatus
    from procurement.services import ProcurementApprovalResolver

    if user.is_staff or user.is_superuser:
        return True
    if (
        user.has_perm("procurement.view_procurementrequest")
        or user.has_perm("procurement.change_procurementrequest")
        or user.has_perm("procurement.delete_procurementrequest")
        or user.has_perm("procurement.execute_procurement")
    ):
        return True
    if procurement_request.requestor_id == user.id:
        return True
    if procurement_request.executor_id == user.id:
        return True
    if procurement_request.approvals.filter(approver=user).exists():
        return True

    participant_department_ids = (
        ProcurementApprovalResolver.get_user_department_participant_ids(user)
    )
    if procurement_request.department_id in participant_department_ids:
        return True
    if procurement_request.processing_department_id in participant_department_ids:
        return True

    return (
        procurement_request.status == ProcurementStatus.APPROVED
        and procurement_request.processing_department_id is None
    )


def user_can_access_employee(user, employee) -> bool:
    return bool(user and user.is_authenticated and employee is not None)
