# Анализ Возможности Миграции Календарей

**Дата:** 27 февраля 2026 г.  
**Цель:** Определить возможность миграции данных из `calendar_app` в `schedule` (django-scheduler)

---

## 📋 Сравнение Систем

### Старая Система: `calendar_app`

#### Models:

**1. Calendar** (настраиваемые календари)
```python
class Calendar(models.Model):
    title = CharField(max_length=200)
    description = TextField(blank=True)
    color = CharField(max_length=7, default="#0d6efd")
    icon = CharField(max_length=50, blank=True)
    
    # Владение (опциональное!)
    owner_user = ForeignKey(User, null=True, blank=True)
    owner_department = ForeignKey(Department, null=True, blank=True)
    
    # Настройки видимости
    visibility = CharField(choices=CalendarVisibility.choices)
    default_can_edit = BooleanField(default=False)
    
    # Автоподписка
    auto_subscribe_new_users = BooleanField(default=False)
    auto_subscribe_department_members = BooleanField(default=False)
    
    is_active = BooleanField(default=True)
```

**Типы календарей:**
- **Глобальный** (owner_user=NULL, owner_department=NULL)
- **Личный** (owner_user задан)
- **Отдела** (owner_department задан)

**2. CalendarEvent** (события)
```python
class CalendarEvent(models.Model):
    # ✨ КЛЮЧЕВОЕ: calendar может быть NULL!
    calendar = ForeignKey(Calendar, null=True, blank=True)
    
    # LEGACY поля (работают если calendar=NULL):
    department = ForeignKey(Department, null=True, blank=True)
    employee = ForeignKey(User, null=True, blank=True)
    
    # Основное
    title = CharField(max_length=200)
    description = TextField(blank=True)
    
    # Даты
    start_date = DateField()
    end_date = DateField(null=True, blank=True)
    start_time = TimeField(null=True, blank=True)
    end_time = TimeField(null=True, blank=True)
    all_day = BooleanField(default=True)
    
    # Повторяемость (custom implementation)
    recurrence = CharField(choices=Recurrence.choices, default="one_time")
    recurrence_interval = PositiveSmallIntegerField(default=1)
    recurrence_count = PositiveIntegerField(null=True, blank=True)
    recurrence_until = DateField(null=True, blank=True)
    weekdays_mask = PositiveSmallIntegerField(default=0)
    
    # Отображение
    color = CharField(max_length=7, blank=True)
    location = CharField(max_length=200, blank=True)
    source = CharField(max_length=120, blank=True)
```

**ЛОГИКА СОБЫТИЯ (если calendar=NULL):**
```python
# department = NULL и employee = NULL → событие компании (глобальное)
# department задан и employee = NULL → событие отдела
# employee задан и department = NULL → личное событие сотрудника
```

**3. CalendarSubscription** (подписки)
```python
class CalendarSubscription(models.Model):
    calendar = ForeignKey(Calendar)
    user = ForeignKey(User)
    
    is_visible = BooleanField(default=True)
    color_override = CharField(max_length=7, blank=True, null=True)
    
    can_edit = BooleanField(default=False)
    can_manage = BooleanField(default=False)
    
    notify_on_new_event = BooleanField(default=True)
    notify_on_event_change = BooleanField(default=True)
```

---

### Новая Система: `schedule` (django-scheduler)

#### Models:

**1. Calendar**
```python
class Calendar(models.Model):
    name = CharField(max_length=200)
    slug = SlugField(max_length=200, unique=True)
    
    # ❌ НЕТ явных полей для владельца!
    # Владение управляется через CalendarRelation
```

**2. Event**
```python
class Event(models.Model):
    # ⚠️ КРИТИЧНО: calendar всегда ОБЯЗАТЕЛЕН!
    calendar = ForeignKey(Calendar, on_delete=CASCADE)
    
    # Основное
    title = CharField(max_length=255)
    description = TextField(blank=True)
    
    # Даты (datetime-based)
    start = DateTimeField()
    end = DateTimeField()
    
    # Повторяемость (через Rule - RFC 5545 rrule)
    rule = ForeignKey(Rule, null=True, blank=True)
    end_recurring_period = DateTimeField(null=True, blank=True)
    
    # Отображение
    color_event = CharField(max_length=10, blank=True, null=True)
```

