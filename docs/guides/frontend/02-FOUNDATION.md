# Frontend Guide: Foundation

## Источники истины

Foundation layer уже существует и задаётся в этих файлах:

- `frontend/src/app/globals.css`
- `frontend/src/components/ui/Modal.tsx`
- `frontend/src/components/shared/SearchableSelect.tsx`
- `frontend/src/components/AppShell.tsx`

Новый UI должен опираться на них. Локальные utility-классы допустимы только как расширение, а не как новая параллельная система.

## Цветовые и surface-токены

Базовые переменные определены в `frontend/src/app/globals.css`.

Ключевые токены:

- `--background`
- `--foreground`
- `--muted-foreground`
- `--surface-primary`
- `--surface-elevated`
- `--surface-secondary`
- `--surface-tertiary`
- `--surface-overlay`
- `--border-subtle`
- `--border-strong`
- `--accent-primary`
- `--accent-primary-strong`
- `--accent-soft`
- `--accent-soft-strong`
- `--success-soft`
- `--danger-soft`
- `--warning-soft`
- `--shadow-card`
- `--shadow-elevated`

Правила:

- не вводить в новые экраны собственную “серую тему” через `bg-white`, `bg-gray-*`, `border-gray-*`
- не использовать локальный `focus:ring-sky-*`, если поведение уже покрывается `app-*`
- новый базовый цветовой токен сначала добавляется в `globals.css`, потом используется в компонентах

## Surface primitives

### `app-surface`

Использование:

- внешний самостоятельный блок
- основная карточка страницы
- primary content container

### `app-surface-elevated`

Использование:

- модалки
- overlay-панели
- визуально поднятые контейнеры

### `app-surface-muted`

Использование:

- вложенные секции
- grouped blocks
- вторичный внутренний слой

Правило вложенности:

- не строить цепочку `card inside card inside card`
- нормальный паттерн для большинства страниц: один внешний `app-surface` и один внутренний `app-surface-muted`

## Form primitives

### `app-input`

Использование:

- text inputs
- textareas
- date/time inputs
- field shells для compose-like строк, если это оправдано паттерном

### `app-select`

Использование:

- native `select`
- select-like triggers

Правило:

- если полю нужен поиск, мультивыбор, chips или сложный dropdown affordance, использовать shared select-компонент, а не локально стилизованный native `select`

## Action primitives

### `app-action-primary`

Использование:

- главное действие формы
- основной CTA секции

### `app-action-secondary`

Использование:

- вторичное действие
- отмена
- нейтральный CTA

### `app-action-ghost`

Использование:

- item actions внутри меню
- лёгкие встроенные действия

### `app-action-danger`

Использование:

- destructive actions

Правило:

- danger action использует ту же базовую оболочку, что и `app-action-secondary`
- destructive state отличать тоном, текстом и hover-состоянием, а не исчезающим контейнером
- icon-only danger action не должен выглядеть "голой" иконкой рядом с secondary control

## Badge, menu, feedback, selected

Использовать существующие primitives:

- `app-badge`
- `app-badge-accent`
- `app-menu`
- `app-selected`
- `app-selected-soft`
- `app-feedback-success`
- `app-feedback-warning`
- `app-feedback-danger`

Правила:

- статус должен быть семантическим
- selected state не подменяется произвольным акцентным фоном
- helper и feedback-блоки должны опираться на существующие feedback classes
