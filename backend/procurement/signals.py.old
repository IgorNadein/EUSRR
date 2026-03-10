"""
Сигналы для модуля закупок.
Автоматическая отправка уведомлений при изменении статусов.
WebSocket события для real-time обновлений.
"""

import logging

from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from notifications.signals import notify

from .constants import ApprovalStatus, ProcurementStatus
from .models import Approval, ProcurementRequest

logger = logging.getLogger(__name__)


def broadcast_request_update(request, event_type='request_updated'):
    """Отправить WebSocket событие об обновлении заявки."""
    try:
        channel_layer = get_channel_layer()
        if not channel_layer:
            return

        # Данные заявки для broadcast
        data = {
            'id': request.id,
            'title': request.title,
            'status': request.status,
            'status_display': request.get_status_display(),
            'department_id': request.department_id,
            'requestor_id': request.requestor_id,
        }

        # Отправляем всем пользователям отдела
        group_name = f'procurement_dept_{request.department_id}'
        async_to_sync(channel_layer.group_send)(
            group_name,
            {
                'type': 'procurement_update',
                'event': event_type,
                'data': data,
            }
        )

        # Отправляем создателю заявки
        async_to_sync(channel_layer.group_send)(
            f'user_{request.requestor_id}',
            {
                'type': 'procurement_update',
                'event': event_type,
                'data': data,
            }
        )

        logger.debug(
            f"[Procurement WS] Broadcast {event_type} for request {request.id}"
        )
    except Exception as e:
        logger.warning(f"[Procurement WS] Broadcast failed: {e}")


@receiver(post_save, sender=ProcurementRequest)
def notify_on_request_status_change(sender, instance, created, **kwargs):
    """Отправить уведомление при изменении статуса заявки."""
    if created:
        # Новая заявка создана - broadcast
        broadcast_request_update(instance, 'request_created')

        if instance.department.head:
            notify.send(
                sender=None,
                recipient=instance.department.head,
                verb='procurement_new_request',
                action_object=instance,
                description=(
                    f'Создана заявка "{instance.title}" '
                    f'на сумму {instance.total_cost}₽'
                ),
                action_url='/procurement',
                data={'title': 'Новая заявка на закупку'},
            )
        return

    # Проверяем изменение статуса
    if hasattr(instance, '_original_status'):
        old_status = instance._original_status
        new_status = instance.status

        if old_status == new_status:
            return

        # Broadcast обновления статуса
        broadcast_request_update(instance, 'request_status_changed')

        # Статус изменился
        if new_status == ProcurementStatus.PENDING:
            # Заявка отправлена на согласование
            notify_approvers(instance)

        elif new_status == ProcurementStatus.APPROVED:
            # Заявка одобрена
            notify_requestor(
                instance,
                'procurement_approved',
                'Заявка одобрена',
                f'Ваша заявка "{instance.title}" была одобрена. '
                f'Можно приступать к закупке.'
            )

        elif new_status == ProcurementStatus.REJECTED:
            # Заявка отклонена
            notify_requestor(
                instance,
                'procurement_rejected',
                'Заявка отклонена',
                f'Ваша заявка "{instance.title}" была отклонена. '
                f'Проверьте комментарии согласующих.'
            )

        elif new_status == ProcurementStatus.COMPLETED:
            # Уведомляем создателя заявки
            notify_requestor(
                instance,
                'procurement_completed',
                'Заявка завершена',
                f'Закупка по заявке "{instance.title}" завершена.'
            )
            # Уведомляем всех одобривших согласующих
            for approval in instance.approvals.filter(status=ApprovalStatus.APPROVED):
                notify.send(
                    sender=None,
                    recipient=approval.approver,
                    verb='procurement_completed',
                    action_object=instance,
                    description=f'Заявка "{instance.title}" успешно завершена.',
                    action_url='/procurement',
                    data={'title': 'Заявка завершена'},
                )

        elif new_status == ProcurementStatus.IN_PROGRESS:
            # Заявка взята в работу
            executor = instance.executor
            executor_name = executor.get_full_name() if executor else 'Сотрудник'

            # Уведомляем создателя заявки (если он не сам взял в работу)
            if executor and instance.requestor != executor:
                notify.send(
                    sender=executor,
                    recipient=instance.requestor,
                    verb='procurement_in_progress',
                    action_object=instance,
                    description=(
                        f'Заявка "{instance.title}" взята в работу '
                        f'пользователем {executor_name}.'
                    ),
                    action_url='/procurement',
                    data={'title': 'Ваша заявка взята в работу'},
                )

            # Уведомляем всех одобривших согласующих
            for approval in instance.approvals.filter(status=ApprovalStatus.APPROVED):
                notify.send(
                    sender=executor,
                    recipient=approval.approver,
                    verb='procurement_in_progress',
                    action_object=instance,
                    description=(
                        f'Заявка "{instance.title}" взята в работу '
                        f'пользователем {executor_name}.'
                    ),
                    action_url='/procurement',
                    data={'title': 'Заявка взята в работу'},
                )

        elif new_status == ProcurementStatus.CANCELLED:
            # Заявка отменена - уведомляем всех причастных согласующих
            reason = getattr(instance, 'cancellation_reason', 'не указана')
            for approval in instance.approvals.all():
                notify.send(
                    sender=None,
                    recipient=approval.approver,
                    verb='procurement_cancelled',
                    action_object=instance,
                    description=(
                        f'Заявка "{instance.title}" была отменена автором. '
                        f'Причина: {reason}'
                    ),
                    action_url='/procurement',
                    data={'title': 'Заявка отменена'},
                )


