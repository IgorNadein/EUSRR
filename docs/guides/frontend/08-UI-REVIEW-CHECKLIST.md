# Frontend Guide: UI Review Checklist

Этот документ нужен для self-check перед коммитом и для code review.

## 1. Geometry

- Используется ли базовая шкала радиусов?
- Нет ли нового `rounded-[...]` без отдельного обоснования?
- Не используется ли `rounded-md` там, где нужен normal control/card contract?
- Совпадает ли визуальный вес элементов одного типа?

## 2. Surfaces

- Понятно ли, где primary panel, а где secondary grouped block?
- Нет ли лишней вложенности `card inside card inside card`?
- Используются ли `app-surface`, `app-surface-elevated`, `app-surface-muted` по назначению?

## 3. Forms

- Форма собрана на `app-input` / `app-select` / shared select-паттернах?
- Понятно ли, какие поля главные, а какие вторичные?
- Не перегружена ли форма визуально?
- Согласован ли паттерн формы с её сценарием: CRUD, compose, filters, settings, dialog?

## 4. Dropdowns

- Если нужен поиск или multi-select, используется ли shared select?
- Не стилизован ли native `select` так, как будто это другой компонент?
- Совпадает ли affordance dropdown-поля с остальным приложением?

## 5. Actions

- Есть ли один очевидный primary action?
- Не спорят ли secondary и danger actions по визуальному весу с primary?
- Семантика destructive actions понятна?

## 6. Responsive

- Экран или модалка читаются на mobile без отдельной layout-ветки?
- Header/footer остаются удобными при длинном контенте?
- Нет ли случайного horizontal overflow?

## 7. API contract и frontend logic

- Не вычисляет ли фронтенд права доступа через устаревшие role-based эвристики?
- Там, где backend уже отдаёт семантический флаг, используется ли он напрямую?
- UI корректно скрывает действия, которые недоступны по business contract?

Особенно важно для:

- requests
- comments
- decision actions
- admin vs participant-only flows

## 8. Legacy

- Не копируется ли legacy-решение в новый код?
- Если legacy оставлен, понятна ли причина?
- Можно ли было безопасно привести участок к target state уже в этой задаче?

## 9. Decision

Если по checklist есть много “нет”, задача не считается просто “визуально нормальной”. Она должна либо быть доделана, либо иметь явный зафиксированный компромисс.
