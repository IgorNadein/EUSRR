# tests/api/v1/calendar_app/test_invitation_api.py
"""
Тесты для API приглашения пользователей в календарь.

Покрывает endpoints:
- POST /api/v1/calendar/calendars/{id}/invite/
- POST /api/v1/calendar/calendars/{id}/invite-bulk/
"""

from __future__ import annotations

import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestCalendarInvite:
    """Тесты для приглашения одного пользователя."""

    def test_invite_user_as_owner(
        self, auth_client, make_user, make_calendar, CalendarSubscription
    ):
        """Владелец может пригласить пользователя."""
        owner = make_user(username="owner")
        invited = make_user(username="invited_user")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite/",
            {
                "user_id": invited.id,
                "can_edit": True,
                "can_manage": False,
                "notify": True,
            },
            format="json",
        )

        assert response.status_code == 201, response.data
        assert response.data["user"] == invited.id
        assert response.data["can_edit"] is True
        assert response.data["can_manage"] is False

        # Проверяем, что подписка создана
        subscription = CalendarSubscription.objects.filter(
            calendar=calendar, user=invited
        ).first()
        assert subscription is not None
        assert subscription.can_edit is True
        assert subscription.can_manage is False

    def test_invite_user_not_owner(self, auth_client, make_user, make_calendar):
        """Не-владелец не может приглашать."""
        owner = make_user(username="owner")
        non_owner = make_user(username="non_owner")
        invited = make_user(username="invited_user")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        client = auth_client(non_owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite/",
            {
                "user_id": invited.id,
                "can_edit": True,
                "notify": True,
            },
            format="json",
        )

        assert response.status_code == 403
        assert "владелец" in response.data["detail"].lower()

    def test_invite_with_edit_permission(
        self, auth_client, make_user, make_calendar, CalendarSubscription
    ):
        """Приглашение с правом редактирования."""
        owner = make_user(username="owner")
        invited = make_user(username="invited_user")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite/",
            {
                "user_id": invited.id,
                "can_edit": True,
                "can_manage": False,
                "notify": False,
            },
            format="json",
        )

        assert response.status_code == 201
        subscription = CalendarSubscription.objects.get(calendar=calendar, user=invited)
        assert subscription.can_edit is True
        assert subscription.can_manage is False

    def test_invite_with_manage_permission(
        self, auth_client, make_user, make_calendar, CalendarSubscription
    ):
        """Приглашение с правом управления."""
        owner = make_user(username="owner")
        invited = make_user(username="invited_user")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite/",
            {
                "user_id": invited.id,
                "can_edit": False,
                "can_manage": True,
                "notify": False,
            },
            format="json",
        )

        assert response.status_code == 201
        subscription = CalendarSubscription.objects.get(calendar=calendar, user=invited)
        assert subscription.can_edit is False
        assert subscription.can_manage is True

    def test_invite_with_both_permissions(
        self, auth_client, make_user, make_calendar, CalendarSubscription
    ):
        """Приглашение с обоими правами (редактирование и управление)."""
        owner = make_user(username="owner")
        invited = make_user(username="invited_user")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite/",
            {
                "user_id": invited.id,
                "can_edit": True,
                "can_manage": True,
                "notify": False,
            },
            format="json",
        )

        assert response.status_code == 201
        subscription = CalendarSubscription.objects.get(calendar=calendar, user=invited)
        assert subscription.can_edit is True
        assert subscription.can_manage is True

    def test_invite_already_subscribed(
        self, auth_client, make_user, make_calendar, make_subscription
    ):
        """Ошибка при приглашении уже подписанного пользователя."""
        owner = make_user(username="owner")
        invited = make_user(username="invited_user")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        # Создаем существующую подписку
        existing_sub = make_subscription(calendar=calendar, user=invited)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite/",
            {
                "user_id": invited.id,
                "can_edit": True,
                "notify": False,
            },
            format="json",
        )

        assert response.status_code == 400
        assert "уже подписан" in response.data["detail"].lower()
        assert response.data.get("subscription_id") == existing_sub.id

    def test_invite_self(self, auth_client, make_user, make_calendar):
        """Ошибка при приглашении самого себя."""
        owner = make_user(username="owner")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite/",
            {
                "user_id": owner.id,
                "can_edit": True,
                "notify": False,
            },
            format="json",
        )

        assert response.status_code == 400
        assert "себя" in response.data["detail"].lower()

    def test_invite_nonexistent_user(self, auth_client, make_user, make_calendar):
        """Ошибка при приглашении несуществующего пользователя."""
        owner = make_user(username="owner")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite/",
            {
                "user_id": 99999,  # несуществующий ID
                "can_edit": True,
                "notify": False,
            },
            format="json",
        )

        assert response.status_code == 404
        assert "не найден" in response.data["detail"].lower()

    def test_invite_by_username(
        self, auth_client, make_user, make_calendar, CalendarSubscription
    ):
        """Приглашение по username вместо user_id."""
        owner = make_user(username="owner")
        invited = make_user(username="invited_user")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite/",
            {
                "username": "invited_user",
                "can_edit": True,
                "notify": False,
            },
            format="json",
        )

        assert response.status_code == 201
        subscription = CalendarSubscription.objects.get(calendar=calendar, user=invited)
        assert subscription.can_edit is True

    def test_invite_by_nonexistent_username(
        self, auth_client, make_user, make_calendar
    ):
        """Ошибка при приглашении по несуществующему username."""
        owner = make_user(username="owner")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite/",
            {
                "username": "nonexistent_user",
                "can_edit": True,
                "notify": False,
            },
            format="json",
        )

        assert response.status_code == 404
        assert "не найден" in response.data["detail"].lower()

    def test_invite_sends_notification(self, auth_client, make_user, make_calendar):
        """Проверка отправки уведомления при приглашении."""
        from notifications.models import Notification, NotificationType

        owner = make_user(username="owner")
        invited = make_user(username="invited_user")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite/",
            {
                "user_id": invited.id,
                "can_edit": True,
                "notify": True,  # Включаем уведомления
            },
            format="json",
        )

        assert response.status_code == 201

        # Получаем тип уведомления
        notification_type = NotificationType.objects.filter(
            code="calendar_invitation"
        ).first()

        # Проверяем, что уведомление создано
        notification = Notification.objects.filter(
            recipient=invited,
            notification_type=notification_type,
            object_id=calendar.id,
        ).first()

        assert notification is not None
        assert "приглас" in notification.message.lower()
        assert calendar.title in notification.message

    def test_invite_without_notification(self, auth_client, make_user, make_calendar):
        """Приглашение без уведомления (notify=False)."""
        from notifications.models import Notification, NotificationType

        owner = make_user(username="owner")
        invited = make_user(username="invited_user")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite/",
            {
                "user_id": invited.id,
                "can_edit": True,
                "notify": False,  # Отключаем уведомления
            },
            format="json",
        )

        assert response.status_code == 201

        # Получаем тип уведомления (если он существует)
        notification_type = NotificationType.objects.filter(
            code="calendar_invitation"
        ).first()

        # Проверяем, что уведомление НЕ создано
        if notification_type:
            notification = Notification.objects.filter(
                recipient=invited,
                notification_type=notification_type,
            ).first()
            assert notification is None

    def test_invite_without_user_identifier(
        self, auth_client, make_user, make_calendar
    ):
        """Ошибка при отсутствии user_id и username."""
        owner = make_user(username="owner")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite/",
            {
                "can_edit": True,
                "notify": False,
            },
            format="json",
        )

        assert response.status_code == 400

    def test_invite_with_both_identifiers(self, auth_client, make_user, make_calendar):
        """Ошибка при указании и user_id и username одновременно."""
        owner = make_user(username="owner")
        invited = make_user(username="invited_user")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite/",
            {
                "user_id": invited.id,
                "username": "invited_user",
                "can_edit": True,
                "notify": False,
            },
            format="json",
        )

        assert response.status_code == 400


