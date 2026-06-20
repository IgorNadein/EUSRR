"""
Celery tasks для автоматизации кадровых событий из заявок.
"""

import logging
from datetime import datetime, time

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

logger = logging.getLogger(__name__)


@shared_task(bind=True, max_retries=3)
def create_scheduled_action(self, request_id):
    """
    Создать кадровое событие для заявки по расписанию.

    Вызывается в date_from для vacation/sick_leave/day_off.

    Args:
        request_id: ID заявки
    """
    from .models import Request
    from .enums import RequestStatus
    from employees.constants import (
        ACTION_ON_DAY_OFF,
        ACTION_ON_LEAVE,
        ACTION_ON_MATERNITY,
        ACTION_ON_SICK_LEAVE,
    )
    from employees.services.request_actions import (
        build_request_action_comment,
        create_request_action,
    )

    try:
        request = Request.objects.get(id=request_id)

        # Проверяем, что заявка все еще одобрена
        if request.status != RequestStatus.APPROVED:
            logger.info(
                f"Request #{request_id} is no longer approved "
                f"(status={request.status}), skipping action creation"
            )
            return

        # Определяем тип события
        action_mapping = {
            "vacation": ACTION_ON_LEAVE,
            "sick_leave": ACTION_ON_SICK_LEAVE,
            "day_off": ACTION_ON_DAY_OFF,
            "maternity": ACTION_ON_MATERNITY,
        }

        action_type = action_mapping.get(request.type)
        if not action_type:
            logger.warning(
                f"Request #{request_id} has type '{request.type}' "
                f"which doesn't map to scheduled action"
            )
            return

        action, created = create_request_action(
            request=request,
            action_type=action_type,
            action_date=request.date_from,
            date_to=request.date_to,
            comment=build_request_action_comment(request),
            extra={
                "approved_by": (request.approver.id if request.approver else None),
                "scheduled": True,
            },
        )
        if not created:
            logger.info(f"Action already exists for Request #{request_id}, skipping")
            return

        logger.info(
            f"Created scheduled EmployeeAction #{action.id} ({action_type}) "
            f"for Request #{request_id}"
        )

        return f"Created action {action.id}"

    except Request.DoesNotExist:
        logger.error(f"Request #{request_id} not found")
        raise
    except Exception as e:
        logger.error(
            f"Failed to create scheduled action for Request #{request_id}: {e}",
            exc_info=True,
        )
        # Retry через 5 минут
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def schedule_auto_return(self, request_id):
    """
    Legacy no-op для старых очередей Celery.

    Возвраты больше не закрывают временные кадровые состояния: период
    хранится в EmployeeAction.date_to. Старые запланированные задачи должны
    спокойно завершаться и не создавать дублирующих событий.
    """
    from .models import Request

    try:
        request = Request.objects.get(id=request_id)
        logger.info(
            "Skipping legacy auto-return for Request #%s; interval ends at %s",
            request_id,
            request.date_to,
        )
        return "Auto-return disabled"

    except Request.DoesNotExist:
        logger.error(f"Request #{request_id} not found for auto-return")
        raise
    except Exception as e:
        logger.error(
            f"Failed to process legacy auto-return for Request #{request_id}: {e}",
            exc_info=True,
        )
        raise self.retry(exc=e, countdown=300)


@shared_task
def cleanup_missed_returns():
    """
    Legacy no-op: возвратные события больше не создаются автоматически.
    """
    logger.info("cleanup_missed_returns skipped: auto-return is disabled")
    return 0


@shared_task
def process_due_personnel_actions():
    """Apply account effects for dismissal actions that are due today.

    Future dismissal actions are created from approved requests immediately, but
    account and department deactivation must happen only when their effective
    date arrives. This task also repairs missed runs by processing all due
    dismissals.
    """
    from api.v1.employees.views.actions import EmployeeActionViewSet
    from employees.constants import ACTION_DISMISSED
    from employees.models import EmployeeAction

    today = timezone.localdate()
    end_of_today = timezone.make_aware(datetime.combine(today, time.max))

    dismissal_employee_ids = EmployeeAction.objects.filter(
        action=ACTION_DISMISSED,
        date__lte=end_of_today,
    ).filter(
        Q(employee__is_active=True)
        | Q(employee__departments_links__is_active=True)
        | Q(employee__role_assignments__is_active=True)
        | Q(employee__headed_departments__isnull=False)
    ).values_list("employee_id", flat=True)

    employee_ids = sorted(set(dismissal_employee_ids))
    viewset = EmployeeActionViewSet()
    processed = 0
    for employee_id in employee_ids:
        viewset._sync_employee_account_state_by_id(employee_id)
        processed += 1

    logger.info("Processed due dismissal actions for %s employees", processed)
    return processed
