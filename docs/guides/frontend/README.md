# Frontend UI Guide

Статус: нормативная карта frontend UI-системы проекта.

Этот раздел фиксирует целевое состояние интерфейса и служит точкой входа для всех решений по стилям, геометрии, карточкам, формам, модалкам и shared UI primitives. Это не одна заметка, а карта правил, по которой нужно проектировать новые экраны и проводить рефакторинг старых.

## Как читать этот раздел

Порядок чтения:

1. [01-OVERVIEW.md](01-OVERVIEW.md)  
   Что это за guide, где проходят границы и как устроен frontend по слоям.
2. [02-FOUNDATION.md](02-FOUNDATION.md)  
   Базовые токены, поверхности, action/form primitives и источники истины.
3. [03-GEOMETRY.md](03-GEOMETRY.md)  
   Целевая шкала радиусов, таксономия карточек и допустимые исключения.
4. [04-PATTERNS.md](04-PATTERNS.md)  
   Формы, dropdown-like UX, модалки, App Shell и target-pattern registry.
5. [05-MIGRATION.md](05-MIGRATION.md)  
   Что считать legacy, как двигать рефакторинг и по каким зонам идти.
6. [06-COMPONENT-INVENTORY.md](06-COMPONENT-INVENTORY.md)  
   Какие shared и feature-shared компоненты уже есть и когда какой использовать.
7. [07-DEVELOPER-WORKFLOW.md](07-DEVELOPER-WORKFLOW.md)  
   Как проектировать новый экран, форму, карточку, модалку и когда выносить код в shared.
8. [08-UI-REVIEW-CHECKLIST.md](08-UI-REVIEW-CHECKLIST.md)  
   Короткий checklist для PR review и самопроверки перед merge.
9. [09-FRONTEND-AUDIT-MAP.md](09-FRONTEND-AUDIT-MAP.md)  
   Карта текущих зон frontend: что уже близко к standard, а что требует рефакторинга.

## Для чего этот guide

Guide обязателен для:

- новых экранов в `frontend/src/app`
- новых shared-компонентов в `frontend/src/components`
- переработки существующих карточек, форм, модалок и dropdown-паттернов
- code review, где нужно определить, является ли локальное UI-решение допустимым

Guide не предназначен для:

- описания API-контрактов
- описания state management конкретной фичи
- feature-specific UX-спеков

## Главная проблема системы

Сейчас frontend уже достаточно зрелый, чтобы его нормализовать системно.

Что уже в хорошем состоянии:

- палитра
- surface hierarchy
- акцентные состояния
- базовые `app-*` primitives

Что расползлось:

- геометрия
- шкала радиусов
- affordance dropdown-полей
- повторяющиеся card patterns
- разные form contracts для похожих сценариев

Именно поэтому этот раздел фиксирует target state заранее, даже если кодовая база ещё не полностью к нему приведена.

## Источники истины

Ключевые frontend primitives, на которые опирается весь guide:

- `frontend/src/app/globals.css`
- `frontend/src/components/ui/Modal.tsx`
- `frontend/src/components/shared/SearchableSelect.tsx`
- `frontend/src/components/AppShell.tsx`
- `frontend/src/components/requests/RequestComposeModal.tsx` как текущий reference для compose-like participant form

## Быстрый контракт

Если нужно принять быстрое решение без чтения всего guide:

- controls: `rounded-lg`
- secondary cards: `rounded-xl`
- primary panels и modal shells: `rounded-2xl`
- pills, avatar, search capsules: `rounded-full`
- `rounded-md` и `rounded-[...]`: legacy или редкое исключение с отдельным обоснованием
- dropdown UX с поиском, multi-select или chip-представлением должен идти через shared select-паттерн, а не через локальный ad-hoc `select`

## Навигация по рефакторингу

С этого раздела должен начинаться будущий глобальный refactor pass:

1. нормализация карточек
2. сокращение custom radii
3. выравнивание shared affordance
4. только потом индивидуальный разбор форм по паттернам

## Что уже покрыто

Этот раздел теперь выполняет две функции:

- нормативная база по visual contract
- прикладной handbook для ежедневной разработки и review

Если вопрос про то, "как должно быть", смотреть документы `01-05`.
Если вопрос про то, "как это делать в коде", смотреть документы `06-09`.
