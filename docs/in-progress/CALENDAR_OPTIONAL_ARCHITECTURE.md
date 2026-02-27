# Упрощённая архитектура: Опциональные настраиваемые календари

**Дата:** 11 февраля 2026 г.
**Подход:** Обратно совместимое расширение без поломки существующего функционала
**Статус:** ✅ Phase 2 (API + Testing) завершена

---

## 📊 Прогресс реализации

### ✅ Phase 1: Модели и миграции (Завершено)
- ✅ Создана модель `Calendar` с настройками видимости
- ✅ Создана модель `CalendarSubscription` с правами доступа
- ✅ Добавлено опциональное поле `calendar` в `CalendarEvent`
- ✅ Миграция 0011 создана и применена
- ✅ Admin интерфейсы настроены
- ✅ Коммит: `feat(calendar): add optional Calendar and CalendarSubscription models`

### ✅ Phase 2: API Layer + Testing (Завершено)
- ✅ `CalendarEventWriteSerializer` поддерживает `calendar_id`
- ✅ Созданы сериализаторы для `Calendar` (read + write)
- ✅ Созданы сериализаторы для `CalendarSubscription` (read + write)
- ✅ `CalendarViewSet` с CRUD операциями
- ✅ Эндпоинты subscribe/unsubscribe для календарей
- ✅ `CalendarSubscriptionViewSet` для управления подписками
- ✅ `CalendarEventsViewSet` обновлен для поддержки `calendar_id`
- ✅ `CalendarManager.get_available_for_user()` метод
- ✅ Методы проверки прав в модели `Calendar`
- ✅ URL маршруты зарегистрированы
- ✅ Коммит API: `feat(calendar): add API layer for optional calendars`

#### 🧪 Тестирование (Завершено)
- ✅ Создана фикстура `make_event` для тестов событий
- ✅ Миграция 0012: `CalendarSubscription.color_override` nullable
- ✅ Добавлены computed-поля в `CalendarSerializer`: `is_personal`, `is_global`, `is_department`
- ✅ Исправлен `CalendarViewSet.create()` для корректного ответа
- ✅ Создан `test_new_calendar_api.py` с 29 тестами:
  * 11 CRUD тестов (list, create, retrieve, update, delete)
  * 6 subscription тестов (subscribe, unsubscribe, my-subscriptions)
  * 3 event filtering тестов (calendar_id filtering, legacy separation)
  * 3 visibility тестов (public, private, department)
  * 6 permission тестов (is_owner, can_user_view, can_user_edit)
- ✅ **Результаты тестов:**
  * ✅ 34 legacy тестов пройдено (обратная совместимость)
  * ✅ 29 новых тестов пройдено (новый функционал)
  * ✅ **Всего: 63 теста успешно!**
- ✅ Коммит тестов: `feat(calendar): add comprehensive test suite for new Calendar API`

#### API эндпоинты (новые):
```
GET    /api/v1/calendar/calendars/              # Список доступных календарей
POST   /api/v1/calendar/calendars/              # Создание календаря
GET    /api/v1/calendar/calendars/{id}/         # Детали календаря
PATCH  /api/v1/calendar/calendars/{id}/         # Обновление календаря
DELETE /api/v1/calendar/calendars/{id}/         # Удаление календаря
POST   /api/v1/calendar/calendars/{id}/subscribe/    # Подписка
POST   /api/v1/calendar/calendars/{id}/unsubscribe/  # Отписка
GET    /api/v1/calendar/calendars/my-calendars/ # Мои календари

GET    /api/v1/calendar/subscriptions/          # Мои подписки
POST   /api/v1/calendar/subscriptions/          # Создать подписку
GET    /api/v1/calendar/subscriptions/{id}/     # Детали подписки
PATCH  /api/v1/calendar/subscriptions/{id}/     # Обновить подписку
DELETE /api/v1/calendar/subscriptions/{id}/     # Удалить подписку

GET    /api/v1/calendar/events/?calendar_id={id}  # События календаря (legacy + new)
```

### ⏳ Phase 3: Frontend (В процессе)

#### ✅ Part 1: UI Components (Завершено)
- ✅ `calendarsApi.js` - API wrapper для работы с календарями
- ✅ `calendarManager.js` - Компонент списка календарей
- ✅ `calendarManageModal.js` - Модальное окно создания/редактирования
- ✅ `calendar-manager.scss` - BEM-стили для компонентов
- ✅ `calendar_desktop.html` - Обновлённый UI с collapsible списком
- ✅ `calendar_modal_manage.html` - Шаблон модального окна
- ✅ Коммит: `feat(calendar): add frontend components for calendar management (Phase 3 - Part 1)`

