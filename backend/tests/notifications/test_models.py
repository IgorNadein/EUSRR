"""
Тесты для моделей уведомлений
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from notifications.models import (
    NotificationCategory,
    NotificationType,
    Notification,
    UserNotificationSettings,
    WebPushSubscription,
)

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


class NotificationCategoryTest(TestCase):
    """Тесты категорий уведомлений"""
    
    def setUp(self):
        self.category = NotificationCategory.objects.create(
            code='test_category',
            name='Test Category',
            icon='bi-test',
            color='primary'
        )
    
    def test_category_creation(self):
        """Создание категории"""
        self.assertEqual(self.category.code, 'test_category')
        self.assertEqual(self.category.name, 'Test Category')
        self.assertTrue(self.category.is_active)
    
    def test_category_str(self):
        """Строковое представление"""
        self.assertEqual(str(self.category), 'Test Category')


class NotificationTypeTest(TestCase):
    """Тесты типов уведомлений"""
    
    def setUp(self):
        self.category = NotificationCategory.objects.create(
            code='test_category',
            name='Test Category'
        )
        self.notification_type = NotificationType.objects.create(
            category=self.category,
            code='test_type',
            name='Test Type',
            default_enabled=True,
            priority='normal'
        )
    
    def test_type_creation(self):
        """Создание типа уведомления"""
        self.assertEqual(self.notification_type.code, 'test_type')
        self.assertEqual(self.notification_type.category, self.category)
        self.assertTrue(self.notification_type.default_enabled)
        self.assertEqual(self.notification_type.priority, 'normal')
    
    def test_type_str(self):
        """Строковое представление"""
        self.assertEqual(str(self.notification_type), 'Test Category: Test Type')


class NotificationTest(TestCase):
    """Тесты уведомлений"""
    
    def setUp(self):
        self.user = create_test_user()
        self.category = NotificationCategory.objects.create(
            code='test_category',
            name='Test Category'
        )
        self.notification_type = NotificationType.objects.create(
            category=self.category,
            code='test_type',
            name='Test Type'
        )
        self.notification = Notification.objects.create(
            recipient=self.user,
            notification_type=self.notification_type,
            title='Test Notification',
            message='Test message',
            short_message='Test'
        )
    
    def test_notification_creation(self):
        """Создание уведомления"""
        self.assertEqual(self.notification.recipient, self.user)
        self.assertEqual(self.notification.title, 'Test Notification')
        self.assertFalse(self.notification.is_read)
        self.assertFalse(self.notification.is_archived)
    
    def test_mark_as_read(self):
        """Отметка как прочитанное"""
        self.assertFalse(self.notification.is_read)
        self.assertIsNone(self.notification.read_at)
        
        self.notification.mark_as_read()
        
        self.assertTrue(self.notification.is_read)
        self.assertIsNotNone(self.notification.read_at)
    
    def test_archive(self):
        """Архивирование"""
        self.assertFalse(self.notification.is_archived)
        self.assertIsNone(self.notification.archived_at)
        
        self.notification.archive()
        
        self.assertTrue(self.notification.is_archived)
        self.assertIsNotNone(self.notification.archived_at)


class UserNotificationSettingsTest(TestCase):
    """Тесты настроек уведомлений пользователя"""
    
    def setUp(self):
        self.user = create_test_user()
        self.category = NotificationCategory.objects.create(
            code='test_category',
            name='Test Category'
        )
        self.notification_type = NotificationType.objects.create(
            category=self.category,
            code='test_type',
            name='Test Type'
        )
        self.settings = UserNotificationSettings.objects.create(
            user=self.user,
            notification_type=self.notification_type,
            is_enabled=True,
            send_web=True,
            send_email=False
        )
    
    def test_settings_creation(self):
        """Создание настроек"""
        self.assertEqual(self.settings.user, self.user)
        self.assertTrue(self.settings.is_enabled)
        self.assertTrue(self.settings.send_web)
        self.assertFalse(self.settings.send_email)


class WebPushSubscriptionTest(TestCase):
    """Тесты Web Push подписок"""
    
    def setUp(self):
        self.user = create_test_user()
        self.subscription = WebPushSubscription.objects.create(
            user=self.user,
            endpoint='https://fcm.googleapis.com/fcm/send/test123',
            p256dh_key='test_p256dh_key',
            auth_key='test_auth_key',
            device_name='Test Device'
        )
    
    def test_subscription_creation(self):
        """Создание подписки"""
        self.assertEqual(self.subscription.user, self.user)
        self.assertEqual(self.subscription.device_name, 'Test Device')
        self.assertTrue(self.subscription.is_active)
        self.assertEqual(self.subscription.error_count, 0)
    
    def test_mark_used(self):
        """Обновление времени использования"""
        self.assertIsNone(self.subscription.last_used_at)
        
        self.subscription.mark_used()
        
        self.assertIsNotNone(self.subscription.last_used_at)
    
    def test_increment_error(self):
        """Инкремент ошибок"""
        self.assertEqual(self.subscription.error_count, 0)
        
        self.subscription.increment_error('Test error')
        
        self.assertEqual(self.subscription.error_count, 1)
        self.assertEqual(self.subscription.last_error, 'Test error')
        self.assertTrue(self.subscription.is_active)
    
    def test_auto_deactivate_after_5_errors(self):
        """Автоматическая деактивация после 5 ошибок"""
        for i in range(5):
            self.subscription.increment_error(f'Error {i+1}')
        
        self.subscription.refresh_from_db()
        self.assertFalse(self.subscription.is_active)
        self.assertEqual(self.subscription.error_count, 5)
    
    def test_reset_errors(self):
        """Сброс ошибок"""
        self.subscription.increment_error('Test error')
        self.assertEqual(self.subscription.error_count, 1)
        
        self.subscription.reset_errors()
        
        self.assertEqual(self.subscription.error_count, 0)
        self.assertEqual(self.subscription.last_error, '')
    
    def test_unique_together(self):
        """Уникальность user + endpoint"""
        with self.assertRaises(Exception):
            WebPushSubscription.objects.create(
                user=self.user,
                endpoint='https://fcm.googleapis.com/fcm/send/test123',
                p256dh_key='another_key',
                auth_key='another_auth'
            )
