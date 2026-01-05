#!/usr/bin/env python
"""
Тестовый скрипт для проверки работы notification signals.

Тестирует все 5 модулей:
1. Communications - сообщения, упоминания, ответы
2. Requests - заявки, статусы, комментарии
3. Documents - документы, ознакомления
4. Calendar - события, изменения
5. Feed - публикации, комментарии

Запуск:
    python test_notification_signals.py
"""

import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eusrr_backend.settings')
django.setup()

from django.contrib.auth import get_user_model
from communications.models import Chat, Message
from requests_app.models import Request, RequestComment
from documents.models import Document, DocumentAcknowledgement
from calendar_app.models import CalendarEvent
from feed.models import Post, Comment
from notifications.models import Notification
from employees.models import Department

Employee = get_user_model()

# ANSI цвета для красивого вывода
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'


def print_header(text):
    print(f"\n{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{text:^60}{Colors.ENDC}")
    print(f"{Colors.HEADER}{Colors.BOLD}{'='*60}{Colors.ENDC}\n")


def print_success(text):
    print(f"{Colors.OKGREEN}[OK] {text}{Colors.ENDC}")


def print_error(text):
    print(f"{Colors.FAIL}[ERROR] {text}{Colors.ENDC}")


def print_info(text):
    print(f"{Colors.OKCYAN}[INFO] {text}{Colors.ENDC}")


def get_or_create_test_users():
    """Создает или получает тестовых пользователей."""
    print_info("Подготовка тестовых пользователей...")
    
    user1, created = Employee.objects.get_or_create(
        email='test_user1@test.com',
        defaults={
            'first_name': 'Иван',
            'last_name': 'Иванов',
            'is_active': True,
            'phone_number': '+79001111111'
        }
    )
    if created:
        user1.set_password('testpass123')
        user1.save()
    
    user2, created = Employee.objects.get_or_create(
        email='test_user2@test.com',
        defaults={
            'first_name': 'Петр',
            'last_name': 'Петров',
            'is_active': True,
            'phone_number': '+79002222222'
        }
    )
    if created:
        user2.set_password('testpass123')
        user2.save()
    
    print_success(f"Пользователи готовы: {user1.email}, {user2.email}")
    return user1, user2


def test_communications(user1, user2):
    """Тестирует signals модуля Communications."""
    print_header("ТЕСТ 1: Communications")
    
    # Очистка предыдущих уведомлений
    Notification.objects.filter(recipient__in=[user1, user2]).delete()
    
    # 1. Создаем приватный чат
    chat = Chat.objects.create(type='private')
    chat.participants.add(user1, user2)
    print_success(f"Создан чат #{chat.id}")
    
    # Проверяем уведомление о добавлении в чат
    notif_count = Notification.objects.filter(
        notification_type__code='chat_added_to_chat'
    ).count()
    print_info(f"Уведомлений о добавлении в чат: {notif_count}")
    
    # 2. Простое сообщение
    msg1 = Message.objects.create(
        chat=chat,
        author=user1,
        content='Привет! Как дела?'
    )
    print_success(f"Создано сообщение #{msg1.id}")
    
    notif = Notification.objects.filter(
        recipient=user2,
        notification_type__code='chat_new_message'
    ).first()
    if notif:
        print_success(f"[+] Уведомление получено: {notif.title}")
    else:
        print_error("Уведомление о новом сообщении НЕ создано!")
    
    # 3. Сообщение с упоминанием
    msg2 = Message.objects.create(
        chat=chat,
        author=user1,
        content=f'Привет @{user2.email}, нужна твоя помощь!'
    )
    print_success(f"Создано сообщение с упоминанием #{msg2.id}")
    
    mention_notif = Notification.objects.filter(
        recipient=user2,
        notification_type__code='chat_mention'
    ).first()
    if mention_notif:
        print_success(f"[+] Уведомление об упоминании: {mention_notif.title}")
    else:
        print_error("Уведомление об упоминании НЕ создано!")
    
    # 4. Ответ на сообщение
    msg3 = Message.objects.create(
        chat=chat,
        author=user2,
        content='Конечно, помогу!',
        reply_to=msg1
    )
    print_success(f"Создан ответ на сообщение #{msg3.id}")
    
    reply_notif = Notification.objects.filter(
        recipient=user1,
        notification_type__code='chat_reply'
    ).first()
    if reply_notif:
        print_success(f"[+] Уведомление об ответе: {reply_notif.title}")
    else:
        print_error("Уведомление об ответе НЕ создано!")
    
    total = Notification.objects.filter(recipient__in=[user1, user2]).count()
    print_info(f"Всего создано уведомлений: {total}")


