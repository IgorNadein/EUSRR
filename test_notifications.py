"""
Тестовый скрипт для проверки системы уведомлений
Запуск: python backend/test_notifications.py
"""

import os
import sys
import django

# Настройка Django окружения
sys.path.insert(0, os.path.join(os.path.dirname(__file__), 'backend'))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from notifications.services import NotificationService
from notifications.models import NotificationCategory, NotificationType, Notification

User = get_user_model()

print("=" * 80)
print("ТЕСТ СИСТЕМЫ УВЕДОМЛЕНИЙ")
print("=" * 80)

# Проверка категорий
print("\n1. Проверка категорий:")
categories = NotificationCategory.objects.all()
print(f"   Создано категорий: {categories.count()}")
for cat in categories:
    print(f"   - {cat.name} ({cat.code}): {cat.types.count()} типов")

# Проверка типов
print("\n2. Проверка типов:")
types = NotificationType.objects.all()
print(f"   Создано типов: {types.count()}")

# Получить первого пользователя
print("\n3. Тестовое уведомление:")
try:
    user = User.objects.first()
    if user:
        print(f"   Пользователь: {user.get_full_name() or user.username}")
        
        # Создать тестовое уведомление
        notification = NotificationService.create_notification(
            recipient=user,
            notification_type_code='system_new_feature',
            title='Система уведомлений запущена!',
            message='Базовая инфраструктура системы уведомлений успешно создана и готова к работе. Этап 1 завершен!',
            action_url='/notifications/',
            send_immediately=True
        )
        
        if notification:
            print(f"   ✅ Уведомление создано: ID={notification.id}")
            print(f"   Заголовок: {notification.title}")
            print(f"   Отправлено на веб: {notification.sent_web}")
        else:
            print("   ⚠️ Уведомление не создано (возможно, тип отключен)")
    else:
        print("   ⚠️ Пользователи не найдены")
except Exception as e:
    print(f"   ❌ Ошибка: {e}")

# Статистика
print("\n4. Статистика:")
total_notifications = Notification.objects.count()
print(f"   Всего уведомлений: {total_notifications}")

print("\n" + "=" * 80)
print("ТЕСТ ЗАВЕРШЕН")
print("=" * 80)
