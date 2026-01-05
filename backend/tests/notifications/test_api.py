"""
Тесты для API endpoints уведомлений
"""
from django.test import TestCase
from django.contrib.auth import get_user_model
from rest_framework.test import APIClient
from rest_framework import status
from notifications.models import (
    NotificationCategory,
    NotificationType,
    Notification,
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


class NotificationAPITest(TestCase):
    """Тесты API уведомлений"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = create_test_user()
        self.client.force_authenticate(user=self.user)
        
        # Создаем категорию и тип
        self.category = NotificationCategory.objects.create(
            code='test_category',
            name='Test Category'
        )
        self.notification_type = NotificationType.objects.create(
            category=self.category,
            code='test_type',
            name='Test Type'
        )
        
        # Создаем тестовые уведомления
        for i in range(5):
            Notification.objects.create(
                recipient=self.user,
                notification_type=self.notification_type,
                title=f'Notification {i+1}',
                message=f'Message {i+1}',
                short_message=f'Short {i+1}'
            )
    
    def test_get_notifications(self):
        """Получение списка уведомлений"""
        response = self.client.get('/api/v1/notifications/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total'], 5)
        self.assertEqual(len(response.data['notifications']), 5)
    
    def test_get_notifications_with_pagination(self):
        """Пагинация"""
        response = self.client.get('/api/v1/notifications/?page=1&page_size=2')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total'], 5)
        self.assertEqual(len(response.data['notifications']), 2)
        self.assertEqual(response.data['page'], 1)
    
    def test_get_unread_notifications(self):
        """Фильтр непрочитанных"""
        response = self.client.get('/api/v1/notifications/?unread_only=true')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total'], 5)  # Все непрочитанные
    
    def test_get_unread_count(self):
        """Получение количества непрочитанных"""
        response = self.client.get('/api/v1/notifications/count/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['count'], 5)
    
    def test_mark_as_read(self):
        """Отметка уведомления как прочитанное"""
        notification = Notification.objects.filter(recipient=self.user).first()
        response = self.client.post(f'/api/v1/notifications/{notification.id}/read/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        notification.refresh_from_db()
        self.assertTrue(notification.is_read)
    
    def test_mark_all_as_read(self):
        """Отметка всех уведомлений как прочитанные"""
        response = self.client.post('/api/v1/notifications/read-all/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        unread_count = Notification.objects.filter(
            recipient=self.user,
            is_read=False
        ).count()
        self.assertEqual(unread_count, 0)
    
    def test_delete_notification(self):
        """Удаление уведомления"""
        notification = Notification.objects.filter(recipient=self.user).first()
        response = self.client.delete(f'/api/v1/notifications/{notification.id}/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Проверяем что уведомление заархивировано, а не удалено
        notification.refresh_from_db()
        self.assertTrue(notification.is_archived)
    
    def test_search_notifications(self):
        """Поиск уведомлений"""
        response = self.client.get('/api/v1/notifications/?search=Notification 3')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['total'], 1)
        self.assertEqual(response.data['notifications'][0]['title'], 'Notification 3')
    
    def test_unauthorized_access(self):
        """Доступ без авторизации"""
        self.client.force_authenticate(user=None)
        response = self.client.get('/api/v1/notifications/')
        
        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)


class WebPushAPITest(TestCase):
    """Тесты Web Push API"""
    
    def setUp(self):
        self.client = APIClient()
        self.user = create_test_user()
        self.client.force_authenticate(user=self.user)
    
    def test_get_vapid_public_key(self):
        """Получение VAPID публичного ключа"""
        response = self.client.get('/api/v1/notifications/push/vapid-key/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('vapid_public_key', response.data)
    
    def test_subscribe_push(self):
        """Подписка на push-уведомления"""
        data = {
            'endpoint': 'https://fcm.googleapis.com/fcm/send/test123',
            'keys': {
                'p256dh': 'test_p256dh_key',
                'auth': 'test_auth_key'
            },
            'device_name': 'Test Browser'
        }
        response = self.client.post('/api/v1/notifications/push/subscribe/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['status'], 'success')
        
        # Проверяем что подписка создана
        subscription = WebPushSubscription.objects.get(user=self.user)
        self.assertEqual(subscription.endpoint, data['endpoint'])
        self.assertEqual(subscription.device_name, 'Test Browser')
    
    def test_subscribe_push_missing_fields(self):
        """Подписка с отсутствующими полями"""
        data = {
            'endpoint': 'https://fcm.googleapis.com/fcm/send/test123'
            # Нет keys
        }
        response = self.client.post('/api/v1/notifications/push/subscribe/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
    
    def test_update_existing_subscription(self):
        """Обновление существующей подписки"""
        # Создаем первую подписку
        data1 = {
            'endpoint': 'https://fcm.googleapis.com/fcm/send/test123',
            'keys': {
                'p256dh': 'old_key',
                'auth': 'old_auth'
            },
            'device_name': 'Old Browser'
        }
        self.client.post('/api/v1/notifications/push/subscribe/', data1, format='json')
        
        # Обновляем подписку с новыми ключами
        data2 = {
            'endpoint': 'https://fcm.googleapis.com/fcm/send/test123',
            'keys': {
                'p256dh': 'new_key',
                'auth': 'new_auth'
            },
            'device_name': 'New Browser'
        }
        response = self.client.post('/api/v1/notifications/push/subscribe/', data2, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data['created'])  # Обновлена, не создана
        
        # Проверяем обновление
        subscription = WebPushSubscription.objects.get(user=self.user)
        self.assertEqual(subscription.p256dh_key, 'new_key')
        self.assertEqual(subscription.device_name, 'New Browser')
    
    def test_unsubscribe_push(self):
        """Отписка от push-уведомлений"""
        # Создаем подписку
        subscription = WebPushSubscription.objects.create(
            user=self.user,
            endpoint='https://fcm.googleapis.com/fcm/send/test123',
            p256dh_key='test_key',
            auth_key='test_auth'
        )
        
        # Отписываемся
        data = {'endpoint': subscription.endpoint}
        response = self.client.delete('/api/v1/notifications/push/unsubscribe/', data, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Проверяем что подписка удалена
        self.assertFalse(
            WebPushSubscription.objects.filter(id=subscription.id).exists()
        )
    
    def test_unsubscribe_all_push(self):
        """Отписка от всех подписок"""
        # Создаем несколько подписок
        for i in range(3):
            WebPushSubscription.objects.create(
                user=self.user,
                endpoint=f'https://fcm.googleapis.com/fcm/send/test{i}',
                p256dh_key=f'test_key_{i}',
                auth_key=f'test_auth_{i}'
            )
        
        # Отписываемся от всех
        response = self.client.delete('/api/v1/notifications/push/unsubscribe/', {}, format='json')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        
        # Проверяем что все подписки удалены
        self.assertEqual(
            WebPushSubscription.objects.filter(user=self.user).count(),
            0
        )
    
    def test_get_subscriptions(self):
        """Получение списка подписок"""
        # Создаем подписки
        for i in range(3):
            WebPushSubscription.objects.create(
                user=self.user,
                endpoint=f'https://fcm.googleapis.com/fcm/send/test{i}',
                p256dh_key=f'test_key_{i}',
                auth_key=f'test_auth_{i}',
                device_name=f'Device {i}'
            )
        
        response = self.client.get('/api/v1/notifications/push/subscriptions/')
        
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(len(response.data['subscriptions']), 3)
