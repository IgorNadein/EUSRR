from unittest.mock import patch

import pytest

from notifications.models import Notification, UserChannelPreferences


pytestmark = pytest.mark.django_db


class TestNotificationChannelRouting:
    def test_enqueue_error_does_not_abort_notification_creation(
        self, user_factory, django_capture_on_commit_callbacks
    ):
        user = user_factory(email="route-recipient@example.com")
        UserChannelPreferences.objects.create(
            user=user,
            web_enabled=True,
            email_enabled=True,
            email_frequency="instant",
            push_enabled=True,
        )

        with (
            patch(
                "notifications.tasks.send_websocket_notification.delay",
                side_effect=RuntimeError("broker unavailable"),
            ) as websocket_delay,
            patch(
                "notifications.tasks.send_email_notification.delay"
            ) as email_delay,
            patch(
                "notifications.tasks.send_push_notification.delay"
            ) as push_delay,
        ):
            with django_capture_on_commit_callbacks(execute=True):
                notification = Notification.objects.create(
                    recipient=user,
                    verb="request_new",
                    description="Новая заявка",
                )

        assert Notification.objects.filter(pk=notification.pk).exists()
        websocket_delay.assert_called_once_with(
            notification.id,
            silent=False,
        )
        email_delay.assert_called_once_with(notification.id)
        push_delay.assert_called_once_with(notification.id)

    def test_missing_preferences_are_created_during_routing(
        self, user_factory, django_capture_on_commit_callbacks
    ):
        user = user_factory(email="new-prefs-recipient@example.com")

        with patch(
            "notifications.tasks.send_websocket_notification.delay"
        ) as websocket_delay:
            with django_capture_on_commit_callbacks(execute=True):
                notification = Notification.objects.create(
                    recipient=user,
                    verb="request_new",
                    description="Новая заявка",
                )

        assert UserChannelPreferences.objects.filter(user=user).exists()
        websocket_delay.assert_called_once_with(
            notification.id,
            silent=False,
        )
