#!/usr/bin/env python
"""
Тестовый скрипт для проверки API регистрации.
Отправляет запросы на /api/v1/auth/register/ и показывает ответы.
"""
import json
import sys
import os
import django

# Настройка Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eusrr_backend.settings")
django.setup()

from django.test import Client
from django.urls import reverse


def test_register():
    """Тестируем регистрацию с валидными данными."""
    client = Client()
    url = reverse("api:v1:register")
    
    # Тестовые данные
    payload = {
        "first_name": "Тест",
        "last_name": "Тестов",
        "phone_number": "+79991234567",
        "email": "test@example.com",
        "birth_date": "1990-01-01",
        "password": "password123",
        "telegram": "@test_user",
        "whatsapp": "",
        "wechat": "",
    }
    
    print(f"Отправка запроса на: {url}")
    print(f"Данные: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    print("-" * 60)
    
    response = client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json"
    )
    
    print(f"Статус: {response.status_code}")
    print(f"Content-Type: {response.get('Content-Type')}")
    
    try:
        data = response.json()
        print(f"Ответ: {json.dumps(data, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"Не удалось распарсить JSON: {e}")
        print(f"Тело ответа: {response.content.decode('utf-8')}")
    
    return response


def test_register_missing_contact():
    """Тестируем регистрацию без контактов."""
    client = Client()
    url = reverse("api:v1:register")
    
    payload = {
        "first_name": "Тест",
        "last_name": "Тестов",
        "phone_number": "+79991234567",
        "email": "test2@example.com",
        "birth_date": "1990-01-01",
        "password": "password123",
        "telegram": "",
        "whatsapp": "",
        "wechat": "",
    }
    
    print("\n" + "=" * 60)
    print("Тест без контактов:")
    print(f"Данные: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    print("-" * 60)
    
    response = client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json"
    )
    
    print(f"Статус: {response.status_code}")
    try:
        data = response.json()
        print(f"Ответ: {json.dumps(data, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"Не удалось распарсить JSON: {e}")
    
    return response


def test_register_invalid_phone():
    """Тестируем регистрацию с неправильным телефоном."""
    client = Client()
    url = reverse("api:v1:register")
    
    payload = {
        "first_name": "Тест",
        "last_name": "Тестов",
        "phone_number": "123",  # неправильный формат
        "email": "test3@example.com",
        "birth_date": "1990-01-01",
        "password": "password123",
        "telegram": "@test_user",
        "whatsapp": "",
        "wechat": "",
    }
    
    print("\n" + "=" * 60)
    print("Тест с неправильным телефоном:")
    print(f"Данные: {json.dumps(payload, indent=2, ensure_ascii=False)}")
    print("-" * 60)
    
    response = client.post(
        url,
        data=json.dumps(payload),
        content_type="application/json"
    )
    
    print(f"Статус: {response.status_code}")
    try:
        data = response.json()
        print(f"Ответ: {json.dumps(data, indent=2, ensure_ascii=False)}")
    except Exception as e:
        print(f"Не удалось распарсить JSON: {e}")
    
    return response


if __name__ == "__main__":
    print("=" * 60)
    print("ТЕСТ API РЕГИСТРАЦИИ")
    print("=" * 60)
    
    test_register()
    test_register_missing_contact()
    test_register_invalid_phone()
    
    print("\n" + "=" * 60)
    print("Тесты завершены")
    print("=" * 60)
