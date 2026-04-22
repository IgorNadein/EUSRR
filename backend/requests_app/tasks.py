"""
Celery tasks для автоматизации кадровых событий из заявок.
"""

import logging
from datetime import date, timedelta

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

        # Планируем автовозврат на date_to + 1 день
        if request.date_to:
            schedule_auto_return.apply_async(
                args=[request_id],
                eta=timezone.make_aware(
                    timezone.datetime.combine(
                        request.date_to + timedelta(days=1),
                        timezone.datetime.min.time(),
                    )
                ),
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
    Автоматически создать событие возврата из отпуска/больничного/отгула.

    Вызывается в date_to + 1 день.

    Args:
        request_id: ID заявки
    """
    from .models import Request
    from .enums import RequestStatus
    from employees.constants import (
        ACTION_RETURNED_FROM_DAY_OFF,
        ACTION_RETURNED_FROM_LEAVE,
        ACTION_RETURNED_FROM_SICK_LEAVE,
    )
    from employees.services.request_actions import create_request_action

    try:
        request = Request.objects.get(id=request_id)

        # Проверяем, что заявка все еще одобрена
        if request.status != RequestStatus.APPROVED:
            logger.info(
                f"Request #{request_id} is no longer approved, skipping auto-return"
            )
            return

        # Определяем тип возврата
        return_mapping = {
            "vacation": ACTION_RETURNED_FROM_LEAVE,
            "sick_leave": ACTION_RETURNED_FROM_SICK_LEAVE,
            "day_off": ACTION_RETURNED_FROM_DAY_OFF,
        }

        return_action = return_mapping.get(request.type)
        if not return_action:
            logger.warning(
                f"Request #{request_id} type '{request.type}' "
                f"doesn't have return action"
            )
            return

        return_comment = (
            f"Автоматически: окончание "
            f"{request.get_type_display().lower()} "
            f"(заявка #{request.id})"
        )
        return_date = (
            request.date_to + timedelta(days=1) if request.date_to else None
        )

        action, created = create_request_action(
            request=request,
            action_type=return_action,
            action_date=return_date,
            comment=return_comment,
            extra={"auto_return": True},
        )
        if not created:
            logger.info(f"Return action already exists for Request #{request_id}")
            return

        logger.info(
            f"Created auto-return EmployeeAction #{action.id} "
            f"({return_action}) for Request #{request_id}"
        )

        return f"Created return action {action.id}"

    except Request.DoesNotExist:
        logger.error(f"Request #{request_id} not found for auto-return")
        raise
    except Exception as e:
        logger.error(
            f"Failed to create auto-return for Request #{request_id}: {e}",
            exc_info=True,
        )
        raise self.retry(exc=e, countdown=300)


@shared_task
def cleanup_missed_returns():
    """
    Periodic task: проверяет заявки, для которых date_to прошел,
    но событие возврата не создано.

    Запускается ежедневно в 00:05.
    """
    from .models import Request
    from .enums import RequestStatus
    from employees.services.request_actions import create_request_action

    logger.info("Running cleanup_missed_returns task")

    today = date.today()
    yesterday = today - timedelta(days=1)

    # Ищем одобренные заявки, которые закончились вчера или раньше
    ended_requests = Request.objects.filter(
        status=RequestStatus.APPROVED,
        type__in=["vacation", "sick_leave", "day_off"],
        date_to__lt=today,
        date_to__gte=yesterday - timedelta(days=7),  # За последнюю неделю
    )

    created_count = 0

    for req in ended_requests:
        # Определяем тип возврата
        return_action = {
            "vacation": "returned_from_leave",
            "sick_leave": "returned_from_sick_leave",
            "day_off": "returned_from_day_off",
        }.get(req.type)

        if not return_action:
            continue

        try:
            action, created = create_request_action(
                request=req,
                action_type=return_action,
                action_date=req.date_to + timedelta(days=1),
                comment=(
                    f"Автоматически восстановлено: окончание "
                    f"{req.get_type_display().lower()} (заявка #{req.id})"
                ),
                extra={"auto_return": True, "cleanup": True},
            )
            if not created:
                continue
            created_count += 1
            logger.info(
                f"Cleanup: created return action #{action.id} for Request #{req.id}"
            )
        except Exception as e:
            logger.error(f"Cleanup: failed to create return for Request #{req.id}: {e}")

    logger.info(f"cleanup_missed_returns completed: {created_count} actions created")
    return created_count
