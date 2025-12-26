# Рефакторинг системы рендеринга сообщений

## Дата: 4 декабря 2025 г.

## Проблема

Система рендеринга сообщений имела дублирование кода:
- `messageRenderer.js` - рендерил новые сообщения через WebSocket
- `chatMessageTemplates.js` - рендерил старые сообщения при скролле вверх

Оба файла содержали:
1. **Многострочные HTML-шаблоны** с переносами строк и отступами
2. **Дублирующуюся логику** для формирования HTML
3. **Разные подходы** к обработке данных

### Симптомы
- Пилюли сообщений растягивались по высоте из-за whitespace в HTML
- `white-space: pre-line` сохранял переносы из исходного кода JavaScript
- Различное отображение сообщений в зависимости от способа загрузки

## Решение

### 1. Единый источник правды
**messageRenderer.js** стал единственным местом генерации HTML:

```javascript
export class MessageRenderer {
    // Полный HTML с обёрткой .msg для WebSocket
    buildMessageHtml(msg, isOwn) {
        return `<div class="d-flex mb-3 msg...">${this.buildMessageInnerHtml(msg, isOwn)}</div>`;
    }

    // Внутренний HTML без обёртки для DOM-элементов
    buildMessageInnerHtml(msg, isOwn) {
        // Все шаблоны в одну строку без переносов
        return `${avatarHtml}<div class="d-flex flex-column">...</div>${rightAvatarHtml}`;
    }
}
```

### 2. Обёртка в chatMessageTemplates.js
**chatMessageTemplates.js** теперь использует MessageRenderer:

```javascript
import { MessageRenderer } from './messageRenderer.js';

export function createMessageElement(msg, options = {}) {
    const renderer = new MessageRenderer({
        meId: options.meId,
        profileUrl: options.profileUrl,
        detailUrlTemplate: options.detailUrlTemplate,
        currentUserAvatar: options.avatarMap[options.meId]
    });

    const wrap = document.createElement('div');
    // Настройка атрибутов wrap...
    
    // Используем единый рендерер
    wrap.innerHTML = renderer.buildMessageInnerHtml(enrichedMsg, mine);
    
    return wrap;
}
```

### 3. Устранение многострочных шаблонов

**ДО:**
```javascript
const forwardedHtml = msg.is_forwarded ? `
    <div class="forwarded-indicator small mb-2">
        <i class="bi-arrow-90deg-right me-2"></i>
        <div>
            <div>Переслано от <strong>${author}</strong></div>
        </div>
    </div>` : '';
```

**ПОСЛЕ:**
```javascript
const forwardedHtml = msg.is_forwarded ? `<div class="forwarded-indicator small mb-2 d-flex align-items-center"><i class="bi-arrow-90deg-right me-2"></i><div><div>Переслано от <strong>${msg.forwarded_from.author_name || 'Пользователя'}</strong>${msg.forwarded_from.chat_name ? ` из «${msg.forwarded_from.chat_name}»` : ''}</div>${msg.forwarded_from.created_at ? `<div class="small opacity-75">${msg.forwarded_from.created_at}</div>` : ''}</div></div>` : '';
```

### 4. Рефакторинг всех компонентов

Применено ко всем HTML-генераторам:
- ✅ `forwardedHtml` - информация о пересылке
- ✅ `replyHtml` - цитата ответа
- ✅ `avatarHtml` - аватары пользователей
- ✅ `rightAvatarHtml` - аватар справа (свои сообщения)
- ✅ `attachmentsHtml` - вложения (изображения, файлы)
- ✅ `pollHtml` - голосования/опросы
- ✅ `bubble` - основной контейнер сообщения

## Архитектура после рефакторинга

```
┌──────────────────────────────────────────────────┐
│          messageRenderer.js                      │
│                                                  │
│  ┌─────────────────────────────────────────┐    │
│  │  buildMessageHtml(msg, isOwn)           │    │
│  │  → Полный HTML с обёрткой .msg          │    │
│  │  → Используется для WebSocket           │    │
│  └─────────────────────────────────────────┘    │
│                      │                           │
│                      ▼                           │
│  ┌─────────────────────────────────────────┐    │
│  │  buildMessageInnerHtml(msg, isOwn)      │◄───┼─── Единый источник
│  │  → HTML без обёртки .msg                │    │    правды для всех
│  │  → Все шаблоны в одну строку            │    │    HTML-шаблонов
│  │  → Нет whitespace из исходного кода     │    │
│  └─────────────────────────────────────────┘    │
│           │           │           │              │
│           ▼           ▼           ▼              │
│  buildAttachmentHtml  buildPollHtml  ...        │
└──────────────────────────────────────────────────┘
                       ▲
                       │
                       │ import & использование
                       │
┌──────────────────────────────────────────────────┐
│      chatMessageTemplates.js                     │
│                                                  │
│  createMessageElement(msg, options)              │
│  → Создаёт DOM элемент                           │
│  → Использует MessageRenderer.buildMessageInnerHtml │
│  → Добавляет pending статус если нужно           │
└──────────────────────────────────────────────────┘
                       ▲
                       │
                       │ использование
                       │
┌──────────────────────────────────────────────────┐
│      chatHistoryLoader.js                        │
│                                                  │
│  prependMessages() → createMessageElement()      │
│  → Загрузка старых сообщений при скролле вверх   │
└──────────────────────────────────────────────────┘
```

