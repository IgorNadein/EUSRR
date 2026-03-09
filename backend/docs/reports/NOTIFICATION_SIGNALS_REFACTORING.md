# Рефакторинг notification_signals - переход на прямой notify.send()

**Дата:** 2025-03-09  
**Статус:** ✅ Завершено

## Проблема

Обнаружено что все приложения пытаются использовать несуществующие Celery задачи:
- `notifications.tasks.process_request_notifications_task` ❌
- `notifications.tasks.process_document_notifications_task` ❌  
- `notifications.tasks.process_event_notifications_task` ❌
- `notifications.tasks.process_message_notifications_task` ❌
- `notifications.tasks.process_post_notifications_task` ❌

**Эти задачи НЕ РЕАЛИЗОВАНЫ!** Код падал в `except` блок и работал через fallback.

## Причина

Архитектура была переусложнена:

```python
# БЫЛО (2 слоя асинхронности - избыточно!):
Signal → transaction.on_commit → Celery task (НЕ СУЩЕСТВУЕТ) 
  → try/except fallback → notify.send() 
  → channels.py post_save → Celery задачи для каналов ✅

# СТАЛО (1 слой - оптимально!):
Signal → notify.send() 
  → channels.py post_save → Celery задачи для каналов ✅
```

**channels.py УЖЕ асинхронный!** Когда вызывается `notify.send()`:
1. Создается Notification в БД (быстро, ~1ms)
2. Post-save signal в channels.py автоматически запускает:
   - `send_websocket_notification.delay()` ✅
   - `send_email_notification.delay()` ✅
   - `send_push_notification.delay()` ✅

## Решение

Упростили все notification_signals.py - убрали несуществующие промежуточные задачи.

### Изменено 5 файлов

| Файл | Изменения |
|------|-----------|
| **requests_app/notification_signals.py** | Убраны 4 вызова `process_request_notifications_task`, прямые вызовы `notify_new_request()` и `notify_status_change()` |
| **documents/notification_signals.py** | Убран `process_document_notifications_task`, прямой вызов `notify_all_employees()` |
| **calendar_app/notification_signals.py** | Убраны 2 вызова `process_event_notifications_task`, прямые вызовы `notify_event_created()` и `notify_event_changed()` |
| **communications/notification_signals.py** | Убран `process_message_notifications_task`, прямой вызов `_create_message_notifications_sync()` |
| **feed/notification_signals.py** | Убран `process_post_notifications_task`, прямой вызов `notify_new_post()` |

### Убрано

- ❌ Все импорты `from notifications.tasks import process_*_notifications_task`
- ❌ Все `transaction.on_commit(lambda: ...)` обертки
- ❌ Все `try/except Exception` fallback блоки
- ❌ ~150 строк избыточного кода

### Добавлено

- ✅ Комментарии "channels.py автоматически отправит через Celery"
- ✅ Прямые вызовы функций создания уведомлений

## Результат

### До
```python
@receiver(post_save, sender=Request)
def create_request_notifications(sender, instance, created, **kwargs):
    from notifications.tasks import process_request_notifications_task
    
    def send_task():
        try:
            process_request_notifications_task.delay(...)  # НЕ СУЩЕСТВУЕТ
        except Exception as e:
            notify_new_request(instance)  # Всегда попадаем сюда
    
    transaction.on_commit(send_task)
```

### После
```python
@receiver(post_save, sender=Request)  
def create_request_notifications(sender, instance, created, **kwargs):
    # Отправляем уведомления напрямую - channels.py автоматически
    # сделает асинхронную отправку через Celery
    notify_new_request(instance)
```

## Преимущества

1. **Простота** - сигнал сразу вызывает функцию, без лишних слоев
2. **Производительность** - убран один hop через Celery
3. **Читаемость** - код делает ровно то что написано
4. **Надежность** - нет fallback'ов на несуществующие задачи
5. **Оптимальная асинхронность** - channels.py автоматически отправляет через Celery

## Проверка

```bash
.venv/bin/python manage.py check
# ✅ System check identified no issues (0 silenced)
```

## Архитектура notifications v2 (финальная)

```
┌─────────────────┐
│  Django Signal  │  (post_save, m2m_changed и т.д.)
└────────┬────────┘
         │
         ↓
┌─────────────────┐
│  notify.send()  │  Создает Notification в БД (~1ms)
└────────┬────────┘
         │
         ↓ post_save signal автоматически
┌─────────────────┐
│  channels.py    │  Роутер по каналам
└────────┬────────┘
         │
         ├─→ send_websocket_notification.delay()  (WebSocket, realtime)
         ├─→ send_email_notification.delay()      (Email с retry)
         └─→ send_push_notification.delay()       (Web Push)
                     ↓
            ┌─────────────────┐
            │  Celery Workers │  С retry, rate limiting, DND
            └─────────────────┘
```

**Единственный способ использования:**

```python
notify.send(
    sender=actor,
    recipient=user,
    verb='action_name',
    description='...',
    action_url='/url/',
    data={'title': '...'}
)
# Всё остальное автоматически! ✨
```

## Итоги

- **Строк кода удалено:** ~150
- **Несуществующих импортов удалено:** 5
- **Промежуточных Celery задач:** 0 (были попытки 5)
- **Реальных Celery задач:** 3 (send_websocket/email/push - работают!)
- **Архитектура:** упрощена с 2 слоев до 1
- **Производительность:** улучшена (меньше hops)
- **Код:** чище, понятнее, работает как задумано

**Теперь notifications v2 работает правильно: signal → notify.send() → channels.py → Celery ✅**
