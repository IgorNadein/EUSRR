#!/usr/bin/env python
"""Тестирование API доступных реакций"""

import os
import sys
import django

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from communications.models import AvailableReaction

print("=" * 60)
print("ДОСТУПНЫЕ РЕАКЦИИ В БД")
print("=" * 60)

reactions = AvailableReaction.objects.filter(is_active=True).order_by('order')

if reactions.exists():
    print(f"\nВсего активных реакций: {reactions.count()}\n")
    for r in reactions:
        status = "✓" if r.is_active else "✗"
        print(f"{status} {r.emoji:3s} | {r.name:15s} | order: {r.order}")
else:
    print("\n⚠️  В БД нет активных реакций!")
    print("Запустите: python manage.py init_reactions")

print("\n" + "=" * 60)

# Проверяем API
print("\nПроверка API endpoint...")
from django.test import Client
from django.contrib.auth import get_user_model

User = get_user_model()
client = Client()

# Создаём тестового пользователя если нет
user, created = User.objects.get_or_create(
    username='test_user',
    defaults={
        'first_name': 'Test',
        'last_name': 'User',
        'email': 'test@example.com'
    }
)

if created:
    user.set_password('password')
    user.save()
    print(f"✓ Создан тестовый пользователь: {user.username}")

# Логинимся
client.force_login(user)

# Делаем запрос
response = client.get('/api/v1/communications/reactions/available/')

print(f"\nОтвет API: HTTP {response.status_code}")
if response.status_code == 200:
    import json
    data = json.loads(response.content)
    print(f"✓ ok: {data.get('ok')}")
    print(f"✓ reactions: {len(data.get('reactions', []))} шт.")
    print("\nСодержимое:")
    for r in data.get('reactions', []):
        print(f"  {r['emoji']} - {r['name']} (order: {r['order']})")
else:
    print(f"✗ Ошибка: {response.content}")

print("\n" + "=" * 60)
print("ГОТОВО!")
print("=" * 60)
