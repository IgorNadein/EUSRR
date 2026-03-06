# documents/conftest.py
"""
Pytest fixtures для тестирования модуля documents
"""

import pytest
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient
from filer.models import File as FilerFile, Folder
from documents.models import (
    Document, DocumentAcknowledgement, DocumentComment,
    DocumentType, DocumentTag, Cabinet
)
from employees.models import Department

User = get_user_model()


@pytest.fixture
def api_client():
    """APIClient для REST API тестов"""
    return APIClient()


@pytest.fixture
def admin_user(db):
    """Superuser с полными правами"""
    return User.objects.create_superuser(
        phone_number='+79999999990',
        email='admin@example.com',
        password='admin123',
        first_name='Admin',
        last_name='User',
        is_active=True
    )


@pytest.fixture
def author_user(db):
    """Автор документов"""
    return User.objects.create_user(
        phone_number='+79999999999',
        email='author@example.com',
        password='author123',
        first_name='Автор',
        last_name='Документов',
        is_active=True
    )


@pytest.fixture
def viewer_user(db):
    """Пользователь-получатель документов"""
    return User.objects.create_user(
        phone_number='+79999999998',
        email='viewer@example.com',
        password='viewer123',
        first_name='Просмотрщик',
        last_name='Документов',
        is_active=True
    )


@pytest.fixture
def other_user(db):
    """Обычный пользователь без доступа"""
    return User.objects.create_user(
        phone_number='+79999999997',
        email='other@example.com',
        password='other123',
        first_name='Другой',
        last_name='Пользователь',
        is_active=True
    )


@pytest.fixture
def department(db):
    """Тестовый отдел"""
    return Department.objects.create(name="Тестовый отдел")


@pytest.fixture
def test_file():
    """SimpleUploadedFile для тестирования"""
    return SimpleUploadedFile(
        "test_document.pdf",
        b"PDF content here",
        content_type="application/pdf"
    )


@pytest.fixture
def filer_file(db, author_user, test_file):
    """FilerFile для тестирования"""
    return FilerFile.objects.create(
        file=test_file,
        original_filename="test_document.pdf",
        name="Test PDF",
        owner=author_user
    )


@pytest.fixture
def document(db, filer_file, author_user, viewer_user):
    """Тестовый документ с автором и получателем"""
    doc = Document.objects.create(
        title="Тестовый документ",
        file=filer_file,
        description="Описание тестового документа",
        uploaded_by=author_user,
        sent_to_all=False,
        acknowledgement_required=False
    )
    doc.recipients.add(viewer_user)
    return doc


@pytest.fixture
def document_sent_to_all(db, filer_file, author_user):
    """Документ для всех сотрудников"""
    return Document.objects.create(
        title="Документ для всех",
        file=filer_file,
        description="Описание",
        uploaded_by=author_user,
        sent_to_all=True,
        acknowledgement_required=True
    )


@pytest.fixture
def folder(db, author_user):
    """Тестовая папка filer"""
    return Folder.objects.create(
        name="Тестовая папка",
        owner=author_user
    )


@pytest.fixture
def document_type(db):
    """Тип документа"""
    return DocumentType.objects.create(
        name="Приказ",
        code="ORDER",
        description="Приказ руководства",
        is_active=True
    )


@pytest.fixture
def document_tag(db):
    """Тег документа"""
    return DocumentTag.objects.create(
        name="Важное",
        color="#FF0000"
    )


@pytest.fixture
def cabinet(db):
    """Шкаф/кабинет документов"""
    return Cabinet.objects.create(
        name="Кадровые документы",
        description="Документы HR отдела"
    )


@pytest.fixture
def authenticated_client(api_client, author_user):
    """APIClient авторизованный как author"""
    api_client.force_authenticate(user=author_user)
    return api_client


@pytest.fixture
def viewer_client(api_client, viewer_user):
    """APIClient авторизованный как viewer"""
    api_client.force_authenticate(user=viewer_user)
    return api_client


@pytest.fixture
def admin_client(api_client, admin_user):
    """APIClient авторизованный как admin"""
    api_client.force_authenticate(user=admin_user)
    return api_client
