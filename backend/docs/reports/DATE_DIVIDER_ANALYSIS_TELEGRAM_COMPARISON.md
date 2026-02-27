# Анализ: Date Divider Logic - EUSRR vs Telegram Web

**Дата:** 13 января 2026  
**Задача:** Централизовать логику добавления разделителей дат в чате

---

## 🔍 Telegram Web - Как они это делают

### Sticky Date Header (ключевая фича)

**Telegram Web K (tweb)** использует **sticky positioning** с **IntersectionObserver API**:

```typescript
// src/components/chat/bubbleGroups.ts
export class BubbleGroup {
  dateContainer: ReturnType<ChatBubbles['getDateContainerByTimestamp']>;
  
  onItemMount() {
    const dateContainer = this.chat.bubbles.getDateContainerByTimestamp(
      this.dateTimestamp / 1000
    );
    positionElementByIndex(
      this.container, 
      dateContainer.container, 
      STICKY_OFFSET + dateGroupsLength - 1 - idx - unmountedLength
    );
    ++dateContainer.groupsLength;
  }
}
```

**CSS** (src/scss/partials/_chatBubble.scss):
```scss
.bubble.is-date {
  position: sticky;
  top: $bubble-overflow-big; // Fixed offset
  z-index: 2;
  pointer-events: none;
  font-weight: var(--font-weight-bold);
  
  &.is-sticky {
    opacity: .00001; // Hide real date when sticky
  }
  
  .can-click-date & .bubble-content {
    cursor: pointer;      // ✅ Кликабельная дата!
    pointer-events: all;
  }
}
```

### StickyIntersector - центральная логика

```typescript
// src/components/stickyIntersector.ts
export default class StickyIntersector {
  private headersObserver: IntersectionObserver;
  
  constructor(
    private container: HTMLElement, 
    private handler: (stuck: boolean, target: HTMLElement) => void
  ) {
    this.observeHeaders();
  }
  
  private observeHeaders() {
    this.headersObserver = new IntersectionObserver((entries) => {
      for(const entry of entries) {
        const targetInfo = entry.boundingClientRect;
        const stickyTarget = entry.target.parentElement;
        const rootBoundsInfo = entry.rootBounds;
        
        // Started sticking
        if(targetInfo.bottom < rootBoundsInfo.top) {
          this.handler(true, stickyTarget);
        }
        
        // Stopped sticking
        if(targetInfo.bottom >= rootBoundsInfo.top &&
           targetInfo.bottom < rootBoundsInfo.bottom) {
          this.handler(false, stickyTarget);
        }
      }
    }, {threshold: 0, root: this.container});
  }
  
  public observeStickyHeaderChanges(element: HTMLElement) {
    const headerSentinel = this.addSentinel(element, 'sticky_sentinel--top');
    this.headersObserver.observe(headerSentinel);
  }
}
```

### Date Formatting - централизовано

```typescript
// src/helpers/date.ts
export function formatDateAccordingToTodayNew(date: Date) {
  const today = new Date();
  const yesterday = new Date(today);
  yesterday.setDate(yesterday.getDate() - 1);

  if (date.toDateString() === today.toDateString()) return 'Сегодня';
  if (date.toDateString() === yesterday.toDateString()) return 'Вчера';

  return date.toLocaleDateString('ru-RU', { 
    day: 'numeric', 
    month: 'long', 
    year: 'numeric' 
  });
}

// Используется ВЕЗДЕ:
// - wrapSentTime (components/wrappers/sentTime.ts)
// - formatFullSentTime
// - bubbleGroups
```

---

## ❌ EUSRR - Текущие проблемы

### 1. Дублирование formatDay() - 6 копий!

| Файл | Строки | Статус |
|------|--------|--------|
| **chatUtils.js** | 84-100 | ✅ Централизованная версия |
| messageRendererV2.js | 563-577 | ❌ Копия |
| messageStoreV2.js | 501-515 | ❌ Копия |
| messageRenderer.js (deprecated) | 93-107 | ❌ Копия |
| messageStore.js (old) | 503 | ❌ Копия |
| chatMessageTemplates.js | 49-52 | ❌ ДРУГАЯ логика (DD.MM.YYYY вместо "Сегодня") |

### 2. Разбросанная логика создания dividers

**3 места создания day-divider:**

