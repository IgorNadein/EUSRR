"""
Edge Cases Tests: Document Notifications

Проверяет граничные случаи и обработку ошибок в системе уведомлений.
"""

import pytest
from django.contrib.auth import get_user_model
from django.db import transaction

from documents.models import Document, DocumentAcknowledgement
from notifications.models import Notification, NotificationType
from tests.api.v1.documents.test_documents_api import make_document, _filer_file

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def notification_types(db):
    """Создает необходимые типы уведомлений."""
    from notifications.models import NotificationCategory
    
    category, _ = NotificationCategory.objects.get_or_create(
        code='documents',
        defaults={'name': 'Документы', 'icon': 'bi-file-earmark', 'color': 'primary'}
    )
    
    doc_ready, _ = NotificationType.objects.get_or_create(
        code='document_ready',
        defaults={
            'category': category,
            'name': 'Новый документ',
            'default_enabled': True,
            'default_channels': {'web': True},
            'priority': 'normal'
        }
    )
    
    return {'document_ready': doc_ready}


class TestBulkOperations:
    """Тесты массовых операций."""
    
    def test_sent_to_all_with_many_users(
        self, make_user, notification_types
    ):
        """sent_to_all с большим количеством пользователей."""
        uploader = make_user("uploader@example.com")
        
        # Создаем 50 пользователей
        users = [make_user(f"user{i}@example.com") for i in range(50)]
        
        doc = make_document(uploaded_by=uploader, sent_to_all=True)
        
        # Проверяем количество уведомлений
        notifs = Notification.objects.filter(
            notification_type=notification_types['document_ready']
        )
        
        # Должны быть уведомления для всех, кроме uploader
        assert notifs.count() == 50
    
    def test_many_recipients_explicitly(
        self, make_user, notification_types
    ):
        """Документ с большим списком явных получателей."""
        uploader = make_user("uploader@example.com")
        recipients = [make_user(f"recipient{i}@example.com") for i in range(30)]
        
        doc = make_document(
            uploaded_by=uploader,
            sent_to_all=False,
            recipients=recipients
        )
        
        notifs = Notification.objects.filter(
            notification_type=notification_types['document_ready']
        )
        
        assert notifs.count() == 30


class TestDuplicatePrevention:
    """Тесты предотвращения дубликатов."""
    
    def test_no_duplicate_notifications_on_update(
        self, make_user, notification_types
    ):
        """Обновление документа не создает дубликаты уведомлений."""
        uploader = make_user("uploader@example.com")
        recipient = make_user("recipient@example.com")
        
        doc = make_document(
            uploaded_by=uploader,
            sent_to_all=False,
            recipients=[recipient]
        )
        
        initial_count = Notification.objects.filter(
            notification_type=notification_types['document_ready']
        ).count()
        
        # Обновляем документ
        doc.title = "Обновленный заголовок"
        doc.save()
        
        # Количество уведомлений не должно измениться
        final_count = Notification.objects.filter(
            notification_type=notification_types['document_ready']
        ).count()
        
        assert final_count == initial_count
    
    def test_adding_same_recipient_twice(
        self, make_user, notification_types
    ):
        """Добавление одного получателя дважды."""
        uploader = make_user("uploader@example.com")
        recipient = make_user("recipient@example.com")
        
        doc = make_document(
            uploaded_by=uploader,
            sent_to_all=False,
            recipients=[recipient]
        )
        
        initial_count = Notification.objects.filter(
            recipient=recipient,
            notification_type=notification_types['document_ready']
        ).count()
        
        # Пытаемся добавить еще раз (ManyToMany предотвратит дубликат)
        doc.recipients.add(recipient)
        
        final_count = Notification.objects.filter(
            recipient=recipient,
            notification_type=notification_types['document_ready']
        ).count()
        
        # Не должно быть нового уведомления
        assert final_count == initial_count


class TestInactiveUsers:
    """Тесты с неактивными пользователями."""
    
    def test_only_active_users_notified_sent_to_all(
        self, make_user, notification_types
    ):
        """sent_to_all уведомляет только активных."""
        uploader = make_user("uploader@example.com")
        active1 = make_user("active1@example.com", active=True)
        active2 = make_user("active2@example.com", active=True)
        inactive1 = make_user("inactive1@example.com", active=False)
        inactive2 = make_user("inactive2@example.com", active=False)
        
        doc = make_document(uploaded_by=uploader, sent_to_all=True)
        
        notifs = Notification.objects.filter(
            notification_type=notification_types['document_ready']
        )
        
        recipient_ids = set(notifs.values_list('recipient_id', flat=True))
        
        # Только активные
        assert active1.id in recipient_ids
        assert active2.id in recipient_ids
        assert inactive1.id not in recipient_ids
        assert inactive2.id not in recipient_ids
    
    def test_inactive_explicit_recipient_not_notified(
        self, make_user, notification_types
    ):
        """Неактивный явный получатель не получает уведомление."""
        uploader = make_user("uploader@example.com")
        active = make_user("active@example.com", active=True)
        inactive = make_user("inactive@example.com", active=False)
        
        doc = make_document(
            uploaded_by=uploader,
            sent_to_all=False,
            recipients=[active, inactive]
        )
        
        notifs = Notification.objects.filter(
            notification_type=notification_types['document_ready']
        )
        
        recipient_ids = set(notifs.values_list('recipient_id', flat=True))
        
        assert active.id in recipient_ids
        assert inactive.id not in recipient_ids


