# Frontend Guide: Geometry

## Целевая шкала радиусов

Это нормативная target-scale для frontend UI:

- `rounded-lg` для controls
- `rounded-xl` для secondary cards и grouped blocks
- `rounded-2xl` для primary panels, page sections и modal shells
- `rounded-full` для pills, avatar, search capsules и похожих капсул

Эта шкала обязательна для новых экранов и перерабатываемых блоков.

## Controls

К controls относятся:

- input
- textarea
- select
- shared select trigger
- небольшие action buttons
- small menu buttons

Норма:

- `rounded-lg`

## Secondary cards

К secondary cards относятся:

- вложенные блоки внутри primary panel
- grouped filter blocks
- компактные detail sections
- utility cards среднего веса

Норма:

- `rounded-xl`

## Primary panels

К primary panels относятся:

- основные секции страниц
- большие feature containers
- modal shells
- крупные empty / detail / state containers

Норма:

- `rounded-2xl`

## Специальные случаи

Допустимо:

- `rounded-full` для capsules, chips, avatars
- редкое отдельное решение для hero/media container, если оно согласовано как special case

Недопустимо по умолчанию:

- новый “авторский” радиус без системной причины

## Legacy-геометрия

Считаются legacy:

- `rounded-md` у новых карточек и полей
- `rounded-[...]` без отдельного обоснования

Практический смысл:

- такое решение нельзя копировать в новые места
- при изменении существующего блока нужно оценить возможность перевода на базовую шкалу

## Таксономия карточек

### Primary container card

Признаки:

- основной контейнер feature-секции
- главный визуальный уровень страницы

Норма:

- `app-surface`
- `rounded-2xl`

### Secondary grouped block

Признаки:

- вложенный блок внутри primary panel
- объединяет несколько связанных элементов

Норма:

- `app-surface-muted`
- `rounded-xl`

### Inline utility / feedback block

Признаки:

- helper
- warning
- state summary
- selected or feedback fragment внутри карточки или формы

Норма:

- `app-selected`, `app-feedback-*` или `app-surface-muted`
- `rounded-lg` или `rounded-xl` в зависимости от веса блока

Правило:

- не превращать маленький helper в ещё одну primary-card конструкцию
