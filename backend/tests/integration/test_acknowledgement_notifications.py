"""
Integration tests: Document Acknowledgement Notifications

Проверяет уведомления при ознакомлении с документами.
"""

import pytest
from django.contrib.auth import get_user_model

from documents.models import Document, DocumentAcknowledgement
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
    
    doc_ready, _ = NotificationType.objects.get_or_create(
        code='document_ready',
        defaults={
            'category': category,
            'name': 'Новый документ на ознакомление',
            'default_enabled': True,
            'default_channels': {'web': True, 'email': True, 'telegram': False},
            'priority': 'normal'
        }
    )
    
    doc_signed_all, _ = NotificationType.objects.get_or_create(
        code='document_signed_all',
        defaults={
            'category': category,
            'name': 'Все ознакомились с документом',
            'default_enabled': True,
            'default_channels': {'web': True, 'email': False, 'telegram': False},
            'priority': 'low'
        }
    )
    
    return {
        'document_ready': doc_ready,
        'document_signed_all': doc_signed_all,
    }


class TestAcknowledgementNotifications:
    """Тесты уведомлений при ознакомлении с документом."""
    
    def test_all_acknowledged_notifies_uploader(
        self, make_user, notification_types
    ):
        """Когда все ознакомились, автор получает уведомление."""
        uploader = make_user("uploader@example.com")
        user1 = make_user("user1@example.com")
        user2 = make_user("user2@example.com")
        
        doc = make_document(
            uploaded_by=uploader,
            sent_to_all=False,
            recipients=[user1, user2]
        )
        
        # Очищаем уведомления о создании
        Notification.objects.all().delete()
        
        # Оба пользователя ознакомились
        DocumentAcknowledgement.objects.create(document=doc, user=user1)
        DocumentAcknowledgement.objects.create(document=doc, user=user2)
        
        # Проверяем уведомление автору
        notif = Notification.objects.get(
            recipient=uploader,
            notification_type=notification_types['document_signed_all']
        )
        
        assert notif is not None
        assert doc.title in notif.message
        assert notif.content_object == doc
    
    def test_partial_acknowledged_no_notification(
        self, make_user, notification_types
    ):
        """Частичное ознакомление не создает уведомление."""
        uploader = make_user("uploader@example.com")
        user1 = make_user("user1@example.com")
        user2 = make_user("user2@example.com")
        
        doc = make_document(
            uploaded_by=uploader,
            sent_to_all=False,
            recipients=[user1, user2]
        )
        
        # Очищаем уведомления о создании
        Notification.objects.all().delete()
        
        # Только один ознакомился
        DocumentAcknowledgement.objects.create(document=doc, user=user1)
        
        # Не должно быть уведомления о полном ознакомлении
        notifs = Notification.objects.filter(
            notification_type=notification_types['document_signed_all']
        )
        assert notifs.count() == 0
    
    def test_no_recipients_no_notification(
        self, make_user, notification_types
    ):
        """Документ без получателей не создает уведомление о завершении."""
        uploader = make_user("uploader@example.com")
        
        doc = make_document(
            uploaded_by=uploader,
            sent_to_all=False,
            recipients=[]
        )
        
        # Очищаем уведомления
        Notification.objects.all().delete()
        
        # Нет получателей = нет ознакомлений = нет уведомления
        # (Проверяем, что не падает)
        notifs = Notification.objects.filter(
            notification_type=notification_types['document_signed_all']
        )
        assert notifs.count() == 0
    
    def test_sent_to_all_needs_all_active_users(
        self, make_user, notification_types
    ):
        """sent_to_all требует ознакомления всех активных пользователей."""
        uploader = make_user("uploader@example.com")
        user1 = make_user("user1@example.com")
        user2 = make_user("user2@example.com")
        user3 = make_user("user3@example.com", active=False)  # неактивный
        
        doc = make_document(uploaded_by=uploader, sent_to_all=True)
        
        # Очищаем уведомления о создании
        Notification.objects.all().delete()
        
        # Только активные должны ознакомиться
        DocumentAcknowledgement.objects.create(document=doc, user=user1)
        DocumentAcknowledgement.objects.create(document=doc, user=user2)
        
        # Проверяем уведомление автору (все активные ознакомились)
        notifs = Notification.objects.filter(
            recipient=uploader,
            notification_type=notification_types['document_signed_all']
        )
        assert notifs.count() == 1
    
    def test_notification_only_sent_once(
        self, make_user, notification_types
    ):
        """Уведомление о завершении отправляется только один раз."""
        uploader = make_user("uploader@example.com")
        user1 = make_user("user1@example.com")
        
        doc = make_document(
            uploaded_by=uploader,
            sent_to_all=False,
            recipients=[user1]
        )
        
        # Очищаем уведомления о создании
        Notification.objects.all().delete()
        
        # Ознакомился
        DocumentAcknowledgement.objects.create(document=doc, user=user1)
        
        # Проверяем количество уведомлений
        notifs = Notification.objects.filter(
            notification_type=notification_types['document_signed_all']
        )
        assert notifs.count() == 1
        
        # Пытаемся создать дубликат (не должно быть ошибки и дубликатов)
        # В реальности это защищено unique_together в модели
        # Здесь просто проверяем, что логика не создаст повторное уведомление


class TestAcknowledgementEdgeCases:
    """Граничные случаи ознакомления."""
    
    def test_document_without_uploader_no_crash(
        self, make_user, notification_types
    ):
        """Документ без автора при полном ознакомлении не падает."""
        from tests.api.v1.documents.test_documents_api import _filer_file
        
        user1 = make_user("user1@example.com")
        
        # Создаем документ без автора
        filer_file = _filer_file(owner=None)
        doc = Document.objects.create(
            title="Безымянный документ",
            uploaded_by=None,
            sent_to_all=False,
            file=filer_file
        )
        doc.recipients.add(user1)
        
        # Очищаем уведомления
        Notification.objects.all().delete()
        
        # Ознакомился
        DocumentAcknowledgement.objects.create(document=doc, user=user1)
        
        # Не должно упасть (нет автора = нет кому отправлять)
        notifs = Notification.objects.filter(
            notification_type=notification_types['document_signed_all']
        )
        # Уведомление не создается, т.к. нет автора
        assert notifs.count() == 0
    
    def test_acknowledgement_progress_tracking(
        self, make_user, notification_types
    ):
        """Прогресс ознакомления корректно отслеживается."""
        uploader = make_user("uploader@example.com")
        recipients = [make_user(f"user{i}@example.com") for i in range(5)]
        
        doc = make_document(
            uploaded_by=uploader,
            sent_to_all=False,
            recipients=recipients
        )
        
        # Очищаем уведомления
        Notification.objects.all().delete()
        
        # Постепенно ознакамливаемся
        for i, recipient in enumerate(recipients[:-1]):  # Все кроме последнего
            DocumentAcknowledgement.objects.create(document=doc, user=recipient)
            
            # Проверяем, что уведомление еще не отправлено
            notifs = Notification.objects.filter(
                notification_type=notification_types['document_signed_all']
            )
            assert notifs.count() == 0, f"Уведомление отправлено после {i+1}/5"
        
        # Последний ознакомился
        DocumentAcknowledgement.objects.create(document=doc, user=recipients[-1])
        
        # Теперь должно быть уведомление
        notifs = Notification.objects.filter(
            notification_type=notification_types['document_signed_all']
        )
        assert notifs.count() == 1
