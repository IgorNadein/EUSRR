# Django Universal Notifications

Универсальная переиспользуемая система уведомлений для Django 5.2+

## ✨ Особенности

- 🎯 **Простота** - 2 модели вместо 6
- 🔄 **Универсальность** - GenericForeignKey для любых объектов
- 📡 **Multi-channel** - WebSocket, Email, Web Push
- ⚡ **Производительность** - оптимизированные индексы и QuerySet
- 🎨 **Гибкость** - легко расширяется под любые нужды
- 🏗️ **Архитектура** - по образу django-notifications-hq

## 🚀 Быстрый старт

```python
from notifications.signals_new import notify

# Создать уведомление
notify.send(
    sender=user,
    recipient=other_user,
    verb='liked',
    description='liked your photo',
    action_url='/photos/123/'
)

# Получить уведомления
unread = user.notifications.unread()

# Отметить как прочитанное
notification.mark_as_read()
```

## 📦 Установка

1. Скопируйте приложение `notifications/` в ваш проект
2. Добавьте в `INSTALLED_APPS`:
   ```python
   INSTALLED_APPS = [
       ...
       'notifications',
   ]
   ```
3. Примените миграции:
   ```bash
   python manage.py migrate notifications
   ```

## 📚 Документация

## 🚧 TODO

### Критичные задачи:
- [ ] Написать unit и integration тесты (coverage >80%)
- [ ] Создать email шаблоны (notification.html/txt, digest.html/txt)
- [ ] Убрать хардкод 'EUSRR' из email sender

### Важные улучшения:
- [ ] Переместить API endpoints в notifications/api/
- [ ] Создать notifications/settings.py для централизованной конфигурации
- [ ] Добавить больше примеров использования в README

### Желательно:
- [ ] Подготовить setup.py для публикации в PyPI
- [ ] Sphinx документация
- [ ] CI/CD pipeline (GitHub Actions)
- [ ] Pre-commit hooks для линтеров

Полная документация: [`backend/docs/guides/NOTIFICATIONS_V2_USAGE.md`](../docs/guides/NOTIFICATIONS_V2_USAGE.md)

## 🏗️ Архитектура

### Модели

**Notification** - основная модель уведомлений
- Структура: `actor` performed `verb` on `action_object` at `target`
- GenericForeignKey для универсальности

**UserChannelPreferences** - настройки каналов доставки
- Один пользователь - одна запись
- Настройки для всех каналов (web, email, telegram, push)

### Компоненты

- `models_new.py` - модели с QuerySet методами
- `signals_new.py` - `notify.send()` API
- `channels.py` - роутинг уведомлений по каналам
- `admin_new.py` - Django Admin интерфейс

## 💡 Примеры

### Социальное взаимодействие

```python
# Лайк
notify.send(
    sender=user,
    recipient=post.author,
    verb='liked',
    target=post,
    description=f'liked your post "{post.title}"',
    action_url=f'/posts/{post.id}/'
)

# Комментарий
notify.send(
    sender=commenter,
    recipient=post.author,
    verb='commented',
    action_object=comment,
    target=post,
    description='commented on your post',
    action_url=f'/posts/{post.id}/#comment-{comment.id}'
)
```

### Системные уведомления

```python
# Одобрение документа
notify.send(
    sender=approver,
    recipient=document.author,
    verb='document_approved',
    action_object=document,
    description=f'Document #{document.id} approved',
    action_url=f'/documents/{document.id}/',
    data={'approved_by': approver.get_full_name()}
)
```

### Множественные получатели

```python
# Уведомить всю команду
notify.send(
    sender=manager,
    recipient=team_members,  # список пользователей
    verb='meeting_scheduled',
    description='Team meeting tomorrow at 10:00',
    action_url='/calendar/'
)
```

## ⚙️ Настройка каналов

```python
# Получить настройки пользователя
prefs = user.channel_preferences

# Включить/выключить каналы
prefs.email_enabled = True
prefs.push_enabled = False
prefs.save()

# Режим "Не беспокоить"
prefs.dnd_enabled = True
prefs.dnd_start_time = '22:00'
prefs.dnd_end_time = '08:00'
prefs.save()

# Отключить определенные типы
prefs.disable_verb('liked')
prefs.disable_verb('followed')
```

## 🧩 Интеграция

### WebSocket (Django Channels)

Уведомления автоматически отправляются через WebSocket если:
- Django Channels установлен и настроен
- `web_enabled=True` в настройках пользователя

### Email

Поддержка мгновенных уведомлений и дайджестов:
- `instant` - сразу при создании
- `daily` - ежедневный дайджест
- `weekly` - еженедельный дайджест

Для дайджестов используйте Celery:
```python
from notifications.channels import send_email_digest

send_email_digest(user, frequency='daily')
```

### Web Push

Требуется:
- `django-push-notifications` установлен
- Модель `WebPushSubscription`
- `push_enabled=True` в настройках

## 🎯 Рекомендуемые verb типы

Используйте стандартные типы для consistency:

**Социальные:**
- `liked`, `commented`, `shared`, `followed`, `mentioned`, `replied`

**Документы:**
- `document_created`, `document_updated`, `document_approved`, `document_rejected`

**Заявки:**
- `request_created`, `request_approved`, `request_rejected`, `request_completed`

**Календарь:**
- `event_created`, `event_updated`, `event_reminder`, `event_cancelled`

**Система:**
- `system_message`, `reminder`, `alert`, `error`

## 📊 QuerySet API

```python
# Фильтрация
user.notifications.unread()           # Непрочитанные
user.notifications.read()             # Прочитанные
user.notifications.active()           # Активные (не удаленные)
user.notifications.deleted()          # Удаленные

# Действия
user.notifications.mark_all_as_read()    # Отметить все как прочитанные
notification.mark_as_read()              # Отметить одно как прочитанное
```

## 🔄 Миграция со старых систем

Если мигрируете с другой системы уведомлений, см. раздел "Миграция" в полной документации.

## 🧪 Тестирование

```python
from notifications.signals_new import notify

# Создать тестовое уведомление
notification = notify.send(
    sender=user1,
    recipient=user2,
    verb='test',
    description='Test notification'
)

assert notification.unread == True
assert notification.recipient == user2
```

## 📄 Лицензия

MIT License - используйте свободно в своих проектах

## 🤝 Вклад

Приложение разработано как универсальное решение и может использоваться в любых Django проектах.

Не стесняйтесь адаптировать под свои нужды!

---

**Версия:** 2.0  
**Django:** 5.2+  
**Python:** 3.10+
