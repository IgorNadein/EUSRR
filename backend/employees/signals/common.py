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

from employees.constants import (
    ACTION_HIRED,
    ACTION_ON_DAY_OFF,
    ACTION_ON_LEAVE,
    ACTION_ON_MATERNITY,
    ACTION_ON_SICK_LEAVE,
)
from employees.models import Employee, EmployeeAction
from employees.services.request_actions import (
    build_request_action_comment,
    create_request_action,
)

logger = logging.getLogger(__name__)


# ============================================================
# Автоматизация создания кадровых событий из заявок
# ============================================================

# Немедленные события (создаются сразу при одобрении)
IMMEDIATE_ACTION_MAPPING = {
    "transfer": "transferred",  # Перевод → Переведен
    "dismissal": "dismissed",  # Увольнение → Уволен
}

# Интервальные события (создаются сразу при одобрении с датами заявки)
SCHEDULED_ACTION_MAPPING = {
    "vacation": ACTION_ON_LEAVE,  # Отпуск → В отпуске
    "sick_leave": ACTION_ON_SICK_LEAVE,  # Больничный → На больничном
    "day_off": ACTION_ON_DAY_OFF,  # Отгул → В отгуле
    "maternity": ACTION_ON_MATERNITY,  # Декрет → В декрете
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


@receiver(pre_save, sender="requests_app.Request")
def track_request_status_change(sender, instance, **kwargs):
    """Сохраняем старый статус перед обновлением для отслеживания изменений."""
    if instance.pk:
        try:
            Request = sender
            old_instance = Request.objects.get(pk=instance.pk)
            instance._old_status = old_instance.status
        except sender.DoesNotExist:
            instance._old_status = None


@receiver(post_save, sender="requests_app.Request")
def create_action_on_request_approval(sender, instance, created, **kwargs):
    """
    Автоматически создает EmployeeAction при одобрении заявок.

    Две стратегии:
    1. НЕМЕДЛЕННО (transfer, dismissal) - сразу при одобрении
    2. ИНТЕРВАЛЬНО (vacation, sick_leave, day_off) - сразу с date_to
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
    old_status = getattr(instance, "_old_status", None)
    if old_status == RequestStatus.APPROVED:
        return  # Уже была одобрена

    if instance.status != RequestStatus.APPROVED:
        return  # Не одобрение

    # === СТРАТЕГИЯ 1: Немедленное создание ===
    if instance.type in IMMEDIATE_ACTION_MAPPING:
        _create_immediate_action(instance)

    # === СТРАТЕГИЯ 2: Интервальное событие сразу после одобрения ===
    elif instance.type in SCHEDULED_ACTION_MAPPING:
        _create_interval_action(instance)

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

    try:
        action, created = create_request_action(
            request=request,
            action_type=action_type,
            action_date=request.date_from or request.decided_at or timezone.now(),
            comment=build_request_action_comment(request),
            extra={
                "approved_by": (request.approver.id if request.approver else None),
                "immediate": True,
            },
        )
        if not created:
            logger.warning(f"EmployeeAction already exists for Request #{request.id}")
            return

        # Применяем эффекты (деактивация, LDAP sync)
        _apply_action_effects(action)

        logger.info(
            f"Created immediate EmployeeAction #{action.id} ({action_type}) "
            f"from Request #{request.id}"
        )

    except Exception as e:
        logger.error(
            f"Failed to create EmployeeAction for Request #{request.id}: {e}",
            exc_info=True,
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
    eta = timezone.make_aware(datetime.combine(request.date_from, datetime.min.time()))

    try:
        task = create_scheduled_action.apply_async(args=[request.id], eta=eta)
        logger.info(
            f"Scheduled EmployeeAction creation for Request #{request.id} "
            f"at {eta} (task_id={task.id})"
        )
    except Exception as e:
        logger.error(
            f"Failed to schedule action for Request #{request.id}: {e}", exc_info=True
        )


def _create_interval_action(request):
    """Создать временное кадровое событие сразу после одобрения заявки."""
    action_type = SCHEDULED_ACTION_MAPPING.get(request.type)
    if not action_type:
        return

    try:
        action, created = create_request_action(
            request=request,
            action_type=action_type,
            action_date=request.date_from,
            date_to=request.date_to,
            comment=build_request_action_comment(request),
            extra={
                "approved_by": (request.approver.id if request.approver else None),
                "interval": True,
            },
        )
        if not created:
            logger.warning(f"EmployeeAction already exists for Request #{request.id}")
            return

        logger.info(
            f"Created interval EmployeeAction #{action.id} ({action_type}) "
            f"from Request #{request.id}"
        )

    except Exception as e:
        logger.error(
            f"Failed to create interval EmployeeAction for Request #{request.id}: {e}",
            exc_info=True,
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
            exc_info=True,
        )