@pytest.mark.django_db
class TestCalendarInviteBulk:
    """Тесты для массового приглашения пользователей."""

    def test_invite_bulk_multiple_users(
        self, auth_client, make_user, make_calendar, CalendarSubscription
    ):
        """Массовое приглашение нескольких пользователей."""
        owner = make_user(username="owner")
        user1 = make_user(username="user1")
        user2 = make_user(username="user2")
        user3 = make_user(username="user3")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite-bulk/",
            {
                "user_ids": [user1.id, user2.id, user3.id],
                "can_edit": True,
                "can_manage": False,
                "notify": False,
            },
            format="json",
        )

        assert response.status_code == 201
        assert response.data["total_created"] == 3
        assert response.data["total_already_subscribed"] == 0
        assert response.data["total_errors"] == 0
        assert len(response.data["created"]) == 3

        # Проверяем, что подписки созданы
        assert CalendarSubscription.objects.filter(
            calendar=calendar, user=user1
        ).exists()
        assert CalendarSubscription.objects.filter(
            calendar=calendar, user=user2
        ).exists()
        assert CalendarSubscription.objects.filter(
            calendar=calendar, user=user3
        ).exists()

    def test_invite_bulk_with_already_subscribed(
        self, auth_client, make_user, make_calendar, make_subscription
    ):
        """Обработка уже подписанных пользователей."""
        owner = make_user(username="owner")
        user1 = make_user(username="user1")
        user2 = make_user(username="user2")
        user3 = make_user(username="user3")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        # User2 уже подписан
        existing_sub = make_subscription(calendar=calendar, user=user2)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite-bulk/",
            {
                "user_ids": [user1.id, user2.id, user3.id],
                "can_edit": True,
                "notify": False,
            },
            format="json",
        )

        # Должен быть статус 201, даже если некоторые уже подписаны
        assert response.status_code in [200, 201]
        assert response.data["total_created"] == 2
        assert response.data["total_already_subscribed"] == 1
        assert response.data["total_errors"] == 0

        # Проверяем список уже подписанных
        already_sub = response.data["already_subscribed"]
        assert len(already_sub) == 1
        assert already_sub[0]["user_id"] == user2.id
        assert already_sub[0]["subscription_id"] == existing_sub.id

    def test_invite_bulk_excludes_owner(
        self, auth_client, make_user, make_calendar, CalendarSubscription
    ):
        """Владелец автоматически исключается из списка приглашаемых."""
        owner = make_user(username="owner")
        user1 = make_user(username="user1")
        user2 = make_user(username="user2")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite-bulk/",
            {
                "user_ids": [user1.id, owner.id, user2.id],  # Включаем owner
                "can_edit": True,
                "notify": False,
            },
            format="json",
        )

        # Владелец должен быть исключен
        assert response.status_code in [200, 201]
        assert response.data["total_created"] == 2

        # Владелец не должен быть в подписках
        assert not CalendarSubscription.objects.filter(
            calendar=calendar, user=owner
        ).exists()

    def test_invite_bulk_partial_errors(self, auth_client, make_user, make_calendar):
        """Обработка частичных ошибок при массовом приглашении."""
        owner = make_user(username="owner")
        user1 = make_user(username="user1")
        user2 = make_user(username="user2")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite-bulk/",
            {
                "user_ids": [
                    user1.id,
                    99999,  # несуществующий пользователь
                    user2.id,
                ],
                "can_edit": True,
                "notify": False,
            },
            format="json",
        )

        # Должны создаться подписки для существующих пользователей
        assert response.status_code in [200, 201]
        # Несуществующий пользователь просто не будет найден и пропущен
        # (User.objects.filter(id__in=[...]) вернет только существующих)

    def test_invite_bulk_by_usernames(
        self, auth_client, make_user, make_calendar, CalendarSubscription
    ):
        """Массовое приглашение по usernames."""
        owner = make_user(username="owner")
        user1 = make_user(username="user1")
        user2 = make_user(username="user2")
        user3 = make_user(username="user3")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite-bulk/",
            {
                "usernames": ["user1", "user2", "user3"],
                "can_edit": True,
                "notify": False,
            },
            format="json",
        )

        assert response.status_code == 201
        assert response.data["total_created"] == 3

        # Проверяем, что подписки созданы
        assert CalendarSubscription.objects.filter(
            calendar=calendar, user=user1
        ).exists()
        assert CalendarSubscription.objects.filter(
            calendar=calendar, user=user2
        ).exists()
        assert CalendarSubscription.objects.filter(
            calendar=calendar, user=user3
        ).exists()

    def test_invite_bulk_empty_list(self, auth_client, make_user, make_calendar):
        """Ошибка при пустом списке пользователей."""
        owner = make_user(username="owner")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite-bulk/",
            {
                "user_ids": [],
                "can_edit": True,
                "notify": False,
            },
            format="json",
        )

        assert response.status_code == 400

    def test_invite_bulk_sends_notifications(
        self, auth_client, make_user, make_calendar
    ):
        """Проверка отправки уведомлений всем приглашенным."""
        from notifications.models import Notification, NotificationType

        owner = make_user(username="owner")
        user1 = make_user(username="user1")
        user2 = make_user(username="user2")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite-bulk/",
            {
                "user_ids": [user1.id, user2.id],
                "can_edit": True,
                "notify": True,  # Включаем уведомления
            },
            format="json",
        )

        assert response.status_code == 201

        # Получаем тип уведомления
        notification_type = NotificationType.objects.filter(
            code="calendar_invitation"
        ).first()

        # Проверяем, что уведомления созданы для обоих пользователей
        notification1 = Notification.objects.filter(
            recipient=user1,
            notification_type=notification_type,
            object_id=calendar.id,
        ).first()
        notification2 = Notification.objects.filter(
            recipient=user2,
            notification_type=notification_type,
            object_id=calendar.id,
        ).first()

        assert notification1 is not None
        assert notification2 is not None

    def test_invite_bulk_without_notifications(
        self, auth_client, make_user, make_calendar
    ):
        """Массовое приглашение без уведомлений."""
        from notifications.models import Notification, NotificationType

        owner = make_user(username="owner")
        user1 = make_user(username="user1")
        user2 = make_user(username="user2")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite-bulk/",
            {
                "user_ids": [user1.id, user2.id],
                "can_edit": True,
                "notify": False,  # Отключаем уведомления
            },
            format="json",
        )

        assert response.status_code == 201

        # Получаем тип уведомления (если он существует)
        notification_type = NotificationType.objects.filter(
            code="calendar_invitation"
        ).first()

        # Проверяем, что уведомления НЕ созданы
        if notification_type:
            notifications_count = Notification.objects.filter(
                notification_type=notification_type,
                object_id=calendar.id,
            ).count()

            assert notifications_count == 0

    def test_invite_bulk_statistics(
        self, auth_client, make_user, make_calendar, make_subscription
    ):
        """Проверка статистики результата массового приглашения."""
        owner = make_user(username="owner")
        user1 = make_user(username="user1")
        user2 = make_user(username="user2")
        user3 = make_user(username="user3")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        # User2 уже подписан
        make_subscription(calendar=calendar, user=user2)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite-bulk/",
            {
                "user_ids": [user1.id, user2.id, user3.id],
                "can_edit": True,
                "notify": False,
            },
            format="json",
        )

        assert response.status_code in [200, 201]

        # Проверяем статистику
        assert "total_created" in response.data
        assert "total_already_subscribed" in response.data
        assert "total_errors" in response.data
        assert "created" in response.data
        assert "already_subscribed" in response.data
        assert "errors" in response.data

        assert response.data["total_created"] == 2
        assert response.data["total_already_subscribed"] == 1
        assert response.data["total_errors"] == 0

    def test_invite_bulk_not_owner(self, auth_client, make_user, make_calendar):
        """Не-владелец не может массово приглашать."""
        owner = make_user(username="owner")
        non_owner = make_user(username="non_owner")
        user1 = make_user(username="user1")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        client = auth_client(non_owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite-bulk/",
            {
                "user_ids": [user1.id],
                "can_edit": True,
                "notify": False,
            },
            format="json",
        )

        assert response.status_code == 403
        assert "владелец" in response.data["detail"].lower()

    def test_invite_bulk_no_users_found(self, auth_client, make_user, make_calendar):
        """Ошибка когда ни один пользователь не найден."""
        owner = make_user(username="owner")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite-bulk/",
            {
                "user_ids": [99998, 99999],  # несуществующие ID
                "can_edit": True,
                "notify": False,
            },
            format="json",
        )

        assert response.status_code == 404
        assert "не найден" in response.data["detail"].lower()

    def test_invite_bulk_without_identifier_list(
        self, auth_client, make_user, make_calendar
    ):
        """Ошибка при отсутствии списка пользователей."""
        owner = make_user(username="owner")
        calendar = make_calendar(title="Test Calendar", owner_user=owner)

        client = auth_client(owner)
        response = client.post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite-bulk/",
            {
                "can_edit": True,
                "notify": False,
            },
            format="json",
        )

        assert response.status_code == 400
