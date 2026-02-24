"""
Тестовый скрипт для проверки оптимизации уведомлений о сообщениях.

Запуск:
    cd backend
    ../.venv/Scripts/python test_message_optimization.py
"""

import os
import django
import time

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from communications.models import Chat, Message
from django.contrib.auth import get_user_model

User = get_user_model()


def test_message_creation_speed():
    """Тест скорости создания сообщения."""
    
    print("=" * 60)
    print("ТЕСТ: Скорость создания сообщения в групповом чате")
    print("=" * 60)
    
    # Находим групповой чат с участниками
    chat = Chat.objects.filter(type='group').first()
    
    if not chat:
        print("❌ Групповой чат не найден")
        return
    
    participants_count = chat.participants.count()
    print(f"📊 Чат: {chat.name or chat.id}")
    print(f"📊 Участников: {participants_count}")
    
    # Находим автора (первого участника)
    author = chat.participants.first()
    
    if not author:
        print("❌ Участники не найдены")
        return
    
    print(f"📊 Автор: {author.get_full_name()}")
    print()
    
    # Создаем тестовое сообщение и замеряем время
    start_time = time.time()
    
    message = Message.objects.create(
        chat=chat,
        author=author,
        content=f"Тестовое сообщение для проверки оптимизации (время: {time.time()})"
    )
    
    end_time = time.time()
    elapsed_ms = (end_time - start_time) * 1000
    
    print(f"✅ Сообщение создано: ID={message.id}")
    print(f"⏱️  Время создания: {elapsed_ms:.2f}ms")
    print()
    
    # Оценка результата
    if elapsed_ms < 50:
        print("🎉 ОТЛИЧНО! Время < 50ms - оптимизация работает!")
    elif elapsed_ms < 100:
        print("✅ ХОРОШО! Время < 100ms - приемлемо")
    elif elapsed_ms < 200:
        print("⚠️  СРЕДНЕ: Время < 200ms - можно улучшить")
    else:
        print(f"❌ МЕДЛЕННО: {elapsed_ms:.2f}ms - проверьте Celery worker")
    
    print()
    print("Рекомендации:")
    print("  1. Убедитесь что Celery worker запущен")
    print("  2. Проверьте логи worker'а: sudo tail -f /var/log/celery/worker.log")
    print("  3. На продакшене время должно быть < 50ms")
    print()


if __name__ == '__main__':
    test_message_creation_speed()
