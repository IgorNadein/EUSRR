"""
Обработчики (handlers) для отправки уведомлений о заявках на закупку.

Содержит бизнес-логику формирования и отправки уведомлений
для различных событий в модуле Procurement.
"""

import logging
from notifications.signals import notify

from .config import NotificationVerbs, MessageTemplates, ActionURLs

logger = logging.getLogger(__name__)


def notify_new_request(request):
    """
    Уведомить о новой заявке на закупку.
    
    Отправляет уведомление руководителю отдела.
    
    Args:
        request: Объект ProcurementRequest
    """
    if not request.department.head:
        logger.warning(
            f"[Procurement] Нет руководителя для отдела {request.department}"
        )
        return
    
    notification_title, description = MessageTemplates.new_request(
        request.title, request.total_cost
    )
    
    notify.send(
        sender=None,
        recipient=request.department.head,
        verb=NotificationVerbs.NEW_REQUEST,
        action_object=request,
        description=description,
        action_url=ActionURLs.PROCUREMENT_LIST,
        data={
            'title': notification_title,
            'request_id': request.id,
            'total_cost': float(request.total_cost),
        },
    )
    
    logger.info(
        f"[Procurement] Отправлено уведомление о новой заявке #{request.id} "
        f"руководителю {request.department.head.username}"
    )


def notify_approvers(request):
    """
    Уведомить всех согласующих о необходимости согласования заявки.
    
    Args:
        request: Объект ProcurementRequest
    """
    from ..constants import ApprovalStatus
    
    pending_approvals = request.approvals.filter(
        status=ApprovalStatus.PENDING
    )
    
    if not pending_approvals.exists():
        logger.warning(
            f"[Procurement] Нет ожидающих согласований "
            f"для заявки #{request.id}"
        )
        return
    
    for approval in pending_approvals:
        notify_approver(approval)


def notify_approver(approval):
    """
    Уведомить конкретного согласующего о необходимости согласования.
    
    Args:
        approval: Объект Approval
    """
    notification_title, description = MessageTemplates.pending_approval(
        approval.request.title, approval.request.total_cost
    )
    
    notify.send(
        sender=None,
        recipient=approval.approver,
        verb=NotificationVerbs.PENDING_APPROVAL,
        action_object=approval.request,
        description=description,
        action_url=ActionURLs.PROCUREMENT_LIST,
        data={
            'title': notification_title,
            'request_id': approval.request.id,
            'approval_id': approval.id,
            'total_cost': float(approval.request.total_cost),
        },
    )
    
    logger.info(
        f"[Procurement] Отправлено уведомление о согласовании "
        f"заявки #{approval.request.id} для {approval.approver.username}"
    )


def notify_requestor(request, verb, title, message):
    """
    Уведомить создателя заявки.
    
    Args:
        request: Объект ProcurementRequest
        verb: Тип уведомления (из NotificationVerbs)
        title: Заголовок уведомления
        message: Текст сообщения
    """
    notify.send(
        sender=None,
        recipient=request.requestor,
        verb=verb,
        action_object=request,
        description=message,
        action_url=ActionURLs.PROCUREMENT_LIST,
        data={
            'title': title,
            'request_id': request.id,
        },
    )
    
    logger.info(
        f"[Procurement] Отправлено уведомление '{verb}' "
        f"создателю заявки #{request.id}"
    )


def notify_request_approved(request):
    """
    Уведомить о полном одобрении заявки.
    
    Args:
        request: Объект ProcurementRequest
    """
    notification_title, description = MessageTemplates.approved(request.title)
    notify_requestor(
        request,
        NotificationVerbs.APPROVED,
        notification_title,
        description
    )


def notify_request_rejected(request):
    """
    Уведомить об отклонении заявки.
    
    Args:
        request: Объект ProcurementRequest
    """
    notification_title, description = MessageTemplates.rejected(request.title)
    notify_requestor(
        request,
        NotificationVerbs.REJECTED,
        notification_title,
        description
    )


