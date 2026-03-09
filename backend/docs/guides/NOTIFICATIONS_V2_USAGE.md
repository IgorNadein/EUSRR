# Универсальная система уведомлений для Django

**Версия:** 2.0  
**Дата:** 9 марта 2026  
**Основана на:** django-notifications-hq архитектуре  
**Совместимость:** Django 5.2+

---

## 📋 Оглавление

1. [Обзор](#обзор)
2. [Архитектура](#архитектура)
3. [Установка](#установка)
4. [Быстрый старт](#быстрый-старт)
5. [API Reference](#api-reference)
6. [Примеры использования](#примеры-использования)
7. [Настройка каналов](#настройка-каналов)
8. [Миграция со старой системы](#миграция-со-старой-системы)

---

## 🎯 Обзор

Упрощенная универсальная система уведомлений, которая:

✅ **Проста** - 2 модели вместо 6  
✅ **Универсальна** - GenericForeignKey для любых объектов  
✅ **Стандартна** - API как в django-notifications-hq  
✅ **Multi-channel** - WebSocket, Email, Telegram, Push  
✅ **Переиспользуема** - можно использовать в других проектах  
✅ **Современна** - Django 5.2+ совместима

---

## 🏗️ Архитектура

### Модели

#### 1. **Notification** (основная модель)

Структура: `actor` performed `verb` on `action_object` at `target`

**Пример:**
```
John (actor) commented (verb) on photo (target)
Mary (actor) liked (verb) your comment (action_object) on post (target)
System (actor) approved (verb) your request (action_object)
```

**Поля:**
- `recipient` - получатель (User)
- `actor` - кто совершил действие (GenericForeignKey)
- `verb` - действие (str): "liked", "commented", "approved"
- `action_object` - объект действия (GenericForeignKey, опционально)
- `target` - целевой объект (GenericForeignKey, опционально)
- `description` - человекочитаемое описание
- `action_url` - URL для перехода
- `data` - дополнительные данные (JSON)
- `unread` - непрочитано (bool)
- `public` - публичное (bool)
- `deleted` - удалено (bool, мягкое удаление)

#### 2. **UserChannelPreferences** (настройки пользователя)

Один пользователь - одна запись с настройками всех каналов.

**Поля:**
- `web_enabled` - веб уведомления (bool)
- `email_enabled` - email уведомления (bool)
- `telegram_enabled` - Telegram уведомления (bool)
- `push_enabled` - Web Push уведомления (bool)
- `email_frequency` - частота email: instant/daily/weekly
- `dnd_enabled` - режим "Не беспокоить" (bool)
- `dnd_start_time` / `dnd_end_time` - время DND
- `disabled_verbs` - список отключенных типов (JSON array)

### Компоненты

1. **signals_new.py** - `notify.send()` API для создания уведомлений
2. **channels.py** - роутинг по каналам доставки (WebSocket, Email, Telegram, Push)
3. **models_new.py** - модели с QuerySet методами
4. **admin_new.py** - Django Admin интерфейс

---

## 📦 Установка

### Шаг 1: Применить миграции

```bash
python manage.py makemigrations notifications
python manage.py migrate notifications
```

### Шаг 2: Обновить код проекта

Код уже готов к использованию! Файлы:
- `backend/notifications/models_new.py`
- `backend/notifications/signals_new.py`
- `backend/notifications/channels.py`
- `backend/notifications/admin_new.py`

### Шаг 3: Подключить в apps.py

```python
# backend/notifications/apps.py
class NotificationsConfig(AppConfig):
    ...
    
    def ready(self):
        # Новые сигналы
        import notifications.signals_new  # noqa
        import notifications.channels  # noqa
```

---

## 🚀 Быстрый старт

### Создание уведомления

```python
from notifications.signals_new import notify

# Простое уведомление
notify.send(
    sender=current_user,
    recipient=other_user,
    verb='liked',
    description='liked your photo'
)

# С объектами
notify.send(
    sender=author,
    recipient=post.author,
    verb='commented',
    action_object=comment,
    target=post,
    description=f'commented on your post "{post.title}"',
    action_url=f'/posts/{post.id}/#comment-{comment.id}',
)

# Множественные получатели
notify.send(
    sender=manager,
    recipient=[user1, user2, user3],
    verb='approved',
    action_object=request,
    description='approved your budget request',
    action_url=f'/requests/{request.id}/',
)

# С дополнительными данными
notify.send(
    sender=system,
    recipient=user,
    verb='reminder',
    description='Meeting in 15 minutes',
    data={
        'meeting_id': 123,
        'meeting_title': 'Sprint Planning',
        'priority': 'high',
    },
    action_url='/calendar/meetings/123/',
)
```

### Получение уведомлений

```python
# Все уведомления пользователя
notifications = user.notifications.all()

# Непрочитанные
unread = user.notifications.unread()

# Прочитанные
read = user.notifications.read()

# По типу (verb)
likes = user.notifications.filter(verb='liked')

# За последние 7 дней
from datetime import timedelta
from django.utils import timezone

recent = user.notifications.filter(
    timestamp__gte=timezone.now() - timedelta(days=7)
)
```

### Управление уведомлениями

```python
# Отметить как прочитанное
notification.mark_as_read()

# Отметить как непрочитанное
notification.mark_as_unread()

# Отметить все как прочитанные
user.notifications.mark_all_as_read()

# Удалить (мягкое удаление)
notification.deleted = True
notification.save()

# Получить только активные
active = user.notifications.active()
```

---

## 📚 API Reference

### notify.send()

Создает уведомление и отправляет по каналам.

**Сигнатура:**
```python
notify.send(
    sender,                # Объект-актор (кто создал)
    recipient,             # User или [User, ...] (кому)
    verb,                  # str (обязательно) - действие
    action_object=None,    # Объект действия (опционально)
    target=None,           # Целевой объект (опционально)
    description='',        # str - описание
    action_url='',         # str - URL для перехода
    data={},               # dict - дополнительные данные
    public=True,           # bool - публичное ли
    timestamp=None,        # datetime - время (по умолчанию now)
)
```

**Возвращает:**
- `Notification` - если один получатель
- `[Notification, ...]` - если несколько получателей

### QuerySet методы

```python
# Фильтрация
.unread()               # Непрочитанные
.read()                 # Прочитанные
.active()               # Активные (не удаленные)
.deleted()              # Удаленные
.public()               # Публичные
.for_user(user)         # Для конкретного пользователя

# Действия
.mark_all_as_read(recipient=None)    # Отметить все как прочитанные
.mark_all_as_unread(recipient=None)  # Отметить все как непрочитанные
```

### Модель Notification

**Методы:**
```python
.mark_as_read()         # Отметить как прочитанное
.mark_as_unread()       # Отметить как непрочитанное
```

**Свойства:**
```python
.timesince              # "5 минут назад"
.slug                   # "123-liked-456" (для URL)
```

### Модель UserChannelPreferences

**Методы:**
```python
.is_verb_enabled(verb)       # Проверить, включен ли тип
.disable_verb(verb)          # Отключить тип
.enable_verb(verb)           # Включить тип
.is_in_dnd_period()          # В режиме "Не беспокоить"?
```

---

## 💡 Примеры использования

### Уведомления о комментариях

```python
# signals.py в приложении comments
from django.db.models.signals import post_save
from django.dispatch import receiver
from notifications.signals_new import notify

@receiver(post_save, sender=Comment)
def notify_comment(sender, instance, created, **kwargs):
    if not created:
        return
    
    comment = instance
    post = comment.post
    
    # Уведомить автора поста
    if comment.author != post.author:
        notify.send(
            sender=comment.author,
            recipient=post.author,
            verb='commented',
            action_object=comment,
            target=post,
            description=f'прокомментировал вашу запись "{post.title}"',
            action_url=f'/posts/{post.id}/#comment-{comment.id}',
        )
    
    # Уведомить упомянутых пользователей
    mentioned_users = comment.extract_mentions()
    if mentioned_users:
        notify.send(
            sender=comment.author,
            recipient=mentioned_users,
            verb='mentioned',
            action_object=comment,
            target=post,
            description=f'упомянул вас в комментарии',
            action_url=f'/posts/{post.id}/#comment-{comment.id}',
        )
```

### Уведомления о лайках

```python
@receiver(post_save, sender=Like)
def notify_like(sender, instance, created, **kwargs):
    if not created:
        return
    
    like = instance
    post = like.post
    
    if like.user != post.author:
        notify.send(
            sender=like.user,
            recipient=post.author,
            verb='liked',
            action_object=like,
            target=post,
            description=f'понравилась ваша запись "{post.title}"',
            action_url=f'/posts/{post.id}/',
            data={'like_id': like.id},
        )
```

### Системные уведомления

```python
from django.contrib.auth import get_user_model

User = get_user_model()

def notify_approval(request):
    """Уведомление об одобрении заявки"""
    notify.send(
        sender=None,  # Системное уведомление
        recipient=request.author,
        verb='request_approved',
        action_object=request,
        description=f'Ваша заявка #{request.id} одобрена',
        action_url=f'/requests/{request.id}/',
        data={
            'request_type': request.type,
            'approved_by': request.approved_by.get_full_name(),
            'approved_at': request.approved_at.isoformat(),
        },
    )
```

### Уведомления о событиях календаря

```python
def notify_event_reminder(event, minutes_before=15):
    """Напоминание о событии"""
    from django.utils import timezone
    
    participants = event.participants.all()
    
    notify.send(
        sender=None,
        recipient=list(participants),
        verb='event_reminder',
        action_object=event,
        description=f'Событие "{event.title}" начнется через {minutes_before} минут',
        action_url=f'/calendar/events/{event.id}/',
        data={
            'event_start': event.start_time.isoformat(),
            'location': event.location,
            'minutes_before': minutes_before,
        },
    )
```

---

## ⚙️ Настройка каналов

### Создание настроек для пользователя

Настройки создаются автоматически при первом уведомлении.

Можно создать вручную:
```python
from notifications.models_new import UserChannelPreferences

prefs, created = UserChannelPreferences.objects.get_or_create(
    user=user,
    defaults={
        'web_enabled': True,
        'email_enabled': True,
        'telegram_enabled': False,
        'push_enabled': True,
        'email_frequency': 'instant',
    }
)
```

### Изменение настроек

```python
# Получить настройки
prefs = user.channel_preferences

# Изменить каналы
prefs.email_enabled = True
prefs.telegram_enabled = True
prefs.save()

# Отключить определенный тип
prefs.disable_verb('liked')
prefs.disable_verb('followed')

# Включить обратно
prefs.enable_verb('liked')

# Установить тихий режим
prefs.dnd_enabled = True
prefs.dnd_start_time = '22:00'
prefs.dnd_end_time = '08:00'
prefs.save()
```

### Email дайджесты

Для отправки дайджестов используйте Celery task:

```python
# tasks.py
from celery import shared_task
from notifications.channels import send_email_digest
from notifications.models_new import UserChannelPreferences

@shared_task
def send_daily_digests():
    """Отправка ежедневных дайджестов"""
    users = UserChannelPreferences.objects.filter(
        email_enabled=True,
        email_frequency='daily'
    ).select_related('user')
    
    for prefs in users:
        send_email_digest(prefs.user, frequency='daily')

@shared_task
def send_weekly_digests():
    """Отправка еженедельных дайджестов"""
    users = UserChannelPreferences.objects.filter(
        email_enabled=True,
        email_frequency='weekly'
    ).select_related('user')
    
    for prefs in users:
        send_email_digest(prefs.user, frequency='weekly')
```

Настройте в Celery beat:
```python
# settings.py
CELERY_BEAT_SCHEDULE = {
    'send-daily-digests': {
        'task': 'notifications.tasks.send_daily_digests',
        'schedule': crontab(hour=8, minute=0),  # Каждый день в 8:00
    },
    'send-weekly-digests': {
        'task': 'notifications.tasks.send_weekly_digests',
        'schedule': crontab(day_of_week=1, hour=8, minute=0),  # Понедельник 8:00
    },
}
```

---

## 🔄 Миграция со старой системы

### Этап 1: Перенос данных

Создайте management command для миграции:

```python
# management/commands/migrate_notifications.py
from django.core.management.base import BaseCommand
from notifications.models import Notification as OldNotification
from notifications.models_new import Notification as NewNotification

class Command(BaseCommand):
    def handle(self, *args, **options):
        old_notifications = OldNotification.objects.all()
        
        for old in old_notifications:
            NewNotification.objects.create(
                recipient=old.recipient,
                verb=old.notification_type.code,  # type code → verb
                description=old.message,
                action_url=old.action_url,
                unread=not old.is_read,
                timestamp=old.created_at,
                deleted=old.is_archived,
                emailed=old.sent_email,
                data={
                    'old_id': old.id,
                    'old_type': old.notification_type.name,
                },
            )
        
        self.stdout.write(f'Migrated {old_notifications.count()} notifications')
```

### Этап 2: Перенос настроек

```python
# management/commands/migrate_user_settings.py
from django.core.management.base import BaseCommand
from notifications.models import UserNotificationSettings as OldSettings
from notifications.models_new import UserChannelPreferences

class Command(BaseCommand):
    def handle(self, *args, **options):
        # Группируем старые настройки по пользователям
        from django.contrib.auth import get_user_model
        User = get_user_model()
        
        for user in User.objects.all():
            old_settings = OldSettings.objects.filter(user=user)
            
            # Определяем какие каналы включены
            web_enabled = old_settings.filter(send_web=True).exists()
            email_enabled = old_settings.filter(send_email=True).exists()
            telegram_enabled = old_settings.filter(send_telegram=True).exists()
            
            # Частота email
            email_freq = old_settings.filter(
                send_email=True
            ).first()
            email_frequency = email_freq.email_frequency if email_freq else 'instant'
            
            # Создаем новые настройки
            UserChannelPreferences.objects.get_or_create(
                user=user,
                defaults={
                    'web_enabled': web_enabled,
                    'email_enabled': email_enabled,
                    'telegram_enabled': telegram_enabled,
                    'email_frequency': email_frequency,
                }
            )
        
        self.stdout.write('User settings migrated')
```

### Этап 3: Постепенная замена кода

1. **Создание уведомлений** - заменить:
   ```python
   # Старое
   NotificationService.create_notification(
       recipient=user,
       notification_type_code='chat_new_message',
       title='Новое сообщение',
       message='...',
   )
   
   # Новое
   notify.send(
       sender=author,
       recipient=user,
       verb='chat_new_message',
       description='...',
   )
   ```

2. **Получение уведомлений** - заменить:
   ```python
   # Старое
   Notification.objects.filter(recipient=user, is_read=False)
   
   # Новое
   user.notifications.unread()
   ```

3. **Отметка прочитанными** - заменить:
   ```python
   # Старое
   NotificationService.mark_as_read(notification_id)
   
   # Новое
   notification.mark_as_read()
   ```

---

## 📖 Рекомендуемые verb типы

Стандартные типы для consistency:

**Социальные действия:**
- `liked` - лайк
- `commented` - комментарий
- `shared` - репост
- `followed` - подписка
- `mentioned` - упоминание
- `replied` - ответ

**Документы:**
- `document_created` - создан документ
- `document_updated` - обновлен документ
- `document_approved` - одобрен документ
- `document_rejected` - отклонен документ
- `document_signed` - подписан документ

**Заявки:**
- `request_created` - создана заявка
- `request_approved` - одобрена заявка
- `request_rejected` - отклонена заявка
- `request_completed` - выполнена заявка

**Календарь:**
- `event_created` - создано событие
- `event_updated` - обновлено событие
- `event_reminder` - напоминание о событии
- `event_cancelled` - отменено событие

**Система:**
- `system_message` - системное сообщение
- `reminder` - напоминание
- `alert` - предупреждение
- `error` - ошибка

---

## 🎨 Кастомизация

### Добавление своего канала

Создайте обработчик в `channels.py`:

```python
@receiver(post_save, sender='notifications.Notification')
def send_sms_notification(sender, instance, created, **kwargs):
    """Отправка SMS"""
    if not created:
        return
    
    notification = instance
    prefs = notification.recipient.channel_preferences
    
    if not hasattr(prefs, 'sms_enabled') or not prefs.sms_enabled:
        return
    
    # Ваша логика отправки SMS
    send_sms(
        phone=notification.recipient.phone,
        message=notification.description,
    )
```

### Кастомные шаблоны email

Создайте шаблоны в `templates/notifications/email/`:

```
templates/
  notifications/
    email/
      default.html         # Общий шаблон
      liked.html           # Для verb='liked'
      commented.html       # Для verb='commented'
      digest.html          # Дайджест
```

---

## 🧪 Тестирование

```python
from django.test import TestCase
from notifications.signals_new import notify
from notifications.models_new import Notification

class NotificationTests(TestCase):
    def test_create_notification(self):
        """Создание уведомления"""
        notification = notify.send(
            sender=self.user1,
            recipient=self.user2,
            verb='liked',
            description='Test'
        )
        
        self.assertIsInstance(notification, Notification)
        self.assertEqual(notification.recipient, self.user2)
        self.assertEqual(notification.verb, 'liked')
        self.assertTrue(notification.unread)
    
    def test_mark_as_read(self):
        """Отметка прочитанным"""
        notification = notify.send(
            sender=self.user1,
            recipient=self.user2,
            verb='test'
        )
        
        notification.mark_as_read()
        
        self.assertFalse(notification.unread)
        self.assertIsNotNone(notification.timestamp_read)
```

---

## 📈 Производительность

### Оптимизация запросов

```python
# Используйте select_related для GenericForeignKey
notifications = user.notifications.select_related(
    'actor_content_type',
    'action_object_content_type',
    'target_content_type',
)

# Prefetch для больших списков
from django.db.models import Prefetch

notifications = Notification.objects.filter(
    recipient=user
).prefetch_related(
    Prefetch('actor_content_type'),
)
```

### Индексы

Все необходимые индексы уже созданы в модели:
- `[recipient, -timestamp]`
- `[recipient, unread, -timestamp]`
- `[verb, -timestamp]`
- `[-timestamp]`

---

## 🆘 Поддержка

При возникновении проблем:

1. Проверьте логи: `logs/notifications.log`
2. Проверьте настройки пользователя в админке
3. Проверьте что сигналы подключены в `apps.py`
4. Убедитесь что Channels работает для WebSocket

---

**Changelog:**
- v2.0 (9 марта 2026) - Полный рефакторинг, упрощение до 2 моделей
- v1.0 - Старая система (6 моделей, NotificationService)
