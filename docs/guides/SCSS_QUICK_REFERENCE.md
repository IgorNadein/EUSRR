# SCSS Quick Reference - EUSRR Project

## 🚀 Быстрый старт

### Компиляция SCSS

```bash
# Перейти в директорию со статикой
cd backend/static

# Собрать app.css (один раз)
npm run build:app

# Watch режим (автоматическая пересборка при изменении)
npm run dev
```

### Добавление нового компонента

1. **Создать файл** `scss/components/_my-component.scss`
2. **Добавить импорт** в `scss/main.scss`:
   ```scss
   @import 'components/my-component';
   ```
3. **Пересобрать** CSS: `npm run build:app`

## 📁 Структура

```
scss/
├── main.scss                    ← ENTRY POINT
├── abstracts/
│   ├── _variables.scss          ← SCSS переменные ($var)
│   ├── _css-variables.scss      ← CSS переменные (--var)
│   └── _mixins.scss             ← Миксины
├── layout/
│   └── _base-app.scss           ← Grid layout
└── components/
    └── _*.scss                  ← 30 компонентов
```

## 🎨 Использование переменных

### CSS Custom Properties (runtime)

```scss
.my-component {
  padding: var(--space-2);        // 8px
  gap: var(--layout-gap);         // 16px
  border-radius: var(--card-radius);
}
```

### Доступные CSS переменные

#### Spacing (8px grid):
```scss
--space-1: 4px    // минимальный отступ
--space-2: 8px    // стандартный
--space-3: 12px   // между секциями
--space-4: 16px   // между блоками
--space-5: 24px   // большой разделитель
```

#### Layout:
```scss
--navbar-h: 60px
--sidebar-w: 200px
--rightbar-w: 350px
--layout-gap: 16px
--layout-padding-y: 24px
```

#### Components:
```scss
--card-padding: 16px
--card-padding-sm: 8px
--card-padding-lg: 24px
--card-radius: 14px
--feed-radius: 18px
```

## 📝 Код стайл

### Вложенность

```scss
.card {
  padding: var(--card-padding);
  
  .card-header {
    background: var(--bs-tertiary-bg);
  }
  
  .card-body {
    padding: var(--space-3);
  }
}
```

### Родительский селектор (&)

```scss
.button {
  background: var(--bs-primary);
  
  &:hover {
    opacity: 0.9;
  }
  
  &--large {
    padding: var(--space-4);
  }
}
```

### Media queries

```scss
.component {
  display: block;
  
  @media (min-width: 768px) {
    display: flex;
  }
}
```

## ⚙️ Кастомизация Bootstrap

Файл: `scss/custom-bootstrap.scss`

```scss
// Переопределить переменные Bootstrap
$primary: #0d6efd;
$spacer: 0.5rem;  // 8px

// Spacers (8px grid)
$spacers: (
  0: 0,
  1: 0.25rem,  // 4px
  2: 0.5rem,   // 8px
  3: 0.75rem,  // 12px
  4: 1rem,     // 16px
  5: 1.5rem,   // 24px
);
```

## 🛠️ Полезные команды

```bash
# Собрать app.css
npm run build:app

# Собрать bootstrap-custom.css
npm run build:bootstrap

# Watch режим (оба файла)
npm run dev

# Проверить размер
ls -lh css/app.css
```

## 🎯 Частые задачи

### Добавить spacing между элементами

```scss
.container {
  display: flex;
  gap: var(--space-2);  // 8px между элементами
}
```

### Создать адаптивный компонент

```scss
.responsive-card {
  padding: var(--space-2);  // 8px на мобильных
  
  @media (min-width: 768px) {
    padding: var(--space-3);  // 12px на планшетах
  }
  
  @media (min-width: 992px) {
    padding: var(--space-4);  // 16px на десктопе
  }
}
```

### Использовать цвета Bootstrap

```scss
.element {
  color: var(--bs-primary);
  background: var(--bs-secondary);
  border-color: var(--bs-border-color);
}
```

## 📦 Что включено в app.css

- ✅ Все 30 SCSS компонентов
- ✅ CSS Custom Properties
- ✅ Layout системы (grid, chat)
- ✅ Utility классы spacing
- ✅ Responsive стили

**Размер:** 95 KB compressed

## ⚠️ Важно

1. **Не создавать новые CSS файлы** - только SCSS в `scss/` папке
2. **Всегда добавлять импорт** в `main.scss` для новых компонентов
3. **Использовать CSS переменные** вместо хардкода значений
4. **Пересобирать** после изменений: `npm run build:app`

## 📚 Документация

- **Полная документация:** [docs/completed/CSS_TO_SCSS_MIGRATION_100_PERCENT_COMPLETE.md](../completed/CSS_TO_SCSS_MIGRATION_100_PERCENT_COMPLETE.md)
- **Phase 6 отчет:** [docs/reports/CSS_TO_SCSS_PHASE6_FINAL_CLEANUP.md](../reports/CSS_TO_SCSS_PHASE6_FINAL_CLEANUP.md)

---

**Обновлено:** 15 января 2026  
**Версия:** 1.0
