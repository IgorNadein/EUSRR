# Frontend Guide: Geometry

## Целевая шкала радиусов

Это нормативная target-scale для frontend UI:

- `rounded-lg` для controls
- `rounded-xl` для secondary cards и grouped blocks
- `rounded-2xl` для primary panels, page sections и modal shells
- `rounded-full` для pills, avatar, search capsules и похожих капсул

Эта шкала обязательна для новых экранов и перерабатываемых блоков.

## Целевая шкала вертикального ритма

Радиусы сами по себе не делают систему согласованной. Если блоки одного веса выглядят похоже, у них должен быть одинаковый spacing.

Нормативная шкала:

- `gap-2` для compact control clusters и плотных inline actions
- `space-y-2` для плотного стека внутри одного secondary/detail block
- `space-y-3` для стека однотипных rows или peer secondary cards внутри одной primary panel
- `space-y-4` для стека крупных grouped blocks или major subsections внутри одной primary panel
- `space-y-6` для page-level section stack

Правило:

- spacing выбирается по весу блока и уровню иерархии, а не по конкретному экрану
- одинаковые `app-surface-muted rounded-xl` блоки не должны жить на `space-y-2` в одной зоне и на `space-y-4` в другой без явной UX-причины

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
