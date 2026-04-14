# Руководства разработчика

Активные гайды и инструкции для работы с проектом.

## 📚 Доступные руководства

### Frontend UI система
- **[frontend/](frontend/)** - нормативная карта frontend UI-системы, геометрии, карточек, форм и модалок

### Frontend и UX
- **MODERN_DOCUMENT_UI.md** - ориентиры по UI системы документов
- **RECIPIENT_PICKER_UX_IMPROVEMENTS.md** - актуальный compose UX для формы заявлений

### Requests
- **REQUESTS_DETAIL_VIEW_GUIDE.md** - текущие правила detail view заявлений
- **testing-request-filters.md** - ручная проверка фильтров заявок

### Валидация
- **LIVE_VALIDATION_GUIDE.md** - живая валидация форм
- **NAME_VALIDATION.md** - валидация имен

### API и backend
- **API_TESTING_GUIDE.md** - тестирование API
- **API_V2_MIGRATION.md** - текущее состояние и контракт API v2
- **DJANGO_RULES_INTEGRATION.md** - object-level permissions через django-rules
- **DJANGO_CORS_SETUP.md** - CORS для frontend/backend

### Realtime и WebSocket
- **REALTIME_MIGRATION_GUIDE.md** - миграция на realtime
- **WEBSOCKET_UNIFIED_MIGRATION.md** - унифицированный WebSocket
- **WEBSOCKET_BACKEND_SETUP.md** - запуск backend с WebSocket

### Кэширование и оптимизация
- **CACHING_SETUP.md** - настройка кэша
- **MESSAGE_NOTIFICATIONS_OPTIMIZATION.md** - оптимизация уведомлений сообщений

### Infrastructure и deployment
- **CELERY_SETUP.md** - запуск Celery в development
- **CELERY_PRODUCTION_DEPLOY.md** - production deploy Celery

### Безопасность и доступ
- **IP_REGISTRATION_RESTRICTIONS.md** - ограничения регистрации
- **ldap-orm-mixins-usage.md** - использование LDAP ORM mixins
- **ldap-password-change-admin.md** - смена LDAP-паролей через админку

### Legacy / на пересмотр
- **CALENDAR_TESTING.md** - сценарии проверки календаря; содержит legacy-термины и требует отдельной ревизии
- **SCSS_QUICK_REFERENCE.md** - справка по старому SCSS-стеку; актуальна только для legacy-частей

## 🧹 Что удалено из `guides`

Как лишние или дублирующие документы удалены:

- `CALENDAR_LIBRARIES.md` - пустой файл
- `MESSENGER_QUICKSTART.md` - пустой файл
- `IP_RESTRICTIONS_README.md` - краткий дубль `IP_REGISTRATION_RESTRICTIONS.md`
- `CACHE_OPTIMIZATION_SUMMARY.md` - summary-дубль `CACHING_SETUP.md`

## 🎯 Использование

Этот каталог должен содержать только актуальные developer guides.

Правила:

- завершённые implementation reports лучше хранить в `docs/completed/` или `docs/reports/`
- активные нормативные документы и инструкции остаются в `docs/guides/`
- если guide устарел, его нужно либо переписать, либо удалить, а не оставлять рядом с актуальным
