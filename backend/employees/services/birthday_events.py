"""
Сервисы для работы с событиями дней рождений сотрудников.
Использует паттерн Service Layer через django-service-objects.
"""
from datetime import datetime, timedelta
from typing import Optional

from django.db import models as django_models
from django.utils import timezone
from service_objects.services import Service
from service_objects.fields import ModelField

from employees.models import Employee
from schedule.models import Calendar, Event, Rule

# Константы
BIRTHDAY_COLOR = "#FFC107"  # Жёлтый/золотой цвет для дней рождения


class UpsertBirthdayEventService(Service):
    """
    Сервис создания/обновления события дня рождения сотрудника.
    
    Использует паттерн External ID: creator_id + title для идентификации.
    Создает ежегодное повторяющееся событие в личном календаре сотрудника.
    """
    employee = ModelField(Employee)
    
    def process(self):
        employee = self.cleaned_data['employee']
        
        # Проверяем наличие даты рождения
        if not employee.birth_date:
            return {
                'success': False,
                'reason': 'no_birth_date',
                'event': None
            }
        
        # Получаем личный календарь сотрудника
        personal_calendar = self._get_or_create_personal_calendar(employee)
        
        # Создаем или обновляем событие
        event, created = self._upsert_birthday_event(employee, personal_calendar)
        
        return {
            'success': True,
            'event': event,
            'created': created
        }
    
    def _get_or_create_personal_calendar(self, employee: Employee) -> Calendar:
        """Получить или создать личный календарь сотрудника."""
        calendar, created = Calendar.objects.get_or_create(
            slug=f'personal-{employee.pk}',
            defaults={
                'name': '👤 Мой календарь'
            }
        )
        
        # Убедиться что есть связь owner
        if created:
            from schedule.models import CalendarRelation
            from django.contrib.contenttypes.models import ContentType
            
            ct = ContentType.objects.get_for_model(Employee)
            CalendarRelation.objects.get_or_create(
                calendar=calendar,
                content_type=ct,
                object_id=employee.pk,
                defaults={
                    'distinction': 'owner',
                    'inheritable': True
                }
            )
        
        return calendar
    
    def _upsert_birthday_event(self, employee: Employee, calendar: Calendar) -> tuple[Event, bool]:
        """Создать или обновить событие дня рождения. Возвращает (event, created)."""
        title = f"🎂 День рождения: {str(employee)}"
        
        # Ищем существующее событие по creator + начало title (паттерн External ID)
        # Используем startswith чтобы обновлять даже если имя сотрудника изменилось
        existing_event = Event.objects.filter(
            creator_id=employee.pk,
            title__startswith='🎂 День рождения:',
            calendar=calendar
        ).first()
        
        # Создаем правило для ежегодного повторения
        rule = self._get_or_create_yearly_rule()
        
        # Вычисляем даты для текущего года
        current_year = timezone.now().year
        start_date = datetime(
            year=current_year,
            month=employee.birth_date.month,
            day=employee.birth_date.day,
            hour=0,
            minute=0
        )
        end_date = start_date + timedelta(days=1)
        
        # Делаем aware если USE_TZ=True
        if timezone.is_naive(start_date):
            start_date = timezone.make_aware(start_date)
            end_date = timezone.make_aware(end_date)
        
        if existing_event:
            # Обновляем существующее событие
            existing_event.title = title
            existing_event.start = start_date
            existing_event.end = end_date
            existing_event.rule = rule
            existing_event.end_recurring_period = None  # Бесконечное повторение
            existing_event.color_event = BIRTHDAY_COLOR
            existing_event.save()
            return existing_event, False  # Обновлено
        else:
            # Создаем новое событие
            event = Event.objects.create(
                title=title,
                start=start_date,
                end=end_date,
                calendar=calendar,
                creator_id=employee.pk,
                rule=rule,
                end_recurring_period=None,  # Бесконечное повторение
                color_event=BIRTHDAY_COLOR,
                description=f"Автоматическое событие: день рождения {str(employee)}"
            )
            return event, True  # Создано
    
    def _get_or_create_yearly_rule(self) -> Rule:
        """Получить или создать правило для ежегодного повторения."""
        rule, created = Rule.objects.get_or_create(
            name='Ежегодно',
            defaults={
                'description': 'Повторять каждый год',
                'frequency': 'YEARLY',
                'params': ''  # Дефолтные параметры
            }
        )
        return rule


class DeleteBirthdayEventService(Service):
    """
    Сервис удаления события дня рождения сотрудника.
    
    Использует паттерн External ID для поиска события.
    """
    employee = ModelField(Employee)
    
    def process(self):
        employee = self.cleaned_data['employee']
        
        title = f"🎂 День рождения: {str(employee)}"
        
        # Ищем событие по creator + паттерн title
        deleted_count, _ = Event.objects.filter(
            creator_id=employee.pk,
            title__startswith='🎂 День рождения:'
        ).delete()
        
        return {
            'success': deleted_count > 0,
            'deleted_count': deleted_count
        }


class BulkSyncBirthdaysService(Service):
    """
    Сервис массовой синхронизации дней рождений всех сотрудников.
    
    Используется для миграции и периодической синхронизации.
    """
    
    def process(self):
        employees = Employee.objects.filter(
            birth_date__isnull=False
        ).select_related()
        
        results = {
            'total': 0,
            'created': 0,
            'updated': 0,
            'skipped': 0,
            'errors': []
        }
        
        for employee in employees:
            results['total'] += 1
            try:
                result = UpsertBirthdayEventService.execute({
                    'employee': employee
                })
                
                if result['success']:
                    if result.get('created'):
                        results['created'] += 1
                    else:
                        results['updated'] += 1
                else:
                    results['skipped'] += 1
            except Exception as e:
                results['errors'].append({
                    'employee_id': employee.pk,
                    'error': str(e)
                })
        
        return results
