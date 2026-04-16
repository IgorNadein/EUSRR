from dataclasses import dataclass

from django.db import transaction
from django.utils import timezone

from notifications.models import Notification
from notifications.realtime import send_notifications_read_all_event

from communications.notifications.config import NotificationVerbs


@dataclass(frozen=True)
class ChatNotificationReadResult:
    notification_ids: list[int]
    count: int


class ChatNotificationReadService:
    """Use case for reading notifications related to a specific chat."""

    chat_related_verbs = (
        NotificationVerbs.NEW_MESSAGE,
        NotificationVerbs.ANNOUNCEMENT,
        NotificationVerbs.MENTION,
        NotificationVerbs.REPLY,
        NotificationVerbs.ADDED_TO_CHAT,
        NotificationVerbs.COMMENTED,
    )

    def mark_chat_notifications_as_read(
        self,
        *,
        user,
        chat_id: int,
    ) -> ChatNotificationReadResult:
        queryset = self._get_unread_queryset(user_id=user.id, chat_id=chat_id)
        notification_ids = list(queryset.values_list('id', flat=True))

        if not notification_ids:
            return ChatNotificationReadResult(notification_ids=[], count=0)

        read_at = timezone.now()
        count = queryset.update(unread=False, timestamp_read=read_at)

        transaction.on_commit(
            lambda: send_notifications_read_all_event(user.id, notification_ids)
        )

        return ChatNotificationReadResult(
            notification_ids=notification_ids,
            count=count,
        )

    def _get_unread_queryset(self, *, user_id: int, chat_id: int):
        return Notification.objects.filter(
            recipient_id=user_id,
            unread=True,
            deleted=False,
            verb__in=self.chat_related_verbs,
            data__chat_id=chat_id,
        )