**⚠️ ВАЖНО:** Event ВСЕГДА требует Calendar. Нельзя создать событие без календаря!

**3. Rule** (повторяющиеся события - RFC 5545)
```python
class Rule(models.Model):
    name = CharField(max_length=32)
    description = TextField()
    frequency = CharField(max_length=10)  # YEARLY, MONTHLY, WEEKLY, DAILY, ...
    params = TextField(blank=True, null=True)  # "byweekday:0,4;interval:1"
```

**4. CalendarRelation** (связи календарей)
```python
class CalendarRelation(models.Model):
    calendar = ForeignKey(Calendar)
    content_type = ForeignKey(ContentType)
    object_id = PositiveIntegerField()
    content_object = GenericForeignKey('content_type', 'object_id')
    
    distinction = CharField(max_length=20)  # 'owner', 'editor', 'viewer'
    inheritable = BooleanField(default=True)
```

**Типы distinction:**
- `owner` - владелец (может управлять календарем)
- `editor` - редактор (может создавать/редактировать события)
- `viewer` - наблюдатель (только просмотр)

---

## 🔍 Ключевые Различия

| Аспект | calendar_app | schedule (django-scheduler) |
|--------|-------------|---------------------------|
| **События без календаря** | ✅ Поддерживается (legacy) | ❌ Невозможно |
| **Системные календари** | ✅ Глобальный/Личный/Отдела через owner_* | ⚠️ Через CalendarRelation |
| **Повторяемость** | Custom (weekdays_mask, interval) | RFC 5545 rrule (Rule model) |
| **Даты** | Separate date+time fields | Combined datetime |
| **Владение** | owner_user, owner_department fields | CalendarRelation (generic) |
| **Подписки** | CalendarSubscription model | CalendarRelation (distinction) |
| **Цвет** | Per-event color field | color_event field |
| **Видимость** | visibility choices + auto_subscribe | Через CalendarRelation |

---

## ⚠️ Проблемы Миграции

### 1. События БЕЗ Календаря (Legacy Events)

**Проблема:** В `calendar_app` события могут существовать БЕЗ привязки к Calendar:

```python
# Глобальное событие компании
event = CalendarEvent.objects.create(
    title="Корпоратив",
    start_date=date.today(),
    # calendar=NULL, department=NULL, employee=NULL
)

# Событие отдела
event = CalendarEvent.objects.create(
    title="Планёрка отдела",
    department=sales_dept,
    # calendar=NULL, employee=NULL
)

# Личное событие
event = CalendarEvent.objects.create(
    title="День рождения",
    employee=user,
    # calendar=NULL, department=NULL
)
```

**В django-scheduler:** Event ВСЕГДА требует Calendar!

**Решение:** Создать системные календари при миграции:

1. **"Календарь компании"** (глобальный)
   - Для событий где: `calendar=NULL, department=NULL, employee=NULL`
   - CalendarRelation: все пользователи как viewers

2. **"Календарь отдела {name}"** (один на отдел)
   - Для событий где: `calendar=NULL, department=X, employee=NULL`
   - CalendarRelation: члены отдела как viewers, руководитель как owner

3. **"Личный календарь {username}"** (один на пользователя)
   - Для событий где: `calendar=NULL, department=NULL, employee=X`
   - CalendarRelation: пользователь как owner

### 2. Повторяемость (Recurrence)

**Проблема:** Разные форматы повторяемости

**calendar_app:**
```python
recurrence = "weekly"
recurrence_interval = 2
weekdays_mask = 5  # Пн + Чт (1 + 4 = 5)
recurrence_until = date(2026, 12, 31)
```