#### ✅ Part 2: Integration (Завершено)
- ✅ `calendarWidgetIntegration.js` - Интеграция менеджера с виджетом
- ✅ `calendarWidget.js` - Модифицирован для поддержки множественных календарей
- ✅ Фильтрация событий по выбранным календарям (`fetchEventsForVisibleCalendars`)
- ✅ Интеграция с FullCalendar.js через `window.calendarIntegration`
- ✅ Обновление цветов событий по календарям
- ✅ Синхронизация состояния видимости через callbacks
- ✅ Fallback на legacy режим для обратной совместимости
- ✅ Дедупликация событий по ID
- ✅ Логирование для debugging
- ✅ `calendar_scripts.html` обновлён для инициализации интеграции

**Архитектурные решения:**
- Неинвазивная интеграция: `calendarWidget.js` проверяет наличие `window.calendarIntegration`
- Legacy режим автоматически активируется если новая система недоступна
- События загружаются с параметром `calendar_id` для каждого видимого календаря
- Цвет календаря переопределяет цвет события для визуальной группировки

### ⏳ Phase 4: Дополнительное тестирование (В планах)
- ✅ Unit тесты для моделей (через API тесты)
- ✅ API тесты для новых эндпоинтов (29 тестов)
- ✅ Тесты прав доступа (6 тестов permissions)
- ✅ Тесты обратной совместимости (34 legacy теста)
- ⏳ Integration тесты frontend + backend
- ⏳ E2E тесты пользовательских сценариев

### ⏳ Phase 5: Документация (В планах)
- ⏳ Обновление README
- ⏳ API документация (OpenAPI/Swagger)
- ⏳ Руководство пользователя

---

## 💡 Ключевая идея

### Принцип работы:

```
CalendarEvent.calendar = NULL  →  Работает как раньше (department/employee)
CalendarEvent.calendar = FK   →  Игнорирует department/employee, использует только calendar
```

**Преимущества:**
- ✅ Существующий код продолжает работать без изменений
- ✅ Новый функционал добавляется опционально
- ✅ Миграция данных НЕ требуется
- ✅ Постепенный переход по желанию

---

## 🏗️ Архитектура

### 1. Добавить модель Calendar (опциональная)

```python
# backend/calendar_app/models.py

class CalendarVisibility(models.TextChoices):
    """Видимость календаря."""
    PUBLIC = "public", _("Публичный (все видят)")
    DEPARTMENT = "department", _("Отдел (только члены отдела)")
    PRIVATE = "private", _("Приватный (только владелец)")
    CUSTOM = "custom", _("Настраиваемый (через права)")


class Calendar(models.Model):
    """Настраиваемый календарь (опциональный, расширенная функциональность).

    Если событие создано БЕЗ calendar → работает старая логика (department/employee).
    Если событие создано С calendar → игнорируются department/employee, используются настройки календаря.
    """

    # Основное
    title = models.CharField(_("Название"), max_length=200)
    description = models.TextField(_("Описание"), blank=True)
    color = models.CharField(_("Цвет"), max_length=7, default="#0d6efd")
    icon = models.CharField(_("Иконка"), max_length=50, blank=True, help_text="Bootstrap icon, например: calendar-event")

    # Владение (опциональное)
    owner_user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="owned_calendars",
        null=True,
        blank=True,
        verbose_name=_("Владелец"),
        help_text=_("Если задано — личный календарь пользователя"),
    )

    owner_department = models.ForeignKey(
        "employees.Department",
        on_delete=models.CASCADE,
        related_name="owned_calendars",
        null=True,
        blank=True,
        verbose_name=_("Отдел-владелец"),
        help_text=_("Если задано — календарь отдела"),
    )

    # Настройки видимости
    visibility = models.CharField(
        _("Видимость"),
        max_length=20,
        choices=CalendarVisibility.choices,
        default=CalendarVisibility.CUSTOM,
    )

    # Права по умолчанию для новых подписчиков
    default_can_edit = models.BooleanField(
        _("Могут редактировать по умолчанию"),
        default=False,
        help_text=_("Если True, все подписчики могут создавать/редактировать события"),
    )

    # Автоподписка
    auto_subscribe_new_users = models.BooleanField(
        _("Автоподписка для новых пользователей"),
        default=False,
        help_text=_("Автоматически подписывать новых сотрудников"),
    )

    auto_subscribe_department_members = models.BooleanField(
        _("Автоподписка для членов отдела"),
        default=False,
        help_text=_("Автоматически подписывать членов отдела-владельца"),
    )

    # Служебное
    is_active = models.BooleanField(_("Активен"), default=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="calendars_created",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = _("Календарь")
        verbose_name_plural = _("Календари")
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["owner_user", "is_active"]),
            models.Index(fields=["owner_department", "is_active"]),
            models.Index(fields=["visibility"]),
        ]

    def __str__(self):
        if self.owner_user:
            return f"{self.title} ({self.owner_user.username})"
        if self.owner_department:
            return f"{self.title} ({self.owner_department.name})"
        return f"{self.title} (Глобальный)"

    def clean(self):
        # Нельзя одновременно user и department
        if self.owner_user and self.owner_department:
            raise ValidationError(
                _("Календарь не может одновременно принадлежать пользователю и отделу.")
            )

    @property
    def is_global(self):
        """Глобальный календарь (без владельца)."""
        return not self.owner_user_id and not self.owner_department_id

    @property
    def is_personal(self):
        """Личный календарь пользователя."""
        return bool(self.owner_user_id)

    @property
    def is_department(self):
        """Календарь отдела."""
        return bool(self.owner_department_id)
```

