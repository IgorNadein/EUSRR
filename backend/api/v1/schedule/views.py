# backend/api/v1/schedule/views.py
"""
ViewSets для django-scheduler (чистый, проверенный код).
Параллельно работают со старым calendar_app.
"""
from rest_framework import viewsets, status
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.renderers import JSONRenderer

from schedule.models import Calendar, Event, Rule, Occurrence, EventRelation
from schedule.periods import Period

from datetime import datetime
from django.utils.dateparse import parse_datetime

from .serializers import (
    CalendarSerializer,
    EventSerializer,
    EventListSerializer,
    RuleSerializer,
    OccurrenceSerializer,
    EventRelationSerializer,
)


class ScheduleCalendarViewSet(viewsets.ModelViewSet):
    """CRUD для django-scheduler Calendar.
    
    Endpoints:
    - GET /api/v1/schedule/calendars/ - список
    - POST /api/v1/schedule/calendars/ - создать
    - GET /api/v1/schedule/calendars/{id}/ - детали
    - PUT/PATCH /api/v1/schedule/calendars/{id}/ - обновить
    - DELETE /api/v1/schedule/calendars/{id}/ - удалить
    """
    
    queryset = Calendar.objects.all()
    serializer_class = CalendarSerializer
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]
    
    def get_queryset(self):
        """Фильтрация календарей."""
        qs = super().get_queryset()
        
        # Фильтр по имени
        name = self.request.query_params.get('name')
        if name:
            qs = qs.filter(name__icontains=name)
        
        return qs.order_by('name')


class ScheduleEventViewSet(viewsets.ModelViewSet):
    """CRUD для django-scheduler Event.
    
    Endpoints:
    - GET /api/v1/schedule/events/ - список
    - GET /api/v1/schedule/events/?calendar=1 - события календаря
    - GET /api/v1/schedule/events/?start=2026-02-01&end=2026-03-01 - в диапазоне
    - POST /api/v1/schedule/events/ - создать
    - GET /api/v1/schedule/events/{id}/ - детали
    - PUT/PATCH /api/v1/schedule/events/{id}/ - обновить
    - DELETE /api/v1/schedule/events/{id}/ - удалить
    """
    
    queryset = Event.objects.select_related('calendar', 'rule', 'creator')
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]
    
    def get_serializer_class(self):
        """Выбор сериализатора."""
        if self.action == 'list':
            return EventListSerializer
        return EventSerializer
    
    def get_queryset(self):
        """Фильтрация событий."""
        qs = super().get_queryset()
        
        # Фильтр по календарю
        calendar_id = self.request.query_params.get('calendar')
        if calendar_id:
            qs = qs.filter(calendar_id=calendar_id)
        
        # Фильтр по диапазону дат
        start_str = self.request.query_params.get('start')
        end_str = self.request.query_params.get('end')
        
        if start_str and end_str:
            start_dt = parse_datetime(start_str)
            end_dt = parse_datetime(end_str)
            
            if start_dt and end_dt:
                # События, которые попадают в диапазон
                qs = qs.filter(
                    start__lte=end_dt,
                    end__gte=start_dt
                )
        
        return qs.order_by('start')
    
    def perform_create(self, serializer):
        """Установка creator при создании."""
        serializer.save(creator=self.request.user)
    
    @action(detail=False, methods=['get'], url_path='occurrences')
    def occurrences(self, request):
        """Получить материализованные вхождения в диапазоне.
        
        Query params:
        - calendar: ID календаря (обязательно)
        - start: начало диапазона (ISO 8601)
        - end: конец диапазона (ISO 8601)
        
        Возвращает все вхождения recurring событий + обычные события.
        """
        calendar_id = request.query_params.get('calendar')
        start_str = request.query_params.get('start')
        end_str = request.query_params.get('end')
        
        if not all([calendar_id, start_str, end_str]):
            return Response(
                {'detail': 'Требуются параметры: calendar, start, end'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            calendar = Calendar.objects.get(id=calendar_id)
        except Calendar.DoesNotExist:
            return Response(
                {'detail': 'Календарь не найден'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        start_dt = parse_datetime(start_str)
        end_dt = parse_datetime(end_str)
        
        if not start_dt or not end_dt:
            return Response(
                {'detail': 'Некорректный формат дат (используйте ISO 8601)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Используем schedule.periods.Period для получения вхождений
        events = calendar.event_set.all()
        period = Period(events, start_dt, end_dt)
        
        # Результат
        occurrences = []
        for occurrence in period.get_occurrences():
            occurrences.append({
                'id': occurrence.event.id,
                'title': occurrence.title or occurrence.event.title,
                'start': occurrence.start.isoformat(),
                'end': occurrence.end.isoformat(),
                'color_event': occurrence.event.color_event,
                'event_id': occurrence.event.id,
                'is_recurring': occurrence.event.rule_id is not None,
            })
        
        return Response(occurrences)


class ScheduleRuleViewSet(viewsets.ModelViewSet):
    """CRUD для django-scheduler Rule (rrule RFC 5545).
    
    Endpoints:
    - GET /api/v1/schedule/rules/ - список правил
    - POST /api/v1/schedule/rules/ - создать правило
    - GET /api/v1/schedule/rules/{id}/ - детали
    """
    
    queryset = Rule.objects.all()
    serializer_class = RuleSerializer
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]


class ScheduleOccurrenceViewSet(viewsets.ReadOnlyModelViewSet):
    """Просмотр Occurrence (материализованных вхождений).
    
    Read-only ViewSet (Occurrence создаются автоматически).
    """
    
    queryset = Occurrence.objects.select_related('event', 'event__calendar')
    serializer_class = OccurrenceSerializer
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]
    
    def get_queryset(self):
        """Фильтрация по событию."""
        qs = super().get_queryset()
        
        event_id = self.request.query_params.get('event')
        if event_id:
            qs = qs.filter(event_id=event_id)
        
        return qs.order_by('start')


class ScheduleEventRelationViewSet(viewsets.ModelViewSet):
    """CRUD для EventRelation (участники встреч).
    
    Endpoints:
    - GET /api/v1/schedule/relations/ - список участников
    - GET /api/v1/schedule/relations/?event=1 - участники события
    - POST /api/v1/schedule/relations/ - добавить участника
    - DELETE /api/v1/schedule/relations/{id}/ - удалить участника
    """
    
    queryset = EventRelation.objects.select_related('event', 'content_type')
    serializer_class = EventRelationSerializer
    permission_classes = [IsAuthenticated]
    renderer_classes = [JSONRenderer]
    
    def get_queryset(self):
        """Фильтрация по событию."""
        qs = super().get_queryset()
        
        event_id = self.request.query_params.get('event')
        if event_id:
            qs = qs.filter(event_id=event_id)
        
        return qs