def test_requests(user1, user2):
    """Тестирует signals модуля Requests."""
    print_header("ТЕСТ 2: Requests")
    
    Notification.objects.filter(recipient__in=[user1, user2]).delete()
    
    # 1. Создаем заявку
    request = Request.objects.create(
        employee=user1,
        type='vacation',
        title='Отпуск',
        comment='Прошу предоставить отпуск',
        status='pending',
        approver=user2
    )
    print_success(f"Создана заявка #{request.id}")
    
    new_request_notif = Notification.objects.filter(
        notification_type__code='request_new'
    ).first()
    if new_request_notif:
        print_success(f"✓ Уведомление о новой заявке: {new_request_notif.title}")
    else:
        print_error("Уведомление о новой заявке НЕ создано!")
    
    # 2. Одобряем заявку
    from django.utils import timezone
    request.status = 'approved'
    request.decided_at = timezone.now()
    request.save()
    print_success(f"Заявка #{request.id} одобрена")
    
    approved_notif = Notification.objects.filter(
        recipient=user1,
        notification_type__code='request_approved'
    ).first()
    if approved_notif:
        print_success(f"✓ Уведомление об одобрении: {approved_notif.title}")
    else:
        print_error("Уведомление об одобрении НЕ создано!")
    
    # 3. Добавляем комментарий
    comment = RequestComment.objects.create(
        request=request,
        author=user2,
        text='Одобрено, хорошего отдыха!'
    )
    print_success(f"Добавлен комментарий #{comment.id}")
    
    comment_notif = Notification.objects.filter(
        recipient=user1,
        notification_type__code='request_comment'
    ).first()
    if comment_notif:
        print_success(f"✓ Уведомление о комментарии: {comment_notif.title}")
    else:
        print_error("Уведомление о комментарии НЕ создано!")
    
    total = Notification.objects.filter(recipient__in=[user1, user2]).count()
    print_info(f"Всего создано уведомлений: {total}")


def test_documents(user1, user2):
    """Тестирует signals модуля Documents."""
    print_header("ТЕСТ 3: Documents")
    
    Notification.objects.filter(recipient__in=[user1, user2]).delete()
    
    # 1. Создаем документ для конкретных получателей
    doc = Document.objects.create(
        title='Важный документ',
        description='Требует ознакомления',
        uploaded_by=user1
    )
    doc.recipients.add(user2)
    print_success(f"Создан документ #{doc.id}")
    
    doc_notif = Notification.objects.filter(
        recipient=user2,
        notification_type__code='document_ready'
    ).first()
    if doc_notif:
        print_success(f"✓ Уведомление о документе: {doc_notif.title}")
    else:
        print_error("Уведомление о документе НЕ создано!")
    
    # 2. Ознакомление с документом
    ack = DocumentAcknowledgement.objects.create(
        document=doc,
        user=user2
    )
    print_success(f"Пользователь {user2.username} ознакомился")
    
    # Проверяем уведомление о полном ознакомлении
    all_ack_notif = Notification.objects.filter(
        recipient=user1,
        notification_type__code='document_signed_all'
    ).first()
    if all_ack_notif:
        print_success(f"✓ Уведомление о полном ознакомлении: {all_ack_notif.title}")
    else:
        print_error("Уведомление о полном ознакомлении НЕ создано!")
    
    total = Notification.objects.filter(recipient__in=[user1, user2]).count()
    print_info(f"Всего создано уведомлений: {total}")


