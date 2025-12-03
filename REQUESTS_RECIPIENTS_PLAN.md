# 📋 План улучшения приложения заявлений: добавление получателей и CC-копий

**Дата создания:** 2 декабря 2025 г.  
**Цель:** Добавить в заявления (requests_app) функционал получателей/копий, аналогичный системе documents

---

## 🎯 Обзор задачи

### Текущее состояние
- ✅ Заявка создается одним сотрудником (`employee`)
- ✅ Одобряется/отклоняется одним согласующим (`approver`)
- ✅ Привязана к одному отделу (`department`)
- ✅ Уведомления отправляются: автору, согласующему, руководителю отдела, пользователям с правом `can_process_requests`

### Целевое состояние
- ✅ Заявка может иметь **несколько получателей** (recipients)
- ✅ Получатели могут быть в **копии (CC)** или **основными получателями**
- ✅ Заявка может быть адресована **нескольким отделам** (departments ManyToMany)
- ✅ Уведомления отправляются всем получателям
- ✅ Получатели видят заявку в своем списке "Мне адресовано"
- ✅ Сохраняется обратная совместимость с текущей системой

---

## 📊 Анализ текущей архитектуры

### Модели
**Request** (`requests_app/models.py`)
- `employee` - ForeignKey (автор)
- `approver` - ForeignKey (согласующий)
- `department` - ForeignKey (один отдел)
- Отсутствуют: `recipients`, `cc_users`, `sent_to_all`

**RequestComment** - комментарии к заявке

### API
**RequestViewSet** (`api/v1/requests_app/views.py`)
- CRUD операции
- Экшены: `approve`, `reject`, `cancel`, `comments`
- Права доступа: департаментные права + модельные права
- Queryset фильтрация по отделам и ролям

### Уведомления
**notification_signals.py** (`requests_app/notification_signals.py`)
- `notify_new_request()` - уведомление о новой заявке
- `notify_status_change()` - изменение статуса
- `create_comment_notification()` - новый комментарий
- Получатели: руководитель отдела, approver, пользователи с `can_process_requests`

### Права доступа
- `DeptViewRequest` - просмотр по департаментным правам
- `DeptCanProcess` - обработка по департаментным правам
- `CommentsPermission` - доступ к комментариям
- `NotFinalOrStaff` - запрет удаления финальных заявок

---

## 🏗️ Этапы реализации

---

## **ЭТАП 1: Расширение модели данных**
**Приоритет:** 🔴 Критический  
**Время:** 2-3 часа  
**Риски:** Миграции БД, обратная совместимость

### 1.1. Обновление модели Request

**Файл:** `backend/requests_app/models.py`

```python
# Добавить поля:

# ManyToMany для нескольких отделов (вместо одного ForeignKey)
departments = models.ManyToManyField(
    "employees.Department",
    verbose_name=_("Отделы-получатели"),
    blank=True,
    related_name="received_requests",
    help_text=_("Заявка будет видна всем уполномоченным сотрудникам этих отделов")
)

# Основные получатели
recipients = models.ManyToManyField(
    settings.AUTH_USER_MODEL,
    verbose_name=_("Получатели"),
    blank=True,
    related_name="received_requests",
    help_text=_("Сотрудники, которым адресована заявка")
)

# Копия
cc_users = models.ManyToManyField(
    settings.AUTH_USER_MODEL,
    verbose_name=_("Копия (CC)"),
    blank=True,
    related_name="requests_cc",
    help_text=_("Сотрудники в копии (уведомления без обязанности рассмотрения)")
)

# Флаг для массовой рассылки
sent_to_all_department = models.BooleanField(
    _("Всем сотрудникам отдела"),
    default=False,
    help_text=_("Если включено, заявка видна всем в выбранных отделах")
)

# ВАЖНО: Сохранить старое поле department для обратной совместимости!
# Оставляем как есть, но делаем nullable
department = models.ForeignKey(
    "employees.Department",
    on_delete=models.SET_NULL,
    null=True,
    blank=True,
    verbose_name=_("Основной отдел"),  # переименуем verbose_name
    help_text=_("Устаревшее поле, используйте departments")
)
```

### 1.2. Создание миграции

**Команда:**
```bash
python manage.py makemigrations requests_app -n add_recipients_and_departments
```

**Важные моменты в миграции:**
- ✅ Сделать старое поле `department` nullable
- ✅ Создать data migration для переноса данных из `department` в `departments`
- ✅ Добавить индексы на ManyToMany таблицы
- ✅ Не удалять старое поле `department` (для обратной совместимости)

### 1.3. Data Migration для переноса данных

**Файл:** `backend/requests_app/migrations/000X_migrate_department_to_departments.py`

```python
def migrate_department_to_departments(apps, schema_editor):
    """
    Переносим данные из единичного department в ManyToMany departments
    """
    Request = apps.get_model('requests_app', 'Request')
    
    for request in Request.objects.filter(department__isnull=False):
        request.departments.add(request.department)
        
    print(f"Migrated {Request.objects.exclude(department=None).count()} departments")
```

### 1.4. Обновление методов модели

