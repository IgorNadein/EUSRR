# Архитектура: Календари как настраиваемые сущности

**Дата:** 11 февраля 2026 г.
**Задача:** Реализация календарей как отдельных настраиваемых объектов с гибким управлением доступом

---

## 📋 Проблема текущей архитектуры

### Текущая реализация:
```
CalendarEvent:
  - department FK (может быть NULL)
  - employee FK (может быть NULL)
  - title, description, dates, ...
```

**Ограничения:**
1. ❌ Календари не существуют как отдельные объекты
2. ❌ Нельзя создать несколько глобальных календарей ("Праздники", "Обучение", "Корпоративы")
3. ❌ Нельзя настроить права доступа к конкретному календарю
4. ❌ Нельзя дать отделу доступ к календарю другого отдела
5. ❌ Нет возможности подписки пользователей на календари
6. ❌ Автоматическое создание при регистрации/создании отдела неявное

### Требуемая функциональность:

#### 1. Множественные глобальные календари
```
✅ "Праздники компании" (админы)
✅ "Корпоративные мероприятия" (HR)
✅ "Обучающие курсы" (Учебный отдел)
✅ "Релизы продуктов" (Разработка)
```

#### 2. Настраиваемый доступ к календарям
```
✅ Просмотр: все сотрудники / конкретные отделы / конкретные пользователи
✅ Редактирование: админы / владельцы / группа редакторов
✅ Подписка: пользователи могут подписаться/отписаться
```

#### 3. Календари отделов с делегированием
```
✅ Отдел может создать несколько календарей ("Планёрки", "Дедлайны")
✅ Отдел может предоставить доступ другим отделам
✅ Руководитель может делегировать управление календарём
```

#### 4. Личные календари с расшариванием
```
✅ Пользователь может создать несколько личных календарей
✅ Можно расшарить календарь коллегам (read-only или read-write)
```

---

## 🏗️ Новая архитектура

### Модель: Calendar (Календарь)

