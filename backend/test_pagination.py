#!/usr/bin/env python
"""
Скрипт для тестирования пагинации в API эндпоинтах.
Запуск: python backend/test_pagination.py
"""

import os
import sys
import django

# Настройка Django
sys.path.insert(0, os.path.dirname(__file__))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from api.client import get_api_client
from django.test import RequestFactory

User = get_user_model()

def test_pagination():
    """Тестирует пагинацию для всех основных эндпоинтов."""
    
    # Создаём fake request для get_api_client
    factory = RequestFactory()
    
    # Берём первого суперпользователя
    admin = User.objects.filter(is_superuser=True).first()
    if not admin:
        print("❌ Нет суперпользователя в БД")
        return
    
    print(f"✅ Используем пользователя: {admin.email}\n")
    
    # Создаём fake HTTP request
    fake_request = factory.get('/')
    fake_request.user = admin
    
    # Получаем API client
    api = get_api_client(fake_request)
    
    endpoints = [
        ('Отделы', 'v1/departments/'),
        ('Сотрудники', 'v1/employees/'),
        ('Документы', 'v1/documents/'),
        ('Заявления', 'v1/requests/'),
        ('Новости', 'v1/posts/'),
    ]
    
    print("=" * 70)
    print("ПРОВЕРКА ПАГИНАЦИИ API")
    print("=" * 70 + "\n")
    
    for name, endpoint in endpoints:
        print(f"📍 {name} ({endpoint})")
        print("-" * 70)
        
        # Запрос без параметров
        resp = api.get(endpoint)
        
        if not resp.ok:
            print(f"   ❌ Ошибка: HTTP {resp.status}")
            print()
            continue
        
        data = resp.json
        
        # Проверяем формат ответа
        if isinstance(data, dict):
            if 'results' in data:
                print(f"   ✅ Пагинация ВКЛЮЧЕНА")
                print(f"   📊 Всего: {data.get('count', '?')}")
                print(f"   📄 На странице: {len(data.get('results', []))}")
                print(f"   ⏭️  Следующая: {'Да' if data.get('next') else 'Нет'}")
                print(f"   ⏮️  Предыдущая: {'Да' if data.get('previous') else 'Нет'}")
            else:
                print(f"   ⚠️  Словарь БЕЗ 'results' (возможно другой формат)")
                print(f"   📄 Ключи: {list(data.keys())[:5]}")
        elif isinstance(data, list):
            print(f"   ❌ Пагинация ОТКЛЮЧЕНА (возвращается список)")
            print(f"   📄 Элементов: {len(data)}")
        else:
            print(f"   ⚠️  Неожиданный тип: {type(data)}")
        
        # Тест с параметром page=2
        print("\n   🔍 Тест page=2:")
        resp2 = api.get(endpoint, params={'page': 2})
        if resp2.ok:
            data2 = resp2.json
            if isinstance(data2, dict) and 'results' in data2:
                print(f"   ✅ Страница 2 работает ({len(data2.get('results', []))} элементов)")
            else:
                print(f"   ⚠️  Страница 2: неожиданный формат")
        else:
            print(f"   ⚠️  Страница 2: HTTP {resp2.status}")
        
        print()
    
    print("=" * 70)
    print("ПРОВЕРКА ЗАВЕРШЕНА")
    print("=" * 70)


if __name__ == '__main__':
    test_pagination()
