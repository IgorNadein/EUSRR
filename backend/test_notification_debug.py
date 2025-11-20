#!/usr/bin/env python
"""
Скрипт для отладки уведомлений
"""
import os
import sys
import django
import logging

# Включаем подробное логирование
logging.basicConfig(level=logging.DEBUG)

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from employees.models import Employee
from notifications.services import NotificationService
from channels.layers import get_channel_layer
from asgiref.sync import async_to_sync

def main():
    """Создать тестовое уведомление с отладкой"""
    print("=" * 60)
    print("ТЕСТ СИСТЕМЫ УВЕДОМЛЕНИЙ")
    print("=" * 60)
    
    # Проверка Channel Layer
    channel_layer = get_channel_layer()
    print(f"\n1. Channel Layer: {type(channel_layer).__name__}")
    
    # Получаем пользователя
    user = Employee.objects.first()
    if not user:
        print("❌ Нет пользователей в системе!")
        sys.exit(1)
    
    print(f"\n2. Получатель: {user.last_name} {user.first_name} (ID={user.id})")
    print(f"   Email: {user.email}")
    
    # Создаём уведомление
    print("\n3. Создание уведомления...")
    notification = NotificationService.create_notification(
        recipient=user,
        notification_type_code='system_announcement',
        title='🔔 Тестовое уведомление',
        message='Это тестовое сообщение для проверки WebSocket. Если вы видите это в браузере - система работает!',
        action_url='/',
    )
    
    if not notification:
        print("❌ Не удалось создать уведомление!")
        sys.exit(1)
    
    print(f"✅ Уведомление создано: ID={notification.id}")
    print(f"   Заголовок: {notification.title}")
    print(f"   Отправлено веб: {notification.sent_web}")
    print(f"   Дата отправки: {notification.sent_at}")
    
    # Проверка отправки через WebSocket
    print(f"\n4. WebSocket группа: notifications_{user.id}")
    
    # Попробуем отправить напрямую
    print("\n5. Отправка тестового сообщения через Channel Layer...")
    try:
        async_to_sync(channel_layer.group_send)(
            f'notifications_{user.id}',
            {
                'type': 'notification_new',
                'notification': {
                    'id': notification.id,
                    'title': '🧪 Прямое тестовое сообщение',
                    'message': 'Это сообщение отправлено напрямую через Channel Layer',
                    'category': 'system',
                    'icon': 'bi-gear',
                    'color': 'light',
                    'priority': 'high',
                }
            }
        )
        print("✅ Сообщение отправлено в Channel Layer")
    except Exception as e:
        print(f"❌ Ошибка отправки: {e}")
    
    print("\n" + "=" * 60)
    print("ПРОВЕРЬТЕ БРАУЗЕР!")
    print("=" * 60)
    print("Вы должны увидеть:")
    print("  1. Toast уведомление справа вверху")
    print("  2. Badge с цифрой в navbar")
    print("  3. В консоли: [Notifications] Received: ...")
    print("=" * 60)

if __name__ == '__main__':
    main()
