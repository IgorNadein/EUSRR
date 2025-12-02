#!/usr/bin/env python
"""
Простое создание тестовых пользователей
"""
import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from django.contrib.auth import get_user_model

User = get_user_model()

# Создаем 5 тестовых пользователей
test_users_data = [
    ('test1@local.dev', 'Тестовый', 'Первый', '+79001111111'),
    ('test2@local.dev', 'Тестовый', 'Второй', '+79002222222'),
    ('test3@local.dev', 'Тестовый', 'Третий', '+79003333333'),
    ('test4@local.dev', 'Тестовый', 'Четвертый', '+79004444444'),
    ('test5@local.dev', 'Тестовый', 'Пятый', '+79005555555'),
]

created = 0
for email, first_name, last_name, phone in test_users_data:
    if not User.objects.filter(email=email).exists():
        user = User.objects.create(
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone_number=phone,
            is_active=True,
            email_verified=True
        )
        user.set_password('test123')
        user.save()
        print(f"✓ Создан: {user.get_full_name()} ({email})")
        created += 1
    else:
        print(f"⚠ Уже существует: {email}")

print(f"\nСоздано новых пользователей: {created}")
print(f"Всего активных: {User.objects.filter(is_active=True).count()}")
