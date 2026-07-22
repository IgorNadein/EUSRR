from unittest.mock import patch

import pytest
from django.core.cache import cache

from push_notifications.models import WebPushDevice
from notifications.cache import unread_summary_cache_key
from notifications.models import Notification
from notifications.models import UserChannelPreferences


pytestmark = pytest.mark.django_db


class TestNotificationUnreadSummary:
    def test_unread_summary_groups_unread_notifications_by_verb(
        self, api_client, user_factory
    ):
        user = user_factory()
        other_user = user_factory()
        Notification.objects.create(
            recipient=user,
            verb="procurement_department_request",
            description="Закупка",
            data={"request_id": 10},
        )
        Notification.objects.create(
            recipient=user,
            verb="procurement_department_request",
            description="Еще закупка",
            data={"request_id": "12"},
        )
        Notification.objects.create(
            recipient=user,
            verb="chat_new_message",
            description="Сообщение",
        )
        Notification.objects.create(
            recipient=user,
            verb="regulation_ready",
            description="Регламент Бухгалтерии",
            data={
                "regulation_scope": "department",
                "regulation_department_ids": [7, "7", 8],
            },
        )
        Notification.objects.create(
            recipient=user,
            verb="regulation_ready",
            description="Регламент компании",
            data={"regulation_scope": "company"},
        )
        Notification.objects.create(
            recipient=user,
            verb="regulation_signed_all",
            description="Личный регламент",
            data={"regulation_scope": "personal"},
        )
        Notification.objects.create(
            recipient=user,
            verb="document_uploaded",
            description="Прочитанный документ",
            unread=False,
        )
        Notification.objects.create(
            recipient=other_user,
            verb="chat_new_message",
            description="Чужое сообщение",
        )

        api_client.force_authenticate(user=user)
        cache.delete(unread_summary_cache_key(user.id))

        response = api_client.get("/api/v1/notifications/summary/")

        assert response.status_code == 200
        assert response.data["total"] == 6
        assert {
            item["verb"]: item["unread"]
            for item in response.data["verbs"]
        } == {
            "procurement_department_request": 2,
            "chat_new_message": 1,
            "regulation_ready": 2,
            "regulation_signed_all": 1,
        }
        assert response.data["procurement_requests"] == [
            {"request_id": 10, "unread": 1},
            {"request_id": 12, "unread": 1},
        ]
        assert response.data["regulation_departments"] == [
            {"department_id": 7, "unread": 1},
            {"department_id": 8, "unread": 1},
        ]
        assert response.data["regulation_company_unread"] == 1
        assert response.data["regulation_personal_unread"] == 1

    def test_unread_summary_cache_does_not_stay_stale_after_mark_as_read(
        self, api_client, user_factory
    ):
        user = user_factory()
        notification = Notification.objects.create(
            recipient=user,
            verb="request_updated",
            description="Заявка обновлена",
        )

        api_client.force_authenticate(user=user)
        cache.delete(unread_summary_cache_key(user.id))

        response = api_client.get("/api/v1/notifications/summary/")
        assert response.status_code == 200
        assert response.data["total"] == 1
        assert cache.get(unread_summary_cache_key(user.id)) is not None

        response = api_client.post(
            f"/api/v1/notifications/{notification.id}/read/"
        )
        assert response.status_code == 200
        cached = cache.get(unread_summary_cache_key(user.id))
        assert cached is None or cached["total"] == 0

        response = api_client.get("/api/v1/notifications/summary/")
        assert response.status_code == 200
        assert response.data["total"] == 0


