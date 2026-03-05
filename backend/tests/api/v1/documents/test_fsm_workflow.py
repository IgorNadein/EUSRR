"""
Unit tests: Document FSM Workflow

Проверяет все переходы FSM состояний документа через API.
"""

import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from documents.models import Document
from tests.api.v1.documents.test_documents_api import make_document

pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    """API клиент."""
    return APIClient()


@pytest.fixture
def grant_permissions(db):
    """Хелпер для выдачи прав."""
    def _grant(user, *perm_codenames):
        perms = Permission.objects.filter(codename__in=perm_codenames)
        user.user_permissions.add(*perms)
        user.refresh_from_db()
    return _grant


def make_document_with_status(uploaded_by, status):
    """Создает документ с указанным статусом (обходит FSM protected).
    
    Args:
        uploaded_by: Пользователь-автор
        status: Нужный статус (строка)
        
    Returns:
        Document: Документ с установленным статусом
    """
    doc = make_document(uploaded_by=uploaded_by)
    # Обходим FSM protected=True для тестов
    Document.objects.filter(pk=doc.pk).update(status=status)
    return Document.objects.get(pk=doc.pk)


class TestFSMTransitions:
    """Тесты FSM переходов документа."""
    
    def test_submit_for_review_draft_to_in_review(
        self, api_client, make_user, grant_permissions
    ):
        """draft → in_review через submit_for_review."""
        user = make_user("author@example.com")
        grant_permissions(user, 'change_document')
        
        doc = make_document_with_status(uploaded_by=user, status='draft')
        assert doc.status == 'draft'
        
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:documents-submit-for-review', kwargs={'pk': doc.id})
        response = api_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        doc = Document.objects.get(pk=doc.id)
        assert doc.status == 'in_review'
    
    def test_approve_in_review_to_approved(
        self, api_client, make_user, grant_permissions
    ):
        """in_review → approved через approve."""
        approver = make_user("approver@example.com")
        grant_permissions(approver, 'change_document')
        
        doc = make_document_with_status(uploaded_by=approver, status='in_review')
        
        api_client.force_authenticate(user=approver)
        url = reverse('api:v1:documents-approve', kwargs={'pk': doc.id})
        response = api_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        doc = Document.objects.get(pk=doc.id)
        assert doc.status == 'approved'
    
    def test_reject_in_review_to_rejected(
        self, api_client, make_user, grant_permissions
    ):
        """in_review → rejected через reject."""
        approver = make_user("approver@example.com")
        grant_permissions(approver, 'change_document')
        
        doc = make_document_with_status(uploaded_by=approver, status='in_review')
        
        api_client.force_authenticate(user=approver)
        url = reverse('api:v1:documents-reject', kwargs={'pk': doc.id})
        response = api_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        doc = Document.objects.get(pk=doc.id)
        assert doc.status == 'rejected'
    
    def test_publish_approved_to_published(
        self, api_client, make_user, grant_permissions
    ):
        """approved → published через publish."""
        publisher = make_user("publisher@example.com")
        grant_permissions(publisher, 'change_document')
        
        doc = make_document_with_status(uploaded_by=publisher, status='approved')
        
        api_client.force_authenticate(user=publisher)
        url = reverse('api:v1:documents-publish', kwargs={'pk': doc.id})
        response = api_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        doc = Document.objects.get(pk=doc.id)
        assert doc.status == 'published'
    
    def test_archive_published_to_archived(
        self, api_client, make_user, grant_permissions
    ):
        """published → archived через archive."""
        archiver = make_user("archiver@example.com")
        grant_permissions(archiver, 'change_document')
        
        doc = make_document_with_status(uploaded_by=archiver, status='published')
        
        api_client.force_authenticate(user=archiver)
        url = reverse('api:v1:documents-archive', kwargs={'pk': doc.id})
        response = api_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        doc = Document.objects.get(pk=doc.id)
        assert doc.status == 'archived'
    
    def test_unarchive_archived_to_published(
        self, api_client, make_user, grant_permissions
    ):
        """archived → published через unarchive."""
        unarchiver = make_user("unarchiver@example.com")
        grant_permissions(unarchiver, 'change_document')
        
        doc = make_document_with_status(uploaded_by=unarchiver, status='archived')
        
        api_client.force_authenticate(user=unarchiver)
        url = reverse('api:v1:documents-unarchive', kwargs={'pk': doc.id})
        response = api_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        doc = Document.objects.get(pk=doc.id)
        assert doc.status == 'published'
    
    def test_return_to_draft_in_review_to_draft(
        self, api_client, make_user, grant_permissions
    ):
        """in_review → draft через return_to_draft."""
        editor = make_user("editor@example.com")
        grant_permissions(editor, 'change_document')
        
        doc = make_document_with_status(uploaded_by=editor, status='in_review')
        
        api_client.force_authenticate(user=editor)
        url = reverse('api:v1:documents-return-to-draft', kwargs={'pk': doc.id})
        response = api_client.post(url)
        
        assert response.status_code == status.HTTP_200_OK
        doc = Document.objects.get(pk=doc.id)
        assert doc.status == 'draft'


