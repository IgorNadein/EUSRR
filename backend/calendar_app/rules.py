"""
django-rules: декларативные правила доступа для calendar_app

Правила используются для проверки permissions на уровне объектов.
https://github.com/dfunckt/django-rules
"""

import rules


# -----------------------------------------------------------------------------
# ПРЕДИКАТЫ (predicates)
# -----------------------------------------------------------------------------

@rules.predicate
def is_superuser(user):
    """Суперпользователь имеет все права"""
    return user.is_superuser


@rules.predicate
def is_calendar_owner(user, calendar):
    """Пользователь является владельцем календаря"""
    if calendar is None:
        return False
    
    # Для django-scheduler
    if hasattr(calendar, 'creator'):
        return calendar.creator == user
    
    # Альтернативные поля
    if hasattr(calendar, 'owner'):
        return calendar.owner == user
    
    return False


@rules.predicate
def is_personal_calendar(user, calendar):
    """Это личный календарь пользователя"""
    if calendar is None:
        return False
    
    # Проверка slug для личного календаря
    if hasattr(calendar, 'slug'):
        return calendar.slug == f'personal-{user.pk}'
    
    # Проверка через creator + тип календаря
    if hasattr(calendar, 'calendar_type') and calendar.calendar_type == 'personal':
        return is_calendar_owner(user, calendar)
    
    return False


@rules.predicate
def has_calendar_access(user, calendar):
    """Пользователь имеет доступ к календарю через подписку или права"""
    if calendar is None:
        return False
    
    # Публичный календарь
    if hasattr(calendar, 'is_public') and calendar.is_public:
        return True
    
    # Календарь отдела
    if hasattr(calendar, 'department') and hasattr(user, 'department'):
        if calendar.department == user.department:
            return True
    
    # Подписка на календарь
    if hasattr(calendar, 'subscriptions'):
        return calendar.subscriptions.filter(user=user).exists()
    
    # Календарь компании (доступен всем сотрудникам)
    if hasattr(calendar, 'calendar_type') and calendar.calendar_type == 'company':
        return user.is_staff
    
    return False


@rules.predicate
def is_event_creator(user, event):
    """Пользователь является создателем события"""
    if event is None:
        return False
    
    # django-scheduler использует creator_id
    if hasattr(event, 'creator'):
        return event.creator == user
    
    if hasattr(event, 'created_by'):
        return event.created_by == user
    
    return False


@rules.predicate
def can_access_event_calendar(user, event):
    """Пользователь имеет доступ к календарю, где находится событие"""
    if event is None or not hasattr(event, 'calendar'):
        return False
    
    return has_calendar_access(user, event.calendar) or is_calendar_owner(user, event.calendar)


@rules.predicate
def is_event_participant(user, event):
    """Пользователь является участником события"""
    if event is None:
        return False
    
    # Проверка через участников
    if hasattr(event, 'participants'):
        return user in event.participants.all()
    
    # Проверка через occurrence (для повторяющихся событий)
    if hasattr(event, 'occurrence_set'):
        return event.occurrence_set.filter(participants=user).exists()
    
    return False


@rules.predicate
def can_manage_calendars(user):
    """
    Пользователь может управлять календарями (администратор календарей).
    Адаптируйте под вашу логику.
    """
    if not hasattr(user, 'position'):
        return False
    
    position_name = getattr(user.position, 'name', '').lower()
    return any(keyword in position_name for keyword in [
        'руководитель', 'начальник', 'директор', 'секретарь', 'администратор'
    ])


@rules.predicate
def is_department_calendar(user, calendar):
    """Календарь относится к отделу пользователя"""
    if calendar is None or not hasattr(user, 'department'):
        return False
    
    if hasattr(calendar, 'department'):
        return calendar.department == user.department
    
    return False


# -----------------------------------------------------------------------------
# ПРАВИЛА (rules)
# -----------------------------------------------------------------------------

# Просмотр календаря
rules.add_rule(
    'calendar_app.view_calendar',
    is_superuser | is_calendar_owner | is_personal_calendar | 
    has_calendar_access | is_department_calendar
)

# Изменение календаря (настройки, название, описание)
rules.add_rule(
    'calendar_app.change_calendar',
    is_superuser | is_calendar_owner | can_manage_calendars
)

# Удаление календаря
rules.add_rule(
    'calendar_app.delete_calendar',
    is_superuser | is_calendar_owner
)

# Создание события в календаре
rules.add_rule(
    'calendar_app.create_event',
    is_superuser | is_calendar_owner | has_calendar_access
)

# Просмотр события
rules.add_rule(
    'calendar_app.view_event',
    is_superuser | is_event_creator | can_access_event_calendar | is_event_participant
)

# Изменение события
rules.add_rule(
    'calendar_app.change_event',
    is_superuser | is_event_creator | is_calendar_owner
)

# Удаление события
rules.add_rule(
    'calendar_app.delete_event',
    is_superuser | is_event_creator | is_calendar_owner
)

# Подписка на календарь
rules.add_rule(
    'calendar_app.subscribe_calendar',
    rules.is_authenticated  # Любой авторизованный может подписаться на публичный календарь
)

# Отмена подписки на календарь
rules.add_rule(
    'calendar_app.unsubscribe_calendar',
    rules.is_authenticated
)

