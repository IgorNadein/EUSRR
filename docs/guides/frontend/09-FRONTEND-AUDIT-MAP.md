# Frontend Guide: Audit Map

Этот документ нужен как стартовая карта рефакторинга. Он не заменяет подробный аудит, но фиксирует, какие крупные зоны уже ближе к target state, а какие ещё содержат заметный объём legacy.

## Статусы

- `ok` — зона уже достаточно согласована с guide
- `mixed` — есть сильные части, но заметно смешение old/new patterns
- `needs refactor` — зона должна попасть в один из следующих refactor pass
- `legacy-heavy` — много технического долга и старых паттернов

## Что именно показывает audit

Этот audit нужен не только для поиска `rounded-md` или `bg-white`.

Он должен отвечать на три вопроса:

- насколько экран совпадает с общей visual system проекта
- не уехал ли экран в другой визуальный жанр по сравнению с соседними app-страницами
- где рефакторинг даст наибольший эффект без риска сломать уже удачный UI

## Карта зон

| Зона | Статус | Что уже хорошо | Основные проблемы | Рекомендуемый следующий шаг |
| --- | --- | --- | --- | --- |
| `requests` | `mixed` | визуально удачный экран, compose-настроение, participant-only логика, UI вокруг `can_decide`, compose/list/detail/controls/preview разведены по feature components, screen orchestration вынесена в hook, list/swipe flow собраны в feature containers, avatar/preview media contract выровнен через local wrapper | зона полезна как проверка guide, но не должна автоматически становиться полным visual-reference; здесь важнее бережный structural refactor без насильственного редизайна | использовать как ориентир по декомпозиции насыщенного экрана и осторожной нормализации уже хорошего UI, а не как шаблон для жёсткой пересборки dense list-паттернов |
| `settings` | `mixed` | сильная surface hierarchy, хорошие primary sections, в целом совпадает с app-shell language | встречаются custom radii, page-level файл очень большой, часть hero/media решений выбивается по геометрии | резать controller/view-model слои и точечно сокращать custom geometry без смены общего layout |
| `documents` | `needs refactor` | богатый набор сценариев, detail/upload/comment patterns уже выделены в компоненты | смешение `rounded-md`, `rounded-lg`, `rounded-xl`, заметный gray-legacy в editor/viewer/tags, слишком много modal-heavy page-logic | сделать отдельный pass по карточкам, metadata/upload flows и documents subcomponents, не ограничиваться только page-level |
| `equipment` | `needs refactor` | понятные формы, hooks уже вынесены, основные списки и модалки покрывают богатый сценарий | большой page-file, смешение app-style и gray/white fragments, detail/comments/forms ещё не сведены к одному contract | после documents пройтись по secondary cards, detail blocks и action forms |
| `procurement` | `needs refactor` | крупные панели и часть detail blocks уже читаются неплохо, есть shared-like detail content | большой page-file, gray/white legacy в stats/suppliers/forms, смешение operational page и старых local panels | нормализовать page panels, suppliers/stats/forms и только потом решать дальнейшую декомпозицию |
| `calendar` | `legacy-heavy` | богатая функциональность, много reusable доменных компонентов | historical layering, legacy-термины и неоднородные модалки | отдельный audit до системного refactor |
| `messages` | `mixed` | зрелая interaction model, сильный composer и message item, app-style в основных экранах в целом выдержан | очень доменно-специфичный UX, крупные page-files, часть settings/create/chat-experiment flows ещё шумят по state/legacy dialogs | использовать выборочно как reference, без механического копирования в другие зоны; дальше резать state-heavy pages |
| `users/profile` | `needs refactor` | хорошие profile sections, hero-like anatomy, action timeline, переиспользуемые section-level components, `/profile` и `/users/[id]` теперь оба опираются на page-level controllers | профиль всё ещё визуально ощущается как screen из другого проекта, `ProfileSections` держат custom hero geometry, users modals и часть users-list screens ещё тянут cluster назад | держать как reference по profile anatomy, но продолжить alignment-pass по people/profile cluster без превращения его в request-like layout |
| `users/directory` | `needs refactor` | простые сценарии, понятные employee/user navigation flows | `users/page.tsx` и часть directory screens всё ещё в white/gray card language, визуально выпадают из app surfaces | после profile cluster пройтись по user/employee lists и привести их к общему app-shell contract |
| `home/feed` | `mixed` | сильный app-shell fit, хорошая operational density, уже много app primitives | page очень большой, комментарии и post-compose logic перегружены, встречаются legacy `rounded-md` fragments | использовать как reference по feed density, но разрезать modal/comments/post flows и дочистить geometry |
| `notifications` | `mixed` | близок к operational app-style, фильтры и list hierarchy уже читаются системно | page-level logic пока монолитная, нет выделенного feature controller, есть место для уплотнения и симметрии с messages/requests | после people cluster сделать короткий structural pass без крупного редизайна |
| `departments` | `mixed` | page/detail screens небольшие и уже живут в app-shell language | не хватает единых richer patterns между list/detail, зона выглядит недоразвитой по сравнению с остальными модулями | low-cost pass после крупных зон: выровнять richness и reuse |
| `auth/legal` | `mixed` | изолированные flows уже отделены от app-shell, общая подача аккуратная | `rounded-[2rem]` и локальная hero-card геометрия образуют мини-систему отдельно от app shell | не смешивать с operational refactor; сделать отдельный compact pass по auth/legal geometry |
| `documents/dashboard` | `legacy-heavy` | есть готовые data blocks | заметны старые rounded patterns и мелкие utility-решения | включить в documents refactor pass |

