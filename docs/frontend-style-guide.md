# Frontend Style Guide

Короткий проектный контракт для новых экранов и рефакторинга старых.

## Базовые поверхности

- Внешний самостоятельный блок страницы: `app-surface`
- Внутренний блок внутри секции: `app-surface-muted`
- Не делать `card inside card inside card`, если можно обойтись одним внешним и одним внутренним уровнем.

## Подписи секций

- Верхние подписи карточек и секций: `app-card-caption`
- Внутренние заголовки внутри блоков:
  - `text-sm font-semibold text-[var(--foreground)]`
- Не смешивать `app-card-caption` и обычный заголовок в одном уровне вложенности.

## Кнопки

- Primary action:
  - `app-action-primary`
- Secondary action:
  - `app-action-secondary`
- Danger action:
  - secondary-style кнопка с red hover/focus, а не тяжелый красный прямоугольник по умолчанию
- Все add/create CTA должны выглядеть одинаково:
  - иконка `Plus`
  - `app-action-primary`
  - `rounded-xl`
  - одинаковая высота и плотность

## Pills и бейджи

- Нейтральный chip/filter: `app-pill`
- Активный/select/primary state: `app-pill-active` или `app-selected`
- Статусы должны быть семантическими:
  - success: `app-feedback-success`
  - warning: `app-feedback-warning`
  - danger: `app-feedback-danger`
- Не использовать случайный синий только потому, что нужен акцент.

## Формы

- Текстовые поля: `app-input`
- Select: `app-select`
- Поисковая строка в шапке: pill-форма
- Обычные form fields: скругленные углы, не pill
- Не смешивать разные hover/focus-паттерны на одном экране

## Профильные и read-only страницы

- `/profile` и `/users/[id]`:
  - hero сверху
  - отдельные широкие секции ниже
  - не дублировать settings-редактирование карандашами в нескольких местах
- Read-only экран:
  - минимум inline editing
  - одно явное действие лучше, чем несколько карандашей по карточкам
- Общий контракт профильно-подобных страниц:
  - `ProfileHeroCard`
  - `ProfileContactsPanel`
  - `ProfileInfoCard`
  - `ProfileSkillsCard`
  - `EmployeeActionsTimeline`
- Hero:
  - `app-card-caption` в шапке карточки
  - status pill справа сверху
  - аватар слева, имя и secondary meta справа
  - внутри hero только один `app-surface-muted` блок контактов
- `Контакты`:
  - строки с иконкой, заголовком и значением
  - опциональные действия справа живут в строке, а не отдельной карточкой
- `Информация`:
  - отдельный полноширинный `app-surface`
  - внутри одна `app-surface-muted` сетка 2x2
- `Навыки`:
  - одинаковая add-row и chip-scale и на self, и на foreign profile
- `/profile`:
  - self-oriented hero
  - без chat/call actions
- `/users/[id]`:
  - тот же hero-contract
  - chat/call/edit/manage actions допустимы только как добавочные props, без отдельной layout-ветки

## Таймлайны

- Линия события цветная по типу события
- Точка только на текущем событии
- Текущее событие определяется по дате, а не по первой записи в списке

## Контакты

- Контактные блоки строятся как список строк внутри `app-surface-muted`
- Не делать отдельную маленькую карточку на каждый контакт
- Иконки контактов нейтральны, если нет реальной причины для акцента

## Чего избегать

- `bg-white`, `bg-gray-*`, `ring-gray-*`, `focus:ring-sky-*` в новых и перерабатываемых экранах
- Разных стилей add/save/delete между соседними страницами
- Декоративных badge без логики состояния
- Смешения old-gray-contract и `app-*` токенов в одном блоке