```python
# В классе Request:

@property
def all_recipients(self):
    """Все получатели: основные + CC"""
    recipient_ids = set(self.recipients.values_list('id', flat=True))
    cc_ids = set(self.cc_users.values_list('id', flat=True))
    return User.objects.filter(id__in=recipient_ids | cc_ids)

@property
def primary_recipients(self):
    """Только основные получатели (без CC)"""
    return self.recipients.all()

def is_recipient(self, user):
    """Проверка, является ли пользователь получателем"""
    return (
        self.recipients.filter(id=user.id).exists() or
        self.cc_users.filter(id=user.id).exists() or
        (self.sent_to_all_department and 
         self.departments.filter(
             employeedepartment__employee=user,
             employeedepartment__is_active=True
         ).exists())
    )

def add_recipient(self, user, is_cc=False):
    """Добавить получателя"""
    if is_cc:
        self.cc_users.add(user)
    else:
        self.recipients.add(user)

def remove_recipient(self, user):
    """Удалить получателя из обеих групп"""
    self.recipients.remove(user)
    self.cc_users.remove(user)
```

---

## **ЭТАП 2: Обновление сериализаторов API**
**Приоритет:** 🔴 Критический  
**Время:** 2-3 часа  
**Зависимости:** Этап 1

### 2.1. Расширение RequestReadSerializer

**Файл:** `backend/api/v1/requests_app/serializers.py`

```python
from ..employees.serializers import EmployeeBriefSerializer

class RequestReadSerializer(serializers.ModelSerializer):
    """Сериализатор чтения заявки с получателями."""
    
    employee = EmployeeBriefSerializer(read_only=True)
    approver = EmployeeBriefSerializer(read_only=True)
    
    # Новые поля
    departments = serializers.PrimaryKeyRelatedField(
        many=True, read_only=True
    )
    recipients = EmployeeBriefSerializer(many=True, read_only=True)
    cc_users = EmployeeBriefSerializer(many=True, read_only=True)
    
    # Вычисляемые поля
    recipient_count = serializers.SerializerMethodField()
    cc_count = serializers.SerializerMethodField()
    is_recipient = serializers.SerializerMethodField()
    
    class Meta:
        model = Request
        fields = (
            # ... существующие поля ...
            "departments",
            "recipients",
            "cc_users",
            "sent_to_all_department",
            "recipient_count",
            "cc_count",
            "is_recipient",
        )
    
    def get_recipient_count(self, obj):
        """Количество получателей"""
        if obj.sent_to_all_department:
            # Считаем всех сотрудников выбранных отделов
            return obj.departments.aggregate(
                total=models.Count(
                    'employeedepartment',
                    filter=models.Q(employeedepartment__is_active=True)
                )
            )['total'] or 0
        return obj.recipients.count()
    
    def get_cc_count(self, obj):
        return obj.cc_users.count()
    
    def get_is_recipient(self, obj):
        """Является ли текущий пользователь получателем"""
        request = self.context.get('request')
        if not request or not request.user:
            return False
        return obj.is_recipient(request.user)
```

### 2.2. Создание поля RecipientIDsField

**Аналогично documents - для поддержки разных форматов:**

```python
class RecipientIDsField(serializers.ListField):
    """
    Принимает recipient_ids в форматах:
    - repeat params: ?recipient_ids=1&recipient_ids=2
    - JSON string: {"recipient_ids": "[1,2,3]"}
    - CSV: {"recipient_ids": "1,2,3"}
    - JSON list: {"recipient_ids": [1,2,3]}
    """
    
    child = serializers.IntegerField(min_value=1)
    
    def to_internal_value(self, data):
        # ... реализация как в DocumentWriteSerializer
        pass
```

### 2.3. Обновление RequestWriteSerializer