### 2. Добавить подписки (упрощённая модель)

```python
class CalendarSubscription(models.Model):
    """Подписка пользователя на календарь с настройками отображения."""

    calendar = models.ForeignKey(
        Calendar,
        on_delete=models.CASCADE,
        related_name="subscriptions",
    )

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="calendar_subscriptions",
    )

    # Настройки отображения
    is_visible = models.BooleanField(_("Отображать"), default=True)
    color_override = models.CharField(
        _("Свой цвет"),
        max_length=7,
        blank=True,
        help_text=_("Переопределяет цвет календаря"),
    )

    # Права подписчика
    can_edit = models.BooleanField(
        _("Может редактировать"),
        default=False,
        help_text=_("Может создавать/редактировать события в этом календаре"),
    )

    can_manage = models.BooleanField(
        _("Может управлять"),
        default=False,
        help_text=_("Может управлять правами других пользователей (только для не-владельцев)"),
    )

    # Уведомления
    notify_on_new_event = models.BooleanField(_("Уведомлять о новых событиях"), default=True)
    notify_on_event_change = models.BooleanField(_("Уведомлять об изменениях"), default=True)

    subscribed_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = _("Подписка на календарь")
        verbose_name_plural = _("Подписки на календари")
        unique_together = [["calendar", "user"]]
        indexes = [
            models.Index(fields=["user", "is_visible"]),
            models.Index(fields=["calendar", "can_edit"]),
        ]

    def __str__(self):
        return f"{self.user.username} → {self.calendar.title}"
```

### 3. Расширить CalendarEvent (БЕЗ удаления существующих полей!)

