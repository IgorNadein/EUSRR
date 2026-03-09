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
from notifications.signals import notify
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
    notify.send(
        sender=None,
        recipient=user,
        verb='chat_new_message',
        description='Иван Иванов: Всем привет! Напоминаю о собрании в 15:00',
        action_url='/communications/chat/1/',
        data={'title': 'Новое сообщение в чате "Общий"', 'chat_id': 1, 'message_id': 123},
    )
    print('[OK] Уведомление отправлено: chat_new_message')

elif choice == '2':
    # Новый документ
    notify.send(
        sender=None,
        recipient=user,
        verb='document_ready',
        description='Администратор загрузил документ "Правила внутреннего распорядка 2025". Требуется ознакомление до 25.11.2025',
        action_url='/documents/5/',
        data={'title': 'Новый документ на ознакомление', 'document_id': 5, 'deadline': '2025-11-25'},
    )
    print('[OK] Уведомление отправлено: document_ready')

elif choice == '3':
    # Одобрена заявка
    notify.send(
        sender=None,
        recipient=user,
        verb='request_approved',
        description='Ваша заявка на отпуск с 01.12.2025 по 14.12.2025 одобрена руководителем Петр Петров',
        action_url='/requests/10/',
        data={'title': 'Заявка одобрена', 'request_id': 10, 'approver_id': 2},
    )
    print('[OK] Уведомление отправлено: request_approved')

elif choice == '4':
    # Новое событие
    notify.send(
        sender=None,
        recipient=user,
        verb='event_created',
        description='Добавлено событие "Новогодний корпоратив" на 28.12.2025 18:00. Место: Ресторан "Прага"',
        action_url='/calendar/events/15/',
        data={'title': 'Новое событие: Корпоратив', 'event_id': 15, 'event_date': '2025-12-28'},
    )
    print('[OK] Уведомление отправлено: event_created')

elif choice == '5':
    # Новая публикация
    notify.send(
        sender=None,
        recipient=user,
        verb='feed_new_post',
        description='Алексей Сидоров опубликовал: "Подведение итогов года. Наши достижения и планы на 2026..."',
        action_url='/feed/posts/42/',
        data={'title': 'Новая публикация от CEO', 'post_id': 42, 'author_id': 1},
    )
    print('[OK] Уведомление отправлено: feed_new_post')

elif choice == '6':
    # Системное
    notify.send(
        sender=None,
        recipient=user,
        verb='system_announcement',
        description='Планируется обслуживание системы 25.11.2025 с 02:00 до 04:00. Возможны кратковременные перерывы в работе.',
        action_url='/announcements/3/',
        data={'title': 'Системное обслуживание', 'maintenance_date': '2025-11-25', 'duration_hours': 2},
    )
    print('[OK] Уведомление отправлено: system_announcement')

elif choice == '7':
    # Создать несколько разных
    items = [
        ('chat_new_message', 'Сообщение от Мария Смирнова',
         'Можете подойти в кабинет?', '/communications/chat/2/'),
        ('request_comment', 'Комментарий к заявке',
         'HR отдел добавил комментарий: "Необходимо приложить справку"', '/requests/8/'),
        ('chat_mention', 'Вас упомянул Олег Иванов',
         f'@{user.email} посмотри пожалуйста этот документ', '/communications/chat/3/'),
        ('event_changed', 'Событие изменено',
         'Время планерки перенесено с 14:00 на 15:30', '/calendar/events/20/'),
        ('feed_post_comment', 'Комментарий к вашей публикации',
         'Анна Петрова прокомментировала ваш пост', '/feed/posts/30/'),
    ]
    for verb, title, description, url in items:
        notify.send(
            sender=None,
            recipient=user,
            verb=verb,
            description=description,
            action_url=url,
            data={'title': title},
        )
    print(f'[OK] Отправлено {len(items)} уведомлений:')
    for verb, title, *_ in items:
        print(f'  - {verb}: {title}')

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
