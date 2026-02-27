#!/usr/bin/env python
"""
Скрипт для создания тестовых уведомлений в реальном времени.
Используйте этот скрипт для проверки работы системы уведомлений.
"""

import os
import django
import sys

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from notifications.services import NotificationService
from communications.models import Chat, Message
from django.utils import timezone

Employee = get_user_model()

print("\n" + "="*70)
print(" ГЕНЕРАТОР ТЕСТОВЫХ УВЕДОМЛЕНИЙ")
print("="*70 + "\n")

# Получить первого активного пользователя
user = Employee.objects.filter(is_active=True).first()

if not user:
    print("[ERROR] Нет активных пользователей в системе!")
    sys.exit(1)

print(f"Получатель: {user.get_full_name()} ({user.email})\n")

# Меню
print("Выберите тип уведомления для генерации:")
print()
print("1. Новое сообщение в чате")
print("2. Новый документ")
print("3. Одобрена заявка")
print("4. Новое событие в календаре")
print("5. Новая публикация")
print("6. Системное уведомление")
print("7. Создать 5 разных уведомлений")
print("0. Выход")
print()

choice = input("Ваш выбор: ").strip()

if choice == '0':
    print("Выход.")
    sys.exit(0)

if choice == '1':
    # Новое сообщение в чате
    notification = NotificationService.create_notification(
        recipient=user,
        notification_type_code='chat_new_message',
        title='Новое сообщение в чате "Общий"',
        message='Иван Иванов: Всем привет! Напоминаю о собрании в 15:00',
        action_url='/communications/chat/1/',
        metadata={'chat_id': 1, 'message_id': 123}
    )
    print(f"[OK] Создано уведомление #{notification.id}: {notification.title}")

elif choice == '2':
    # Новый документ
    notification = NotificationService.create_notification(
        recipient=user,
        notification_type_code='document_ready',
        title='Новый документ на ознакомление',
        message='Администратор загрузил документ "Правила внутреннего распорядка 2025". Требуется ознакомление до 25.11.2025',
        action_url='/documents/5/',
        metadata={'document_id': 5, 'deadline': '2025-11-25'}
    )
    print(f"[OK] Создано уведомление #{notification.id}: {notification.title}")

elif choice == '3':
    # Одобрена заявка
    notification = NotificationService.create_notification(
        recipient=user,
        notification_type_code='request_approved',
        title='Заявка одобрена',
        message='Ваша заявка на отпуск с 01.12.2025 по 14.12.2025 одобрена руководителем Петр Петров',
        action_url='/requests/10/',
        metadata={'request_id': 10, 'approver_id': 2}
    )
    print(f"[OK] Создано уведомление #{notification.id}: {notification.title}")

elif choice == '4':
    # Новое событие
    notification = NotificationService.create_notification(
        recipient=user,
        notification_type_code='event_created',
        title='Новое событие: Корпоратив',
        message='Добавлено событие "Новогодний корпоратив" на 28.12.2025 18:00. Место: Ресторан "Прага"',
        action_url='/calendar/events/15/',
        metadata={'event_id': 15, 'event_date': '2025-12-28'}
    )
    print(f"[OK] Создано уведомление #{notification.id}: {notification.title}")

elif choice == '5':
    # Новая публикация
    notification = NotificationService.create_notification(
        recipient=user,
        notification_type_code='feed_new_post',
        title='Новая публикация от CEO',
        message='Алексей Сидоров опубликовал: "Подведение итогов года. Наши достижения и планы на 2026..."',
        action_url='/feed/posts/42/',
        metadata={'post_id': 42, 'author_id': 1}
    )
    print(f"[OK] Создано уведомление #{notification.id}: {notification.title}")

elif choice == '6':
    # Системное
    notification = NotificationService.create_notification(
        recipient=user,
        notification_type_code='system_announcement',
        title='Системное обслуживание',
        message='Планируется обслуживание системы 25.11.2025 с 02:00 до 04:00. Возможны кратковременные перерывы в работе.',
        action_url='/announcements/3/',
        metadata={'maintenance_date': '2025-11-25', 'duration_hours': 2}
    )
    print(f"[OK] Создано уведомление #{notification.id}: {notification.title}")

elif choice == '7':
    # Создать несколько разных
    notifications = []
    
    # 1. Сообщение
    n = NotificationService.create_notification(
        recipient=user,
        notification_type_code='chat_new_message',
        title='Сообщение от Мария Смирнова',
        message='Можете подойти в кабинет?',
        action_url='/communications/chat/2/',
    )
    notifications.append(n)
    
    # 2. Комментарий к заявке
    n = NotificationService.create_notification(
        recipient=user,
        notification_type_code='request_comment',
        title='Комментарий к заявке',
        message='HR отдел добавил комментарий: "Необходимо приложить справку"',
        action_url='/requests/8/',
    )
    notifications.append(n)
    
    # 3. Упоминание
    n = NotificationService.create_notification(
        recipient=user,
        notification_type_code='chat_mention',
        title='Вас упомянул Олег Иванов',
        message=f'@{user.email} посмотри пожалуйста этот документ',
        action_url='/communications/chat/3/',
    )
    notifications.append(n)
    
    # 4. Событие изменено
    n = NotificationService.create_notification(
        recipient=user,
        notification_type_code='event_changed',
        title='Событие изменено',
        message='Время планерки перенесено с 14:00 на 15:30',
        action_url='/calendar/events/20/',
    )
    notifications.append(n)
    
    # 5. Комментарий к посту
    n = NotificationService.create_notification(
        recipient=user,
        notification_type_code='feed_post_comment',
        title='Комментарий к вашей публикации',
        message='Анна Петрова прокомментировала ваш пост',
        action_url='/feed/posts/30/',
    )
    notifications.append(n)
    
    print(f"[OK] Создано {len(notifications)} уведомлений:")
    for n in notifications:
        print(f"  - #{n.id}: {n.title}")

else:
    print("[ERROR] Неверный выбор")
    sys.exit(1)

print()
print("="*70)
print(" ГОТОВО! Проверьте уведомления в интерфейсе")
print("="*70)
print()
print("Откройте: http://localhost:9000/")
print("- Колокольчик в navbar должен показать новое уведомление")
print("- Должен прийти WebSocket с обновлением")
print("- Должно сработать браузерное уведомление (если разрешено)")
print("- Должен воспроизвестись звук (если включен)")
print()
