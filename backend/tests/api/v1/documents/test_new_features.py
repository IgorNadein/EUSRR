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

from documents.models import (
    Document,
    DocumentTag,
    DocumentType,
    Cabinet,
    DocumentComment,
)
from tests.api.v1.documents.test_documents_api import make_document, grant_perms

pytestmark = pytest.mark.django_db

User = get_user_model()


# =============================================================================
# DOCUMENTTAG VIEWSET TESTS
# =============================================================================

class TestDocumentTagViewSet:
    """Тесты для DocumentTagViewSet."""
    
    def test_list_tags(self, auth_client_factory, user_factory):
        """Тест получения списка тегов."""
        user = user_factory()
        client = auth_client_factory(user)
        
        # Создаём тег
        tag = DocumentTag.objects.create(
            name='Important',
            slug='important',
            color='#ff0000'
        )
        
        url = reverse('api:v1:document-tags-list')
        response = client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['name'] == 'Important'
    
    def test_create_tag(self, auth_client_factory, user_factory):
        """Тест создания тега."""
        user = user_factory()
        client = auth_client_factory(user)
        
        url = reverse('api:v1:document-tags-list')
        data = {
            'name': 'Urgent',
            'slug': 'urgent',
            'color': '#00ff00'
        }
        response = client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert DocumentTag.objects.filter(slug='urgent').exists()
    
    def test_tag_documents(self, auth_client_factory, user_factory):
        """Тест получения документов тега."""
        user = user_factory()
        client = auth_client_factory(user)
        
        tag = DocumentTag.objects.create(
            name='Important',
            slug='important'
        )
        doc = make_document(uploaded_by=user)
        tag.documents.add(doc)
        
        url = reverse('api:v1:document-tags-documents', args=[tag.pk])
        response = client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
    
    def test_search_tags(self, auth_client_factory, user_factory):
        """Тест поиска тегов."""
        user = user_factory()
        client = auth_client_factory(user)
        
        DocumentTag.objects.create(name='Important', slug='important')
        DocumentTag.objects.create(name='Urgent', slug='urgent')
        
        url = reverse('api:v1:document-tags-list')
        response = client.get(url, {'search': 'Import'})
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['name'] == 'Important'


# =============================================================================
# DOCUMENTTYPE VIEWSET TESTS
# =============================================================================

class TestDocumentTypeViewSet:
    """Тесты для DocumentTypeViewSet."""
    
    def test_list_types(self, auth_client_factory, user_factory):
        """Тест получения списка типов."""
        user = user_factory()
        client = auth_client_factory(user)
        
        DocumentType.objects.create(
            name='Contract',
            code='contract',
            is_active=True
        )
        
        url = reverse('api:v1:document-types-list')
        response = client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert len(response.data['results']) == 1
    
    def test_filter_inactive(self, auth_client_factory, user_factory):
        """Тест фильтрации неактивных типов."""
        user = user_factory()
        client = auth_client_factory(user)
        
        DocumentType.objects.create(
            name='Active Type',
            code='active',
            is_active=True
        )
        DocumentType.objects.create(
            name='Inactive Type',
            code='inactive',
            is_active=False
        )
        
        url = reverse('api:v1:document-types-list')
        
        # Без фильтра - только активные
        response = client.get(url)
        assert len(response.data['results']) == 1
        
        # С фильтром - все
        response = client.get(url, {'include_inactive': 'true'})
        assert len(response.data['results']) == 2


# =============================================================================
# CABINET VIEWSET TESTS
# =============================================================================

