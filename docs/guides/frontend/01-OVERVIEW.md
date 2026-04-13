# Frontend Guide: Overview

## Назначение

Этот guide определяет правила, по которым должны строиться новые frontend-экраны, shared-компоненты и рефакторинг существующего UI.

При конфликте между текущим состоянием кода и этим guide приоритет у guide. Если часть системы ещё не приведена к target state, это legacy-состояние, а не альтернативная норма.

## Границы

Guide покрывает:

- визуальную систему frontend
- layout-принципы
- shared UI primitives
- геометрию
- card и form patterns
- modal и dropdown contracts

Guide не покрывает:

- API-дизайн
- state management конкретной фичи
- domain-логику
- отдельные feature-спеки

## Карта frontend-проекта

### `frontend/src/app`

Роль:

- маршруты Next.js App Router
- page-level composition
- orchestration экранов

Правила:

- страницы собирают UI из shared и feature-компонентов
- страницы не должны становиться вторым слоем дизайн-системы
- повторяемый паттерн должен подниматься в `components`
- если в странице уже живут toolbar/filters, expandable rows, detail modal и preview modal, это сигнал к разрезанию на feature-компоненты

### `frontend/src/components`

Роль:

- shared UI primitives
- reusable feature-компоненты
- списки, панели, dropdowns, modals, detail blocks

Правила:

- всё, что задаёт повторяемую визуальную механику, должно жить здесь
- shared-компонент должен использовать проектный visual contract, а не изобретать новый
- если похожий primitive уже есть, его нужно расширять, а не создавать параллельный

### `frontend/src/hooks`

Роль:

- orchestration логики
- загрузка данных
- derived state

Правила:

- hook не кодирует дизайн-систему
- hook может возвращать данные для UI, но не должен становиться хранилищем визуальных классов
- page-specific orchestration вроде router-sync, deep-link открытия detail modal и menu dismiss logic допустимо выносить в feature hook, если page-level файл начинает разрастаться
- derived actions уровня feature, например `clearFilters` или готовая выборка `pendingDecisionRequests`, лучше держать рядом с feature hook, а не собирать заново в page-level JSX

### `frontend/src/lib`

Роль:

- API clients
- adapters
- shared helpers

Правила:

- этот слой не должен зависеть от page-level UI
- UI-специфичные преобразования нужно держать ближе к feature-компоненту

### `frontend/src/types`

Роль:

- типы API
- shared domain contracts

Правила:

- типы описывают данные, а не визуальное оформление
- UI-значимые семантические флаги должны приходить как явные поля, а не вычисляться по role-based эвристикам в нескольких местах

## Текущее состояние системы

Система уже имеет foundation layer, но он не доведён до конца.

Сильные стороны:

- единая палитра
- surface hierarchy
- `app-*` action и state primitives
- общая идея shared shell

Основные проблемы:

- разные радиусы у однотипных элементов
- дрейф карточек по визуальному весу
- разный dropdown affordance у похожих полей
- локальные ad-hoc решения в feature-страницах
- расхождение по типу экранов: часть страниц живёт как рабочие модули системы, часть как showcase/profile/dashboard из другого продукта

Следствие:

- карточки и геометрию можно и нужно нормализовать системно
- формы нужно оценивать уже после этого, индивидуально по UX-паттернам

## Экранные жанры

Перед рефакторингом нужно определить не только набор компонентов, но и жанр экрана.

Базовые типы в этом проекте:

- operational workspace: плотные рабочие страницы со status/actions/list/detail flow
- profile-like page: hero + секции + персональные или справочные блоки
- dashboard/feed: обзорные экраны с несколькими контентными зонами
- auth/legal flow: изолированные страницы вне основного app-shell сценария

Правило:

- рефакторинг должен приводить все жанры к одной продуктовой системе
- но не должен насильно превращать один жанр в другой
- удачный operational screen нельзя без причины перепридумывать как showcase-layout
- удачный profile-screen нельзя механически уплотнять до вида request list только ради единообразия
