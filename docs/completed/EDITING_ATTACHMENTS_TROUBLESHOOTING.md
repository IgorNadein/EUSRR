# Troubleshooting: Edited Messages Lose Attachments/Reply

## Проблема

При редактировании сообщений через WebSocket, сообщения с вложениями или ответами становятся "простыми" - теряют эти компоненты в DOM.

## Что сделано для исправления

### 1. Backend Fix: Перезагрузка сообщения с prefetch

**Файл:** `backend/api/v1/communications/views.py`

**Проблема:** При вызове `serialize_message(message)` после сохранения не подгружались связанные объекты.

**Решение:** Перезагружать сообщение со всеми связями перед сериализацией:

```python
# БЫЛО:
message.save()
payload = serialize_message(message)  # ← attachments не загружены!

# СТАЛО:
message.save()

# Перезагружаем со всеми связями
message = Message.objects.select_related(
    'author',
    'reply_to',
    'reply_to__author',
    'forwarded_from_author',
    'poll'
).prefetch_related(
    'attachments',
    'reactions',
    'reactions__user',
    'poll__options'
).get(pk=message.id)

payload = serialize_message(message)  # ← attachments загружены!
```

### 2. Frontend: Добавлено детальное логирование

**Файл:** `backend/static/js/components/messageEditing.js`

Добавлено подробное логирование для отладки:

```javascript
console.log('[MessageEditing] ========== MESSAGE DATA ==========');
console.log('[MessageEditing] attachments:', message.attachments);
console.log('[MessageEditing] attachments length:', message.attachments?.length);
console.log('[MessageEditing] reply_to:', message.reply_to);
console.log('[MessageEditing] HTML contains "attachment":', newMessageHtml.includes('attachment'));
```

## Как проверить исправление

### Тест 1: Проверка backend сериализации

```bash
cd backend
python test_message_serialization.py
```

**Ожидаемый результат:**
```
✓ С prefetch все вложения загружены корректно!
✓ С select_related reply_to загружен корректно!
```

### Тест 2: Проверка MessageRenderer

1. Откройте: `http://localhost:9000/test-message-renderer/` (нужно добавить URL)
2. Нажмите кнопки тестов
3. Проверьте что HTML содержит:
   - `attachment-item` для вложений
   - `reply-reference` для ответов
   - `forwarded-indicator` для пересылок

### Тест 3: Реальное редактирование

1. Откройте чат с сообщением содержащим вложения
2. Откройте DevTools → Console
3. Отредактируйте сообщение (только текст!)
4. Проверьте логи:

**Что должно быть в Console:**
```
[MessageEditing] Message edited event received
[MessageEditing] ========== MESSAGE DATA ==========
[MessageEditing] attachments: [{id: 1, file_name: "test.pdf", ...}]
[MessageEditing] attachments length: 1
[MessageEditing] HTML contains "attachment": true
[MessageEditing] ✓ Message DOM replaced
```

## Возможные проблемы

### Проблема 1: attachments undefined

**Симптомы:**
```javascript
[MessageEditing] attachments: undefined
[MessageEditing] attachments length: undefined
```

**Причина:** Backend не отправил attachments в payload

**Решение:** Проверить что `serialize_message` вызывается с перезагруженным объектом

### Проблема 2: HTML не содержит attachment

**Симптомы:**
```javascript
[MessageEditing] attachments: [{...}]
[MessageEditing] HTML contains "attachment": false
```

**Причина:** `MessageRenderer.buildMessageHtml` не генерирует HTML для вложений

**Решение:** Проверить логику в `messageRenderer.js`:
```javascript
const attachmentsHtml = msg.attachments?.length ? 
    msg.attachments.map(att => this.buildAttachmentHtml(att)).join('') : '';
```

### Проблема 3: Вложения есть в HTML но не видны

**Симптомы:**
- В логах: `HTML contains "attachment": true`
- На странице: вложения не отображаются

**Причина:** CSS скрывает элементы или JS не переинициализировал компоненты

**Решение:** Проверить `reinitMessageComponents` и CSS стили

### Проблема 4: reply_to теряется

**Симптомы:**
```javascript
[MessageEditing] reply_to: null
```

**Причина:** Backend не загрузил reply_to из-за отсутствия select_related

**Решение:** Убедиться что в `edit_message` есть:
```python
message = Message.objects.select_related(
    'reply_to',
    'reply_to__author'
).get(pk=message.id)
```

## Тестовые сценарии

### Сценарий 1: Редактирование с вложениями

1. Создать сообщение с файлом
2. Отредактировать текст сообщения
3. **Ожидается:** Файл остался на месте

### Сценарий 2: Редактирование с ответом

1. Ответить на чье-то сообщение
2. Отредактировать свой ответ
3. **Ожидается:** Блок reply-to остался

### Сценарий 3: Редактирование переслан ного

1. Переслать сообщение
2. Отредактировать текст
3. **Ожидается:** "Переслано от..." остался

## Команды для отладки

```bash
# Запустить тесты сериализации
cd backend
python test_message_serialization.py

# Проверить что сервер запущен
curl http://localhost:9000/api/v1/communications/reactions/available/

# Открыть тест рендерера (в браузере)
http://localhost:9000/test-message-renderer/

# Смотреть логи WebSocket в реальном времени
# Откройте DevTools → Console → отфильтруйте [MessageEditing]
```

## Статус

- ✅ Backend исправлен (добавлен prefetch)
- ✅ Frontend логирование добавлено
- ⏳ Требуется тестирование на реальных данных
- ⏳ Требуется проверка всех сценариев

## Следующие шаги

1. Протестировать редактирование сообщения с вложением
2. Проверить логи в Console
3. Убедиться что `message.attachments` не undefined
4. Убедиться что HTML содержит attachment-item
5. Проверить что DOM обновился корректно