## Поток данных

### WebSocket (новые сообщения)
```
WebSocket event
    ↓
chatDetail.js
    ↓
messageRenderer.buildMessageHtml()
    ↓
insertAdjacentHTML()
    ↓
DOM
```

### HTTP + Скролл (старые сообщения)
```
Scroll вверх
    ↓
chatHistoryLoader.loadMore()
    ↓
fetch(/api/messages?before_id=...)
    ↓
chatMessageTemplates.createMessageElement()
    ↓
    → MessageRenderer.buildMessageInnerHtml()
    ↓
DOM element
    ↓
insertBefore()
```

## Преимущества рефакторинга

### ✅ Единообразие
- Одинаковый HTML независимо от способа загрузки
- Нет расхождений между WebSocket и HTTP
- Единая логика обработки всех компонентов (ответы, вложения, опросы)

### ✅ Производительность
- Нет лишних whitespace в HTML
- Компактные пилюли сообщений
- Правильная работа `white-space: pre-line` (сохраняет только `\n` из контента)

### ✅ Поддерживаемость
- DRY (Don't Repeat Yourself)
- Одно место для изменений
- Легче тестировать и дебажить

### ✅ Расширяемость
- Новые типы вложений добавляются в одном месте
- Новые поля сообщений обрабатываются единообразно

## CSS изменения

### _chat-detail.scss
```scss
.bubble {
  border-radius: 16px;
  padding: var(--space-1) var(--space-2);
  word-break: break-word;
  white-space: pre-line; /* Сохраняет \n из контента, схлопывает пробелы из HTML */
  box-shadow: 0 1px 2px rgba(0, 0, 0, 0.06);
  
  > div {
    white-space: inherit; /* Наследование для вложенных элементов */
  }
}
```

## Тестирование

После рефакторинга проверить:
1. ✅ Переносы строк (`\n`) отображаются корректно
2. ✅ Высота пилюль соответствует контенту (без растягивания)
3. ✅ Сообщения с 1 символом компактные
4. ✅ Старые сообщения (скролл вверх) выглядят так же как новые (WebSocket)
5. ✅ Сообщения с вложениями, опросами, ответами не имеют лишних отступов
6. ✅ Аватары отображаются корректно
7. ✅ Реакции работают
8. ✅ Редактирование сообщений работает

## Совместимость

### Обратная совместимость
- ✅ Все существующие функции сохранены
- ✅ API не изменился
- ✅ DOM-структура осталась прежней
- ✅ CSS-классы не изменились

### Зависимости
```javascript
// messageRenderer.js
export class MessageRenderer { ... }
export function createMessageRenderer(config) { ... }

// chatMessageTemplates.js
import { MessageRenderer } from './messageRenderer.js';
import { esc } from '../utils/stringUtils.js';

// chatHistoryLoader.js
import { createMessageElement } from './chatMessageTemplates.js';
```

## Следующие шаги

1. **Тестирование** - проверить все сценарии использования
2. **Мониторинг** - отследить производительность в production
3. **Документация** - обновить комментарии в коде
4. **Оптимизация** - возможно кеширование MessageRenderer
5. **Расширение** - добавить поддержку новых типов контента

## Файлы изменены

- ✅ `backend/static/js/components/messageRenderer.js`
  - Добавлен метод `buildMessageInnerHtml()`
  - Все шаблоны переведены в одну строку
  - Добавлена поддержка параметра `meId`
  
- ✅ `backend/static/js/components/chatMessageTemplates.js`
  - Переписан `createMessageElement()` для использования MessageRenderer
  - Удалён дублирующийся код генерации HTML
  - Сохранена обратная совместимость API

- ✅ `backend/static/scss/components/_chat-detail.scss`
  - Изменён `white-space: pre-wrap` → `pre-line`
  - Добавлено правило наследования для вложенных `div`

## Авторы

- Рефакторинг: GitHub Copilot + Igor
- Дата: 4 декабря 2025 г.
