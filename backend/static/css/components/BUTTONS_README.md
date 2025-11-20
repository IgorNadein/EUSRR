# Документация: Компонент Buttons

## Обзор

Расширенная система кнопок, дополняющая стандартные кнопки Bootstrap дополнительными вариантами и утилитами.

## Классы кнопок

### 1. Круглые кнопки (`.btn-circle`)

Идеально круглые кнопки для иконок. Автоматически становятся квадратными с `border-radius: 50%`.

#### Базовое использование

```html
<button class="btn btn-primary btn-circle">
  <i class="bi-plus"></i>
</button>

<button class="btn btn-outline-secondary btn-circle">
  <i class="bi-funnel"></i>
</button>
```

#### Размеры

```html
<!-- Маленькая: 32x32px -->
<button class="btn btn-primary btn-circle btn-sm">
  <i class="bi-heart"></i>
</button>

<!-- Средняя (по умолчанию): 36x36px -->
<button class="btn btn-primary btn-circle">
  <i class="bi-star"></i>
</button>

<!-- Большая: 44x44px -->
<button class="btn btn-primary btn-circle btn-lg">
  <i class="bi-search"></i>
</button>
```

Или используйте специальные классы:
```html
<button class="btn btn-primary btn-circle-sm">...</button>
<button class="btn btn-primary btn-circle-md">...</button>
<button class="btn btn-primary btn-circle-lg">...</button>
```

#### Состояния

Toggle-кнопки автоматически вращаются при раскрытии:

```html
<button class="btn btn-outline-secondary btn-circle" 
        data-bs-toggle="collapse" 
        data-bs-target="#filters"
        aria-expanded="false">
  <i class="bi-funnel"></i>
</button>
<!-- При aria-expanded="true" кнопка повернется на 180° -->
```

### 2. Кнопки с иконками (`.btn-icon`)

Кнопки с иконкой и текстом. На мобильных устройствах текст скрывается.

```html
<button class="btn btn-primary btn-icon">
  <i class="bi-plus-lg"></i>
  <span class="btn-text">Создать</span>
</button>

<a href="/create" class="btn btn-success btn-icon">
  <i class="bi-file-plus"></i>
  <span class="btn-text">Новый документ</span>
</a>
```

**Поведение:**
- Десктоп: иконка + текст
- Мобильные (< 768px): только иконка (круглая кнопка)

### 3. Кнопки-призраки (`.btn-ghost`)

Прозрачные кнопки без фона, появляется фон при наведении.

```html
<button class="btn btn-ghost">
  <i class="bi-pencil"></i>
  Редактировать
</button>

<button class="btn btn-ghost btn-circle">
  <i class="bi-three-dots"></i>
</button>
```

### 4. Pill-кнопки (`.btn-pill`)

Максимально скругленные кнопки (`border-radius: 999px`).

```html
<button class="btn btn-primary btn-pill">
  Подписаться
</button>

<a href="/more" class="btn btn-outline-secondary btn-pill">
  Узнать больше
</a>
```

## Группы кнопок

### Группа круглых кнопок

```html
<div class="btn-circle-group">
  <button class="btn btn-outline-secondary btn-circle">
    <i class="bi-funnel"></i>
  </button>
  <button class="btn btn-outline-secondary btn-circle">
    <i class="bi-sort-down"></i>
  </button>
  <button class="btn btn-primary btn-circle">
    <i class="bi-plus"></i>
  </button>
</div>
```

## Примеры использования

### Пример 1: Шапка страницы с фильтрами

```html
<div class="d-flex align-items-center gap-2">
  <h1>Сотрудники</h1>
  
  <div class="ms-auto d-flex gap-2">
    <!-- Поиск -->
    <input type="search" class="form-control" placeholder="Поиск...">
    
    <!-- Кнопка фильтров -->
    <button class="btn btn-outline-secondary btn-circle" 
            data-bs-toggle="collapse" 
            data-bs-target="#filters">
      <i class="bi-funnel"></i>
    </button>
    
    <!-- Кнопка создания -->
    <button class="btn btn-primary btn-icon">
      <i class="bi-plus-lg"></i>
      <span class="btn-text">Создать</span>
    </button>
  </div>
</div>
```

### Пример 2: Карточка с действиями

```html
<div class="card">
  <div class="card-body">
    <h5>Название документа</h5>
    <p>Описание...</p>
    
    <div class="btn-circle-group">
      <button class="btn btn-ghost btn-circle" title="Редактировать">
        <i class="bi-pencil"></i>
      </button>
      <button class="btn btn-ghost btn-circle" title="Поделиться">
        <i class="bi-share"></i>
      </button>
      <button class="btn btn-ghost btn-circle" title="Удалить">
        <i class="bi-trash"></i>
      </button>
    </div>
  </div>
</div>
```

### Пример 3: Навигация с разными размерами

```html
<div class="d-flex align-items-center gap-3">
  <!-- Маленькие кнопки для вспомогательных действий -->
  <button class="btn btn-outline-secondary btn-circle btn-sm">
    <i class="bi-arrow-left"></i>
  </button>
  
  <!-- Обычная кнопка для основного действия -->
  <button class="btn btn-primary btn-pill">
    Далее
  </button>
  
  <!-- Маленькая кнопка справа -->
  <button class="btn btn-outline-secondary btn-circle btn-sm">
    <i class="bi-arrow-right"></i>
  </button>
</div>
```

## Комбинирование с Bootstrap

Все новые классы полностью совместимы со стандартными классами Bootstrap:

```html
<!-- Цвета Bootstrap -->
<button class="btn btn-primary btn-circle">...</button>
<button class="btn btn-success btn-circle">...</button>
<button class="btn btn-danger btn-circle">...</button>
<button class="btn btn-outline-secondary btn-circle">...</button>

<!-- Размеры Bootstrap + круглые кнопки -->
<button class="btn btn-primary btn-circle btn-sm">...</button>
<button class="btn btn-primary btn-circle btn-lg">...</button>

<!-- Состояния Bootstrap -->
<button class="btn btn-primary btn-circle" disabled>...</button>
<button class="btn btn-outline-secondary btn-circle active">...</button>
```

## Миграция со старого кода

### Было (специфичные стили):

```html
<button class="btn btn-outline-secondary page-filter-toggle">
  <i class="bi-funnel"></i>
</button>
```

```css
.page-filter-toggle {
  width: 36px !important;
  height: 36px !important;
  border-radius: 50% !important;
  /* ... еще 20 строк CSS ... */
}
```

### Стало (универсальный класс):

```html
<button class="btn btn-outline-secondary btn-circle">
  <i class="bi-funnel"></i>
</button>
```

```css
/* Никаких дополнительных стилей не нужно! */
```

## CSS переменные

Компонент использует стандартные переменные Bootstrap:
- `--bs-primary` - основной цвет
- `--bs-body-color` - цвет текста
- `--bs-border-color` - цвет границ
- `--bs-border-radius` - скругление углов

## Поддержка темной темы

Все кнопки автоматически адаптируются под темную тему через `prefers-color-scheme: dark`.

## Доступность

- Все кнопки имеют правильные `aria-label` атрибуты
- Иконки используют `line-height: 1` для правильного центрирования
- Фокус-стейты наследуются от Bootstrap
- Поддержка клавиатурной навигации

## Производительность

- Минимальное использование `!important` (только где абсолютно необходимо)
- CSS переменные для легкой кастомизации
- Оптимизированные селекторы
- Не влияет на другие компоненты
