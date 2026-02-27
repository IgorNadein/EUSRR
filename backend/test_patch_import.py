#!/usr/bin/env python
"""Проверка импорта и применения патча."""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eusrr_backend.settings")

print("\n" + "=" * 80)
print("1. ЗАПУСК DJANGO")
print("=" * 80)
django.setup()

print("\n" + "=" * 80)
print("2. ИМПОРТ Event БЕЗ ПАТЧА")
print("=" * 80)
from schedule.models import Event
print(f"Event._event_params: {Event._event_params}")
print(f"Имя метода: {Event._event_params.__name__}")

print("\n" + "=" * 80)
print("3. ИМПОРТ ПАТЧА")
print("=" * 80)
import schedule_patch  # noqa

print("\n" + "=" * 80)
print("4. ПРОВЕРКА Event ПОСЛЕ ПАТЧА")
print("=" * 80)
print(f"Event._event_params: {Event._event_params}")
print(f"Имя метода: {Event._event_params.__name__}")

# Проверим на реальном событии
print("\n" + "=" * 80)
print("5. ТЕСТ НА РЕАЛЬНОМ СОБЫТИИ")
print("=" * 80)
event = Event.objects.filter(title__icontains='ыфвыфыф').first()
if event:
    print(f"Event ID: {event.id}")
    result = event._event_params()
    print(f"_event_params() result: {result}")
    if 'byweekday' in result:
        print(f"byweekday = {result['byweekday']}")
        if len(result['byweekday']) > 1:
            print("✅ ПАТЧ РАБОТАЕТ - несколько дней сохранены!")
        else:
            print("❌ ПАТЧ НЕ РАБОТАЕТ - только один день!")
else:
    print("Событие не найдено")
