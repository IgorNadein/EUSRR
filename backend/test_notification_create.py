#!/usr/bin/env python
"""
Скрипт для создания тестового уведомления
"""
import os
import sys
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from employees.models import Employee
from notifications.services import NotificationService

def main():
    """Создать тестовое уведомление"""
    # Получаем первого пользователя
    user = Employee.objects.first()
    
    if not user:
        print("❌ Нет пользователей в системе!")
        sys.exit(1)
    
    # Создаём тестовое уведомление
    notification = NotificationService.create_notification(
        recipient=user,
        notification_type_code='system_announcement',
        title='🎉 Тестовое уведомление',
        message='Проверка real-time уведомлений через WebSocket. Вы должны увидеть toast справа вверху!',
        action_url='/',
    )
    
    print(f'✅ Создано уведомление ID={notification.id}')
    print(f'👤 Получатель: {user.last_name} {user.first_name}')
    print(f'📧 Отправлено на веб: {notification.sent_web}')
    print(f'📝 Приоритет: {notification.notification_type.priority}')
    print(f'🔔 Категория: {notification.notification_type.category.name}')
    print()
    print('Проверьте браузер - должен появиться toast и обновиться badge!')

if __name__ == '__main__':
    main()
