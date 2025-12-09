"""
Сигналы для модуля закупок.
Автоматическая отправка уведомлений при изменении статусов.
"""

from django.db.models.signals import post_save
from django.dispatch import receiver

from notifications.services import NotificationService

from .constants import ApprovalStatus, ProcurementStatus
from .models import Approval, ProcurementRequest


@receiver(post_save, sender=ProcurementRequest)
def notify_on_request_status_change(sender, instance, created, **kwargs):
    """Отправить уведомление при изменении статуса заявки."""
    if created:
        # Новая заявка создана
        if instance.department.head:
            NotificationService.create_notification(
                recipient=instance.department.head,
                notification_type_code='procurement_new_request',
                title="Новая заявка на закупку",
                message=(
                    f'Создана заявка "{instance.title}" '
                    f'на сумму {instance.estimated_cost}₽'
                ),
                action_url=f'/procurement/requests/{instance.id}/',
                send_immediately=True,
            )
        return

    # Проверяем изменение статуса
    if hasattr(instance, '_original_status'):
        old_status = instance._original_status
        new_status = instance.status

        if old_status == new_status:
            return

        # Статус изменился
        if new_status == ProcurementStatus.PENDING:
            # Заявка отправлена на согласование
            notify_approvers(instance)

        elif new_status == ProcurementStatus.APPROVED:
            # Заявка одобрена
            notify_requestor(
                instance,
                'procurement_approved',
                "Заявка одобрена",
                f'Ваша заявка "{instance.title}" была одобрена. '
                f'Можно приступать к закупке.'
            )

        elif new_status == ProcurementStatus.REJECTED:
            # Заявка отклонена
            notify_requestor(
                instance,
                'procurement_rejected',
                "Заявка отклонена",
                f'Ваша заявка "{instance.title}" была отклонена. '
                f'Проверьте комментарии согласующих.'
            )

        elif new_status == ProcurementStatus.COMPLETED:
            # Заявка завершена
            notify_requestor(
                instance,
                'procurement_completed',
                "Заявка завершена",
                f'Закупка по заявке "{instance.title}" завершена.'
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
            # Согласование одобрено
            notify_requestor(
                instance.request,
                'procurement_stage_approved',
                "Этап согласования пройден",
                f'{instance.approver.get_full_name()} одобрил '
                f'заявку "{instance.request.title}".'
            )

        elif new_status == ApprovalStatus.REJECTED:
            # Согласование отклонено
            notify_requestor(
                instance.request,
                'procurement_rejected',
                "Заявка отклонена",
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
    NotificationService.create_notification(
        recipient=approval.approver,
        notification_type_code='procurement_pending_approval',
        title="Требуется согласование",
        message=(
            f'Заявка "{approval.request.title}" '
            f'ожидает вашего согласования. '
            f'Сумма: {approval.request.estimated_cost}₽'
        ),
        action_url=f'/procurement/requests/{approval.request.id}/',
        send_immediately=True,
    )


def notify_requestor(request, notification_type_code, title, message):
    """Уведомить создателя заявки."""
    NotificationService.create_notification(
        recipient=request.requestor,
        notification_type_code=notification_type_code,
        title=title,
        message=message,
        action_url=f'/procurement/requests/{request.id}/',
        send_immediately=True,
    )


# Сохраняем исходный статус перед сохранением
@receiver(post_save, sender=ProcurementRequest)
def save_original_status(sender, instance, **kwargs):
    """Сохранить оригинальный статус для отслеживания изменений."""
    if instance.pk:
        original = ProcurementRequest.objects.filter(
            pk=instance.pk
        ).first()
        if original:
            instance._original_status = original.status


@receiver(post_save, sender=Approval)
def save_original_approval_status(sender, instance, **kwargs):
    """Сохранить оригинальный статус согласования."""
    if instance.pk:
        original = Approval.objects.filter(pk=instance.pk).first()
        if original:
            instance._original_approval_status = original.status
