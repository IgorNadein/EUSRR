# employees/signals/common.py
"""Общие Django signals для приложения employees.

Обработчики:
- Создание кадровых событий (EmployeeAction)
- Автоматизация из заявок (requests_app)
"""

import logging
from datetime import datetime

from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver
from django.utils import timezone

from employees.constants import ACTION_HIRED
from employees.models import Employee, EmployeeAction

logger = logging.getLogger(__name__)


# ============================================================
# Автоматизация создания кадровых событий из заявок
# ============================================================

# Немедленные события (создаются сразу при одобрении)
IMMEDIATE_ACTION_MAPPING = {
    "transfer": "transferred",      # Перевод → Переведен
    "dismissal": "dismissed",        # Увольнение → Уволен
}

# Отложенные события (создаются по Celery в date_from)
SCHEDULED_ACTION_MAPPING = {
    "vacation": "on_leave",          # Отпуск → В отпуске
    "sick_leave": "on_sick_leave",   # Больничный → На больничном
}


@receiver(post_save, sender=Employee)
def create_hired_action(sender, instance: Employee, created, **kwargs):
    """
    При первом сохранении нового сотрудника создаём событие «Принят».
    """
    if created:
        EmployeeAction.objects.create(
            employee=instance,
            action=ACTION_HIRED,
            date=instance.created_at or timezone.now(),
            comment="Автоматически: принят при регистрации",
        )


# ============================================================
# Обработчики заявок (requests_app)
# ============================================================

@receiver(pre_save, sender='requests_app.Request')
def track_request_status_change(sender, instance, **kwargs):
    """Сохраняем старый статус перед обновлением для отслеживания изменений."""
    if instance.pk:
        try:
            Request = sender
            old_instance = Request.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except sender.DoesNotExist:
            instance._old_status = None


@receiver(post_save, sender='requests_app.Request')
def create_action_on_request_approval(sender, instance, created, **kwargs):
    """
    Автоматически создает EmployeeAction при одобрении заявок.

    Две стратегии:
    1. НЕМЕДЛЕННО (transfer, dismissal) - сразу при одобрении
    2. ОТЛОЖЕННО (vacation, sick_leave) - через Celery в date_from
    """
    # Пропускаем если это новая заявка
    if created:
        return

    # Получаем enum из requests_app
    try:
        from requests_app.enums import RequestStatus
    except ImportError:
        logger.error("Cannot import RequestStatus from requests_app")
        return

    # Проверяем изменение статуса
    old_status = getattr(instance, '_old_status', None)
    if old_status == RequestStatus.APPROVED:
        return  # Уже была одобрена

    if instance.status != RequestStatus.APPROVED:
        return  # Не одобрение

    # === СТРАТЕГИЯ 1: Немедленное создание ===
    if instance.type in IMMEDIATE_ACTION_MAPPING:
        _create_immediate_action(instance)

    # === СТРАТЕГИЯ 2: Отложенное создание через Celery ===
    elif instance.type in SCHEDULED_ACTION_MAPPING:
        _schedule_delayed_action(instance)

    else:
        logger.debug(
            f"Request #{instance.id} approved but type '{instance.type}' "
            f"doesn't create EmployeeAction"
        )


def _create_immediate_action(request):
    """Создать событие немедленно (для увольнения, перевода)."""
    action_type = IMMEDIATE_ACTION_MAPPING.get(request.type)
    if not action_type:
        return

    # Проверяем дубли
    if EmployeeAction.objects.filter(
        extra__request_id=request.id,
        action=action_type
    ).exists():
        logger.warning(
            f"EmployeeAction already exists for Request #{request.id}"
        )
        return

    # Создаем событие
    action_date = request.date_from or request.decided_at or timezone.now()
    action_comment = f"Заявление #{request.id}"
    if request.comment:
        action_comment += f": {request.comment[:200]}"

    try:
        action = EmployeeAction.objects.create(
            employee=request.employee,
            action=action_type,
            date=action_date,
            comment=action_comment,
            extra={
                'request_id': request.id,
                'approved_by': (
                    request.approver.id if request.approver else None
                ),
                'immediate': True
            }
        )

        # Применяем эффекты (деактивация, LDAP sync)
        _apply_action_effects(action)

        logger.info(
            f"Created immediate EmployeeAction #{action.id} ({action_type}) "
            f"from Request #{request.id}"
        )

    except Exception as e:
        logger.error(
            f"Failed to create EmployeeAction for Request #{request.id}: {e}",
            exc_info=True
        )


def _schedule_delayed_action(request):
    """Запланировать создание события через Celery."""
    try:
        from requests_app.tasks import create_scheduled_action
    except ImportError:
        logger.error("Cannot import create_scheduled_action task")
        return

    if not request.date_from:
        logger.warning(
            f"Request #{request.id} type '{request.type}' needs date_from "
            f"for scheduling"
        )
        return

    # Если date_from уже прошла или сегодня - создаем сразу
    today = timezone.now().date()
    if request.date_from <= today:
        logger.info(
            f"Request #{request.id} date_from is today or past, "
            f"creating action immediately"
        )
        # Вызываем task синхронно
        create_scheduled_action.apply(args=[request.id])
        return

    # Иначе планируем на date_from в 00:00
    eta = timezone.make_aware(
        datetime.combine(request.date_from, datetime.min.time())
    )

    try:
        task = create_scheduled_action.apply_async(
            args=[request.id],
            eta=eta
        )
        logger.info(
            f"Scheduled EmployeeAction creation for Request #{request.id} "
            f"at {eta} (task_id={task.id})"
        )
    except Exception as e:
        logger.error(
            f"Failed to schedule action for Request #{request.id}: {e}",
            exc_info=True
        )


def _apply_action_effects(action):
    """Применяет эффекты кадрового события (как в EmployeeActionViewSet)."""
    try:
        from api.v1.employees.views.actions import EmployeeActionViewSet
        viewset = EmployeeActionViewSet()
        viewset._apply_effects(action)
    except Exception as e:
        logger.error(
            f"Failed to apply effects for EmployeeAction #{action.id}: {e}",
            exc_info=True
        )
