#!/usr/bin/env python
"""
Скрипт для демонстрации N+1 проблемы в текущей реализации
"""
import os
import sys
import django
from pathlib import Path

# Setup Django
sys.path.insert(0, str(Path(__file__).parent.parent))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from django.db import connection, reset_queries
from django.db.models import Count, OuterRef, Subquery, Q
from django.db.models.functions import Coalesce
from communications.models import Chat, ChatReadState, ChatUserSettings, Message
from django.conf import settings

# Включаем отслеживание SQL
settings.DEBUG = True

Employee = get_user_model()

def test_current_implementation():
    """Текущая реализация с подзапросами"""
    
    user = Employee.objects.first()
    if not user:
        print("Нет пользователей в базе")
        return
    
    print(f"Тестируем для пользователя: {user}")
    print("=" * 80)
    
    # Сбрасываем счетчик запросов
    reset_queries()
    
    # Текущая реализация из ChatViewSet.get_queryset()
    read_state_subq = ChatReadState.objects.filter(
        chat=OuterRef('pk'),
        user=user
    ).values('last_read_message_id')[:1]

    unread_count_subq = Message.objects.filter(
        chat=OuterRef('pk'),
        id__gt=Coalesce(Subquery(read_state_subq), 0),
        is_deleted=False
    ).exclude(author=user).values('chat').annotate(
        count=Count('id')
    ).values('count')

    chats = Chat.objects.filter(
        Q(participants=user) |
        Q(department__in=user.departments_links.filter(
            is_active=True
        ).values('department')) |
        Q(include_all_employees=True)
    ).annotate(
        unread_count=unread_count_subq
    ).distinct()[:10]  # Берем первые 10 чатов
    
    # Принудительно выполняем запрос
    chat_list = list(chats)
    
    print(f"\nЗагружено чатов: {len(chat_list)}")
    print(f"Количество SQL запросов: {len(connection.queries)}")
    print("\n" + "=" * 80)
    
    # Показываем первые 3 запроса
    for i, query in enumerate(connection.queries[:3], 1):
        print(f"\nЗапрос #{i}:")
        print(query['sql'][:500])
        if len(query['sql']) > 500:
            print("... (обрезано)")
        print(f"Время: {query['time']}s")
    
    if len(connection.queries) > 3:
        print(f"\n... еще {len(connection.queries) - 3} запросов")
    
    print("\n" + "=" * 80)
    print("\nПРОБЛЕМА:")
    print("Несмотря на то, что это ОДИН SQL запрос, внутри него есть")
    print("ПОДЗАПРОСЫ (subqueries) для каждого чата в SELECT clause.")
    print("PostgreSQL выполняет их для КАЖДОЙ строки результата.")
    print("\nЭто не классический N+1, но похожая проблема производительности.")
    
    return chat_list

if __name__ == '__main__':
    test_current_implementation()
