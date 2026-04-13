# Frontend Guide: Audit Map

Этот документ нужен как стартовая карта рефакторинга. Он не заменяет подробный аудит, но фиксирует, какие крупные зоны уже ближе к target state, а какие ещё содержат заметный объём legacy.

## Статусы

- `ok` — зона уже достаточно согласована с guide
- `mixed` — есть сильные части, но заметно смешение old/new patterns
- `needs refactor` — зона должна попасть в один из следующих refactor pass
- `legacy-heavy` — много технического долга и старых паттернов

## Карта зон

| Зона | Статус | Что уже хорошо | Основные проблемы | Рекомендуемый следующий шаг |
| --- | --- | --- | --- | --- |
| `requests` | `mixed` | визуально удачный экран, compose-настроение, participant-only логика, UI вокруг `can_decide`, compose/list/detail/controls/preview разведены по feature components, screen orchestration вынесена в hook, list/swipe flow собраны в feature containers, avatar/preview media contract выровнен через local wrapper | зона полезна как проверка guide, но не должна автоматически становиться полным visual-reference; здесь важнее бережный structural refactor без насильственного редизайна | использовать как ориентир по декомпозиции насыщенного экрана и осторожной нормализации уже хорошего UI, а не как шаблон для жёсткой пересборки dense list-паттернов |
| `settings` | `mixed` | сильная surface hierarchy, хорошие primary sections | встречаются custom radii и локальная геометрическая неоднородность | рефакторить карточки и кастомные радиусы без смены общего layout |
| `documents` | `needs refactor` | богатый набор сценариев, detail/upload/comment patterns уже выделены в компоненты | смешение `rounded-md`, `rounded-lg`, `rounded-xl`, разные уровни visual density | сделать отдельный pass по карточкам и metadata/upload flows |
| `equipment` | `needs refactor` | понятные формы и вторичные блоки | много локальных card/form решений, геометрия плавает | после `documents` пройтись по secondary cards и action forms |
| `procurement` | `mixed` | крупные панели и часть detail blocks уже читаются неплохо | остаются старые form fragments и неоднородные локальные поля | нормализовать page panels и supplier/request forms |
| `calendar` | `legacy-heavy` | богатая функциональность, много reusable доменных компонентов | historical layering, legacy-термины и неоднородные модалки | отдельный audit до системного refactor |
| `messages` | `mixed` | зрелая interaction model, сильный composer и message item | очень доменно-специфичный UX, не всё переносимо как общий стандарт | использовать выборочно как reference, без механического копирования в другие зоны |
| `users/profile` | `mixed` | хорошие profile sections и hero-like patterns | часть экранов ещё может дрейфовать по локальным решениям | держать как reference для profile contract и точечно упрощать |
| `documents/dashboard` | `legacy-heavy` | есть готовые data blocks | заметны старые rounded patterns и мелкие utility-решения | включить в documents refactor pass |

## Порядок следующего рефакторинга

Рациональный порядок:

1. `settings`
2. `documents`
3. `equipment`
4. `procurement`
5. отдельный audit по `calendar`

`requests` лучше использовать как проверочную зону для guide: сначала сохранять удачный внешний контракт и чистить структуру, а уже потом решать, какие визуальные паттерны действительно стоит поднимать в общие правила.

## Как использовать эту карту

Перед началом крупной UI-задачи:

- посмотреть статус зоны
- понять, это target-like area или legacy area
- решить, задача локальная или это хороший момент для mini-refactor

Если зона помечена как `needs refactor` или `legacy-heavy`, новый код внутри неё особенно не должен копировать старые решения “как есть”.