class TestNotificationRealtimeEvents:
    def test_mark_as_read_sends_realtime_event(self, api_client, user_factory):
        user = user_factory()
        notification = Notification.objects.create(
            recipient=user,
            verb="request_updated",
            description="Заявка обновлена",
        )

        api_client.force_authenticate(user=user)

        with patch(
            "notifications.api.views.send_notification_read_event"
        ) as send_event:
            response = api_client.post(
                f"/api/v1/notifications/{notification.id}/read/"
            )

        assert response.status_code == 200
        notification.refresh_from_db()
        assert notification.unread is False
        send_event.assert_called_once_with(user.id, notification.id)

    def test_mark_all_as_read_sends_realtime_event_with_ids(
        self, api_client, user_factory
    ):
        user = user_factory()
        first = Notification.objects.create(
            recipient=user,
            verb="request_new",
            description="Новая заявка",
        )
        second = Notification.objects.create(
            recipient=user,
            verb="request_updated",
            description="Заявка обновлена",
        )

        api_client.force_authenticate(user=user)

        with patch(
            "notifications.api.views.send_notifications_read_all_event"
        ) as send_event:
            response = api_client.post("/api/v1/notifications/read-all/")

        assert response.status_code == 200
        assert (
            Notification.objects.filter(
                recipient=user,
                unread=True,
                deleted=False,
            ).count()
            == 0
        )
        send_event.assert_called_once()
        args, kwargs = send_event.call_args
        assert args[0] == user.id
        assert set(args[1]) == {first.id, second.id}
        assert kwargs == {"category": None}

    def test_mark_category_as_read_sends_category_realtime_event(
        self, api_client, user_factory
    ):
        user = user_factory()
        matching = Notification.objects.create(
            recipient=user,
            verb="request_updated",
            description="Заявка обновлена",
        )
        other = Notification.objects.create(
            recipient=user,
            verb="document_uploaded",
            description="Документ загружен",
        )

        api_client.force_authenticate(user=user)

        with patch(
            "notifications.api.views.send_notifications_read_all_event"
        ) as send_event:
            response = api_client.post(
                "/api/v1/notifications/category/read/",
                {
                    "verbs": ["request_updated"],
                    "category": "Заявки",
                },
                format="json",
            )

        assert response.status_code == 200
        matching.refresh_from_db()
        other.refresh_from_db()
        assert matching.unread is False
        assert other.unread is True
        send_event.assert_called_once()
        args, kwargs = send_event.call_args
        assert args == (user.id, [matching.id])
        assert kwargs == {"category": "Заявки"}


class TestNotificationPreferencesApi:
    def test_get_preferences_returns_never_frequency(
        self, api_client, user_factory
    ):
        user = user_factory()
        UserChannelPreferences.objects.create(
            user=user,
            email_enabled=True,
            email_frequency="never",
        )

        api_client.force_authenticate(user=user)
        response = api_client.get("/api/v1/notifications/preferences/")

        assert response.status_code == 200
        assert response.data["email_frequency"] == "never"

    def test_put_preferences_accepts_legacy_disabled_alias(
        self, api_client, user_factory
    ):
        user = user_factory()
        api_client.force_authenticate(user=user)

        response = api_client.put(
            "/api/v1/notifications/preferences/",
            {"email_enabled": True, "email_frequency": "disabled"},
            format="json",
        )

        assert response.status_code == 200
        prefs = UserChannelPreferences.objects.get(user=user)
        assert prefs.email_enabled is True
        assert prefs.email_frequency == "never"

    def test_put_preferences_accepts_never(
        self, api_client, user_factory
    ):
        user = user_factory()
        api_client.force_authenticate(user=user)

        response = api_client.put(
            "/api/v1/notifications/preferences/",
            {"email_frequency": "never"},
            format="json",
        )

        assert response.status_code == 200
        prefs = UserChannelPreferences.objects.get(user=user)
        assert prefs.email_frequency == "never"

    def test_subscribe_push_enables_push_preferences(
        self, api_client, user_factory
    ):
        user = user_factory()
        UserChannelPreferences.objects.create(user=user, push_enabled=False)
        api_client.force_authenticate(user=user)

        response = api_client.post(
            "/api/v1/notifications/push/subscribe/",
            {
                "endpoint": "https://push.example.test/endpoint-1",
                "keys": {"p256dh": "test-p256dh", "auth": "test-auth"},
                "device_name": "Chrome",
            },
            format="json",
        )

        assert response.status_code == 200
        prefs = UserChannelPreferences.objects.get(user=user)
        assert prefs.push_enabled is True
        assert WebPushDevice.objects.filter(
            user=user,
            registration_id="https://push.example.test/endpoint-1",
            active=True,
        ).exists()

    def test_unsubscribe_last_push_device_disables_push_preferences(
        self, api_client, user_factory
    ):
        user = user_factory()
        UserChannelPreferences.objects.create(user=user, push_enabled=True)
        WebPushDevice.objects.create(
            user=user,
            registration_id="https://push.example.test/endpoint-1",
            p256dh="test-p256dh",
            auth="test-auth",
            browser="Chrome",
            active=True,
        )
        api_client.force_authenticate(user=user)

        response = api_client.delete(
            "/api/v1/notifications/push/unsubscribe/",
            {"endpoint": "https://push.example.test/endpoint-1"},
            format="json",
        )

        assert response.status_code == 200
        prefs = UserChannelPreferences.objects.get(user=user)
        assert prefs.push_enabled is False