#### A. messageRendererV2.js
```javascript
// Lines 147: в prependMessages()
items.push({ type: 'day-divider', text: msgDay });

// Lines 235-250: в appendMessage()
if (msgDay !== lastMsgDay) {
    container.appendChild(this._createDayDivider(msgDay));
}

// Lines 332-340: приватный метод
_createDayDivider(text) {
    const dividerEl = document.createElement('div');
    dividerEl.className = 'day-divider text-center small text-muted my-3';
    dividerEl.innerHTML = `<span class="px-3 py-1 rounded-pill bg-light">${escapeHtml(text)}</span>`;
    return dividerEl;
}
```

#### B. messageStoreV2.js
```javascript
// Lines 324-340: getMessagesWithDividers()
// НО ИСПОЛЬЗУЕТСЯ ЛИ ОНА???
getMessagesWithDividers(chatId) {
    const messages = this.getMessagesForChat(chatId);
    const result = [];
    let lastDay = null;

    for (const message of messages) {
        const day = this._formatDay(new Date(message.created_ts));
        
        if (day !== lastDay) {
            result.push({ type: 'divider', text: day });
            lastDay = day;
        }
        
        result.push({ type: 'message', message });
    }

    return result;
}
```

#### C. messageRenderer.js (deprecated)
```javascript
// Дублирует всю логику из V2
```

### 3. Отсутствие sticky header

**У нас:**
```html
<!-- Просто divider в потоке сообщений -->
<div class="day-divider text-center small text-muted my-3">
  <span class="px-3 py-1 rounded-pill bg-light">Сегодня</span>
</div>
```

**В Telegram:**
```html
<!-- Sticky header с наблюдателем -->
<div class="bubbles-date-group">
  <div class="sticky_sentinel--top"></div>
  <div class="bubble is-date" style="position: sticky; top: 56px;">
    <div class="bubble-content">Сегодня</div>
  </div>
  <!-- messages -->
</div>
```

### 4. Дата не кликабельная

**Telegram:** При клике на дату открывается календарь для перехода к конкретной дате.

**EUSRR:** Дата - просто статичный текст.

---

## ✅ Рекомендации по централизации

### Вариант 1: Простая централизация (Quick Win)

**Шаг 1: Удалить дубликаты formatDay**

```javascript
// messageRendererV2.js
import { formatDay } from '../utils/chatUtils.js';

// Удалить:
// _formatDay(date) { ... }

// Заменить все использования:
const msgDay = formatDay(msgDate); // вместо this._formatDay(msgDate)
```

**Шаг 2: Централизовать создание divider**

```javascript
// utils/chatDividers.js (НОВЫЙ ФАЙЛ)
import { formatDay } from './chatUtils.js';
import escapeHtml from '../helpers/dom/escapeHtml.js';

export class DateDividerManager {
    /**
     * Создает элемент date divider
     */
    static createDivider(date) {
        const text = formatDay(date);
        const dividerEl = document.createElement('div');
        dividerEl.className = 'day-divider text-center small text-muted my-3';
        dividerEl.innerHTML = `<span class="px-3 py-1 rounded-pill bg-light">${escapeHtml(text)}</span>`;
        dividerEl.dataset.date = date.toISOString().split('T')[0]; // YYYY-MM-DD
        return dividerEl;
    }
    
    /**
     * Проверяет нужен ли divider между двумя сообщениями
     */
    static shouldAddDivider(prevMessage, currentMessage) {
        if (!prevMessage) return true;
        
        const prevDay = formatDay(new Date(prevMessage.created_ts));
        const currDay = formatDay(new Date(currentMessage.created_ts));
        
        return prevDay !== currDay;
    }
    
    /**
     * Находит или создает divider для массива сообщений
     */
    static insertDividers(messages) {
        const result = [];
        let lastDay = null;
        
        for (const message of messages) {
            const day = formatDay(new Date(message.created_ts));
            
            if (day !== lastDay) {
                result.push({ type: 'day-divider', text: day, date: new Date(message.created_ts) });
                lastDay = day;
            }
            
            result.push({ type: 'message', message });
        }
        
        return result;
    }
}
```

**Шаг 3: Использовать в Renderer**

```javascript
// messageRendererV2.js
import { DateDividerManager } from '../utils/chatDividers.js';

prependMessages(messages, silent = false) {
    const items = DateDividerManager.insertDividers(messages);
    
    items.forEach(item => {
        if (item.type === 'day-divider') {
            fragment.appendChild(DateDividerManager.createDivider(item.date));
        } else {
            // render message
        }
    });
}

appendMessage(message) {
    const lastMessage = container.querySelector('.msg:last-of-type');
    
    if (DateDividerManager.shouldAddDivider(lastMsgData, message)) {
        container.appendChild(DateDividerManager.createDivider(new Date(message.created_ts)));
    }
}
```

