#!/usr/bin/env python
"""
Скрипт для тестирования уведомлений модуля Requests.
Создает тестовые заявления и проверяет отправку уведомлений.

Использование:
    python scripts/utils/test_request_notifications.py
"""

import os
import django
import sys

# Добавляем backend в путь
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from requests_app.models import Request
from employees.models import Department
from notifications.models import Notification

Employee = get_user_model()

print("\n" + "="*70)
print(" ТЕСТИРОВАНИЕ УВЕДОМЛЕНИЙ МОДУЛЯ REQUESTS")
print("="*70 + "\n")

# Получаем тестовых пользователей
users = Employee.objects.filter(is_active=True)[:3]

if len(users) < 2:
    print("[ERROR] Нужно минимум 2 активных пользователя!")
    sys.exit(1)

author = users[0]
recipient = users[1]
cc_user = users[2] if len(users) > 2 else None

print(f"👤 Автор заявления: {author.get_full_name()} ({author.email})")
print(f"👤 Получатель: {recipient.get_full_name()} ({recipient.email})")
if cc_user:
    print(f"👤 В копии: {cc_user.get_full_name()} ({cc_user.email})")

# Получаем первый отдел (если есть)
department = Department.objects.first()
if not department:
    print("\n[WARNING] Нет отделов в системе. Создаем тестовый...")
    department = Department.objects.create(
        name="Тестовый отдел",
        head=recipient
    )

print(f"\n🏢 Отдел: {department.name}")
print("\n" + "="*70)

# Меню
print("\nВыберите тест:\n")
print("1. Новое заявление (уведомление получателям)")
print("2. Изменение статуса заявления (одобрение)")
print("3. Изменение статуса заявления (отклонение)")
print("4. Комментарий к заявлению")
print("5. Проверить все уведомления пользователя")
print("0. Выход")
print()

choice = input("Ваш выбор: ").strip()

if choice == '0':
    print("Выход.")
    sys.exit(0)

if choice == '1':
    print("\n📝 Создаем новое заявление...")
    
    # Создаем заявление
    request = Request.objects.create(
        employee=author,
        type='vacation',
        comment='Тестовое заявление на отпуск',
        status='pending',
        department=department
    )
    
    # Устанавливаем получателей (это триггерит m2m_changed сигнал)
    request.recipients.set([recipient])
    if cc_user:
        request.cc_users.set([cc_user])
    
    print(f"✅ Создано заявление #{request.id}")
    
    # Проверяем уведомления
    notifications = Notification.objects.filter(
        recipient__in=[recipient, cc_user] if cc_user else [recipient]
    ).order_by('-timestamp')[:5]
    
    print(f"\n📬 Отправлено уведомлений: {notifications.count()}")
    for notif in notifications:
        print(f"  - [{notif.recipient.username}] {notif.data.get('title', 'N/A')}")
        print(f"    Verb: {notif.verb} | Read: {notif.unread}")

elif choice == '2':
    # Находим или создаем заявление
    request = Request.objects.filter(status='pending').first()
    
    if not request:
        print("⚠️  Нет заявлений со статусом 'pending', создаем новое...")
        request = Request.objects.create(
            employee=author,
            type='vacation',
            comment='Тестовое заявление для одобрения',
            status='pending',
            department=department,
            approver=recipient
        )
        request.recipients.set([recipient])
    
    print(f"\n✅ Одобряем заявление #{request.id}...")
    
    request.approver = recipient
    request.status = 'approved'
    request.save()
    
    print(f"✅ Заявление одобрено!")
    
    # Проверяем уведомления
    notifications = Notification.objects.filter(
        verb='request_approved',
        recipient=author
    ).order_by('-timestamp')[:3]
    
    print(f"\n📬 Уведомлений об одобрении: {notifications.count()}")
    for notif in notifications:
        print(f"  - [{notif.recipient.username}] {notif.data.get('title', 'N/A')}")

elif choice == '3':
    # Находим или создаем заявление
    request = Request.objects.filter(status='pending').first()
    
    if not request:
        print("⚠️  Нет заявлений со статусом 'pending', создаем новое...")
        request = Request.objects.create(
            employee=author,
            type='vacation',
            comment='Тестовое заявление для отклонения',
            status='pending',
            department=department,
            approver=recipient
        )
        request.recipients.set([recipient])
    
    print(f"\n❌ Отклоняем заявление #{request.id}...")
    
    request.approver = recipient
    request.status = 'rejected'
    request.save()
    
    print(f"❌ Заявление отклонено!")
    
    # Проверяем уведомления
    notifications = Notification.objects.filter(
        verb='request_rejected',
        recipient=author
    ).order_by('-timestamp')[:3]
    
    print(f"\n📬 Уведомлений об отклонении: {notifications.count()}")
    for notif in notifications:
        print(f"  - [{notif.recipient.username}] {notif.data.get('title', 'N/A')}")

elif choice == '4':
    # Находим или создаем заявление
    request = Request.objects.first()
    
    if not request:
        print("⚠️  Нет заявлений, создаем новое...")
        request = Request.objects.create(
            employee=author,
            type='vacation',
            comment='Тестовое заявление',
            status='pending',
            department=department
        )
        request.recipients.set([recipient])
    
    print(f"\n💬 Добавляем комментарий к заявлению #{request.id}...")
    
    from requests_app.models import RequestComment
    
    comment = RequestComment.objects.create(
        request=request,
        author=recipient,
        text='Это тестовый комментарий к заявлению'
    )
    
    print(f"✅ Комментарий добавлен!")
    
    # Проверяем уведомления
    notifications = Notification.objects.filter(
        verb='request_comment',
        recipient=author
    ).order_by('-timestamp')[:3]
    
    print(f"\n📬 Уведомлений о комментарии: {notifications.count()}")
    for notif in notifications:
        print(f"  - [{notif.recipient.username}] {notif.data.get('title', 'N/A')}")
        print(f"    {notif.description[:80]}...")

elif choice == '5':
    print("\n📊 Все уведомления по заявлениям:\n")
    
    request_verbs = ['request_new', 'request_approved', 'request_rejected', 
                     'request_comment', 'request_status_changed']
    
    for user in users:
        count = Notification.objects.filter(
            recipient=user,
            verb__in=request_verbs
        ).count()
        
        unread = Notification.objects.filter(
            recipient=user,
            verb__in=request_verbs,
            unread=True
        ).count()
        
        print(f"👤 {user.username}: {count} всего, {unread} непрочитанных")
        
        recent = Notification.objects.filter(
            recipient=user,
            verb__in=request_verbs
        ).order_by('-timestamp')[:3]
        
        for notif in recent:
            read_icon = "✉️" if notif.unread else "✅"
            print(f"  {read_icon} {notif.verb}: {notif.data.get('title', 'N/A')[:50]}")

else:
    print("[ERROR] Неверный выбор")
    sys.exit(1)

print("\n" + "="*70)
print(" ГОТОВО!")
print("="*70)
print("\nДля проверки уведомлений:")
print("- Откройте http://localhost:9000/ и войдите под тестовым пользователем")
print("- Проверьте колокольчик в navbar")
print("- Проверьте вкладку в Chrome DevTools 'Network' → WS (WebSocket)")
print()