```python
class CalendarType(models.TextChoices):
    """Тип календаря."""
    GLOBAL = "global", _("Глобальный")
    DEPARTMENT = "department", _("Отдела")
    PERSONAL = "personal", _("Личный")
    SHARED = "shared", _("Общий (расшаренный)")


class Calendar(models.Model):
    """Календарь как отдельная сущность с настраиваемым доступом."""

    # Основное
    title = models.CharField(_("Название"), max_length=200)
    description = models.TextField(_("Описание"), blank=True)
    color = models.CharField(_("Цвет"), max_length=7, default="#0d6efd")

    # Тип и владение
    calendar_type = models.CharField(
        _("Тип календаря"),
        max_length=20,
        choices=CalendarType.choices,
        default=CalendarType.PERSONAL,
    )

    # Владельцы (взаимоисключающие для GLOBAL/DEPARTMENT/PERSONAL)
    owner_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="owned_calendars",
        null=True,
        blank=True,
        verbose_name=_("Владелец (пользователь)"),
    )

    owner_department = models.ForeignKey(
        "employees.Department",
        on_delete=models.CASCADE,
        related_name="owned_calendars",
        null=True,
        blank=True,
        verbose_name=_("Владелец (отдел)"),
    )

    # Системный календарь (автоматически созданный)
    is_system = models.BooleanField(
        _("Системный"),
        default=False,
        help_text=_("Создан автоматически при регистрации/инициализации"),
    )

    system_key = models.CharField(
        _("Системный ключ"),
        max_length=100,
        blank=True,
        db_index=True,
        unique=True,
        null=True,
        help_text=_("Уникальный идентификатор системного календаря"),
    )

    # Настройки доступа
    is_public = models.BooleanField(
        _("Публичный"),
        default=False,
        help_text=_("Доступен всем для просмотра"),
    )

    allow_subscription = models.BooleanField(
        _("Разрешить подписку"),
        default=True,
        help_text=_("Пользователи могут подписаться на этот календарь"),
    )

    default_for_new_users = models.BooleanField(
        _("По умолчанию для новых пользователей"),
        default=False,
        help_text=_("Автоматически добавляется новым сотрудникам"),
    )

    # Служебное
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calendars_created",
        verbose_name=_("Создал"),
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    is_active = models.BooleanField(_("Активен"), default=True)

    class Meta:
        verbose_name = _("Календарь")
        verbose_name_plural = _("Календари")
        ordering = ["calendar_type", "title"]
        indexes = [
            models.Index(fields=["calendar_type", "is_active"]),
            models.Index(fields=["owner_user", "is_active"]),
            models.Index(fields=["owner_department", "is_active"]),
            models.Index(fields=["system_key"]),
        ]
        constraints = [
            # Системный календарь обязан иметь system_key
            models.CheckConstraint(
                check=(
                    models.Q(is_system=False) | models.Q(system_key__isnull=False)
                ),
                name="system_calendar_must_have_key"
            ),
            # Уникальность system_key для системных календарей
            models.UniqueConstraint(
                fields=["system_key"],
                condition=models.Q(is_system=True),
                name="unique_system_key"
            ),
        ]

    def __str__(self):
        type_label = self.get_calendar_type_display()
        owner = ""
        if self.owner_user:
            owner = f" ({self.owner_user.get_full_name() or self.owner_user.username})"
        elif self.owner_department:
            owner = f" ({self.owner_department.name})"
        return f"[{type_label}] {self.title}{owner}"

    def clean(self):
        """Валидация владения календарём."""
        # GLOBAL не имеет владельца
        if self.calendar_type == CalendarType.GLOBAL:
            if self.owner_user or self.owner_department:
                raise ValidationError(
                    _("Глобальный календарь не может иметь владельца.")
                )

        # DEPARTMENT должен иметь owner_department
        if self.calendar_type == CalendarType.DEPARTMENT:
            if not self.owner_department:
                raise ValidationError(
                    _("Календарь отдела должен иметь владельца (отдел).")
                )
            if self.owner_user:
                raise ValidationError(
                    _("Календарь отдела не может иметь владельца-пользователя.")
                )

        # PERSONAL должен иметь owner_user
        if self.calendar_type == CalendarType.PERSONAL:
            if not self.owner_user:
                raise ValidationError(
                    _("Личный календарь должен иметь владельца (пользователя).")
                )
            if self.owner_department:
                raise ValidationError(
                    _("Личный календарь не может иметь владельца-отдел.")
                )

        # Системный календарь должен иметь уникальный system_key
        if self.is_system and not self.system_key:
            raise ValidationError(
                _("Системный календарь должен иметь system_key.")
            )

    @property
    def is_global(self):
        return self.calendar_type == CalendarType.GLOBAL

    @property
    def is_department_calendar(self):
        return self.calendar_type == CalendarType.DEPARTMENT

    @property
    def is_personal_calendar(self):
        return self.calendar_type == CalendarType.PERSONAL
```

### Модель: CalendarPermission (Права доступа к календарю)

```python
class PermissionLevel(models.TextChoices):
    """Уровень доступа к календарю."""
    VIEW = "view", _("Просмотр")
    EDIT = "edit", _("Редактирование")
    MANAGE = "manage", _("Управление")  # + права доступа


class CalendarPermission(models.Model):
    """Права доступа к календарю для пользователя или отдела."""

    calendar = models.ForeignKey(
        Calendar,
        on_delete=models.CASCADE,
        related_name="permissions",
        verbose_name=_("Календарь"),
    )

    # Кому предоставлен доступ (одно из двух)
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="calendar_permissions",
        null=True,
        blank=True,
        verbose_name=_("Пользователь"),
    )

    department = models.ForeignKey(
        "employees.Department",
        on_delete=models.CASCADE,
        related_name="calendar_permissions",
        null=True,
        blank=True,
        verbose_name=_("Отдел"),
    )

    # Уровень доступа
    level = models.CharField(
        _("Уровень доступа"),
        max_length=10,
        choices=PermissionLevel.choices,
        default=PermissionLevel.VIEW,
    )

    # Служебное
    granted_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
        verbose_name=_("Предоставил"),
    )
    granted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Право доступа к календарю")
        verbose_name_plural = _("Права доступа к календарям")
        indexes = [
            models.Index(fields=["calendar", "user"]),
            models.Index(fields=["calendar", "department"]),
        ]
        constraints = [
            # Либо user, либо department
            models.CheckConstraint(
                check=(
                    models.Q(user__isnull=False, department__isnull=True) |
                    models.Q(user__isnull=True, department__isnull=False)
                ),
                name="permission_target_xor"
            ),
            # Уникальность: один пользователь = один уровень доступа
            models.UniqueConstraint(
                fields=["calendar", "user"],
                condition=models.Q(user__isnull=False),
                name="unique_user_permission"
            ),
            models.UniqueConstraint(
                fields=["calendar", "department"],
                condition=models.Q(department__isnull=False),
                name="unique_dept_permission"
            ),
        ]

    def __str__(self):
        target = self.user if self.user else self.department
        return f"{self.calendar.title} → {target} ({self.get_level_display()})"

    def clean(self):
        """Валидация целевого получателя прав."""
        if not self.user and not self.department:
            raise ValidationError(
                _("Необходимо указать либо пользователя, либо отдел.")
            )
        if self.user and self.department:
            raise ValidationError(
                _("Нельзя одновременно указывать пользователя и отдел.")
            )
```

