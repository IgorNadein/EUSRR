# Аудит автоскролла в проекте EUSRR

## 📊 Сводная информация

**Дата аудита:** 13 января 2026  
**Цель:** Найти все места автоскролла и оценить их влияние на UX

---

## 🔍 Найденные места автоскролла

### 1. ⚠️ **userWebSocket.js** (КРИТИЧНО)

**Файл:** `backend/static/js/components/userWebSocket.js`

#### Место 1: Initial Messages (строка 273-279)
```javascript
if (options.messageRenderer && messages?.length) {
  options.messageRenderer.renderMessages(messages);
  
  if (!window.chatControllerV2) {  // Есть проверка на V2
    requestAnimationFrame(() => {
      state.scrollEl.scrollTop = state.scrollEl.scrollHeight;
    });
  }
}
```
**Статус:** ✅ Исправлено (есть проверка `!window.chatControllerV2`)  
**Проблема:** Срабатывает при WebSocket событии `initial_messages`

#### Место 2: New Message (строка 316)
```javascript
if (isOwnMessage || isAtBottom) {
  requestAnimationFrame(() => scrollToBottom());
}
```
**Статус:** ❌ АКТИВЕН! Дублирует логику ChatControllerV2  
**Проблема:** Автоскролл при получении нового сообщения через WebSocket  
**Решение:** Добавить проверку `if (!window.chatControllerV2)` перед автоскроллом

#### Место 3: scrollToBottom функция (строка 536-553)
```javascript
function scrollToBottom(instant = false) {
  if (!state.scrollEl) return;
  
  if (instant) {
    const prev = state.scrollEl.style.scrollBehavior;
    state.scrollEl.style.scrollBehavior = 'auto';
    state.scrollEl.scrollTop = state.scrollEl.scrollHeight;
    if (prev) {
      state.scrollEl.style.scrollBehavior = prev;
    } else {
      state.scrollEl.style.removeProperty('scroll-behavior');
    }
  } else {
    state.scrollEl.scrollTop = state.scrollEl.scrollHeight;
  }
}
```
**Статус:** ⚠️ Backward compatibility  
**Используется:** Только для старой архитектуры (не V2)

---

### 2. 🎮 **chatControllerV2.js**

**Файл:** `backend/static/js/controllers/chatControllerV2.js`

#### Место 1: Начальная загрузка (строки 161-180)
```javascript
// Нет anchor - скроллим в самый низ (как в Telegram)
await new Promise(resolve => {
  requestAnimationFrame(() => {
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        // Тройной RAF для надежности
        this.scrollElement.scrollTop = this.scrollElement.scrollHeight;
        // ...
```
**Статус:** ✅ Правильно - только при первой загрузке БЕЗ anchor  
**Когда срабатывает:** Открытие чата без последнего прочитанного сообщения

#### Место 2: Новое сообщение (строки 424-427)
```javascript
if (shouldScroll) {
  this.scrollManager.scrollToBottom({ 
    instant: isMyMessage && !AUTOSCROLL_CONFIG.SMOOTH_SCROLL_FOR_OWN,
    force: isMyMessage
  });
```
**Статус:** ✅ Правильно - с проверкой `isAtBottom` для чужих сообщений  
**Логика:**
- Свое сообщение → всегда скроллим
- Чужое сообщение + внизу → скроллим
- Чужое сообщение + читаем историю → НЕ скроллим (показываем индикатор)

#### Место 3: Кнопка "новые сообщения" (строки 671-675)
```javascript
btn.addEventListener('click', () => {
  this.scrollManager.scrollToBottom({ 
    instant: !AUTOSCROLL_CONFIG.SMOOTH_SCROLL_ON_CLICK, 
    force: true 
  });
```
**Статус:** ✅ Правильно - только по клику пользователя

---

### 3. 📜 **scrollManagerV2.js**

**Файл:** `backend/static/js/managers/scrollManagerV2.js`

#### Метод scrollToBottom (строки 365-383)
```javascript
scrollToBottom(options = {}) {
  const { instant = false, force = false } = options;
  
  if (!force && !this.isNearBottom()) {
    return;  // НЕ скроллим если пользователь читает историю
  }
  
  if (instant) {
    this.scrollEl.scrollTop = this.scrollEl.scrollHeight;
  } else {
    requestAnimationFrame(() => {
      this.scrollEl.scrollTop = this.scrollEl.scrollHeight;
    });
  }
}
```
**Статус:** ✅ Правильно - имеет проверку `isNearBottom()` и флаг `force`

---

### 4. 💬 **messageRenderer.js**

**Файл:** `backend/static/js/components/messageRenderer.js`

#### Inline onclick в reply-reference (строка 260)
```javascript
onclick="document.querySelector('[data-message-id=\\\"${msg.reply_to.id}\\\"]')?.scrollIntoView({behavior:'smooth',block:'center'})"
```
**Статус:** ✅ Правильно - скролл к цитируемому сообщению по клику  
**Проблема:** Нет - это ожидаемое поведение

---

### 5. 📝 **postDetailModal.js**

**Файл:** `backend/static/js/components/postDetailModal.js`

#### scrollToBottom в модальном окне (строка 366)
```javascript
function scrollToBottom() {
  window.scrollTo({ top: 0, behavior: 'smooth' });
}
```
**Статус:** ✅ Правильно - скролл комментариев в модальном окне  
**Область:** Только для модального окна постов (не чат)

---

## 🐛 Обнаруженные проблемы

### ❌ Проблема 1: Дублирование автоскролла
**Место:** `userWebSocket.js:316`  
**Описание:** При получении нового сообщения через WebSocket происходит автоскролл В userWebSocket И в chatControllerV2  
**Последствия:**
- Двойной скролл при получении сообщения
- Конфликт логики (может скроллить когда не нужно)
- После прыжка на дату может автоматически вернуться вниз

