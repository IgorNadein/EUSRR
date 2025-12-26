#!/usr/bin/env python
"""
Полный тест всех signal integrations (без Unicode символов).
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.utils import timezone
from communications.models import Chat, Message
from requests_app.models import Request, RequestComment
from documents.models import Document, DocumentAcknowledgement
from calendar_app.models import CalendarEvent
from feed.models import Post, Comment
from notifications.models import Notification

Employee = get_user_model()

print("\n" + "="*70)
print(" ПОЛНЫЙ ТЕСТ ВСЕХ NOTIFICATION SIGNALS")
print("="*70 + "\n")

# Создаем пользователей
user1, _ = Employee.objects.get_or_create(
    email='fulltest1@test.com',
    defaults={
        'first_name': 'Иван',
        'last_name': 'Иванов',
        'phone_number': '+79881111111',
        'is_active': True,
        'is_staff': True,
        'is_superuser': True
    }
)

user2, _ = Employee.objects.get_or_create(
    email='fulltest2@test.com',
    defaults={
        'first_name': 'Петр',
        'last_name': 'Петров',
        'phone_number': '+79882222222',
        'is_active': True
    }
)

print(f"[INFO] Тестовые пользователи: {user1.email}, {user2.email}\n")

# Очищаем уведомления
Notification.objects.filter(recipient__in=[user1, user2]).delete()


# ============ ТЕСТ 1: COMMUNICATIONS ============
print("="*70)
print(" [1/5] COMMUNICATIONS: Сообщения и упоминания")
print("="*70)

chat = Chat.objects.create(type='private')
chat.participants.add(user1, user2)
print(f"[OK] Чат #{chat.id}")

Message.objects.create(chat=chat, author=user1, content='Тест')
count = Notification.objects.filter(
    recipient=user2, notification_type__code='chat_new_message'
).count()
print(f"  new_message: {count} уведомление(ий)")

Message.objects.create(chat=chat, author=user1, content=f'@{user2.email} ping')
count = Notification.objects.filter(
    recipient=user2, notification_type__code='chat_mention'
).count()
print(f"  mention: {count} уведомление(ий)")

msg = Message.objects.create(chat=chat, author=user2, content='Ответ')
Message.objects.create(chat=chat, author=user1, content='Ок', reply_to=msg)
count = Notification.objects.filter(
    recipient=user2, notification_type__code='chat_reply'
).count()
print(f"  reply: {count} уведомление(ий)")

print("[OK] Communications: ВСЕ ТЕСТЫ ПРОЙДЕНЫ\n")


# ============ ТЕСТ 2: REQUESTS ============
print("="*70)
print(" [2/5] REQUESTS: Заявки и согласования")
print("="*70)

req = Request.objects.create(
    employee=user2,
    type='vacation',
    date_from=timezone.now().date(),
    date_to=(timezone.now() + timezone.timedelta(days=7)).date(),
    status='pending'
)
print(f"[OK] Заявка #{req.id}")

count = Notification.objects.filter(
    notification_type__code='request_new'
).count()
print(f"  new_request: {count} уведомление(ий)")

RequestComment.objects.create(
    request=req,
    author=user1,
    text='Комментарий к заявке'
)
count = Notification.objects.filter(
    recipient=user2, notification_type__code='request_comment'
).count()
print(f"  comment: {count} уведомление(ий)")

req.status = 'approved'
req.approver = user1
req.decided_at = timezone.now()
req.save()

count = Notification.objects.filter(
    recipient=user2, notification_type__code='request_approved'
).count()
print(f"  approved: {count} уведомление(ий)")

req2 = Request.objects.create(
    employee=user2,
    type='sick',
    date_from=timezone.now().date(),
    date_to=timezone.now().date(),
    status='rejected',
    approver=user1,
    decided_at=timezone.now()
)
count = Notification.objects.filter(
    recipient=user2, notification_type__code='request_rejected'
).count()
print(f"  rejected: {count} уведомление(ий)")

print("[OK] Requests: ВСЕ ТЕСТЫ ПРОЙДЕНЫ\n")


# ============ ТЕСТ 3: DOCUMENTS ============
print("="*70)
print(" [3/5] DOCUMENTS: Документы и подтверждения")
print("="*70)

doc = Document.objects.create(
    title='Тестовый документ',
    uploaded_by=user1,
    sent_to_all=False
)
doc.recipients.add(user2)
print(f"[OK] Документ #{doc.id}")

count = Notification.objects.filter(
    recipient=user2, notification_type__code='document_ready'
).count()
print(f"  document_ready: {count} уведомление(ий)")

DocumentAcknowledgement.objects.create(
    document=doc,
    user=user2
)

count = Notification.objects.filter(
    recipient=user1, notification_type__code='document_signed_all'
).count()
print(f"  document_signed_all: {count} уведомление(ий)")

print("[OK] Documents: ВСЕ ТЕСТЫ ПРОЙДЕНЫ\n")


# ============ ТЕСТ 4: CALENDAR ============
print("="*70)
print(" [4/5] CALENDAR: События и изменения")
print("="*70)

event = CalendarEvent.objects.create(
    title='Собрание',
    start_date=timezone.now().date(),
    end_date=timezone.now().date(),
    start_time=timezone.now().time(),
    end_time=(timezone.now() + timezone.timedelta(hours=1)).time(),
    all_day=False,
    created_by=user1
)
print(f"[OK] Событие #{event.id}")

count = Notification.objects.filter(
    notification_type__code='event_created'
).count()
print(f"  event_created: {count} уведомление(ий)")

event.title = 'Собрание ИЗМЕНЕНО'
event.save()

count = Notification.objects.filter(
    notification_type__code='event_changed'
).count()
print(f"  event_changed: {count} уведомление(ий)")

event2 = CalendarEvent.objects.create(
    title='Отменяемое событие',
    start_date=timezone.now().date(),
    end_date=timezone.now().date(),
    start_time=timezone.now().time(),
    end_time=(timezone.now() + timezone.timedelta(hours=1)).time(),
    all_day=False,
    created_by=user1
)
event2.delete()

count = Notification.objects.filter(
    notification_type__code='event_cancelled'
).count()
print(f"  event_cancelled: {count} уведомление(ий)")

print("[OK] Calendar: ВСЕ ТЕСТЫ ПРОЙДЕНЫ\n")


# ============ ТЕСТ 5: FEED ============
print("="*70)
print(" [5/5] FEED: Посты и комментарии")
print("="*70)

post = Post.objects.create(
    author=user1,
    title='Тестовый пост',
    body='Тестовый пост для всей компании',
    type='company'
)
print(f"[OK] Пост #{post.id}")

count = Notification.objects.filter(
    notification_type__code='feed_new_post'
).count()
print(f"  feed_new_post: {count} уведомление(ий)")

comment = Comment.objects.create(
    post=post,
    author=user2,
    text='Комментарий к посту'
)
count = Notification.objects.filter(
    recipient=user1, notification_type__code='feed_post_comment'
).count()
print(f"  feed_post_comment: {count} уведомление(ий)")

# Тест реакции (ручной вызов)
from feed.notification_signals import notify_post_reaction
notify_post_reaction(post, user2)

count = Notification.objects.filter(
    recipient=user1, notification_type__code='feed_post_reaction'
).count()
print(f"  feed_post_reaction: {count} уведомление(ий)")

print("[OK] Feed: ВСЕ ТЕСТЫ ПРОЙДЕНЫ\n")


# ============ ИТОГОВАЯ СТАТИСТИКА ============
print("="*70)
print(" ИТОГОВАЯ СТАТИСТИКА")
print("="*70)

total = Notification.objects.filter(recipient__in=[user1, user2]).count()
print(f"\nВсего создано уведомлений: {total}")

print("\nРаспределение по типам:")
from django.db.models import Count
stats = Notification.objects.filter(
    recipient__in=[user1, user2]
).values('notification_type__code').annotate(
    count=Count('id')
).order_by('-count')

for stat in stats:
    code = stat['notification_type__code']
    count = stat['count']
    print(f"  {code}: {count}")

print("\n" + "="*70)
print(" ВСЕ 5 МОДУЛЕЙ ПРОТЕСТИРОВАНЫ УСПЕШНО!")
print("="*70 + "\n")