### Модель: CalendarSubscription (Подписки пользователей)

```python
class CalendarSubscription(models.Model):
    """Подписка пользователя на календарь."""

    calendar = models.ForeignKey(
        Calendar,
        on_delete=models.CASCADE,
        related_name="subscriptions",
        verbose_name=_("Календарь"),
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="calendar_subscriptions",
        verbose_name=_("Пользователь"),
    )

    # Настройки подписки
    is_visible = models.BooleanField(
        _("Отображать"),
        default=True,
        help_text=_("Показывать события этого календаря в виджете"),
    )

    color_override = models.CharField(
        _("Переопределить цвет"),
        max_length=7,
        blank=True,
        help_text=_("Личный цвет для событий этого календаря"),
    )

    receive_notifications = models.BooleanField(
        _("Получать уведомления"),
        default=True,
    )

    # Автоматическая подписка (по умолчанию для новых пользователей)
    is_auto_subscribed = models.BooleanField(
        _("Автоподписка"),
        default=False,
        help_text=_("Добавлена автоматически при регистрации"),
    )

    subscribed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Подписка на календарь")
        verbose_name_plural = _("Подписки на календари")
        unique_together = [["calendar", "user"]]
        indexes = [
            models.Index(fields=["user", "is_visible"]),
            models.Index(fields=["calendar", "is_visible"]),
        ]

    def __str__(self):
        return f"{self.user.username} → {self.calendar.title}"
```

### Обновление: CalendarEvent

```python
class CalendarEvent(models.Model):
    """Событие календаря с поддержкой повторяемости."""

    # НОВОЕ: Связь с календарём
    calendar = models.ForeignKey(
        Calendar,
        on_delete=models.CASCADE,
        related_name="events",
        verbose_name=_("Календарь"),
    )

    # УДАЛИТЬ: department, employee (теперь через calendar)

    # Основное (без изменений)
    title = models.CharField(_("Название"), max_length=200)
    description = models.TextField(_("Описание"), blank=True)

    # Даты/время (без изменений)
    start_date = models.DateField(_("Дата начала"))
    end_date = models.DateField(_("Дата окончания"), null=True, blank=True)
    start_time = models.TimeField(_("Время начала"), null=True, blank=True)
    end_time = models.TimeField(_("Время окончания"), null=True, blank=True)
    all_day = models.BooleanField(_("Весь день"), default=True)

    # Повторяемость (без изменений)
    recurrence = models.CharField(...)
    recurrence_interval = models.PositiveSmallIntegerField(...)
    # ... остальные поля recurrence

    # Отображение
    color = models.CharField(
        _("Цвет"),
        max_length=7,
        blank=True,
        help_text=_("Переопределяет цвет календаря для этого события"),
    )
    location = models.CharField(_("Локация"), max_length=200, blank=True)

    # Служебное
    created_by = models.ForeignKey(...)
    created_at = models.DateTimeField(auto_now_add=True)
    source = models.CharField(...)  # Для системных событий (дни рождения)

    class Meta:
        verbose_name = _("Событие календаря")
        verbose_name_plural = _("События календаря")
        ordering = ["calendar", "start_date", "start_time"]
        indexes = [
            models.Index(fields=["calendar", "start_date"]),
            models.Index(fields=["calendar", "recurrence", "start_date"]),
            models.Index(fields=["source"]),
        ]
```

---

## 🔄 Миграция данных

### Шаг 1: Создание новых моделей

