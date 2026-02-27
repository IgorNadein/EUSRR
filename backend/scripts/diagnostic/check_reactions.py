#!/usr/bin/env python
"""Простая проверка API доступных реакций"""

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
print("ГОТОВО!")
print("=" * 60)