class TestFSMInvalidTransitions:
    """Тесты невалидных переходов FSM."""
    
    def test_cannot_approve_draft(
        self, api_client, make_user, grant_permissions
    ):
        """Нельзя approve документ в состоянии draft."""
        user = make_user("user@example.com")
        grant_permissions(user, 'change_document')
        
        doc = make_document_with_status(uploaded_by=user, status='draft')
        
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:documents-approve', kwargs={'pk': doc.id})
        response = api_client.post(url)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        doc = Document.objects.get(pk=doc.id)
        assert doc.status == 'draft'  # Не изменился
    
    def test_cannot_publish_draft(
        self, api_client, make_user, grant_permissions
    ):
        """Нельзя publish документ в состоянии draft."""
        user = make_user("user@example.com")
        grant_permissions(user, 'change_document')
        
        doc = make_document_with_status(uploaded_by=user, status='draft')
        
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:documents-publish', kwargs={'pk': doc.id})
        response = api_client.post(url)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        doc = Document.objects.get(pk=doc.id)
        assert doc.status == 'draft'
    
    def test_cannot_archive_draft(
        self, api_client, make_user, grant_permissions
    ):
        """Нельзя archive документ в состоянии draft."""
        user = make_user("user@example.com")
        grant_permissions(user, 'change_document')
        
        doc = make_document_with_status(uploaded_by=user, status='draft')
        
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:documents-archive', kwargs={'pk': doc.id})
        response = api_client.post(url)
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        doc = Document.objects.get(pk=doc.id)
        assert doc.status == 'draft'


class TestFSMPermissions:
    """Тесты проверки прав доступа для FSM действий."""
    
    def test_submit_requires_change_permission(
        self, api_client, make_user
    ):
        """submit_for_review требует change_document."""
        owner = make_user("owner@example.com")
        user = make_user("user@example.com")
        doc = make_document_with_status(uploaded_by=owner, status='draft')
        
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:documents-submit-for-review', kwargs={'pk': doc.id})
        response = api_client.post(url)
        
        # Без прав - 403 или 404 (зависит от queryset filtering)
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_approve_requires_change_permission(
        self, api_client, make_user
    ):
        """approve требует change_document."""
        owner = make_user("owner@example.com")
        user = make_user("user@example.com")
        doc = make_document_with_status(uploaded_by=owner, status='in_review')
        
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:documents-approve', kwargs={'pk': doc.id})
        response = api_client.post(url)
        
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_publish_requires_change_permission(
        self, api_client, make_user
    ):
        """publish требует change_document."""
        owner = make_user("owner@example.com")
        user = make_user("user@example.com")
        doc = make_document_with_status(uploaded_by=owner, status='approved')
        
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:documents-publish', kwargs={'pk': doc.id})
        response = api_client.post(url)
        
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_archive_requires_change_permission(
        self, api_client, make_user
    ):
        """archive требует change_document."""
        owner = make_user("owner@example.com")
        user = make_user("user@example.com")
        doc = make_document_with_status(uploaded_by=owner, status='published')
        
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:documents-archive', kwargs={'pk': doc.id})
        response = api_client.post(url)
        
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ]
    
    def test_unauthenticated_cannot_change_status(
        self, api_client, make_user
    ):
        """Неаутентифицированный пользователь не может менять статус."""
        user = make_user("user@example.com")
        doc = make_document_with_status(uploaded_by=user, status='draft')
        
        # Без аутентификации
        url = reverse('api:v1:documents-submit-for-review', kwargs={'pk': doc.id})
        response = api_client.post(url)
        
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        doc = Document.objects.get(pk=doc.id)
        assert doc.status == 'draft'