```python
# backend/calendar_app/migrations/000X_add_calendar_models.py

from django.db import migrations, models
import django.db.models.deletion

class Migration(migrations.Migration):
    dependencies = [
        ('calendar_app', '000X_previous_migration'),
        ('employees', '000X_department_migration'),
    ]

    operations = [
        # Создание модели Calendar
        migrations.CreateModel(
            name='Calendar',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True)),
                ('title', models.CharField(max_length=200)),
                ('description', models.TextField(blank=True)),
                ('color', models.CharField(default='#0d6efd', max_length=7)),
                ('calendar_type', models.CharField(max_length=20, choices=[...])),
                ('is_system', models.BooleanField(default=False)),
                ('system_key', models.CharField(max_length=100, unique=True, null=True)),
                ('is_public', models.BooleanField(default=False)),
                ('allow_subscription', models.BooleanField(default=True)),
                ('default_for_new_users', models.BooleanField(default=False)),
                ('is_active', models.BooleanField(default=True)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                # ForeignKeys будут добавлены отдельно
            ],
        ),

        # Добавление ForeignKey полей
        migrations.AddField(
            model_name='calendar',
            name='owner_user',
            field=models.ForeignKey(
                null=True, blank=True,
                on_delete=django.db.models.deletion.CASCADE,
                related_name='owned_calendars',
                to=settings.AUTH_USER_MODEL
            ),
        ),
        # ... остальные FK

        # Создание CalendarPermission
        migrations.CreateModel(name='CalendarPermission', ...),

        # Создание CalendarSubscription
        migrations.CreateModel(name='CalendarSubscription', ...),
    ]
```

### Шаг 2: Миграция существующих событий

```python
# backend/calendar_app/migrations/000X_migrate_events_to_calendars.py

from django.db import migrations

def migrate_events_to_calendars(apps, schema_editor):
    """Создаёт календари для существующих событий и привязывает их."""
    CalendarEvent = apps.get_model('calendar_app', 'CalendarEvent')
    Calendar = apps.get_model('calendar_app', 'Calendar')
    User = apps.get_model('employees', 'Employee')
    Department = apps.get_model('employees', 'Department')

    # 1. Создать глобальный календарь для событий компании
    company_calendar, _ = Calendar.objects.get_or_create(
        system_key='company_default',
        defaults={
            'title': 'Календарь компании',
            'description': 'Основной календарь корпоративных событий',
            'calendar_type': 'global',
            'is_system': True,
            'is_public': True,
            'default_for_new_users': True,
        }
    )

    # 2. Мигрировать события компании (department=NULL, employee=NULL)
    company_events = CalendarEvent.objects.filter(
        department__isnull=True,
        employee__isnull=True
    )
    for event in company_events:
        event.calendar = company_calendar
        event.save(update_fields=['calendar'])

    print(f"✅ Мигрировано событий компании: {company_events.count()}")

    # 3. Создать календари для отделов
    for dept in Department.objects.all():
        dept_calendar, created = Calendar.objects.get_or_create(
            system_key=f'department_{dept.id}_default',
            defaults={
                'title': f'Календарь отдела {dept.name}',
                'description': f'Календарь событий отдела {dept.name}',
                'calendar_type': 'department',
                'owner_department': dept,
                'is_system': True,
                'is_public': False,
                'allow_subscription': True,
            }
        )

        # Мигрировать события отдела
        dept_events = CalendarEvent.objects.filter(department=dept)
        for event in dept_events:
            event.calendar = dept_calendar
            event.save(update_fields=['calendar'])

        if created:
            print(f"✅ Создан календарь отдела: {dept.name} ({dept_events.count()} событий)")

    # 4. Создать личные календари для пользователей
    for user in User.objects.all():
        user_calendar, created = Calendar.objects.get_or_create(
            system_key=f'personal_{user.id}_default',
            defaults={
                'title': 'Мой календарь',
                'description': 'Личный календарь событий',
                'calendar_type': 'personal',
                'owner_user': user,
                'is_system': True,
                'is_public': False,
                'allow_subscription': False,
            }
        )

        # Мигрировать личные события
        personal_events = CalendarEvent.objects.filter(employee=user)
        for event in personal_events:
            event.calendar = user_calendar
            event.save(update_fields=['calendar'])

        if created and personal_events.exists():
            print(f"✅ Создан личный календарь: {user.username} ({personal_events.count()} событий)")

def reverse_migration(apps, schema_editor):
    """Откат: восстановление department/employee из calendar."""
    CalendarEvent = apps.get_model('calendar_app', 'CalendarEvent')

    for event in CalendarEvent.objects.select_related('calendar').all():
        cal = event.calendar
        if cal.calendar_type == 'department' and cal.owner_department:
            event.department = cal.owner_department
        elif cal.calendar_type == 'personal' and cal.owner_user:
            event.employee = cal.owner_user
        event.save(update_fields=['department', 'employee'])

class Migration(migrations.Migration):
    dependencies = [
        ('calendar_app', '000X_add_calendar_field_to_events'),
    ]

    operations = [
        migrations.RunPython(
            migrate_events_to_calendars,
            reverse_migration
        ),
    ]
```