```python
class RequestWriteSerializer(serializers.ModelSerializer):
    """Сериализатор записи заявки с получателями."""
    
    # Существующие поля...
    
    # Новые поля
    department_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Department.objects.all(),
        source='departments',
        required=False
    )
    recipient_ids = RecipientIDsField(required=False, allow_empty=True)
    cc_user_ids = RecipientIDsField(required=False, allow_empty=True)
    sent_to_all_department = serializers.BooleanField(required=False, default=False)
    
    class Meta:
        model = Request
        fields = (
            # ... существующие ...
            "department_ids",
            "recipient_ids", 
            "cc_user_ids",
            "sent_to_all_department",
        )
    
    def validate(self, attrs):
        """Валидация получателей и отделов"""
        sent_to_all = attrs.get('sent_to_all_department', False)
        recipient_ids = attrs.get('recipient_ids', [])
        departments = attrs.get('departments', [])
        
        # Если sent_to_all_department=True, должны быть указаны отделы
        if sent_to_all and not departments:
            raise serializers.ValidationError({
                'department_ids': 'Укажите отделы для массовой рассылки'
            })
        
        # Если sent_to_all_department=False и нет отделов, должны быть получатели
        if not sent_to_all and not departments and not recipient_ids:
            raise serializers.ValidationError({
                'recipient_ids': 'Укажите получателей или отделы'
            })
        
        # Автор не может быть в получателях
        request = self.context.get('request')
        if request and request.user:
            employee_id = attrs.get('employee', request.user).id
            if employee_id in recipient_ids:
                raise serializers.ValidationError({
                    'recipient_ids': 'Автор не может быть получателем'
                })
        
        return attrs
    
    def _set_recipients(self, request_obj, recipient_ids, is_cc=False):
        """Устанавливает получателей (фильтрует только активных)"""
        if not recipient_ids:
            if is_cc:
                request_obj.cc_users.clear()
            else:
                request_obj.recipients.clear()
            return
        
        users = User.objects.filter(
            id__in=recipient_ids,
            is_active=True
        )
        
        if is_cc:
            request_obj.cc_users.set(users)
        else:
            request_obj.recipients.set(users)
    
    def create(self, validated_data):
        """Создание с получателями"""
        recipient_ids = validated_data.pop('recipient_ids', [])
        cc_user_ids = validated_data.pop('cc_user_ids', [])
        departments = validated_data.pop('departments', [])
        
        # Создаем заявку
        request_obj = super().create(validated_data)
        
        # Устанавливаем связи
        if departments:
            request_obj.departments.set(departments)
        
        self._set_recipients(request_obj, recipient_ids, is_cc=False)
        self._set_recipients(request_obj, cc_user_ids, is_cc=True)
        
        return request_obj
    
    def update(self, instance, validated_data):
        """Обновление с получателями"""
        recipient_ids = validated_data.pop('recipient_ids', None)
        cc_user_ids = validated_data.pop('cc_user_ids', None)
        departments = validated_data.pop('departments', None)
        
        # Обновляем основные поля
        instance = super().update(instance, validated_data)
        
        # Обновляем связи только если переданы
        if departments is not None:
            instance.departments.set(departments)
        
        if recipient_ids is not None:
            self._set_recipients(instance, recipient_ids, is_cc=False)
        
        if cc_user_ids is not None:
            self._set_recipients(instance, cc_user_ids, is_cc=True)
        
        return instance
```

---

## **ЭТАП 3: Обновление логики доступа и queryset**
**Приоритет:** 🔴 Критический  
**Время:** 2-4 часа  
**Зависимости:** Этап 1, 2

### 3.1. Расширение get_queryset в RequestViewSet

**Файл:** `backend/api/v1/requests_app/views.py`

```python
def get_queryset(self) -> QuerySet[EmployeeRequest]:
    """
    Список заявок с учётом получателей:
    - staff/глобальные видят всё
    - автор видит свои заявки
    - получатели (recipients/cc_users) видят адресованные им
    - сотрудники отделов видят заявки отделов (с правами)
    """
    qs = super().get_queryset()
    user = self.request.user
    params = self.request.query_params
    
    mine_raw = (params.get("mine") or "").lower()
    want_mine = (params.get("view") == "mine") or (
        mine_raw in {"1", "true", "yes", "on"}
    )
    
    # Новый параметр для фильтрации "мне адресовано"
    addressed_to_me = params.get("addressed_to_me") == "true"
    
    if user.is_staff or self._can_view_all(user):
        if want_mine:
            qs = qs.filter(employee_id=user.id)
        elif addressed_to_me:
            # Заявки, где я получатель
            qs = qs.filter(
                Q(recipients=user) | Q(cc_users=user) |
                Q(
                    sent_to_all_department=True,
                    departments__in=user.employee_departments.filter(
                        is_active=True
                    ).values_list('department_id', flat=True)
                )
            ).distinct()
    else:
        # Обычный пользователь
        scope = Q(employee_id=user.id)  # Свои заявки
        
        # Заявки, где я получатель
        scope |= Q(recipients=user) | Q(cc_users=user)
        
        # Заявки отделов с sent_to_all_department
        my_dept_ids = user.employee_departments.filter(
            is_active=True
        ).values_list('department_id', flat=True)
        
        if my_dept_ids:
            scope |= Q(
                sent_to_all_department=True,
                departments__in=my_dept_ids
            )
        
        # Департаментные права (как было)
        view_dept_ids = (
            EmployeeDepartment.objects.filter(
                employee_id=user.id,
                is_active=True,
                role__scoped_permissions__code="view_request",
            )
            .values_list("department_id", flat=True)
            .distinct()
        )
        
        if view_dept_ids:
            scope |= Q(departments__in=view_dept_ids)
        
        # Фильтр "только адресованные мне"
        if addressed_to_me:
            scope = (
                Q(recipients=user) | Q(cc_users=user) |
                Q(sent_to_all_department=True, departments__in=my_dept_ids)
            )
        elif want_mine:
            scope = Q(employee_id=user.id)
        
        qs = qs.filter(scope).distinct()
    
    # Применяем фильтры type/status
    t = (params.get("type") or "").strip()
    s = (params.get("status") or "").strip()
    if t:
        qs = qs.filter(type=t)
    if s:
        qs = qs.filter(status=s)
    
    return qs
```

### 3.2. Обновление пермишенов

**Файл:** `backend/api/v1/requests_app/permissions.py`

Добавить проверку получателей:

```python
class RequestRecipientPermission(BasePermission):
    """
    Получатель заявки имеет право на просмотр
    """
    
    def has_object_permission(self, request, view, obj):
        user = request.user
        
        # Staff видит всё
        if user.is_staff:
            return True
        
        # Автор видит свою заявку
        if obj.employee_id == user.id:
            return True
        
        # Получатель (основной или CC) видит заявку
        if obj.is_recipient(user):
            return True
        
        # Департаментные права
        # ... существующая логика ...
        
        return False
```

