# Frontend Guide: Component Inventory

Этот документ отвечает на вопрос: какие UI-примитивы и повторно используемые компоненты уже есть в коде и когда их нужно брать вместо создания нового решения.

## 1. Foundation primitives

Это первый выбор для любого нового экрана.

### `frontend/src/app/globals.css`

Назначение:

- цветовые токены
- surface hierarchy
- базовые form primitives
- action states
- feedback states

Использовать, когда:

- нужен новый экран на существующей дизайн-системе
- нужно собрать карточку, поле, кнопку или feedback-блок без изобретения новой визуальной базы

Не использовать как:

- место для локального feature-хака без повторного применения

### `frontend/src/components/AppShell.tsx`

Что даёт:

- shell background
- header
- global search
- mobile navigation drawers
- `PageHeader`

Использовать, когда:

- нужен normal page внутри основного приложения

Не использовать, когда:

- экран является отдельным auth/legal flow и у него другой layout-contract

### `frontend/src/components/ui/Modal.tsx`

Что даёт:

- единый modal shell
- focus trap
- close handling
- header/footer contract
- responsive sizing

Использовать, когда:

- нужен обычный modal dialog
- нет отдельного сценария drawer/workspace/fullscreen flow

Не использовать как:

- основание для новой параллельной modal-системы

### `frontend/src/components/shared/SearchableSelect.tsx`

Компоненты:

- `SearchableSelectSingle`
- `SearchableSelectMulti`

Использовать, когда:

- нужен поиск по списку
- нужен multi-select
- нужно chip-представление выбранных значений
- нужен compose-like address field

Не использовать native `select`, если:

- начинаются локальные доработки стрелки
- нужен поиск
- нужен выбор нескольких пользователей

## 2. Shell-level и системные компоненты

### `NotificationCenter`

Роль:

- системный блок уведомлений

Когда использовать:

- в shell или system-level surface
- не как основу для произвольных выпадающих списков

### `MobileLeftDrawer` и `MobileCalendarDrawer`

Роль:

- мобильные системные drawer-паттерны

Когда использовать:

- для app-level mobile navigation / side panels

Не использовать:

- как shortcut для каждой произвольной feature-модалки

## 3. Feature-shared компоненты

Эти компоненты полезны как референс и иногда как основа для похожих сценариев, но они уже ближе к домену.

### Calendar

Файлы:

- `CalendarModal.tsx`
- `EventModal.tsx`
- `CalendarParticipantsModal.tsx`
- `CalendarSubscriptionsModal.tsx`
- `ViewDayEventsModal.tsx`
- `ViewEventDetailsModal.tsx`
- `calendar/CalendarSidebar.tsx`
- `calendar/CalendarCard.tsx`

Использовать как референс для:

- event forms
- side panels
- selection-heavy dialog flows

С оговоркой:

- calendar UI ещё не является эталоном всей системы и содержит legacy-решения

### Documents

Файлы:

- `DocumentDetailModal.tsx`
- `DocumentUploadForm.tsx`
- `DocumentPreview.tsx`
- `DocumentMetadataEditor.tsx`
- `DocumentComments.tsx`

Использовать как референс для:

- document-heavy UI
- detail panels
- upload flows
- metadata forms

С оговоркой:

- documents содержит заметный пласт legacy-геометрии и нуждается в дальнейшем выравнивании

### Requests

Файлы:

- `requests/RequestAttachmentPreviewModal.tsx`
- `requests/RequestAvatar.tsx`
- `requests/RequestComposeModal.tsx`
- `requests/RequestDetailModal.tsx`
- `requests/RequestListControls.tsx`
- `requests/RequestListItem.tsx`
- `requests/RequestListSection.tsx`
- `requests/RequestSwipeModePanel.tsx`
- `requests/RequestUserBadge.tsx`
- `requests/SwipeApprovalMode.tsx`
- `app/requests/page.tsx`
- `hooks/useRequestsPage.ts`
- `hooks/useRequestsPageScreen.ts`

Использовать как референс для:

