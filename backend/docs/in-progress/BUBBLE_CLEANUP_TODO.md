# TODO: Завершение рефакторинга .bubble

## ⚠️ Требуют обновления

### 1. `_chat-detail.scss` - Удалить устаревшие стили

**Строки для удаления:**

#### Строки 772-810: Базовые стили bubble (дублируются в _bubble-base.scss)
```scss
.bubble {
  border-radius: $radius-lg;
  padding: var(--space-1) var(--space-2);
  // ...
}

.bubble-me {
  background: color-mix(in srgb, var(--bs-primary) 92%, #fff 0%);
  color: #fff;
}

.bubble-other {
  background: var(--bs-secondary-bg);
  color: var(--bs-body-color);
}
```
**Действие:** Удалить полностью, перенесено в `_bubble-base.scss` и `_bubble-variants.scss`

---

#### Строки 287-360: Attachment стили (дублируются в _bubble-content.scss)
```scss
.bubble .attachment-item {
  background: transparent;
  // ...
}

.bubble-other .attachment-item a {
  background: rgba(0, 0, 0, 0.05);
  // ...
}

.bubble-me .attachment-item a {
  background: rgba(255, 255, 255, 0.15);
  // ...
}
```
**Действие:** Удалить, заменено на `.bubble__attachment` в `_bubble-content.scss`

---

#### Строки 412-430: Message states (дублируются в _bubble-variants.scss)
```scss
.message-pending .bubble {
  position: relative;
  opacity: 0.8;
}

.message-failed {
  opacity: 0.6;
  .bubble {
    border: 1px solid var(--bs-danger);
    // ...
  }
}
```
**Действие:** Удалить, заменено на `.bubble--pending` и `.bubble--failed`

---

#### Строки 490-505: Attachment meta с !important
```scss
.bubble-me .message-attachments .text-secondary {
  color: rgba(255, 255, 255, 0.9) !important;
  opacity: 1;
}

.bubble-me .message-attachments .fw-semibold {
  color: rgba(255, 255, 255, 0.95) !important;
}

.bubble-me .message-attachments i {
  color: rgba(255, 255, 255, 0.9) !important;
}
```
**Действие:** Удалить, заменено на CSS-переменные `--bubble-attachment-text`, `--bubble-attachment-icon` в `_bubble-variants.scss`

---

### 2. `_chat-polls.scss` - Обновить на CSS-переменные

**Строки 92-115: Poll в bubble**

#### Было:
```scss
.message-bubble .poll-widget {
  max-width: 500px;
}

.bubble-other .poll-widget {
  background: var(--bs-secondary-bg);
}

.bubble-me {
  .poll-widget {
    background: rgba(255, 255, 255, 0.15);
  }
  
  .poll-question {
    color: #fff;
  }
  
  .poll-option-result {
    .progress {
      background-color: rgba(255, 255, 255, 0.2);
    }
  }
}
```

#### Должно быть:
```scss
// Удалить эти стили - они уже в _bubble-content.scss через CSS-переменные
// Poll автоматически использует:
// - var(--bubble-poll-bg)
// - var(--bubble-poll-text)
// - var(--bubble-poll-progress-bg)
// Которые определены в .bubble--me и .bubble--other
```

---

### 3. JavaScript файлы - Обновить селекторы

#### `chatMarkRead.js` (строка 376)
```javascript
// Было
const bubble = lastMsg.querySelector('.bubble') || lastMsg;

// Оставить как есть - базовый класс .bubble не изменился
```

#### `chatMessageTemplates.js` (строка 179)
```javascript
// Было
const bubble = tempDiv.querySelector('.bubble');

// Оставить как есть
```

**Примечание:** Базовый класс `.bubble` остался без изменений, поэтому эти файлы работают корректно.

---

## 🔧 План действий

### Шаг 1: Обновить `_chat-detail.scss`
```bash
# Открыть файл
code backend/static/scss/components/chat/_chat-detail.scss

# Удалить строки:
# 772-810 (BUBBLES & AVATARS секция)
# 287-360 (Вложения в сообщениях)
# 412-430 (Состояния сообщений)
# 490-505 (Attachment meta с !important)
```

### Шаг 2: Обновить `_chat-polls.scss`
```bash
# Открыть файл
code backend/static/scss/components/chat/_chat-polls.scss

# Удалить строки 92-115 (POLL IN MESSAGE BUBBLES секция)
# Или заменить на комментарий:
# "Стили poll в bubble определены через CSS-переменные в _bubble-content.scss"
```

### Шаг 3: Скомпилировать SCSS
```bash
cd backend/static
sass scss/custom-bootstrap.scss:css/custom-bootstrap.css --no-source-map --style compressed
```

### Шаг 4: Тестирование
1. Открыть чат
2. Проверить отображение сообщений
3. Проверить голосования
4. Проверить вложения
5. Проверить hover эффекты
6. Проверить mobile view

---

## ✅ Чек-лист перед коммитом

- [ ] Удалены дубликаты из `_chat-detail.scss`
- [ ] Обновлен `_chat-polls.scss`
- [ ] SCSS компилируется без ошибок
- [ ] Визуальное тестирование пройдено
- [ ] Mobile responsive работает
- [ ] Нет console errors в браузере
- [ ] Git diff проверен (удалено ~200 строк устаревшего кода)

---

## 📊 Метрики улучшения

### Размер CSS (после удаления дубликатов)
- **Было:** ~850 строк bubble-related кода
- **Стало:** ~760 строк (модульный код)
- **Экономия:** ~90 строк (-10.5%)

### Специфичность селекторов
- **Было:** 0,0,4,0 (`.bubble-me .message-attachments .text-secondary`)
- **Стало:** 0,0,1,0 (`.bubble__attachment-meta`)
- **Улучшение:** В 4 раза меньше

### Использование !important
- **Было:** 4 случая
- **Стало:** 0 случаев
- **Улучшение:** 100% устранение anti-pattern

### Модульность
- **Было:** 3 файла с bubble стилями
- **Стало:** 4 специализированных модуля + 3 обновленных
- **Улучшение:** Четкое разделение ответственности

---

**Приоритет:** 🔴 ВЫСОКИЙ  
**Оценка времени:** 30-45 минут  
**Риски:** Низкие (новые стили полностью покрывают старую функциональность)