---

## **ЭТАП 4: Обновление системы уведомлений**
**Приоритет:** 🟡 Высокий  
**Время:** 3-4 часа  
**Зависимости:** Этап 1, 2, 3

### 4.1. Обновление notify_new_request

**Файл:** `backend/requests_app/notification_signals.py`

```python
def notify_new_request(request_obj):
    """
    Отправляет уведомление о новой заявке:
    - Всем основным получателям (recipients)
    - Всем в копии (cc_users)
    - Согласующему (approver)
    - Руководителям отделов
    - Пользователям с правом can_process_requests
    
    При sent_to_all_department=True отправляет всем сотрудникам отделов
    """
    recipients_set = set()
    
    # 1. Основные получатели
    for recipient in request_obj.recipients.filter(is_active=True):
        recipients_set.add(recipient)
    
    # 2. Копия (CC)
    for cc_user in request_obj.cc_users.filter(is_active=True):
        recipients_set.add(cc_user)
    
    # 3. Если sent_to_all_department - все сотрудники отделов
    if request_obj.sent_to_all_department:
        dept_employees = User.objects.filter(
            employee_departments__department__in=request_obj.departments.all(),
            employee_departments__is_active=True,
            is_active=True
        ).exclude(id=request_obj.employee.id).distinct()
        
        recipients_set.update(dept_employees)
    
    # 4. Согласующий
    if request_obj.approver and request_obj.approver.id != request_obj.employee.id:
        recipients_set.add(request_obj.approver)
    
    # 5. Руководители отделов
    for department in request_obj.departments.all():
        if department.head and department.head.id != request_obj.employee.id:
            recipients_set.add(department.head)
    
    # 6. Пользователи с правом обрабатывать заявки в этих отделах
    dept_processors = User.objects.filter(
        employee_departments__department__in=request_obj.departments.all(),
        employee_departments__is_active=True,
        employee_departments__role__scoped_permissions__code='can_process_requests',
        is_active=True
    ).exclude(id=request_obj.employee.id).distinct()
    
    recipients_set.update(dept_processors)
    
    # Определяем тип уведомления для каждого получателя
    author_name = request_obj.employee.get_full_name() or request_obj.employee.username
    
    for recipient in recipients_set:
        # Определяем роль получателя
        is_primary = request_obj.recipients.filter(id=recipient.id).exists()
        is_cc = request_obj.cc_users.filter(id=recipient.id).exists()
        is_approver = request_obj.approver_id == recipient.id
        
        # Формируем заголовок и сообщение
        if is_approver:
            title = f'Новая заявка на согласование от {author_name}'
            notification_type = 'request_new_to_approve'
        elif is_primary:
            title = f'Вам адресована заявка от {author_name}'
            notification_type = 'request_new_to_recipient'
        elif is_cc:
            title = f'Вы в копии заявки от {author_name}'
            notification_type = 'request_new_cc'
        else:
            title = f'Новая заявка в отделе от {author_name}'
            notification_type = 'request_new_dept'
        
        message = (
            f'Тип: {request_obj.get_type_display()}. '
            f'{request_obj.comment[:100] if request_obj.comment else ""}'
        )
        
        NotificationService.create_notification(
            recipient=recipient,
            notification_type_code=notification_type,
            title=title,
            message=message,
            content_object=request_obj,
            action_url=f'/requests/{request_obj.id}/',
            metadata={
                'request_id': request_obj.id,
                'request_type': request_obj.type,
                'employee_id': request_obj.employee.id,
                'is_primary_recipient': is_primary,
                'is_cc': is_cc,
                'is_approver': is_approver,
            }
        )
```

### 4.2. Обновление notify_status_change

```python
def notify_status_change(request_obj, old_status, new_status):
    """
    Уведомляет о изменении статуса:
    - Автора
    - Всех получателей (recipients)
    - Всех в копии (cc_users)
    """
    recipients_to_notify = set()
    
    # 1. Автор
    recipients_to_notify.add(request_obj.employee)
    
    # 2. Основные получатели
    recipients_to_notify.update(request_obj.recipients.filter(is_active=True))
    
    # 3. Копия
    recipients_to_notify.update(request_obj.cc_users.filter(is_active=True))
    
    # Формируем уведомления
    for recipient in recipients_to_notify:
        if new_status == 'approved':
            notification_type = 'request_approved'
            title = 'Заявка одобрена'
            # ... existing logic ...
        # ... rest of the logic ...
```

### 4.3. Обновление create_comment_notification

```python
def create_comment_notification(comment):
    """
    Уведомляет о новом комментарии:
    - Автора заявки
    - Всех получателей
    - Всех в копии
    - Согласующего
    """
    request_obj = comment.request
    author = comment.author
    recipients_set = set()
    
    # Автор заявки
    if request_obj.employee.id != author.id:
        recipients_set.add(request_obj.employee)
    
    # Получатели
    recipients_set.update(
        request_obj.recipients.filter(is_active=True).exclude(id=author.id)
    )
    
    # CC
    recipients_set.update(
        request_obj.cc_users.filter(is_active=True).exclude(id=author.id)
    )
    
    # Согласующий
    if request_obj.approver and request_obj.approver.id != author.id:
        recipients_set.add(request_obj.approver)
    
    # Отправляем уведомления
    for recipient in recipients_set:
        NotificationService.create_notification(
            # ... existing logic ...
        )
```