- compose-like form pattern
- detail modal с participant-heavy content
- page-level toolbar/filter block, который вынесен из страницы в feature component
- feature container для list shell, который собирает rows + empty state + load more
- отдельный mode-panel для alternate flow вроде swipe-review
- attachment preview modal как отдельный feature block, а не хвост page-level JSX
- локальный avatar/media wrapper вокруг `next/image`, когда feature уже использует несколько однотипных аватаров и preview
- participant badge pattern для request-like доменов
- participant-only UI decisions
- conditional action rendering по данным API
- разделения page-level orchestration и feature-level compose workspace
- screen-specific router/menu/deep-link orchestration без засорения page-level JSX

`requests/RequestUserBadge.tsx` использовать как ориентир, когда нужен person-chip паттерн:

- `avatar + name` внутри capsule
- опциональная ссылка на профиль
- compact и large варианты внутри одного feature wrapper

Не копировать компонент дословно во все модули, но сохранять приоритет этого паттерна над сырой строкой получателя или локально собранным badge.

С оговоркой:

- `requests` сейчас хороший ориентир по декомпозиции и compose/detail flow, но не должен автоматически становиться visual-template для всех dense lists

### Users / profile-like screens

Файлы:

- `users/ProfileSections.tsx`
- `users/EditUserProfileModal.tsx`
- `users/EmployeeActionModal.tsx`
- `users/EmployeeActionsTimeline.tsx`
- `hooks/useProfilePage.ts`
- `hooks/useUserDetailPage.ts`

Использовать как референс для:

- profile hero
- profile sections
- info cards
- action timeline
- page-level profile controllers, которые держат loading/derived state/API orchestration вне page JSX

### Departments

Файлы:

- `departments/DepartmentPersonChip.tsx`
- `app/departments/[id]/page.tsx`
- `hooks/useDepartmentPage.ts`

Использовать как референс для:

- detail screen, который должен уметь переключаться между `showcase` и `management` без смены route и без ощущения двух разных страниц
- page-level controller для domain actions вокруг одного объекта: overview, members, head management, roles
- richer detail layout, где есть сильный header, один основной roster-блок и один secondary-блок ролей, без раздувания служебных summary-panels
- member roster с role assignment и person-chip подачей вместо сырых строк участников
- role management на уровне названий ролей и назначений участникам, без фронтового permission-editor

С оговоркой:

- `departments/[id]` должен оставаться привязанным к реальным backend-capabilities; не наращивать UI, если под него нет соответствующих endpoint/actions

### Messages

Файлы:

- `messages/MessageComposer.tsx`
- `messages/ChatMessageItem.tsx`
- `messages/ChatDialogHeader.tsx`
- `ScrollableMessageList.tsx`

Использовать как референс для:

- dense interactive lists
- composer area
- dialog-like chat surface

С оговоркой:

- chat решает очень специфический UX, поэтому не должен автоматически становиться шаблоном для остальных модулей

## 4. Что считать shared, а что нет

Компонент нужно считать shared, если:

- он решает повторяемую визуальную механику
- у него нет жёсткой доменной привязки
- он пригоден минимум для двух feature-зон

Компонент не нужно тащить в shared, если:

- он глубоко привязан к одному домену
- у него много domain-specific props и состояний
- он служит хорошим референсом, но плохим универсальным primitive

## 5. Быстрый выбор перед новой разработкой

Если нужен:

- page shell: `AppShell`, `PageHeader`
- modal: `Modal`
- searchable dropdown: `SearchableSelect*`
- compose address line: `SearchableSelectMulti` с compose-like layout
- comment composer / delete action: `shared/CommentControls.tsx`
- primary/secondary surface: `app-surface` / `app-surface-muted`
- feedback block: `app-selected`, `app-feedback-*`

Если после этого всё ещё хочется создать новый primitive, сначала проверить:

- нет ли уже похожего решения в `components`
- нельзя ли расширить существующий shared-компонент
- не пытаемся ли мы решить локальную проблему новым глобальным паттерном
