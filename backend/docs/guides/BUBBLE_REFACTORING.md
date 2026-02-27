# Рефакторинг архитектуры .bubble - BEM миграция

**Дата:** 21 января 2026  
**Статус:** ✅ Завершено

## 📋 Обзор изменений

Проведен полный рефакторинг системы стилей для сообщений чата с переходом на **BEM-методологию** и **CSS-переменные**.

### Было
```scss
// Хаотичное распределение по файлам
.bubble { }
.bubble-me { }
.bubble-other { }
.msg .bubble { }
.bubble .attachment-item { }
// + использование !important
// + глубокая вложенность (4+ уровня)
// + конфликты white-space
```

### Стало
```scss
// Модульная BEM-архитектура
.bubble { }                 // Базовый блок
.bubble--me { }             // Модификатор типа
.bubble--other { }          // Модификатор типа
.bubble__content { }        // Элемент
.bubble__attachment { }     // Элемент
.bubble--pending { }        // Модификатор состояния
```

---

## 🗂️ Структура новых файлов

### 1. `_bubble-base.scss` - Базовый блок
**Назначение:** Структурные и типографские свойства без цветовой темизации

```scss
.bubble {
  display: block;
  border-radius: $radius-lg;
  padding: var(--space-1) var(--space-2);
  max-width: 70%;
  white-space: pre-line;
  
  // Темизация через CSS-переменные
  background: var(--bubble-bg);
  color: var(--bubble-text);
}
```

**Элементы:**
- `.bubble__author` - Имя автора
- `.bubble__content` - Текст сообщения
- `.bubble__edited` - Индикатор редактирования
- `.bubble__time` - Время отправки
- `.bubble__attachments` - Контейнер вложений
- `.bubble__poll` - Контейнер голосования
- `.bubble__reply-preview` - Превью ответа
- `.bubble__reactions` - Контейнер реакций

### 2. `_bubble-variants.scss` - Модификаторы типов
**Назначение:** Цветовая темизация для разных типов сообщений

**Модификаторы:**
- `.bubble--me` - Мои сообщения (синий фон)
- `.bubble--other` - Чужие сообщения (серый фон)
- `.bubble--system` - Системные сообщения (пунктирная рамка)
- `.bubble--pending` - В процессе отправки (spinner)
- `.bubble--failed` - Ошибка отправки (красная рамка)
- `.bubble--deleted` - Удалённое сообщение (зачеркнутое)

**Примеры CSS-переменных:**
```scss
.bubble--me {
  --bubble-bg: color-mix(in srgb, var(--bs-primary) 92%, #fff);
  --bubble-text: #fff;
  --bubble-attachment-bg: rgba(255, 255, 255, 0.15);
  --bubble-poll-progress-bg: rgba(255, 255, 255, 0.2);
}
```

### 3. `_bubble-content.scss` - Вложенный контент
**Назначение:** Стили для attachments, polls, media внутри bubble

**Компоненты:**
- `.bubble__attachment--media` - Изображения и видео
- `.bubble__attachment--file` - Документы с иконками
- `.bubble__attachment--audio` - Аудио-плеер
- `.bubble__poll` - Виджет голосования
- `.bubble__reactions` - Реакции пользователей
- `.bubble__link-preview` - Open Graph превью

### 4. `_bubble-states.scss` - Интерактивные состояния
**Назначение:** Hover, focus, selection, drag&drop состояния

**Компоненты:**
- `.msg__actions` - Панель действий при hover
- `.msg__quick-reactions` - Быстрые реакции при hover
- `.msg--selected` - Выделенное сообщение
- `.msg--selectable` - Режим множественного выделения
- `.msg--dragging` - В процессе перетаскивания

---

## 🔄 Таблица миграции классов

### HTML классы

| Старый класс | Новый класс | Комментарий |
|-------------|-------------|-------------|
| `.bubble` | `.bubble` | Базовый класс остался |
| `.bubble-me` | `.bubble--me` | BEM модификатор |
| `.bubble-other` | `.bubble--other` | BEM модификатор |
| `.message-author` | `.bubble__author` | BEM элемент |
| `.message-content` | `.bubble__content` | BEM элемент |
| `.edited-indicator` | `.bubble__edited` | BEM элемент |
| `.message-time` | `.bubble__time` | BEM элемент |
| `.message-attachments` | `.bubble__attachments` | BEM элемент |
| `.attachment-item` | `.bubble__attachment` | BEM элемент |
| `.message-reply-preview` | `.bubble__reply-preview` | BEM элемент |
| `.message-reactions` | `.bubble__reactions` | BEM элемент |
| `.message-actions` | `.msg__actions` | Изменен контекст |
| `.quick-reactions` | `.msg__quick-reactions` | Изменен контекст |
| `.msg.new` | `.bubble--animating` | BEM модификатор |
| `.message-pending` | `.bubble--pending` | BEM модификатор |
| `.message-failed` | `.bubble--failed` | BEM модификатор |

### JavaScript селекторы

| Старый селектор | Новый селектор |
|----------------|---------------|
| `.querySelector('.bubble')` | `.querySelector('.bubble')` |
| `.classList.add('bubble-me')` | `.classList.add('bubble--me')` |
| `.querySelector('.message-content')` | `.querySelector('.bubble__content')` |
| `.querySelector('.message-attachments')` | `.querySelector('.bubble__attachments')` |

---

## 🛠️ Измененные файлы

### Созданы новые файлы
✅ `backend/static/scss/components/chat/_bubble-base.scss` (180 строк)  
✅ `backend/static/scss/components/chat/_bubble-variants.scss` (150 строк)  
✅ `backend/static/scss/components/chat/_bubble-content.scss` (220 строк)  
✅ `backend/static/scss/components/chat/_bubble-states.scss` (210 строк)