**django-scheduler:**
```python
rule = Rule.objects.create(
    name="Weekly Mon+Thu",
    frequency="WEEKLY",
    params="byweekday:0,3;interval:2;until:20261231"  # RFC 5545
)
event.rule = rule
event.end_recurring_period = datetime(2026, 12, 31, 23, 59, 59)
```

**Маппинг:**

| calendar_app | django-scheduler RFC 5545 |
|--------------|--------------------------|
| `one_time` | No Rule (rule=NULL) |
| `hourly` | `frequency='HOURLY'` + `interval` |
| `daily` | `frequency='DAILY'` + `interval` |
| `weekly` | `frequency='WEEKLY'` + `byweekday` |
| `monthly` | `frequency='MONTHLY'` + `interval` |
| `annual` | `frequency='YEARLY'` + `interval` |

**Конвертация weekdays_mask:**
```python
# calendar_app: битовая маска (1=Пн, 2=Вт, 4=Ср, 8=Чт, 16=Пт, 32=Сб, 64=Вс)
# django-scheduler: список [0=Mon, 1=Tue, 2=Wed, 3=Thu, 4=Fri, 5=Sat, 6=Sun]

def convert_weekdays_mask(mask):
    days = []
    if mask & 1: days.append(0)    # Пн
    if mask & 2: days.append(1)    # Вт
    if mask & 4: days.append(2)    # Ср
    if mask & 8: days.append(3)    # Чт
    if mask & 16: days.append(4)   # Пт
    if mask & 32: days.append(5)   # Сб
    if mask & 64: days.append(6)   # Вс
    return days
```

### 3. Даты: Date+Time vs DateTime

**Проблема:** Разные представления времени

**calendar_app:**
```python
start_date = date(2026, 3, 1)
start_time = time(10, 30)  # может быть NULL
all_day = False
```

**django-scheduler:**
```python
start = datetime(2026, 3, 1, 10, 30)  # всегда datetime
end = datetime(2026, 3, 1, 12, 0)     # всегда datetime
```

**Конвертация:**
```python
from django.utils import timezone

if event.all_day:
    # Событие на весь день: 00:00 - 23:59
    start = timezone.make_aware(datetime.combine(event.start_date, time(0, 0)))
    end_date = event.end_date or event.start_date
    end = timezone.make_aware(datetime.combine(end_date, time(23, 59, 59)))
else:
    # Событие с точным временем
    start = timezone.make_aware(datetime.combine(event.start_date, event.start_time))
    end_date = event.end_date or event.start_date
    end_time = event.end_time or event.start_time
    end = timezone.make_aware(datetime.combine(end_date, end_time))
```

### 4. CalendarSubscription → CalendarRelation

**Проблема:** Разные модели для подписок

**calendar_app:**
```python
subscription = CalendarSubscription.objects.create(
    calendar=cal,
    user=user,
    can_edit=True,
    can_manage=False,
    is_visible=True,
    color_override="#FF0000",
    notify_on_new_event=True
)
```

**django-scheduler:**
```python
# CalendarRelation НЕ хранит:
# - color_override
# - notify_on_new_event
# - is_visible

relation = CalendarRelation.objects.create(
    calendar=cal,
    content_type=ContentType.objects.get_for_model(User),
    object_id=user.id,
    distinction='editor',  # can_edit=True → editor
    inheritable=True
)
```

**Маппинг distinction:**
```python
if subscription.can_manage:
    distinction = 'owner'
elif subscription.can_edit:
    distinction = 'editor'
else:
    distinction = 'viewer'
```

**❌ ПОТЕРЯ ДАННЫХ:**
- `color_override` - персональные цвета календарей
- `is_visible` - скрытые календари
- `notify_on_new_event`, `notify_on_event_change` - настройки уведомлений

**Решение:** Сохранить legacy таблицу CalendarSubscription или создать расширение для django-scheduler.

---

## ✅ Возможна ли Миграция?

### Ответ: **ДА, но с оговорками**