def notify_request_completed(request):
    """
    Уведомить о завершении заявки.
    
    Отправляет уведомления:
    - Создателю заявки
    - Всем одобрившим согласующим
    
    Args:
        request: Объект ProcurementRequest
    """
    from ..constants import ApprovalStatus
    
    # Уведомляем создателя
    notification_title, description = MessageTemplates.completed(request.title)
    notify_requestor(
        request,
        NotificationVerbs.COMPLETED,
        notification_title,
        description
    )
    
    # Уведомляем всех одобривших согласующих
    notification_title, description = MessageTemplates.completed_approver(
        request.title
    )
    
    for approval in request.approvals.filter(status=ApprovalStatus.APPROVED):
        notify.send(
            sender=None,
            recipient=approval.approver,
            verb=NotificationVerbs.COMPLETED,
            action_object=request,
            description=description,
            action_url=ActionURLs.PROCUREMENT_LIST,
            data={
                'title': notification_title,
                'request_id': request.id,
            },
        )


def notify_request_in_progress(request, executor):
    """
    Уведомить о взятии заявки в работу.
    
    Отправляет уведомления:
    - Создателю заявки (если он не сам взял в работу)
    - Всем одобрившим согласующим
    
    Args:
        request: Объект ProcurementRequest
        executor: Пользователь, взявший заявку в работу
    """
    from ..constants import ApprovalStatus
    
    executor_name = executor.get_full_name() if executor else 'Сотрудник'
    
    # Уведомляем создателя (если он не сам взял в работу)
    if executor and request.requestor != executor:
        notification_title, description = (
            MessageTemplates.in_progress_requestor(
                request.title, executor_name
            )
        )
        
        notify.send(
            sender=executor,
            recipient=request.requestor,
            verb=NotificationVerbs.IN_PROGRESS,
            action_object=request,
            description=description,
            action_url=ActionURLs.PROCUREMENT_LIST,
            data={
                'title': notification_title,
                'request_id': request.id,
                'executor_id': executor.id,
            },
        )
    
    # Уведомляем всех одобривших согласующих
    notification_title, description = MessageTemplates.in_progress(
        request.title, executor_name
    )
    
    for approval in request.approvals.filter(status=ApprovalStatus.APPROVED):
        notify.send(
            sender=executor,
            recipient=approval.approver,
            verb=NotificationVerbs.IN_PROGRESS,
            action_object=request,
            description=description,
            action_url=ActionURLs.PROCUREMENT_LIST,
            data={
                'title': notification_title,
                'request_id': request.id,
                'executor_id': executor.id if executor else None,
            },
        )


def notify_request_cancelled(request):
    """
    Уведомить об отмене заявки.
    
    Отправляет уведомления всем причастным согласующим.
    
    Args:
        request: Объект ProcurementRequest
    """
    reason = getattr(request, 'cancellation_reason', 'не указана')
    notification_title, description = MessageTemplates.cancelled(
        request.title, reason
    )
    
    for approval in request.approvals.all():
        notify.send(
            sender=None,
            recipient=approval.approver,
            verb=NotificationVerbs.CANCELLED,
            action_object=request,
            description=description,
            action_url=ActionURLs.PROCUREMENT_LIST,
            data={
                'title': notification_title,
                'request_id': request.id,
                'reason': reason,
            },
        )


def notify_stage_approved(approval):
    """
    Уведомить о прохождении этапа согласования.
    
    Args:
        approval: Объект Approval
    """
    approver_name = approval.approver.get_full_name()
    notification_title, description = MessageTemplates.stage_approved(
        approver_name, approval.request.title
    )
    
    notify_requestor(
        approval.request,
        NotificationVerbs.STAGE_APPROVED,
        notification_title,
        description
    )


def notify_stage_rejected(approval):
    """
    Уведомить об отклонении на этапе согласования.
    
    Args:
        approval: Объект Approval
    """
    approver_name = approval.approver.get_full_name()
    notification_title, description = MessageTemplates.rejected_by_approver(
        approver_name, approval.request.title, approval.comment
    )
    
    notify_requestor(
        approval.request,
        NotificationVerbs.REJECTED,
        notification_title,
        description
    )
