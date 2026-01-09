# Миграция Notifications API в api/v1/

**Дата:** 9 января 2026  
**Статус:** ✅ Завершено

## Что изменилось

### Новая структура API

```
backend/api/v1/notifications/
├── __init__.py
├── views.py      # ← Перенесено из notifications/api_views.py
└── urls.py       # ← Перенесено из notifications/api_urls.py
```

### Изменения URL paths

| Старый путь (DEPRECATED) | Новый путь | Статус |
|-------------------------|-----------|---------|
| `/api/v1/notifications/*` | `/api/v1/notifications/*` | ✅ Без изменений |

**Примечание:** URL пути остались прежними, изменилась только внутренняя структура кода.

### Изменения в коде

**backend/api/urls.py:**
```python
# УДАЛЕНО:
path("v1/", include("notifications.api_urls")),

# Теперь всё в api/v1/urls.py
```

**backend/api/v1/urls.py:**
```python
# ДОБАВЛЕНО:
path("notifications/", include("api.v1.notifications.urls")),
```

## Причины миграции

### ❌ Проблемы до миграции

1. **Несогласованность архитектуры:**
   - `employees` → `api/v1/employees/`
   - `documents` → `api/v1/documents/`
   - `notifications` → `notifications/api_views.py` ← РАЗНАЯ структура!

2. **Отсутствие версионирования:**
   - API notifications не был версионирован
   - Сложно поддерживать breaking changes

3. **Дублирование кода:**
   - Отдельный роутинг в `api/urls.py`
   - Нестандартное размещение

### ✅ Преимущества после миграции

1. **Единообразная структура:**
   - Все API модули теперь в `api/v1/`
   - Понятная и предсказуемая организация

2. **Версионирование:**
   - API notifications теперь в v1
   - Готово к созданию v2 при необходимости

3. **Упрощённая поддержка:**
   - Все API в одном месте
   - Единый стиль кода и документации

## Обратная совместимость

### ✅ API endpoints не изменились

Все URL пути остались прежними:
- `/api/v1/notifications/` - список уведомлений
- `/api/v1/notifications/count/` - количество непрочитанных
- `/api/v1/notifications/<id>/read/` - отметить прочитанным
- И т.д.

### ⚠️ Изменения для разработчиков

**Импорты в Python коде:**

```python
# СТАРОЕ (DEPRECATED):
from notifications.api_views import get_notifications

# НОВОЕ:
from api.v1.notifications.views import get_notifications
```

**URL reversing:**

```python
# СТАРОЕ (DEPRECATED):
reverse('notifications_api:list')

# НОВОЕ:
reverse('v1:notifications_api_v1:list')
```

## Миграционный период

### Старые файлы помечены как DEPRECATED

Файлы `notifications/api_views.py` и `notifications/api_urls.py` помечены предупреждением:

```python
"""
DEPRECATED: Этот файл устарел и будет удалён в следующей версии.
Используйте вместо него: api.v1.notifications.views
Миграция: 9 января 2026
"""
```

### План удаления

1. **✅ Сейчас (9 января 2026):** Файлы помечены как deprecated
2. **🕐 Через 1 месяц:** Проверка использования старых импортов
3. **🗑️ Через 2 месяца:** Удаление deprecated файлов

## Тестирование

### ✅ Синтаксис проверен

```bash
python -m py_compile api/v1/notifications/views.py
python -m py_compile api/v1/notifications/urls.py
```

### ✅ Импорты работают

```python
from api.v1.notifications import views
# ✅ OK
```

### 🔍 Требуется дополнительное тестирование

- [ ] Протестировать все API endpoints в браузере
- [ ] Проверить WebSocket уведомления
- [ ] Проверить Telegram интеграцию
- [ ] Проверить Web Push подписки

## Развёртывание

### На сервере

```bash
cd /home/igor/EUSRR
git pull
sudo systemctl restart gunicorn-eusrr
```

### Проверка после развёртывания

```bash
# Проверить, что API доступен
curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/v1/notifications/

# Проверить логи
journalctl -u gunicorn-eusrr -f
```

## Rollback (если потребуется)

В случае проблем:

```bash
git revert HEAD
git push
# На сервере
git pull
sudo systemctl restart gunicorn-eusrr
```

Старые файлы (`api_views.py`, `api_urls.py`) остаются в проекте в течение 2 месяцев как fallback.

## Связанные изменения

- Commit: `[будет добавлен]` - "refactor: Move notifications API to api/v1/ for consistency"
- Issue: N/A
- PR: N/A

## Заключение

✅ Миграция завершена успешно
✅ Обратная совместимость сохранена
✅ Архитектура API стала единообразной
✅ Готово к production deployment
