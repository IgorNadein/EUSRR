from django.db import transaction
from django.db.models.signals import post_delete, post_save
from django.dispatch import receiver

from .activity import create_procurement_activity
from .constants import ApprovalStatus, ProcurementStatus
from .models import (
    Approval,
    ProcurementActivityAction,
    ProcurementActivityObjectKind,
    ProcurementItemAttachment,
    ProcurementRequest,
)


REQUEST_STATUS_ACTIONS = {
    ProcurementStatus.PENDING: ProcurementActivityAction.SUBMITTED,
    ProcurementStatus.APPROVED: ProcurementActivityAction.APPROVED,
    ProcurementStatus.WAITING: ProcurementActivityAction.APPROVED,
    ProcurementStatus.IN_PROGRESS: ProcurementActivityAction.STARTED,
    ProcurementStatus.COMPLETED: ProcurementActivityAction.COMPLETED,
    ProcurementStatus.REJECTED: ProcurementActivityAction.REJECTED,
    ProcurementStatus.CANCELLED: ProcurementActivityAction.CANCELLED,
}


@receiver(post_save, sender=ProcurementRequest)
def record_procurement_request_activity(sender, instance, created, **kwargs):
    actor = getattr(instance, "_notification_actor", None)
    if created:
        create_procurement_activity(
            instance,
            actor or instance.requestor,
            ProcurementActivityAction.CREATED,
            object_kind=ProcurementActivityObjectKind.REQUEST,
            object_id=instance.pk,
            metadata={"title": instance.title},
        )
        return

    old_status = getattr(instance, "_original_status", instance.status)
    if old_status == instance.status:
        return

    action = REQUEST_STATUS_ACTIONS.get(instance.status)
    if action is None:
        return
    create_procurement_activity(
        instance,
        actor,
        action,
        object_kind=ProcurementActivityObjectKind.REQUEST,
        object_id=instance.pk,
        metadata={
            "old_status": old_status,
            "new_status": instance.status,
            "reason": getattr(instance, "cancellation_reason", ""),
        },
    )


@receiver(post_save, sender=Approval)
def record_procurement_approval_activity(sender, instance, created, **kwargs):
    if created:
        return
    old_status = getattr(instance, "_original_approval_status", instance.status)
    if old_status == instance.status:
        return
    action = {
        ApprovalStatus.APPROVED: ProcurementActivityAction.STAGE_APPROVED,
        ApprovalStatus.REJECTED: ProcurementActivityAction.STAGE_REJECTED,
    }.get(instance.status)
    if action is None:
        return
    create_procurement_activity(
        instance.request,
        instance.approver,
        action,
        object_kind=ProcurementActivityObjectKind.APPROVAL,
        object_id=instance.pk,
        metadata={
            "step_name": instance.step_name,
            "priority": instance.priority,
            "comment": instance.comment,
        },
    )


@receiver(post_delete, sender=ProcurementItemAttachment)
def delete_procurement_item_attachment_file(sender, instance, **kwargs):
    if not instance.file or not instance.file.name:
        return

    storage = instance.file.storage
    name = instance.file.name
    transaction.on_commit(
        lambda: storage.delete(name) if storage.exists(name) else None
    )