```python
class CalendarEvent(models.Model):
    """Событие календаря с поддержкой повторяемости.

    ОБРАТНАЯ СОВМЕСТИМОСТЬ:
    - Если calendar = NULL → используется старая логика (department/employee)
    - Если calendar задан → игнорируются department/employee, используется calendar
    """

    # ✨ НОВОЕ: Опциональная привязка к настраиваемому календарю
    calendar = models.ForeignKey(
        Calendar,
        on_delete=models.CASCADE,
        related_name="events",
        null=True,
        blank=True,
        verbose_name=_("Календарь"),
        help_text=_("Если не задан — событие использует стандартную логику (department/employee)"),
    )

    # ✅ ОСТАВЛЯЕМ: Старые поля для обратной совместимости
    department = models.ForeignKey(
        "employees.Department",
        on_delete=models.CASCADE,
        related_name="calendar_events",
        verbose_name=_("Отдел"),
        null=True,
        blank=True,
        help_text=_("LEGACY: используется если calendar=NULL"),
    )

    employee = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="personal_calendar_events",
        verbose_name=_("Сотрудник"),
        null=True,
        blank=True,
        help_text=_("LEGACY: используется если calendar=NULL"),
    )

    # ... остальные поля БЕЗ ИЗМЕНЕНИЙ ...

    class Meta:
        verbose_name = _("Событие календаря")
        verbose_name_plural = _("События календаря")
        ordering = ["start_date", "start_time"]
        indexes = [
            # Новый индекс для календарей
            models.Index(fields=["calendar", "start_date"]),
            # Старые индексы для обратной совместимости
            models.Index(fields=["department", "start_date"]),
            models.Index(fields=["employee", "start_date"]),
            models.Index(fields=["source"]),
        ]

    def __str__(self):
        # Новая логика: приоритет calendar
        if self.calendar_id:
            return f"[{self.calendar.title}] {self.title} ({self.start_date:%d.%m.%Y})"

        # Старая логика
        if self.employee_id:
            scope = f"Личный ({self.employee})"
        elif self.department_id:
            scope = str(self.department)
        else:
            scope = _("Компания")

        if self.end_date:
            return f"{scope}: {self.title} ({self.start_date:%d.%m.%Y}–{self.end_date:%d.%m.%Y})"
        return f"{scope}: {self.title} ({self.start_date:%d.%m.%Y})"

    @property
    def is_legacy_event(self):
        """True если событие использует старую логику (без calendar)."""
        return self.calendar_id is None

    @property
    def is_modern_event(self):
        """True если событие использует новую логику (с calendar)."""
        return self.calendar_id is not None

    def clean(self):
        """Валидация с учётом новой/старой логики."""
        # Если указан calendar — department и employee должны быть пусты
        if self.calendar_id:
            if self.department_id or self.employee_id:
                raise ValidationError(
                    _("При использовании календаря нельзя указывать department или employee.")
                )

        # Старая валидация (только если calendar = NULL)
        if not self.calendar_id:
            if self.department_id and self.employee_id:
                raise ValidationError(
                    _("Событие не может одновременно принадлежать отделу и сотруднику.")
                )

        # ... остальная валидация БЕЗ ИЗМЕНЕНИЙ ...
```

---

## 📊 Сравнение подходов

| Критерий | Полная миграция | Опциональный календарь (РЕКОМЕНДУЕТСЯ) |
|----------|----------------|----------------------------------------|
| **Обратная совместимость** | ❌ Требует миграции данных | ✅ Полная, ничего не ломается |
| **Сложность реализации** | Высокая (12-16 дней) | Средняя (6-8 дней) |
| **Риск поломки** | Высокий | Минимальный |
| **Миграция данных** | Обязательна | Не требуется |
| **Старый код** | Нужно переписать | Работает как раньше |
| **Тесты** | Все переписать | Добавить новые, старые не трогать |
| **Откат** | Сложный | Простой (удалить поле) |
| **Гибкость** | Все через Calendar | На выбор: legacy или modern |
| **Постепенный переход** | ❌ Нет | ✅ Да, по желанию |

---

## 🎯 Логика работы

### Сценарий 1: Старое событие (календарь не указан)

```python
# Создаём событие по-старому (как раньше)
event = CalendarEvent.objects.create(
    department=hr_department,  # Старая логика
    title="Планёрка HR",
    start_date=date(2026, 2, 15),
    all_day=True
)

# ✅ Работает как раньше
# ✅ Отображается в календаре отдела HR
# ✅ Доступ через department_id фильтр
```

### Сценарий 2: Новое событие (с календарём)

```python
# Создаём настраиваемый календарь
training_calendar = Calendar.objects.create(
    title="Обучающие курсы",
    visibility=CalendarVisibility.PUBLIC,
    auto_subscribe_new_users=True,
    default_can_edit=False,  # Только админы могут редактировать
    created_by=admin
)

# Создаём событие в календаре
event = CalendarEvent.objects.create(
    calendar=training_calendar,  # НОВАЯ логика
    title="Python Advanced",
    start_date=date(2026, 3, 1),
    all_day=True
)

# ✅ department и employee игнорируются
# ✅ Права доступа через CalendarSubscription
# ✅ Отображается только подписчикам
```

### Сценарий 3: Смешанное использование

```python
# В одной системе могут быть оба типа событий
legacy_events = CalendarEvent.objects.filter(calendar__isnull=True)  # Старые
modern_events = CalendarEvent.objects.filter(calendar__isnull=False)  # Новые

# API автоматически поддерживает оба типа
all_events = CalendarEvent.objects.all()  # Все события работают
```

---

## 🔌 API (минимальные изменения)

### Обновление ViewSet (обратная совместимость)

