#!/usr/bin/env python
"""
Тестирование уведомлений для объявлений
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from communications.models import Chat, Message
from employees.models import Employee

def test_announcement_notifications():
    """Проверяет, что уведомления для объявлений отправляются всем"""
    
    # Находим чат-объявление
    announcement = Chat.objects.filter(type='announcement').first()
    
    if not announcement:
        print("❌ Нет объявлений в системе")
        return
    
    print(f"✓ Найдено объявление: {announcement.name}")
    print(f"  Created by: {announcement.created_by}")
    print(f"  include_all_employees: {announcement.include_all_employees}")
    
    # Получаем участников
    participants = announcement.get_participants
    print(f"  Участников (get_participants): {participants.count()}")
    
    # Список участников
    for p in participants[:5]:
        print(f"    - {p.get_full_name() or p.username} ({p.email})")
    
    if participants.count() > 5:
        print(f"    ... и ещё {participants.count() - 5}")
    
    # Проверяем последнее сообщение
    last_message = announcement.messages.order_by('-created_at').first()
    
    if last_message:
        print(f"\n✓ Последнее сообщение:")
        print(f"  ID: {last_message.id}")
        print(f"  Автор: {last_message.author}")
        print(f"  Текст: {last_message.content[:50]}...")
        print(f"  Создано: {last_message.created_at}")
        
        # Проверяем уведомления
        from notifications.models import Notification
        notifications = Notification.objects.filter(
            content_type__model='message',
            object_id=last_message.id
        )
        
        print(f"\n✓ Уведомлений создано: {notifications.count()}")
        
        # Проверяем тип уведомлений
        announcement_notifs = notifications.filter(
            notification_type__code='announcement_new_message'
        )
        print(f"  Типа 'announcement_new_message': {announcement_notifs.count()}")
        
        # Показываем первые 5
        for n in notifications[:5]:
            print(f"    - Для: {n.recipient.get_full_name()}")
            print(f"      Тип: {n.notification_type.code}")
            print(f"      Прочитано: {n.is_read}")
    else:
        print("\n❌ Нет сообщений в объявлении")
    
    # Итоги
    print("\n" + "="*60)
    all_employees = Employee.objects.filter(is_active=True).count()
    print(f"Всего активных сотрудников: {all_employees}")
    print(f"Участников объявления: {participants.count()}")
    
    if participants.count() == all_employees:
        print("✅ ПРАВИЛЬНО: Все сотрудники получат уведомления")
    else:
        print(f"⚠️  ВНИМАНИЕ: Уведомления получат только {participants.count()} из {all_employees}")

if __name__ == '__main__':
    test_announcement_notifications()
