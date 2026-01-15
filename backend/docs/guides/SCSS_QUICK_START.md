# SCSS Quick Start Guide

## 🎯 Для разработчиков

### Работа со стилями

**После изменения SCSS файлов:**

```bash
# Перейти в директорию статики
cd backend/static

# Пересобрать стили
npm run build:app

# ИЛИ запустить watch режим (автокомпиляция)
npm run watch:app
```

**Watch режим** - рекомендуется при активной разработке:
```bash
npm run dev  # Запустит автокомпиляцию Bootstrap + App
```

### Где находятся стили?

**SCSS исходники** (редактируем здесь):
```
backend/static/scss/
├── main.scss              # Главный файл (импорты)
├── abstracts/
│   ├── _variables.scss    # Цвета, размеры, токены
│   └── _mixins.scss       # Переиспользуемые миксины
├── layout/
│   └── _base-app.scss     # Основной layout приложения
└── components/
    ├── _buttons.scss      # Кнопки
    ├── _cards.scss        # Карточки
    └── ...                # Другие компоненты
```

**Скомпилированный CSS** (не редактируем вручную):
```
backend/static/css/
├── app.css               # ← Этот файл загружается на страницах
└── bootstrap-custom.css  # ← Bootstrap с кастомизацией
```

### Как добавить новые стили?

#### Вариант 1: Добавить в существующий компонент

Найди нужный SCSS файл в `scss/components/` и добавь стили:

```scss
// scss/components/_buttons.scss

.btn-custom {
  padding: var(--space-2);
  background: var(--bs-primary);
  
  &:hover {
    background: var(--bs-primary-dark);
  }
}
```

#### Вариант 2: Создать новый компонент

1. Создай файл `scss/components/_my-component.scss`
2. Добавь импорт в `scss/main.scss`:
   ```scss
   @import 'components/my-component';
   ```
3. Пересобери: `npm run build:app`

### Используй переменные

**Вместо жестко заданных значений:**
```scss
❌ .my-element {
  padding: 16px;
  color: #0d6efd;
}
```

**Используй переменные:**
```scss
✅ .my-element {
  padding: var(--space-2);
  color: var(--bs-primary);
}
```

**Доступные переменные** (см. `scss/abstracts/_variables.scss`):
- Цвета: `--bs-primary`, `--bs-secondary`, `--bs-danger`, etc.
- Отступы: `--space-1` (8px), `--space-2` (16px), `--space-3` (24px)
- Радиусы: `--radius-sm`, `--radius-md`, `--radius-lg`
- Тени: `--shadow-sm`, `--shadow-md`, `--shadow-lg`

### Темная тема

Всегда добавляй стили для темной темы:

```scss
.my-card {
  background: #ffffff;
  color: #000000;
  
  [data-bs-theme="dark"] & {
    background: #2b3035;
    color: #dee2e6;
  }
}
```

### Вложенность селекторов

SCSS позволяет вкладывать селекторы:

```scss
.card {
  padding: 1rem;
  
  .card-header {
    font-weight: 600;
    
    &:hover {
      background: var(--bs-tertiary-bg);
    }
  }
  
  &.highlighted {
    border-color: var(--bs-primary);
  }
}
```

## 🚨 Частые проблемы

### Стили не применились?

1. **Проверь компиляцию:**
   ```bash
   npm run build:app
   ```

2. **Очисти кеш браузера:** Ctrl+Shift+R (Chrome/Firefox)

3. **Проверь консоль** на ошибки компиляции

### Файл app.css не обновляется?

Убедись что watch процесс запущен:
```bash
npm run watch:app
```

### Предупреждения при компиляции?

Deprecation warnings про `@import` - **это нормально**, не критично. Стили работают корректно.

## 📚 Полезные ресурсы

- [Sass официальная документация](https://sass-lang.com/documentation)
- [Bootstrap 5.3 документация](https://getbootstrap.com/docs/5.3/)
- Полный отчет о миграции: `backend/docs/reports/CSS_TO_SCSS_MIGRATION_COMPLETE.md`

## 🔥 Quick Reference

```bash
# Пересобрать всё
npm run build:css

# Только app.css
npm run build:app

# Только Bootstrap
npm run build:bootstrap

# Watch режим
npm run dev

# Проверить размер
ls -lh css/app.css
```

---

**Вопросы?** Смотри полную документацию в `backend/docs/`