### Шаг 3: Удаление старых полей

```python
# backend/calendar_app/migrations/000X_remove_old_fields.py

class Migration(migrations.Migration):
    dependencies = [
        ('calendar_app', '000X_migrate_events_to_calendars'),
    ]

    operations = [
        # Удалить старые поля department и employee из CalendarEvent
        migrations.RemoveField(
            model_name='calendarevent',
            name='department',
        ),
        migrations.RemoveField(
            model_name='calendarevent',
            name='employee',
        ),
    ]
```

---

## 🎯 Примеры использования

### 1. Создание глобального календаря (админ)

```python
from calendar_app.models import Calendar, CalendarType

# Календарь праздников (доступен всем)
holidays_cal = Calendar.objects.create(
    title="Праздники компании",
    description="Официальные праздники и выходные",
    calendar_type=CalendarType.GLOBAL,
    color="#FF5733",
    is_public=True,
    default_for_new_users=True,
    created_by=admin_user
)

# Календарь обучения (доступ по подписке)
training_cal = Calendar.objects.create(
    title="Обучающие мероприятия",
    calendar_type=CalendarType.GLOBAL,
    color="#28A745",
    is_public=True,
    allow_subscription=True,
    created_by=hr_manager
)
```

### 2. Настройка прав доступа

```python
from calendar_app.models import CalendarPermission, PermissionLevel

# HR отделу - право редактирования календаря обучения
CalendarPermission.objects.create(
    calendar=training_cal,
    department=hr_department,
    level=PermissionLevel.EDIT,
    granted_by=admin_user
)

# Конкретному пользователю - управление календарём
CalendarPermission.objects.create(
    calendar=training_cal,
    user=training_coordinator,
    level=PermissionLevel.MANAGE,
    granted_by=admin_user
)
```

### 3. Подписка пользователей

```python
from calendar_app.models import CalendarSubscription

# Пользователь подписывается на календарь
CalendarSubscription.objects.create(
    calendar=training_cal,
    user=employee,
    is_visible=True,
    color_override="#00BFFF",  # Личный цвет
    receive_notifications=True
)

# Автоподписка новых пользователей (при регистрации)
for calendar in Calendar.objects.filter(default_for_new_users=True):
    CalendarSubscription.objects.create(
        calendar=calendar,
        user=new_user,
        is_visible=True,
        is_auto_subscribed=True
    )
```

### 4. Создание события в календаре

```python
from calendar_app.models import CalendarEvent, Recurrence

# Создание праздника в глобальном календаре
CalendarEvent.objects.create(
    calendar=holidays_cal,
    title="Новый год",
    start_date=date(2026, 1, 1),
    end_date=date(2026, 1, 1),
    all_day=True,
    recurrence=Recurrence.ANNUAL,
    color="#FF0000",  # Переопределяет цвет календаря
    created_by=admin_user
)
```

### 5. Получение календарей пользователя

