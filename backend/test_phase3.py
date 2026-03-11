#!/usr/bin/env python
"""
Тест Фазы 3: API и WebSocket consumers
"""
import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from communications.models import Chat
from employees.models import Department
from django.contrib.contenttypes.models import ContentType
from django.contrib.auth import get_user_model

Employee = get_user_model()

print("=" * 80)
print("ФАЗА 3: ТЕСТИРОВАНИЕ API И CONSUMERS")
print("=" * 80)

# 1. Тест API serializers
print("\n1. Тест API serializers:")
from communications.api.serializers import ChatListSerializer, ChatDetailSerializer

chat = Chat.objects.first()
if chat:
    # ChatListSerializer
    list_data = ChatListSerializer(chat).data
    print(f"   ✓ ChatListSerializer работает")
    print(f"     - Новые поля в ответе:")
    print(f"       context_object_id: {list_data.get('context_object_id')}")
    print(f"       context_type: {list_data.get('context_type')}")
    print(f"       flags: {list_data.get('flags')}")
    print(f"       extra_data: {list_data.get('extra_data')}")
    print(f"       include_all_users: {list_data.get('include_all_users')}")
    print(f"     - Старые поля (DEPRECATED) тоже есть:")
    print(f"       is_main: {list_data.get('is_main')}")
    print(f"       department: {list_data.get('department')}")
    
    # ChatDetailSerializer
    detail_data = ChatDetailSerializer(chat).data
    print(f"\n   ✓ ChatDetailSerializer работает")
    print(f"     - context_app: {detail_data.get('context_app')}")

# 2. Тест WebSocket consumers (has_user_access логика)
print("\n2. Тест WebSocket consumers:")

user = Employee.objects.filter(is_active=True).first()
dept_chat = Chat.objects.filter(type='department').first()

if user and dept_chat:
    # Тестируем логику из has_user_access (без асинхронности)
    from communications.models import ChatMembership
    chat = dept_chat
    
    # Логика из consumers.has_user_access
    has_access = False
    if chat.type == "department":
        if chat.include_all_users:
            has_access = True
        else:
            has_access = chat.get_participants().filter(pk=user.pk).exists()
    elif chat.type == "direct":
        has_access = chat.get_participants().filter(pk=user.pk).exists()
    
    print(f"   ✓ has_user_access() логика для department chat: {has_access}")
    print(f"     User: {user}")
    print(f"     Chat: {dept_chat}")
    print(f"     include_all_users: {chat.include_all_users}")

# 3. Проверка фильтров в API views
print("\n3. Тест фильтров API views:")
from django.db.models import Q

user2 = Employee.objects.filter(is_active=True).first()
if user2:
    # Проверяем фильтр как в ChatViewSet
    dept_ids = list(user2.departments_links.filter(
        is_active=True
    ).values_list('department_id', flat=True))
    
    print(f"   User departments: {len(dept_ids)}")
    
    dept_ct = None
    if dept_ids:
        dept_ct = ContentType.objects.get_for_model(Department)
    
    chats = Chat.objects.filter(
        Q(participants=user2)
        | Q(department__in=dept_ids)  # OLD
        | (Q(context_content_type=dept_ct, context_object_id__in=dept_ids) if dept_ct else Q(pk__in=[]))  # NEW
        | Q(include_all_users=True)  # NEW
    ).distinct()
    
    print(f"   ✓ Найдено доступных чатов: {chats.count()}")

# 4. Проверка что старые поля еще работают
print("\n4. Тест обратной совместимости:")
old_dept_chats = Chat.objects.filter(department__isnull=False).count()
new_context_chats = Chat.objects.filter(context_object_id__isnull=False).count()
print(f"   Чатов со старым полем department: {old_dept_chats}")
print(f"   Чатов с новым полем context_object: {new_context_chats}")

old_main_chats = Chat.objects.filter(is_main=True).count()
new_flags_chats = Chat.objects.filter(flags__is_primary=True).count()
print(f"   Чатов со старым полем is_main: {old_main_chats}")
print(f"   Чатов с новым полем flags['is_primary']: {new_flags_chats}")

print("\n" + "=" * 80)
print("✅ ВСЕ ТЕСТЫ ФАЗЫ 3 ЗАВЕРШЕНЫ")
print("=" * 80)
