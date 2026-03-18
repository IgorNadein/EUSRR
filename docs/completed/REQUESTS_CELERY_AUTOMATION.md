# Автоматизация кадровых событий через Celery

**Дата**: 17 марта 2026 г.  
**Статус**: ✅ Реализовано

## Что сделано

Реализована **полная автоматизация** создания кадровых событий из заявок с использованием **Celery + Redis**.

## Архитектура

### 3 стратегии обработки заявок:

```
┌─────────────────────────────────────────────┐
│  1. НЕМЕДЛЕННЫЕ (dismissal, transfer)       │
│     ↓ approve() → Signal → EmployeeAction   │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│  2. ОТЛОЖЕННЫЕ (vacation, sick_leave)       │
│     ↓ approve() → Signal → Celery Task      │
│     ↓ date_from → EmployeeAction            │
└─────────────────────────────────────────────┘

┌─────────────────────────────────────────────┐
│  3. АВТОВОЗВРАТ (vacation, sick_leave)      │
│     ↓ date_to + 1 день → Celery Task        │
│     ↓ EmployeeAction (returned_from_leave)  │
└─────────────────────────────────────────────┘
```

---

## Файлы

### 1. `requests_app/tasks.py` - Celery задачи

**Задачи**:
- `create_scheduled_action()` - создает событие в date_from
- `schedule_auto_return()` - создает событие возврата в date_to + 1
- `cleanup_missed_returns()` - periodic task для восстановления пропущенных

### 2. `requests_app/signals.py` - обработчик одобрения

**Логика**:
- Отслеживает переход в APPROVED
- Немедленные типы → создает сразу
- Отложенные типы → планирует через Celery

### 3. `eusrr_backend/celery.py` - Celery beat schedule

**Periodic tasks**:
- `cleanup-missed-returns` - каждый день в 00:05

---

## Таблица автоматизации

| Заявка | Событие начала | Когда | Событие возврата | Когда |
|--------|----------------|-------|------------------|-------|
| **dismissal** | `dismissed` | ✅ Сразу при approve | - | - |
| **transfer** | `transferred` | ✅ Сразу при approve | - | - |
| **vacation** | `on_leave` | 🕐 В `date_from` | `returned_from_leave` | 🕐 `date_to` + 1 день |
| **sick_leave** | `on_sick_leave` | 🕐 В `date_from` | `returned_from_leave` | 🕐 `date_to` + 1 день |
| **day_off** | - | ❌ Не создается | - | - |
| **other** | - | ❌ Не создается | - | - |

---

## Примеры работы

### Пример 1: Увольнение (немедленное)

```python
# 17 марта - создаем заявку
request = Request.objects.create(
    employee=user,
    type='dismissal',
    date_from='2026-04-01'
)

# 17 марта - HR одобряет
request.approve(hr_manager)

# ✅ СРАЗУ создано EmployeeAction(action='dismissed')
# ✅ employee.is_active = False
# ✅ LDAP sync выполнен
```

### Пример 2: Отпуск (отложенное)

```python
# 17 марта - создаем заявку на отпуск 1-14 апреля
request = Request.objects.create(
    employee=user,
    type='vacation',
    date_from='2026-04-01',
    date_to='2026-04-14'
)

# 17 марта - HR одобряет
request.approve(hr_manager)
# ✅ Celery task запланирован на 01.04.2026 00:00

# 1 апреля 00:00 - Celery автоматически:
# ✅ Создает EmployeeAction(action='on_leave')
# ✅ Планирует автовозврат на 15.04.2026 00:00

# 15 апреля 00:00 - Celery автоматически:
# ✅ Создает EmployeeAction(action='returned_from_leave')
```

### Пример 3: Отпуск начинается сегодня

```python
# 17 марта - создаем заявку с date_from=сегодня
request = Request.objects.create(
    employee=user,
    type='vacation',
    date_from='2026-03-17',  # Сегодня!
    date_to='2026-03-24'
)

# 17 марта - HR одобряет
request.approve(hr_manager)
# ✅ Событие создается СРАЗУ (не через Celery)
# ✅ Автовозврат запланирован на 25.03.2026
```

