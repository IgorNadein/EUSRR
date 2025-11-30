#!/usr/bin/env python
"""
Создаём тестовое сообщение в объявлении и проверяем уведомления
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from communications.models import Chat, Message
from employees.models import Employee
from notifications.models import Notification

def create_test_message():
    """Создаёт тестовое сообщение в объявлении"""
    
    # Находим чат-объявление
    announcement = Chat.objects.filter(type='announcement').first()
    
    if not announcement:
        print("❌ Нет объявлений в системе")
        return
    
    print(f"✓ Найдено объявление: {announcement.name}")
    print(f"  Created by: {announcement.created_by}")
    
    # Подсчитываем уведомления ДО
    notif_count_before = Notification.objects.count()
    print(f"\nУведомлений ДО создания сообщения: {notif_count_before}")
    
    # Создаём сообщение
    message = Message.objects.create(
        chat=announcement,
        author=announcement.created_by,
        content="ТЕСТОВОЕ ОБЪЯВЛЕНИЕ для проверки уведомлений"
    )
    
    print(f"\n✓ Создано сообщение ID={message.id}")
    
    # Подсчитываем уведомления ПОСЛЕ
    notif_count_after = Notification.objects.count()
    print(f"Уведомлений ПОСЛЕ создания сообщения: {notif_count_after}")
    print(f"Создано новых уведомлений: {notif_count_after - notif_count_before}")
    
    # Проверяем уведомления для этого сообщения
    message_notifs = Notification.objects.filter(
        content_type__model='message',
        object_id=message.id
    )
    
    print(f"\nУведомлений для сообщения ID={message.id}: {message_notifs.count()}")
    
    if message_notifs.exists():
        print("\n📧 Список уведомлений:")
        for n in message_notifs:
            print(f"  - Получатель: {n.recipient.get_full_name()}")
            print(f"    Тип: {n.notification_type.code}")
            print(f"    Заголовок: {n.title}")
            print()
    else:
        print("\n❌ Уведомления НЕ созданы!")
        print("\nПроверяем настройки:")
        print(f"  - message.is_system: {message.is_system}")
        print(f"  - message.is_deleted: {message.is_deleted}")
        print(f"  - chat.type: {announcement.type}")
        
        # Проверяем участников
        participants = announcement.get_participants
        print(f"  - Участников: {participants.count()}")
        for p in participants:
            print(f"    * {p.get_full_name()} (ID={p.id})")
        
        print(f"  - Автор: {message.author.get_full_name()} (ID={message.author.id})")
        
        # Участники без автора
        participants_no_author = participants.exclude(id=message.author.id)
        print(f"  - Участников без автора: {participants_no_author.count()}")

if __name__ == '__main__':
    create_test_message()
