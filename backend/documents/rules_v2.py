# documents/rules_v2.py
"""
django-rules: декларативные правила доступа для DocumentV2

Адаптация правил доступа для новых моделей с django-filer.
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
def is_document_uploader(user, document):
    """Пользователь загрузил документ"""
    if document is None:
        return False
    return document.uploaded_by == user


@rules.predicate
def has_document_access_v2(user, document):
    """
    Пользователь имеет доступ к документу через:
    - sent_to_all=True (все активные сотрудники)
    - departments (пользователь в одном из отделов-получателей)
    - recipients (пользователь в списке получателей)
    """
    if document is None:
        return False
    
    # Документ для всех
    if document.sent_to_all and user.is_active:
        return True
    
    # Проверка через отделы
    if hasattr(user, 'department') and user.department:
        if document.departments.filter(id=user.department.id).exists():
            return True
    
    # Прямой доступ через recipients
    if document.recipients.filter(id=user.id).exists():
        return True
    
    return False


@rules.predicate
def can_manage_documents(user):
    """
    Пользователь может управлять документами.
    Адаптируйте под вашу логику (по должности, группе и т.д.)
    """
    if not hasattr(user, 'position'):
        return False
    
    position_name = getattr(user.position, 'name', '').lower()
    return any(keyword in position_name for keyword in [
        'руководитель', 'начальник', 'директор', 'заведующий', 'кадры'
    ])


@rules.predicate
def is_same_department(user, document):
    """Документ относится к отделу пользователя"""
    if document is None or not hasattr(user, 'department'):
        return False
    
    return document.departments.filter(id=user.department.id).exists()


@rules.predicate
def has_acknowledged_document(user, document):
    """Пользователь уже ознакомился с документом"""
    if document is None:
        return False
    
    from documents.models_v2 import DocumentAcknowledgementV2
    return DocumentAcknowledgementV2.objects.filter(
        document=document,
        user=user
    ).exists()


# -----------------------------------------------------------------------------
# ПРАВИЛА (rules)
# -----------------------------------------------------------------------------

# Просмотр документа
rules.add_rule(
    'documents.view_documentv2',
    is_superuser | is_document_uploader | has_document_access_v2
)

# Изменение документа (только загрузивший и менеджеры)
rules.add_rule(
    'documents.change_documentv2',
    is_superuser | is_document_uploader | can_manage_documents
)

# Удаление документа (только загрузивший, менеджеры и superuser)
rules.add_rule(
    'documents.delete_documentv2',
    is_superuser | is_document_uploader | can_manage_documents
)

# Скачивание документа (все, кто имеет доступ на просмотр)
rules.add_rule(
    'documents.download_documentv2',
    is_superuser | is_document_uploader | has_document_access_v2
)

# Отметка об ознакомлении (только те, у кого есть доступ)
rules.add_rule(
    'documents.acknowledge_documentv2',
    has_document_access_v2
)

# Просмотр списка ознакомившихся (загрузивший + менеджеры)
rules.add_rule(
    'documents.view_acknowledgements_documentv2',
    is_superuser | is_document_uploader | can_manage_documents
)

# Выдача доступа другим пользователям (только загрузивший и менеджеры)
rules.add_rule(
    'documents.share_documentv2',
    is_superuser | is_document_uploader | can_manage_documents
)

# Просмотр истории версий документа (filer + reversion)
rules.add_rule(
    'documents.view_documentv2_history',
    is_superuser | is_document_uploader | can_manage_documents
)

# Просмотр всех документов отдела
rules.add_rule(
    'documents.view_department_documents',
    is_superuser | can_manage_documents
)


# -----------------------------------------------------------------------------
# PERMISSIONS ДЛЯ МОДЕЛЕЙ
# -----------------------------------------------------------------------------

# Если вы хотите переопределить стандартные Django permissions:
rules.add_perm('documents.view_documentv2', is_superuser | has_document_access_v2)
rules.add_perm('documents.change_documentv2', is_superuser | is_document_uploader | can_manage_documents)
rules.add_perm('documents.delete_documentv2', is_superuser | is_document_uploader | can_manage_documents)
rules.add_perm('documents.add_documentv2', rules.is_authenticated)  # Все авторизованные могут создавать


# -----------------------------------------------------------------------------
# ИСПОЛЬЗОВАНИЕ В КОДЕ
# -----------------------------------------------------------------------------

"""
# В views:
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, render, redirect
import rules
from documents.models_v2 import DocumentV2, DocumentAcknowledgementV2