Миграция **технически возможна**, НО:

#### ✅ Что можно мигрировать:

1. **Calendar → Calendar**
   - ✅ Основные поля (title → name, description, color)
   - ✅ Создание slug из title
   - ⚠️ Владение через CalendarRelation (owner_user, owner_department)

2. **CalendarEvent → Event**
   - ✅ Основные поля (title, description, location)
   - ✅ Даты (date+time → datetime)
   - ✅ Цвет (color → color_event)
   - ✅ Legacy события (создать системные календари)

3. **Повторяемость → Rule**
   - ✅ Конвертация recurrence → RFC 5545
   - ✅ Маппинг weekdays_mask → byweekday
   - ✅ recurrence_until → end_recurring_period

4. **CalendarSubscription → CalendarRelation**
   - ✅ Базовая связь (calendar + user)
   - ✅ Права (can_edit/can_manage → distinction)

#### ❌ Что будет потеряно:

1. **Настройки CalendarSubscription:**
   - ❌ `color_override` - персональные цвета
   - ❌ `is_visible` - скрытие календарей
   - ❌ `notify_on_new_event` - настройки уведомлений
   - ❌ `notify_on_event_change`

2. **Настройки Calendar:**
   - ❌ `default_can_edit` - права по умолчанию
   - ❌ `auto_subscribe_new_users` - автоподписка
   - ❌ `auto_subscribe_department_members`
   - ❌ `is_active` - деактивация календарей

3. **Метаданные CalendarEvent:**
   - ❌ `source` - технический ключ связи (employee:123:birthday)
   - ⚠️ `created_by` - авторство события (можно сохранить в description)

#### ⚠️ Риски:

1. **Потеря функционала:**
   - Пользователи потеряют персональные цвета календарей
   - Пользователи потеряют настройки уведомлений
   - Потеря автоподписки на календари

2. **Изменение поведения:**
   - Legacy события будут перемещены в системные календари
   - События отделов будут в отдельных календарях (вместо фильтра по department)
   - Невозможность создать событие без календаря

3. **Сложность rollback:**
   - Обратная миграция СЛОЖНАЯ (потеря данных)
   - Нужно сохранить старые таблицы для возможности отката

---

## 🎯 Рекомендованная Стратегия

### Вариант A: Полная Замена (РИСКОВАННО ⚠️)

**Шаги:**
1. Создать backup БД
2. Создать системные календари (глобальный + по отделам + личные)
3. Мигрировать CalendarEvent → Event (с созданием Rule для повторяющихся)
4. Мигрировать Calendar → Calendar (с CalendarRelation)
5. Мигрировать CalendarSubscription → CalendarRelation
6. Переключить API endpoints на `/api/v1/schedule/`
7. Обновить Frontend

**Проблемы:**
- ❌ Потеря функционала (см. выше)
- ❌ Breaking changes для пользователей
- ❌ Сложный rollback

### Вариант B: Параллельная Работа (РЕКОМЕНДУЕТСЯ ✅)

**Идея:** Обе системы работают параллельно, постепенный переход

**Шаги:**
1. ✅ Оставить `calendar_app` как legacy (read-only)
2. ✅ Новые события создаются только в `schedule`
3. ✅ Frontend показывает ОБЕ системы (merged view)
4. ✅ Постепенная миграция пользователей (opt-in)
5. ✅ Через 3-6 месяцев: полное отключение `calendar_app`

**Преимущества:**
- ✅ Нет потери данных
- ✅ Возможность отката
- ✅ Постепенная адаптация пользователей
- ✅ Проверка django-scheduler в продакшене

**Недостатки:**
- ⚠️ Поддержка двух систем (временно)
- ⚠️ Сложность Frontend (две API)

### Вариант C: Гибрид (НЕ РЕКОМЕНДУЕТСЯ ❌)

Создать обертку над `calendar_app`, которая использует django-scheduler внутри, но сохраняет интерфейс.

