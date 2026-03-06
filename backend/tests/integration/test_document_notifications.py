"""
Integration tests: Documents ↔ Notifications

Проверяет создание уведомлений при работе с документами.
"""

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

from documents.models import Document, DocumentAcknowledgement
from notifications.models import Notification, NotificationType
from tests.api.v1.documents.test_documents_api import make_document, grant_perms, _filer_file

pytestmark = pytest.mark.django_db

User = get_user_model()


@pytest.fixture
def notification_types(db):
    """Создает необходимые типы уведомлений."""
    from notifications.models import NotificationCategory
    
    # Категория documents
    category, _ = NotificationCategory.objects.get_or_create(
        code='documents',
        defaults={
            'name': 'Документы',
            'icon': 'bi-file-earmark',
            'color': 'primary'
        }
    )
    
    # Тип document_ready
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
    
    # Тип document_signed_all
    doc_signed, _ = NotificationType.objects.get_or_create(
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
        'document_signed_all': doc_signed,
    }


class TestDocumentCreationNotifications:
    """Тесты уведомлений при создании документа."""
    
    def test_sent_to_all_creates_notifications(
        self, make_user, notification_types
    ):
        """sent_to_all=True создает уведомления всем активным пользователям."""
        # Создаем пользователей
        uploader = make_user("uploader@example.com")
        user1 = make_user("user1@example.com")
        user2 = make_user("user2@example.com")
        user3 = make_user("user3@example.com", active=False)  # неактивный
        
        # Создаем документ
        doc = make_document(uploaded_by=uploader, sent_to_all=True)
        
        # Проверяем уведомления
        notifications = Notification.objects.filter(
            notification_type=notification_types['document_ready']
        )
        
        # Должны получить все активные, кроме uploader
        assert notifications.count() == 2
        recipient_ids = set(notifications.values_list('recipient_id', flat=True))
        assert recipient_ids == {user1.id, user2.id}
        
        # Проверяем содержимое уведомления
        notif = notifications.first()
        assert doc.title in notif.message
        assert notif.content_object == doc
        assert 'document_id' in notif.metadata
    
    def test_sent_to_all_excludes_uploader(
        self, make_user, notification_types
    ):
        """Автор документа не получает уведомление о своем документе."""
        uploader = make_user("uploader@example.com")
        
        doc = make_document(uploaded_by=uploader, sent_to_all=True)
        
        # Проверяем, что uploader не получил уведомление
        uploader_notifs = Notification.objects.filter(
            recipient=uploader,
            notification_type=notification_types['document_ready']
        )
        assert uploader_notifs.count() == 0
    
    def test_recipients_create_notifications(
        self, make_user, notification_types
    ):
        """sent_to_all=False + recipients создает уведомления только получателям."""
        uploader = make_user("uploader@example.com")
        recipient1 = make_user("r1@example.com")
        recipient2 = make_user("r2@example.com")
        other_user = make_user("other@example.com")
        
        doc = make_document(
            uploaded_by=uploader,
            sent_to_all=False,
            recipients=[recipient1, recipient2]
        )
        
        # Проверяем уведомления
        notifications = Notification.objects.filter(
            notification_type=notification_types['document_ready']
        )
        
        assert notifications.count() == 2
        recipient_ids = set(notifications.values_list('recipient_id', flat=True))
        assert recipient_ids == {recipient1.id, recipient2.id}
        
        # other_user не должен получить уведомление
        assert not Notification.objects.filter(recipient=other_user).exists()
    
    def test_departments_create_notifications(
        self, make_user, notification_types
    ):
        """sent_to_all=False + departments создает уведомления сотрудникам отделов."""
        from employees.models import Department, EmployeeDepartment
        
        uploader = make_user("uploader@example.com")
        
        # Создаем отдел и сотрудников
        dept = Department.objects.create(name="IT Department")
        emp1 = make_user("emp1@example.com")
        emp2 = make_user("emp2@example.com")
        
        # Назначаем в отдел
        EmployeeDepartment.objects.create(
            employee=emp1,
            department=dept,
            is_active=True
        )
        EmployeeDepartment.objects.create(
            employee=emp2,
            department=dept,
            is_active=True
        )
        
        # Создаем документ для отдела
        doc = make_document(uploaded_by=uploader, sent_to_all=False)
        doc.departments.add(dept)
        
        # Проверяем уведомления
        notifications = Notification.objects.filter(
            notification_type=notification_types['document_ready']
        )
        
        assert notifications.count() == 2
        recipient_ids = set(notifications.values_list('recipient_id', flat=True))
        assert recipient_ids == {emp1.id, emp2.id}
    
    def test_combined_recipients_and_departments(
        self, make_user, notification_types
    ):
        """Комбинация recipients + departments без дубликатов."""
        from employees.models import Department, EmployeeDepartment
        
        uploader = make_user("uploader@example.com")
        
        # Создаем отдел
        dept = Department.objects.create(name="HR Department")
        dept_emp = make_user("dept_emp@example.com")
        EmployeeDepartment.objects.create(
            employee=dept_emp,
            department=dept,
            is_active=True
        )
        
        # Создаем индивидуального получателя
        individual = make_user("individual@example.com")
        
        # Документ и для отдела, и для индивидуального получателя
        doc = make_document(
            uploaded_by=uploader,
            sent_to_all=False,
            recipients=[individual]
        )
        doc.departments.add(dept)
        
        # Проверяем уведомления
        notifications = Notification.objects.filter(
            notification_type=notification_types['document_ready']
        )
        
        assert notifications.count() == 2
        recipient_ids = set(notifications.values_list('recipient_id', flat=True))
        assert recipient_ids == {dept_emp.id, individual.id}
    
    def test_inactive_users_not_notified(
        self, make_user, notification_types
    ):
        """Неактивные пользователи не получают уведомления."""
        uploader = make_user("uploader@example.com")
        active = make_user("active@example.com", active=True)
        inactive = make_user("inactive@example.com", active=False)
        
        doc = make_document(
            uploaded_by=uploader,
            sent_to_all=False,
            recipients=[active, inactive]
        )
        
        # Только активный пользователь должен получить уведомление
        notifications = Notification.objects.filter(
            notification_type=notification_types['document_ready']
        )
        
        assert notifications.count() == 1
        assert notifications.first().recipient == active
    
    def test_notification_has_correct_data(
        self, make_user, notification_types
    ):
        """Уведомление содержит корректные данные."""
        uploader = make_user(
            "uploader@example.com",
            first_name="Иван",
            last_name="Иванов"
        )
        recipient = make_user("recipient@example.com")
        
        doc = make_document(
            uploaded_by=uploader,
            title="Важный документ",
            sent_to_all=False,
            recipients=[recipient]
        )
        
        notif = Notification.objects.get(recipient=recipient)
        
        # Проверяем заголовок и сообщение
        assert notif.title == 'Новый документ на ознакомление'
        assert 'Иван Иванов' in notif.message or 'Важный документ' in notif.message
        
        # Проверяем ссылку
        assert notif.action_url == '/documents/'
        
        # Проверяем метаданные
        assert notif.metadata['document_id'] == doc.id
        assert notif.metadata['uploaded_by_id'] == uploader.id
        assert notif.metadata['sent_to_all'] is False
        
        # Проверяем связь с объектом
        assert notif.content_object == doc
    
    def test_notification_type_is_document_ready(
        self, make_user, notification_types
    ):
        """Тип уведомления должен быть document_ready."""
        uploader = make_user("uploader@example.com")
        recipient = make_user("recipient@example.com")
        
        doc = make_document(
            uploaded_by=uploader,
            sent_to_all=False,
            recipients=[recipient]
        )
        
        notif = Notification.objects.get(recipient=recipient)
        assert notif.notification_type == notification_types['document_ready']


class TestDocumentWithoutUploader:
    """Граничный случай: документ без автора."""
    
    def test_document_without_uploader(
        self, make_user, notification_types
    ):
        """Документ без автора все равно создает уведомления."""
        recipient = make_user("recipient@example.com")
        
        # Создаем документ без автора
        filer_file = _filer_file(owner=None)
        doc = Document.objects.create(
            title="Безымянный документ",
            uploaded_by=None,  # Нет автора
            sent_to_all=False,
            file=filer_file
        )
        doc.recipients.add(recipient)
        
        # Проверяем, что уведомление все равно создано
        notif = Notification.objects.get(recipient=recipient)
        assert notif is not None
        assert 'Администратор' in notif.message or 'документ' in notif.message.lower()
