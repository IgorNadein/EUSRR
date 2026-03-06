"""
Integration tests: Document Comments Notifications

Проверяет уведомления при добавлении комментариев к документам.
"""

import pytest
from django.contrib.auth import get_user_model

from documents.models import Document, DocumentComment
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
    
    comment, _ = NotificationType.objects.get_or_create(
        code='document_comment',
        defaults={
            'category': category,
            'name': 'Новый комментарий к документу',
            'default_enabled': True,
            'default_channels': {'web': True, 'email': False, 'telegram': False},
            'priority': 'normal'
        }
    )
    
    reply, _ = NotificationType.objects.get_or_create(
        code='document_comment_reply',
        defaults={
            'category': category,
            'name': 'Ответ на ваш комментарий',
            'default_enabled': True,
            'default_channels': {'web': True, 'email': True, 'telegram': False},
            'priority': 'normal'
        }
    )
    
    return {
        'document_comment': comment,
        'document_comment_reply': reply,
    }


class TestCommentNotifications:
    """Тесты уведомлений при добавлении комментариев."""
    
    def test_comment_notifies_uploader(
        self, make_user, notification_types
    ):
        """Комментарий к документу уведомляет автора документа."""
        uploader = make_user("uploader@example.com")
        commenter = make_user("commenter@example.com")
        
        doc = make_document(uploaded_by=uploader)
        
        # Очищаем уведомления о создании документа
        Notification.objects.all().delete()
        
        # Добавляем комментарий
        comment = DocumentComment.objects.create(
            document=doc,
            user=commenter,
            text="Важный комментарий"
        )
        
        # Проверяем уведомление автору документа
        notif = Notification.objects.get(
            recipient=uploader,
            notification_type=notification_types['document_comment']
        )
        
        assert notif is not None
        assert 'комментарий' in notif.message.lower()
        assert notif.content_object == comment
    
    def test_comment_does_not_notify_self(
        self, make_user, notification_types
    ):
        """Автор документа не получает уведомление о своем комментарии."""
        uploader = make_user("uploader@example.com")
        
        doc = make_document(uploaded_by=uploader)
        
        # Очищаем уведомления
        Notification.objects.all().delete()
        
        # Автор сам комментирует
        DocumentComment.objects.create(
            document=doc,
            user=uploader,
            text="Мой комментарий"
        )
        
        # Не должно быть уведомления
        notifs = Notification.objects.filter(
            recipient=uploader,
            notification_type=notification_types['document_comment']
        )
        assert notifs.count() == 0
    
    def test_reply_notifies_parent_comment_author(
        self, make_user, notification_types
    ):
        """Ответ на комментарий уведомляет автора родительского комментария."""
        uploader = make_user("uploader@example.com")
        commenter = make_user("commenter@example.com")
        replier = make_user("replier@example.com")
        
        doc = make_document(uploaded_by=uploader)
        
        # Первый комментарий
        parent_comment = DocumentComment.objects.create(
            document=doc,
            user=commenter,
            text="Вопрос"
        )
        
        # Очищаем уведомления
        Notification.objects.all().delete()
        
        # Ответ на комментарий
        reply = DocumentComment.objects.create(
            document=doc,
            user=replier,
            parent=parent_comment,
            text="Ответ на вопрос"
        )
        
        # Проверяем уведомление автору родительского комментария
        notifs = Notification.objects.filter(
            recipient=commenter,
            notification_type=notification_types['document_comment_reply']
        )
        assert notifs.count() == 1
        
        notif = notifs.first()
        assert 'ответ' in notif.message.lower()
        assert notif.content_object == reply
    
    def test_reply_does_not_notify_self(
        self, make_user, notification_types
    ):
        """Ответ на свой комментарий не создает уведомление."""
        uploader = make_user("uploader@example.com")
        commenter = make_user("commenter@example.com")
        
        doc = make_document(uploaded_by=uploader)
        
        # Комментарий
        parent_comment = DocumentComment.objects.create(
            document=doc,
            user=commenter,
            text="Вопрос"
        )
        
        # Очищаем уведомления
        Notification.objects.all().delete()
        
        # Ответ самому себе
        DocumentComment.objects.create(
            document=doc,
            user=commenter,
            parent=parent_comment,
            text="Дополнение"
        )
        
        # Не должно быть уведомления о reply
        notifs = Notification.objects.filter(
            recipient=commenter,
            notification_type=notification_types['document_comment_reply']
        )
        assert notifs.count() == 0
    
    def test_reply_notifies_both_uploader_and_parent_author(
        self, make_user, notification_types
    ):
        """Ответ создает уведомления и автору документа, и автору комментария."""
        uploader = make_user("uploader@example.com")
        commenter = make_user("commenter@example.com")
        replier = make_user("replier@example.com")
        
        doc = make_document(uploaded_by=uploader)
        
        parent_comment = DocumentComment.objects.create(
            document=doc,
            user=commenter,
            text="Вопрос"
        )
        
        # Очищаем уведомления
        Notification.objects.all().delete()
        
        # Ответ
        DocumentComment.objects.create(
            document=doc,
            user=replier,
            parent=parent_comment,
            text="Ответ"
        )
        
        # Проверяем уведомление автору документа
        uploader_notifs = Notification.objects.filter(
            recipient=uploader,
            notification_type=notification_types['document_comment']
        )
        assert uploader_notifs.count() == 1
        
        # Проверяем уведомление автору комментария
        commenter_notifs = Notification.objects.filter(
            recipient=commenter,
            notification_type=notification_types['document_comment_reply']
        )
        assert commenter_notifs.count() == 1


class TestCommentEdgeCases:
    """Граничные случаи комментариев."""
    
    def test_comment_without_document_uploader(
        self, make_user, notification_types
    ):
        """Комментарий к документу без автора не падает."""
        from tests.api.v1.documents.test_documents_api import _filer_file
        
        commenter = make_user("commenter@example.com")
        
        # Документ без автора
        filer_file = _filer_file(owner=None)
        doc = Document.objects.create(
            title="Безымянный документ",
            uploaded_by=None,
            file=filer_file
        )
        
        # Комментарий
        DocumentComment.objects.create(
            document=doc,
            user=commenter,
            text="Комментарий"
        )
        
        # Не должно упасть (нет автора = нет кому уведомлять)
        notifs = Notification.objects.filter(
            notification_type=notification_types['document_comment']
        )
        # Может быть пусто или создано для других целей
        # Главное - не упало
    
    def test_multiple_comments_create_multiple_notifications(
        self, make_user, notification_types
    ):
        """Несколько комментариев создают несколько уведомлений."""
        uploader = make_user("uploader@example.com")
        commenter1 = make_user("commenter1@example.com")
        commenter2 = make_user("commenter2@example.com")
        
        doc = make_document(uploaded_by=uploader)
        
        # Очищаем уведомления
        Notification.objects.all().delete()
        
        # Два комментария от разных пользователей
        DocumentComment.objects.create(
            document=doc,
            user=commenter1,
            text="Первый комментарий"
        )
        DocumentComment.objects.create(
            document=doc,
            user=commenter2,
            text="Второй комментарий"
        )
        
        # Автор должен получить 2 уведомления
        notifs = Notification.objects.filter(
            recipient=uploader,
            notification_type=notification_types['document_comment']
        )
        assert notifs.count() == 2
