"""
Обработчики (handlers) для отправки уведомлений о заявках на закупку.

Содержит бизнес-логику формирования и отправки уведомлений
для различных событий в модуле Procurement.
"""

import logging
from notifications.signals import notify

from .config import NotificationVerbs, MessageTemplates, ActionURLs

logger = logging.getLogger(__name__)


def _actor_id(actor):
    return getattr(actor, "id", None)


def _actor_name(actor):
    if not actor:
        return "Система"
    return actor.get_full_name() or getattr(actor, "username", "") or str(actor)


def _request_actor(request):
    return getattr(request, "_notification_actor", None)


def _send_procurement_notification(
    *,
    recipient,
    verb,
    procurement_request,
    title,
    description,
    actor=None,
    action_object=None,
    extra_data=None,
):
    """Отправить procurement-уведомление одному получателю."""
    if not recipient:
        return

    data = {
        "title": title,
        "request_id": procurement_request.id,
    }
    if actor:
        data["actor_id"] = actor.id
    if extra_data:
        data.update(extra_data)

    notify.send(
        sender=actor,
        recipient=recipient,
        verb=verb,
        action_object=action_object or procurement_request,
        target=procurement_request,
        description=description,
        action_url=ActionURLs.request_detail(procurement_request.id),
        data=data,
    )


def _notify_many(
    recipients,
    *,
    verb,
    procurement_request,
    title,
    description,
    actor=None,
    action_object=None,
    extra_data=None,
):
    """Отправить уведомление списку получателей с дедупликацией."""
    seen = set()
    actor_id = _actor_id(actor)
    for recipient in recipients:
        if not recipient or recipient.id in seen:
            continue
        seen.add(recipient.id)
        if actor_id and recipient.id == actor_id:
            continue
        _send_procurement_notification(
            recipient=recipient,
            verb=verb,
            procurement_request=procurement_request,
            title=title,
            description=description,
            actor=actor,
            action_object=action_object,
            extra_data=extra_data,
        )


def _processing_department_recipients(procurement_request):
    """Активные участники отдела-исполнителя, включая роли и руководителя."""
    if not procurement_request.processing_department_id:
        return []

    from employees.models import Employee, EmployeeDepartment, RoleAssignment

    department = procurement_request.processing_department
    recipient_ids = set(
        EmployeeDepartment.objects.filter(
            department_id=department.id,
            is_active=True,
        ).values_list("employee_id", flat=True)
    )
    recipient_ids.update(
        RoleAssignment.objects.filter(
            role__department_id=department.id,
            is_active=True,
        ).values_list("employee_id", flat=True)
    )
    if department.head_id:
        recipient_ids.add(department.head_id)

    return list(Employee.objects.filter(id__in=recipient_ids, is_active=True))


def get_current_pending_approvals(request):
    """Вернуть pending approvals только текущего этапа."""
    from ..constants import ApprovalStatus

    pending_approvals = request.approvals.filter(
        status=ApprovalStatus.PENDING
    ).order_by("priority", "created_at", "id")
    first_pending = pending_approvals.first()
    if first_pending is None:
        return pending_approvals.none()
    return pending_approvals.filter(priority=first_pending.priority)


