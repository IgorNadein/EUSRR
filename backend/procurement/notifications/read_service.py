from dataclasses import dataclass

from django.contrib.contenttypes.models import ContentType
from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from notifications.cache import invalidate_unread_summary
from notifications.models import Notification
from notifications.realtime import send_notifications_read_all_event
from procurement.models import ProcurementRequest


@dataclass(frozen=True)
class ProcurementNotificationReadResult:
    notification_ids: list[int]
    count: int


class ProcurementNotificationReadService:
    """Use case for reading notifications related to a procurement request."""

    procurement_verb_filter = (
        Q(verb__startswith="procurement_")
        | Q(verb__startswith="equipment_")
    )

    def mark_request_notifications_as_read(
        self,
        *,
        user,
        procurement_request: ProcurementRequest,
    ) -> ProcurementNotificationReadResult:
        queryset = self._get_unread_queryset(
            user_id=user.id,
            procurement_request=procurement_request,
        )
        notification_ids = list(queryset.values_list("id", flat=True))

        if not notification_ids:
            return ProcurementNotificationReadResult(
                notification_ids=[],
                count=0,
            )

        read_at = timezone.now()
        count = Notification.objects.filter(
            id__in=notification_ids,
        ).update(
            unread=False,
            timestamp_read=read_at,
        )

        invalidate_unread_summary(user.id)

        def notify_after_commit():
            invalidate_unread_summary(user.id)
            send_notifications_read_all_event(user.id, notification_ids)

        transaction.on_commit(notify_after_commit)

        return ProcurementNotificationReadResult(
            notification_ids=notification_ids,
            count=count,
        )

    def _get_unread_queryset(
        self,
        *,
        user_id: int,
        procurement_request: ProcurementRequest,
    ):
        request_content_type = ContentType.objects.get_for_model(
            ProcurementRequest,
        )
        request_id = procurement_request.id
        request_id_text = str(request_id)

        request_filter = (
            Q(data__request_id=request_id)
            | Q(data__request_id=request_id_text)
            | Q(
                target_content_type=request_content_type,
                target_object_id=request_id_text,
            )
            | Q(
                action_object_content_type=request_content_type,
                action_object_object_id=request_id_text,
            )
        )

        return (
            Notification.objects.filter(
                recipient_id=user_id,
                unread=True,
                deleted=False,
            )
            .filter(self.procurement_verb_filter)
            .filter(request_filter)
            .distinct()
        )
