"""
Тесты для проверки прав доступа к календарям.

Проверяет исправление бага, где обычные пользователи не могли
создавать события в глобальных календарях с правом can_edit.
"""

from datetime import date

import pytest
from calendar_app.models import Calendar, CalendarSubscription, CalendarVisibility
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()


@pytest.fixture
def api_client():
    """API клиент."""
    return APIClient()


@pytest.fixture
def admin_user(db):
    """Создаёт администратора."""
    return User.objects.create_superuser(
        username="admin", email="admin@test.com", password="admin123"
    )


@pytest.fixture
def regular_user(db):
    """Создаёт обычного пользователя."""
    return User.objects.create_user(
        username="user",
        email="user@test.com",
        password="user123",
        phone_number="+79001234567",
        send_activation_email=False,
    )


@pytest.fixture
def global_calendar(db, admin_user):
    """Создаёт глобальный календарь."""
    return Calendar.objects.create(
        title="Общий календарь",
        description="Календарь для всех",
        visibility=CalendarVisibility.PUBLIC,
        default_can_edit=False,  # По умолчанию не могут редактировать
        created_by=admin_user,
    )


@pytest.mark.django_db
class TestGlobalCalendarPermissions:
    """Тесты прав доступа для глобальных календарей."""

    def test_admin_can_create_event_in_global_calendar(
        self, api_client, admin_user, global_calendar
    ):
        """Админ может создавать события в глобальном календаре."""
        api_client.force_authenticate(user=admin_user)

        response = api_client.post(
            "/api/v1/calendar/events/",
            {
                "calendar_id": global_calendar.id,
                "title": "Встреча админов",
                "start_date": "2026-03-01",
                "all_day": True,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "Встреча админов"

    def test_regular_user_cannot_create_without_permission(
        self, api_client, regular_user, global_calendar
    ):
        """Обычный пользователь НЕ может создавать без прав."""
        api_client.force_authenticate(user=regular_user)

        response = api_client.post(
            "/api/v1/calendar/events/",
            {
                "calendar_id": global_calendar.id,
                "title": "Попытка создать",
                "start_date": "2026-03-01",
                "all_day": True,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_regular_user_can_create_with_subscription(
        self, api_client, regular_user, global_calendar
    ):
        """Обычный пользователь МОЖЕТ создавать с подпиской can_edit=True."""
        # Создаём подписку с правом редактирования
        CalendarSubscription.objects.create(
            calendar=global_calendar, user=regular_user, can_edit=True
        )

        api_client.force_authenticate(user=regular_user)

        response = api_client.post(
            "/api/v1/calendar/events/",
            {
                "calendar_id": global_calendar.id,
                "title": "Событие пользователя",
                "start_date": "2026-03-01",
                "all_day": True,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "Событие пользователя"

    def test_regular_user_cannot_create_with_readonly_subscription(
        self, api_client, regular_user, global_calendar
    ):
        """Пользователь НЕ может создавать с подпиской can_edit=False."""
        # Создаём подписку БЕЗ права редактирования
        CalendarSubscription.objects.create(
            calendar=global_calendar, user=regular_user, can_edit=False
        )

        api_client.force_authenticate(user=regular_user)

        response = api_client.post(
            "/api/v1/calendar/events/",
            {
                "calendar_id": global_calendar.id,
                "title": "Попытка создать",
                "start_date": "2026-03-01",
                "all_day": True,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_regular_user_can_create_when_default_can_edit_true(
        self, api_client, regular_user, admin_user
    ):
        """Пользователь МОЖЕТ создавать если default_can_edit=True."""
        # Создаём календарь с default_can_edit=True
        calendar = Calendar.objects.create(
            title="Открытый календарь",
            visibility=CalendarVisibility.PUBLIC,
            default_can_edit=True,  # ✅ Все могут редактировать
            created_by=admin_user,
        )

        # Подписываем пользователя (обязательно для доступа)
        CalendarSubscription.objects.create(
            calendar=calendar, user=regular_user, can_edit=True
        )

        api_client.force_authenticate(user=regular_user)

        response = api_client.post(
            "/api/v1/calendar/events/",
            {
                "calendar_id": calendar.id,
                "title": "Открытое событие",
                "start_date": "2026-03-01",
                "all_day": True,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "Открытое событие"


@pytest.mark.django_db
class TestLegacyCalendarPermissions:
    """Тесты обратной совместимости с legacy календарями."""

    def test_regular_user_cannot_create_in_company_calendar(
        self, api_client, regular_user
    ):
        """Обычный пользователь НЕ может создавать в календаре компании (legacy)."""
        api_client.force_authenticate(user=regular_user)

        response = api_client.post(
            "/api/v1/calendar/events/",
            {
                # Без calendar_id, department_id, employee_id = календарь компании
                "title": "Попытка создать",
                "start_date": "2026-03-01",
                "all_day": True,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_admin_can_create_in_company_calendar(self, api_client, admin_user):
        """Админ МОЖЕТ создавать в календаре компании (legacy)."""
        api_client.force_authenticate(user=admin_user)

        response = api_client.post(
            "/api/v1/calendar/events/",
            {
                "title": "Собрание компании",
                "start_date": "2026-03-01",
                "all_day": True,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "Собрание компании"

    def test_user_can_create_in_personal_calendar(self, api_client, regular_user):
        """Пользователь МОЖЕТ создавать в своём личном календаре."""
        api_client.force_authenticate(user=regular_user)

        response = api_client.post(
            "/api/v1/calendar/events/",
            {
                "employee_id": regular_user.id,
                "title": "Личное событие",
                "start_date": "2026-03-01",
                "all_day": True,
            },
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["title"] == "Личное событие"


@pytest.mark.django_db
class TestEventUpdateDeletePermissions:
    """Тесты прав на обновление и удаление событий."""

    def test_user_can_update_own_event_in_global_calendar(
        self, api_client, regular_user, global_calendar
    ):
        """Пользователь МОЖЕТ обновлять своё событие если есть права."""
        from calendar_app.models import CalendarEvent

        # Даём права
        CalendarSubscription.objects.create(
            calendar=global_calendar, user=regular_user, can_edit=True
        )

        # Создаём событие
        event = CalendarEvent.objects.create(
            calendar=global_calendar,
            title="Моё событие",
            start_date=date(2026, 3, 1),
            all_day=True,
            created_by=regular_user,
        )

        api_client.force_authenticate(user=regular_user)

        response = api_client.patch(
            f"/api/v1/calendar/events/{event.id}/",
            {"title": "Обновлённое событие"},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["title"] == "Обновлённое событие"

    def test_user_cannot_update_without_permission(
        self, api_client, regular_user, global_calendar, admin_user
    ):
        """Пользователь НЕ может обновлять без прав."""
        from calendar_app.models import CalendarEvent

        # Создаём событие БЕЗ прав у пользователя
        event = CalendarEvent.objects.create(
            calendar=global_calendar,
            title="Событие админа",
            start_date=date(2026, 3, 1),
            all_day=True,
            created_by=admin_user,
        )

        api_client.force_authenticate(user=regular_user)

        response = api_client.patch(
            f"/api/v1/calendar/events/{event.id}/",
            {"title": "Попытка обновить"},
            format="json",
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN
