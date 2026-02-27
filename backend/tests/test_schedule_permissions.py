# backend/tests/test_schedule_permissions.py
"""
Тесты для системы прав доступа календарей django-scheduler.
"""
import pytest
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from schedule.models import Calendar, CalendarRelation, Event, Rule

User = get_user_model()


@pytest.fixture
def api_client():
    """API клиент для тестов."""
    return APIClient()


@pytest.fixture
def user1(db):
    """Первый тестовый пользователь."""
    return User.objects.create_user(
        username='user1',
        email='user1@example.com',
        password='testpass123',
        first_name='User',
        last_name='One',
        phone_number='+79991234567'  # Правильное имя параметра
    )


@pytest.fixture
def user2(db):
    """Второй тестовый пользователь."""
    return User.objects.create_user(
        username='user2',
        email='user2@example.com',
        password='testpass123',
        first_name='User',
        last_name='Two',
        phone_number='+79991234568'
    )


@pytest.fixture
def user3(db):
    """Третий тестовый пользователь."""
    return User.objects.create_user(
        username='user3',
        email='user3@example.com',
        password='testpass123',
        first_name='User',
        last_name='Three',
        phone_number='+79991234569'
    )


@pytest.mark.django_db
class TestCalendarPermissions:
    """Тесты прав доступа к календарям."""
    
    def test_create_calendar_creates_owner_relation(self, api_client, user1):
        """При создании календаря автоматически создается owner relation."""
        api_client.force_authenticate(user=user1)
        
        response = api_client.post('/api/v1/schedule/calendars/', {
            'name': 'Test Calendar',
        })
        
        assert response.status_code == status.HTTP_201_CREATED
        calendar_id = response.data['id']
        
        # Проверяем, что создался CalendarRelation с owner
        ct = ContentType.objects.get_for_model(User)
        relation = CalendarRelation.objects.get(
            calendar_id=calendar_id,
            content_type=ct,
            object_id=user1.id
        )
        
        assert relation.distinction == 'owner'
        assert relation.inheritable is True
    
    def test_get_calendars_shows_only_accessible(self, api_client, user1, user2):
        """Пользователь видит только свои календари."""
        api_client.force_authenticate(user=user1)
        
        # user1 создает календарь
        response = api_client.post('/api/v1/schedule/calendars/', {
            'name': 'User1 Calendar',
        })
        assert response.status_code == status.HTTP_201_CREATED
        
        # user2 создает свой календарь
        api_client.force_authenticate(user=user2)
        response = api_client.post('/api/v1/schedule/calendars/', {
            'name': 'User2 Calendar',
        })
        assert response.status_code == status.HTTP_201_CREATED
        
        # user1 видит только свой календарь
        api_client.force_authenticate(user=user1)
        response = api_client.get('/api/v1/schedule/calendars/')
        assert response.status_code == status.HTTP_200_OK
        
        if isinstance(response.data, dict) and 'results' in response.data:
            calendars = response.data['results']
        else:
            calendars = response.data
        
        assert len(calendars) == 1
        assert calendars[0]['name'] == 'User1 Calendar'
    
    def test_add_participant_to_calendar(self, api_client, user1, user2):
        """Owner может добавить участника к календарю."""
        api_client.force_authenticate(user=user1)
        
        # Создаем календарь
        response = api_client.post('/api/v1/schedule/calendars/', {
            'name': 'Shared Calendar',
        })
        calendar_id = response.data['id']
        
        # Добавляем user2 как viewer
        response = api_client.post(
            f'/api/v1/schedule/calendars/{calendar_id}/add-participant/',
            {'user_id': user2.id, 'role': 'viewer'}
        )
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['user_info']['id'] == user2.id
        assert response.data['distinction'] == 'viewer'
        
        # Теперь user2 должен видеть календарь
        api_client.force_authenticate(user=user2)
        response = api_client.get('/api/v1/schedule/calendars/')
        
        if isinstance(response.data, dict) and 'results' in response.data:
            calendars = response.data['results']
        else:
            calendars = response.data
        
        assert len(calendars) == 1
        assert calendars[0]['id'] == calendar_id
    
    def test_non_owner_cannot_add_participant(self, api_client, user1, user2, user3):
        """Не-owner не может добавлять участников."""
        api_client.force_authenticate(user=user1)
        
        # user1 создает календарь
        response = api_client.post('/api/v1/schedule/calendars/', {
            'name': 'Test Calendar',
        })
        calendar_id = response.data['id']
        
        # Добавляем user2 как editor
        api_client.post(
            f'/api/v1/schedule/calendars/{calendar_id}/add-participant/',
            {'user_id': user2.id, 'role': 'editor'}
        )
        
        # user2 пытается добавить user3 - должно быть запрещено
        api_client.force_authenticate(user=user2)
        response = api_client.post(
            f'/api/v1/schedule/calendars/{calendar_id}/add-participant/',
            {'user_id': user3.id, 'role': 'viewer'}
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_remove_participant_from_calendar(self, api_client, user1, user2):
        """Owner может удалить участника из календаря."""
        api_client.force_authenticate(user=user1)
        
        # Создаем календарь и добавляем user2
        response = api_client.post('/api/v1/schedule/calendars/', {
            'name': 'Test Calendar',
        })
        calendar_id = response.data['id']
        
        api_client.post(
            f'/api/v1/schedule/calendars/{calendar_id}/add-participant/',
            {'user_id': user2.id, 'role': 'viewer'}
        )
        
        # Удаляем user2
        response = api_client.delete(
            f'/api/v1/schedule/calendars/{calendar_id}/remove-participant/{user2.id}/'
        )
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        # user2 больше не видит календарь
        api_client.force_authenticate(user=user2)
        response = api_client.get('/api/v1/schedule/calendars/')
        
        if isinstance(response.data, dict) and 'results' in response.data:
            calendars = response.data['results']
        else:
            calendars = response.data
        
        assert len(calendars) == 0
    
    def test_cannot_remove_owner(self, api_client, user1):
        """Нельзя удалить owner из календаря."""
        api_client.force_authenticate(user=user1)
        
        # Создаем календарь
        response = api_client.post('/api/v1/schedule/calendars/', {
            'name': 'Test Calendar',
        })
        calendar_id = response.data['id']
        
        # Пытаемся удалить себя (owner)
        response = api_client.delete(
            f'/api/v1/schedule/calendars/{calendar_id}/remove-participant/{user1.id}/'
        )
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_list_participants(self, api_client, user1, user2, user3):
        """Получение списка участников календаря."""
        api_client.force_authenticate(user=user1)
        
        # Создаем календарь
        response = api_client.post('/api/v1/schedule/calendars/', {
            'name': 'Test Calendar',
        })
        calendar_id = response.data['id']
        
        # Добавляем участников
        api_client.post(
            f'/api/v1/schedule/calendars/{calendar_id}/add-participant/',
            {'user_id': user2.id, 'role': 'editor'}
        )
        api_client.post(
            f'/api/v1/schedule/calendars/{calendar_id}/add-participant/',
            {'user_id': user3.id, 'role': 'viewer'}
        )
        
        # Получаем список участников
        response = api_client.get(
            f'/api/v1/schedule/calendars/{calendar_id}/participants/'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 3  # owner + 2 участника
        
        # Проверяем роли
        roles = {p['user_info']['id']: p['distinction'] for p in response.data}
        assert roles[user1.id] == 'owner'
        assert roles[user2.id] == 'editor'
        assert roles[user3.id] == 'viewer'


@pytest.mark.django_db
class TestRecurringEvents:
    """Тесты повторяющихся событий."""
    
    def test_create_rule(self, api_client, user1):
        """Создание правила повторения."""
        api_client.force_authenticate(user=user1)
        
        response = api_client.post('/api/v1/schedule/rules/', {
            'name': 'Weekly',
            'description': 'Every week on Monday',
            'frequency': 'WEEKLY',
            'params': 'byweekday:0'  # Monday
        })
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['frequency'] == 'WEEKLY'
        assert response.data['frequency_display'] == 'Еженедельно'  # Django локализация
    
    def test_create_recurring_event(self, api_client, user1):
        """Создание события с повторением."""
        api_client.force_authenticate(user=user1)
        
        # Создаем календарь
        cal_response = api_client.post('/api/v1/schedule/calendars/', {
            'name': 'Test Calendar',
        })
        calendar_id = cal_response.data['id']
        
        # Создаем правило
        rule_response = api_client.post('/api/v1/schedule/rules/', {
            'name': 'Daily',
            'description': 'Every day',
            'frequency': 'DAILY',
            'params': ''
        })
        rule_id = rule_response.data['id']
        
        # Создаем событие с правилом
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        start = timezone.now()
        end = start + timedelta(hours=1)
        end_recurring = start + timedelta(days=30)
        
        response = api_client.post('/api/v1/schedule/events/', {
            'title': 'Daily Meeting',
            'description': 'Team standup',
            'start': start.isoformat(),
            'end': end.isoformat(),
            'calendar': calendar_id,
            'rule': rule_id,
            'end_recurring_period': end_recurring.isoformat(),
        })
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['rule'] == rule_id
        assert response.data['end_recurring_period'] is not None
    
    def test_get_occurrences(self, api_client, user1):
        """Получение материализованных вхождений для recurring события."""
        api_client.force_authenticate(user=user1)
        
        # Создаем календарь
        cal_response = api_client.post('/api/v1/schedule/calendars/', {
            'name': 'Test Calendar',
        })
        calendar_id = cal_response.data['id']
        
        # Создаем правило - еженедельно
        rule_response = api_client.post('/api/v1/schedule/rules/', {
            'name': 'Weekly',
            'description': 'Every week',
            'frequency': 'WEEKLY',
            'params': ''
        })
        rule_id = rule_response.data['id']
        
        # Создаем событие
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        start = timezone.now()
        end = start + timedelta(hours=1)
        end_recurring = start + timedelta(weeks=4)
        
        api_client.post('/api/v1/schedule/events/', {
            'title': 'Weekly Meeting',
            'start': start.isoformat(),
            'end': end.isoformat(),
            'calendar': calendar_id,
            'rule': rule_id,
            'end_recurring_period': end_recurring.isoformat(),
        })
        
        # Получаем occurrences
        response = api_client.get(
            '/api/v1/schedule/events/occurrences/',
            {
                'calendar': calendar_id,
                'start': start.isoformat(),
                'end': (start + timedelta(weeks=5)).isoformat(),
            }
        )
        
        assert response.status_code == status.HTTP_200_OK
        # Должно быть ~4 вхождения (еженедельно в течение 4 недель)
        assert len(response.data) >= 4


@pytest.mark.django_db
class TestiCalendarExport:
    """Тесты экспорта в iCalendar формат."""
    
    def test_export_calendar_to_ics(self, api_client, user1):
        """Экспорт календаря в .ics файл."""
        api_client.force_authenticate(user=user1)
        
        # Создаем календарь
        cal_response = api_client.post('/api/v1/schedule/calendars/', {
            'name': 'Test Calendar',
        })
        calendar_id = cal_response.data['id']
        
        # Добавляем событие
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        start = timezone.now()
        end = start + timedelta(hours=2)
        
        api_client.post('/api/v1/schedule/events/', {
            'title': 'Test Event',
            'description': 'Test Description',
            'start': start.isoformat(),
            'end': end.isoformat(),
            'calendar': calendar_id,
        })
        
        # Экспортируем календарь
        response = api_client.get(
            f'/api/v1/schedule/calendars/{calendar_id}/export-ical/'
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response['Content-Type'] == 'text/calendar'
        assert 'Content-Disposition' in response
        assert '.ics' in response['Content-Disposition']
        
        # Проверяем содержимое
        content = response.content.decode('utf-8')
        assert 'BEGIN:VCALENDAR' in content
        assert 'BEGIN:VEVENT' in content
        assert 'Test Event' in content
        assert 'END:VEVENT' in content
        assert 'END:VCALENDAR' in content


@pytest.mark.django_db
class TestEventRelations:
    """Тесты участников событий."""
    
    def test_add_participant_to_event(self, api_client, user1, user2):
        """Добавление участника к событию."""
        api_client.force_authenticate(user=user1)
        
        # Создаем календарь
        cal_response = api_client.post('/api/v1/schedule/calendars/', {
            'name': 'Test Calendar',
        })
        calendar_id = cal_response.data['id']
        
        # Создаем событие
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        start = timezone.now()
        end = start + timedelta(hours=1)
        
        event_response = api_client.post('/api/v1/schedule/events/', {
            'title': 'Meeting',
            'start': start.isoformat(),
            'end': end.isoformat(),
            'calendar': calendar_id,
        })
        event_id = event_response.data['id']
        
        # Добавляем user2 как участника
        ct = ContentType.objects.get_for_model(User)
        response = api_client.post('/api/v1/schedule/relations/', {
            'event': event_id,
            'content_type': ct.id,
            'object_id': user2.id,
            'distinction': 'attendee',
        })
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['event'] == event_id
    
    def test_list_event_participants(self, api_client, user1, user2, user3):
        """Получение списка участников события."""
        api_client.force_authenticate(user=user1)
        
        # Создаем календарь и событие
        cal_response = api_client.post('/api/v1/schedule/calendars/', {
            'name': 'Test Calendar',
        })
        calendar_id = cal_response.data['id']
        
        from datetime import datetime, timedelta
        from django.utils import timezone
        
        start = timezone.now()
        end = start + timedelta(hours=1)
        
        event_response = api_client.post('/api/v1/schedule/events/', {
            'title': 'Team Meeting',
            'start': start.isoformat(),
            'end': end.isoformat(),
            'calendar': calendar_id,
        })
        event_id = event_response.data['id']
        
        # Добавляем участников
        ct = ContentType.objects.get_for_model(User)
        api_client.post('/api/v1/schedule/relations/', {
            'event': event_id,
            'content_type': ct.id,
            'object_id': user2.id,
            'distinction': 'attendee',
        })
        api_client.post('/api/v1/schedule/relations/', {
            'event': event_id,
            'content_type': ct.id,
            'object_id': user3.id,
            'distinction': 'attendee',
        })
        
        # Получаем список участников
        response = api_client.get(
            '/api/v1/schedule/relations/',
            {'event': event_id}
        )
        
        assert response.status_code == status.HTTP_200_OK
        
        if isinstance(response.data, dict) and 'results' in response.data:
            relations = response.data['results']
        else:
            relations = response.data
        
        assert len(relations) == 2