### 4.4. Создание новых типов уведомлений

**Файл:** `backend/notifications/fixtures/notification_types.json` (или через админку)

Добавить новые типы:
- `request_new_to_recipient` - Вам адресована заявка
- `request_new_cc` - Вы в копии заявки
- `request_new_dept` - Новая заявка в отделе

---

## **ЭТАП 5: Обновление фронтенда**
**Приоритет:** 🟡 Высокий  
**Время:** 4-6 часов  
**Зависимости:** Этап 1, 2, 3, 4

### 5.1. Создание компонента RecipientPicker

**Файл:** `backend/static/js/components/requestRecipientPicker.js`

Взять за основу `documentCrudHandler.js` и адаптировать:

```javascript
class RequestRecipientPicker {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            multiple: true,
            showCC: true,
            allowDepartments: true,
            ...options
        };
        this.init();
    }
    
    init() {
        this.renderPicker();
        this.attachEventListeners();
    }
    
    async searchEmployees(query) {
        // Поиск через /api/v1/employees/?search=...
    }
    
    addRecipient(employee, isCC = false) {
        // Добавить получателя или CC
    }
    
    removeRecipient(employeeId) {
        // Удалить получателя
    }
    
    getRecipientIds() {
        // Получить ID получателей для отправки
        return {
            recipient_ids: [...this.recipients],
            cc_user_ids: [...this.ccUsers]
        };
    }
    
    renderPicker() {
        this.container.innerHTML = `
            <div class="recipient-picker">
                <div class="form-check mb-2">
                    <input type="checkbox" id="sentToAllDept" 
                           class="form-check-input">
                    <label class="form-check-label" for="sentToAllDept">
                        Всем сотрудникам отделов
                    </label>
                </div>
                
                <div id="departmentSelect" style="display:none">
                    <label>Выберите отделы:</label>
                    <select id="deptMultiSelect" multiple class="form-select">
                        <!-- Загружаем через API -->
                    </select>
                </div>
                
                <div id="recipientSelect">
                    <label>Получатели:</label>
                    <input type="text" id="recipientSearch" 
                           class="form-control" 
                           placeholder="Поиск сотрудников...">
                    <div id="recipientResults" class="list-group mt-2"></div>
                    <div id="selectedRecipients" class="mt-2"></div>
                </div>
                
                <div id="ccSelect" class="mt-3">
                    <label>Копия (CC):</label>
                    <input type="text" id="ccSearch" 
                           class="form-control" 
                           placeholder="Поиск для копии...">
                    <div id="ccResults" class="list-group mt-2"></div>
                    <div id="selectedCC" class="mt-2"></div>
                </div>
            </div>
        `;
    }
}
```

### 5.2. Обновление форм создания/редактирования

**Файлы:** 
- `backend/templates/requests_app/request_form.html`
- `backend/templates/requests_app/request_list_full.html` (модалки)

Добавить блок выбора получателей:

```html
<div class="mb-3">
    <label class="form-label">Кому адресована заявка</label>
    <div id="recipientPicker"></div>
</div>

<script>
const picker = new RequestRecipientPicker('recipientPicker', {
    showCC: true,
    allowDepartments: true
});

// При сабмите формы
form.addEventListener('submit', async (e) => {
    e.preventDefault();
    
    const formData = new FormData(form);
    const recipientData = picker.getRecipientIds();
    
    // Добавляем recipient_ids как повторяющиеся параметры
    recipientData.recipient_ids.forEach(id => {
        formData.append('recipient_ids', id);
    });
    
    recipientData.cc_user_ids.forEach(id => {
        formData.append('cc_user_ids', id);
    });
    
    // Отправка через API
    const response = await fetch('/api/v1/requests/', {
        method: 'POST',
        headers: {
            'Authorization': `Bearer ${apiToken}`,
        },
        body: formData
    });
    
    // ...
});
</script>
```

### 5.3. Обновление списка заявлений

**Файл:** `backend/templates/requests_app/request_list_full.html`

Добавить:
- Фильтр "Мне адресовано" (`?addressed_to_me=true`)
- Отображение получателей в карточке заявки
- Индикаторы CC

```html
<!-- Фильтры -->
<div class="btn-group" role="group">
    <input type="radio" class="btn-check" name="viewMode" 
           id="viewMy" value="mine" checked>
    <label class="btn btn-outline-primary" for="viewMy">Мои</label>
    
    <input type="radio" class="btn-check" name="viewMode" 
           id="viewAddressed" value="addressed">
    <label class="btn btn-outline-primary" for="viewAddressed">
        Мне адресовано
    </label>
    
    <input type="radio" class="btn-check" name="viewMode" 
           id="viewAll" value="all">
    <label class="btn btn-outline-primary" for="viewAll">Все</label>
</div>

<!-- В карточке заявки -->
<div class="request-recipients mt-2">
    <small class="text-muted">
        <i class="bi-people"></i>
        Получатели: 
        <span class="recipients-list">
            <!-- Аватарки получателей -->
        </span>
        {% if request.cc_count > 0 %}
        <span class="badge bg-secondary ms-2">
            +{{ request.cc_count }} в копии
        </span>
        {% endif %}
    </small>
</div>
```

