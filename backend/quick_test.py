#!/usr/bin/env python
"""
Быстрый тест signals без Unicode символов.
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from communications.models import Chat, Message
from notifications.models import Notification

Employee = get_user_model()

print("\n" + "="*60)
print(" БЫСТРЫЙ ТЕСТ СИСТЕМЫ УВЕДОМЛЕНИЙ")
print("="*60 + "\n")

# Создаем пользователей
user1, _ = Employee.objects.get_or_create(
    email='quicktest1@test.com',
    defaults={
        'first_name': 'User',
        'last_name': 'One',
        'phone_number': '+79991111111',
        'is_active': True
    }
)

user2, _ = Employee.objects.get_or_create(
    email='quicktest2@test.com',
    defaults={
        'first_name': 'User',
        'last_name': 'Two',
        'phone_number': '+79992222222',
        'is_active': True
    }
)

print(f"[INFO] Пользователи: {user1.email}, {user2.email}\n")

# Очищаем старые уведомления
Notification.objects.filter(recipient__in=[user1, user2]).delete()

# ТЕСТ 1: Приватный чат и сообщение
print("="*60)
print(" ТЕСТ: Communications - Сообщения и упоминания")
print("="*60)

chat = Chat.objects.create(type='private')
chat.participants.add(user1, user2)
print(f"[OK] Создан чат #{chat.id}")

# Простое сообщение
msg1 = Message.objects.create(
    chat=chat,
    author=user1,
    content='Привет! Как дела?'
)

count = Notification.objects.filter(
    recipient=user2,
    notification_type__code='chat_new_message'
).count()
print(f"[{'OK' if count > 0 else 'FAIL'}] Уведомление о новом сообщении: {count}")

# Упоминание
msg2 = Message.objects.create(
    chat=chat,
    author=user1,
    content=f'@{user2.email} нужна помощь!'
)

count = Notification.objects.filter(
    recipient=user2,
    notification_type__code='chat_mention'
).count()
print(f"[{'OK' if count > 0 else 'FAIL'}] Уведомление об упоминании: {count}")

# Ответ на сообщение
msg3 = Message.objects.create(
    chat=chat,
    author=user2,
    content='Конечно!',
    reply_to=msg1
)

count = Notification.objects.filter(
    recipient=user1,
    notification_type__code='chat_reply'
).count()
print(f"[{'OK' if count > 0 else 'FAIL'}] Уведомление об ответе: {count}")

# Итого
total = Notification.objects.filter(recipient__in=[user1, user2]).count()
print(f"\n[INFO] Всего создано уведомлений: {total}")

# Показываем список
print("\nСозданные уведомления:")
for notif in Notification.objects.filter(recipient__in=[user1, user2])[:10]:
    print(f"  - {notif.recipient.email}: [{notif.notification_type.code}] {notif.title}")

print("\n" + "="*60)
print(" ТЕСТ ЗАВЕРШЕН!")
print("="*60 + "\n")
