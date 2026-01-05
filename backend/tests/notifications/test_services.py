"""
Тесты для NotificationService
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from notifications.models import (
    NotificationCategory,
    NotificationType,
    Notification,
    UserNotificationSettings,
)
from notifications.services import NotificationService

User = get_user_model()


def create_test_user(email='test@example.com', phone='+79990000001'):
    """Helper для создания тестового пользователя с обязательным phone_number"""
    return User.objects.create_user(
        email=email,
        phone_number=phone,
        password='testpass123',
        first_name='Test',
        last_name='User',
        is_active=True
    )


class NotificationServiceTest(TestCase):
    """Тесты сервиса уведомлений"""
    
    def setUp(self):
        self.user = create_test_user()
        
        self.category = NotificationCategory.objects.create(
            code='test_category',
            name='Test Category'
        )
        
        self.notification_type = NotificationType.objects.create(
            category=self.category,
            code='test_type',
            name='Test Type',
            default_enabled=True
        )
    
    def test_create_notification(self):
        """Создание уведомления через сервис"""
        notification = NotificationService.create_notification(
            recipient=self.user,
            notification_type_code='test_type',
            title='Test Title',
            message='Test Message',
            action_url='/test/',
            send_immediately=False
        )
        
        self.assertIsNotNone(notification)
        self.assertEqual(notification.recipient, self.user)
        self.assertEqual(notification.title, 'Test Title')
        self.assertEqual(notification.message, 'Test Message')
        self.assertEqual(notification.action_url, '/test/')
    
    def test_create_notification_invalid_type(self):
        """Создание с несуществующим типом"""
        notification = NotificationService.create_notification(
            recipient=self.user,
            notification_type_code='invalid_type',
            title='Test',
            message='Test',
            send_immediately=False
        )
        
        self.assertIsNone(notification)
    
    def test_get_user_settings_creates_if_not_exists(self):
        """Автоматическое создание настроек"""
        settings = NotificationService.get_user_settings(
            self.user,
            self.notification_type
        )
        
        self.assertIsNotNone(settings)
        self.assertEqual(settings.user, self.user)
        self.assertEqual(settings.notification_type, self.notification_type)
        self.assertTrue(settings.is_enabled)
    
    def test_mark_as_read(self):
        """Отметка как прочитанное через сервис"""
        notification = Notification.objects.create(
            recipient=self.user,
            notification_type=self.notification_type,
            title='Test',
            message='Test'
        )
        
        success = NotificationService.mark_as_read(notification.id, self.user)
        
        self.assertTrue(success)
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
    
    def test_mark_as_read_wrong_user(self):
        """Попытка прочитать чужое уведомление"""
        other_user = create_test_user(
            email='other@example.com',
            phone='+79990000002'
        )
        
        notification = Notification.objects.create(
            recipient=other_user,
            notification_type=self.notification_type,
            title='Test',
            message='Test'
        )
        
        success = NotificationService.mark_as_read(notification.id, self.user)
        
        self.assertFalse(success)
        notification.refresh_from_db()
        self.assertFalse(notification.is_read)
    
    def test_mark_all_as_read(self):
        """Отметка всех как прочитанные"""
        # Создаем несколько уведомлений
        for i in range(5):
            Notification.objects.create(
                recipient=self.user,
                notification_type=self.notification_type,
                title=f'Test {i}',
                message=f'Message {i}'
            )
        
        count = NotificationService.mark_all_as_read(self.user)
        
        self.assertEqual(count, 5)
        unread = Notification.objects.filter(
            recipient=self.user,
            is_read=False
        ).count()
        self.assertEqual(unread, 0)
