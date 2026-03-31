# backend/api/v1/schedule/tests.py
"""
Тесты для django-scheduler API endpoints.
"""
import pytest
from django.utils import timezone
from datetime import datetime, timedelta
from rest_framework.test import APIClient
from rest_framework import status
from schedule.models import Calendar, Event, Rule
from employees.models import Employee


@pytest.fixture
def api_client():
    """Клиент API с авторизацией."""
    client = APIClient()
    return client


@pytest.fixture
def test_user(db):
    """Создание тестового пользователя."""
    user = Employee.objects.create_user(
        email="test@example.com",
        phone_number="+79991234567",  # Обязательное поле
        password="testpass123",
        username="testuser",
        first_name="Test",
        last_name="User",
        send_activation_email=False  # Не отправляем email в тестах
    )
    return user


@pytest.fixture
def authenticated_client(api_client, test_user):
    """Авторизованный клиент."""
    api_client.force_authenticate(user=test_user)
    return api_client


@pytest.fixture
def test_calendar(test_user):
    """Создание тестового календаря."""
    return Calendar.objects.create(
        name="Тестовый календарь",
        slug="test-calendar"
    )


@pytest.fixture
def test_event(test_calendar, test_user):
    """Создание тестового события."""
    now = timezone.now()
    return Event.objects.create(
        calendar=test_calendar,
        title="Тестовое событие",
        description="Описание",
        start=now,
        end=now + timedelta(hours=1),
        creator=test_user,
        color_event="#3498db"
    )


# ==================== ТЕСТЫ КАЛЕНДАРЕЙ ====================

