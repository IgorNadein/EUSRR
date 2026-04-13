# Frontend Guide: Migration

## Как трактовать legacy

Legacy не означает “удалить немедленно”. Это означает:

- решение нельзя копировать в новые места
- при касании блока нужно оценить перевод на target state
- если перевод пока невозможен, причина должна быть понятна и зафиксирована

## Что можно рефакторить массово

Без отдельного UX-исследования обычно можно:

- приводить card-like контейнеры к `rounded-xl` и `rounded-2xl`
- убирать `rounded-md` у карточек и стандартных полей
- сокращать `rounded-[...]` у обычных секций
- подтягивать простые inputs, buttons и surfaces к `app-*` primitives

## Что требует ручного review

Ручной review обязателен для:

- сложных форм
- compose workflows
- multi-step dialogs
- dropdown-полей со сложным поведением
- drawer-like и workspace-like интерфейсов
- экранов, где геометрия тесно завязана на сценарий использования

## Приоритет рефакторинга

Рекомендуемый порядок:

1. карточки и surface hierarchy
2. сокращение custom radii
3. выравнивание shared affordance
4. только после этого формы по отдельным UX-паттернам

## Ориентиры по крупным зонам

### `requests`

Использовать как ориентир по compose-настроению и декомпозиции насыщенного экрана.

Сейчас это reference для:

- идеи “форма как рабочее пространство”
- разрезания page-level orchestration и feature-level list/detail/controls/preview блоков
- вынесения screen-specific router/menu/deep-link orchestration в отдельный hook
- feature containers уровня list-section / swipe-mode panel, которые собирают несколько leaf-компонентов внутри одного сценария

### `procurement`

Хороший кандидат для следующей волны нормализации крупных panel-контейнеров и detail cards.

### `equipment`

Подходит для рефакторинга secondary cards и form blocks, потому что там много повторяющейся геометрии.

### `settings`

Сильный ориентир по primary/secondary surface hierarchy, но там ещё встречаются кастомные радиусы, которые нужно сокращать.

### `documents`

Ключевая зона для аудита legacy-геометрии: заметно смешение `rounded-md`, `rounded-lg`, `rounded-xl` и локальных utility-решений.

## Правила локального override

Локальный override допустим только если:

- задача не покрывается существующим primitive
- решение действительно локально
- override не ломает base semantics цвета, surface или focus behavior
- у него есть понятное обоснование

Если override начинает повторяться, он должен быть поднят в shared layer.