@receiver(post_save, sender=Approval)
def notify_on_approval_change(sender, instance, created, **kwargs):
    """Отправить уведомление при изменении согласования."""
    if created:
        # Новое согласование создано
        notify_approver(instance)
        return

    # Проверяем изменение статуса согласования
    if hasattr(instance, '_original_approval_status'):
        old_status = instance._original_approval_status
        new_status = instance.status

        if old_status == new_status:
            return

        # Статус согласования изменился
        if new_status == ApprovalStatus.APPROVED:
            notify_requestor(
                instance.request,
                'procurement_stage_approved',
                'Этап согласования пройден',
                f'{instance.approver.get_full_name()} одобрил '
                f'заявку "{instance.request.title}".'
            )

        elif new_status == ApprovalStatus.REJECTED:
            notify_requestor(
                instance.request,
                'procurement_rejected',
                'Заявка отклонена',
                f'{instance.approver.get_full_name()} отклонил '
                f'заявку "{instance.request.title}". '
                f'Причина: {instance.comment}'
            )


def notify_approvers(request):
    """Уведомить всех согласующих о новой заявке."""
    for approval in request.approvals.filter(
        status=ApprovalStatus.PENDING
    ):
        notify_approver(approval)


def notify_approver(approval):
    """Уведомить согласующего о необходимости согласования."""
    notify.send(
        sender=None,
        recipient=approval.approver,
        verb='procurement_pending_approval',
        action_object=approval.request,
        description=(
            f'Заявка "{approval.request.title}" '
            f'ожидает вашего согласования. '
            f'Сумма: {approval.request.total_cost}₽'
        ),
        action_url='/procurement',
        data={'title': 'Требуется согласование'},
    )


def notify_requestor(request, verb, title, message):
    """Уведомить создателя заявки."""
    notify.send(
        sender=None,
        recipient=request.requestor,
        verb=verb,
        action_object=request,
        description=message,
        action_url='/procurement',
        data={'title': title},
    )


# Сохраняем исходный статус перед сохранением
@receiver(pre_save, sender=ProcurementRequest)
def save_original_status(sender, instance, **kwargs):
    """Сохранить оригинальный статус для отслеживания изменений."""
    if instance.pk:
        try:
            original = ProcurementRequest.objects.get(pk=instance.pk)
            instance._original_status = original.status
        except ProcurementRequest.DoesNotExist:
            pass


@receiver(pre_save, sender=Approval)
def save_original_approval_status(sender, instance, **kwargs):
    """Сохранить оригинальный статус согласования для отслеживания изменений."""
    if instance.pk:
        try:
            original = Approval.objects.get(pk=instance.pk)
            instance._original_approval_status = original.status
        except Approval.DoesNotExist:
            pass


@receiver(pre_save, sender=Approval)
def save_original_approval_status(sender, instance, **kwargs):
    """Сохранить оригинальный статус согласования."""
    if instance.pk:
        try:
            original = Approval.objects.get(pk=instance.pk)
            instance._original_approval_status = original.status
        except Approval.DoesNotExist:
            pass
