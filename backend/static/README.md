# Static Assets - Custom Bootstrap

Этот каталог содержит статические файлы проекта с кастомизированным Bootstrap.

## Структура

```
static/
├── css/                    # Скомпилированные CSS файлы
│   ├── bootstrap-custom.css   # Кастомный Bootstrap (генерируется)
│   ├── variables.css          # CSS переменные проекта
│   └── components/            # Компоненты приложения
├── scss/                   # SCSS исходники
│   └── custom-bootstrap.scss  # Конфигурация Bootstrap
├── node_modules/           # npm зависимости (игнорируется в git)
└── package.json            # npm конфигурация
```

## Настройка окружения

### 1. Установка Node.js (если еще не установлен)

```bash
winget install OpenJS.NodeJS.LTS
```

### 2. Установка зависимостей

```bash
cd backend/static
npm install
```

## Разработка

### Компиляция Bootstrap

**Однократная сборка:**
```bash
npm run build
```

**Режим разработки (автоматическая пересборка при изменениях):**
```bash
npm run dev
```

### Изменение системы отступов

Все настройки отступов находятся в файле `scss/custom-bootstrap.scss`:

```scss
// Базовая шкала отступов (8px grid)
$spacers: (
  0: 0,           // 0px
  1: 0.5rem,      // 8px  - var(--space-1)
  2: 1rem,        // 16px - var(--space-2)
  3: 1.5rem,      // 24px - var(--space-3)
  4: 2rem,        // 32px - var(--space-4)
  5: 3rem,        // 48px - var(--space-5)
);
```

После изменений запустите:
```bash
npm run build
```

## Система отступов

Проект использует унифицированную 8px сетку:

- `--space-1` (0.5rem / 8px) - минимальный отступ
- `--space-2` (1rem / 16px) - стандартный отступ
- `--space-3` (1.5rem / 24px) - секции
- `--space-4` (2rem / 32px) - блоки
- `--space-5` (3rem / 48px) - большие разделители

### Bootstrap классы

Все Bootstrap utility классы теперь используют нашу сетку:

- `.p-1`, `.m-1` = 8px
- `.p-2`, `.m-2` = 16px
- `.p-3`, `.m-3` = 24px
- `.p-4`, `.m-4` = 32px
- `.p-5`, `.m-5` = 48px

То же самое для `.px-*`, `.py-*`, `.mx-*`, `.my-*`, `.gap-*` и т.д.

## Компоненты Bootstrap

Все компоненты настроены на использование нашей системы:

- Cards → padding: 16px
- Buttons → padding: 8px 16px
- Forms → padding: 8px 16px
- Modals → padding: 16px
- Alerts → padding: 16px
- и т.д.

## Troubleshooting

**Проблема:** Изменения в SCSS не применяются

**Решение:**
1. Проверьте, что `npm run build` завершился успешно
2. Очистите кэш браузера (Ctrl+Shift+R)
3. Проверьте, что в `base.html` подключен `bootstrap-custom.css`

**Проблема:** npm команды не работают

**Решение:**
```bash
# Добавьте Node.js в PATH для текущей сессии
export PATH="/c/Program Files/nodejs:$PATH"

# Или перезапустите терминал после установки Node.js
```

## Дополнительная настройка

Для более глубокой кастомизации Bootstrap см. документацию:
- https://getbootstrap.com/docs/5.3/customize/sass/
- https://sass-lang.com/documentation
