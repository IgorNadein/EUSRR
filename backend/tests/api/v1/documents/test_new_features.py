"""
Тесты для новых фич документооборота:
- DocumentTag ViewSet
- DocumentType ViewSet
- Cabinet ViewSet
- DocumentComment ViewSet
- Related Documents
- Thumbnails API
- django-reversion endpoints (versions, activity, revert)
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from documents.models import (
    Document,
    DocumentTag,
    DocumentType,
    Cabinet,
    DocumentComment,
)
from filer.models import Folder, File as FilerFile
from employees.models import Department

User = get_user_model()


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def user(db):
    """Обычный пользователь."""
    return User.objects.create_user(
        username='testuser',
        email='test@example.com',
        password='testpass123',
        first_name='Test',
        last_name='User'
    )


@pytest.fixture
def staff_user(db):
    """Staff пользователь."""
    return User.objects.create_user(
        username='staffuser',
        email='staff@example.com',
        password='staffpass123',
        first_name='Staff',
        last_name='User',
        is_staff=True
    )


@pytest.fixture
def document(user):
    """Тестовый документ."""
    return Document.objects.create(
        title='Test Document',
        description='Test Description',
        uploaded_by=user,
        status='draft'
    )


@pytest.fixture
def document_tag(db):
    """Тестовый тег."""
    return DocumentTag.objects.create(
        name='Important',
        slug='important',
        color='#ff0000'
    )


@pytest.fixture
def document_type(db):
    """Тестовый тип документа."""
    return DocumentType.objects.create(
        name='Contract',
        code='contract',
        description='Legal contracts',
        is_active=True
    )


@pytest.fixture
def cabinet(user):
    """Тестовый кабинет."""
    return Cabinet.objects.create(
        name='Test Cabinet',
        slug='test-cabinet',
        description='Test Cabinet Description',
        created_by=user
    )


# =============================================================================
# DOCUMENTTAG VIEWSET TESTS
# =============================================================================

@pytest.mark.django_db
class TestDocumentTagViewSet:
    """Тесты для DocumentTagViewSet."""
    
    def test_list_tags(self, api_client, user, document_tag):
        """Тест получения списка тегов."""
        api_client.force_authenticate(user=user)
        url = reverse('v1:document-tags-list')
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['name'] == 'Important'
    
    def test_create_tag(self, api_client, user):
        """Тест создания тега."""
        api_client.force_authenticate(user=user)
        url = reverse('v1:document-tags-list')
        
        data = {
            'name': 'Urgent',
            'slug': 'urgent',
            'color': '#00ff00'
        }
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        assert DocumentTag.objects.filter(slug='urgent').exists()
    
    def test_tag_documents(self, api_client, user, document_tag, document):
        """Тест получения документов тега."""
        document_tag.documents.add(document)
        api_client.force_authenticate(user=user)
        
        url = reverse('v1:document-tags-documents', args=[document_tag.pk])
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1


# =============================================================================
# DOCUMENTTYPE VIEWSET TESTS
# =============================================================================

@pytest.mark.django_db
class TestDocumentTypeViewSet:
    """Тесты для DocumentTypeViewSet."""
    
    def test_list_types(self, api_client, user, document_type):
        """Тест получения списка типов."""
        api_client.force_authenticate(user=user)
        url = reverse('v1:document-types-list')
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['name'] == 'Contract'
    
    def test_filter_inactive(self, api_client, user, document_type):
        """Тест фильтрации неактивных типов."""
        DocumentType.objects.create(
            name='Inactive Type',
            code='inactive',
            is_active=False
        )
        api_client.force_authenticate(user=user)
        
        # Без фильтра - только активные
        url = reverse('v1:document-types-list')
        response = api_client.get(url)
        assert len(response.data['results']) == 1
        
        # С фильтром - все
        response = api_client.get(url, {'include_inactive': 'true'})
        assert len(response.data['results']) == 2


# =============================================================================
# CABINET VIEWSET TESTS
# =============================================================================

@pytest.mark.django_db
class TestCabinetViewSet:
    """Тесты для CabinetViewSet."""
    
    def test_list_cabinets(self, api_client, user, cabinet):
        """Тест получения списка кабинетов."""
        api_client.force_authenticate(user=user)
        url = reverse('v1:cabinets-list')
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
    
    def test_create_cabinet(self, api_client, user):
        """Тест создания кабинета."""
        api_client.force_authenticate(user=user)
        url = reverse('v1:cabinets-list')
        
        data = {
            'name': 'New Cabinet',
            'slug': 'new-cabinet',
            'description': 'Test'
        }
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        cabinet = Cabinet.objects.get(slug='new-cabinet')
        assert cabinet.created_by == user
    
    def test_add_document_to_cabinet(self, api_client, user, cabinet, document):
        """Тест добавления документа в кабинет."""
        api_client.force_authenticate(user=user)
        url = reverse('v1:cabinets-add-document', args=[cabinet.pk])
        
        response = api_client.post(url, {'document_id': document.pk})
        
        assert response.status_code == status.HTTP_200_OK
        assert cabinet.documents.filter(pk=document.pk).exists()
    
    def test_remove_document_from_cabinet(self, api_client, user, cabinet, document):
        """Тест удаления документа из кабинета."""
        cabinet.documents.add(document)
        api_client.force_authenticate(user=user)
        
        url = reverse('v1:cabinets-remove-document', args=[cabinet.pk])
        response = api_client.post(url, {'document_id': document.pk})
        
        assert response.status_code == status.HTTP_200_OK
        assert not cabinet.documents.filter(pk=document.pk).exists()


# =============================================================================
# DOCUMENTCOMMENT VIEWSET TESTS
# =============================================================================

@pytest.mark.django_db
class TestDocumentCommentViewSet:
    """Тесты для DocumentCommentViewSet."""
    
    def test_create_comment(self, api_client, user, document):
        """Тест создания комментария."""
        api_client.force_authenticate(user=user)
        url = reverse('v1:document-comments-list')
        
        data = {
            'document_id': document.pk,
            'text': 'Test comment'
        }
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        comment = DocumentComment.objects.get(document=document)
        assert comment.text == 'Test comment'
        assert comment.author == user
    
    def test_create_reply(self, api_client, user, document):
        """Тест создания ответа на комментарий."""
        parent = DocumentComment.objects.create(
            document=document,
            author=user,
            text='Parent comment'
        )
        api_client.force_authenticate(user=user)
        
        url = reverse('v1:document-comments-list')
        data = {
            'document_id': document.pk,
            'parent_id': parent.pk,
            'text': 'Reply comment'
        }
        response = api_client.post(url, data)
        
        assert response.status_code == status.HTTP_201_CREATED
        reply = DocumentComment.objects.get(parent=parent)
        assert reply.text == 'Reply comment'
        assert reply.depth == 1
    
    def test_update_comment(self, api_client, user, document):
        """Тест обновления комментария."""
        comment = DocumentComment.objects.create(
            document=document,
            author=user,
            text='Original text'
        )
        api_client.force_authenticate(user=user)
        
        url = reverse('v1:document-comments-detail', args=[comment.pk])
        response = api_client.patch(url, {'text': 'Updated text'})
        
        assert response.status_code == status.HTTP_200_OK
        comment.refresh_from_db()
        assert comment.text == 'Updated text'
        assert comment.is_edited is True
    
    def test_delete_own_comment(self, api_client, user, document):
        """Тест удаления своего комментария."""
        comment = DocumentComment.objects.create(
            document=document,
            author=user,
            text='Test'
        )
        api_client.force_authenticate(user=user)
        
        url = reverse('v1:document-comments-detail', args=[comment.pk])
        response = api_client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not DocumentComment.objects.filter(pk=comment.pk).exists()
    
    def test_cannot_delete_others_comment(self, api_client, user, staff_user, document):
        """Тест запрета удаления чужого комментария."""
        comment = DocumentComment.objects.create(
            document=document,
            author=staff_user,
            text='Test'
        )
        api_client.force_authenticate(user=user)
        
        url = reverse('v1:document-comments-detail', args=[comment.pk])
        response = api_client.delete(url)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


# =============================================================================
# RELATED DOCUMENTS TESTS
# =============================================================================

@pytest.mark.django_db
class TestRelatedDocuments:
    """Тесты для связанных документов."""
    
    def test_add_related_document(self, api_client, user, document):
        """Тест добавления связанного документа."""
        related_doc = Document.objects.create(
            title='Related Doc',
            uploaded_by=user
        )
        api_client.force_authenticate(user=user)
        
        url = reverse('v1:documents-add-related', args=[document.pk])
        response = api_client.post(url, {'document_id': related_doc.pk})
        
        assert response.status_code == status.HTTP_200_OK
        assert document.related_documents.filter(pk=related_doc.pk).exists()
    
    def test_list_related_documents(self, api_client, user, document):
        """Тест получения списка связанных документов."""
        related_doc = Document.objects.create(
            title='Related Doc',
            uploaded_by=user
        )
        document.related_documents.add(related_doc)
        api_client.force_authenticate(user=user)
        
        url = reverse('v1:documents-related', args=[document.pk])
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
    
    def test_remove_related_document(self, api_client, user, document):
        """Тест удаления связанного документа."""
        related_doc = Document.objects.create(
            title='Related Doc',
            uploaded_by=user
        )
        document.related_documents.add(related_doc)
        api_client.force_authenticate(user=user)
        
        url = reverse('v1:documents-remove-related', args=[document.pk])
        response = api_client.post(url, {'document_id': related_doc.pk})
        
        assert response.status_code == status.HTTP_200_OK
        assert not document.related_documents.filter(pk=related_doc.pk).exists()
    
    def test_cannot_link_to_self(self, api_client, user, document):
        """Тест запрета связывания документа с самим собой."""
        api_client.force_authenticate(user=user)
        
        url = reverse('v1:documents-add-related', args=[document.pk])
        response = api_client.post(url, {'document_id': document.pk})
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# DJANGO-REVERSION TESTS
# =============================================================================

@pytest.mark.django_db
class TestReversionEndpoints:
    """Тесты для endpoints django-reversion."""
    
    def test_get_versions(self, api_client, user, document):
        """Тест получения истории версий."""
        # Создаем версию через изменение
        document.title = 'Updated Title'
        document.save()
        
        api_client.force_authenticate(user=user)
        url = reverse('v1:documents-versions', args=[document.pk])
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        # Должна быть хотя бы одна версия
        assert len(response.data) >= 1
    
    def test_get_activity(self, api_client, user, document):
        """Тест получения activity timeline."""
        api_client.force_authenticate(user=user)
        url = reverse('v1:documents-activity', args=[document.pk])
        
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)


# =============================================================================
# INTEGRATION TESTS
# =============================================================================

@pytest.mark.django_db
class TestIntegration:
    """Интеграционные тесты."""
    
    def test_document_with_all_features(self, api_client, user, document_tag, document_type, cabinet):
        """Тест документа со всеми фичами."""
        api_client.force_authenticate(user=user)
        
        # Создаем документ
        document = Document.objects.create(
            title='Complex Document',
            uploaded_by=user,
            document_type=document_type
        )
        
        # Добавляем тег
        document_tag.documents.add(document)
        
        # Добавляем в кабинет
        cabinet.documents.add(document)
        
        # Создаем комментарий
        DocumentComment.objects.create(
            document=document,
            author=user,
            text='Test comment'
        )
        
        # Проверяем, что все связано
        assert document.document_type == document_type
        assert document_tag in document.tags.all()
        assert document in cabinet.documents.all()
        assert document.comments.count() == 1
