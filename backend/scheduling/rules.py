"""
django-rules: декларативные правила доступа для django-scheduler

Правила используются для проверки permissions на уровне объектов.
Интегрируется с CalendarRelation для управления доступом к календарям и событиям.

https://github.com/dfunckt/django-rules
"""
import rules
from django.contrib.contenttypes.models import ContentType


# -----------------------------------------------------------------------------
# ПРЕДИКАТЫ (predicates)
# -----------------------------------------------------------------------------

@rules.predicate
def is_superuser(user):
    """Суперпользователь имеет все права"""
    return user.is_superuser


@rules.predicate
def can_view_calendar(user, calendar):
    """Проверяет доступ пользователя к календарю через CalendarRelation"""
    if calendar is None:
        return False
    
    if user.is_superuser:
        return True
    
    try:
        from schedule.models import CalendarRelation
        user_ct = ContentType.objects.get_for_model(user)
        
        return CalendarRelation.objects.filter(
            calendar=calendar,
            content_type=user_ct,
            object_id=user.id
        ).exists()
    except Exception:
        return False


@rules.predicate
def can_edit_calendar(user, calendar):
    """Проверяет право на редактирование календаря"""
    if calendar is None:
        return False
    
    if user.is_superuser:
        return True
    
    try:
        from schedule.models import CalendarRelation
        user_ct = ContentType.objects.get_for_model(user)
        
        # Проверяем что пользователь имеет отношение с правом редактирования
        relation = CalendarRelation.objects.filter(
            calendar=calendar,
            content_type=user_ct,
            object_id=user.id,
            distinction='owner'  # или используйте ваше значение для владельца
        ).first()
        
        return relation is not None
    except Exception:
        return False


@rules.predicate
def can_view_event(user, event):
    """Проверяет доступ пользователя к событию через календарь"""
    if event is None:
        return False
    
    if user.is_superuser:
        return True
    
    # Проверяем доступ через календарь
    return can_view_calendar(user, event.calendar)


@rules.predicate
def can_edit_event(user, event):
    """Проверяет право на редактирование события"""
    if event is None:
        return False
    
    if user.is_superuser:
        return True
    
    # Проверяем доступ через календарь
    return can_edit_calendar(user, event.calendar)


# -----------------------------------------------------------------------------
# ПРАВИЛА (rules) - регистрация в django-rules
# -----------------------------------------------------------------------------

# Календари
rules.add_rule('can_view_calendar', is_superuser | can_view_calendar)
rules.add_rule('can_edit_calendar', is_superuser | can_edit_calendar)
rules.add_rule('can_delete_calendar', is_superuser | can_edit_calendar)

# События
rules.add_rule('can_view_event', is_superuser | can_view_event)
rules.add_rule('can_edit_event', is_superuser | can_edit_event)
rules.add_rule('can_delete_event', is_superuser | can_edit_event)

# Для использования в DRF permissions или templates:
# {% if request.user|has_rule:'can_edit_calendar' calendar %}
#   <button>Edit Calendar</button>
# {% endif %}
