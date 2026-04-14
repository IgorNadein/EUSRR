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

## Что нельзя делать механически

Без отдельного обоснования нельзя:

- брать удачный экран и переделывать его под другой визуальный жанр только ради декомпозиции
- считать, что выравнивание `rounded-*` автоматически решает проблему согласованности системы
- копировать успешный local layout в другие зоны без проверки, совпадает ли у экранов тип сценария

Особенно важно:

- `requests` сейчас ближе к общему operational style проекта
- `users/profile` визуально неплох, но местами ощущается как screen из другого продукта
- это означает, что refactor должен сначала фиксировать продуктовый character экрана, а уже потом править geometry/detail-level debt

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

С оговоркой:

- зона крупная и функционально богатая, но в ней заметно смешение app-style и gray/white legacy fragments
- refactor должен идти не только по page-level layout, но и по дочерним panels/forms

### `equipment`

Подходит для рефакторинга secondary cards и form blocks, потому что там много повторяющейся геометрии.

### `settings`

Сильный ориентир по primary/secondary surface hierarchy, но там ещё встречаются кастомные радиусы, которые нужно сокращать.

### `users/profile`

Использовать как ориентир по profile anatomy:

- hero
- section stack
- contacts/info/timeline decomposition

С оговоркой:

- профиль нельзя считать полным stylistic reference для всего приложения
- эту зону нужно подтянуть ближе к общему product feel без потери profile-specific anatomy

### `documents`

Ключевая зона для аудита legacy-геометрии: заметно смешение `rounded-md`, `rounded-lg`, `rounded-xl` и локальных utility-решений.

## Правила локального override

Локальный override допустим только если:

- задача не покрывается существующим primitive
- решение действительно локально
- override не ломает base semantics цвета, surface или focus behavior
- у него есть понятное обоснование

Если override начинает повторяться, он должен быть поднят в shared layer.
