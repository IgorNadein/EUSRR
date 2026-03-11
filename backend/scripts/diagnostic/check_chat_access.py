#!/usr/bin/env python
"""
Скрипт для проверки доступа к чатам
"""
import os
import sys
import django

# Настройка Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from communications.models import Chat, ChatMembership
from django.db.models import Q

User = get_user_model()

def check_chat_access():
    print("=" * 60)
    print("ПРОВЕРКА ДОСТУПА К ЧАТАМ")
    print("=" * 60)
    
    # Получаем текущего пользователя (первого активного)
    users = User.objects.filter(is_active=True)
    if not users.exists():
        print("❌ Нет активных пользователей!")
        return
    
    print(f"\n📋 Всего активных пользователей: {users.count()}")
    for user in users[:5]:
        print(f"  - {user.username} (ID: {user.id})")
    
    # Проверяем чаты
    print(f"\n📨 Всего чатов в системе: {Chat.objects.count()}")
    
    for chat in Chat.objects.all()[:10]:
        print(f"\n{'='*60}")
        print(f"📌 Чат ID: {chat.id}")
        print(f"   Тип: {chat.type}")
        print(f"   Название: {chat.name or '(без названия)'}")
        print(f"   Создан: {chat.created_at}")
        
        if chat.type == "private":
            participants = chat.participants.all()
            print(f"   Участники (через participants): {[u.username for u in participants]}")
        
        if chat.type == "group" or chat.type == "channel":
            # Для групповых чатов и каналов показываем участников
            participants = chat.participants.all()
            if participants.exists():
                print(f"   Участники: {[u.username for u in participants[:5]]}")
            
            # Для каналов может быть привязан объект через GenericFK
            if chat.context_object:
                print(f"   Привязан к: {chat.context_object} (тип: {chat.context_content_type})")
        
        # Проверяем membership
        memberships = ChatMembership.objects.filter(chat=chat)
        if memberships.exists():
            print(f"   Участники (через ChatMembership): {[m.user.username for m in memberships]}")
        
        # Проверяем доступ для каждого пользователя
        print(f"\n   Доступ пользователей к этому чату:")
        for user in users[:3]:
            membership_chat_ids = ChatMembership.objects.filter(
                user=user
            ).values_list('chat_id', flat=True)
            
            has_access = Chat.objects.filter(
                Q(type="global")
                | Q(type="private", participants=user)
                | Q(type="group", participants=user)
                | Q(type="channel", participants=user)
                | Q(id__in=membership_chat_ids)
            ).filter(id=chat.id).exists()
            
            status = "✅" if has_access else "❌"
            print(f"   {status} {user.username}: {'Доступ есть' if has_access else 'Доступа нет'}")
            
            if not has_access:
                # Детальная проверка
                is_global = chat.type == "global"
                is_private = chat.type == "private" and chat.participants.filter(id=user.id).exists()
                is_group = chat.type == "group" and chat.participants.filter(id=user.id).exists()
                is_channel = chat.type == "channel" and chat.participants.filter(id=user.id).exists()
                is_member = chat.id in membership_chat_ids
                
                print(f"      - Глобальный: {is_global}")
                print(f"      - Личный участник: {is_private}")
                print(f"      - Группа: {is_group}")
                print(f"      - Канал: {is_channel}")
                print(f"      - Через membership: {is_member}")

if __name__ == "__main__":
    check_chat_access()
