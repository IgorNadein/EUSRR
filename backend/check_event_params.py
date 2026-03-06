#!/usr/bin/env python
"""Проверка параметров события в базе данных."""
import os
import sys
import django

# Setup Django
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "eusrr_backend.settings")
django.setup()

# ЯВНЫЙ импорт патча
import schedule_patch  # noqa

from schedule.models import Event, Rule

# Найдём событие по названию
event = Event.objects.filter(title__icontains='ыфвыфыф').first()

if event:
    print(f"=" * 80)
    print(f"Event ID: {event.id}")
    print(f"Title: {event.title}")
    print(f"Start: {event.start} (weekday: {event.start.weekday()})")
    print(f"End recurring: {event.end_recurring_period}")
    print(f"=" * 80)
    
    if event.rule:
        print(f"\nRule ID: {event.rule.id}")
        print(f"Frequency: {event.rule.frequency}")
        print(f"Params: {event.rule.params}")
        print(f"=" * 80)
        
        # Проверим occurrences
        from datetime import datetime
        from django.utils import timezone
        start = timezone.make_aware(datetime(2026, 2, 1, 0, 0, 0))
        end = timezone.make_aware(datetime(2026, 2, 28, 23, 59, 59))
        occurrences = event.get_occurrences(start, end)
        
        print(f"\nOccurrences в феврале 2026:")
        for occ in occurrences:
            print(f"  - {occ.start.strftime('%Y-%m-%d %A')} {occ.start.strftime('%H:%M')}")
        print(f"=" * 80)
    else:
        print("НЕТ ПРАВИЛА!")
else:
    print("Событие не найдено!")