**Проблемы:**
- ❌ Сложность поддержки
- ❌ Потеря преимуществ django-scheduler
- ❌ Непонятная архитектура

---

## 📝 Пример Миграции (Data Migration)

```python
# backend/calendar_app/migrations/00XX_migrate_to_django_scheduler.py

from django.db import migrations
from django.utils import timezone
from datetime import datetime, time
from django.contrib.contenttypes.models import ContentType


def migrate_calendars_forward(apps, schema_editor):
    """Мигрирует данные из calendar_app в schedule."""
    
    # Old models
    OldCalendar = apps.get_model('calendar_app', 'Calendar')
    OldCalendarEvent = apps.get_model('calendar_app', 'CalendarEvent')
    OldCalendarSubscription = apps.get_model('calendar_app', 'CalendarSubscription')
    
    # New models
    NewCalendar = apps.get_model('schedule', 'Calendar')
    NewEvent = apps.get_model('schedule', 'Event')
    NewRule = apps.get_model('schedule', 'Rule')
    CalendarRelation = apps.get_model('schedule', 'CalendarRelation')
    
    Employee = apps.get_model('employees', 'Employee')
    Department = apps.get_model('employees', 'Department')
    
    user_ct = ContentType.objects.get_for_model(Employee)
    dept_ct = ContentType.objects.get_for_model(Department)
    
    print("\n=== MIGRATION START ===\n")
    
    # 1. Создать системные календари
    print("1. Creating system calendars...")
    
    # Глобальный календарь компании
    company_cal, _ = NewCalendar.objects.get_or_create(
        slug='company',
        defaults={'name': 'Календарь компании'}
    )
    print(f"  ✅ Company calendar: {company_cal.name}")
    
    # Календари отделов
    dept_calendars = {}
    for dept in Department.objects.all():
        slug = f'dept-{dept.id}'
        cal, _ = NewCalendar.objects.get_or_create(
            slug=slug,
            defaults={'name': f'Календарь отдела {dept.name}'}
        )
        dept_calendars[dept.id] = cal
        
        # CalendarRelation: владелец отдела
        if dept.head_id:
            CalendarRelation.objects.get_or_create(
                calendar=cal,
                content_type=user_ct,
                object_id=dept.head_id,
                distinction='owner'
            )
        
        # CalendarRelation: члены отдела как viewers
        for member in dept.employees.filter(is_active=True):
            CalendarRelation.objects.get_or_create(
                calendar=cal,
                content_type=user_ct,
                object_id=member.id,
                distinction='viewer'
            )
        
        print(f"  ✅ Department calendar: {cal.name}")
    
    # Личные календари пользователей
    personal_calendars = {}
    for user in Employee.objects.filter(is_active=True):
        slug = f'personal-{user.id}'
        cal, _ = NewCalendar.objects.get_or_create(
            slug=slug,
            defaults={'name': f'Личный календарь {user.get_full_name()}'}
        )
        personal_calendars[user.id] = cal
        
        # CalendarRelation: владелец
        CalendarRelation.objects.get_or_create(
            calendar=cal,
            content_type=user_ct,
            object_id=user.id,
            distinction='owner'
        )
        print(f"  ✅ Personal calendar: {cal.name}")
    
    print(f"\nCreated {1 + len(dept_calendars) + len(personal_calendars)} system calendars\n")
    
    # 2. Мигрировать пользовательские календари
    print("2. Migrating custom calendars...")
    
    calendar_mapping = {}  # old_id → new_calendar
    
    for old_cal in OldCalendar.objects.all():
        slug = f'legacy-{old_cal.id}'
        new_cal = NewCalendar.objects.create(
            name=old_cal.title,
            slug=slug
        )
        calendar_mapping[old_cal.id] = new_cal
        
        # CalendarRelation: владелец
        if old_cal.owner_user_id:
            CalendarRelation.objects.create(
                calendar=new_cal,
                content_type=user_ct,
                object_id=old_cal.owner_user_id,
                distinction='owner'
            )
        elif old_cal.owner_department_id:
            # Владелец отдела = руководитель
            dept = old_cal.owner_department
            if dept.head_id:
                CalendarRelation.objects.create(
                    calendar=new_cal,
                    content_type=user_ct,
                    object_id=dept.head_id,
                    distinction='owner'
                )
        
        print(f"  ✅ Migrated: {old_cal.title}")
    
    print(f"\nMigrated {len(calendar_mapping)} custom calendars\n")
    
    # 3. Мигрировать события
    print("3. Migrating events...")
    
    migrated_count = 0
    skipped_count = 0
    
    for old_event in OldCalendarEvent.objects.all():
        try:
            # Определить целевой календарь
            if old_event.calendar_id:
                # Событие в пользовательском календаре
                target_cal = calendar_mapping.get(old_event.calendar_id)
            elif old_event.employee_id:
                # Личное событие
                target_cal = personal_calendars.get(old_event.employee_id)
            elif old_event.department_id:
                # Событие отдела
                target_cal = dept_calendars.get(old_event.department_id)
            else:
                # Глобальное событие компании
                target_cal = company_cal
            
            if not target_cal:
                print(f"  ⚠️ No target calendar for event: {old_event.title}")
                skipped_count += 1
                continue
            
            # Конвертация даты+время → datetime
            if old_event.all_day:
                start_dt = timezone.make_aware(
                    datetime.combine(old_event.start_date, time(0, 0))
                )
                end_date = old_event.end_date or old_event.start_date
                end_dt = timezone.make_aware(
                    datetime.combine(end_date, time(23, 59, 59))
                )
            else:
                start_dt = timezone.make_aware(
                    datetime.combine(old_event.start_date, old_event.start_time)
                )
                end_date = old_event.end_date or old_event.start_date
                end_time = old_event.end_time or old_event.start_time
                end_dt = timezone.make_aware(
                    datetime.combine(end_date, end_time)
                )
            
            # Создать Rule если есть повторяемость
            rule = None
            if old_event.recurrence != 'one_time':
                rule = create_rule_from_recurrence(
                    apps, old_event.recurrence, old_event.recurrence_interval,
                    old_event.weekdays_mask, old_event.recurrence_until,
                    old_event.recurrence_count, old_event.title
                )
            
            # Создать новое событие
            new_event = NewEvent.objects.create(
                calendar=target_cal,
                title=old_event.title,
                description=old_event.description,
                start=start_dt,
                end=end_dt,
                rule=rule,
                end_recurring_period=timezone.make_aware(
                    datetime.combine(old_event.recurrence_until, time(23, 59, 59))
                ) if old_event.recurrence_until else None,
                color_event=old_event.color if old_event.color else None,
            )
            
            migrated_count += 1
            
            if migrated_count % 100 == 0:
                print(f"  ... {migrated_count} events migrated")
        
        except Exception as e:
            print(f"  ❌ Error migrating event '{old_event.title}': {e}")
            skipped_count += 1
    
    print(f"\n✅ Migrated {migrated_count} events")
    print(f"⚠️ Skipped {skipped_count} events\n")
    
    # 4. Мигрировать подписки
    print("4. Migrating subscriptions...")
    
    sub_count = 0
    for sub in OldCalendarSubscription.objects.all():
        target_cal = calendar_mapping.get(sub.calendar_id)
        if not target_cal:
            continue
        
        # Определить distinction
        if sub.can_manage:
            distinction = 'owner'
        elif sub.can_edit:
            distinction = 'editor'
        else:
            distinction = 'viewer'
        
        CalendarRelation.objects.get_or_create(
            calendar=target_cal,
            content_type=user_ct,
            object_id=sub.user_id,
            defaults={'distinction': distinction}
        )
        sub_count += 1
    
    print(f"✅ Migrated {sub_count} subscriptions\n")
    
    print("=== MIGRATION COMPLETE ===\n")


def create_rule_from_recurrence(apps, recurrence, interval, weekdays_mask, 
                                  until, count, event_title):
    """Создает Rule из параметров повторяемости calendar_app."""
    
    Rule = apps.get_model('schedule', 'Rule')
    
    # Маппинг частоты
    freq_mapping = {
        'hourly': 'HOURLY',
        'daily': 'DAILY',
        'weekly': 'WEEKLY',
        'monthly': 'MONTHLY',
        'annual': 'YEARLY',
    }
    
    frequency = freq_mapping.get(recurrence, 'DAILY')
    
    # Формирование params
    params_parts = []
    
    if interval > 1:
        params_parts.append(f'interval:{interval}')
    
    if recurrence == 'weekly' and weekdays_mask:
        # Конвертация битовой маски в byweekday
        days = []
        if weekdays_mask & 1: days.append('0')
        if weekdays_mask & 2: days.append('1')
        if weekdays_mask & 4: days.append('2')
        if weekdays_mask & 8: days.append('3')
        if weekdays_mask & 16: days.append('4')
        if weekdays_mask & 32: days.append('5')
        if weekdays_mask & 64: days.append('6')
        if days:
            params_parts.append(f'byweekday:{",".join(days)}')
    
    if until:
        params_parts.append(f'until:{until.strftime("%Y%m%d")}')
    
    if count:
        params_parts.append(f'count:{count}')
    
    params = ';'.join(params_parts) if params_parts else ''
    
    # Создать Rule
    rule_name = f'{event_title[:20]} - {frequency}'
    rule = Rule.objects.create(
        name=rule_name,
        frequency=frequency,
        params=params
    )
    
    return rule


def migrate_calendars_reverse(apps, schema_editor):
    """Откат миграции (удаление мигрированных данных)."""
    NewCalendar = apps.get_model('schedule', 'Calendar')
    
    # Удалить только мигрированные календари (по slug prefix)
    NewCalendar.objects.filter(
        slug__startswith='company'
    ).delete()
    NewCalendar.objects.filter(
        slug__startswith='dept-'
    ).delete()
    NewCalendar.objects.filter(
        slug__startswith='personal-'
    ).delete()
    NewCalendar.objects.filter(
        slug__startswith='legacy-'
    ).delete()
    
    print("✅ Rollback complete: removed migrated calendars")


class Migration(migrations.Migration):
    
    dependencies = [
        ('calendar_app', '0007_previous_migration'),
        ('schedule', '0014_auto_20201025_0546'),  # django-scheduler
        ('employees', '0042_latest_migration'),
    ]
    
    operations = [
        migrations.RunPython(
            migrate_calendars_forward,
            migrate_calendars_reverse
        ),
    ]
```

