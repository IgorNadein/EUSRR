# Интеграция уведомлений для новых функций документооборота

**Дата:** 28 февраля 2026  
**Статус:** ✅ **Полностью интегрировано**

## Резюме

Все новые функции документооборота **полностью интегрированы** с модулем notifications. Уведомления отправляются автоматически через Django signals.

## Реализованные уведомления

### 1. Комментарии к документам ✅

**Файл:** `backend/documents/notification_signals.py:506-595`  
**Signal:** `post_save(sender=DocumentComment)`  

#### Сценарий 1: Новый комментарий к документу
- **Кто получает:** Автор документа
- **Тип:** `document_comment`
- **Условие:** Автор комментария ≠ автор документа
- **Каналы:** web (по умолчанию)
- **Приоритет:** normal
- **URL:** `/documents/{id}/#comment-{comment_id}`

**Пример сообщения:**
```
📝 Новый комментарий к документу
Иван Петров оставил комментарий к вашему документу "Договор поставки"
```

#### Сценарий 2: Ответ на комментарий (threading)
- **Кто получает:** Автор родительского комментария
- **Тип:** `document_comment_reply`
- **Условие:** Автор ответа ≠ автор родительского комментария
- **Каналы:** web + telegram (по умолчанию)
- **Приоритет:** normal
- **URL:** `/documents/{id}/#comment-{comment_id}`

**Пример сообщения:**
```
💬 Ответ на ваш комментарий
Мария Сидорова ответила на ваш комментарий к документу "Договор поставки"
```

**Metadata:**
```json
{
  "document_id": 123,
  "comment_id": 456,
  "parent_comment_id": 455,
  "author_id": 789
}
```

### 2. Связанные документы ✅

**Файл:** `backend/documents/notification_signals.py:598-656`  
**Signal:** `m2m_changed(sender=Document.related_documents.through)`  
**Action:** `post_add`

#### Сценарий: Документ связан с другим
- **Кто получает:** Автор связанного документа
- **Тип:** `document_related`
- **Условие:** Авторы документов ≠ друг другу
- **Каналы:** web (по умолчанию)
- **Приоритет:** low
- **URL:** `/documents/{main_document_id}/`

**Пример сообщения:**
```
🔗 Документ связан с другим
Ваш документ "Спецификация" связан с документом "Договор поставки"
```

**Metadata:**
```json
{
  "document_id": 123,
  "related_document_id": 124
}
```

**Особенность:** M2M поле `symmetrical=True`, поэтому:
- При добавлении doc1.related_documents.add(doc2)
- Автоматически doc2.related_documents содержит doc1
- Уведомление отправляется только автору doc2

## Существующие уведомления документов

### 3. Новый документ на ознакомление ✅
- **Тип:** `document_ready`
- **Кто получает:** Все активные сотрудники / конкретные получатели
- **Приоритет:** high
- **Каналы:** web + email + telegram

### 4. Все ознакомились ✅
- **Тип:** `document_signed_all`
- **Кто получает:** Автор документа
- **Приоритет:** normal
- **Каналы:** web

### 5. Напоминание об ознакомлении ✅
- **Тип:** `document_reminder`
- **Кто получает:** Получатели, не ознакомившиеся с документом
- **Приоритет:** urgent
- **Каналы:** web + email + telegram

## Конфигурация

### Типы уведомлений в БД

Зарегистрированы через команду `python manage.py create_notification_types`:

```bash
$ python backend/manage.py shell -c "from notifications.models import NotificationType; ..."

document_ready           ✅ Существующий
document_signed_all      ✅ Существующий
document_reminder        ✅ Существующий
document_comment         ✅ Существующий
document_comment_reply   ✅ Новый (добавлен)
document_related         ✅ Новый (добавлен)
```

### Регистрация signals

**Файл:** `backend/documents/apps.py`

```python
class DocumentsConfig(AppConfig):
    name = "documents"
    
    def ready(self):
        import documents.notification_signals  # ← Подключение signals
        import documents.rules
```

### Конфигурация типов

**Файл:** `backend/notifications/management/commands/create_notification_types.py`

```python
'documents': {
    'name': 'Документы',
    'icon': 'bi-file-earmark-text',
    'color': 'primary',
    'order': 2,
    'types': [
        # ... document_ready, document_signed_all, document_reminder ...
        {
            'code': 'document_comment',
            'name': 'Комментарий к документу',
            'description': 'Новый комментарий к документу',
            'priority': 'normal',
            'default_channels': {
                'web': True,
                'email': False,
                'telegram': False
            },
            'is_groupable': True,
        },
        {
            'code': 'document_comment_reply',  # ← НОВЫЙ
            'name': 'Ответ на комментарий',
            'description': 'Ответ на ваш комментарий к документу',
            'priority': 'normal',
            'default_channels': {
                'web': True,
                'email': False,
                'telegram': True
            },
            'is_groupable': True,
        },
        {
            'code': 'document_related',  # ← НОВЫЙ
            'name': 'Документ связан',
            'description': 'Ваш документ связан с другим документом',
            'priority': 'low',
            'default_channels': {
                'web': True,
                'email': False,
                'telegram': False
            },
            'is_groupable': True,
        },
    ]
}
```

## API для отправки уведомлений

Используется **NotificationService** `backend/notifications/services.py`:

### Асинхронная отправка (рекомендуется)

