"""
django-rules: декларативные правила доступа для requests_app

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
def is_request_author(user, request_obj):
    """Пользователь является автором заявки"""
    if request_obj is None:
        return False
    return request_obj.created_by == user or request_obj.author == user


@rules.predicate
def is_request_assignee(user, request_obj):
    """Пользователь является исполнителем заявки"""
    if request_obj is None:
        return False
    
    # Проверка через assigned_to (один исполнитель)
    if hasattr(request_obj, 'assigned_to'):
        return request_obj.assigned_to == user
    
    # Проверка через assignees (несколько исполнителей)
    if hasattr(request_obj, 'assignees'):
        return user in request_obj.assignees.all()
    
    return False


@rules.predicate
def is_request_approver(user, request_obj):
    """Пользователь назначен согласующим для этой заявки"""
    if request_obj is None:
        return False
    
    # Проверка через approvers
    if hasattr(request_obj, 'approvers'):
        return user in request_obj.approvers.all()
    
    # Проверка через approval_chain
    if hasattr(request_obj, 'approval_chain'):
        return request_obj.approval_chain.filter(approver=user).exists()
    
    return False


@rules.predicate
def can_manage_requests(user):
    """
    Пользователь может управлять заявками (по должности или роли).
    Адаптируйте под вашу логику.
    """
    if not hasattr(user, 'position'):
        return False
    
    position_name = getattr(user.position, 'name', '').lower()
    return any(keyword in position_name for keyword in [
        'руководитель', 'начальник', 'директор', 'менеджер', 'администратор'
    ])


@rules.predicate
def is_department_request(user, request_obj):
    """Заявка относится к отделу пользователя"""
    if request_obj is None or not hasattr(user, 'department'):
        return False
    
    # Проверка через department
    if hasattr(request_obj, 'department'):
        return request_obj.department == user.department
    
    # Проверка через автора заявки
    if hasattr(request_obj, 'created_by') and hasattr(request_obj.created_by, 'department'):
        return request_obj.created_by.department == user.department
    
    return False


@rules.predicate
def is_request_watcher(user, request_obj):
    """Пользователь наблюдает за заявкой (подписан на уведомления)"""
    if request_obj is None:
        return False
    
    if hasattr(request_obj, 'watchers'):
        return user in request_obj.watchers.all()
    
    return False


@rules.predicate
def can_change_request_status(user, request_obj):
    """Пользователь может менять статус заявки"""
    if request_obj is None:
        return False
    
    # Автор может закрывать/отменять свою заявку
    if is_request_author(user, request_obj):
        return True
    
    # Исполнитель может переводить в работу/выполнено
    if is_request_assignee(user, request_obj):
        return True
    
    # Менеджеры могут менять любые статусы
    if can_manage_requests(user):
        return True
    
    return False


# -----------------------------------------------------------------------------
# ПРАВИЛА (rules)
# -----------------------------------------------------------------------------

# Просмотр заявки
rules.add_rule(
    'requests_app.view_request',
    is_superuser | is_request_author | is_request_assignee | 
    is_request_approver | is_request_watcher | can_manage_requests
)

# Изменение заявки
rules.add_rule(
    'requests_app.change_request',
    is_superuser | is_request_author | can_manage_requests
)

# Удаление заявки (только автор и менеджеры)
rules.add_rule(
    'requests_app.delete_request',
    is_superuser | (is_request_author & rules.always_allow) | can_manage_requests
)

# Назначение исполнителя
rules.add_rule(
    'requests_app.assign_request',
    is_superuser | can_manage_requests | is_request_author
)

# Изменение статуса заявки
rules.add_rule(
    'requests_app.change_status',
    is_superuser | can_change_request_status
)

# Согласование заявки
rules.add_rule(
    'requests_app.approve_request',
    is_superuser | is_request_approver | can_manage_requests
)

# Комментирование заявки
rules.add_rule(
    'requests_app.comment_request',
    is_superuser | is_request_author | is_request_assignee | 
    is_request_watcher | can_manage_requests
)

# Добавление наблюдателей
rules.add_rule(
    'requests_app.add_watchers',
    is_superuser | is_request_author | can_manage_requests
)

# Просмотр всех заявок отдела
rules.add_rule(
    'requests_app.view_department_requests',
    is_superuser | can_manage_requests
)

# Просмотр статистики по заявкам
rules.add_rule(
    'requests_app.view_statistics',
    is_superuser | can_manage_requests
)


# -----------------------------------------------------------------------------
# ИСПОЛЬЗОВАНИЕ В КОДЕ
# -----------------------------------------------------------------------------

"""
# В views:
from django.core.exceptions import PermissionDenied
import rules

def request_detail(request, pk):
    request_obj = get_object_or_404(Request, pk=pk)
    
    if not rules.test_rule('requests_app.view_request', request.user, request_obj):
        raise PermissionDenied
    
    return render(request, 'requests_app/detail.html', {'request': request_obj})


def request_assign(request, pk):
    request_obj = get_object_or_404(Request, pk=pk)
    
    if not rules.test_rule('requests_app.assign_request', request.user, request_obj):
        raise PermissionDenied
    
    # Логика назначения
    assignee_id = request.POST.get('assignee_id')
    request_obj.assigned_to_id = assignee_id
    request_obj.save()
    
    return redirect('requests_app:detail', pk=request_obj.pk)


# В templates:
{% load rules %}

{% has_rule 'requests_app.change_status' user request as can_change_status %}
{% if can_change_status %}
    <form method="post" action="{% url 'requests_app:change_status' request.pk %}">
        {% csrf_token %}
        <select name="status" class="form-select">
            <option value="new">Новая</option>
            <option value="in_progress">В работе</option>
            <option value="completed">Выполнено</option>
        </select>
        <button type="submit" class="btn btn-primary">Изменить статус</button>
    </form>
{% endif %}


# В DRF permissions:
from rest_framework import permissions
import rules

class RequestPermission(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return rules.test_rule('requests_app.view_request', request.user, obj)
        elif request.method in ['PUT', 'PATCH']:
            return rules.test_rule('requests_app.change_request', request.user, obj)
        elif request.method == 'DELETE':
            return rules.test_rule('requests_app.delete_request', request.user, obj)
        return False


# Фильтрация QuerySet (только доступные заявки):
from django.db.models import Q

def get_accessible_requests(user):
    return Request.objects.filter(
        Q(created_by=user) |  # Созданные пользователем
        Q(assigned_to=user) |  # Назначенные пользователю
        Q(watchers=user) |  # Наблюдаемые пользователем
        Q(approvers=user) |  # Требующие согласования
        Q(department=user.department)  # Заявки отдела
    ).distinct()
"""