---

## Защита от ошибок

### 1. **Idempotency** (защита от дублей)
```python
# Проверка перед созданием
if EmployeeAction.objects.filter(
    extra__request_id=request_id,
    action=action_type
).exists():
    return  # Уже создано
```

### 2. **Retry логика**
```python
@shared_task(bind=True, max_retries=3)
def create_scheduled_action(self, request_id):
    try:
        # ... создание
    except Exception as e:
        # Retry через 5 минут
        raise self.retry(exc=e, countdown=300)
```

### 3. **Cleanup task** (восстановление пропущенных)
```python
# Каждый день в 00:05 проверяет:
# - Заявки, которые закончились, но нет события возврата
# - Создает пропущенные события
```

### 4. **Отмена заявки**
```python
# Если заявку отменили до date_from:
# - Celery task выполнится
# - Проверит статус: if status != APPROVED: return
# - Событие НЕ будет создано
```

---

## Метаданные в extra

Каждое созданное событие содержит:

```python
# Немедленное событие
extra = {
    'request_id': 123,
    'approved_by': 5,
    'immediate': True
}

# Отложенное событие
extra = {
    'request_id': 123,
    'approved_by': 5,
    'scheduled': True
}

# Автовозврат
extra = {
    'request_id': 123,
    'auto_return': True
}

# Восстановленное cleanup'ом
extra = {
    'request_id': 123,
    'auto_return': True,
    'cleanup': True
}
```

---

## Запуск

### Celery Worker
```bash
cd backend
celery -A eusrr_backend worker -l info
```

### Celery Beat (для periodic tasks)
```bash
celery -A eusrr_backend beat -l info
```

### Одной командой (для разработки)
```bash
celery -A eusrr_backend worker -B -l info
```

---

## Мониторинг

### Flower (Celery monitoring)
```bash
celery -A eusrr_backend flower
# http://localhost:5555
```

### Проверка задач
```python
from celery import current_app

# Посмотреть запланированные задачи
current_app.control.inspect().scheduled()

# Посмотреть активные задачи
current_app.control.inspect().active()
```

---

## Расширение

### Добавить новый тип (например, декрет)

**1. Обновить маппинг**:
```python
# requests_app/signals.py
SCHEDULED_ACTION_MAPPING = {
    "vacation": "on_leave",
    "sick_leave": "on_sick_leave",
    "maternity": "on_maternity",  # ← Добавить
}
```

**2. Обновить tasks.py**:
```python
# В create_scheduled_action
action_mapping = {
    'vacation': 'on_leave',
    'sick_leave': 'on_sick_leave',
    'maternity': 'on_maternity',  # ← Добавить
}

# В schedule_auto_return
return_mapping = {
    'vacation': 'returned_from_leave',
    'sick_leave': 'returned_from_leave',
    'maternity': 'returned_from_maternity',  # ← Добавить
}
```

**3. Добавить тип в RequestType**:
```python
# requests_app/enums.py
class RequestType(TextChoices):
    # ...
    MATERNITY = "maternity", "Декрет"
```

**Всё!** Автоматизация заработает для нового типа.

---

## Логирование

Все действия логируются:

```
INFO: Scheduled EmployeeAction creation for Request #123 at 2026-04-01 00:00:00
INFO: Created scheduled EmployeeAction #456 (on_leave) for Request #123
INFO: Created auto-return EmployeeAction #457 (returned_from_leave) for Request #123
INFO: cleanup_missed_returns completed: 2 actions created
```

---

## Преимущества решения

✅ **Автоматизация** - все работает без ручного вмешательства  
✅ **Гибкость** - можно отменить заявку до date_from  
✅ **Надежность** - retry + cleanup task  
✅ **Масштабируемость** - Celery + Redis  
✅ **Audittrail** - все события с метаданными  
✅ **Расширяемость** - легко добавить новые типы  
✅ **Event-driven** - декаплинг через сигналы  

---

**Автор**: GitHub Copilot  
**Дата**: 17 марта 2026 г.
