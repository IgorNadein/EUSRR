"""
Тесты видимости документов в зависимости от статуса.

Проверяет, что обычные пользователи БЕЗ прав видят только:
1. Опубликованные документы (status=PUBLISHED)
2. Свои собственные документы в любом статусе
"""

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.utils import timezone
from rest_framework import status as http_status
from documents.models import Document
from filer.models import File
from io import BytesIO
from django.core.files.uploadedfile import SimpleUploadedFile


User = get_user_model()

pytestmark = pytest.mark.django_db


def _filer_file(owner=None, filename="test.pdf"):
    """Создает filer.File объект для тестирования."""
    content = BytesIO(b"fake pdf content")
    uploaded_file = SimpleUploadedFile(
        filename,
        content.read(),
        content_type="application/pdf"
    )
    return File.objects.create(
        owner=owner,
        file=uploaded_file,
        original_filename=filename
    )


def make_document(
    *,
    title: str = "Doc",
    uploaded_by: User,
    description: str = "desc",
    sent_to_all: bool = True,
    recipients=None,
    status: str = Document.Status.PUBLISHED,
) -> Document:
    """Создаёт Document напрямую (минует API)."""
    filer_file = _filer_file(owner=uploaded_by)
    
    doc = Document.objects.create(
        title=title,
        description=description,
        uploaded_by=uploaded_by,
        uploaded_at=timezone.now(),
        sent_to_all=sent_to_all,
        file=filer_file,
        status=status,
    )
    if not sent_to_all and recipients:
        doc.recipients.set(recipients)
    return doc


@pytest.mark.django_db
class TestDocumentStatusVisibility:
    """Тесты видимости документов по статусу для обычных пользователей."""

    def test_regular_user_sees_only_published_documents(
        self, api_client, make_user
    ):
        """Обычный пользователь не видит неопубликованные чужие документы."""
        # Создаем документы от другого автора
        author = make_user(email="author@test.com")
        
        doc_draft = make_document(
            uploaded_by=author,
            sent_to_all=True,
            status=Document.Status.DRAFT
        )
        doc_in_review = make_document(
            uploaded_by=author,
            sent_to_all=True,
            status=Document.Status.IN_REVIEW
        )
        doc_approved = make_document(
            uploaded_by=author,
            sent_to_all=True,
            status=Document.Status.APPROVED
        )
        doc_published = make_document(
            uploaded_by=author,
            sent_to_all=True,
            status=Document.Status.PUBLISHED
        )
        doc_rejected = make_document(
            uploaded_by=author,
            sent_to_all=True,
            status=Document.Status.REJECTED
        )
        doc_archived = make_document(
            uploaded_by=author,
            sent_to_all=True,
            status=Document.Status.ARCHIVED
        )

        # Обычный пользователь без прав
        regular_user = make_user(
            email="regular@test.com",
            staff=False
        )
        api_client.force_authenticate(regular_user)

        # Запрос списка документов
        url = reverse("api:v1:documents-list")
        response = api_client.get(url)

        assert response.status_code == http_status.HTTP_200_OK
        doc_ids = {doc["id"] for doc in response.data["results"]}

        # Должен видеть только PUBLISHED
        assert doc_published.id in doc_ids
        assert doc_draft.id not in doc_ids
        assert doc_in_review.id not in doc_ids
        assert doc_approved.id not in doc_ids
        assert doc_rejected.id not in doc_ids
        assert doc_archived.id not in doc_ids

    def test_regular_user_sees_own_documents_any_status(
        self, api_client, make_user
    ):
        """Обычный пользователь видит СВОИ документы в любом статусе."""
        regular_user = make_user(
            email="regular@test.com",
            staff=False
        )

        # Создаем свои документы в разных статусах
        own_draft = make_document(
            uploaded_by=regular_user,
            sent_to_all=True,
            status=Document.Status.DRAFT
        )
        own_published = make_document(
            uploaded_by=regular_user,
            sent_to_all=True,
            status=Document.Status.PUBLISHED
        )

        api_client.force_authenticate(regular_user)
        url = reverse("api:v1:documents-list")
        response = api_client.get(url)

        assert response.status_code == http_status.HTTP_200_OK
        doc_ids = {doc["id"] for doc in response.data["results"]}

        # Видит свои документы в любом статусе
        assert own_draft.id in doc_ids
        assert own_published.id in doc_ids

    def test_staff_user_sees_all_documents(
        self, api_client, make_user
    ):
        """Staff пользователь видит все документы независимо от статуса."""
        author = make_user(email="author@test.com")
        
        doc_draft = make_document(
            uploaded_by=author,
            sent_to_all=True,
            status=Document.Status.DRAFT
        )
        doc_published = make_document(
            uploaded_by=author,
            sent_to_all=True,
            status=Document.Status.PUBLISHED
        )

        # Staff пользователь
        staff_user = make_user(
            email="staff@test.com",
            staff=True
        )
        api_client.force_authenticate(staff_user)

        url = reverse("api:v1:documents-list")
        response = api_client.get(url)

        assert response.status_code == http_status.HTTP_200_OK
        doc_ids = {doc["id"] for doc in response.data["results"]}

        # Staff видит все
        assert doc_draft.id in doc_ids
        assert doc_published.id in doc_ids

    def test_user_with_view_permission_sees_all_documents(
        self, api_client, make_user
    ):
        """Пользователь с правом view_document видит все документы."""
        from django.contrib.auth.models import Permission
        
        author = make_user(email="author@test.com")
        
        doc_draft = make_document(
            uploaded_by=author,
            sent_to_all=True,
            status=Document.Status.DRAFT
        )
        doc_published = make_document(
            uploaded_by=author,
            sent_to_all=True,
            status=Document.Status.PUBLISHED
        )

        # Пользователь с правом view_document
        privileged_user = make_user(
            email="privileged@test.com",
            staff=False
        )
        # Добавляем право вручную
        perm = Permission.objects.get(
            codename='view_document',
            content_type__app_label='documents'
        )
        privileged_user.user_permissions.add(perm)
        
        api_client.force_authenticate(privileged_user)

        url = reverse("api:v1:documents-list")
        response = api_client.get(url)

        assert response.status_code == http_status.HTTP_200_OK
        doc_ids = {doc["id"] for doc in response.data["results"]}

        # Пользователь с правом видит все
        assert doc_draft.id in doc_ids
        assert doc_published.id in doc_ids

    def test_scope_mine_filters_by_status(
        self, api_client, make_user
    ):
        """Параметр scope=mine также фильтрует по статусу."""
        author = make_user(email="author@test.com")
        
        doc_draft = make_document(
            uploaded_by=author,
            sent_to_all=True,
            status=Document.Status.DRAFT
        )
        doc_published = make_document(
            uploaded_by=author,
            sent_to_all=True,
            status=Document.Status.PUBLISHED
        )

        regular_user = make_user(
            email="regular2@test.com",
            staff=False
        )
        api_client.force_authenticate(regular_user)

        url = reverse("api:v1:documents-list")
        response = api_client.get(url, {"scope": "mine"})

        assert response.status_code == http_status.HTTP_200_OK
        doc_ids = {doc["id"] for doc in response.data["results"]}

        # Даже с scope=mine - не видит чужие неопубликованные
        assert doc_published.id in doc_ids
        assert doc_draft.id not in doc_ids