**Решение:**
```javascript
// Строка 316 userWebSocket.js
if (isOwnMessage || isAtBottom) {
  // Добавить проверку на V2
  if (!window.chatControllerV2) {
    requestAnimationFrame(() => scrollToBottom());
  }
}
```

---

### ⚠️ Проблема 2: loadNewer загружает не из Store

**Место:** `scrollManagerV2.js` метод `loadMoreNewer()`  
**Описание:** При скролле вниз после прыжка на дату, метод `loadNewer()` загружает сообщения ПОСЛЕ текущего newestId в Store, а не после последнего видимого сообщения

**Текущая логика:**
1. Пользователь прыгает на 1 декабря 2024
2. Store содержит ~30 сообщений вокруг этой даты
3. newestId = последнее из этих 30 сообщений (например 5 декабря)
4. При скролле вниз loadNewer грузит сообщения ПОСЛЕ 5 декабря
5. НО пропускает весь период с 6 декабря по сегодня!

**Правильная архитектура (как Telegram):**
```
[Store после loadAround]
├── messages: сообщения вокруг 1 декабря (30 шт)
├── boundaries:
│   ├── oldestId: самое старое сообщение в Store
│   ├── newestId: самое новое сообщение в Store  
│   ├── hasMoreBefore: true (есть сообщения ДО oldestId)
│   ├── hasMoreAfter: true (есть сообщения ПОСЛЕ newestId ДО текущего момента)
│   └── actualNewestId: ID самого последнего сообщения в чате (с сервера)
```

**Решение:**
- При `loadAround()` сохранять информацию о РЕАЛЬНОМ самом новом сообщении в чате
- `hasMoreAfter` должен означать "есть сообщения между newestId и actualNewestId"
- При `loadNewer()` проверять `hasMoreAfter` и грузить следующий батч

---

## ✅ Рекомендации

### 1. Отключить дублирующийся автоскролл в userWebSocket
```javascript
// userWebSocket.js строка 316
if (isOwnMessage || isAtBottom) {
  if (!window.chatControllerV2) {  // ← Добавить проверку
    requestAnimationFrame(() => scrollToBottom());
  }
}
```

### 2. Исправить loadNewer для корректной загрузки истории
**Проблема:** Когда прыгаем на дату, loadNewer грузит сообщения сразу после текущих, пропуская промежуточные

**Варианты решения:**

#### Вариант A: Добавить actualNewestId в boundaries
```javascript
// При loadAround сохранять реальный newest
_updateBoundaries(chatId, {
  newestId: messages[messages.length - 1].id,  // Последнее загруженное
  actualNewestId: result.actual_newest_id,     // С сервера
  hasMoreAfter: newestId < actualNewestId
});
```

#### Вариант B: Использовать timestamp вместо after_id
```javascript
// loadNewer с timestamp вместо ID
const result = await this._fetchWithRetry(
  buildUrl(API_ENDPOINTS.MESSAGES(chatId), {
    after_timestamp: boundaries.newestTimestamp,
    limit: this.config.HISTORY_LIMIT
  }),
  requestKey
);
```

### 3. Добавить debounce для loadNewer (уже есть! ✅)

### 4. Логирование для отладки
Добавить в `chatControllerV2._handleNewMessage`:
```javascript
console.log('[Autoscroll Decision]', {
  isMyMessage,
  isAtBottom,
  shouldScroll,
  scrollTop: this.scrollManager.scrollEl.scrollTop,
  scrollHeight: this.scrollManager.scrollEl.scrollHeight
});
```

---

## 📈 Приоритеты

1. **ВЫСОКИЙ:** Исправить дублирование автоскролла (userWebSocket.js:316)
2. **ВЫСОКИЙ:** Исправить loadNewer для правильной загрузки промежуточных сообщений
3. **СРЕДНИЙ:** Добавить логирование для отладки автоскролла
4. **НИЗКИЙ:** Оптимизировать количество RAF вызовов

---

## 🧪 Тестовые сценарии

### Сценарий 1: Прыжок на старую дату
1. Открыть чат
2. Кликнуть на дату → выбрать старую дату (например 1 месяц назад)
3. ✅ Должно перепрыгнуть мгновенно (без smooth scroll)
4. ✅ НЕ должно автоматически скроллить вниз после прыжка
5. Прокрутить вверх → должны загрузиться старые сообщения
6. Прокрутить вниз → должны загрузиться промежуточные сообщения (НЕ последние!)

### Сценарий 2: Получение нового сообщения
1. Открыть чат
2. Прокрутить к середине истории
3. Получить новое сообщение через WebSocket
4. ✅ НЕ должно автоматически скроллить (показать индикатор)
5. Прокрутить вниз
6. ✅ Должно автоматически скроллить к новым сообщениям

### Сценарий 3: Отправка своего сообщения
1. Открыть чат
2. Прокрутить к середине истории  
3. Отправить свое сообщение
4. ✅ Должно автоматически проскроллить вниз к своему сообщению

---

## 📝 Заключение

**Основные проблемы:**
1. ❌ Дублирующийся автоскролл в userWebSocket и chatControllerV2
2. ❌ loadNewer не учитывает промежуточные сообщения после прыжка на дату

**Статус файлов:**
- ✅ `chatControllerV2.js` - логика правильная
- ✅ `scrollManagerV2.js` - методы реализованы корректно
- ❌ `userWebSocket.js` - нужна проверка на V2
- ⚠️ `messageLoaderV2.js` - нужно исправить loadNewer для учета промежуточных сообщений