### Обновлены существующие файлы
✅ `backend/static/scss/custom-bootstrap.scss` - добавлены импорты  
✅ `backend/static/scss/components/chat/_chat-enhanced.scss` - удалены дубликаты  
✅ `backend/static/js/renderers/messageRendererV2.js` - BEM классы в рендерере

### Требуют обновления
⚠️ `backend/static/scss/components/chat/_chat-detail.scss` - удалить старые стили bubble (строки 772-810, 287-360, 412-430, 490-505)  
⚠️ `backend/static/scss/components/chat/_chat-polls.scss` - использовать CSS-переменные вместо .bubble-me/.bubble-other

---

## 🎯 Преимущества новой архитектуры

### 1. Модульность
- Каждый аспект в отдельном файле
- Легко найти и изменить стили
- Простое добавление новых модификаторов

### 2. Переиспользуемость
```scss
// Добавить новый тип сообщения - 5 строк
.bubble--draft {
  --bubble-bg: #fffbeb;
  --bubble-text: #92400e;
}
```

### 3. Производительность
- Без `!important` - меньше специфичности
- CSS-переменные вычисляются браузером
- Уменьшен размер итогового CSS (меньше дублирования)

### 4. Поддерживаемость
```scss
// ❌ Было (специфичность 0,0,4,0)
.bubble-me .message-attachments .text-secondary {
  color: #fff !important;
}

// ✅ Стало (специфичность 0,0,1,0)
.bubble__attachment-meta {
  color: var(--bubble-attachment-meta);
}
```

### 5. Темизация
Легко добавить темную тему или корпоративные цвета:
```scss
[data-theme="dark"] {
  .bubble--me {
    --bubble-bg: #1e3a8a;
  }
  .bubble--other {
    --bubble-bg: #1f2937;
  }
}
```

---

## 📝 Рекомендации по использованию

### Создание сообщения в JavaScript
```javascript
// ✅ Правильно
const bubbleModifier = isOwn ? 'bubble--me' : 'bubble--other';
const html = `
  <div class="bubble ${bubbleModifier}">
    <div class="bubble__author">
      <a href="${authorUrl}">${authorName}</a>
    </div>
    <div class="bubble__content">${content}</div>
    <div class="bubble__time">${time}</div>
  </div>
`;
```

### Добавление нового состояния
```scss
// _bubble-variants.scss
.bubble--forwarded {
  --bubble-bg: #f0f9ff;
  border-left: 4px solid var(--bs-info);
}
```

### Стилизация вложений
```scss
// _bubble-content.scss
.bubble__attachment--video {
  video {
    max-width: 400px;
    border-radius: $radius-md;
  }
}
```

---

## ⚠️ Breaking Changes

### JavaScript
Необходимо обновить селекторы в следующих файлах:
- `backend/static/js/components/chatMarkRead.js`
- `backend/static/js/components/chatMessageTemplates.js`
- `backend/static/js/renderers/messageRendererV2.js` ✅ Обновлено

### SCSS
Если есть кастомные стили, использующие:
- `.bubble-me` → заменить на `.bubble--me`
- `.bubble-other` → заменить на `.bubble--other`
- `.message-attachments` → заменить на `.bubble__attachments`

---

## 🧪 Тестирование

### Чек-лист после миграции
- [ ] Отображение своих сообщений (синий фон)
- [ ] Отображение чужих сообщений (серый фон)
- [ ] Системные сообщения по центру
- [ ] Вложения (изображения, файлы, аудио)
- [ ] Голосования внутри сообщений
- [ ] Реакции под сообщениями
- [ ] Reply preview кликабелен
- [ ] Hover actions появляются
- [ ] Mobile responsive (кнопки всегда видны)
- [ ] Анимация новых сообщений
- [ ] Pending состояние (spinner)
- [ ] Failed состояние (warning icon)
- [ ] Выделение сообщений (selection mode)

### Команда для проверки SCSS компиляции
```bash
cd backend/static
sass scss/custom-bootstrap.scss:css/custom-bootstrap.css --no-source-map
```

### Тестовые сценарии
1. Отправить сообщение
2. Ответить на сообщение (reply)
3. Прикрепить файл
4. Создать голосование
5. Добавить реакцию
6. Открыть на мобильном устройстве

---

## 🔮 Дальнейшие улучшения

### Краткосрочные (1-2 недели)
1. Обновить `_chat-detail.scss` - удалить старые стили bubble
2. Обновить `_chat-polls.scss` - использовать CSS-переменные
3. Обновить остальные JS файлы с селекторами bubble
4. Добавить unit-тесты для CSS классов

### Среднесрочные (1-2 месяца)
1. Добавить темную тему через CSS-переменные
2. Создать Storybook для bubble компонентов
3. Оптимизировать анимации для low-end устройств
4. Добавить accessibility тесты

### Долгосрочные (3+ месяца)
1. Перенести на CSS Container Queries для адаптивности
2. Использовать CSS Cascade Layers для изоляции
3. Добавить View Transitions API для анимаций
4. Создать дизайн-систему на основе bubble

---

## 📚 Дополнительные ресурсы

- [BEM Methodology](https://en.bem.info/methodology/)
- [CSS Variables (MDN)](https://developer.mozilla.org/en-US/docs/Web/CSS/Using_CSS_custom_properties)
- [SCSS Best Practices](https://sass-guidelin.es/)

---

**Автор:** GitHub Copilot  
**Дата создания:** 21 января 2026  
**Версия:** 1.0
