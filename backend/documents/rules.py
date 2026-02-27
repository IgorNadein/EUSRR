"""
django-rules: декларативные правила доступа для documents

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
def is_document_owner(user, document):
    """Пользователь является создателем документа"""
    if document is None:
        return False
    return document.created_by == user or document.owner == user


@rules.predicate
def is_document_author(user, document):
    """Пользователь является автором документа"""
    if document is None or not hasattr(document, 'author'):
        return False
    return document.author == user


@rules.predicate
def has_document_access(user, document):
    """
    Пользователь имеет доступ к документу через:
    - Публичный доступ (is_public)
    - Доступ для отдела (department_access)
    - Прямой доступ в списке разрешённых пользователей
    """
    if document is None:
        return False
    
    # Публичный документ
    if hasattr(document, 'is_public') and document.is_public:
        return True
    
    # Доступ для отдела
    if hasattr(document, 'department_access') and hasattr(user, 'department'):
        if document.department_access and document.department_access == user.department:
            return True
    
    # Прямой доступ через ManyToMany (если есть поле shared_with или allowed_users)
    if hasattr(document, 'shared_with'):
        if user in document.shared_with.all():
            return True
    
    if hasattr(document, 'allowed_users'):
        if user in document.allowed_users.all():
            return True
    
    return False


@rules.predicate
def can_approve_documents(user):
    """
    Пользователь может согласовывать документы.
    Адаптируйте под вашу логику (по должности, группе и т.д.)
    """
    if not hasattr(user, 'position'):
        return False
    
    position_name = getattr(user.position, 'name', '').lower()
    return any(keyword in position_name for keyword in [
        'руководитель', 'начальник', 'директор', 'заведующий'
    ])


@rules.predicate
def is_document_approver(user, document):
    """Пользователь назначен согласующим для этого документа"""
    if document is None:
        return False
    
    # Проверка через связь approvers, если есть
    if hasattr(document, 'approvers'):
        return user in document.approvers.all()
    
    # Проверка через связь approval_chain (если используется цепочка согласования)
    if hasattr(document, 'approval_chain'):
        return document.approval_chain.filter(approver=user).exists()
    
    return False


@rules.predicate
def is_same_department(user, document):
    """Документ относится к отделу пользователя"""
    if document is None or not hasattr(user, 'department'):
        return False
    
    if hasattr(document, 'department'):
        return document.department == user.department
    
    return False


@rules.predicate
def is_document_category_manager(user, document):
    """
    Пользователь является менеджером категории документа.
    Адаптируйте под вашу структуру категорий.
    """
    if document is None or not hasattr(document, 'category'):
        return False
    
    category = document.category
    if hasattr(category, 'managers'):
        return user in category.managers.all()
    
    return False


# -----------------------------------------------------------------------------
# ПРАВИЛА (rules)
# -----------------------------------------------------------------------------

# Просмотр документа
rules.add_rule(
    'documents.view_document',
    is_superuser | is_document_owner | is_document_author | has_document_access
)

# Изменение документа (только владелец и автор)
rules.add_rule(
    'documents.change_document',
    is_superuser | is_document_owner | is_document_author
)

# Удаление документа (только владелец и superuser)
rules.add_rule(
    'documents.delete_document',
    is_superuser | is_document_owner
)

# Согласование документа (согласующие + руководители)
rules.add_rule(
    'documents.approve_document',
    is_superuser | is_document_approver | can_approve_documents
)

# Публикация документа (владелец + менеджеры категории)
rules.add_rule(
    'documents.publish_document',
    is_superuser | is_document_owner | is_document_category_manager
)

# Скачивание документа (все, кто имеет доступ на просмотр)
rules.add_rule(
    'documents.download_document',
    is_superuser | is_document_owner | is_document_author | has_document_access
)

# Выдача доступа другим пользователям (только владелец)
rules.add_rule(
    'documents.share_document',
    is_superuser | is_document_owner
)

# Просмотр истории изменений документа
rules.add_rule(
    'documents.view_document_history',
    is_superuser | is_document_owner | is_document_author | is_document_category_manager
)

# Просмотр всех документов отдела
rules.add_rule(
    'documents.view_department_documents',
    is_superuser | can_approve_documents
)


# -----------------------------------------------------------------------------
# PERMISSIONS ДЛЯ МОДЕЛЕЙ
# -----------------------------------------------------------------------------

# Если вы хотите переопределить стандартные Django permissions:
# rules.add_perm('documents.view_document', is_superuser | has_document_access)
# rules.add_perm('documents.change_document', is_superuser | is_document_owner)
# rules.add_perm('documents.delete_document', is_superuser | is_document_owner)
# rules.add_perm('documents.add_document', rules.is_authenticated)  # Все авторизованные могут создавать


# -----------------------------------------------------------------------------
# ИСПОЛЬЗОВАНИЕ В КОДЕ
# -----------------------------------------------------------------------------

"""
# В views:
from django.core.exceptions import PermissionDenied
import rules

def document_detail(request, pk):
    document = get_object_or_404(Document, pk=pk)
    
    # Проверка доступа
    if not rules.test_rule('documents.view_document', request.user, document):
        raise PermissionDenied
    
    return render(request, 'documents/detail.html', {'document': document})


def document_approve(request, pk):
    document = get_object_or_404(Document, pk=pk)
    
    # Проверка прав на согласование
    if not rules.test_rule('documents.approve_document', request.user, document):
        raise PermissionDenied
    
    # Логика согласования
    document.status = 'approved'
    document.approved_by = request.user
    document.save()
    
    return redirect('documents:detail', pk=document.pk)


# В templates:
{% load rules %}

{% has_rule 'documents.change_document' user document as can_edit %}
{% if can_edit %}
    <a href="{% url 'documents:edit' document.pk %}" class="btn btn-primary">
        Редактировать
    </a>
{% endif %}

{% has_rule 'documents.approve_document' user document as can_approve %}
{% if can_approve and document.status == 'pending' %}
    <form method="post" action="{% url 'documents:approve' document.pk %}">
        {% csrf_token %}
        <button type="submit" class="btn btn-success">Согласовать</button>
    </form>
{% endif %}


# В DRF permissions:
from rest_framework import permissions
import rules

class DocumentPermission(permissions.BasePermission):
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return rules.test_rule('documents.view_document', request.user, obj)
        elif request.method in ['PUT', 'PATCH']:
            return rules.test_rule('documents.change_document', request.user, obj)
        elif request.method == 'DELETE':
            return rules.test_rule('documents.delete_document', request.user, obj)
        return False


# В queryset filtering (показывать только доступные документы):
from django.db.models import Q

def get_accessible_documents(user):
    # Документы, к которым есть доступ
    return Document.objects.filter(
        Q(created_by=user) |  # Созданные пользователем
        Q(owner=user) |  # Принадлежащие пользователю
        Q(is_public=True) |  # Публичные
        Q(department_access=user.department) |  # Доступные для отдела
        Q(shared_with=user)  # Расшаренные для пользователя
    ).distinct()


# Middleware для проверки доступа к файлам:
# (если файлы отдаются через X-Accel-Redirect или подобное)

class DocumentAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    
    def __call__(self, request):
        if request.path.startswith('/media/documents/'):
            # Извлекаем документ по пути
            document = self.get_document_from_path(request.path)
            if document and not rules.test_rule('documents.view_document', request.user, document):
                return HttpResponseForbidden("У вас нет доступа к этому документу")
        
        return self.get_response(request)
"""
