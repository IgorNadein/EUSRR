#!/usr/bin/env python
"""
Тест полного цикла уведомлений

Проверяет:
1. Создание уведомления через notify.send()
2. Срабатывание post_save сигнала
3. Отправку задач в Celery
4. Наличие уведомления в БД
5. Выполнение задач Celery
"""

import django
import os
import sys
import time

# Setup Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
sys.path.insert(0, os.path.dirname(__file__))
django.setup()

from django.contrib.auth import get_user_model
from notifications.signals import notify
from notifications.models import Notification

User = get_user_model()


def test_notification_creation():
    """Тест создания уведомления"""
    
    print("\n" + "="*60)
    print("ТЕСТ СИСТЕМЫ УВЕДОМЛЕНИЙ")
    print("="*60)
    
    # 1. Находим двух пользователей
    print("\n1. Поиск пользователей...")
    users = User.objects.filter(is_active=True)[:2]
    
    if users.count() < 2:
        print("❌ Нужно минимум 2 активных пользователя")
        return
    
    sender = users[0]
    recipient = users[1]
    
    print(f"   ✅ Отправитель: {sender.username} (ID: {sender.id})")
    print(f"   ✅ Получатель: {recipient.username} (ID: {recipient.id})")
    
    # 2. Проверяем настройки получателя
    print("\n2. Проверка настроек получателя...")
    try:
        prefs = recipient.channel_preferences
        print(f"   ✅ web_enabled: {prefs.web_enabled}")
        print(f"   ✅ email_enabled: {prefs.email_enabled}")
        print(f"   ✅ push_enabled: {prefs.push_enabled}")
        print(f"   ✅ email_frequency: {prefs.email_frequency}")
        print(f"   ✅ DND период: {prefs.is_in_dnd_period()}")
    except Exception as e:
        print(f"   ⚠️ Нет настроек (будут созданы): {e}")
    
    # 3. Подсчет уведомлений до создания
    print("\n3. Подсчет уведомлений перед тестом...")
    count_before = Notification.objects.count()
    print(f"   Всего уведомлений в БД: {count_before}")
    
    # 4. Создаем уведомление
    print("\n4. Создание уведомления через notify.send()...")
    
    try:
        result = notify.send(
            sender=sender,
            recipient=recipient,
            verb='test_notification',
            description=f'🧪 Тестовое уведомление от {sender.username}',
            action_url='/test/',
            data={
                'test': True,
                'timestamp': time.time(),
            }
        )
        
        print(f"   ✅ notify.send() выполнен")
        print(f"   Результат: {result}")
        
    except Exception as e:
        print(f"   ❌ Ошибка при создании: {e}")
        import traceback
        traceback.print_exc()
        return
    
    # 5. Проверяем что уведомление создано в БД
    print("\n5. Проверка создания в БД...")
    time.sleep(0.1)  # Небольшая задержка для сохранения
    
    count_after = Notification.objects.count()
    new_notifications = count_after - count_before
    
    print(f"   Всего уведомлений в БД: {count_after}")
    print(f"   Создано новых: {new_notifications}")
    
    if new_notifications == 0:
        print("   ❌ Уведомление не создано в БД!")
        return
    
    # 6. Получаем созданное уведомление
    print("\n6. Детали созданного уведомления...")
    notification = Notification.objects.filter(recipient=recipient).order_by('-id').first()
    
    if notification:
        print(f"   ✅ ID: {notification.id}")
        print(f"   ✅ verb: {notification.verb}")
        print(f"   ✅ description: {notification.description}")
        print(f"   ✅ recipient: {notification.recipient.username}")
        print(f"   ✅ actor: {notification.actor}")
        print(f"   ✅ unread: {notification.unread}")
        print(f"   ✅ timestamp: {notification.timestamp}")
    else:
        print("   ❌ Уведомление не найдено!")
        return
    
    # 7. Ждем выполнения Celery задач
    print("\n7. Ожидание выполнения Celery задач...")
    print("   ⏳ Ждем 2 секунды...")
    time.sleep(2)
    
    # 8. Проверяем логи Celery
    print("\n8. Результаты:")
    print("   📋 Проверьте логи Celery worker на наличие:")
    print(f"      - Task notifications.send_websocket_notification[...] received")
    print(f"      - Notification {notification.id} not found (если есть race condition)")
    print(f"      - Task ... succeeded (если всё ОК)")
    
    print("\n" + "="*60)
    print("ТЕСТ ЗАВЕРШЕН")
    print("="*60)
    print("\nПроверьте:")
    print("1. Логи Celery worker")
    print("2. WebSocket соединение в браузере")
    print("3. Появилось ли уведомление в UI")
    print()


if __name__ == '__main__':
    test_notification_creation()
