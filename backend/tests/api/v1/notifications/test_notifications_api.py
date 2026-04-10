from unittest.mock import patch

import pytest

from notifications.models import Notification
from notifications.models import UserChannelPreferences


pytestmark = pytest.mark.django_db


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
