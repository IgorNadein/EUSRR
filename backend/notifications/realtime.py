from asgiref.sync import async_to_sync
from channels.layers import get_channel_layer

from .models import Notification


def get_unread_notifications_count(user_id):
    return Notification.objects.filter(
        recipient_id=user_id,
        unread=True,
        deleted=False,
    ).count()


def _send_user_event(user_id, event):
    channel_layer = get_channel_layer()
    if channel_layer is None:
        return

    async_to_sync(channel_layer.group_send)(f"user_{user_id}", event)


def send_notification_read_event(user_id, notification_id, unread_count=None):
    count = (
        get_unread_notifications_count(user_id)
        if unread_count is None
        else unread_count
    )

    _send_user_event(
        user_id,
        {
            "type": "notification_read",
            "notification_id": notification_id,
            "unread_count": count,
        },
    )
    _send_user_event(
        user_id,
        {
            "type": "notification_count_update",
            "count": count,
        },
    )


def send_notifications_read_all_event(
    user_id,
    notification_ids,
    unread_count=None,
    category=None,
):
    count = (
        get_unread_notifications_count(user_id)
        if unread_count is None
        else unread_count
    )

    _send_user_event(
        user_id,
        {
            "type": "notifications_read_all",
            "notification_ids": notification_ids,
            "category": category,
            "unread_count": count,
        },
    )
    _send_user_event(
        user_id,
        {
            "type": "notification_count_update",
            "count": count,
        },
    )
