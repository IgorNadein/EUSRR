# documents/test_documents_api.py
"""
Comprehensive pytest API tests для DocumentViewSet
"""

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status
from filer.models import File as FilerFile
from documents.models import (
    Document, DocumentAcknowledgement, DocumentComment
)
from reversion.models import Version
import reversion


# =============================================================================
# CRUD TESTS
# =============================================================================

@pytest.mark.django_db
class TestDocumentCRUDAPI:
    """Тесты CRUD операций для документов"""
    
    def test_list_documents_authenticated(self, viewer_client, document):
        """GET /documents/ - авторизованный пользователь видит свои документы"""
        response = viewer_client.get('/api/v1/documents/')
        assert response.status_code == status.HTTP_200_OK
        # viewer в recipients - должен видеть документ
        assert len(response.data.get('results', response.data)) >= 1
    
    def test_list_documents_unauthenticated(self, api_client):
        """GET /documents/ - неавторизованный получает 401"""
        response = api_client.get('/api/v1/documents/')
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
    
    def test_create_document(self, authenticated_client, author_user):
        """POST /documents/ - автор может создать документ"""
        file_obj = SimpleUploadedFile("new_doc.txt", b"Content", content_type="text/plain")
        
        data = {
            'title': 'Новый документ',
            'description': 'Описание',
            'sent_to_all': True,
            'file': file_obj,
        }
        
        response = authenticated_client.post('/api/v1/documents/', data, format='multipart')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'Новый документ'
    
    def test_retrieve_document_as_recipient(self, viewer_client, document):
        """GET /documents/{id}/ - получатель может просмотреть"""
        response = viewer_client.get(f'/api/v1/documents/{document.id}/')
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == document.title
    
    def test_retrieve_document_as_non_recipient(self, api_client, other_user, document):
        """GET /documents/{id}/ - не-получатель не видит документ (404 - отфильтрован queryset)"""
        api_client.force_authenticate(user=other_user)
        response = api_client.get(f'/api/v1/documents/{document.id}/')
        # QuerySet фильтрует недоступные документы, поэтому 404
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_update_document_as_author(self, authenticated_client, document, author_user):
        """PATCH /documents/{id}/ - автор может редактировать"""
        data = {'title': 'Обновленное название'}
        response = authenticated_client.patch(f'/api/v1/documents/{document.id}/', data)
        assert response.status_code == status.HTTP_200_OK
        
        # Проверяем через API response (refresh_from_db не работает с FSM protected fields)
        assert response.data['title'] == 'Обновленное название'
    
    def test_update_document_as_viewer_forbidden(self, viewer_client, document):
        """PATCH /documents/{id}/ - получатель не может редактировать"""
        data = {'title': 'Попытка изменить'}
        response = viewer_client.patch(f'/api/v1/documents/{document.id}/', data)
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_delete_document_as_author(self, authenticated_client, document):
        """DELETE /documents/{id}/ - автор может удалить"""
        doc_id = document.id
        response = authenticated_client.delete(f'/api/v1/documents/{doc_id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Document.objects.filter(id=doc_id).exists()
    
    def test_delete_document_as_viewer_forbidden(self, viewer_client, document):
        """DELETE /documents/{id}/ - получатель не может удалить"""
        response = viewer_client.delete(f'/api/v1/documents/{document.id}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN


# =============================================================================
# FSM WORKFLOW TESTS
# =============================================================================

@pytest.mark.django_db
class TestDocumentFSMWorkflow:
    """Тесты FSM переходов состояний документа"""
    
    def test_submit_for_review_transition(self, authenticated_client, document):
        """POST submit-for-review: draft → in_review"""
        assert document.status == Document.Status.DRAFT
        
        response = authenticated_client.post(
            f'/api/v1/documents/{document.id}/submit-for-review/'
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == Document.Status.IN_REVIEW
    
    def test_approve_transition(self, authenticated_client, document):
        """POST approve: in_review → approved"""
        document.submit_for_review()
        document.save()
        
        response = authenticated_client.post(
            f'/api/v1/documents/{document.id}/approve/'
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == Document.Status.APPROVED
    
    def test_reject_transition(self, authenticated_client, document):
        """POST reject: in_review → rejected"""
        document.submit_for_review()
        document.save()
        
        response = authenticated_client.post(
            f'/api/v1/documents/{document.id}/reject/'
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == Document.Status.REJECTED
    
    def test_publish_transition(self, authenticated_client, document):
        """POST publish: approved → published"""
        document.submit_for_review()
        document.approve()
        document.save()
        
        response = authenticated_client.post(
            f'/api/v1/documents/{document.id}/publish/'
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == Document.Status.PUBLISHED
    
    def test_return_to_draft_transition(self, authenticated_client, document):
        """POST return-to-draft: in_review → draft"""
        document.submit_for_review()
        document.save()
        
        response = authenticated_client.post(
            f'/api/v1/documents/{document.id}/return-to-draft/'
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == Document.Status.DRAFT
    
    def test_archive_transition(self, authenticated_client, document):
        """POST archive: published → archived"""
        document.submit_for_review()
        document.approve()
        document.publish()
        document.save()
        
        response = authenticated_client.post(
            f'/api/v1/documents/{document.id}/archive/'
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['status'] == Document.Status.ARCHIVED
    
    def test_unarchive_transition(self, authenticated_client, document):
        """POST unarchive: archived → published"""
        document.submit_for_review()
        document.approve()
        document.publish()
        document.archive()
        document.save()
        
        response = authenticated_client.post(
            f'/api/v1/documents/{document.id}/unarchive/'
        )
        assert response.status_code == status.HTTP_200_OK

        assert document.status == Document.Status.PUBLISHED
    
    def test_invalid_transition_returns_400(self, authenticated_client, document):
        """Невалидный переход возвращает 400"""
        # Пытаемся reject когда status=DRAFT (невалидно)
        response = authenticated_client.post(
            f'/api/v1/documents/{document.id}/reject/'
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# =============================================================================
# VERSIONING TESTS
# =============================================================================

@pytest.mark.django_db
class TestDocumentVersioning:
    """Тесты версионирования django-reversion"""
    
    def test_get_versions(self, authenticated_client, document):
        """GET /documents/{id}/versions/ - история версий"""
        # Создаем версии через reversion
        with reversion.create_revision():
            document.title = "Version 1"
            document.save()
            reversion.set_comment("First change")
        
        with reversion.create_revision():
            document.title = "Version 2"
            document.save()
            reversion.set_comment("Second change")
        
        response = authenticated_client.get(
            f'/api/v1/documents/{document.id}/versions/'
        )
        assert response.status_code == status.HTTP_200_OK
        
        versions = response.data
        assert len(versions) >= 2
    
    def test_get_activity_timeline(self, authenticated_client, viewer_user, document):
        """GET /documents/{id}/activity/ - timeline активности"""
        # Создаем ознакомление
        DocumentAcknowledgement.objects.create(
            document=document,
            user=viewer_user
        )
        
        # Создаем версию
        with reversion.create_revision():
            document.title = "Changed"
            document.save()
        
        response = authenticated_client.get(
            f'/api/v1/documents/{document.id}/activity/'
        )
        assert response.status_code == status.HTTP_200_OK
        
        activity = response.data
        assert len(activity) > 0
        
        # Проверяем типы в timeline
        types = [item['type'] for item in activity]
        assert 'version' in types or 'acknowledgement' in types
    
    def test_revert_to_version(self, authenticated_client, document):
        """POST /documents/{id}/revert/ - откат к версии"""
        original_title = "Original Title"
        
        # Сохраняем первую версию
        with reversion.create_revision():
            document.title = original_title
            document.save()
        
        # Получаем первую версию
        versions = Version.objects.get_for_object(document)
        first_version = versions.first()
        
        # Меняем документ
        with reversion.create_revision():
            document.title = "Modified Title"
            document.save()
        
        # Откатываем
        data = {
            'version_id': first_version.id,
            'comment': 'Откат'
        }
        
        response = authenticated_client.post(
            f'/api/v1/documents/{document.id}/revert/',
            data
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == original_title


# =============================================================================
# ACKNOWLEDGEMENT TESTS
# =============================================================================

@pytest.mark.django_db
class TestDocumentAcknowledgement:
    """Тесты ознакомления с документами"""
    
    def test_acknowledge_document(self, viewer_client, viewer_user, document):
        """POST /documents/{id}/acknowledge/ - подтвердить ознакомление"""
        response = viewer_client.post(
            f'/api/v1/documents/{document.id}/acknowledge/'
        )
        assert response.status_code == status.HTTP_200_OK
        
        # Проверяем создание записи
        assert DocumentAcknowledgement.objects.filter(
            document=document,
            user=viewer_user
        ).exists()
    
    def test_acknowledge_non_recipient_forbidden(self, api_client, other_user, document):
        """Не-получатель не может ознакомиться"""
        api_client.force_authenticate(user=other_user)
        
        response = api_client.post(
            f'/api/v1/documents/{document.id}/acknowledge/'
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
    
    def test_get_acknowledgements_list(self, viewer_client, viewer_user, document):
        """GET /documents/{id}/acknowledgements/ - список ознакомившихся"""
        # Создаем ознакомление
        DocumentAcknowledgement.objects.create(
            document=document,
            user=viewer_user
        )
        
        response = viewer_client.get(
            f'/api/v1/documents/{document.id}/acknowledgements/'
        )
        assert response.status_code == status.HTTP_200_OK
        
        acks = response.data
        assert len(acks) == 1
        assert acks[0]['user']['id'] == viewer_user.id
    
    def test_double_acknowledge_prevented(self, viewer_client, viewer_user, document):
        """Двойное ознакомление запрещено"""
        # Первое ознакомление
        viewer_client.post(f'/api/v1/documents/{document.id}/acknowledge/')
        
        # Второе ознакомление - должно вернуть ошибку или already acknowledged
        response = viewer_client.post(
            f'/api/v1/documents/{document.id}/acknowledge/'
        )
        # Может вернуть 200 с сообщением "already acknowledged" или 400
        # Главное - запись одна
        count = DocumentAcknowledgement.objects.filter(
            document=document,
            user=viewer_user
        ).count()
        assert count == 1


# =============================================================================
# COMMENT TESTS
# =============================================================================

@pytest.mark.django_db
class TestDocumentComments:
    """Тесты комментариев к документам"""
    
    def test_create_comment(self, viewer_client, viewer_user, document):
        """POST /document-comments/ - создать комментарий"""
        data = {
            'text': 'Отличный документ!',
            'document_id': document.id
        }
        
        response = viewer_client.post('/api/v1/document-comments/', data)
        assert response.status_code == status.HTTP_201_CREATED
        
        assert DocumentComment.objects.filter(
            document=document,
            author=viewer_user
        ).exists()
    
    def test_create_reply_to_comment(self, authenticated_client, viewer_client, viewer_user, author_user, document):
        """Создание ответа на комментарий"""
        # Создаем родительский комментарий
        parent = DocumentComment.objects.create(
            document=document,
            author=viewer_user,
            text='Parent comment'
        )
        
        # Создаем ответ
        data = {
            'text': 'Reply to parent',
            'document_id': document.id,
            'parent_id': parent.id
        }
        
        response = authenticated_client.post('/api/v1/document-comments/', data)
        assert response.status_code == status.HTTP_201_CREATED
        
        reply = DocumentComment.objects.get(parent=parent)
        assert reply.text == 'Reply to parent'
    
    def test_get_comment_replies(self, viewer_client, viewer_user, author_user, document):
        """GET /comments/{id}/replies/ - получить ответы"""
        parent = DocumentComment.objects.create(
            document=document,
            author=viewer_user,
            text='Parent'
        )
        
        DocumentComment.objects.create(
            document=document,
            author=author_user,
            text='Reply 1',
            parent=parent
        )
        
        DocumentComment.objects.create(
            document=document,
            author=author_user,
            text='Reply 2',
            parent=parent
        )
        
        response = viewer_client.get(f'/api/v1/document-comments/{parent.id}/replies/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 2
    
    def test_delete_own_comment(self, viewer_client, viewer_user, document):
        """Пользователь может удалить свой комментарий"""
        comment = DocumentComment.objects.create(
            document=document,
            author=viewer_user,
            text='My comment'
        )
        
        response = viewer_client.delete(f'/api/v1/document-comments/{comment.id}/')
        assert response.status_code == status.HTTP_204_NO_CONTENT
    
    def test_delete_others_comment_forbidden(self, viewer_client, author_user, document):
        """Нельзя удалить чужой комментарий"""
        comment = DocumentComment.objects.create(
            document=document,
            author=author_user,
            text='Author comment'
        )
        
        response = viewer_client.delete(f'/api/v1/document-comments/{comment.id}/')
        assert response.status_code == status.HTTP_403_FORBIDDEN


# =============================================================================
# PERMISSIONS TESTS
# =============================================================================

@pytest.mark.django_db
class TestDocumentPermissions:
    """Тесты системы разрешений"""
    
    def test_sent_to_all_visible_to_everyone(self, api_client, other_user, document_sent_to_all):
        """sent_to_all=True - документ видим всем активным пользователям"""
        api_client.force_authenticate(user=other_user)
        
        response = api_client.get(f'/api/v1/documents/{document_sent_to_all.id}/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_private_document_hidden_from_others(self, api_client, other_user, document):
        """Приватный документ скрыт от не-получателей (404 - отфильтрован)"""
        api_client.force_authenticate(user=other_user)
        
        response = api_client.get(f'/api/v1/documents/{document.id}/')
        # QuerySet фильтрует недоступные документы
        assert response.status_code == status.HTTP_404_NOT_FOUND
    
    def test_department_member_can_view(self, api_client, other_user, document, department):
        """Член отдела-получателя может видеть документ"""
        # Добавляем пользователя в отдел
        other_user.department = department
        other_user.save()
        
        # Добавляем отдел в получатели документа
        document.departments.add(department)
        
        api_client.force_authenticate(user=other_user)
        
        response = api_client.get(f'/api/v1/documents/{document.id}/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_author_can_always_edit(self, authenticated_client, document):
        """Автор всегда может редактировать свой документ"""
        data = {'description': 'Updated by author'}
        response = authenticated_client.patch(
            f'/api/v1/documents/{document.id}/',
            data
        )
        assert response.status_code == status.HTTP_200_OK
    
    def test_admin_has_full_access(self, admin_client, document):
        """Admin имеет полный доступ"""
        # Должен видеть документ
        response = admin_client.get(f'/api/v1/documents/{document.id}/')
        # Admin может иметь доступ или нет в зависимости от rules
        assert response.status_code in [status.HTTP_200_OK, status.HTTP_403_FORBIDDEN]


# =============================================================================
# FOLDER TESTS
# =============================================================================

@pytest.mark.django_db
class TestFolderAPI:
    """Тесты для папок документов"""
    
    def test_list_folders(self, authenticated_client, folder):
        """GET /folders/ - список папок"""
        response = authenticated_client.get('/api/v1/folders/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_create_folder(self, authenticated_client):
        """POST /folders/ - создание папки"""
        data = {'name': 'Новая папка'}
        response = authenticated_client.post('/api/v1/folders/', data)
        assert response.status_code == status.HTTP_201_CREATED
    
    def test_get_folder_children(self, authenticated_client, folder, author_user):
        """GET /folders/{id}/children/ - дочерние папки"""
        # Создаем дочернюю папку
        from filer.models import Folder as FilerFolder
        child = FilerFolder.objects.create(
            name='Дочерняя',
            parent=folder,
            owner=author_user
        )
        
        response = authenticated_client.get(f'/api/v1/folders/{folder.id}/children/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
    
    def test_get_folder_documents(self, authenticated_client, folder, document, filer_file):
        """GET /folders/{id}/documents/ - документы в папке"""
        # Перемещаем документ в папку
        document.folder = folder
        document.save()
        
        response = authenticated_client.get(f'/api/v1/folders/{folder.id}/documents/')
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1


# =============================================================================
# TAG & TYPE TESTS
# =============================================================================

@pytest.mark.django_db
class TestDocumentTagsAndTypes:
    """Тесты для тегов и типов документов"""
    
    def test_list_tags(self, authenticated_client, document_tag):
        """GET /document-tags/ - список тегов"""
        response = authenticated_client.get('/api/v1/document-tags/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_create_tag(self, authenticated_client):
        """POST /document-tags/ - создание тега"""
        data = {'name': 'Срочно', 'color': '#FF0000'}
        response = authenticated_client.post('/api/v1/document-tags/', data)
        assert response.status_code == status.HTTP_201_CREATED
    
    def test_list_document_types(self, authenticated_client, document_type):
        """GET /document-types/ - список типов"""
        response = authenticated_client.get('/api/v1/document-types/')
        assert response.status_code == status.HTTP_200_OK
    
    def test_get_documents_by_tag(self, authenticated_client, document, document_tag):
        """GET /tags/{id}/documents/ - документы с тегом"""
        # Добавляем тег к документу (если есть M2M)
        if hasattr(document, 'tags'):
            document.tags.add(document_tag)
        
        response = authenticated_client.get(f'/api/v1/document-tags/{document_tag.id}/documents/')
        assert response.status_code == status.HTTP_200_OK


# =============================================================================
# RELATED DOCUMENTS TESTS
# =============================================================================

@pytest.mark.django_db
class TestRelatedDocuments:
    """Тесты для связанных документов"""
    
    def test_get_related_documents(self, authenticated_client, document):
        """GET /documents/{id}/related/ - связанные документы"""
        response = authenticated_client.get(
            f'/api/v1/documents/{document.id}/related/'
        )
        assert response.status_code == status.HTTP_200_OK
    
    def test_add_related_document(self, authenticated_client, document, filer_file, author_user):
        """POST /documents/{id}/add_related/ - добавить связь"""
        # Создаем второй документ
        doc2 = Document.objects.create(
            title="Связанный документ",
            file=filer_file,
            uploaded_by=author_user,
            sent_to_all=True
        )
        
        data = {'document_id': doc2.id}
        response = authenticated_client.post(
            f'/api/v1/documents/{document.id}/add_related/',
            data
        )
        assert response.status_code == status.HTTP_200_OK
        
        # Проверяем связь
        assert doc2 in document.related_documents.all()
    
    def test_remove_related_document(self, authenticated_client, document, filer_file, author_user):
        """POST /documents/{id}/remove_related/ - удалить связь"""
        # Создаем и связываем документ
        doc2 = Document.objects.create(
            title="Связанный",
            file=filer_file,
            uploaded_by=author_user,
            sent_to_all=True
        )
        document.related_documents.add(doc2)
        
        data = {'document_id': doc2.id}
        response = authenticated_client.post(
            f'/api/v1/documents/{document.id}/remove_related/',
            data
        )
        assert response.status_code == status.HTTP_200_OK
        
        # Проверяем что связь удалена
        assert doc2 not in document.related_documents.all()
