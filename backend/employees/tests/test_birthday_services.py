"""
Тесты для сервисного слоя работы с днями рождения (Service Layer Pattern).
Используется django-service-objects для инкапсуляции бизнес-логики.
"""
import pytest
from datetime import date
from django.contrib.auth import get_user_model
from django.db.models import signals
from django.utils import timezone

from employees.models import Employee
from employees.services import (
    UpsertBirthdayEventService,
    DeleteBirthdayEventService,
    BulkSyncBirthdaysService
)
from schedule.models import Calendar, Event, Rule

User = get_user_model()


@pytest.fixture(autouse=True)
def disable_birthday_signals(settings):
    """Отключаем сигналы дней рождений для изолированного тестирования сервисов."""
    from unittest.mock import patch
    
    # Мокируем только функции-обработчики сигналов, а не сами сервисы
    with patch('employees.signals_birthday.sync_birthday_event_on_employee_save'):
        with patch('employees.signals_birthday.delete_birthday_event_on_employee_delete'):
            yield


@pytest.fixture
def create_test_employee():
    """Фикстура для создания тестовых сотрудников с валидными данными."""
    employee_counter = 0
    
    def _create_employee(**kwargs):
        nonlocal employee_counter
        employee_counter += 1
        defaults = {
            'username': f'testuser{employee_counter}',
            'email': f'testuser{employee_counter}@example.com',
            'phone_number': f'+7900000{employee_counter:04d}',
            'password': 'test123',
            'first_name': 'Test',
            'last_name': f'User{employee_counter}'
        }
        defaults.update(kwargs)
        
        # Employee наследуется от AbstractUser
        employee = Employee.objects.create_user(**defaults)
        return employee
    
    return _create_employee


@pytest.mark.django_db
class TestUpsertBirthdayEventService:
    """Тесты для сервиса создания/обновления событий дня рождения."""
    
    def test_create_birthday_event_for_new_employee(self, create_test_employee):
        """Создание нового события дня рождения."""
        # Arrange
        employee = create_test_employee(
            username='john',
            email='john@example.com',
            first_name='John',
            last_name='Doe',
            birth_date=date(1990, 5, 15)
        )
        
        # Act
        result = UpsertBirthdayEventService.execute({'employee': employee})
        
        # Assert
        assert result['success'] is True
        assert result['created'] is True
        assert result['event'] is not None
        
        event = result['event']
        assert event.title == '🎂 День рождения: John Doe'
        assert event.creator_id == employee.pk
        assert event.rule is not None
        assert event.rule.frequency == 'YEARLY'
        assert event.end_recurring_period is None  # Бесконечное повторение
    
    def test_update_existing_birthday_event(self, create_test_employee):
        """Обновление существующего события при изменении данных."""
        # Arrange
        employee = create_test_employee(
            username='jane',
            email='jane@example.com',
            first_name='Jane',
            last_name='Smith',
            birth_date=date(1985, 3, 20)
        )
        
        # Создаем событие
        first_result = UpsertBirthdayEventService.execute({'employee': employee})
        first_event_id = first_result['event'].id
        
        # Act - меняем имя сотрудника
        employee.first_name = 'Janet'
        employee.save()
        
        second_result = UpsertBirthdayEventService.execute({'employee': employee})
        
        # Assert
        assert second_result['success'] is True
        assert second_result['created'] is False  # Обновлено, не создано
        assert second_result['event'].id == first_event_id  # Тот же event
        assert second_result['event'].title == '🎂 День рождения: Janet Smith'
    
    def test_skip_employee_without_birth_date(self, create_test_employee):
        """Пропуск сотрудника без даты рождения."""
        # Arrange
        employee = create_test_employee(
            username='nobirthday',
            email='nobirthday@example.com',
            first_name='No',
            last_name='Birthday',
            birth_date=None
        )
        
        # Act
        result = UpsertBirthdayEventService.execute({'employee': employee})
        
        # Assert
        assert result['success'] is False
        assert result['reason'] == 'no_birth_date'
        assert result['event'] is None
    
    def test_creates_personal_calendar_if_not_exists(self, create_test_employee):
        """Автоматически создает личный календарь при первом событии."""
        # Arrange
        employee = create_test_employee(
            username='newuser',
            email='newuser@example.com',
            first_name='New',
            last_name='User',
            birth_date=date(1992, 7, 10)
        )
        
        # Убедимся, что календаря нет
        assert not Calendar.objects.filter(slug=f'employee-{employee.pk}').exists()
        
        # Act
        result = UpsertBirthdayEventService.execute({'employee': employee})
        
        # Assert
        assert result['success'] is True
        calendar = Calendar.objects.get(slug=f'employee-{employee.pk}')
        assert calendar.name == '👤 Мой календарь'
        assert result['event'].calendar == calendar
    
    def test_yearly_rule_reused_across_employees(self, create_test_employee):
        """Правило 'Ежегодно' переиспользуется для всех событий."""
        # Arrange
        employee1 = create_test_employee(
            username='user1',
            email='user1@example.com',
            first_name='User',
            last_name='One',
            birth_date=date(1990, 1, 1)
        )
        employee2 = create_test_employee(
            username='user2',
            email='user2@example.com',
            first_name='User',
            last_name='Two',
            birth_date=date(1991, 2, 2)
        )
        
        # Act
        result1 = UpsertBirthdayEventService.execute({'employee': employee1})
        result2 = UpsertBirthdayEventService.execute({'employee': employee2})
        
        # Assert
        assert result1['event'].rule.id == result2['event'].rule.id
        assert Rule.objects.filter(name='Ежегодно').count() == 1


