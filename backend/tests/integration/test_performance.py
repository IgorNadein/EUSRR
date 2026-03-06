"""
Performance Tests: Document Notifications

Проверяет производительность системы уведомлений при массовых операциях.
"""

import pytest
import time
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
    
    doc_signed_all, _ = NotificationType.objects.get_or_create(
        code='document_signed_all',
        defaults={
            'category': category,
            'name': 'Все ознакомились',
            'default_enabled': True,
            'default_channels': {'web': True},
            'priority': 'low'
        }
    )
    
    return {
        'document_ready': doc_ready,
        'document_signed_all': doc_signed_all
    }


@pytest.mark.performance
class TestNotificationPerformance:
    """Тесты производительности уведомлений."""
    
    def test_100_users_notification_time(
        self, make_user, notification_types
    ):
        """Создание уведомлений для 100 пользователей."""
        uploader = make_user("uploader@example.com")
        users = [make_user(f"user{i}@example.com") for i in range(100)]
        
        start_time = time.time()
        
        doc = make_document(uploaded_by=uploader, sent_to_all=True)
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Проверяем, что создание заняло разумное время (< 5 секунд)
        assert elapsed < 5.0, f"Создание уведомлений заняло {elapsed:.2f}s"
        
        # Проверяем количество
        notifs = Notification.objects.filter(
            notification_type=notification_types['document_ready']
        )
        assert notifs.count() == 100
    
    def test_bulk_acknowledgement_performance(
        self, make_user, notification_types
    ):
        """Массовое ознакомление с документом."""
        uploader = make_user("uploader@example.com")
        users = [make_user(f"user{i}@example.com") for i in range(50)]
        
        doc = make_document(
            uploaded_by=uploader,
            sent_to_all=False,
            recipients=users
        )
        
        # Очищаем уведомления о создании
        Notification.objects.all().delete()
        
        start_time = time.time()
        
        # Все ознакомились
        for user in users:
            DocumentAcknowledgement.objects.create(document=doc, user=user)
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Должно быть быстро (< 3 секунды)
        assert elapsed < 3.0, f"Массовое ознакомление заняло {elapsed:.2f}s"
        
        # Проверяем уведомление о завершении
        notifs = Notification.objects.filter(
            recipient=uploader,
            notification_type=notification_types['document_signed_all']
        )
        assert notifs.count() >= 1
    
    def test_query_count_for_notification_creation(
        self, make_user, notification_types, django_assert_max_num_queries
    ):
        """Количество запросов при создании уведомления."""
        uploader = make_user("uploader@example.com")
        recipients = [make_user(f"user{i}@example.com") for i in range(10)]
        
        # Проверяем, что не делаем N+1 запросов
        # Допустим разумный лимит для 10 получателей
        with django_assert_max_num_queries(100):
            doc = make_document(
                uploaded_by=uploader,
                sent_to_all=False,
                recipients=recipients
            )
    
    def test_notification_retrieval_performance(
        self, make_user, notification_types
    ):
        """Получение уведомлений пользователя."""
        user = make_user("user@example.com")
        uploader = make_user("uploader@example.com")
        
        # Создаем 50 документов для пользователя
        for i in range(50):
            make_document(
                uploaded_by=uploader,
                sent_to_all=False,
                recipients=[user]
            )
        
        start_time = time.time()
        
        # Получаем все уведомления
        notifs = list(
            Notification.objects.filter(recipient=user)
            .select_related('notification_type', 'notification_type__category')
            .prefetch_related('content_type')
        )
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Должно быть быстро (< 1 секунда)
        assert elapsed < 1.0, f"Получение 50 уведомлений заняло {elapsed:.2f}s"
        assert len(notifs) == 50


@pytest.mark.performance
class TestScalability:
    """Тесты масштабируемости."""
    
    def test_multiple_departments_performance(
        self, make_user, notification_types
    ):
        """Уведомления для нескольких отделов."""
        from employees.models import Department, EmployeeDepartment
        
        uploader = make_user("uploader@example.com")
        
        # Создаем 5 отделов по 10 сотрудников
        departments = []
        for d in range(5):
            dept = Department.objects.create(name=f"Department {d}")
            departments.append(dept)
            
            for e in range(10):
                emp = make_user(f"dept{d}_emp{e}@example.com")
                EmployeeDepartment.objects.create(
                    employee=emp,
                    department=dept,
                    is_active=True
                )
        
        start_time = time.time()
        
        # Документ для всех отделов
        doc = make_document(uploaded_by=uploader, sent_to_all=False)
        for dept in departments:
            doc.departments.add(dept)
        
        end_time = time.time()
        elapsed = end_time - start_time
        
        # Разумное время (< 5 секунд)
        assert elapsed < 5.0, f"Уведомления для 5 отделов заняли {elapsed:.2f}s"
        
        # Проверяем количество уведомлений
        notifs = Notification.objects.filter(
            notification_type=notification_types['document_ready']
        )
        assert notifs.count() == 50  # 5 отделов * 10 сотрудников
    
    def test_large_recipient_list_memory(
        self, make_user, notification_types
    ):
        """Использование памяти при большом списке получателей."""
        import tracemalloc
        
        uploader = make_user("uploader@example.com")
        recipients = [make_user(f"user{i}@example.com") for i in range(200)]
        
        tracemalloc.start()
        
        doc = make_document(
            uploaded_by=uploader,
            sent_to_all=False,
            recipients=recipients
        )
        
        current, peak = tracemalloc.get_traced_memory()
        tracemalloc.stop()
        
        # Пиковое использование памяти не должно превышать 50 МБ
        assert peak < 50 * 1024 * 1024, f"Пиковое использование памяти: {peak / 1024 / 1024:.2f} MB"
        
        # Проверяем результат
        notifs = Notification.objects.filter(
            notification_type=notification_types['document_ready']
        )
        assert notifs.count() == 200