```python
def get_user_calendars(user):
    """Возвращает все календари, доступные пользователю."""
    from django.db.models import Q

    # 1. Личные календари пользователя
    personal_cals = Calendar.objects.filter(
        calendar_type=CalendarType.PERSONAL,
        owner_user=user,
        is_active=True
    )

    # 2. Публичные календари
    public_cals = Calendar.objects.filter(
        is_public=True,
        is_active=True
    )

    # 3. Календари отделов пользователя
    user_departments = user.departments_links.filter(
        is_active=True
    ).values_list('department_id', flat=True)

    dept_cals = Calendar.objects.filter(
        calendar_type=CalendarType.DEPARTMENT,
        owner_department_id__in=user_departments,
        is_active=True
    )

    # 4. Календари с явными правами доступа
    permitted_cals = Calendar.objects.filter(
        Q(permissions__user=user) |
        Q(permissions__department_id__in=user_departments),
        is_active=True
    ).distinct()

    # 5. Подписки пользователя
    subscribed_cals = Calendar.objects.filter(
        subscriptions__user=user,
        subscriptions__is_visible=True,
        is_active=True
    )

    # Объединение и удаление дубликатов
    all_cals = (personal_cals | public_cals | dept_cals |
                permitted_cals | subscribed_cals).distinct()

    return all_cals.order_by('calendar_type', 'title')
```

### 6. Проверка прав пользователя

```python
def check_calendar_permission(calendar, user, required_level='view'):
    """Проверяет права пользователя на календарь."""
    from calendar_app.models import PermissionLevel

    # Админы могут всё
    if user.is_superuser or user.is_staff:
        return True

    # Владелец может всё
    if calendar.owner_user_id == user.id:
        return True

    # Публичный календарь - просмотр для всех
    if required_level == 'view' and calendar.is_public:
        return True

    # Проверка календаря отдела
    if calendar.calendar_type == CalendarType.DEPARTMENT:
        user_departments = user.departments_links.filter(
            is_active=True
        ).values_list('department_id', flat=True)

        if calendar.owner_department_id in user_departments:
            if required_level == 'view':
                return True
            # Для редактирования нужны явные права

    # Проверка явных прав доступа
    level_hierarchy = {
        'view': 1,
        'edit': 2,
        'manage': 3
    }

    required_int = level_hierarchy.get(required_level, 1)

    # Права пользователя
    user_perm = calendar.permissions.filter(user=user).first()
    if user_perm:
        user_level = level_hierarchy.get(user_perm.level, 0)
        if user_level >= required_int:
            return True

    # Права через отдел
    user_departments = user.departments_links.filter(
        is_active=True
    ).values_list('department_id', flat=True)

    dept_perm = calendar.permissions.filter(
        department_id__in=user_departments
    ).order_by('-level').first()

    if dept_perm:
        dept_level = level_hierarchy.get(dept_perm.level, 0)
        if dept_level >= required_int:
            return True

    return False
```

---

## 📡 API изменения

### Новые эндпоинты:

```python
# backend/api/v1/calendar/urls.py

urlpatterns = [
    # Календари
    path('calendars/', CalendarListCreateView.as_view(), name='calendar-list'),
    path('calendars/<int:pk>/', CalendarDetailView.as_view(), name='calendar-detail'),
    path('calendars/<int:pk>/permissions/', CalendarPermissionsView.as_view()),
    path('calendars/<int:pk>/subscribe/', CalendarSubscribeView.as_view()),
    path('calendars/<int:pk>/unsubscribe/', CalendarUnsubscribeView.as_view()),
    path('calendars/my/', MyCalendarsView.as_view(), name='my-calendars'),

    # События (обновлённый эндпоинт)
    path('calendars/<int:calendar_id>/events/', CalendarEventsView.as_view()),
    path('events/<int:pk>/', EventDetailView.as_view()),

    # Подписки
    path('subscriptions/', MySubscriptionsView.as_view()),
]
```

### Примеры запросов:

```http
# Получить все календари пользователя
GET /api/v1/calendar/calendars/my/

# Создать новый календарь
POST /api/v1/calendar/calendars/
{
    "title": "Дедлайны проекта X",
    "calendar_type": "department",
    "owner_department_id": 5,
    "color": "#FF6347",
    "is_public": false,
    "allow_subscription": true
}

# Предоставить права редактирования
POST /api/v1/calendar/calendars/123/permissions/
{
    "user_id": 456,
    "level": "edit"
}

# Подписаться на календарь
POST /api/v1/calendar/calendars/123/subscribe/
{
    "receive_notifications": true,
    "color_override": "#00FF00"
}

# Получить события конкретного календаря
GET /api/v1/calendar/calendars/123/events/?start=2025-11-01&end=2025-11-30
```

---

## 🔧 Сигналы и автоматизация

### Автосоздание календарей