---

### Вариант 2: Telegram-style (Полная реализация)

**1. DateContainerManager - группировка по дням**

```javascript
// managers/dateContainerManager.js
export class DateContainerManager {
    constructor(scrollElement) {
        this.scrollElement = scrollElement;
        this.dateContainers = new Map(); // timestamp -> {container, groupsLength}
    }
    
    /**
     * Получает или создает контейнер для даты
     */
    getDateContainer(timestamp) {
        const date = new Date(timestamp * 1000);
        const dateTimestamp = new Date(date.getFullYear(), date.getMonth(), date.getDate()).getTime();
        
        if (!this.dateContainers.has(dateTimestamp)) {
            const container = this.createDateContainer(date, dateTimestamp);
            this.dateContainers.set(dateTimestamp, {
                container,
                groupsLength: 0,
                dateTimestamp
            });
        }
        
        return this.dateContainers.get(dateTimestamp);
    }
    
    createDateContainer(date, dateTimestamp) {
        const container = document.createElement('div');
        container.classList.add('bubbles-date-group');
        container.dataset.dateTimestamp = dateTimestamp;
        
        // Sticky date bubble
        const dateBubble = this.createStickyDateBubble(date);
        container.appendChild(dateBubble);
        
        return container;
    }
    
    createStickyDateBubble(date) {
        const bubble = document.createElement('div');
        bubble.classList.add('bubble', 'is-date');
        
        const content = document.createElement('div');
        content.classList.add('bubble-content');
        content.textContent = formatDay(date);
        
        // Кликабельность
        content.style.cursor = 'pointer';
        content.addEventListener('click', () => {
            this.onDateClick(date);
        });
        
        bubble.appendChild(content);
        return bubble;
    }
    
    onDateClick(date) {
        // Открыть календарь для перехода к дате
        // TODO: интегрировать с существующим date picker
        console.log('Navigate to date:', date);
    }
}
```

**2. StickyDateObserver - IntersectionObserver для sticky**

```javascript
// observers/stickyDateObserver.js
export class StickyDateObserver {
    constructor(scrollElement) {
        this.scrollElement = scrollElement;
        this.observer = null;
        this.activeStickyDate = null;
        this.init();
    }
    
    init() {
        this.observer = new IntersectionObserver(
            (entries) => this.handleIntersection(entries),
            {
                root: this.scrollElement,
                rootMargin: '-56px 0px 0px 0px', // offset для header
                threshold: [0, 1]
            }
        );
    }
    
    handleIntersection(entries) {
        entries.forEach(entry => {
            const dateBubble = entry.target;
            
            if (entry.isIntersecting && entry.intersectionRatio < 1) {
                // Date начала прилипать
                dateBubble.classList.add('is-sticky');
                this.activeStickyDate = dateBubble;
            } else if (!entry.isIntersecting || entry.intersectionRatio === 1) {
                // Date перестала прилипать
                dateBubble.classList.remove('is-sticky');
                
                if (this.activeStickyDate === dateBubble) {
                    this.activeStickyDate = null;
                }
            }
        });
    }
    
    observe(dateBubble) {
        this.observer.observe(dateBubble);
    }
    
    unobserve(dateBubble) {
        this.observer.unobserve(dateBubble);
    }
    
    disconnect() {
        this.observer.disconnect();
    }
}
```

**3. CSS для sticky positioning**

```css
/* static/css/components/chat-date-dividers.css */
.bubbles-date-group {
  position: relative;
}

.bubble.is-date {
  position: sticky;
  top: 56px; /* offset для chat-header */
  z-index: 2;
  padding: 8px 0;
  margin: 12px 0;
  pointer-events: none;
  transition: opacity 0.3s ease;
  opacity: 1;
}

.bubble.is-date .bubble-content {
  background: rgba(255, 255, 255, 0.9);
  backdrop-filter: blur(10px);
  border-radius: 12px;
  padding: 4px 12px;
  font-weight: 600;
  color: var(--secondary-text-color);
  cursor: pointer;
  pointer-events: all;
  box-shadow: 0 2px 4px rgba(0, 0, 0, 0.1);
  transition: background 0.2s ease;
}

.bubble.is-date .bubble-content:hover {
  background: rgba(255, 255, 255, 1);
}

/* Когда дата прилипла - скрываем оригинал */
.bubble.is-date.is-sticky {
  opacity: 0.00001; /* для Safari */
}

/* Fake date для показа во время sticky */
.bubble.is-date.is-fake {
  position: absolute;
  top: 0;
  left: 50%;
  transform: translateX(-50%);
  opacity: 1 !important;
  visibility: visible !important;
}
```

