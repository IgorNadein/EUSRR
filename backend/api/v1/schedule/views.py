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
from django.http import HttpResponse
from django.contrib.contenttypes.models import ContentType
from django.db.models import Q

from schedule.models import Calendar, Event, Rule, Occurrence, EventRelation, CalendarRelation
from schedule.periods import Period
from schedule.feeds import CalendarICalendar  # Правильный импорт

from datetime import datetime
from django.utils.dateparse import parse_datetime

from .serializers import (
    CalendarSerializer,
    CalendarRelationSerializer,
    EventSerializer,
    EventListSerializer,
    RuleSerializer,
    OccurrenceSerializer,
    EventRelationSerializer,
)
from .permissions import IsOwnerOfCalendar, CanEditCalendar


class ScheduleCalendarViewSet(viewsets.ModelViewSet):
    """CRUD для django-scheduler Calendar с системой прав доступа.
    
    Endpoints:
    - GET /api/v1/schedule/calendars/ - список календарей (только доступные пользователю)
    - POST /api/v1/schedule/calendars/ - создать (автоматически owner)
    - GET /api/v1/schedule/calendars/{id}/ - детали
    - PUT/PATCH /api/v1/schedule/calendars/{id}/ - обновить
    - DELETE /api/v1/schedule/calendars/{id}/ - удалить
    
    Дополнительные actions:
    - POST /api/v1/schedule/calendars/{id}/add_participant/ - добавить участника
    - DELETE /api/v1/schedule/calendars/{id}/remove_participant/ - удалить участника
    - GET /api/v1/schedule/calendars/{id}/participants/ - список участников
    - GET /api/v1/schedule/calendars/{id}/export_ical/ - экспорт в .ics
    """
    
    queryset = Calendar.objects.all()
    serializer_class = CalendarSerializer
    permission_classes = [IsAuthenticated, IsOwnerOfCalendar]
    renderer_classes = [JSONRenderer]
    pagination_class = None  # Отключаем пагинацию - календарей немного, нужны все
    
    def get_queryset(self):
        """Фильтрация календарей по доступу пользователя."""
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        qs = super().get_queryset()
        user = self.request.user
        
        # Админы видят все
        if user.is_staff or user.is_superuser:
            return qs.order_by('name')
        
        # Остальные видят только календари, где они участники
        ct = ContentType.objects.get_for_model(User)
        calendar_ids = CalendarRelation.objects.filter(
            content_type=ct,
            object_id=user.id
        ).values_list('calendar_id', flat=True)
        
        qs = qs.filter(id__in=calendar_ids)
        
        # Фильтр по имени
        name = self.request.query_params.get('name')
        if name:
            qs = qs.filter(name__icontains=name)
        
        return qs.order_by('name')
    
    def perform_create(self, serializer):
        """При создании календаря автоматически добавляем creator как owner."""
        calendar = serializer.save()
        # Создаем CalendarRelation с distinction='owner'
        calendar.create_relation(self.request.user, distinction='owner', inheritable=True)
    
    @action(detail=True, methods=['post'], url_path='add-participant')
    def add_participant(self, request, pk=None):
        """Добавить участника к календарю.
        
        Body:
        {
            "user_id": 123,
            "role": "viewer"  # owner, editor, viewer
        }
        """
        calendar = self.get_object()
        
        # Проверка прав (только owner может добавлять участников)
        if not self._is_owner(calendar, request.user):
            return Response(
                {'detail': 'Только владелец может добавлять участников'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        serializer = CalendarRelationSerializer(data={
            'calendar': calendar.id,
            'user_id': request.data.get('user_id'),
            'distinction': request.data.get('role', 'viewer'),
            'inheritable': True
        })
        
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    @action(detail=True, methods=['delete'], url_path='remove-participant/(?P<user_id>[0-9]+)')
    def remove_participant(self, request, pk=None, user_id=None):
        """Удалить участника из календаря."""
        calendar = self.get_object()
        
        # Проверка прав
        if not self._is_owner(calendar, request.user):
            return Response(
                {'detail': 'Только владелец может удалять участников'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        ct = ContentType.objects.get_for_model(User)
        
        # Нельзя удалить owner
        relation = CalendarRelation.objects.filter(
            calendar=calendar,
            content_type=ct,
            object_id=user_id
        ).first()
        
        if not relation:
            return Response(
                {'detail': 'Участник не найден'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        if relation.distinction == 'owner':
            return Response(
                {'detail': 'Нельзя удалить владельца календаря'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        relation.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
    
    @action(detail=True, methods=['get'])
    def participants(self, request, pk=None):
        """Получить список всех участников календаря."""
        calendar = self.get_object()
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        ct = ContentType.objects.get_for_model(User)
        
        relations = CalendarRelation.objects.filter(
            calendar=calendar,
            content_type=ct
        )
        
        serializer = CalendarRelationSerializer(relations, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'], url_path='export-ical')
    def export_ical(self, request, pk=None):
        """Экспорт календаря в формат iCalendar (.ics).
        
        Использует встроенный CalendarICalendar из django-scheduler.
        """
        calendar = self.get_object()
        
        # Создаем feed для экспорта
        feed = CalendarICalendar()
        response = feed(request, pk)
        
        # Устанавливает имя файла
        response['Content-Disposition'] = f'attachment; filename="{calendar.slug}.ics"'
        
        return response
    
    @action(detail=True, methods=['post'], url_path='import-ical')
    def import_ical(self, request, pk=None):
        """Импорт событий из файла iCalendar (.ics) в календарь.
        
        Ожидает файл в request.FILES['file'].
        """
        from icalendar import Calendar as ICalendar
        from django.utils import timezone
        
        calendar = self.get_object()
        
        # Проверка, что пользователь - владелец
        if not self._is_owner(calendar, request.user):
            return Response(
                {'error': 'Только владелец может импортировать события в календарь'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Проверка наличия файла
        if 'file' not in request.FILES:
            return Response(
                {'error': 'Файл не найден. Отправьте файл с ключом "file"'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        ics_file = request.FILES['file']
        
        try:
            # Парсим iCalendar файл
            ical = ICalendar.from_ical(ics_file.read())
            
            imported_count = 0
            skipped_count = 0
            errors = []
            
            # Проходим по всем событиям в файле
            for component in ical.walk():
                if component.name == "VEVENT":
                    try:
                        # Извлекаем данные события
                        summary = str(component.get('summary', ''))
                        description = str(component.get('description', ''))
                        dtstart = component.get('dtstart')
                        dtend = component.get('dtend')
                        
                        if not dtstart:
                            skipped_count += 1
                            continue
                        
                        # Преобразуем даты
                        start_dt = dtstart.dt
                        if not timezone.is_aware(start_dt):
                            start_dt = timezone.make_aware(start_dt)
                        
                        if dtend:
                            end_dt = dtend.dt
                            if not timezone.is_aware(end_dt):
                                end_dt = timezone.make_aware(end_dt)
                        else:
                            # Если нет времени окончания, делаем событие длиной 1 час
                            from datetime import timedelta
                            end_dt = start_dt + timedelta(hours=1)
                        
                        # Создаем событие
                        Event.objects.create(
                            calendar=calendar,
                            title=summary or 'Без названия',
                            description=description,
                            start=start_dt,
                            end=end_dt,
                            creator=request.user
                        )
                        imported_count += 1
                        
                    except Exception as e:
                        errors.append(f"Ошибка импорта события '{summary}': {str(e)}")
                        skipped_count += 1
            
            return Response({
                'success': True,
                'imported': imported_count,
                'skipped': skipped_count,
                'errors': errors if errors else None
            })
            
        except Exception as e:
            return Response(
                {'error': f'Ошибка парсинга файла: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def _is_owner(self, calendar, user):
        """Проверка, является ли пользователь владельцем календаря."""
        if user.is_staff or user.is_superuser:
            return True
        
        from django.contrib.auth import get_user_model
        User = get_user_model()
        ct = ContentType.objects.get_for_model(User)
        
        return CalendarRelation.objects.filter(
            calendar=calendar,
            content_type=ct,
            object_id=user.id,
            distinction='owner'
        ).exists()


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
    permission_classes = [IsAuthenticated, CanEditCalendar]
    renderer_classes = [JSONRenderer]
    
    def get_serializer_class(self):
        """Выбор сериализатора."""
        if self.action == 'list':
            return EventListSerializer
        return EventSerializer
    
    def get_queryset(self):
        """Фильтрация событий.
        
        Пользователь видит события из:
        1. Календарей, где он участник (CalendarRelation)
        2. Событий, где он участник (EventRelation)
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        qs = super().get_queryset()
        user = self.request.user
        
        # Админы видят все события
        if not (user.is_staff or user.is_superuser):
            ct = ContentType.objects.get_for_model(User)
            
            # ID календарей где пользователь участник
            accessible_calendar_ids = CalendarRelation.objects.filter(
                content_type=ct,
                object_id=user.id
            ).values_list('calendar_id', flat=True)
            
            # ID событий где пользователь участник
            participant_event_ids = EventRelation.objects.filter(
                content_type=ct,
                object_id=user.id
            ).values_list('event_id', flat=True)
            
            # Объединяем: события из доступных календарей ИЛИ где пользователь участник
            qs = qs.filter(
                Q(calendar_id__in=accessible_calendar_ids) |
                Q(id__in=participant_event_ids)
            )
        
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
        - calendar: ID календаря (необязательно, если не указан - все доступные календари)
        - start: начало диапазона (ISO 8601)
        - end: конец диапазона (ISO 8601)
        
        Возвращает все вхождения recurring событий + обычные события.
        """
        calendar_id = request.query_params.get('calendar')
        start_str = request.query_params.get('start')
        end_str = request.query_params.get('end')
        
        if not all([start_str, end_str]):
            return Response(
                {'detail': 'Требуются параметры: start, end'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        start_dt = parse_datetime(start_str)
        end_dt = parse_datetime(end_str)
        
        if not start_dt or not end_dt:
            return Response(
                {'detail': 'Некорректный формат дат (используйте ISO 8601)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Если указан конкретный календарь - фильтруем по нему
        if calendar_id:
            try:
                calendar = Calendar.objects.get(id=calendar_id)
                calendars = [calendar]
            except Calendar.DoesNotExist:
                return Response(
                    {'detail': 'Календарь не найден'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            # Если календарь не указан - берем все доступные пользователю календари
            from django.contrib.auth import get_user_model
            User = get_user_model()
            user = request.user
            
            if user.is_staff or user.is_superuser:
                calendars = Calendar.objects.all()
            else:
                ct = ContentType.objects.get_for_model(User)
                calendar_ids = CalendarRelation.objects.filter(
                    content_type=ct,
                    object_id=user.id
                ).values_list('calendar_id', flat=True)
                calendars = Calendar.objects.filter(id__in=calendar_ids)
        
        # Результат
        occurrences = []
        
        # Обрабатываем каждый календарь
        for calendar in calendars:
            events = Event.objects.filter(calendar=calendar)
            period = Period(events, start_dt, end_dt)
            
            for occurrence in period.get_occurrences():
                # Создаем уникальный ID для каждого вхождения (комбинация event_id и start)
                unique_id = f"{occurrence.event.id}_{occurrence.start.isoformat()}"
                
                occurrences.append({
                    'id': unique_id,  # Уникальный ID для каждого вхождения
                    'title': occurrence.title or occurrence.event.title,
                    'description': occurrence.event.description,
                    'start': occurrence.start.isoformat(),
                    'end': occurrence.end.isoformat(),
                    'calendar': calendar.id,  # Добавляем ID календаря
                    'color_event': occurrence.event.color_event,
                    'event_id': occurrence.event.id,  # ID оригинального события
                    'is_recurring': occurrence.event.rule_id is not None,
                    'rule': occurrence.event.rule_id,
                    'end_recurring_period': occurrence.event.end_recurring_period.isoformat() if occurrence.event.end_recurring_period else None,
                })
        
        return Response(occurrences)
    
    @action(detail=False, methods=['get'], url_path='my-events')
    def my_events(self, request):
        """Получить события текущего пользователя (где он участник).
        
        Query params:
        - start: начало диапазона (ISO 8601, необязательно)
        - end: конец диапазона (ISO 8601, необязательно)
        
        Возвращает только события где пользователь является участником (EventRelation).
        """
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        user = request.user
        ct = ContentType.objects.get_for_model(User)
        
        # ID событий где пользователь участник
        participant_event_ids = EventRelation.objects.filter(
            content_type=ct,
            object_id=user.id
        ).values_list('event_id', flat=True)
        
        # Фильтруем события
        qs = self.queryset.filter(id__in=participant_event_ids)
        
        # Фильтр по диапазону дат (если указан)
        start_str = request.query_params.get('start')
        end_str = request.query_params.get('end')
        
        if start_str and end_str:
            start_dt = parse_datetime(start_str)
            end_dt = parse_datetime(end_str)
            
            if start_dt and end_dt:
                qs = qs.filter(
                    start__lte=end_dt,
                    end__gte=start_dt
                )
        
        qs = qs.order_by('start')
        
        # Используем EventListSerializer для детальной информации
        serializer = EventListSerializer(qs, many=True)
        return Response(serializer.data)


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
