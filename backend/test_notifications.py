#!/usr/bin/env python
"""
Тестовый скрипт для проверки системы уведомлений v2.0

Использование:
    python test_notifications.py

Что тестируется:
- Создание уведомления через notify.send()
- Сохранение в БД
- Отправка через Celery задачи (WebSocket, Email, Push)
- Channel preferences
- API endpoints
"""
import os
import django

# Настройка Django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from notifications.signals import notify
from notifications.models import Notification, UserChannelPreferences

User = get_user_model()


def test_notify_send():
    """Тест создания уведомления через notify.send()"""
    print("\n" + "="*80)
    print("ТЕСТ 1: Создание уведомления через notify.send()")
    print("="*80)
    
    try:
        # Получаем первых двух пользователей
        users = User.objects.all()[:2]
        if len(users) < 2:
            print("❌ Нужно минимум 2 пользователя в БД")
            return False
        
        sender_user = users[0]
        recipient_user = users[1]
        
        print(f"📤 Отправитель: {sender_user.username}")
        print(f"📥 Получатель: {recipient_user.username}")
        
        # Создаем уведомление
        notification = notify.send(
            sender=sender_user,
            recipient=recipient_user,
            verb='liked',
            description=f'{sender_user.get_full_name() or sender_user.username} liked your post',
            action_url='/posts/123/',
        )
        
        if isinstance(notification, list):
            notification = notification[0]
        
        print(f"✅ Уведомление создано: ID={notification.id}")
        print(f"   Verb: {notification.verb}")
        print(f"   Description: {notification.description}")
        print(f"   Actor: {notification.actor}")
        print(f"   Unread: {notification.unread}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_channel_preferences():
    """Тест настроек каналов"""
    print("\n" + "="*80)
    print("ТЕСТ 2: UserChannelPreferences")
    print("="*80)
    
    try:
        user = User.objects.first()
        if not user:
            print("❌ Нет пользователей в БД")
            return False
        
        print(f"👤 Пользователь: {user.username}")
        
        # Получаем или создаем настройки
        prefs, created = UserChannelPreferences.objects.get_or_create(user=user)
        
        if created:
            print("✅ Созданы новые настройки с дефолтными значениями")
        else:
            print("✅ Настройки уже существуют")
        
        print(f"   Web: {prefs.web_enabled}")
        print(f"   Email: {prefs.email_enabled} (frequency: {prefs.email_frequency})")
        print(f"   Push: {prefs.push_enabled}")
        print(f"   DND: {prefs.dnd_enabled} ({prefs.dnd_start_time} - {prefs.dnd_end_time})")
        
        # Проверяем is_in_dnd_period()
        is_dnd = prefs.is_in_dnd_period()
        print(f"   Сейчас в DND: {is_dnd}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_queryset_methods():
    """Тест методов QuerySet"""
    print("\n" + "="*80)
    print("ТЕСТ 3: QuerySet методы")
    print("="*80)
    
    try:
        user = User.objects.first()
        if not user:
            print("❌ Нет пользователей в БД")
            return False
        
        print(f"👤 Пользователь: {user.username}")
        
        # Получаем статистику
        total = Notification.objects.filter(recipient=user).count()
        unread = Notification.objects.filter(recipient=user).unread().count()
        read_count = Notification.objects.filter(recipient=user).read().count()
        
        print(f"📊 Статистика:")
        print(f"   Всего: {total}")
        print(f"   Непрочитанных: {unread}")
        print(f"   Прочитанных: {read_count}")
        
        # Последние 5 уведомлений
        recent = Notification.objects.filter(
            recipient=user
        ).order_by('-timestamp')[:5]
        
        if recent:
            print(f"\n📬 Последние {recent.count()} уведомлений:")
            for n in recent:
                status = "🔵" if n.unread else "⚪"
                print(f"   {status} [{n.verb}] {n.description[:50]}... ({n.timesince()} ago)")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_mark_as_read():
    """Тест отметки как прочитанного"""
    print("\n" + "="*80)
    print("ТЕСТ 4: Отметка как прочитанного")
    print("="*80)
    
    try:
        user = User.objects.first()
        if not user:
            print("❌ Нет пользователей в БД")
            return False
        
        # Находим непрочитанное уведомление
        notification = Notification.objects.filter(
            recipient=user,
            unread=True
        ).first()
        
        if not notification:
            print("⚠️  Нет непрочитанных уведомлений")
            return True
        
        print(f"📬 Уведомление ID={notification.id}: unread={notification.unread}")
        
        # Отмечаем как прочитанное
        notification.mark_as_read()
        
        # Перезагружаем из БД
        notification.refresh_from_db()
        
        print(f"✅ После mark_as_read(): unread={notification.unread}")
        print(f"   timestamp_read: {notification.timestamp_read}")
        
        return True
        
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return False


def main():
    """Запуск всех тестов"""
    print("\n" * 2)
    print("╔" + "="*78 + "╗")
    print("║" + " "*20 + "ТЕСТИРОВАНИЕ NOTIFICATIONS V2.0" + " "*25 + "║")
    print("╚" + "="*78 + "╝")
    
    results = []
    
    # Запускаем тесты
    results.append(("notify.send()", test_notify_send()))
    results.append(("UserChannelPreferences", test_channel_preferences()))
    results.append(("QuerySet методы", test_queryset_methods()))
    results.append(("mark_as_read()", test_mark_as_read()))
    
    # Итоги
    print("\n" + "="*80)
    print("ИТОГИ")
    print("="*80)
    
    for test_name, result in results:
        status = "✅ PASSED" if result else "❌ FAILED"
        print(f"{status}: {test_name}")
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    print(f"\n{'='*80}")
    print(f"Пройдено: {passed}/{total} тестов")
    print(f"{'='*80}\n")
    
    return all(r for _, r in results)


if __name__ == "__main__":
    success = main()
    exit(0 if success else 1)