```python
# backend/api/v1/calendar/views.py

class CalendarEventsViewSet(ModelViewSet):
    """CRUD событий с поддержкой legacy и modern режимов."""

    def get_queryset(self):
        """Фильтрация с учётом новой и старой логики."""
        qs = super().get_queryset()

        if self.action != "list":
            return qs

        # НОВОЕ: Если передан calendar_id
        calendar_id = self.request.query_params.get('calendar_id')
        if calendar_id:
            return qs.filter(calendar_id=calendar_id)

        # СТАРОЕ: Логика department/employee (без изменений!)
        dep = self._dept_id(required=False)
        emp = self._employee_id(required=False)

        if emp is not None:
            # Legacy: личный календарь
            return qs.filter(
                models.Q(employee_id=emp, calendar__isnull=True) |  # Старые события
                models.Q(calendar__owner_user_id=emp)  # Новые события в личном календаре
            )
        elif dep is not None:
            # Legacy: календарь отдела
            return qs.filter(
                models.Q(department_id=dep, calendar__isnull=True) |  # Старые
                models.Q(calendar__owner_department_id=dep)  # Новые
            )
        else:
            # Legacy: календарь компании
            return qs.filter(
                department__isnull=True,
                employee__isnull=True,
                calendar__isnull=True  # Только старые глобальные события
            )

    def perform_create(self, serializer):
        """Создание с поддержкой обоих режимов."""
        # Если передан calendar_id — используем новую логику
        calendar_id = self.request.data.get('calendar_id')
        if calendar_id:
            serializer.save(
                calendar_id=calendar_id,
                department=None,  # Очищаем legacy поля
                employee=None,
                created_by=self.request.user
            )
        else:
            # Старая логика (без изменений)
            dep = self._dept_id(required=False)
            emp = self._employee_id(required=False)

            if emp is not None:
                serializer.save(employee_id=emp, department=None, created_by=self.request.user)
            else:
                serializer.save(department_id=dep, employee=None, created_by=self.request.user)

        cache.clear()
```

### Новые эндпоинты (опциональные)

```python
# backend/api/v1/calendar/urls.py

urlpatterns = [
    # ✅ Старые эндпоинты РАБОТАЮТ БЕЗ ИЗМЕНЕНИЙ
    path('events/', CalendarEventsViewSet.as_view({'get': 'list', 'post': 'create'})),

    # ✨ Новые эндпоинты для календарей
    path('calendars/', CalendarListCreateView.as_view()),
    path('calendars/<int:pk>/', CalendarDetailView.as_view()),
    path('calendars/<int:pk>/subscribe/', CalendarSubscribeView.as_view()),
    path('calendars/<int:pk>/unsubscribe/', CalendarUnsubscribeView.as_view()),
    path('calendars/my/', MyCalendarsView.as_view()),
]
```

---

## 🚀 План реализации (упрощённый)

### Фаза 1: Модели (1-2 дня)
```bash
# 1. Добавить модели Calendar и CalendarSubscription
#    В models.py, БЕЗ удаления существующих полей
# 2. Добавить поле calendar в CalendarEvent (null=True, blank=True)
# 3. Создать миграции
.venv/Scripts/python backend/manage.py makemigrations
.venv/Scripts/python backend/manage.py migrate
```

### Фаза 2: API (2-3 дня)
```python
# 1. Добавить сериализаторы для Calendar
# 2. Обновить CalendarEventsViewSet (обратная совместимость)
# 3. Добавить ViewSet для Calendar (CRUD)
# 4. Добавить эндпоинты подписок
```

### Фаза 3: Frontend (2-3 дня)
```javascript
// 1. Добавить UI управления календарями (опционально)
// 2. Добавить мультивыбор календарей в виджете
// 3. Старый код РАБОТАЕТ БЕЗ ИЗМЕНЕНИЙ
```

### Фаза 4: Тестирование (1 день)
```python
# 1. Тесты для новых моделей
# 2. Старые тесты НЕ ТРОГАЕМ (они должны пройти!)
# 3. Тесты смешанного режима
```

**Итого: ~6-8 дней** (вместо 12-16)

---

## 📝 Примеры использования

### 1. Создать календарь "Праздники" (админ)

```python
from calendar_app.models import Calendar, CalendarVisibility

holidays = Calendar.objects.create(
    title="Праздники компании",
    description="Официальные праздники и выходные",
    visibility=CalendarVisibility.PUBLIC,
    auto_subscribe_new_users=True,  # Все новые пользователи автоматически подписаны
    color="#FF5733",
    created_by=admin_user
)

# Создать событие
CalendarEvent.objects.create(
    calendar=holidays,  # Привязываем к календарю
    title="Новый год",
    start_date=date(2026, 1, 1),
    recurrence=Recurrence.ANNUAL,
    all_day=True
)
```