class TestCabinetViewSet:
    """Тесты для CabinetViewSet."""
    
    def test_list_cabinets(self, auth_client_factory, user_factory):
        """Тест получения списка кабинетов."""
        user = user_factory()
        client = auth_client_factory(user)
        
        Cabinet.objects.create(
            name='Test Cabinet',
            slug='test-cabinet',
            created_by=user
        )
        
        url = reverse('api:v1:cabinets-list')
        response = client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'results' in response.data
        assert len(response.data['results']) == 1
    
    def test_create_cabinet(self, auth_client_factory, user_factory):
        """Тест создания кабинета."""
        user = user_factory()
        client = auth_client_factory(user)
        
        url = reverse('api:v1:cabinets-list')
        data = {
            'name': 'New Cabinet',
            'slug': 'new-cabinet',
            'description': 'Test'
        }
        response = client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        cabinet = Cabinet.objects.get(slug='new-cabinet')
        assert cabinet.created_by == user
    
    def test_add_document_to_cabinet(self, auth_client_factory, user_factory):
        """Тест добавления документа в кабинет."""
        user = user_factory()
        client = auth_client_factory(user)
        
        cabinet = Cabinet.objects.create(
            name='Cabinet',
            slug='cabinet',
            created_by=user
        )
        doc = make_document(uploaded_by=user)
        
        url = reverse('api:v1:cabinets-add-document', args=[cabinet.pk])
        response = client.post(url, {'document_id': doc.pk}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert cabinet.documents.filter(pk=doc.pk).exists()
    
    def test_remove_document_from_cabinet(self, auth_client_factory, user_factory):
        """Тест удаления документа из кабинета."""
        user = user_factory()
        client = auth_client_factory(user)
        
        cabinet = Cabinet.objects.create(
            name='Cabinet',
            slug='cabinet',
            created_by=user
        )
        doc = make_document(uploaded_by=user)
        cabinet.documents.add(doc)
        
        url = reverse('api:v1:cabinets-remove-document', args=[cabinet.pk])
        response = client.post(url, {'document_id': doc.pk}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert not cabinet.documents.filter(pk=doc.pk).exists()
    
    def test_children_cabinets(self, auth_client_factory, user_factory):
        """Тест получения дочерних кабинетов."""
        user = user_factory()
        client = auth_client_factory(user)
        
        parent = Cabinet.objects.create(
            name='Parent',
            slug='parent',
            created_by=user
        )
        child = Cabinet.objects.create(
            name='Child',
            slug='child',
            created_by=user,
            parent=parent
        )
        
        url = reverse('api:v1:cabinets-children', args=[parent.pk])
        response = client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['name'] == 'Child'


# =============================================================================
# DOCUMENTCOMMENT VIEWSET TESTS
# =============================================================================

class TestDocumentCommentViewSet:
    """Тесты для DocumentCommentViewSet."""
    
    def test_create_comment(self, auth_client_factory, user_factory):
        """Тест создания комментария."""
        user = user_factory()
        client = auth_client_factory(user)
        
        doc = make_document(uploaded_by=user)
        
        url = reverse('api:v1:document-comments-list')
        data = {
            'document_id': doc.pk,
            'text': 'Test comment'
        }
        response = client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        comment = DocumentComment.objects.get(document=doc)
        assert comment.text == 'Test comment'
        assert comment.author == user
    
    def test_create_reply(self, auth_client_factory, user_factory):
        """Тест создания ответа на комментарий."""
        user = user_factory()
        client = auth_client_factory(user)
        
        doc = make_document(uploaded_by=user)
        parent = DocumentComment.objects.create(
            document=doc,
            author=user,
            text='Parent comment'
        )
        
        url = reverse('api:v1:document-comments-list')
        data = {
            'document_id': doc.pk,
            'parent_id': parent.pk,
            'text': 'Reply comment'
        }
        response = client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        reply = DocumentComment.objects.get(parent=parent)
        assert reply.text == 'Reply comment'
        assert reply.depth == 1
    
    def test_update_comment(self, auth_client_factory, user_factory):
        """Тест обновления комментария."""
        user = user_factory()
        client = auth_client_factory(user)
        
        doc = make_document(uploaded_by=user)
        comment = DocumentComment.objects.create(
            document=doc,
            author=user,
            text='Original text'
        )
        
        url = reverse('api:v1:document-comments-detail', args=[comment.pk])
        response = client.patch(url, {'text': 'Updated text'}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        comment.refresh_from_db()
        assert comment.text == 'Updated text'
        assert comment.is_edited is True
    
    def test_delete_own_comment(self, auth_client_factory, user_factory):
        """Тест удаления своего комментария."""
        user = user_factory()
        client = auth_client_factory(user)
        
        doc = make_document(uploaded_by=user)
        comment = DocumentComment.objects.create(
            document=doc,
            author=user,
            text='Test'
        )
        
        url = reverse('api:v1:document-comments-detail', args=[comment.pk])
        response = client.delete(url)
        
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not DocumentComment.objects.filter(pk=comment.pk).exists()
    
    def test_cannot_delete_others_comment(self, auth_client_factory, user_factory):
        """Тест запрета удаления чужого комментария."""
        user1 = user_factory()
        user2 = user_factory()
        client = auth_client_factory(user1)
        
        doc = make_document(uploaded_by=user1)
        comment = DocumentComment.objects.create(
            document=doc,
            author=user2,
            text='Test'
        )
        
        url = reverse('api:v1:document-comments-detail', args=[comment.pk])
        response = client.delete(url)
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_list_comment_replies(self, auth_client_factory, user_factory):
        """Тест получения ответов на комментарий."""
        user = user_factory()
        client = auth_client_factory(user)
        
        doc = make_document(uploaded_by=user)
        parent = DocumentComment.objects.create(
            document=doc,
            author=user,
            text='Parent'
        )
        DocumentComment.objects.create(
            document=doc,
            author=user,
            text='Reply 1',
            parent=parent
        )
        DocumentComment.objects.create(
            document=doc,
            author=user,
            text='Reply 2',
            parent=parent
        )
        
        url = reverse('api:v1:document-comments-replies', args=[parent.pk])
        response = client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2


# =============================================================================
# RELATED DOCUMENTS TESTS
# =============================================================================

class TestRelatedDocuments:
    """Тесты для связанных документов."""
    
    def test_add_related_document(self, auth_client_factory, user_factory):
        """Тест добавления связанного документа."""
        user = user_factory()
        client = auth_client_factory(user)
        
        doc = make_document(uploaded_by=user, title='Main Doc')
        related_doc = make_document(uploaded_by=user, title='Related Doc')
        
        url = reverse('api:v1:documents-add-related', args=[doc.pk])
        response = client.post(url, {'document_id': related_doc.pk}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert doc.related_documents.filter(pk=related_doc.pk).exists()
    
    def test_list_related_documents(self, auth_client_factory, user_factory):
        """Тест получения списка связанных документов."""
        user = user_factory()
        client = auth_client_factory(user)
        
        doc = make_document(uploaded_by=user, title='Main Doc')
        related_doc = make_document(uploaded_by=user, title='Related Doc')
        doc.related_documents.add(related_doc)
        
        url = reverse('api:v1:documents-related', args=[doc.pk])
        response = client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
    
    def test_remove_related_document(self, auth_client_factory, user_factory):
        """Тест удаления связанного документа."""
        user = user_factory()
        client = auth_client_factory(user)
        
        doc = make_document(uploaded_by=user)
        related_doc = make_document(uploaded_by=user)
        doc.related_documents.add(related_doc)
        
        url = reverse('api:v1:documents-remove-related', args=[doc.pk])
        response = client.post(url, {'document_id': related_doc.pk}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert not doc.related_documents.filter(pk=related_doc.pk).exists()
    
    def test_cannot_link_to_self(self, auth_client_factory, user_factory):
        """Тест запрета связывания документа с самим собой."""
        user = user_factory()
        client = auth_client_factory(user)
        
        doc = make_document(uploaded_by=user)
        
        url = reverse('api:v1:documents-add-related', args=[doc.pk])
        response = client.post(url, {'document_id': doc.pk}, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# DJANGO-REVERSION TESTS
# =============================================================================

class TestReversionEndpoints:
    """Тесты для endpoints django-reversion."""
    
    def test_get_versions(self, auth_client_factory, user_factory):
        """Тест получения истории версий."""
        user = user_factory()
        client = auth_client_factory(user)
        
        doc = make_document(uploaded_by=user)
        # Создаём версию через изменение
        doc.title = 'Updated Title'
        doc.save()
        
        url = reverse('api:v1:documents-versions', args=[doc.pk])
        response = client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)
    
    def test_get_activity(self, auth_client_factory, user_factory):
        """Тест получения activity timeline."""
        user = user_factory()
        client = auth_client_factory(user)
        
        doc = make_document(uploaded_by=user)
        
        url = reverse('api:v1:documents-activity', args=[doc.pk])
        response = client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)


# =============================================================================
# EDGE CASES И ПРОБЛЕМНЫЕ СЦЕНАРИИ
# =============================================================================

class TestEdgeCases:
    """Тесты edge cases и потенциальных проблем."""
    
    def test_tag_with_long_name(self, auth_client_factory, user_factory):
        """Тест создания тега с очень длинным названием."""
        user = user_factory()
        client = auth_client_factory(user)
        
        url = reverse('api:v1:document-tags-list')
        data = {
            'name': 'A' * 101,  # Превышает максимум 100
            'slug': 'long-tag'
        }
        response = client.post(url, data, format='json')
        
        # Должна быть ошибка валидации
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_duplicate_tag_slug(self, auth_client_factory, user_factory):
        """Тест создания тега с дубликатом slug."""
        user = user_factory()
        client = auth_client_factory(user)
        
        DocumentTag.objects.create(name='Tag1', slug='same-slug')
        
        url = reverse('api:v1:document-tags-list')
        data = {
            'name': 'Tag2',
            'slug': 'same-slug'
        }
        response = client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_comment_on_nonexistent_document(self, auth_client_factory, user_factory):
        """Тест создания комментария к несуществующему документу."""
        user = user_factory()
        client = auth_client_factory(user)
        
        url = reverse('api:v1:document-comments-list')
        data = {
            'document_id': 99999,  # Несуществующий ID
            'text': 'Test'
        }
        response = client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_reply_to_wrong_document_comment(self, auth_client_factory, user_factory):
        """Тест ответа на комментарий из другого документа."""
        user = user_factory()
        client = auth_client_factory(user)
        
        doc1 = make_document(uploaded_by=user, title='Doc1')
        doc2 = make_document(uploaded_by=user, title='Doc2')
        
        comment_doc1 = DocumentComment.objects.create(
            document=doc1,
            author=user,
            text='Comment'
        )
        
        url = reverse('api:v1:document-comments-list')
        data = {
            'document_id': doc2.pk,  # Другой документ
            'parent_id': comment_doc1.pk,  # Комментарий из doc1
            'text': 'Reply'
        }
        response = client.post(url, data, format='json')
        
        # Должна быть ошибка, т.к. parent из другого документа
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_nested_comments_depth(self, auth_client_factory, user_factory):
        """Тест глубоко вложенных комментариев."""
        user = user_factory()
        client = auth_client_factory(user)
        
        doc = make_document(uploaded_by=user)
        
        # Создаём цепочку из 5 уровней
        parent = None
        for i in range(5):
            comment = DocumentComment.objects.create(
                document=doc,
                author=user,
                text=f'Level {i}',
                parent=parent
            )
            parent = comment
        
        # Проверяем depth последнего комментария
        assert parent.depth == 4
    
    def test_empty_comment_text(self, auth_client_factory, user_factory):
        """Тест создания комментария с пустым текстом."""
        user = user_factory()
        client = auth_client_factory(user)
        
        doc = make_document(uploaded_by=user)
        
        url = reverse('api:v1:document-comments-list')
        data = {
            'document_id': doc.pk,
            'text': ''  # Пустой текст
        }
        response = client.post(url, data, format='json')
        
        # Должна быть ошибка валидации
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_related_document_symmetry(self, auth_client_factory, user_factory):
        """Тест симметричности связанных документов."""
        user = user_factory()
        client = auth_client_factory(user)
        
        doc1 = make_document(uploaded_by=user, title='Doc1')
        doc2 = make_document(uploaded_by=user, title='Doc2')
        
        # Добавляем doc2 как связанный с doc1
        doc1.related_documents.add(doc2)
        
        # Проверяем, что doc1 тоже связан с doc2 (symmetrical=True)
        assert doc2.related_documents.filter(pk=doc1.pk).exists()
    
    def test_empty_cabinet_name(self, auth_client_factory, user_factory):
        """Тест создания кабинета с пустым названием."""
        user = user_factory()
        client = auth_client_factory(user)
        
        url = reverse('api:v1:cabinets-list')
        data = {
            'name': '',
            'slug': 'empty'
        }
        response = client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
    
    def test_add_nonexistent_document_to_cabinet(self, auth_client_factory, user_factory):
        """Тест добавления несуществующего документа в кабинет."""
        user = user_factory()
        client = auth_client_factory(user)
        
        cabinet = Cabinet.objects.create(
            name='Cabinet',
            slug='cabinet',
            created_by=user
        )
        
        url = reverse('api:v1:cabinets-add-document', args=[cabinet.pk])
        response = client.post(url, {'document_id': 99999}, format='json')
        
        # 404 более правильный статус для несуществующего ресурса
        assert response.status_code == status.HTTP_404_NOT_FOUND