# Экспорт календаря (iCal)
rules.add_rule(
    'calendar_app.export_calendar',
    is_superuser | is_calendar_owner | has_calendar_access
)

# Приглашение участников на событие
rules.add_rule(
    'calendar_app.invite_participants',
    is_superuser | is_event_creator | is_calendar_owner
)

# Просмотр всех календарей (для администраторов)
rules.add_rule(
    'calendar_app.view_all_calendars',
    is_superuser | can_manage_calendars
)


# -----------------------------------------------------------------------------
# ИСПОЛЬЗОВАНИЕ В КОДЕ
# -----------------------------------------------------------------------------

"""
# В views:
from django.core.exceptions import PermissionDenied
import rules

def calendar_detail(request, slug):
    calendar = get_object_or_404(Calendar, slug=slug)
    
    if not rules.test_rule('calendar_app.view_calendar', request.user, calendar):
        raise PermissionDenied("У вас нет доступа к этому календарю")
    
    events = calendar.event_set.all()
    return render(request, 'calendar_app/calendar.html', {
        'calendar': calendar,
        'events': events
    })


def event_create(request, calendar_slug):
    calendar = get_object_or_404(Calendar, slug=calendar_slug)
    
    if not rules.test_rule('calendar_app.create_event', request.user, calendar):
        return JsonResponse({'error': 'Нет прав на создание событий'}, status=403)
    
    # Логика создания события
    event = Event.objects.create(
        calendar=calendar,
        creator=request.user,
        title=request.POST.get('title'),
        start=request.POST.get('start'),
        end=request.POST.get('end'),
    )
    
    return JsonResponse({'event_id': event.pk})


def event_update(request, pk):
    event = get_object_or_404(Event, pk=pk)
    
    if not rules.test_rule('calendar_app.change_event', request.user, event):
        return JsonResponse({'error': 'Нет прав на изменение'}, status=403)
    
    event.title = request.POST.get('title', event.title)
    event.save()
    
    return JsonResponse({'success': True})


# В templates:
{% load rules %}

{% has_rule 'calendar_app.create_event' user calendar as can_create %}
{% if can_create %}
    <button class="btn btn-primary" data-bs-toggle="modal" data-bs-target="#eventModal">
        Создать событие
    </button>
{% endif %}

{% for event in events %}
    <div class="event">
        <h4>{{ event.title }}</h4>
        <p>{{ event.start|date:"d.m.Y H:i" }} - {{ event.end|date:"d.m.Y H:i" }}</p>
        
        {% has_rule 'calendar_app.change_event' user event as can_edit %}
        {% if can_edit %}
            <a href="{% url 'calendar_app:event_edit' event.pk %}" class="btn btn-sm btn-primary">
                Редактировать
            </a>
        {% endif %}
        
        {% has_rule 'calendar_app.delete_event' user event as can_delete %}
        {% if can_delete %}
            <form method="post" action="{% url 'calendar_app:event_delete' event.pk %}" 
                  onsubmit="return confirm('Удалить событие?')">
                {% csrf_token %}
                <button type="submit" class="btn btn-sm btn-danger">Удалить</button>
            </form>
        {% endif %}
    </div>
{% endfor %}


# В DRF permissions (уже реализовано в api/v1/schedule/permissions.py):
from rest_framework import permissions
import rules

class IsCalendarOwnerOrAdmin(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        # Для Calendar
        if hasattr(obj, 'creator'):
            calendar = obj
        # Для Event
        elif hasattr(obj, 'calendar'):
            calendar = obj.calendar
        else:
            return False
        
        if request.method in permissions.SAFE_METHODS:
            return rules.test_rule('calendar_app.view_calendar', request.user, calendar)
        elif request.method in ['POST']:
            return rules.test_rule('calendar_app.create_event', request.user, calendar)
        elif request.method in ['PUT', 'PATCH']:
            if hasattr(obj, 'calendar'):  # Event
                return rules.test_rule('calendar_app.change_event', request.user, obj)
            else:  # Calendar
                return rules.test_rule('calendar_app.change_calendar', request.user, obj)
        elif request.method == 'DELETE':
            if hasattr(obj, 'calendar'):
                return rules.test_rule('calendar_app.delete_event', request.user, obj)
            else:
                return rules.test_rule('calendar_app.delete_calendar', request.user, obj)
        
        return False


# Фильтрация QuerySet (только доступные календари):
from django.db.models import Q

def get_accessible_calendars(user):
    return Calendar.objects.filter(
        Q(creator=user) |  # Собственные календари
        Q(slug=f'personal-{user.pk}') |  # Личный календарь
        Q(is_public=True) |  # Публичные календари
        Q(department=user.department) |  # Календари отдела
        Q(calendar_type='company') |  # Корпоративный календарь
        Q(subscriptions__user=user)  # Подписки
    ).distinct()


# Middleware для защиты iCal экспорта:
class CalendarExportMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.path.startswith('/calendar/export/'):
            # Извлечение календаря
            slug = request.path.split('/')[-2]
            calendar = Calendar.objects.filter(slug=slug).first()
            
            if calendar and not rules.test_rule('calendar_app.export_calendar', request.user, calendar):
                return HttpResponseForbidden("У вас нет прав на экспорт этого календаря")
        
        return self.get_response(request)
"""
