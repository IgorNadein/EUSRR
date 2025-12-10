# Система бюджетов отделов в модуле закупок

## Где выставляется бюджет?

### 1️⃣ **Django Admin (Основное место)**

```
http://localhost:9000/admin/procurement/budget/
```

**Процесс:**
1. Перейти в Django Admin → Procurement → Budget
2. Нажать "Add budget"
3. Заполнить форму:
   - **Department** — выбрать отдел (IT, HR, финансы и т.д.)
   - **Year** — год (2025, 2026)
   - **Quarter** — квартал (1, 2, 3, 4)
   - **Allocated amount** — сумма выделенного бюджета в рублях
   - **Spent amount** — (заполняется автоматически, если оставить 0)

### 2️⃣ **REST API (для приложений)**

**Создание бюджета:**
```bash
POST /api/procurement/budgets/
Content-Type: application/json

{
  "department": 5,              # ID отдела
  "year": 2025,
  "quarter": 4,
  "allocated_amount": "500000.00"
}
```

**Редактирование:**
```bash
PATCH /api/procurement/budgets/1/
{
  "allocated_amount": "600000.00"
}
```

**Получение текущего квартала:**
```bash
GET /api/procurement/budgets/current_quarter/
```

**Получить бюджет своего отдела:**
```bash
GET /api/procurement/budgets/my-department/
```

## Структура модели Budget

```python
class Budget(models.Model):
    department          # ForeignKey на Department
    year               # 2025, 2026, ...
    quarter            # 1, 2, 3, 4
    allocated_amount   # Выделено денег (основное число!)
    spent_amount       # Потрачено (меняется при одобрении заявок)
    created_at         # Когда создан
    updated_at         # Когда обновлён
```

**Ключевое свойство:** `(department, year, quarter)` — уникальный набор!
```
Нельзя создать два бюджета для одного отдела на один период!
```

## Примеры бюджетов

### Компания с 3 отделами на Q4 2025:

```
┌────────────────┬──────┬─────────┬──────────────┐
│ Отдел          │ 2025 │ Q4      │ Бюджет       │
├────────────────┼──────┼─────────┼──────────────┤
│ IT             │ 2025 │ 4       │ 1,000,000₽   │
│ HR             │ 2025 │ 4       │   300,000₽   │
│ Финансы        │ 2025 │ 4       │   500,000₽   │
│ Маркетинг      │ 2025 │ 4       │   250,000₽   │
└────────────────┴──────┴─────────┴──────────────┘
```

## Как работает проверка бюджета?

Когда пользователь отправляет заявку на согласование:

```python
# 1. Система получает текущий квартал
now = timezone.now()
quarter = (now.month - 1) // 3 + 1

# 2. Ищет бюджет отдела на этот период
budget = Budget.objects.get(
    department=procurement_request.department,
    year=now.year,
    quarter=quarter
)

# 3. Проверяет остаток
remaining = budget.remaining_amount  # allocated - spent
if remaining >= procurement_request.estimated_cost:
    # ✅ Можно отправить на согласование
else:
    # ❌ Недостаточно бюджета
    return error
```

## Ключевые свойства Budget

```python
# Остаток бюджета
remaining_amount = allocated_amount - spent_amount

# Зарезервировано (pending заявки)
reserved_amount = sum(pending_requests.estimated_cost)

# Доступно с учётом резерва
available_amount = remaining_amount - reserved_amount

# Процент использования
utilization_percentage = (spent_amount / allocated_amount) * 100

# Можно ли потратить X?
can_spend(amount: Decimal) → bool
```

## Пример в коде

```python
# Проверка в views.py при отправке заявки
available, remaining = procurement_request.check_budget_available()

if not available:
    return Response({
        'error': 'Недостаточно бюджета',
        'required': float(procurement_request.estimated_cost),
        'remaining': float(remaining),
    }, status=400)
```

## Алерты при низком бюджете

Система автоматически отправляет уведомления руководителю отдела:

```python
# budget_low (остаток < 20%)
"Бюджет отдела снижается. Остаток: 45,000₽ (18%)"

# budget_critical (остаток < 10%)  
"⚠️ Критически низкий бюджет! Остаток: 8,000₽ (3%)"
```

**Когда:** При одобрении заявки если бюджет падает ниже порогов

## Как менять бюджет?

### ✅ Правильно (сумма выделенного):
```
Отдел IT на Q4 2025: 1,000,000₽
Потом изменили: 1,500,000₽ (увеличили бюджет)
```

### ❌ Неправильно (not spent_amount):
```
❌ Не меняйте spent_amount вручную - это меняется автоматически
```

## Права доступа

| Action | Кто может |
|--------|-----------|
| Создать бюджет | `CanManageBudget` (админ) |
| Редактировать | `CanManageBudget` (админ) |
| Удалить | `CanManageBudget` (админ) |
| Просмотреть свой | Руководитель отдела |
| Просмотреть все | Суперпользователь/Админ |

## Типичный цикл

```
Q1 2025: Выделили IT-отделу 1,000,000₽
    ↓
Заявка #1: 50,000₽ → одобрена
Заявка #2: 100,000₽ → одобрена
Zaявка #3: 30,000₽ → одобрена
    ↓
Потрачено: 180,000₽
Остаток: 820,000₽
Использовано: 18%
    ↓
Q2 2025: Новый квартал, новый бюджет
```

## SQL для статистики

```sql
-- Сколько потрачено каждый отдел на Q4 2025?
SELECT 
    d.name,
    b.allocated_amount,
    b.spent_amount,
    (b.allocated_amount - b.spent_amount) as remaining
FROM procurement_budget b
JOIN employees_department d ON b.department_id = d.id
WHERE b.year = 2025 AND b.quarter = 4;

-- Самый загруженный отдел по бюджету
SELECT 
    d.name,
    b.allocated_amount,
    (b.spent_amount::float / b.allocated_amount * 100) as utilization
FROM procurement_budget b
JOIN employees_department d ON b.department_id = d.id
WHERE b.year = 2025
ORDER BY utilization DESC;
```

## Интеграция с заявками

```
ProcurementRequest (заявка)
    ├─ department_id
    ├─ estimated_cost
    └─ check_budget_available()
        ↓ ищет
    Budget (бюджет)
        ├─ department
        ├─ allocated_amount
        └─ spent_amount
```

## Автоматические обновления spent_amount

```python
# На данный момент spent_amount меняется вручную в:
# - Django Admin
# - API PATCH запрос

# В будущем можно автоматизировать при:
# - Завершении заявки (status=COMPLETED)
# - Поступлении счёта (через другую модель Invoice)
```
