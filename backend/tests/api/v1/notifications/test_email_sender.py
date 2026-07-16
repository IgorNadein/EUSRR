from unittest.mock import patch

import pytest

from notifications.models import Notification, UserChannelPreferences
from notifications.senders.email import EmailNotificationSender
from notifications.tasks.email import send_digest_emails


pytestmark = pytest.mark.django_db


def _disable_auto_delivery(user):
    UserChannelPreferences.objects.create(
        user=user,
        web_enabled=False,
        email_enabled=False,
        push_enabled=False,
    )


class TestEmailNotificationSender:
    def test_digest_marks_list_notifications_as_emailed(self, user_factory):
        user = user_factory(email="digest-recipient@example.com")
        _disable_auto_delivery(user)
        first = Notification.objects.create(
            recipient=user,
            verb="request_new",
            description="Новая заявка",
        )
        second = Notification.objects.create(
            recipient=user,
            verb="document_ready",
            description="Документ готов",
        )

        sender = EmailNotificationSender()
        with patch("notifications.senders.email.send_mail") as send_mail:
            result = sender.send_digest(user, [first, second], "daily")

        assert result is True
        send_mail.assert_called_once()
        first.refresh_from_db()
        second.refresh_from_db()
        assert first.emailed is True
        assert second.emailed is True


class TestDigestEmailDispatch:
    def test_dispatches_only_matching_users_with_pending_notifications(
        self, user_factory
    ):
        daily_user = user_factory(email="daily-digest@example.com")
        weekly_user = user_factory(email="weekly-digest@example.com")
        empty_user = user_factory(email="empty-digest@example.com")
        instant_user = user_factory(email="instant@example.com")
        for user, frequency in (
            (daily_user, "daily"),
            (weekly_user, "weekly"),
            (empty_user, "daily"),
            (instant_user, "instant"),
        ):
            UserChannelPreferences.objects.create(
                user=user,
                web_enabled=False,
                email_enabled=True,
                email_frequency=frequency,
                push_enabled=False,
            )
        Notification.objects.create(
            recipient=daily_user,
            verb="request_new",
            description="Новая заявка",
        )
        Notification.objects.create(
            recipient=weekly_user,
            verb="document_ready",
            description="Документ готов",
        )
        Notification.objects.create(
            recipient=instant_user,
            verb="request_new",
            description="Мгновенная заявка",
        )

        with patch(
            "notifications.tasks.email.send_digest_email.delay"
        ) as digest_delay:
            dispatched = send_digest_emails("daily")

        assert dispatched == 1
        digest_delay.assert_called_once_with(daily_user.id, "daily")