---

## ✅ Итоговая Рекомендация

### **Вариант B: Параллельная Работа** ✅

**Почему:**
1. ✅ Нет потери данных
2. ✅ Возможность отката
3. ✅ Постепенная адаптация пользователей
4. ✅ Проверка django-scheduler в продакшене

**План:**
1. **Фаза 1 (1-2 недели):** Создать миграцию (как показано выше)
2. **Фаза 2 (1 месяц):** Параллельная работа обеих систем, Frontend показывает merged view
3. **Фаза 3 (2-3 месяца):** Пользователи тестируют новую систему, сообщают об ошибках
4. **Фаза 4 (1 неделя):** Переключение на полностью новую систему
5. **Фаза 5 (3-6 месяцев):** Мониторинг, затем удаление `calendar_app`

**Риски:**
- ⚠️ Временная поддержка двух систем
- ⚠️ Сложность Frontend (две API)

**Выигрыш:**
- 🔥 Полностью проверенная библиотека (django-scheduler)
- 🔥 RFC 5545 rrule (стандартная повторяемость)
- 🔥 Упрощение кода (меньше кастомной логики)

---

**Документ подготовлен:** 27 февраля 2026 г.  
**Автор:** GitHub Copilot (Claude Sonnet 4.5)  
**Версия:** 1.0
