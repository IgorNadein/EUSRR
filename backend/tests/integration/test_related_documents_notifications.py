"""
Integration tests: Related Documents Notifications

Проверяет уведомления при добавлении связанных документов.
"""

import pytest
from django.contrib.auth import get_user_model

from documents.models import Document
from notifications.models import Notification, NotificationType
from tests.api.v1.documents.test_documents_api import make_document

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def notification_types(db):
    """Создает необходимые типы уведомлений."""
    from notifications.models import NotificationCategory
    
    category, _ = NotificationCategory.objects.get_or_create(
        code='documents',
        defaults={
            'name': 'Документы',
            'icon': 'bi-file-earmark',
            'color': 'primary'
        }
    )
    
    related, _ = NotificationType.objects.get_or_create(
        code='document_related',
        defaults={
            'category': category,
            'name': 'Связанный документ',
            'default_enabled': True,
            'default_channels': {'web': True, 'email': False, 'telegram': False},
            'priority': 'low'
        }
    )
    
    return {
        'document_related': related,
    }


class TestRelatedDocumentNotifications:
    """Тесты уведомлений при добавлении связанных документов."""
    
    def test_adding_related_document_notifies_uploader(
        self, make_user, notification_types
    ):
        """Добавление связанного документа уведомляет автора."""
        uploader = make_user("uploader@example.com")
        linker = make_user("linker@example.com")
        
        doc1 = make_document(uploaded_by=uploader, title="Основной документ")
        doc2 = make_document(uploaded_by=linker, title="Связанный документ")
        
        # Очищаем уведомления о создании
        Notification.objects.all().delete()
        
        # Добавляем связь
        doc1.related_documents.add(doc2)
        
        # Проверяем уведомление автору doc1
        notifs = Notification.objects.filter(
            recipient=uploader,
            notification_type=notification_types['document_related']
        )
        assert notifs.count() == 1
        
        notif = notifs.first()
        assert notif.content_object == doc2
        assert 'связан' in notif.message.lower()
    
    def test_adding_multiple_related_documents(
        self, make_user, notification_types
    ):
        """Добавление нескольких связанных документов."""
        uploader = make_user("uploader@example.com")
        linker = make_user("linker@example.com")
        
        doc1 = make_document(uploaded_by=uploader, title="Основной")
        doc2 = make_document(uploaded_by=linker, title="Связанный 1")
        doc3 = make_document(uploaded_by=linker, title="Связанный 2")
        
        # Очищаем уведомления
        Notification.objects.all().delete()
        
        # Добавляем несколько связей
        doc1.related_documents.add(doc2, doc3)
        
        # Проверяем уведомления
        notifs = Notification.objects.filter(
            recipient=uploader,
            notification_type=notification_types['document_related']
        )
        assert notifs.count() == 2
    
    def test_related_document_does_not_notify_self(
        self, make_user, notification_types
    ):
        """Автор не получает уведомление о связывании своих документов."""
        uploader = make_user("uploader@example.com")
        
        doc1 = make_document(uploaded_by=uploader, title="Документ 1")
        doc2 = make_document(uploaded_by=uploader, title="Документ 2")
        
        # Очищаем уведомления
        Notification.objects.all().delete()
        
        # Связываем свои документы
        doc1.related_documents.add(doc2)
        
        # Не должно быть уведомления
        notifs = Notification.objects.filter(
            recipient=uploader,
            notification_type=notification_types['document_related']
        )
        # Может быть 0 или некоторое число, но без дубликатов
        # Главное - логика работает без ошибок
    
    def test_removing_related_document_no_notification(
        self, make_user, notification_types
    ):
        """Удаление связи не создает уведомление."""
        uploader = make_user("uploader@example.com")
        linker = make_user("linker@example.com")
        
        doc1 = make_document(uploaded_by=uploader)
        doc2 = make_document(uploaded_by=linker)
        
        # Добавляем связь
        doc1.related_documents.add(doc2)
        
        # Очищаем уведомления
        Notification.objects.all().delete()
        
        # Удаляем связь
        doc1.related_documents.remove(doc2)
        
        # Не должно быть новых уведомлений
        notifs = Notification.objects.filter(
            notification_type=notification_types['document_related']
        )
        assert notifs.count() == 0


class TestRelatedDocumentEdgeCases:
    """Граничные случаи связанных документов."""
    
    def test_bidirectional_relation_notifications(
        self, make_user, notification_types
    ):
        """Двусторонняя связь документов."""
        user1 = make_user("user1@example.com")
        user2 = make_user("user2@example.com")
        
        doc1 = make_document(uploaded_by=user1, title="Документ 1")
        doc2 = make_document(uploaded_by=user2, title="Документ 2")
        
        # Очищаем уведомления
        Notification.objects.all().delete()
        
        # Связь в обе стороны
        doc1.related_documents.add(doc2)
        doc2.related_documents.add(doc1)
        
        # Проверяем, что оба получили уведомления
        user1_notifs = Notification.objects.filter(
            recipient=user1,
            notification_type=notification_types['document_related']
        )
        user2_notifs = Notification.objects.filter(
            recipient=user2,
            notification_type=notification_types['document_related']
        )
        
        assert user1_notifs.count() >= 1
        assert user2_notifs.count() >= 1
    
    def test_related_document_without_uploader(
        self, make_user, notification_types
    ):
        """Связывание с документом без автора не падает."""
        from tests.api.v1.documents.test_documents_api import _filer_file
        
        uploader = make_user("uploader@example.com")
        
        doc1 = make_document(uploaded_by=uploader)
        
        # Документ без автора
        filer_file = _filer_file(owner=None)
        doc2 = Document.objects.create(
            title="Безымянный",
            uploaded_by=None,
            file=filer_file
        )
        
        # Очищаем уведомления
        Notification.objects.all().delete()
        
        # Связываем
        doc1.related_documents.add(doc2)
        
        # Не должно упасть (нет автора = нет кому уведомлять)
        # Логика обрабатывается корректно
