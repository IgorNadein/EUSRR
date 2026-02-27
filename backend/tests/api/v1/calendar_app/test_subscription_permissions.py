"""
Тесты для прав доступа к подпискам календарей.

Проверяет логику:
- Владелец календаря может изменять can_edit, can_manage
- Владелец подписки может изменять is_visible, color_override
- Другие пользователи получают 403
"""

import pytest
from rest_framework import status


@pytest.mark.django_db
class TestSubscriptionPermissions:
    """Тесты прав доступа к обновлению подписок."""

    def test_owner_can_change_permissions(self, auth_client, make_user, make_calendar):
        """Владелец календаря может изменять права подписки."""
        owner = make_user(username="owner")
        subscriber = make_user(username="subscriber")
        calendar = make_calendar(owner_user=owner)

        # Создаём подписку
        response = auth_client(owner).post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite/",
            data={"user_id": subscriber.id, "can_edit": False, "notify": False},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        subscription_id = response.data["id"]

        # Владелец календаря меняет права
        response = auth_client(owner).patch(
            f"/api/v1/calendar/subscriptions/{subscription_id}/",
            data={"can_edit": True, "can_manage": True},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["can_edit"] is True
        assert response.data["can_manage"] is True

    def test_subscriber_can_change_personal_settings(
        self, auth_client, make_user, make_calendar
    ):
        """Подписчик может изменять свои личные настройки."""
        owner = make_user(username="owner")
        subscriber = make_user(username="subscriber")
        calendar = make_calendar(owner_user=owner)

        # Создаём подписку
        response = auth_client(owner).post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite/",
            data={"user_id": subscriber.id, "can_edit": False, "notify": False},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        subscription_id = response.data["id"]

        # Подписчик меняет видимость
        response = auth_client(subscriber).patch(
            f"/api/v1/calendar/subscriptions/{subscription_id}/",
            data={"is_visible": False},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_visible"] is False

        # Подписчик меняет цвет
        response = auth_client(subscriber).patch(
            f"/api/v1/calendar/subscriptions/{subscription_id}/",
            data={"color_override": "#FF5733"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["color_override"] == "#FF5733"

    def test_subscriber_cannot_change_permissions(
        self, auth_client, make_user, make_calendar
    ):
        """Подписчик НЕ может изменять права доступа."""
        owner = make_user(username="owner")
        subscriber = make_user(username="subscriber")
        calendar = make_calendar(owner_user=owner)

        # Создаём подписку
        response = auth_client(owner).post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite/",
            data={"user_id": subscriber.id, "can_edit": False, "notify": False},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        subscription_id = response.data["id"]

        # Подписчик пытается изменить права - должен получить 403
        response = auth_client(subscriber).patch(
            f"/api/v1/calendar/subscriptions/{subscription_id}/",
            data={"can_edit": True},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert "владелец календаря" in response.data["detail"].lower()

    def test_other_user_cannot_change_subscription(
        self, auth_client, make_user, make_calendar
    ):
        """Другой пользователь не может изменять чужую подписку."""
        owner = make_user(username="owner")
        subscriber = make_user(username="subscriber")
        other_user = make_user(username="other")
        calendar = make_calendar(owner_user=owner)

        # Создаём подписку
        response = auth_client(owner).post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite/",
            data={"user_id": subscriber.id, "can_edit": False, "notify": False},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        subscription_id = response.data["id"]

        # Другой пользователь пытается изменить is_visible - 404
        # (не видит подписку в get_queryset)
        response = auth_client(other_user).patch(
            f"/api/v1/calendar/subscriptions/{subscription_id}/",
            data={"is_visible": False},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_owner_can_change_subscriber_personal_settings(
        self, auth_client, make_user, make_calendar
    ):
        """Владелец календаря может изменять личные настройки подписчиков."""
        owner = make_user(username="owner")
        subscriber = make_user(username="subscriber")
        calendar = make_calendar(owner_user=owner)

        # Создаём подписку
        response = auth_client(owner).post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite/",
            data={"user_id": subscriber.id, "can_edit": False, "notify": False},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        subscription_id = response.data["id"]

        # Владелец может изменить is_visible подписчика
        response = auth_client(owner).patch(
            f"/api/v1/calendar/subscriptions/{subscription_id}/",
            data={"is_visible": False, "color_override": "#123456"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["is_visible"] is False
        assert response.data["color_override"] == "#123456"

    def test_combined_changes_by_owner(self, auth_client, make_user, make_calendar):
        """Владелец может изменять права И личные настройки одновременно."""
        owner = make_user(username="owner")
        subscriber = make_user(username="subscriber")
        calendar = make_calendar(owner_user=owner)

        # Создаём подписку
        response = auth_client(owner).post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite/",
            data={"user_id": subscriber.id, "can_edit": False, "notify": False},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        subscription_id = response.data["id"]

        # Владелец меняет всё разом
        response = auth_client(owner).patch(
            f"/api/v1/calendar/subscriptions/{subscription_id}/",
            data={
                "can_edit": True,
                "can_manage": True,
                "is_visible": False,
                "color_override": "#ABCDEF",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["can_edit"] is True
        assert response.data["can_manage"] is True
        assert response.data["is_visible"] is False
        assert response.data["color_override"] == "#ABCDEF"

    def test_subscriber_can_only_change_own_settings(
        self, auth_client, make_user, make_calendar
    ):
        """Подписчик может изменять только свои настройки, не может права."""
        owner = make_user(username="owner")
        subscriber = make_user(username="subscriber")
        calendar = make_calendar(owner_user=owner)

        # Создаём подписку
        response = auth_client(owner).post(
            f"/api/v1/calendar/calendars/{calendar.id}/invite/",
            data={"user_id": subscriber.id, "can_edit": False, "notify": False},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        subscription_id = response.data["id"]

        # Попытка изменить is_visible + can_edit - должна провалиться
        response = auth_client(subscriber).patch(
            f"/api/v1/calendar/subscriptions/{subscription_id}/",
            data={"is_visible": False, "can_edit": True},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