class TestFullWorkflowCycle:
    """Тест полного цикла документа через все состояния."""
    
    def test_complete_document_lifecycle(
        self, api_client, make_user, grant_permissions
    ):
        """Полный жизненный цикл: draft → in_review → approved → published → archived → published."""
        user = make_user("admin@example.com")
        grant_permissions(user, 'change_document')
        api_client.force_authenticate(user=user)
        
        # 1. Создаем документ (draft)
        doc = make_document_with_status(uploaded_by=user, status='draft')
        assert doc.status == 'draft'
        
        # 2. Отправляем на проверку
        url = reverse('api:v1:documents-submit-for-review', kwargs={'pk': doc.id})
        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        doc = Document.objects.get(pk=doc.id)
        assert doc.status == 'in_review'
        
        # 3. Утверждаем
        url = reverse('api:v1:documents-approve', kwargs={'pk': doc.id})
        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        doc = Document.objects.get(pk=doc.id)
        assert doc.status == 'approved'
        
        # 4. Публикуем
        url = reverse('api:v1:documents-publish', kwargs={'pk': doc.id})
        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        doc = Document.objects.get(pk=doc.id)
        assert doc.status == 'published'
        
        # 5. Архивируем
        url = reverse('api:v1:documents-archive', kwargs={'pk': doc.id})
        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        doc = Document.objects.get(pk=doc.id)
        assert doc.status == 'archived'
        
        # 6. Разархивируем
        url = reverse('api:v1:documents-unarchive', kwargs={'pk': doc.id})
        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        doc = Document.objects.get(pk=doc.id)
        assert doc.status == 'published'


# =============================================================================
# DJANGO-RULES: Author Permissions Tests
# =============================================================================

