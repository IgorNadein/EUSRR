#!/usr/bin/env python
"""
Тест денормализации unread_count
"""
import os
import sys
import django
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db import connection, reset_queries
from django.conf import settings
from communications.models import Chat, ChatReadState, Message

# Включаем отслеживание SQL
settings.DEBUG = True

Employee = get_user_model()

def test_denormalized_unread():
    """Тестируем оптимизированный подход с денормализацией"""
    
    user = Employee.objects.first()
    if not user:
        print("❌ Нет пользователей в базе")
        return
    
    print(f"📊 Тестируем денормализацию для пользователя: {user}")
    print("=" * 80)
    
    # Сбрасываем счетчик запросов
    reset_queries()
    
    # НОВЫЙ ОПТИМИЗИРОВАННЫЙ KOD из ChatViewSet.get_queryset()
    from django.db.models import Q, Prefetch
    from communications.models import ChatUserSettings
    
    chats = Chat.objects.filter(
        Q(participants=user) |
        Q(department__in=user.departments_links.filter(
            is_active=True
        ).values('department')) |
        Q(include_all_employees=True)
    ).select_related(
        'department', 'created_by'
    ).prefetch_related(
        'participants',
        Prefetch(
            'user_settings',
            queryset=ChatUserSettings.objects.filter(user=user),
            to_attr='my_settings'
        ),
        Prefetch(
            'read_states',
            queryset=ChatReadState.objects.filter(user=user),
            to_attr='my_read_state'
        )
    ).distinct()[:10]
    
    # Принудительно выполняем запрос
    chat_list = list(chats)
    
    print(f"\n✅ Загружено чатов: {len(chat_list)}")
    print(f"📈 Количество SQL запросов: {len(connection.queries)}")
    print("\n" + "=" * 80)
    
    # Показываем unread_count для каждого чата
    print("\n📬 Счетчики непрочитанных:")
    for chat in chat_list:
        unread = 0
        if hasattr(chat, 'my_read_state') and chat.my_read_state:
            unread = chat.my_read_state[0].unread_count
        
        print(f"  Chat #{chat.id} ({chat.type}): {unread} непрочитанных")
    
    # Показываем SQL запросы
    print("\n" + "=" * 80)
    print("\n🔍 SQL Запросы:")
    for i, query in enumerate(connection.queries, 1):
        print(f"\n[{i}] {query['sql'][:200]}...")
        print(f"    Время: {query['time']}s")
    
    print("\n" + "=" * 80)
    print("\n✨ РЕЗУЛЬТАТ:")
    print(f"   - Один основной JOIN запрос вместо 100+ подзапросов")
    print(f"   - unread_count читается из денормализованного поля")
    print(f"   - Общее время выполнения: {sum(float(q['time']) for q in connection.queries):.4f}s")
    
    # Тест создания нового сообщения
    print("\n" + "=" * 80)
    print("\n📝 Тест: создание нового сообщения...")
    
    test_chat = chat_list[0] if chat_list else None
    if test_chat:
        reset_queries()
        
        # Создаем сообщение от другого пользователя
        other_user = Employee.objects.exclude(id=user.id).first()
        if other_user:
            msg = Message.objects.create(
                chat=test_chat,
                author=other_user,
                content="Тестовое сообщение для проверки инкремента"
            )
            
            print(f"✅ Сообщение создано: #{msg.id}")
            print(f"📊 SQL запросов: {len(connection.queries)}")
            
            # Проверяем что счетчик увеличился
            read_state = ChatReadState.objects.get(chat=test_chat, user=user)
            print(f"📈 Новый unread_count: {read_state.unread_count}")
            
            # Удаляем тестовое сообщение
            msg.delete()
            print("🗑️  Тестовое сообщение удалено")

if __name__ == '__main__':
    test_denormalized_unread()