def document_detail_v2(request, pk):
    document = get_object_or_404(DocumentV2, pk=pk)
    
    # Проверка доступа
    if not rules.test_rule('documents.view_documentv2', request.user, document):
        raise PermissionDenied
    
    # Проверка, ознакомился ли пользователь
    has_acknowledged = rules.test_rule('documents.has_acknowledged_document', request.user, document)
    
    return render(request, 'documents/detail_v2.html', {
        'document': document,
        'has_acknowledged': has_acknowledged,
    })


def document_acknowledge_v2(request, pk):
    document = get_object_or_404(DocumentV2, pk=pk)
    
    # Проверка прав на ознакомление
    if not rules.test_rule('documents.acknowledge_documentv2', request.user, document):
        raise PermissionDenied
    
    # Создаем запись об ознакомлении (если еще нет)
    DocumentAcknowledgementV2.objects.get_or_create(
        document=document,
        user=request.user
    )
    
    return redirect('documents:detail_v2', pk=document.pk)


def document_download_v2(request, pk):
    document = get_object_or_404(DocumentV2, pk=pk)
    
    # Проверка прав на скачивание
    if not rules.test_rule('documents.download_documentv2', request.user, document):
        raise PermissionDenied
    
    # Отдаем файл через django-filer
    from django.http import FileResponse
    return FileResponse(document.file.file.open(), as_attachment=True)


# В templates:
{% load rules %}

{% has_rule 'documents.view_documentv2' user document as can_view %}
{% if can_view %}
    <a href="{{ document.file.url }}" target="_blank" class="btn btn-primary">
        Открыть документ
    </a>
{% endif %}

{% has_rule 'documents.change_documentv2' user document as can_edit %}
{% if can_edit %}
    <a href="{% url 'documents:edit_v2' document.pk %}" class="btn btn-secondary">
        Редактировать
    </a>
{% endif %}

{% has_rule 'documents.acknowledge_documentv2' user document as can_acknowledge %}
{% if can_acknowledge %}
    {% has_rule 'documents.has_acknowledged_document' user document as has_acknowledged %}
    {% if not has_acknowledged %}
        <form method="post" action="{% url 'documents:acknowledge_v2' document.pk %}">
            {% csrf_token %}
            <button type="submit" class="btn btn-success">Ознакомиться</button>
        </form>
    {% else %}
        <span class="badge bg-success">✅ Вы ознакомились</span>
    {% endif %}
{% endif %}


# В DRF permissions:
from rest_framework import permissions
import rules

class DocumentV2Permission(permissions.BasePermission):
    \"\"\"Permission класс для DocumentV2 API\"\"\"
    
    def has_permission(self, request, view):
        # Только авторизованные пользователи
        return request.user and request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        if request.method in permissions.SAFE_METHODS:
            return rules.test_rule('documents.view_documentv2', request.user, obj)
        elif request.method in ['PUT', 'PATCH']:
            return rules.test_rule('documents.change_documentv2', request.user, obj)
        elif request.method == 'DELETE':
            return rules.test_rule('documents.delete_documentv2', request.user, obj)
        return False


# В queryset filtering (показывать только доступные документы):
from django.db.models import Q

def get_accessible_documents_v2(user):
    \"\"\"Получить все документы, доступные пользователю\"\"\"
    if user.is_superuser:
        return DocumentV2.objects.all()
    
    # Документы, к которым есть доступ
    query = Q()
    
    # 1. Загруженные пользователем
    query |= Q(uploaded_by=user)
    
    # 2. Для всех активных сотрудников
    if user.is_active:
        query |= Q(sent_to_all=True)
    
    # 3. Для отдела пользователя
    if hasattr(user, 'department') and user.department:
        query |= Q(departments=user.department)
    
    # 4. Напрямую в списке получателей
    query |= Q(recipients=user)
    
    return DocumentV2.objects.filter(query).distinct()


# ViewSet пример с фильтрацией:
from rest_framework import viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

class DocumentV2ViewSet(viewsets.ModelViewSet):
    permission_classes = [DocumentV2Permission]
    
    def get_queryset(self):
        # Показываем только доступные документы
        return get_accessible_documents_v2(self.request.user)
    
    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        document = self.get_object()
        
        if not rules.test_rule('documents.acknowledge_documentv2', request.user, document):
            return Response({'error': 'No permission'}, status=403)
        
        ack, created = DocumentAcknowledgementV2.objects.get_or_create(
            document=document,
            user=request.user
        )
        
        return Response({
            'acknowledged': True,
            'acknowledged_at': ack.acknowledged_at
        })
"""
