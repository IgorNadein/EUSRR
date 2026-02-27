#!/usr/bin/env python
"""Создание тестовых календарей и событий для проверки UI"""

from schedule.models import Calendar, Event
from employees.models import Employee
from datetime import datetime, timedelta
import pytz

# Часовой пояс
tz = pytz.timezone('Europe/Moscow')

# Получаем первого пользователя
try:
    user = Employee.objects.first()
    if not user:
        print("❌ Нет пользователей в системе")
        exit(1)
except Exception as e:
    print(f"❌ Ошибка получения пользователя: {e}")
    exit(1)

print(f"✅ Используем пользователя: {user.username}")

# Создаём календари
calendars_data = [
    {"name": "Рабочий календарь", "slug": "work"},
    {"name": "Личные дела", "slug": "personal"},
    {"name": "Встречи", "slug": "meetings"},
]

calendars = []
for data in calendars_data:
    cal, created = Calendar.objects.get_or_create(
        slug=data["slug"],
        defaults={"name": data["name"]}
    )
    calendars.append(cal)
    status = "создан" if created else "уже существует"
    print(f"📅 Календарь '{cal.name}' ({data['slug']}): {status}")

# Создаём тестовые события
now = datetime.now(tz)
today = now.replace(hour=0, minute=0, second=0, microsecond=0)

events_data = [
    # Рабочий календарь
    {
        "calendar": calendars[0],
        "title": "Планёрка",
        "description": "Еженедельное совещание команды",
        "start": today.replace(hour=10, minute=0),
        "end": today.replace(hour=11, minute=0),
        "color_event": "#3b82f6",
    },
    {
        "calendar": calendars[0],
        "title": "Дедлайн проекта",
        "description": "Завершение первого этапа",
        "start": today + timedelta(days=3, hours=18),
        "end": today + timedelta(days=3, hours=19),
        "color_event": "#ef4444",
    },
    {
        "calendar": calendars[0],
        "title": "Код-ревью",
        "description": "Проверка pull requests",
        "start": today + timedelta(days=1, hours=15),
        "end": today + timedelta(days=1, hours=16),
        "color_event": "#8b5cf6",
    },
    
    # Личные дела
    {
        "calendar": calendars[1],
        "title": "Тренировка в зале",
        "description": "",
        "start": today.replace(hour=19, minute=0),
        "end": today.replace(hour=20, minute=30),
        "color_event": "#10b981",
    },
    {
        "calendar": calendars[1],
        "title": "День рождения друга",
        "description": "Купить подарок",
        "start": today + timedelta(days=5, hours=18),
        "end": today + timedelta(days=5, hours=23),
        "color_event": "#f59e0b",
    },
    
    # Встречи
    {
        "calendar": calendars[2],
        "title": "Встреча с клиентом",
        "description": "Обсуждение нового проекта",
        "start": today + timedelta(days=2, hours=14),
        "end": today + timedelta(days=2, hours=15, minutes=30),
        "color_event": "#06b6d4",
    },
    {
        "calendar": calendars[2],
        "title": "Собеседование кандидата",
        "description": "Senior Python Developer",
        "start": today + timedelta(days=4, hours=11),
        "end": today + timedelta(days=4, hours=12),
        "color_event": "#ec4899",
    },
]

created_count = 0
for event_data in events_data:
    event, created = Event.objects.get_or_create(
        calendar=event_data["calendar"],
        title=event_data["title"],
        start=event_data["start"],
        defaults={
            "description": event_data["description"],
            "end": event_data["end"],
            "color_event": event_data["color_event"],
            "creator": user,
        }
    )
    if created:
        created_count += 1
        print(f"✅ Создано событие: {event.title} ({event_data['calendar'].name})")

print(f"\n🎉 Готово! Создано {created_count} новых событий")
print(f"📊 Всего календарей: {Calendar.objects.count()}")
print(f"📊 Всего событий: {Event.objects.count()}")