def notify_new_request(request):
    """
    Legacy-helper для старого сценария уведомления руководителя отдела.

    Новая логика адресных заявок использует notify_processing_department_request().

    Args:
        request: Объект ProcurementRequest
    """
    if not request.department.head:
        logger.warning(
            f"[Procurement] Нет руководителя для отдела {request.department}"
        )
        return

    actor = request.requestor
    notification_title, description = MessageTemplates.new_request(
        request.title,
        request.total_cost,
        _actor_name(actor),
    )

    notify.send(
        sender=actor,
        recipient=request.department.head,
        verb=NotificationVerbs.NEW_REQUEST,
        action_object=request,
        description=description,
        action_url=ActionURLs.request_detail(request.id),
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


def notify_processing_department_request(request, actor=None):
    """Уведомить отдел-исполнитель о новой адресной заявке."""
    if not request.processing_department_id:
        return

    actor = actor or request.requestor
    department_name = request.processing_department.name
    notification_title, description = MessageTemplates.department_request(
        request.title,
        department_name,
        _actor_name(actor),
    )
    recipients = _processing_department_recipients(request)
    _notify_many(
        recipients,
        verb=NotificationVerbs.DEPARTMENT_REQUEST,
        procurement_request=request,
        title=notification_title,
        description=description,
        actor=actor,
        extra_data={
            "processing_department_id": request.processing_department_id,
            "total_cost": float(request.total_cost),
        },
    )

    logger.info(
        f"[Procurement] Отправлено уведомление о заявке #{request.id} "
        f"в отдел {department_name}"
    )


def notify_approvers(request):
    """
    Уведомить согласующих только текущего этапа.

    Args:
        request: Объект ProcurementRequest
    """
    pending_approvals = get_current_pending_approvals(request)

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

    _send_procurement_notification(
        recipient=approval.approver,
        verb=NotificationVerbs.PENDING_APPROVAL,
        procurement_request=approval.request,
        title=notification_title,
        description=description,
        extra_data={
            "approval_id": approval.id,
            "total_cost": float(approval.request.total_cost),
        },
    )

    logger.info(
        f"[Procurement] Отправлено уведомление о согласовании "
        f"заявки #{approval.request.id} для {approval.approver.username}"
    )


def notify_requestor(
    request,
    verb,
    title,
    message,
    *,
    actor=None,
    action_object=None,
    extra_data=None,
):
    """
    Уведомить создателя заявки.

    Args:
        request: Объект ProcurementRequest
        verb: Тип уведомления (из NotificationVerbs)
        title: Заголовок уведомления
        message: Текст сообщения
    """
    actor = actor or _request_actor(request)
    if actor and actor.id == request.requestor_id:
        return

    _send_procurement_notification(
        actor=actor,
        verb=verb,
        recipient=request.requestor,
        procurement_request=request,
        title=title,
        description=message,
        action_object=action_object,
        extra_data=extra_data,
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
        description,
        extra_data={
            "old_status": getattr(request, "_original_status", None),
            "new_status": request.status,
        },
    )


def notify_request_returned_to_processing(request):
    """Уведомить исполнителя или отдел, что согласованная заявка вернулась."""
    if not request.processing_department_id:
        return

    actor = _request_actor(request)
    title = "Заявка вернулась в обработку"
    description = (
        f'Заявка "{request.title}" согласована и снова доступна '
        f'для обработки.'
    )
    recipients = []
    if request.executor_id:
        recipients.append(request.executor)
    else:
        recipients.extend(_processing_department_recipients(request))

    _notify_many(
        recipients,
        verb=NotificationVerbs.APPROVED,
        procurement_request=request,
        title=title,
        description=description,
        actor=actor,
        extra_data={
            "old_status": getattr(request, "_original_status", None),
            "new_status": request.status,
            "processing_department_id": request.processing_department_id,
            "executor_id": request.executor_id,
        },
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
        description,
        extra_data={
            "old_status": getattr(request, "_original_status", None),
            "new_status": request.status,
        },
    )


def notify_request_completed(request):
    """
    Уведомить о завершении заявки.

    Отправляет уведомления:
    - Создателю заявки

    Args:
        request: Объект ProcurementRequest
    """
    notification_title, description = MessageTemplates.completed(request.title)
    actor = _request_actor(request) or request.executor
    notify_requestor(
        request,
        NotificationVerbs.COMPLETED,
        notification_title,
        description,
        actor=actor,
        extra_data={
            "old_status": getattr(request, "_original_status", None),
            "new_status": request.status,
        },
    )


def notify_request_arrival(request, actor=None):
    """Вручную уведомить заказчика о поступлении по заявке."""
    notification_title, description = MessageTemplates.arrival_notice(
        request.title,
    )
    notify_requestor(
        request,
        NotificationVerbs.ARRIVAL_NOTICE,
        notification_title,
        description,
        actor=actor,
        extra_data={
            "status": request.status,
            "fulfillment_status": request.fulfillment_status,
        },
    )


def notify_request_in_progress(request, executor):
    """
    Уведомить о взятии заявки в работу.

    Заказчика не уведомляем: это промежуточный статус обработки.
    Финальные статусы и комментарии остаются основными сигналами.

    Args:
        request: Объект ProcurementRequest
        executor: Пользователь, взявший заявку в работу
    """
    return


def notify_executor_reassigned(request, previous_executor, actor):
    """Уведомить прежнего исполнителя о перехвате адресной заявки."""
    if not previous_executor:
        return
    if actor and previous_executor.id == actor.id:
        return

    notification_title, description = MessageTemplates.executor_reassigned(
        request.title,
        _actor_name(actor),
    )
    _send_procurement_notification(
        recipient=previous_executor,
        verb=NotificationVerbs.EXECUTOR_REASSIGNED,
        procurement_request=request,
        title=notification_title,
        description=description,
        actor=actor,
        extra_data={
            "old_executor_id": previous_executor.id,
            "new_executor_id": actor.id if actor else None,
        },
    )

    logger.info(
        f"[Procurement] Исполнитель заявки #{request.id} изменён: "
        f"{previous_executor.id} -> {_actor_id(actor)}"
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

    actor = _request_actor(request)
    recipients = [approval.approver for approval in request.approvals.all()]
    _notify_many(
        recipients,
        verb=NotificationVerbs.CANCELLED,
        procurement_request=request,
        title=notification_title,
        description=description,
        actor=actor,
        extra_data={
            "reason": reason,
            "old_status": getattr(request, "_original_status", None),
            "new_status": request.status,
        },
    )


def notify_stage_approved(approval):
    """
    Уведомить о прохождении этапа согласования.

    Args:
        approval: Объект Approval
    """
    # Не уведомляем заказчика о каждом промежуточном этапе согласования.
    # Следующий согласующий всё ещё должен получить pending-уведомление.
    notify_approvers(approval.request)


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
        description,
        actor=approval.approver,
        extra_data={
            "approval_id": approval.id,
            "approval_priority": approval.priority,
            "new_status": "rejected",
        },
    )


def notify_item_updated(item, actor=None, changed_fields=None):
    """Не уведомлять заказчика о технических изменениях позиции."""
    return


def notify_item_issue_reported(item, actor=None):
    """Уведомить исполнителей о проблеме, которую отметил заявитель."""
    procurement_request = item.request
    actor_name = _actor_name(actor)
    notification_title = 'Позиция закупки требует внимания'
    description = (
        f'{actor_name} отметил проблему по позиции "{item.name}" '
        f'в заявке "{procurement_request.title}".'
    )
    recipients = []
    if procurement_request.executor_id:
        recipients.append(procurement_request.executor)
    recipients.extend(_processing_department_recipients(procurement_request))
    _notify_many(
        recipients,
        verb=NotificationVerbs.ITEM_UPDATED,
        procurement_request=procurement_request,
        title=notification_title,
        description=description,
        actor=actor,
        action_object=item,
        extra_data={
            "item_id": item.id,
            "item_name": item.name,
            "changed_fields": ["execution_status"],
            "new_status": item.execution_status,
        },
    )


def notify_request_comment(request, message, actor=None):
    """Уведомить автора заявки о комментарии к заявке."""
    actor = actor or message.author
    notification_title, description = MessageTemplates.request_commented(
        request.title,
        _actor_name(actor),
    )
    notify_requestor(
        request,
        NotificationVerbs.REQUEST_COMMENTED,
        notification_title,
        description,
        actor=actor,
        action_object=message,
        extra_data={
            "comment_id": message.id,
            "author_id": message.author_id,
        },
    )


def notify_item_comment(item, message, actor=None):
    """Уведомить автора заявки о комментарии к позиции."""
    actor = actor or message.author
    procurement_request = item.request
    notification_title, description = MessageTemplates.item_commented(
        procurement_request.title,
        item.name,
        _actor_name(actor),
    )
    notify_requestor(
        procurement_request,
        NotificationVerbs.ITEM_COMMENTED,
        notification_title,
        description,
        actor=actor,
        action_object=message,
        extra_data={
            "comment_id": message.id,
            "author_id": message.author_id,
            "item_id": item.id,
            "item_name": item.name,
        },
    )