## Порядок следующего рефакторинга

Рациональный порядок после текущего audit:

1. `users/profile` + `users/directory`
2. `home/feed` + `notifications`
3. `documents` + `documents/dashboard`
4. `equipment`
5. `procurement`
6. `messages`
7. `settings`
8. отдельный audit по `calendar`
9. `departments`
10. `auth/legal`

Логика порядка:

- сначала устранять самые заметные genre-mismatch зоны, которые визуально выбиваются из остального продукта
- потом идти в крупные operational pages, где уже есть app-style foundation, но слишком много structural debt
- затем чистить heavy business-modules с большим объёмом legacy fragments
- calendar оставлять отдельным спец-аудитом, а не вписывать в механическую волну

## Детальный план волн

### Волна 1. Product alignment

Зоны:

- `users/profile`
- `users/directory`

Цель:

- подтянуть people/profile cluster к общему product feel без потери profile anatomy

Что делать:

- `/profile` уже переведён на page-level controller по аналогии с `useUserDetailPage`
- `EditUserProfileModal` и `EmployeeActionModal` уже подтянуты к app-style primitives
- нормализовать `ProfileSections` по геометрии без уничтожения hero/section contract
- привести `users/page.tsx` к app-surface language

### Волна 2. Operational pages with high leverage

Зоны:

- `home/feed`
- `notifications`

Цель:

- укрепить самые частые рабочие экраны, уже близкие к target state

Что делать:

- разрезать большие page-level controllers
- дочистить legacy `rounded-md` в feed/comments actions
- выровнять controls/list/detail semantics между feed, notifications и requests

### Волна 3. Documents system

Зоны:

- `documents`
- `documents/dashboard`

Цель:

- убрать самый заметный geometry/token drift внутри document flows

Что делать:

- tags, metadata, folder tree, viewer, related documents, upload/detail flows
- сократить `rounded-md` и gray-legacy
- проверить modal/viewer/editor contracts отдельно от page shell

### Волна 4. Asset/workflow modules

Зоны:

- `equipment`
- `procurement`

Цель:

- привести тяжёлые operational modules к одному panel/detail/form contract

Что делать:

- пройтись по stats/suppliers/detail/comments/forms в `procurement`
- пройтись по equipment detail/history/comments/QR/forms
- только после этого решать, где нужна дополнительная декомпозиция page-level файлов

### Волна 5. Messages

Зоны:

- `messages`
- `messages/[chatId]`
- `messages/[chatId]/settings`

Цель:

- сохранить сильный доменный UX, но снять лишний state/dialog debt

Что делать:

- не трогать core chat UX механически
- отдельно проходить list/settings/create-chat/dialog states
- использовать как reference выборочно, а не как global standard

### Волна 6. Settings and supportive modules

Зоны:

- `settings`
- `departments`
- `auth/legal`

Цель:

- дочистить крупные secondary zones после выравнивания основных рабочих сценариев

Что делать:

- у `settings` сначала резать size/structure page, затем geometry
- у `departments` поднять богатство patterns до общего уровня app
- у `auth/legal` выровнять isolated geometry отдельно от app-shell жанра

### Волна 7. Calendar special audit

Зона:

- `calendar`

Цель:

- перед любым большим refactor сначала зафиксировать фактическую архитектуру и legacy boundary

Что делать:

- отдельная карта модалок, cards, subscriptions/import/export/event flows
- только после этого принимать решение о системной переработке

## Как использовать эту карту

Перед началом крупной UI-задачи:

- посмотреть статус зоны
- понять, это target-like area или legacy area
- решить, задача локальная или это хороший момент для mini-refactor

Если зона помечена как `needs refactor` или `legacy-heavy`, новый код внутри неё особенно не должен копировать старые решения “как есть”.
