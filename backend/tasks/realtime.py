import logging
from collections.abc import Iterable

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Q

from employees.models import Department, EmployeeDepartment, RoleAssignment

from .models import TaskBoard

logger = logging.getLogger(__name__)


def get_task_board_recipient_ids(board: TaskBoard) -> set[int]:
    if not board or not board.pk:
        return set()

    User = get_user_model()
    admin_q = Q(is_staff=True) | Q(is_superuser=True)

    if not board.members.exists() and not board.departments.exists():
        return set(
            User.objects.filter(is_active=True)
            .values_list("id", flat=True)
        )

    department_ids = list(board.departments.values_list("id", flat=True))
    recipient_ids = {board.created_by_id}
    recipient_ids.update(board.members.values_list("id", flat=True))

    if department_ids:
        recipient_ids.update(
            EmployeeDepartment.objects.filter(
                department_id__in=department_ids,
                is_active=True,
                employee__is_active=True,
            ).values_list("employee_id", flat=True)
        )
        recipient_ids.update(
            Department.objects.filter(
                id__in=department_ids,
                head__is_active=True,
            ).values_list("head_id", flat=True)
        )
        recipient_ids.update(
            RoleAssignment.objects.filter(
                role__department_id__in=department_ids,
                is_active=True,
                employee__is_active=True,
            ).values_list("employee_id", flat=True)
        )

    recipient_ids.update(
        User.objects.filter(is_active=True)
        .filter(admin_q)
        .values_list("id", flat=True)
    )

    return set(
        User.objects.filter(
            id__in={user_id for user_id in recipient_ids if user_id},
            is_active=True,
        ).values_list("id", flat=True)
    )


def send_task_board_update(
    board: TaskBoard | None,
    event: str,
    model: str,
    object_id: int | None = None,
    *,
    recipient_ids: Iterable[int] | None = None,
    board_id: int | None = None,
    extra: dict | None = None,
) -> None:
    resolved_board_id = board_id or getattr(board, "id", None)
    if not resolved_board_id:
        return

    recipients = set(
        recipient_ids
        or (
            get_task_board_recipient_ids(board)
            if board and board.pk
            else set()
        )
    )
    if not recipients:
        return

    payload = {
        "board_id": resolved_board_id,
        "event": event,
        "model": model,
        "object_id": object_id,
    }
    if extra:
        payload.update(extra)

    def _send() -> None:
        channel_layer = get_channel_layer()
        if channel_layer is None:
            return

        message = {
            "type": "task_board_update",
            "event": event,
            "data": payload,
        }
        for user_id in recipients:
            try:
                async_to_sync(channel_layer.group_send)(
                    f"user_{user_id}",
                    message,
                )
            except Exception:
                logger.exception(
                    "Failed to send task board update to user %s",
                    user_id,
                )

    transaction.on_commit(_send)
