# 🐛 Исправление бага: Ответы на сообщения не работали

**Дата:** 21 января 2026 г.  
**Проблема:** Сообщения отправлялись как обычные, даже после нажатия "Ответить"

---

## 🔍 Обнаруженная проблема

### Симптомы из логов:

```javascript
chatFormManager.js:199 [ChatFormManager] Mode: REPLY 11  // ✅ Режим установлен
chatComposer.js:307 [ChatComposer] Mode: reply MessageId: null  // ❌ ID потерян!
```

**Результат:** Сообщение отправилось как обычное (без `reply_to`), а не как ответ.

---

## 💡 Причина бага

### Ошибка в [chatComposer.js](../static/js/components/chatComposer.js#L295)

**Неправильный код:**
```javascript
const mode = window.chatFormManager?.mode || 'send';
const messageId = window.chatFormManager?.currentMessageId || null;
                                          ^^^^^^^^^^^^^^^
                                          СВОЙСТВО НЕ СУЩЕСТВУЕТ!
```

Свойства `mode` и `currentMessageId` **не экспортируются** из `chatFormManager`.

### Правильный способ получения данных:

```javascript
const formData = window.chatFormManager.getFormData();
// Возвращает:
// {
//   mode: 'send' | 'edit' | 'reply',
//   editMessageId: number | null,
//   replyToMessageId: number | null,
//   content: string
// }
```

---

## ✅ Исправление

### Файл: [chatComposer.js](../static/js/components/chatComposer.js)

#### До (неправильно):
```javascript
async handleSubmit(event) {
    const content = (this.textarea?.value || '').trim();
    
    // ❌ Неправильно: обращение к несуществующим свойствам
    const mode = window.chatFormManager?.mode || 'send';
    const messageId = window.chatFormManager?.currentMessageId || null;
    
    console.log('[ChatComposer] Mode:', mode, 'MessageId:', messageId);
    
    if (mode === 'edit' && messageId) {
        await this.sendEdit(messageId, content);
    } else {
        await this.sendMessage(content); // ❌ reply_to не передается!
    }
}
```

#### После (правильно):
```javascript
async handleSubmit(event) {
    const content = (this.textarea?.value || '').trim();
    
    // ✅ Правильно: используем getFormData()
    const formData = window.chatFormManager?.getFormData() || { mode: 'send' };
    const mode = formData.mode;
    const messageId = formData.editMessageId || null;
    const replyToMessageId = formData.replyToMessageId || null; // ✅ Получаем ID
    
    console.log('[ChatComposer] Mode:', mode, 'EditId:', messageId, 'ReplyTo:', replyToMessageId);
    
    if (mode === 'edit' && messageId) {
        await this.sendEdit(messageId, content);
    } else {
        await this.sendMessage(content, replyToMessageId); // ✅ Передаем ID
    }
}

// ✅ Обновлена сигнатура метода
async sendMessage(content, replyToMessageId = null) {
    const formData = new FormData(this.form);
    
    // ✅ Явно добавляем reply_to если это ответ
    if (replyToMessageId) {
        formData.set('reply_to', replyToMessageId);
        console.log('[ChatComposer] Sending reply to message:', replyToMessageId);
    }
    
    // ... остальной код
}
```

---

## 🧪 Как проверить исправление

### Тест 1: Ответ через контекстное меню

1. Открыть любой чат
2. ПКМ на сообщении → **Ответить**
3. Написать текст и отправить
4. Проверить логи:

```javascript
// ✅ ПРАВИЛЬНЫЙ ЛОГ (после исправления):
chatFormManager.js:199 [ChatFormManager] Mode: REPLY 11
chatComposer.js:307 [ChatComposer] Mode: reply EditId: null ReplyTo: 11  // ✅ ReplyTo: 11
chatComposer.js:XXX [ChatComposer] Sending reply to message: 11  // ✅ Подтверждение
```

5. Проверить в UI: новое сообщение должно показывать превью оригинального сообщения

### Тест 2: Проверка данных на backend

Открыть Network tab и посмотреть payload запроса:

```
POST /api/v1/communications/messages/upload/

FormData:
- chat_id: 8
- content: "щшоь"
- reply_to: 11  // ✅ Должно быть!
```

---

## 📊 Влияние изменений

### Что было исправлено:

| Компонент | Изменение | Статус |
|-----------|-----------|---------|
| `handleSubmit()` | Использует `getFormData()` вместо прямого доступа к свойствам | ✅ Исправлено |
| `sendMessage()` | Добавлен параметр `replyToMessageId` | ✅ Исправлено |
| FormData | Явно добавляется `reply_to` | ✅ Исправлено |
| Логирование | Показывает `ReplyTo` отдельно от `EditId` | ✅ Улучшено |
| Баг в `finally` | Исправлено `this.isSubmitting = false` | ✅ Бонус-фикс |

### Что НЕ затронуто:

- ✅ `chatFormManager` - работал правильно
- ✅ `messageContextMenu` - работал правильно  
- ✅ Backend - работал правильно
- ✅ Рендеринг превью - работал правильно

**Проблема была только в `chatComposer.js`** - неправильное получение данных из `chatFormManager`.

---

## 🎯 Итоги

### До исправления:
❌ Ответы не работали (отправлялись как обычные сообщения)  
❌ `replyToMessageId` терялся при отправке

### После исправления:
✅ Ответы работают корректно  
✅ `reply_to` передается на backend  
✅ Превью ответа отображается в сообщениях  
✅ Логи показывают правильные значения

---

**Статус:** 🟢 Баг исправлен  
**Тестирование:** Требуется проверка в браузере  
**Коммит:** Готово к коммиту