def test_calendar(user1, user2):
    """Тестирует signals модуля Calendar."""
    print_header("ТЕСТ 4: Calendar")
    
    Notification.objects.filter(recipient__in=[user1, user2]).delete()
    
    from datetime import date, timedelta
    
    # 1. Создаем событие компании
    event = CalendarEvent.objects.create(
        title='Общее собрание',
        description='Ежеквартальное собрание',
        start_date=date.today() + timedelta(days=7),
        created_by=user1
    )
    print_success(f"Создано событие #{event.id}")
    
    event_notif = Notification.objects.filter(
        notification_type__code='event_created'
    ).first()
    if event_notif:
        print_success(f"✓ Уведомление о событии: {event_notif.title}")
        print_info(f"  Получателей: {Notification.objects.filter(notification_type__code='event_created').count()}")
    else:
        print_error("Уведомление о событии НЕ создано!")
    
    # 2. Изменяем событие
    Notification.objects.all().delete()  # Очищаем для чистоты теста
    event.title = 'ВАЖНОЕ Общее собрание'
    event.save()
    print_success(f"Событие #{event.id} изменено")
    
    changed_notif = Notification.objects.filter(
        notification_type__code='event_changed'
    ).first()
    if changed_notif:
        print_success(f"✓ Уведомление об изменении: {changed_notif.title}")
    else:
        print_error("Уведомление об изменении НЕ создано!")
    
    # 3. Удаляем событие
    Notification.objects.all().delete()
    event.delete()
    print_success("Событие удалено")
    
    cancelled_notif = Notification.objects.filter(
        notification_type__code='event_cancelled'
    ).first()
    if cancelled_notif:
        print_success(f"✓ Уведомление об отмене: {cancelled_notif.title}")
    else:
        print_error("Уведомление об отмене НЕ создано!")


def test_feed(user1, user2):
    """Тестирует signals модуля Feed."""
    print_header("ТЕСТ 5: Feed")
    
    Notification.objects.filter(recipient__in=[user1, user2]).delete()
    
    # 1. Создаем публикацию компании
    post = Post.objects.create(
        author=user1,
        title='Важная новость',
        body='Текст важной новости для всех сотрудников',
        type='company'
    )
    print_success(f"Создана публикация #{post.id}")
    
    post_notif = Notification.objects.filter(
        notification_type__code='feed_new_post'
    ).first()
    if post_notif:
        print_success(f"✓ Уведомление о публикации: {post_notif.title}")
        print_info(f"  Получателей: {Notification.objects.filter(notification_type__code='feed_new_post').count()}")
    else:
        print_error("Уведомление о публикации НЕ создано!")
    
    # 2. Добавляем комментарий
    comment = Comment.objects.create(
        post=post,
        author=user2,
        text='Отличная новость!'
    )
    print_success(f"Добавлен комментарий #{comment.id}")
    
    comment_notif = Notification.objects.filter(
        recipient=user1,
        notification_type__code='feed_post_comment'
    ).first()
    if comment_notif:
        print_success(f"✓ Уведомление о комментарии: {comment_notif.title}")
    else:
        print_error("Уведомление о комментарии НЕ создано!")
    
    # 3. Тестируем функцию реакции
    from feed.notification_signals import notify_post_reaction
    notify_post_reaction(post, user2)
    print_success("Вызвана функция реакции")
    
    reaction_notif = Notification.objects.filter(
        recipient=user1,
        notification_type__code='feed_post_reaction'
    ).first()
    if reaction_notif:
        print_success(f"✓ Уведомление о реакции: {reaction_notif.title}")
    else:
        print_error("Уведомление о реакции НЕ создано!")


def main():
    """Основная функция запуска всех тестов."""
    print(f"{Colors.BOLD}{Colors.OKBLUE}")
    print("="*60)
    print("     ТЕСТИРОВАНИЕ СИСТЕМЫ УВЕДОМЛЕНИЙ - ЭТАП 3")
    print("     Интеграция с модулями через signals")
    print("="*60)
    print(f"{Colors.ENDC}")
    
    try:
        # Подготовка
        user1, user2 = get_or_create_test_users()
        
        # Запуск тестов
        test_communications(user1, user2)
        test_requests(user1, user2)
        test_documents(user1, user2)
        test_calendar(user1, user2)
        test_feed(user1, user2)
        
        # Итоговая статистика
        print_header("ИТОГИ")
        total_notifications = Notification.objects.count()
        total_types_used = Notification.objects.values(
            'notification_type__code'
        ).distinct().count()
        
        print_success(f"Всего уведомлений в БД: {total_notifications}")
        print_success(f"Использовано типов: {total_types_used}")
        
        print(f"\n{Colors.OKGREEN}{Colors.BOLD}✓ ВСЕ ТЕСТЫ ЗАВЕРШЕНЫ!{Colors.ENDC}\n")
        
    except Exception as e:
        print_error(f"ОШИБКА: {e}")
        import traceback
        traceback.print_exc()


if __name__ == '__main__':
    main()