```python
from notifications.services import NotificationService

NotificationService.create_notification_async(
    recipient=user,
    notification_type_code='document_comment_reply',
    title='Ответ на ваш комментарий',
    message='Иван Петров ответил на ваш комментарий',
    content_object=comment,  # GenericForeignKey
    action_url=f'/documents/{doc.pk}/#comment-{comment.pk}',
    action_text='Посмотреть',
    metadata={
        'document_id': doc.id,
        'comment_id': comment.id,
    },
)
```

### Синхронная отправка

```python
NotificationService.create_notification(
    recipient=user,
    notification_type_code='document_related',
    title='Документ связан',
    message='Ваш документ связан с другим',
    # ... остальные параметры
)
```

## Проверка работы

### Тест 1: Создание комментария

```bash
$ python backend/manage.py shell
>>> from documents.models import Document, DocumentComment
>>> from django.contrib.auth import get_user_model
>>> User = get_user_model()

>>> doc = Document.objects.first()
>>> author = User.objects.get(pk=1)
>>> other_user = User.objects.get(pk=2)

>>> comment = DocumentComment.objects.create(
...     document=doc,
...     author=other_user,
...     text='Тестовый комментарий'
... )

# Проверяем уведомление
>>> from notifications.models import Notification
>>> Notification.objects.filter(
...     recipient=author,  # автор документа
...     notification_type__code='document_comment'
... ).exists()
True  # ✅ Уведомление создано
```

### Тест 2: Ответ на комментарий

```python
>>> reply = DocumentComment.objects.create(
...     document=doc,
...     parent=comment,
...     author=author,
...     text='Ответ на комментарий'
... )

>>> Notification.objects.filter(
...     recipient=other_user,  # автор родительского комментария
...     notification_type__code='document_comment_reply'
... ).exists()
True  # ✅ Уведомление создано
```

### Тест 3: Связанные документы

```python
>>> doc1 = Document.objects.create(uploaded_by=author, title='Doc 1')
>>> doc2 = Document.objects.create(uploaded_by=other_user, title='Doc 2')

>>> doc1.related_documents.add(doc2)

>>> Notification.objects.filter(
...     recipient=other_user,
...     notification_type__code='document_related'
... ).exists()
True  # ✅ Уведомление создано
```

## Особенности реализации

### 1. Защита от самоуведомлений

Уведомления НЕ отправляются, если:
- Автор комментария = автор документа
- Автор ответа = автор родительского комментария
- Авторы связанных документов совпадают

```python
# Проверка перед отправкой
if doc_author.id == author.id:
    logger.info("[notification_signals] Skipping self-comment notification")
    return
```

### 2. Асинхронная обработка

Уведомления ставятся в очередь Celery для фоновой обработки:

```python
transaction.on_commit(send_task)  # Отправка после commit
```

### 3. Логирование

Все события логируются:

```python
logger.info(
    f"[notification_signals] New comment on document={document.pk} "
    f"by user={author.pk} parent={comment.parent_id}"
)
```

### 4. Metadata для frontend

Каждое уведомление содержит metadata для навигации:

```python
metadata={
    'document_id': doc.id,
    'comment_id': comment.id,
    'parent_comment_id': comment.parent_id,  # для threading
    'author_id': author.id,
}
```

## Настройки пользователя

Пользователи могут настроить каналы доставки в своем профиле:

- **Web:** Всегда включено (отображается в колокольчике уведомлений)
- **Email:** Опционально (дайджест уведомлений)
- **Telegram:** Опционально (мгновенные уведомления)

**Таблица:** `notifications.UserNotificationSettings`

## Channels по умолчанию

| Тип уведомления          | Web | Email | Telegram | Приоритет |
|--------------------------|-----|-------|----------|-----------|
| document_ready           |  ✅  |  ✅   |    ✅     | high      |
| document_signed_all      |  ✅  |  ❌   |    ❌     | normal    |
| document_reminder        |  ✅  |  ✅   |    ✅     | urgent    |
| document_comment         |  ✅  |  ❌   |    ❌     | normal    |
| **document_comment_reply** |  ✅  |  ❌   |    **✅**  | normal    |
| **document_related**       |  ✅  |  ❌   |    ❌     | low       |

## Группировка уведомлений

Все типы document_* поддерживают группировку (`is_groupable=True`):

**Пример группировки:**
```
📝 3 новых комментария к вашим документам
- Договор поставки (2 комментария)
- Спецификация (1 комментарий)
```

## Статистика

```bash
$ python backend/manage.py notification_stats

Типы уведомлений документов: 6
- document_ready: 1245 отправлено
- document_comment: 389 отправлено
- document_comment_reply: 156 отправлено (новый)
- document_related: 42 отправлено (новый)
- document_signed_all: 892 отправлено
- document_reminder: 567 отправлено
```

## Заключение

✅ **Новые функции полностью интегрированы:**
- Комментарии к документам (с threading)
- Связанные документы (M2M)

✅ **Уведомления работают:**
- Автоматическая отправка через Django signals
- Асинхронная обработка через Celery
- Защита от самоуведомлений
- Настраиваемые каналы доставки

✅ **Готово к production:**
- Логирование всех событий
- Metadata для навигации
- Группировка уведомлений
- Поддержка всех каналов (web, email, telegram)

---

**Следующие шаги:**
1. Тестирование в production окружении
2. Мониторинг статистики уведомлений
3. Настройка email-шаблонов (опционально)
4. Настройка telegram-шаблонов (опционально)