### 2. Создать календарь отдела с расшариванием

```python
# HR создаёт календарь "Обучение"
training = Calendar.objects.create(
    title="Обучающие курсы",
    owner_department=hr_department,
    visibility=CalendarVisibility.CUSTOM,
    default_can_edit=False,  # По умолчанию только просмотр
    created_by=hr_manager
)

# Даём право редактирования конкретному сотруднику
from calendar_app.models import CalendarSubscription

CalendarSubscription.objects.create(
    calendar=training,
    user=training_coordinator,
    is_visible=True,
    can_edit=True,  # Может создавать события
    can_manage=False
)

# Разработчики подписываются на календарь
for dev in developers:
    CalendarSubscription.objects.create(
        calendar=training,
        user=dev,
        is_visible=True,
        can_edit=False,  # Только просмотр
        notify_on_new_event=True
    )
```

### 3. Получить все календари пользователя

```python
def get_user_calendars(user):
    """Возвращает все доступные календари."""
    from django.db.models import Q

    # 1. Личные календари
    owned = Calendar.objects.filter(
        owner_user=user,
        is_active=True
    )

    # 2. Календари отделов пользователя
    user_depts = user.departments_links.filter(
        is_active=True
    ).values_list('department_id', flat=True)

    dept_owned = Calendar.objects.filter(
        owner_department_id__in=user_depts,
        is_active=True
    )

    # 3. Публичные календари
    public = Calendar.objects.filter(
        visibility=CalendarVisibility.PUBLIC,
        is_active=True
    )

    # 4. Подписки
    subscribed = Calendar.objects.filter(
        subscriptions__user=user,
        subscriptions__is_visible=True,
        is_active=True
    )

    return (owned | dept_owned | public | subscribed).distinct()
```

### 4. Миграция старого события в новый календарь (опционально)

```python
# Создать календарь для старых событий компании
company_calendar = Calendar.objects.create(
    title="Основной календарь компании",
    visibility=CalendarVisibility.PUBLIC,
    color="#0D6EFD"
)

# Перенести старые события (опционально, не обязательно!)
legacy_events = CalendarEvent.objects.filter(
    department__isnull=True,
    employee__isnull=True,
    calendar__isnull=True  # Только legacy события
)

for event in legacy_events:
    event.calendar = company_calendar
    event.save(update_fields=['calendar'])

# ✅ Теперь они управляются через calendar
# ✅ Но старые события могут продолжать работать по-старому
```

---

## ✨ Преимущества упрощённого подхода

### 1. Нулевой риск поломки
```python
# ✅ Весь существующий код работает БЕЗ ИЗМЕНЕНИЙ
CalendarEvent.objects.filter(department=dept)  # Работает
CalendarEvent.objects.create(employee=user, ...)  # Работает

# ✨ Новый функционал добавляется опционально
CalendarEvent.objects.filter(calendar=calendar)  # Тоже работает
```

### 2. Постепенный переход
```
Шаг 1: Выпустить функционал (все работает как раньше)
Шаг 2: Создать несколько календарей для тестирования
Шаг 3: Постепенно переводить события на новые календари
Шаг 4: В будущем (если нужно) убрать legacy поля
```

### 3. Гибкость выбора
```
Хотите простоту? → Используйте department/employee (как раньше)
Хотите гибкость? → Создавайте Calendar и управляйте правами
Нужны оба? → Система поддерживает смешанный режим
```

### 4. Минимум кода
```
Добавлено: 2 модели (~150 строк)
Изменено: 1 поле в CalendarEvent (~5 строк)
Обновлено: API ViewSet (~50 строк)
Старый код: 0 изменений ✅
```

---

## 🎯 Рекомендация

**Использовать упрощённый подход:**

1. ✅ **Безопасно** — ничего не ломается
2. ✅ **Быстро** — 6-8 дней вместо 12-16
3. ✅ **Гибко** — постепенный переход
4. ✅ **Понятно** — простая логика "есть calendar или нет"
5. ✅ **Масштабируемо** — можно расширять по мере роста

### Следующий шаг:

```bash
# Создать ветку
git checkout -b feature/optional-calendars

# Начать с моделей
# 1. Добавить Calendar и CalendarSubscription в models.py
# 2. Добавить поле calendar в CalendarEvent
# 3. Сделать миграции
```

Хотите, чтобы я начал реализацию с моделей?

---

**Автор:** GitHub Copilot
**Дата:** 11 февраля 2026 г.
