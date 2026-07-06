from django.db.models import Q
from employees.models import Department, EmployeeDepartment, RoleAssignment
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