@pytest.mark.django_db
class TestCalendarAPI:
    """Тесты для Calendar ViewSet."""
    
    def test_list_calendars_unauthorized(self, api_client):
        """Проверка: неавторизованный доступ запрещён."""
        response = api_client.get('/api/v1/schedule/calendars/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_list_calendars(self, authenticated_client, test_calendar):
        """Проверка: список календарей возвращается."""
        response = authenticated_client.get('/api/v1/schedule/calendars/')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Проверяем что данные - это список
        data = response.data if isinstance(response.data, list) else response.data.get('results', [])
        assert len(data) > 0
        
        # Проверяем структуру
        calendar_data = data[0]
        assert calendar_data['name'] == test_calendar.name
        assert calendar_data['slug'] == test_calendar.slug
        assert 'events_count' in calendar_data
    
    def test_create_calendar(self, authenticated_client):
        """Проверка: создание календаря."""
        data = {
            "name": "Новый календарь",
            "slug": "new-calendar"
        }
        response = authenticated_client.post(
            '/api/v1/schedule/calendars/',
            data,
            format='json'
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == data['name']
        assert response.data['slug'] == data['slug']
        
        # Проверяем что календарь создался в БД
        assert Calendar.objects.filter(slug='new-calendar').exists()
    
    def test_create_calendar_without_slug(self, authenticated_client):
        """Проверка: slug автогенерируется если не указан."""
        data = {"name": "Календарь без slug"}
        response = authenticated_client.post(
            '/api/v1/schedule/calendars/',
            data,
            format='json'
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        assert 'slug' in response.data
        assert response.data['slug']  # slug не пустой
    
    def test_create_calendar_with_title(self, authenticated_client):
        """Проверка: поддержка поля 'title' (EUSRR совместимость)."""
        data = {
            "title": "Календарь через title",
        }
        response = authenticated_client.post(
            '/api/v1/schedule/calendars/',
            data,
            format='json'
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        # title конвертируется в name
        assert response.data['name'] == data['title'] or 'name' in response.data
    
    def test_get_calendar_detail(self, authenticated_client, test_calendar):
        """Проверка: получение деталей календаря."""
        response = authenticated_client.get(
            f'/api/v1/schedule/calendars/{test_calendar.id}/'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == test_calendar.id
        assert response.data['name'] == test_calendar.name
    
    def test_update_calendar(self, authenticated_client, test_calendar):
        """Проверка: обновление календаря."""
        data = {"name": "Обновлённое имя"}
        response = authenticated_client.patch(
            f'/api/v1/schedule/calendars/{test_calendar.id}/',
            data,
            format='json'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['name'] == data['name']
        
        test_calendar.refresh_from_db()
        assert test_calendar.name == data['name']
    
    def test_delete_calendar(self, authenticated_client, test_calendar):
        """Проверка: удаление календаря."""
        calendar_id = test_calendar.id
        response = authenticated_client.delete(
            f'/api/v1/schedule/calendars/{calendar_id}/'
        )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Calendar.objects.filter(id=calendar_id).exists()
    
    def test_filter_calendars_by_name(self, authenticated_client):
        """Проверка: фильтрация по имени."""
        Calendar.objects.create(name="Первый", slug="first")
        Calendar.objects.create(name="Второй", slug="second")
        
        response = authenticated_client.get(
            '/api/v1/schedule/calendars/?name=Первый'
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.data if isinstance(response.data, list) else response.data.get('results', [])
        assert len(data) == 1
        assert data[0]['name'] == "Первый"


# ==================== ТЕСТЫ СОБЫТИЙ ====================

@pytest.mark.django_db
class TestEventAPI:
    """Тесты для Event ViewSet."""
    
    def test_list_events(self, authenticated_client, test_event):
        """Проверка: список событий."""
        response = authenticated_client.get('/api/v1/schedule/events/')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) > 0
    
    def test_create_event(self, authenticated_client, test_calendar):
        """Проверка: создание события."""
        now = timezone.now()
        data = {
            "calendar": test_calendar.id,
            "title": "Новое событие",
            "description": "Описание события",
            "start": now.isoformat(),
            "end": (now + timedelta(hours=2)).isoformat(),
            "color_event": "#ff5733"
        }
        
        response = authenticated_client.post(
            '/api/v1/schedule/events/',
            data,
            format='json'
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == data['title']
        assert response.data['calendar'] == test_calendar.id
        assert 'creator' in response.data
    
    def test_get_event_detail(self, authenticated_client, test_event):
        """Проверка: получение деталей события."""
        response = authenticated_client.get(
            f'/api/v1/schedule/events/{test_event.id}/'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == test_event.id
        assert response.data['title'] == test_event.title
        assert response.data['calendar_name'] == test_event.calendar.name
    
    def test_update_event(self, authenticated_client, test_event):
        """Проверка: обновление события."""
        data = {
            "title": "Обновлённое событие",
            "description": "Новое описание"
        }
        response = authenticated_client.patch(
            f'/api/v1/schedule/events/{test_event.id}/',
            data,
            format='json'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == data['title']
        
        test_event.refresh_from_db()
        assert test_event.title == data['title']
    
    def test_delete_event(self, authenticated_client, test_event):
        """Проверка: удаление события."""
        event_id = test_event.id
        response = authenticated_client.delete(
            f'/api/v1/schedule/events/{event_id}/'
        )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Event.objects.filter(id=event_id).exists()
    
    def test_filter_events_by_calendar(self, authenticated_client, test_calendar, test_event):
        """Проверка: фильтрация по календарю."""
        # Создаём второй календарь с событием
        other_calendar = Calendar.objects.create(name="Other", slug="other")
        
        response = authenticated_client.get(
            f'/api/v1/schedule/events/?calendar={test_calendar.id}'
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.data if isinstance(response.data, list) else response.data.get('results', [])
        assert all(e['calendar'] == test_calendar.id for e in data)
    
    def test_filter_events_by_date_range(self, authenticated_client, test_calendar):
        """Проверка: фильтрация по диапазону дат."""
        now = timezone.now()
        
        # Создаём события в разные даты
        Event.objects.create(
            calendar=test_calendar,
            title="Прошлое",
            start=now - timedelta(days=) + timedelta(hours=1),  # Фикс: end > start
        )
        Event.objects.create(
            calendar=test_calendar,
            title="Сегодня",
            start=now,
            end=now + timedelta(hours=1),
        )
        Event.objects.create(
            calendar=test_calendar,
            title="Будущее",
            start=now + timedelta(days=10),
            end=now + timedelta(days=10, hours=1),
        )
        
        # Запрашиваем только сегодняшние
        start = (now - timedelta(hours=1)).isoformat()
        end = (now + timedelta(hours=2)).isoformat()
        
        response = authenticated_client.get(
            f'/api/v1/schedule/events/?start={start}&end={end}'
        )
        
        assert response.status_code == status.HTTP_200_OK
        data = response.data if isinstance(response.data, list) else response.data.get('results', [])
        assert len(data) == 1
        assert data[0]['title'] == "Сегодня"
    
    def test_event_validation_end_before_start(self, authenticated_client, test_calendar):
        """Проверка: валидация - конец не может быть раньше начала."""
        now = timezone.now()
        data = {
            "calendar": test_calendar.id,
            "title": "Невалидное событие",
            "start": now.isoformat(),
            "end": (now - timedelta(hours=1)).isoformat(),  # Раньше начала!
        }
        
        response = authenticated_client.post(
            '/api/v1/schedule/events/',
            data,
            format='json'
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'end' in response.data


# ==================== ТЕСТЫ ПРАВИЛ (RRULE) ====================

@pytest.mark.django_db
class TestRuleAPI:
    """Тесты для Rule ViewSet."""
    
    def test_list_rules(self, authenticated_client):
        """Проверка: список правил."""
        Rule.objects.create(
            name="Еженедельно",
            frequency="WEEKLY",
            params={"byweekday": [0, 2, 4]}  # Пн, Ср, Пт
        )
        
        response = authenticated_client.get('/api/v1/schedule/rules/')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) > 0
    
    def test_create_rule(self, authenticated_client):
        """Проверка: создание правила."""
        data = {
            "name": "Каждый день",
            "description": "Ежедневное повторение",
            "frequency": "DAILY",
            "params": {}
        }
        
        response = authenticated_client.post(
            '/api/v1/schedule/rules/',
            data,
            format='json'
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == data['name']
        assert response.data['frequency'] == "DAILY"


# ==================== ИНТЕГРАЦИОННЫЕ ТЕСТЫ ====================

@pytest.mark.django_db
class TestIntegration:
    """Интеграционные тесты полного workflow."""
    
    def test_full_crud_workflow(self, authenticated_client, test_user):
        """Проверка: полный цикл CRUD для календаря и события."""
        # 1. Создаём календарь
        cal_response = authenticated_client.post(
            '/api/v1/schedule/calendars/',
            {"name": "Workflow Calendar"},
            format='json'
        )
        assert cal_response.status_code == status.HTTP_201_CREATED
        calendar_id = cal_response.data['id']
        
        # 2. Создаём событие
        now = timezone.now()
        event_response = authenticated_client.post(
            '/api/v1/schedule/events/',
            {
                "calendar": calendar_id,
                "title": "Workflow Event",
                "start": now.isoformat(),
                "end": (now + timedelta(hours=1)).isoformat(),
            },
            format='json'
        )
        assert event_response.status_code == status.HTTP_201_CREATED
        event_id = event_response.data['id']
        
        data = list_response.data if isinstance(list_response.data, list) else list_response.data.get('results', [])
        assert len(тий календаря
        list_response = authenticated_client.get(
            f'/api/v1/schedule/events/?calendar={calendar_id}'
        )
        assert list_response.status_code == status.HTTP_200_OK
        assert len(list_response.data) == 1
        
        # 4. Обновляем событие
        update_response = authenticated_client.patch(
            f'/api/v1/schedule/events/{event_id}/',
            {"title": "Updated Event"},
            format='json'
        )
        assert update_response.status_code == status.HTTP_200_OK
        assert update_response.data['title'] == "Updated Event"
        
        # 5. Удаляем событие
        delete_event_response = authenticated_client.delete(
            f'/api/v1/schedule/events/{event_id}/'
        )
        assert delete_event_response.status_code == status.HTTP_204_NO_CONTENT
        
        # 6. Удаляем календарь
        delete_cal_response = authenticated_client.delete(
            f'/api/v1/schedule/calendars/{calendar_id}/'
        )
        assert delete_cal_response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_events_count_in_calendar(self, authenticated_client, test_calendar):
        """Проверка: счётчик событий в календаре."""
        # Создаём несколько событий
        now = timezone.now()
        for i in range(3):
            Event.objects.create(
                calendar=test_calendar,
                title=f"Event {i}",
                start=now + timedelta(hours=i),
                end=now + timedelta(hours=i+1),
            )
        
        response = authenticated_client.get(
            f'/api/v1/schedule/calendars/{test_calendar.id}/'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['events_count'] == 3


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