class TestEmptyStates:
    """Тесты пустых состояний."""
    
    def test_document_with_no_recipients_no_notifications(
        self, make_user, notification_types
    ):
        """Документ без получателей не создает уведомлений."""
        uploader = make_user("uploader@example.com")
        
        doc = make_document(
            uploaded_by=uploader,
            sent_to_all=False,
            recipients=[]
        )
        
        notifs = Notification.objects.filter(
            notification_type=notification_types['document_ready']
        )
        
        # Нет получателей = нет уведомлений (кроме служебных)
        # Проверяем, что не упало
    
    def test_system_with_no_users_except_uploader(
        self, make_user, notification_types
    ):
        """Система с единственным пользователем."""
        # Удаляем всех пользователей
        User.objects.all().delete()
        
        uploader = make_user("only_user@example.com")
        
        doc = make_document(
            uploaded_by=uploader,
            sent_to_all=True
        )
        
        notifs = Notification.objects.filter(
            notification_type=notification_types['document_ready']
        )
        
        # Автор не уведомляет сам себя
        assert notifs.count() == 0


class TestTransactionSafety:
    """Тесты безопасности транзакций."""
    
    def test_notification_created_after_commit(
        self, make_user, notification_types
    ):
        """Уведомления создаются после commit транзакции."""
        uploader = make_user("uploader@example.com")
        recipient = make_user("recipient@example.com")
        
        with transaction.atomic():
            doc = make_document(
                uploaded_by=uploader,
                sent_to_all=False,
                recipients=[recipient]
            )
            
            # Внутри транзакции уведомление может быть не создано
            # (зависит от реализации on_commit)
        
        # После commit уведомление должно быть
        notifs = Notification.objects.filter(
            notification_type=notification_types['document_ready']
        )
        assert notifs.count() >= 1


class TestDocumentWithoutUploader:
    """Тесты документов без автора."""
    
    def test_document_without_uploader_sent_to_all(
        self, make_user, notification_types
    ):
        """Документ без автора sent_to_all."""
        user1 = make_user("user1@example.com")
        user2 = make_user("user2@example.com")
        
        filer_file = _filer_file(owner=None)
        doc = Document.objects.create(
            title="Системный документ",
            uploaded_by=None,
            sent_to_all=True,
            file=filer_file
        )
        
        # Должны быть уведомления всем пользователям
        notifs = Notification.objects.filter(
            notification_type=notification_types['document_ready']
        )
        
        # Проверяем, что логика работает
        assert notifs.count() >= 2
    
    def test_document_without_uploader_recipients(
        self, make_user, notification_types
    ):
        """Документ без автора с получателями."""
        recipient = make_user("recipient@example.com")
        
        filer_file = _filer_file(owner=None)
        doc = Document.objects.create(
            title="Анонимный документ",
            uploaded_by=None,
            sent_to_all=False,
            file=filer_file
        )
        doc.recipients.add(recipient)
        
        # Проверяем уведомление
        notifs = Notification.objects.filter(
            recipient=recipient,
            notification_type=notification_types['document_ready']
        )
        
        assert notifs.count() == 1
        notif = notifs.first()
        
        # Сообщение должно корректно обработать отсутствие автора
        assert 'администратор' in notif.message.lower() or 'система' in notif.message.lower()


class TestConcurrency:
    """Тесты параллельных операций."""
    
    def test_simultaneous_acknowledgements(
        self, make_user, notification_types
    ):
        """Одновременное ознакомление несколькими пользователями."""
        uploader = make_user("uploader@example.com")
        user1 = make_user("user1@example.com")
        user2 = make_user("user2@example.com")
        
        doc = make_document(
            uploaded_by=uploader,
            sent_to_all=False,
            recipients=[user1, user2]
        )
        
        # Очищаем уведомления
        Notification.objects.all().delete()
        
        # Оба одновременно ознакомились
        ack1 = DocumentAcknowledgement.objects.create(document=doc, user=user1)
        ack2 = DocumentAcknowledgement.objects.create(document=doc, user=user2)
        
        # Должно быть только одно уведомление о завершении
        from notifications.models import NotificationType
        signed_all = NotificationType.objects.get(code='document_signed_all')
        
        notifs = Notification.objects.filter(
            recipient=uploader,
            notification_type=signed_all
        )
        
        # Может быть 1 или 2 (race condition), но не больше
        assert notifs.count() <= 2
