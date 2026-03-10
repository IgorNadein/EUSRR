"""
Django сигналы для автоматической генерации уведомлений в модуле Procurement.

Обрабатывает события:
- Создание новой заявки на закупку
- Изменение статуса заявки
- Изменение статуса согласования

Все уведомления отправляются через универсальную систему notifications:
noti fy.send() → channels.py → Celery → WebSocket/Email/Push
"""

import logging
from django.db.models.signals import post_save, pre_save
from django.dispatch import receiver

from ..constants import ApprovalStatus, ProcurementStatus
from ..models import Approval, ProcurementRequest
from .handlers import (
    notify_new_request,
    notify_approvers,
    notify_request_approved,
    notify_request_rejected,
    notify_request_completed,
    notify_request_in_progress,
    notify_request_cancelled,
    notify_stage_approved,
    notify_stage_rejected,
)

logger = logging.getLogger(__name__)


@receiver(post_save, sender=ProcurementRequest)
def create_request_notifications(sender, instance, created, **kwargs):
    """
    Создает уведомления при создании или изменении заявки.
    
    Обрабатывает:
    1. Новая заявка - уведомление руководителю отдела
    2. Изменение статуса - уведомления соответствующим получателям
    """
    try:
        request = instance
        
        if created:
            # Новая заявка создана
            # WebSocket broadcast будет автоматически через notify.send()
            notify_new_request(request)
            return
        
        # Проверяем изменение статуса
        if hasattr(request, '_original_status'):
            old_status = request._original_status
            new_status = request.status
            
            if old_status == new_status:
                return
            
            # Обработка изменения статуса
            # WebSocket broadcast будет автоматически через notify.send()
            _handle_status_change(request, new_status)
    
    except Exception as e:
        logger.exception(f"[SIGNAL ERROR] create_request_notifications: {e}")


def _handle_status_change(request, new_status):
    """
    Обработать изменение статуса заявки.
    
    Args:
        request: Объект ProcurementRequest
        new_status: Новый статус
    """
    if new_status == ProcurementStatus.PENDING:
        # Заявка отправлена на согласование
        notify_approvers(request)
    
    elif new_status == ProcurementStatus.APPROVED:
        # Заявка одобрена
        notify_request_approved(request)
    
    elif new_status == ProcurementStatus.REJECTED:
        # Заявка отклонена
        notify_request_rejected(request)
    
    elif new_status == ProcurementStatus.COMPLETED:
        # Заявка завершена
        notify_request_completed(request)
    
    elif new_status == ProcurementStatus.IN_PROGRESS:
        # Заявка взята в работу
        executor = request.executor
        notify_request_in_progress(request, executor)
    
    elif new_status == ProcurementStatus.CANCELLED:
        # Заявка отменена
        notify_request_cancelled(request)


@receiver(post_save, sender=Approval)
def create_approval_notifications(sender, instance, created, **kwargs):
    """
    Создает уведомления при создании или изменении согласования.
    
    Обрабатывает:
    1. Новое согласование - уведомление согласующему
    2. Одобрение - уведомление создателю заявки
    3. Отклонение - уведомление создателю заявки
    """
    try:
        approval = instance
        
        if created:
            # Новое согласование создано
            from .handlers import notify_approver
            notify_approver(approval)
            return
        
        # Проверяем изменение статуса согласования
        if hasattr(approval, '_original_approval_status'):
            old_status = approval._original_approval_status
            new_status = approval.status
            
            if old_status == new_status:
                return
            
            # Обработка изменения статуса согласования
            if new_status == ApprovalStatus.APPROVED:
                notify_stage_approved(approval)
            
            elif new_status == ApprovalStatus.REJECTED:
                notify_stage_rejected(approval)
    
    except Exception as e:
        logger.exception(f"[SIGNAL ERROR] create_approval_notifications: {e}")


@receiver(pre_save, sender=ProcurementRequest)
def track_request_status_change(sender, instance, **kwargs):
    """
    Сохранить оригинальный статус для отслеживания изменений.
    """
    if instance.pk:
        try:
            original = ProcurementRequest.objects.get(pk=instance.pk)
            instance._original_status = original.status
        except ProcurementRequest.DoesNotExist:
            pass


@receiver(pre_save, sender=Approval)
def track_approval_status_change(sender, instance, **kwargs):
    """
    Сохранить оригинальный статус согласования для отслеживания изменений.
    """
    if instance.pk:
        try:
            original = Approval.objects.get(pk=instance.pk)
            instance._original_approval_status = original.status
        except Approval.DoesNotExist:
            pass
