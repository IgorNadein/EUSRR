import logging

from celery import shared_task
from django.db.models import Q
from django.utils import timezone

from .constants import GuestVisitEventType, GuestVisitStatus
from .models import Guest, GuestVisit
from .services import (
    GuestLdapService,
    GuestVisitWorkflow,
    get_guest_admin_users,
    notify_guest_visit,
    record_guest_event,
)

logger = logging.getLogger(__name__)


@shared_task(ignore_result=True)
def activate_due_guest_visits():
    now = timezone.now()
    visits = GuestVisit.objects.filter(
        status=GuestVisitStatus.APPROVED,
        unlimited=False,
        access_starts_at__lte=now,
    ).filter(Q(access_expires_at__isnull=True) | Q(access_expires_at__gt=now))
    for visit in visits.select_related("guest", "inviter"):
        try:
            GuestLdapService().sync_guest_for_visit(visit)
        except Exception:
            logger.exception("Failed to activate guest visit %s", visit.pk)


@shared_task(ignore_result=True)
def expire_guest_visits():
    now = timezone.now()
    visits = GuestVisit.objects.filter(
        status=GuestVisitStatus.APPROVED,
        unlimited=False,
        access_expires_at__lte=now,
    )
    for visit in visits.select_related("guest", "inviter"):
        try:
            GuestVisitWorkflow.expire(visit)
        except Exception:
            logger.exception("Failed to expire guest visit %s", visit.pk)


@shared_task(ignore_result=True)
def detect_inactive_inviters():
    visits = GuestVisit.objects.filter(
        status=GuestVisitStatus.APPROVED,
        inviter_inactive=False,
    ).select_related("guest", "inviter")
    admins = list(get_guest_admin_users())
    for visit in visits:
        inviter = visit.inviter
        if inviter.is_active and getattr(inviter, "is_actually_active", True):
            continue
        reason = "Приглашающий неактивен, гостевой доступ отозван автоматически."
        old_status = visit.status
        visit.inviter_inactive = True
        visit.status = GuestVisitStatus.REVOKED
        visit.revoked_at = timezone.now()
        visit.revoke_reason = reason
        visit.save(
            update_fields=[
                "inviter_inactive",
                "status",
                "revoked_at",
                "revoke_reason",
                "updated_at",
            ]
        )
        record_guest_event(
            visit,
            GuestVisitEventType.INVITER_INACTIVE_DETECTED,
            from_status=old_status,
            to_status=GuestVisitStatus.REVOKED,
            comment=reason,
            metadata={"inviter_id": inviter.id},
        )
        record_guest_event(
            visit,
            GuestVisitEventType.REVOKED,
            from_status=old_status,
            to_status=GuestVisitStatus.REVOKED,
            comment=reason,
            metadata={"reason": "inviter_inactive", "inviter_id": inviter.id},
        )
        notify_guest_visit(
            visit,
            "guest_inviter_inactive",
            admins,
            title="Приглашающий гостя неактивен",
            message=reason,
        )
        try:
            GuestLdapService().sync_guest_for_visit(visit)
        except Exception:
            logger.exception(
                "Failed to sync guest %s after inactive inviter revoke",
                visit.guest_id,
            )


def execute_guest_queue_operation(operation: str, payload: dict) -> None:
    guest_id = payload.get("guest_id") or payload.get("object_pk")
    guest = Guest.objects.get(pk=guest_id)
    service = GuestLdapService()
    if operation in {"guest_sync", "guest_disable"}:
        service.sync_guest(
            guest,
            enqueue_on_error=False,
            raise_on_error=True,
        )
    elif operation == "guest_delete":
        service.disable_guest(
            guest,
            enqueue_on_error=False,
            raise_on_error=True,
        )
    else:
        raise ValueError(f"Unknown guest LDAP operation: {operation}")
