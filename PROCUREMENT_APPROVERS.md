# Механизм назначения согласующих в заявках на закупку

## Как это работает

### 1. Определение требуемых ролей (модель `ProcurementRequest`)

Когда пользователь отправляет заявку на согласование (`submit` action), система определяет какие роли нужны:

```python
# в procurement/models.py - метод get_required_approvals()

cost = estimated_cost  # Сумма заявки

if cost < 10,000₽:                    # НИЗКАЯ
    → [DEPARTMENT_HEAD]               # Только руководитель отдела

elif cost < 100,000₽:                 # СРЕДНЯЯ  
    → [DEPARTMENT_HEAD,               # Руководитель отдела +
       FINANCE_MANAGER]               # Финансовый менеджер

else:                                 # ВЫСОКАЯ (> 100K)
    → [DEPARTMENT_HEAD,               # Руководитель отдела +
       FINANCE_MANAGER,               # Финансовый менеджер +
       DIRECTOR]                      # Генеральный директор
```

### 2. Поиск конкретных людей (вьюсет `ProcurementRequestViewSet.submit()`)

После определения ролей система ищет людей, занимающих эти должности:

```python
for role in required_approvals:
    approver = None
    
    if role == DEPARTMENT_HEAD:
        # ✅ Берёт руководителя из department.head
        approver = procurement_request.department.head
    
    elif role == FINANCE_MANAGER:
        # ✅ Ищет пользователя с правом change_budget
        approver = Employee.objects.filter(
            is_active=True,
            groups__permissions__codename='change_budget'
        ).first()
    
    elif role == DIRECTOR:
        # ✅ Берёт первого суперпользователя
        approver = Employee.objects.filter(
            is_superuser=True
        ).first()
    
    # Создаём запись согласования
    Approval.objects.create(
        request=procurement_request,
        approver=approver,
        role=role,
        status=ApprovalStatus.PENDING
    )
```

## Пример

### Заявка на 50,000₽ от отдела IT

```
Сумма: 50,000₽
Отдел: IT (руководитель = Петр Петров)

┌─────────────────────────────────────────┐
│ Определение ролей (get_required_approvals)
│ 10,000 < 50,000 < 100,000  
│ → [DEPARTMENT_HEAD, FINANCE_MANAGER]
└─────────────────────────────────────────┘
          ↓
┌─────────────────────────────────────────┐
│ Поиск согласующих (submit action)       │
├─────────────────────────────────────────┤
│ DEPARTMENT_HEAD                         │
│ → IT.head = Петр Петров ✓              │
│                                         │
│ FINANCE_MANAGER                         │
│ → Permission(change_budget)             │
│ → Мария Сидорова ✓                      │
└─────────────────────────────────────────┘
          ↓
┌─────────────────────────────────────────┐
│ Создание записей согласования           │
├─────────────────────────────────────────┤
│ Approval #1: Петр Петров (PENDING)     │
│ Approval #2: Мария Сидорова (PENDING)  │
└─────────────────────────────────────────┘
          ↓
       Уведомления
       ↙         ↖
   Петр         Мария
```

## Где это конфигурируется?

| Компонент | Где конфигурируется | Как |
|-----------|-------------------|-----|
| **Пороги сумм** | `procurement/constants.py` | APPROVAL_THRESHOLD_LOW, APPROVAL_THRESHOLD_HIGH |
| **Руководитель отдела** | Django Admin → Departments | Выбрать `head` в модели Department |
| **Финансовый менеджер** | Django Admin → Permissions | Дать permission `change_budget` пользователю или группе |
| **Директор** | Django Admin → Users | Сделать пользователя суперпользователем (`is_superuser=True`) |

## Потенциальные проблемы и решения

### 1. "Финансовый менеджер не найдена"
```python
# Причина: нет пользователя с правом change_budget
# Решение: 
Django Admin → Users → выбрать пользователя → добавить permission change_budget
```

### 2. "Директор не найден"
```python
# Причина: нет суперпользователей в системе
# Решение:
Django Admin → Users → выбрать пользователя → поставить галочку is_superuser
```

### 3. Разные согласующие для разных отделов
```python
# Текущая реализация: один финменеджер и один директор на всю компанию
# Чтобы сделать разных:
# 1. Создать модель ApprovalChain или DepartmentApprovalPolicy
# 2. Связать со своими финменеджерами и директорами
# 3. Изменить логику поиска в submit action
```

## API для отладки

### Проверить какие роли требуются для заявки
```bash
GET /api/procurement/requests/{id}/
# Ответ содержит поле "required_approvals" если его добавить в сериализатор
```

### Узнать кто назначен согласующим
```bash
GET /api/procurement/requests/{id}/
# approvals: [
#   { id, approver, role, status, comment }
# ]
```

## Параметры для настройки

```python
# backend/procurement/constants.py

APPROVAL_THRESHOLD_LOW = 10_000    # ← Можно менять
APPROVAL_THRESHOLD_HIGH = 50_000   # ← Можно менять

# Порог         | Рол требующиеся
# < 10K         | Руководитель отдела
# 10K - 50K     | Руководитель + Финансы
# > 50K         | Руководитель + Финансы + Директор
```