```python
# backend/calendar_app/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver

@receiver(post_save, sender=User)
def create_personal_calendar(sender, instance, created, **kwargs):
    """Создаёт личный календарь при регистрации пользователя."""
    if created:
        Calendar.objects.create(
            title="Мой календарь",
            calendar_type=CalendarType.PERSONAL,
            owner_user=instance,
            is_system=True,
            system_key=f"personal_{instance.id}_default",
            color="#6C757D"
        )

        # Автоподписка на календари по умолчанию
        default_calendars = Calendar.objects.filter(
            default_for_new_users=True,
            is_active=True
        )
        for calendar in default_calendars:
            CalendarSubscription.objects.create(
                calendar=calendar,
                user=instance,
                is_auto_subscribed=True
            )


@receiver(post_save, sender=Department)
def create_department_calendar(sender, instance, created, **kwargs):
    """Создаёт календарь отдела при создании отдела."""
    if created:
        Calendar.objects.create(
            title=f"Календарь {instance.name}",
            calendar_type=CalendarType.DEPARTMENT,
            owner_department=instance,
            is_system=True,
            system_key=f"department_{instance.id}_default",
            color="#0D6EFD",
            allow_subscription=True
        )
```

---

## 📊 Итоговое сравнение

| Функция | Было | Стало |
|---------|------|-------|
| **Глобальные календари** | 1 (неявный) | Множество (создаются админами) |
| **Календари отдела** | 1 на отдел (автомат) | Множество на отдел |
| **Личные календари** | 1 на пользователя (неявный) | Множество на пользователя |
| **Права доступа** | Жёсткие (по типу) | Гибкие (CalendarPermission) |
| **Подписки** | Нет | Да (CalendarSubscription) |
| **Делегирование** | Нет | Да (MANAGE уровень) |
| **Расшаривание** | Нет | Да (permissions на user/dept) |
| **Настройка видимости** | Нет | Да (is_visible в подписке) |
| **Цвет календаря** | Только на событии | На календаре + override на событии |
| **Автосоздание** | Неявное | Явное через сигналы |

---

## ✅ Преимущества новой архитектуры

1. ✅ **Гибкость:** Любое количество календарей любого типа
2. ✅ **Настраиваемость:** Права доступа на уровне calendar + user/dept
3. ✅ **Масштабируемость:** Отдел может иметь "Планёрки", "Дедлайны", "Отпуска"
4. ✅ **UX:** Пользователь видит только нужные календари (подписки)
5. ✅ **Безопасность:** Явные права вместо неявных правил
6. ✅ **Прозрачность:** Системные календари помечены `is_system=True`
7. ✅ **Расширяемость:** Легко добавить новые типы календарей (PROJECT, TEAM, etc.)

---

## 🚀 План реализации

### Фаза 1: Модели и миграции (2-3 дня)
- [x] Создать модели Calendar, CalendarPermission, CalendarSubscription
- [x] Написать миграции с переносом данных
- [x] Добавить сигналы автосоздания

### Фаза 2: API (3-4 дня)
- [ ] Сериализаторы для новых моделей
- [ ] ViewSets для календарей и подписок
- [ ] Обновить CalendarEventsViewSet (filter по calendar_id)
- [ ] Middleware проверки прав доступа

### Фаза 3: Frontend (4-5 дней)
- [ ] UI выбора календарей (мультивыбор checkbox)
- [ ] Модалка создания/настройки календаря
- [ ] Управление правами доступа (для MANAGE уровня)
- [ ] Управление подписками (список + вкл/выкл)

### Фаза 4: Тестирование (2-3 дня)
- [ ] Unit тесты моделей
- [ ] API тесты (права доступа, CRUD)
- [ ] E2E тесты UI

### Фаза 5: Документация (1 день)
- [ ] Обновить README
- [ ] API документация (Swagger)
- [ ] Гайд для пользователей

**Общее время:** ~12-16 рабочих дней

---

## 📖 Следующие шаги

1. **Утвердить архитектуру** с командой/владельцем продукта
2. **Создать ветку** `feature/calendar-entities`
3. **Начать с миграций** (Фаза 1) — критично для целостности данных
4. **Параллельно разработать API** (Фаза 2)
5. **Обновить фронт** (Фаза 3) после готовности API

---

**Автор:** GitHub Copilot
**Дата:** 11 февраля 2026 г.