### 5.4. Детальная страница заявки

**Файл:** `backend/templates/requests_app/request_detail.html`

Добавить секцию получателей:

```html
<div class="card mb-3">
    <div class="card-header">
        <i class="bi-people"></i> Получатели
    </div>
    <div class="card-body">
        <h6>Адресовано:</h6>
        <div class="recipients-grid">
            {% for recipient in request.recipients.all %}
            <div class="recipient-item">
                <img src="{{ recipient.avatar.url }}" 
                     class="avatar-sm rounded-circle">
                <span>{{ recipient.get_full_name }}</span>
            </div>
            {% endfor %}
        </div>
        
        {% if request.cc_users.all %}
        <h6 class="mt-3">Копия (CC):</h6>
        <div class="cc-grid">
            {% for cc_user in request.cc_users.all %}
            <div class="cc-item">
                <img src="{{ cc_user.avatar.url }}" 
                     class="avatar-sm rounded-circle opacity-75">
                <span class="text-muted">{{ cc_user.get_full_name }}</span>
            </div>
            {% endfor %}
        </div>
        {% endif %}
    </div>
</div>
```

---

## **ЭТАП 6: Обновление админки**
**Приоритет:** 🟢 Средний  
**Время:** 1-2 часа  
**Зависимости:** Этап 1

### 6.1. Обновление RequestAdmin

**Файл:** `backend/requests_app/admin.py`

```python
@admin.register(Request)
class RequestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "display_title",
        "type",
        "status",
        "employee",
        "get_departments",  # Новое
        "get_recipients_count",  # Новое
        "get_cc_count",  # Новое
        "date_from",
        "date_to",
        "decided_at",
        "created_at",
    )
    
    filter_horizontal = ('recipients', 'cc_users', 'departments')
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('employee', 'type', 'title', 'status')
        }),
        ('Получатели', {
            'fields': (
                'sent_to_all_department',
                'departments',
                'recipients',
                'cc_users',
                'approver',
            )
        }),
        # ... остальные fieldsets ...
    )
    
    def get_departments(self, obj):
        return ", ".join([d.name for d in obj.departments.all()[:3]])
    get_departments.short_description = 'Отделы'
    
    def get_recipients_count(self, obj):
        return obj.recipients.count()
    get_recipients_count.short_description = 'Получателей'
    
    def get_cc_count(self, obj):
        return obj.cc_users.count()
    get_cc_count.short_description = 'Копий'
```

---

## **ЭТАП 7: Тестирование**
**Приоритет:** 🔴 Критический  
**Время:** 4-6 часов  
**Зависимости:** Все предыдущие этапы

### 7.1. Unit-тесты моделей

**Файл:** `backend/tests/requests_app/test_recipients_models.py`

```python
class TestRequestRecipients(TestCase):
    def test_add_recipient(self):
        """Тест добавления получателя"""
        request = make_request()
        user = make_user()
        
        request.add_recipient(user, is_cc=False)
        
        assert request.recipients.filter(id=user.id).exists()
        assert not request.cc_users.filter(id=user.id).exists()
    
    def test_is_recipient(self):
        """Тест проверки получателя"""
        request = make_request()
        recipient = make_user()
        cc_user = make_user()
        random_user = make_user()
        
        request.add_recipient(recipient, is_cc=False)
        request.add_recipient(cc_user, is_cc=True)
        
        assert request.is_recipient(recipient)
        assert request.is_recipient(cc_user)
        assert not request.is_recipient(random_user)
    
    def test_sent_to_all_department(self):
        """Тест рассылки всем в отделе"""
        dept = Department.objects.create(name="IT")
        user1 = make_user()
        user2 = make_user()
        
        EmployeeDepartment.objects.create(
            employee=user1, department=dept, is_active=True
        )
        EmployeeDepartment.objects.create(
            employee=user2, department=dept, is_active=True
        )
        
        request = make_request(sent_to_all_department=True)
        request.departments.add(dept)
        
        assert request.is_recipient(user1)
        assert request.is_recipient(user2)
```

### 7.2. API-тесты

**Файл:** `backend/tests/api/v1/requests_app/test_recipients_api.py`