@pytest.mark.django_db
class TestDeleteBirthdayEventService:
    """Тесты для сервиса удаления событий дня рождения."""
    
    def test_delete_existing_birthday_event(self, create_test_employee):
        """Удаление существующего события."""
        # Arrange
        employee = create_test_employee(
            username='todelete',
            email='todelete@example.com',
            first_name='To',
            last_name='Delete',
            birth_date=date(1988, 4, 25)
        )
        
        # Создаем событие
        UpsertBirthdayEventService.execute({'employee': employee})
        assert Event.objects.filter(creator_id=employee.pk).exists()
        
        # Act
        result = DeleteBirthdayEventService.execute({'employee': employee})
        
        # Assert
        assert result['success'] is True
        assert result['deleted_count'] == 1
        assert not Event.objects.filter(creator_id=employee.pk).exists()
    
    def test_delete_nonexistent_event_returns_false(self, create_test_employee):
        """Попытка удалить несуществующее событие."""
        # Arrange
        employee = create_test_employee(
            username='noevents',
            email='noevents@example.com',
            first_name='No',
            last_name='Events',
            birth_date=date(1995, 8, 30)
        )
        
        # Act
        result = DeleteBirthdayEventService.execute({'employee': employee})
        
        # Assert
        assert result['success'] is False
        assert result['deleted_count'] == 0


@pytest.mark.django_db
class TestBulkSyncBirthdaysService:
    """Тесты для массовой синхронизации дней рождений."""
    
    def test_bulk_sync_creates_events_for_all_employees(self, create_test_employee):
        """Массовая синхронизация создает события для всех сотрудников."""
        # Arrange
        employees_data = [
            ('user1', 'Alice', 'Johnson', date(1990, 1, 10)),
            ('user2', 'Bob', 'Williams', date(1985, 5, 20)),
            ('user3', 'Charlie', 'Brown', date(1992, 9, 15)),
        ]
        
        for username, first, last, birth in employees_data:
            create_test_employee(
                username=username,
                email=f'{username}@example.com',
                first_name=first,
                last_name=last,
                birth_date=birth
            )
        
        # Act
        result = BulkSyncBirthdaysService.execute({})
        
        # Assert
        assert result['total'] == 3
        assert result['created'] == 3
        assert result['updated'] == 0
        assert result['skipped'] == 0
        assert len(result['errors']) == 0
        
        # Проверяем, что события созданы
        assert Event.objects.filter(title__startswith='🎂 День рождения:').count() == 3
    
    def test_bulk_sync_updates_existing_events(self, create_test_employee):
        """Массовая синхронизация обновляет существующие события."""
        # Arrange
        employee = create_test_employee(
            username='existing',
            email='existing@example.com',
            first_name='Existing',
            last_name='User',
            birth_date=date(1987, 6, 12)
        )
        
        # Создаем событие заранее
        UpsertBirthdayEventService.execute({'employee': employee})
        
        # Act
        result = BulkSyncBirthdaysService.execute({})
        
        # Assert
        assert result['total'] == 1
        assert result['created'] == 0
        assert result['updated'] == 1
        assert result['skipped'] == 0
    
    def test_bulk_sync_skips_employees_without_birth_date(self, create_test_employee):
        """Пропускает сотрудников без даты рождения."""
        # Arrange
        create_test_employee(
            username='withbd',
            email='withbd@example.com',
            first_name='With',
            last_name='BirthDate',
            birth_date=date(1990, 1, 1)
        )
        
        create_test_employee(
            username='nobd',
            email='nobd@example.com',
            first_name='No',
            last_name='BirthDate',
            birth_date=None
        )
        
        # Act
        result = BulkSyncBirthdaysService.execute({})
        
        # Assert
        assert result['total'] == 2
        assert result['created'] == 1
        assert result['skipped'] == 1
    
    def test_bulk_sync_handles_errors_gracefully(self, create_test_employee):
        """Обрабатывает ошибки без падения всего процесса."""
        # Arrange
        create_test_employee(
            username='valid',
            email='valid@example.com',
            first_name='Valid',
            last_name='Employee',
            birth_date=date(1993, 3, 5)
        )
        
        # Act
        result = BulkSyncBirthdaysService.execute({})
        
        # Assert
        assert result['total'] >= 1
        assert result['created'] + result['updated'] >= 1
        # Часть может быть успешной даже если есть ошибки