**4. Интеграция в ChatControllerV2**

```javascript
// controllers/chatControllerV2.js
import { DateContainerManager } from '../managers/dateContainerManager.js';
import { StickyDateObserver } from '../observers/stickyDateObserver.js';

constructor(options) {
    // ...existing code...
    
    this.dateContainerManager = new DateContainerManager(this.scrollElement);
    this.stickyDateObserver = new StickyDateObserver(this.scrollElement);
}

async init() {
    // ...existing init code...
    
    // Observe all date bubbles
    const dateBubbles = this.scrollElement.querySelectorAll('.bubble.is-date');
    dateBubbles.forEach(bubble => {
        this.stickyDateObserver.observe(bubble);
    });
}
```

---

## 📊 Сравнительная таблица

| Функция | EUSRR (сейчас) | Telegram Web | Приоритет |
|---------|----------------|--------------|-----------|
| **formatDay** | ✅ Есть (chatUtils) | ✅ Централизовано | 🟢 Уже есть |
| **Дублирование formatDay** | ❌ 6 копий | ✅ Одна функция | 🔴 HIGH |
| **DateDivider создание** | ❌ 3 места | ✅ Одно место | 🔴 HIGH |
| **Sticky positioning** | ❌ Нет | ✅ Есть | 🟡 MEDIUM |
| **Кликабельная дата** | ❌ Нет | ✅ Есть (календарь) | 🟡 MEDIUM |
| **IntersectionObserver** | ❌ Нет | ✅ Есть | 🟡 MEDIUM |
| **Date группировка** | ❌ Простой divider | ✅ DateContainer с группами | 🟢 LOW |

---

## 🎯 План реализации

### Phase 1: Централизация (1-2 часа) ⚡ PRIORITY

✅ **ВЫПОЛНИТЬ В ПЕРВУЮ ОЧЕРЕДЬ**

1. Создать `utils/chatDividers.js` с классом `DateDividerManager`
2. Удалить `_formatDay()` из всех файлов кроме `chatUtils.js`
3. Заменить все вызовы на `import { formatDay }`
4. Централизовать создание divider в `DateDividerManager.createDivider()`
5. Обновить `messageRendererV2.js` для использования `DateDividerManager`

### Phase 2: Sticky Header (4-6 часов) 🎨 ENHANCEMENT

1. Создать `managers/dateContainerManager.js`
2. Создать `observers/stickyDateObserver.js`
3. Добавить CSS для sticky positioning
4. Интегрировать в `ChatControllerV2`

### Phase 3: Кликабельная дата (2-3 часа) 🔧 FEATURE

1. Добавить обработчик клика на дату
2. Интегрировать с существующим date picker
3. Реализовать навигацию к выбранной дате

---

## 📝 Итоги

### Что делает Telegram правильно:

1. ✅ **Централизация** - одна функция `formatDateAccordingToTodayNew()`
2. ✅ **Sticky positioning** - дата всегда видна при скролле
3. ✅ **IntersectionObserver** - эффективное отслеживание видимости
4. ✅ **Кликабельность** - быстрый переход к дате
5. ✅ **Группировка** - BubbleGroup → DateContainer → Messages

### Что нужно исправить в EUSRR:

1. ❌ Убрать 5 копий `_formatDay()` - использовать `chatUtils.formatDay`
2. ❌ Централизовать создание divider в одном месте
3. 🟡 Добавить sticky positioning (опционально)
4. 🟡 Сделать дату кликабельной (опционально)

### Минимально необходимые изменения:

**Файлы для изменения:**
- `messageRendererV2.js` - удалить `_formatDay`, использовать `DateDividerManager`
- `messageStoreV2.js` - удалить `_formatDay`, удалить `getMessagesWithDividers` (не используется?)
- `messageRenderer.js` - deprecated, можно оставить
- `chatMessageTemplates.js` - ПЕРЕИМЕНОВАТЬ в `formatDateShort` (другая логика)

**Новые файлы:**
- `utils/chatDividers.js` - класс `DateDividerManager`

---

**Рекомендация:** Начать с **Phase 1** - централизации. Это займет 1-2 часа и решит проблему дублирования кода. **Phase 2 и 3** можно сделать позже как улучшение UX.
