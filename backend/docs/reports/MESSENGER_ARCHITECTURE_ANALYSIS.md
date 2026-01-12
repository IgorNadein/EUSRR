# Анализ архитектуры мессенджера: Проблемы и решения

**Дата:** 12 января 2026  
**Статус:** Критические проблемы найдены

## 🔴 Ключевые проблемы

### 1. **Отсутствует загрузка "вокруг" сообщения**

**Текущая реализация:**
```python
# GET /api/v1/communications/chats/{id}/messages/?before_id=X&limit=50
# Загружает только СТАРЫЕ сообщения (before)
```

**Проблема:**
- При открытии чата с 1000 сообщений (950 прочитано, 50 новых)
- Загружаются последние 50 сообщений
- Но скролл должен быть на сообщении #950 (last read)
- Пользователь не видит контекст ВОКРУГ last read

**Как в Telegram/WhatsApp:**
```
GET /messages?around=950&limit=50
→ Возвращает: сообщения 925-975 (25 до + 25 после)
→ Скролл на сообщении #950
```

### 2. **LastRead хранится как timestamp вместо message_id**

**Текущая реализация:**
```python
# ChatReadState хранит last_read_at (timestamp)
# Проблема: несколько сообщений могут иметь одинаковый timestamp
```

**Правильно:**
```python
# Хранить last_read_message_id
# Позволяет точно позиционировать скролл
```

### 3. **WebSocket дублирует HTTP загрузку**

**Текущая проблема:**
```javascript
// 1. ChatController загружает через HTTP
await loader.loadInitialMessages() // → 50 сообщений

// 2. WebSocket присылает те же сообщения
ws.send({action: 'open_chat'}) // → initial_messages с теми же 50
```

**Результат:** Двойная загрузка, повторный render, прыжки скролла

**Правильно:**
- WebSocket НЕ должен отправлять initial messages
- Initial загрузка ТОЛЬКО через HTTP
- WS только для real-time обновлений

### 4. **Нет bidirectional pagination**

**Современные мессенджеры:**
```
┌─────────────────────────┐
│ ↑ Scroll up = load more │ ← Бесконечный скролл вверх
├─────────────────────────┤
│   [Сообщения вокруг]    │ ← Initial load вокруг last_read
├─────────────────────────┤
│ ↓ Scroll down = load    │ ← Если есть более новые
└─────────────────────────┘
```

**Наша система:**
```
┌─────────────────────────┐
│ ↑ Scroll up = load more │ ← Работает
├─────────────────────────┤
│   [Последние 50]        │ ← Всегда загружаются последние
├─────────────────────────┤
│ ✗ No scroll down load   │ ← НЕТ
└─────────────────────────┘
```

## ✅ Решение

### Фаза 1: Backend - новый endpoint (5 минут)

```python
# backend/api/v1/communications/views.py

@login_required
@require_GET
def load_chat_messages_around(request, pk: int):
    """Загрузка сообщений ВОКРУГ конкретного message_id"""
    chat = get_object_or_404(Chat, pk=pk)
    user = request.user

    if not user_can_access_chat(chat, user):
        return JsonResponse({"ok": False, "error": "forbidden"}, status=403)

    # Параметры
    around_id = request.GET.get("around_id")  # ID сообщения-центра
    limit = int(request.GET.get("limit", 50))
    half = limit // 2

    if not around_id:
        # Если нет around_id - используем last_read
        read_state = ChatReadState.objects.filter(
            chat=chat, user=user
        ).first()
        
        if read_state and read_state.last_read_message_id:
            around_id = read_state.last_read_message_id
        else:
            # Нет last_read - загружаем последние
            return load_chat_messages(request, pk)

    # Загружаем around
    anchor = Message.objects.filter(chat=chat, pk=around_id).first()
    if not anchor:
        return load_chat_messages(request, pk)

    # Сообщения ДО anchor
    before_qs = (
        Message.objects.filter(
            chat=chat, created_at__lt=anchor.created_at
        )
        .order_by("-created_at")[:half]
    )
    before_messages = list(reversed(list(before_qs)))

    # Сообщения ПОСЛЕ anchor (включая само)
    after_qs = (
        Message.objects.filter(
            chat=chat, created_at__gte=anchor.created_at
        )
        .order_by("created_at")[: half + 1]
    )
    after_messages = list(after_qs)

    # Объединяем
    all_messages = before_messages + after_messages
    serialized = [serialize_message(m) for m in all_messages]

    return JsonResponse({
        "ok": True,
        "messages": serialized,
        "anchor_id": int(around_id),
        "has_more_before": len(before_messages) == half,
        "has_more_after": len(after_messages) > half
    })
```

### Фаза 2: Frontend - использовать новый endpoint (10 минут)

```javascript
// messageLoader.js

async loadInitialMessages(chatId, options = {}) {
    // Проверяем есть ли lastReadMessageId
    const lastReadId = options.lastReadMessageId || 
                       this._getLastReadFromStorage(chatId);

    let url;
    if (lastReadId) {
        // Загружаем ВОКРУГ last read
        url = `/api/v1/communications/chats/${chatId}/messages/around/`;
        url += `?around_id=${lastReadId}&limit=50`;
    } else {
        // Загружаем последние
        url = `/api/v1/communications/chats/${chatId}/messages/`;
        url += `?limit=50`;
    }

    const response = await fetch(url);
    const data = await response.json();
    
    // Сохраняем в Store
    messages.forEach(msg => msg.chat_id = chatId);
    this.store.addMessages(data.messages);

    return {
        messages: data.messages,
        anchorId: data.anchor_id,  // На какое сообщение скроллить
        hasMoreBefore: data.has_more_before,
        hasMoreAfter: data.has_more_after
    };
}
```

### Фаза 3: Обновить ChatReadState (20 минут)

```python
# Добавить поле last_read_message_id в модель
class ChatReadState(models.Model):
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    last_read_at = models.DateTimeField()  # Deprecated
    last_read_message_id = models.BigIntegerField(null=True)  # NEW
```

## 📊 Результат

**До:**
```
Открытие чата → Загрузка последних 50 → Скролл вниз → Прыжок
```

**После:**
```
Открытие чата → Загрузка 25 до + 25 после last_read → 
Скролл уже на нужной позиции → Без прыжков
```

## 🎯 Приоритет

1. **Критично:** Endpoint `messages/around/` - 5 минут
2. **Критично:** Frontend использует around - 10 минут  
3. **Средне:** Обновить ChatReadState с message_id - 20 минут
4. **Низко:** Bidirectional scroll (load after) - 30 минут

## 🔗 Примеры из реальных мессенджеров

**Telegram API:**
```
messages.getHistory(
  peer, 
  offset_id: int,     // ID сообщения-якоря
  add_offset: -25,    // -25 = загрузить 25 выше
  limit: 50          // Всего 50 сообщений
)
// Возвращает 25 до + 25 после offset_id
```

**Discord API:**
```
GET /channels/{id}/messages?around={message_id}&limit=50
// Возвращает сообщения вокруг указанного
```

**WhatsApp:**
- Хранит last_read_message_id
- При открытии загружает 40 сообщений вокруг него
- Скролл автоматически на last_read