```python
class TestRequestRecipientsAPI(TestCase):
    def test_create_with_recipients(self):
        """Тест создания заявки с получателями"""
        author = make_user()
        recipient1 = make_user()
        recipient2 = make_user()
        
        client = APIClient()
        client.force_authenticate(user=author)
        
        response = client.post('/api/v1/requests/', {
            'type': 'vacation',
            'date_from': '2025-12-10',
            'date_to': '2025-12-20',
            'recipient_ids': [recipient1.id, recipient2.id],
        })
        
        assert response.status_code == 201
        data = response.json()
        assert data['recipient_count'] == 2
    
    def test_filter_addressed_to_me(self):
        """Тест фильтра 'мне адресовано'"""
        author = make_user()
        recipient = make_user()
        
        request1 = make_request(employee=author)
        request1.recipients.add(recipient)
        
        request2 = make_request(employee=author)
        # recipient не в получателях
        
        client = APIClient()
        client.force_authenticate(user=recipient)
        
        response = client.get('/api/v1/requests/?addressed_to_me=true')
        
        assert response.status_code == 200
        data = response.json()
        assert len(data) == 1
        assert data[0]['id'] == request1.id
    
    def test_notifications_to_recipients(self):
        """Тест отправки уведомлений получателям"""
        author = make_user()
        recipient1 = make_user()
        cc_user = make_user()
        
        client = APIClient()
        client.force_authenticate(user=author)
        
        response = client.post('/api/v1/requests/', {
            'type': 'other',
            'title': 'Test request',
            'recipient_ids': [recipient1.id],
            'cc_user_ids': [cc_user.id],
        })
        
        assert response.status_code == 201
        
        # Проверяем уведомления
        notif_recipient = Notification.objects.filter(
            recipient=recipient1,
            notification_type__code='request_new_to_recipient'
        ).first()
        assert notif_recipient is not None
        
        notif_cc = Notification.objects.filter(
            recipient=cc_user,
            notification_type__code='request_new_cc'
        ).first()
        assert notif_cc is not None
```

### 7.3. Интеграционные тесты

**Файл:** `backend/tests/requests_app/test_recipients_integration.py`

```python
class TestRequestRecipientsIntegration(TestCase):
    def test_full_workflow_with_recipients(self):
        """Полный цикл заявки с получателями"""
        # 1. Создание
        author = make_user()
        recipient = make_user()
        approver = make_user()
        
        request = Request.objects.create(
            employee=author,
            type='vacation',
            title='Test',
            approver=approver
        )
        request.recipients.add(recipient)
        
        # 2. Проверка видимости
        assert request.is_recipient(recipient)
        
        # 3. Одобрение
        request.approve(by_user=approver)
        
        # 4. Проверка уведомлений
        notifs = Notification.objects.filter(
            recipient=recipient,
            metadata__request_id=request.id
        )
        assert notifs.count() >= 2  # Создание + одобрение
        
        # 5. Комментарий
        comment = RequestComment.objects.create(
            request=request,
            author=approver,
            text='Approved'
        )
        
        # 6. Проверка уведомления о комментарии
        comment_notif = Notification.objects.filter(
            recipient=recipient,
            notification_type__code='request_comment'
        ).first()
        assert comment_notif is not None
```

---

## **ЭТАП 8: Документация и миграция данных**
**Приоритет:** 🟢 Средний  
**Время:** 2-3 часа  
**Зависимости:** Все предыдущие этапы

### 8.1. Документация для пользователей

**Файл:** `REQUESTS_RECIPIENTS_GUIDE.md`

Создать руководство:
- Как создать заявку с получателями
- Разница между получателями и CC
- Как отфильтровать заявки "мне адресовано"
- Настройка уведомлений

### 8.2. Документация для разработчиков

**Файл:** `docs/api/requests_recipients_api.md`

API документация:
- Новые поля в сериализаторах
- Новые query параметры
- Примеры запросов

### 8.3. Changelog

**Файл:** `CHANGELOG.md`

```markdown
## [2.0.0] - 2025-12-XX

### Added
- ✨ Множественные получатели для заявлений (recipients)
- ✨ Копия (CC) для заявлений (cc_users)
- ✨ Поддержка нескольких отделов (departments ManyToMany)
- ✨ Флаг "Всем сотрудникам отдела" (sent_to_all_department)
- ✨ Фильтр "Мне адресовано" в API и UI
- ✨ Компонент RecipientPicker для выбора получателей
- ✨ Новые типы уведомлений для получателей

### Changed
- 🔄 Поле department теперь nullable (для обратной совместимости)
- 🔄 Логика уведомлений учитывает получателей
- 🔄 Права доступа расширены для получателей
- 🔄 UI форм создания/редактирования заявлений

### Migration
- ⚠️ Требуется миграция БД: `python manage.py migrate requests_app`
- ⚠️ Старые заявки с department будут автоматически перенесены в departments
```

---

## 📋 Чек-лист выполнения

### Перед началом
- [ ] Создать feature-ветку `feature/requests-recipients`
- [ ] Создать backup базы данных
- [ ] Убедиться, что все тесты проходят

### Этап 1: Модели (2-3 часа)
- [ ] Добавить поля в модель Request
- [ ] Создать миграции
- [ ] Создать data migration
- [ ] Добавить методы в модель
- [ ] Запустить миграции на dev
- [ ] Проверить в админке

### Этап 2: Сериализаторы (2-3 часа)
- [ ] Обновить RequestReadSerializer
- [ ] Создать RecipientIDsField
- [ ] Обновить RequestWriteSerializer
- [ ] Добавить валидацию
- [ ] Тестировать через API консоль

### Этап 3: Права доступа (2-4 часа)
- [ ] Обновить get_queryset
- [ ] Добавить фильтр addressed_to_me
- [ ] Обновить пермишены
- [ ] Тестировать доступ

