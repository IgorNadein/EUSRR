# SCSS Architecture Naming Conventions

## 📁 Структура папок

```
scss/
├── abstracts/          # Design tokens, mixins, functions
│   ├── _index.scss     # Центральный импорт
│   ├── _variables.scss # Design tokens
│   └── _mixins.scss    # Reusable patterns
├── layout/             # Глобальные структуры страниц
│   └── _chat-layout.scss
├── components/         # UI компоненты
│   ├── _badges.scss    # (было _badges-telegram-style.scss)
│   ├── _cards.scss
│   ├── _navbar.scss
│   ├── _sidebar.scss
│   └── chat/           # Подпапка для чат-компонентов
│       ├── _chat-detail.scss
│       ├── _chat-list.scss
│       ├── _chat-message.scss
│       └── _chat-polls.scss
├── utilities/          # Helper классы
└── custom-bootstrap.scss  # Entry point
```

## 🎯 Соглашения об именовании

### Файлы

**Правило:** `_[prefix]-[component].scss`

✅ **Хорошо:**
- `_badges.scss` (короткое, понятное)
- `_chat-detail.scss` (prefix + component)
- `_message-inputs.scss` (понятная семантика)

❌ **Плохо:**
- `_badges-telegram-style.scss` (слишком длинное)
- `_chat-new-messages-indicator.scss` (слишком специфичное)

### Классы компонентов

**Правило:** BEM (Block Element Modifier)

**Структура:**
```scss
.block {}              // Компонент
.block__element {}     // Элемент внутри блока
.block--modifier {}    // Модификация блока
.block__element--modifier {} // Модификация элемента
```

**Примеры:**

✅ **Правильно:**
```scss
// Badge компонент
.badge {}
.badge--sm {}          // Модификатор размера
.badge--primary {}     // Модификатор цвета
.badge__icon {}        // Элемент внутри badge

// Chat компонент
.chat {}
.chat__header {}
.chat__message {}
.chat__message--mine {}
.chat__avatar {}
```

❌ **Неправильно:**
```scss
.badge-telegram {}      // Не добавляй vendor/tech префиксы
.badge-telegram-sm {}   // Используй --sm
.chat-row {}           // Используй .chat__item
.chatAvatar {}         // camelCase недопустим
```

### Utility классы

**Правило:** Префикс `u-` для универсальных утилит

```scss
.u-hidden {}           // Utility
.u-text-truncate {}
.u-flex-center {}
```

### State классы

**Правило:** Префикс `is-` или `has-`

```scss
.is-active {}
.is-disabled {}
.is-loading {}
.has-error {}
.has-badge {}
```

## 📦 Организация кода в файле

**Структура SCSS файла:**

```scss
// 1. Header comment
// 2. Imports (если нужны локальные)
// 3. Variables (локальные, если есть)
// 4. Base component
// 5. Elements (__element)
// 6. Modifiers (--modifier)
// 7. States (.is-*, .has-*)
// 8. Responsive (@include mobile {})
// 9. Dark mode (@include dark-mode {})
```

**Пример:**

```scss
// =============================================================================
// Badges Component
// =============================================================================
// Telegram-style notification badges

// =============================================================================
// 1. BASE COMPONENT
// =============================================================================
.badge {
  @include badge-base();
  // styles
}

// =============================================================================
// 2. ELEMENTS
// =============================================================================
.badge__icon {
  // styles
}

// =============================================================================
// 3. MODIFIERS - SIZE
// =============================================================================
.badge--sm {
  @include badge-base($badge-height-sm);
}

.badge--lg {
  @include badge-base($badge-height-lg);
}

// =============================================================================
// 4. MODIFIERS - COLOR
// =============================================================================
.badge--primary {
  background: var(--bs-primary);
}

// =============================================================================
// 5. STATES
// =============================================================================
.badge.is-hidden {
  display: none;
}

// =============================================================================
// 6. RESPONSIVE
// =============================================================================
@include mobile() {
  .badge {
    font-size: $font-size-xs;
  }
}

// =============================================================================
// 7. DARK MODE
// =============================================================================
[data-bs-theme="dark"] {
  .badge {
    box-shadow: $badge-shadow-dark;
  }
}
```

## 🔧 Использование Design Tokens

**Всегда используй:**

❌ **Неправильно:**
```scss
.badge {
  border-radius: 10px;
  box-shadow: 0 2px 4px rgba(0,0,0,0.15);
  background: #0088cc;
}
```

✅ **Правильно:**
```scss
.badge {
  @include radius($radius-md);
  @include shadow($shadow-md);
  background: $telegram-blue;
}
```

## 📝 Миграция существующих классов

### Badges
```scss
// Старый код
.badge-telegram {}
.badge-telegram-sm {}
.badge-telegram-primary {}

// Новый код
.badge {}
.badge--sm {}
.badge--primary {}
```

### Chat
```scss
// Старый код
.chat-row {}
.chat-section {}
.chat-avatar {}

// Новый код
.chat__item {}
.chat__section {}
.chat__avatar {}
```

### Cards
```scss
// Старый код
.card.compact {}
.card.highlighted {}

// Новый код
.card--compact {}
.card--highlighted {}
```

## 🚀 План миграции

1. ✅ Создать `abstracts/` с design tokens
2. ✅ Создать `layout/` для глобальных структур
3. ⏳ Переименовать файлы для краткости
4. ⏳ Рефакторинг классов в BEM
5. ⏳ Применить design tokens ко всем компонентам
6. ⏳ Создать подпапку `components/chat/`
7. ⏳ Обновить импорты в custom-bootstrap.scss