@pytest.mark.django_db
class TestAuthorCanSubmitOwnDocument:
    """Тесты проверки что автор может отправить СВОЙ документ на рассмотрение
    через django-rules (без модельного права change_document)."""
    
    def test_author_can_submit_own_document_without_model_permission(
        self, api_client, make_user
    ):
        """Автор БЕЗ модельного права change_document может отправить 
        свой документ на рассмотрение (через django-rules is_document_uploader)."""
        from documents.models import Document
        
        author = make_user("author@example.com", staff=False)
        
        # Создаем документ в draft явно
        doc = make_document(uploaded_by=author, status=Document.Status.DRAFT)
        assert doc.status == Document.Status.DRAFT
        assert doc.uploaded_by == author
        
        # Автор БЕЗ модельного права должен иметь возможность submit_for_review
        # благодаря django-rules: is_document_uploader
        api_client.force_authenticate(user=author)
        url = reverse('api:v1:documents-submit-for-review', kwargs={'pk': doc.id})
        response = api_client.post(url)
        
        # Должно работать!
        assert response.status_code == status.HTTP_200_OK, \
            f"Expected 200, got {response.status_code}. Author should be able to submit own document via django-rules"
        
        # Перечитываем из БД
        doc = Document.objects.get(pk=doc.id)
        assert doc.status == Document.Status.IN_REVIEW
    
    def test_regular_user_cannot_submit_others_document(
        self, api_client, make_user
    ):
        """Обычный пользователь НЕ может отправить чужой документ на рассмотрение."""
        from documents.models import Document
        
        author = make_user("author@example.com")
        other_user = make_user("other@example.com", staff=False)
        
        # Документ автора в draft
        doc = make_document(uploaded_by=author, status=Document.Status.DRAFT)
        assert doc.status == Document.Status.DRAFT
        
        # Другой пользователь не должен иметь доступ
        api_client.force_authenticate(user=other_user)
        url = reverse('api:v1:documents-submit-for-review', kwargs={'pk': doc.id})
        response = api_client.post(url)
        
        # 404 (документ не в queryset) или 403 (нет прав)
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ], f"Expected 403/404, got {response.status_code}"
        
        # Статус не должен измениться
        doc = Document.objects.get(pk=doc.id)
        assert doc.status == Document.Status.DRAFT, "Status should not change"
    
    def test_author_can_edit_own_draft_document(
        self, api_client, make_user
    ):
        """Автор может редактировать свой черновик."""
        from documents.models import Document
        
        author = make_user("author@example.com", staff=False)
        
        # Создаем документ в draft
        doc = make_document(uploaded_by=author, title='Original Title', status=Document.Status.DRAFT)
        assert doc.title == 'Original Title'
        assert doc.status == Document.Status.DRAFT
        
        api_client.force_authenticate(user=author)
        url = reverse('api:v1:documents-detail', kwargs={'pk': doc.id})
        response = api_client.patch(url, {'title': 'Updated Title'}, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Перечитываем документ из БД
        doc = Document.objects.get(pk=doc.id)
        assert doc.title == 'Updated Title'
    
    def test_author_cannot_approve_own_document(
        self, api_client, make_user
    ):
        """КРИТИЧНО: Автор НЕ может одобрить свой документ (разделение обязанностей!)"""
        from documents.models import Document
        
        author = make_user("author@example.com", staff=False)
        
        # Создаем документ и отправляем на рассмотрение
        doc = make_document(uploaded_by=author, status=Document.Status.DRAFT)
        
        # Автор отправляет на рассмотрение - это ОК
        api_client.force_authenticate(user=author)
        url = reverse('api:v1:documents-submit-for-review', kwargs={'pk': doc.id})
        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        
        # Проверяем что статус изменился
        doc = Document.objects.get(pk=doc.id)
        assert doc.status == Document.Status.IN_REVIEW
        
        # Теперь автор пытается ОДОБРИТЬ свой документ - должно быть запрещено!
        url = reverse('api:v1:documents-approve', kwargs={'pk': doc.id})
        response = api_client.post(url)
        
        # Должен получить 403 ИЛИ 400 (FSM не разрешает или нет прав)
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_400_BAD_REQUEST
        ], f"Author should NOT be able to approve own document! Got {response.status_code}"
        
        # Статус НЕ должен измениться
        doc = Document.objects.get(pk=doc.id)
        assert doc.status == Document.Status.IN_REVIEW, "Status should remain IN_REVIEW"
    
    def test_author_cannot_publish_own_document(
        self, api_client, make_user
    ):
        """КРИТИЧНО: Автор НЕ может опубликовать свой документ (разделение обязанностей!)"""
        from documents.models import Document
        
        author = make_user("author@example.com", staff=False)
        
        # Создаем документ в статусе APPROVED (как будто менеджер одобрил)
        doc = make_document_with_status(uploaded_by=author, status='approved')
        doc = Document.objects.get(pk=doc.id)
        assert doc.status == Document.Status.APPROVED
        
        # Автор пытается ОПУБЛИКОВАТЬ - должно быть запрещено!
        api_client.force_authenticate(user=author)
        url = reverse('api:v1:documents-publish', kwargs={'pk': doc.id})
        response = api_client.post(url)
        
        # Должен получить 403 ИЛИ 400
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_400_BAD_REQUEST
        ], f"Author should NOT be able to publish own document! Got {response.status_code}"
        
        # Статус НЕ должен измениться
        doc = Document.objects.get(pk=doc.id)
        assert doc.status == Document.Status.APPROVED, "Status should remain APPROVED"
