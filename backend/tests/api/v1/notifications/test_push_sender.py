import json
from unittest.mock import patch

import pytest
from django.contrib.contenttypes.models import ContentType
from django.test import override_settings
from push_notifications.models import WebPushDevice

from notifications.models import Notification, UserChannelPreferences
from notifications.senders.push import PushNotificationSender


pytestmark = pytest.mark.django_db


def _make_push_device(user):
    return WebPushDevice.objects.create(
        user=user,
        registration_id="https://push.example.test/endpoint",
        p256dh="test-p256dh",
        auth="test-auth",
        browser="CHROME",
        active=True,
    )


def _disable_auto_delivery(user):
    UserChannelPreferences.objects.create(
        user=user,
        web_enabled=False,
        email_enabled=False,
        push_enabled=False,
    )


def _make_notification(user, **kwargs):
    _disable_auto_delivery(user)
    return Notification.objects.create(recipient=user, **kwargs)


def _send_and_load_payload(notification):
    sender = PushNotificationSender()
    with patch.object(WebPushDevice, "send_message", autospec=True) as send_message:
        result = sender.send(notification)

    assert result is True
    send_message.assert_called_once()
    return json.loads(send_message.call_args.args[1])


class TestPushNotificationSenderPayload:
    def test_chat_push_uses_actor_name_without_technical_verb(
        self, user_factory
    ):
        recipient = user_factory(email="recipient@example.com")
        actor = user_factory(
            email="actor@example.com",
            first_name="Олеся",
            last_name="Рубцова",
        )
        _make_push_device(recipient)

        notification = _make_notification(
            recipient,
            actor_content_type=ContentType.objects.get_for_model(actor),
            actor_object_id=actor.pk,
            verb="chat_new_message",
            description="Полинина",
            action_url="/messages/123",
            data={
                "title": "Новое сообщение от Рубцова Олеся",
                "chat_id": 123,
                "message_id": 456,
            },
        )

        payload = _send_and_load_payload(notification)

        assert payload["title"] == "Рубцова Олеся"
        assert payload["head"] == "Рубцова Олеся"
        assert payload["body"] == "Полинина"
        assert payload["url"] == "/messages/123"
        assert payload["data"] == {
            "url": "/messages/123",
            "notification_id": notification.id,
        }
        assert "icon" not in payload
        assert "chat_new_message" not in json.dumps(payload)
        assert "verb" not in payload["data"]

    @override_settings(SITE_URL="https://corp.example.test")
    def test_chat_push_uses_actor_avatar_as_icon(self, user_factory):
        recipient = user_factory(email="avatar-recipient@example.com")
        actor = user_factory(
            email="avatar-actor@example.com",
            first_name="Олеся",
            last_name="Рубцова",
        )
        actor.avatar = "users/avatars/actor.jpg"
        actor.save(update_fields=["avatar"])
        _make_push_device(recipient)

        notification = _make_notification(
            recipient,
            actor_content_type=ContentType.objects.get_for_model(actor),
            actor_object_id=actor.pk,
            verb="chat_new_message",
            description="Полинина",
            action_url="/messages/123",
            data={
                "title": "Новое сообщение от Рубцова Олеся",
                "chat_id": 123,
                "message_id": 456,
            },
        )

        payload = _send_and_load_payload(notification)

        assert (
            payload["icon"]
            == "https://corp.example.test/media/users/avatars/actor.jpg"
        )

    def test_non_chat_push_uses_notification_data_title(self, user_factory):
        recipient = user_factory(email="request-recipient@example.com")
        _make_push_device(recipient)
        notification = _make_notification(
            recipient,
            verb="request_approved",
            description="Ваша заявка одобрена",
            action_url="/requests?request=10",
            data={"title": "Заявка одобрена"},
        )

        payload = _send_and_load_payload(notification)

        assert payload["title"] == "Заявка одобрена"
        assert payload["head"] == "Заявка одобрена"
        assert "request_approved" not in json.dumps(payload)

    def test_non_chat_push_does_not_use_actor_avatar_icon(self, user_factory):
        recipient = user_factory(email="request-avatar-recipient@example.com")
        actor = user_factory(email="request-avatar-actor@example.com")
        actor.avatar = "users/avatars/request-actor.jpg"
        actor.save(update_fields=["avatar"])
        _make_push_device(recipient)

        notification = _make_notification(
            recipient,
            actor_content_type=ContentType.objects.get_for_model(actor),
            actor_object_id=actor.pk,
            verb="request_approved",
            description="Ваша заявка одобрена",
            action_url="/requests?request=10",
            data={"title": "Заявка одобрена"},
        )

        payload = _send_and_load_payload(notification)

        assert "icon" not in payload

    def test_push_title_falls_back_without_actor_or_data_title(
        self, user_factory
    ):
        recipient = user_factory(email="fallback-recipient@example.com")
        _make_push_device(recipient)
        notification = _make_notification(
            recipient,
            verb="system_announcement",
            description="Системное уведомление",
            action_url="/",
            data={},
        )

        payload = _send_and_load_payload(notification)

        assert payload["title"] == "Новое уведомление"
        assert payload["head"] == "Новое уведомление"
        assert "system_announcement" not in json.dumps(payload)

    def test_push_body_is_still_truncated_to_300_characters(
        self, user_factory
    ):
        recipient = user_factory(email="long-body-recipient@example.com")
        _make_push_device(recipient)
        long_body = "а" * 350
        notification = _make_notification(
            recipient,
            verb="document_ready",
            description=long_body,
            action_url="/documents",
            data={"title": "Документ на ознакомление"},
        )

        payload = _send_and_load_payload(notification)

        assert len(payload["body"]) == 300
        assert payload["body"] == ("а" * 297) + "..."

    def test_permanent_push_error_deactivates_device(self, user_factory):
        recipient = user_factory(email="stale-device-recipient@example.com")
        device = _make_push_device(recipient)
        notification = _make_notification(
            recipient,
            verb="document_ready",
            description="Документ готов",
            action_url="/documents",
            data={"title": "Документ"},
        )

        sender = PushNotificationSender()
        with patch.object(
            WebPushDevice,
            "send_message",
            autospec=True,
            side_effect=Exception("Push failed: 400 Bad Request"),
        ):
            result = sender.send(notification)

        assert result is False
        device.refresh_from_db()
        assert device.active is False

    def test_transient_push_error_keeps_device_active(self, user_factory):
        recipient = user_factory(email="transient-device-recipient@example.com")
        device = _make_push_device(recipient)
        notification = _make_notification(
            recipient,
            verb="document_ready",
            description="Документ готов",
            action_url="/documents",
            data={"title": "Документ"},
        )

        sender = PushNotificationSender()
        with patch.object(
            WebPushDevice,
            "send_message",
            autospec=True,
            side_effect=TimeoutError("temporary timeout"),
        ):
            result = sender.send(notification)

        assert result is False
        device.refresh_from_db()
        assert device.active is True