### Этап 4: Уведомления (3-4 часа)
- [ ] Обновить notify_new_request
- [ ] Обновить notify_status_change
- [ ] Обновить create_comment_notification
- [ ] Создать типы уведомлений
- [ ] Тестировать отправку

### Этап 5: Фронтенд (4-6 часов)
- [ ] Создать RequestRecipientPicker
- [ ] Обновить форму создания
- [ ] Обновить список заявлений
- [ ] Обновить детальную страницу
- [ ] Тестировать UI

### Этап 6: Админка (1-2 часа)
- [ ] Обновить RequestAdmin
- [ ] Добавить filter_horizontal
- [ ] Тестировать в админке

### Этап 7: Тесты (4-6 часов)
- [ ] Unit-тесты моделей
- [ ] API-тесты
- [ ] Интеграционные тесты
- [ ] Все тесты проходят

### Этап 8: Документация (2-3 часа)
- [ ] Руководство пользователя
- [ ] API документация
- [ ] Changelog
- [ ] README обновлен

### Финал
- [ ] Code review
- [ ] QA тестирование
- [ ] Merge в master
- [ ] Deploy на staging
- [ ] Deploy на production

---

## ⚠️ Риски и меры по снижению

### Риск 1: Проблемы с миграцией БД
**Вероятность:** Средняя  
**Воздействие:** Высокое  
**Меры:**
- Тестировать миграции на копии production БД
- Создать rollback скрипты
- Сохранить старое поле `department` для обратной совместимости

### Риск 2: Производительность при большом количестве получателей
**Вероятность:** Средняя  
**Воздействие:** Среднее  
**Меры:**
- Использовать `prefetch_related` для получателей
- Добавить индексы на ManyToMany таблицы
- Использовать bulk_create для уведомлений

### Риск 3: Конфликты с существующей системой прав
**Вероятность:** Низкая  
**Воздействие:** Высокое  
**Меры:**
- Сохранить всю существующую логику прав
- Добавить новую логику через OR условия
- Покрыть тестами все сценарии доступа

### Риск 4: Проблемы с уведомлениями (spam)
**Вероятность:** Средняя  
**Воздействие:** Среднее  
**Меры:**
- Добавить настройки частоты уведомлений
- Группировать уведомления
- Добавить batch отправку

---

## 🎯 Критерии приемки

### Функциональные требования
- [x] Можно создать заявку с несколькими получателями
- [x] Можно добавить пользователей в копию (CC)
- [x] Можно выбрать несколько отделов
- [x] Можно включить "Всем сотрудникам отдела"
- [x] Получатели видят заявку в "Мне адресовано"
- [x] Получатели получают уведомления
- [x] CC получают уведомления с меткой "копия"
- [x] Автор видит список получателей
- [x] Можно редактировать получателей до финального статуса
- [x] Старые заявки продолжают работать

### Нефункциональные требования
- [x] Время отклика API < 500ms
- [x] UI responsive на мобильных
- [x] Покрытие тестами > 80%
- [x] Документация полная и актуальная
- [x] Обратная совместимость сохранена

---

## 📅 Оценка времени

| Этап | Время (часы) | Сложность |
|------|-------------|-----------|
| 1. Модели | 2-3 | 🟡 Средняя |
| 2. Сериализаторы | 2-3 | 🟡 Средняя |
| 3. Права доступа | 2-4 | 🔴 Высокая |
| 4. Уведомления | 3-4 | 🔴 Высокая |
| 5. Фронтенд | 4-6 | 🔴 Высокая |
| 6. Админка | 1-2 | 🟢 Низкая |
| 7. Тесты | 4-6 | 🟡 Средняя |
| 8. Документация | 2-3 | 🟢 Низкая |
| **ИТОГО** | **20-31 час** | **2-4 дня** |

---

## 🚀 Рекомендации по внедрению

### Поэтапное внедрение
1. **Week 1:** Этапы 1-3 (Backend core)
2. **Week 2:** Этапы 4-5 (Уведомления + Frontend)
3. **Week 3:** Этапы 6-8 (Админка + Тесты + Docs)

### Feature Flags
Рассмотреть использование feature flag для постепенного включения:

```python
# settings.py
FEATURES = {
    'requests_recipients': env.bool('FEATURE_REQUESTS_RECIPIENTS', default=False)
}

# В коде
if settings.FEATURES['requests_recipients']:
    # Новая логика с получателями
else:
    # Старая логика
```

### Мониторинг
- Логировать создание заявок с получателями
- Мониторить время отправки уведомлений
- Отслеживать ошибки миграции

---

## 💡 Будущие улучшения (после основной реализации)

1. **Группы получателей**
   - Создание групп рассылки
   - Шаблоны получателей

2. **Умные рекомендации**
   - Автоматическое предложение получателей на основе типа заявки
   - ML для предсказания согласующих

3. **Workflow**
   - Последовательное согласование
   - Параллельное согласование
   - Условные маршруты

4. **Аналитика**
   - Дашборд по заявкам отдела
   - Статистика по получателям
   - Время обработки

---

**Автор плана:** AI Assistant  
**Дата:** 2 декабря 2025 г.  
**Версия:** 1.0
