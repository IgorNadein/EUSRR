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

    Вызывается в date_from для vacation/sick_leave.

    Args:
        request_id: ID заявки
    """
    from .models import Request
    from .enums import RequestStatus
    from employees.models import EmployeeAction

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
            'vacation': 'on_leave',
            'sick_leave': 'on_sick_leave',
        }

        action_type = action_mapping.get(request.type)
        if not action_type:
            logger.warning(
                f"Request #{request_id} has type '{request.type}' "
                f"which doesn't map to scheduled action"
            )
            return

        # Проверяем, что событие еще не создано
        if EmployeeAction.objects.filter(
            extra__request_id=request_id,
            action=action_type
        ).exists():
            logger.info(
                f"Action already exists for Request #{request_id}, skipping"
            )
            return

        # Создаем событие
        action_comment = f"Заявление #{request.id}"
        if request.comment:
            action_comment += f": {request.comment[:200]}"

        action = EmployeeAction.objects.create(
            employee=request.employee,
            action=action_type,
            date=timezone.now(),
            comment=action_comment,
            extra={
                'request_id': request.id,
                'approved_by': (
                    request.approver.id if request.approver else None
                ),
                'scheduled': True
            }
        )

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
                        timezone.datetime.min.time()
                    )
                )
            )

        return f"Created action {action.id}"

    except Request.DoesNotExist:
        logger.error(f"Request #{request_id} not found")
        raise
    except Exception as e:
        logger.error(
            f"Failed to create scheduled action for Request #{request_id}: {e}",
            exc_info=True
        )
        # Retry через 5 минут
        raise self.retry(exc=e, countdown=300)


@shared_task(bind=True, max_retries=3)
def schedule_auto_return(self, request_id):
    """
    Автоматически создать событие возврата из отпуска/больничного.

    Вызывается в date_to + 1 день.

    Args:
        request_id: ID заявки
    """
    from .models import Request
    from .enums import RequestStatus
    from employees.models import EmployeeAction

    try:
        request = Request.objects.get(id=request_id)

        # Проверяем, что заявка все еще одобрена
        if request.status != RequestStatus.APPROVED:
            logger.info(
                f"Request #{request_id} is no longer approved, "
                f"skipping auto-return"
            )
            return

        # Определяем тип возврата
        return_mapping = {
            'vacation': 'returned_from_leave',
            'sick_leave': 'returned_from_leave',
        }

        return_action = return_mapping.get(request.type)
        if not return_action:
            logger.warning(
                f"Request #{request_id} type '{request.type}' "
                f"doesn't have return action"
            )
            return

        # Проверяем, что событие возврата еще не создано
        if EmployeeAction.objects.filter(
            extra__request_id=request_id,
            action=return_action
        ).exists():
            logger.info(
                f"Return action already exists for Request #{request_id}"
            )
            return

        # Создаем событие возврата
        return_comment = (
            f"Автоматически: окончание "
            f"{request.get_type_display().lower()} "
            f"(заявка #{request.id})"
        )

        action = EmployeeAction.objects.create(
            employee=request.employee,
            action=return_action,
            date=timezone.now(),
            comment=return_comment,
            extra={
                'request_id': request.id,
                'auto_return': True
            }
        )

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
            exc_info=True
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
    from employees.models import EmployeeAction

    logger.info("Running cleanup_missed_returns task")

    today = date.today()
    yesterday = today - timedelta(days=1)

    # Ищем одобренные заявки, которые закончились вчера или раньше
    ended_requests = Request.objects.filter(
        status=RequestStatus.APPROVED,
        type__in=['vacation', 'sick_leave'],
        date_to__lt=today,
        date_to__gte=yesterday - timedelta(days=7)  # За последнюю неделю
    )

    created_count = 0

    for req in ended_requests:
        # Определяем тип возврата
        return_action = {
            'vacation': 'returned_from_leave',
            'sick_leave': 'returned_from_leave',
        }.get(req.type)

        if not return_action:
            continue

        # Проверяем, что события возврата нет
        if EmployeeAction.objects.filter(
            extra__request_id=req.id,
            action=return_action
        ).exists():
            continue

        # Создаем пропущенное событие возврата
        try:
            action = EmployeeAction.objects.create(
                employee=req.employee,
                action=return_action,
                date=req.date_to + timedelta(days=1),
                comment=(
                    f"Автоматически восстановлено: окончание "
                    f"{req.get_type_display().lower()} (заявка #{req.id})"
                ),
                extra={
                    'request_id': req.id,
                    'auto_return': True,
                    'cleanup': True
                }
            )
            created_count += 1
            logger.info(
                f"Cleanup: created return action #{action.id} "
                f"for Request #{req.id}"
            )
        except Exception as e:
            logger.error(
                f"Cleanup: failed to create return for Request #{req.id}: {e}"
            )

    logger.info(
        f"cleanup_missed_returns completed: {created_count} actions created"
    )
    return created_count
