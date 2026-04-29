"""
Celery tasks для автоматизации кадровых событий из заявок.
"""

import logging

from celery import shared_task
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
