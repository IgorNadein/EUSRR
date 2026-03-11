# Рефакторинг модели Chat: Сравнение

## ❌ ТЕКУЩАЯ ВЕРСИЯ (с бизнес-логикой EUSRR)

```python
# backend/communications/models.py (СТАРАЯ ВЕРСИЯ)

from employees.models import Department, EmployeeDepartment  # ← жесткая зависимость

class Chat(models.Model):
    # ❌ Специфичные типы для EUSRR
    CHAT_TYPE_CHOICES = [
        ("private", "Личный"),
        ("group", "Групповой"),
        ("department", "Отдел"),        # ← EUSRR специфично
        ("channel", "Канал"),
        ("announcement", "Объявления"),
        ("global", "Глобальный"),       # ← EUSRR специфично
    ]
    
    type = models.CharField(max_length=16, choices=CHAT_TYPE_CHOICES, db_index=True)
    name = models.CharField(max_length=255, blank=True)
    description = models.TextField(blank=True)
    avatar = models.ImageField(upload_to='chat_avatars/%Y/%m/', null=True, blank=True)
    created_by = models.ForeignKey(settings.AUTH_USER_MODEL, ...)
    
    # ❌ Специфичное название поля
    include_all_employees = models.BooleanField(default=False)  # ← "employees" специфично
    
    participants = models.ManyToManyField(settings.AUTH_USER_MODEL, blank=True, related_name="chats")
    
    # ❌ Жесткая FK на Department
    department = models.ForeignKey(
        Department,  # ← жесткая зависимость от employees app
        null=True,
        blank=True,
        on_delete=models.CASCADE
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    
    # ❌ EUSRR-специфичное поле
    is_main = models.BooleanField(default=False)  # ← бизнес-правило EUSRR
    
    is_blocked = models.BooleanField(default=False)
    blocked_at = models.DateTimeField(null=True, blank=True)
    blocked_by = models.ForeignKey(settings.AUTH_USER_MODEL, ...)
    can_reply = models.BooleanField(default=True)
    
    class Meta:
        constraints = [
            # ❌ EUSRR-специфичные constraints
            models.UniqueConstraint(
                fields=["type"],
                condition=Q(is_main=True, type="global"),
                name="unique_main_global_chat",
            ),
            models.UniqueConstraint(
                fields=["type", "department"],  # ← привязка к Department
                condition=Q(is_main=True, type="department"),
                name="unique_main_department_chat",
            ),
            models.UniqueConstraint(
                fields=["type", "created_by"],
                condition=Q(type="announcement"),
                name="unique_announcement_per_user",
            ),
        ]
        indexes = [
            models.Index(fields=["department"]),  # ← department-специфичный индекс
            ...
        ]
    
    # ❌ Жесткая бизнес-логика в методе
    @property
    def get_participants(self):
        if self.type == "department" and self.department_id:
            # ← Знает про EmployeeDepartment, Department.head_id
            employee_ids = EmployeeDepartment.objects.filter(
                department_id=self.department_id, is_active=True
            ).values_list("employee_id", flat=True)
            return Employee.objects.filter(
                Q(id__in=employee_ids) | Q(id=self.department.head_id)
            ).distinct()
        
        if self.type == "global":
            # ← Знает про Employee.is_active
            return Employee.objects.filter(is_active=True)
        
        if self.type in ["announcement", "channel"]:
            if self.include_all_employees:  # ← специфичное название
                return Employee.objects.filter(is_active=True)
        ...
```

**Проблемы:**
- ❌ Импорт `Department`, `EmployeeDepartment` - жесткая зависимость
- ❌ FK на `Department` - нельзя использовать с другими моделями
- ❌ Типы "department", "global" - специфичны для HR-систем
- ❌ `include_all_employees` - специфичное название
- ❌ `is_main` - бизнес-правило EUSRR
- ❌ Constraints привязаны к `department`
- ❌ `get_participants()` знает про `EmployeeDepartment`, `head_id`, `is_active`

---

## ✅ РЕФАКТОРЕННАЯ ВЕРСИЯ (универсальная)

```python
# backend/communications/models.py (НОВАЯ ВЕРСИЯ)

from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.utils.module_loading import import_string

class Chat(models.Model):
    """
    Универсальная модель чата для любых Django проектов.
    
    Поддерживает:
    - Личные чаты (1-на-1 или группа)
    - Групповые чаты с ролями
    - Каналы (broadcast)
    - Объявления
    - Привязку к любым моделям через GenericForeignKey (опционально)
    
    Расширяется через:
    - Дополнительные типы через settings.CHAT_EXTRA_TYPES
    - Callbacks для получения участников
    - Plugins для кастомной логики
    """
    
    # ✅ Базовые универсальные типы (минимальный набор)
    CORE_CHAT_TYPES = [
        ("private", "Private"),           # Личный чат (1-на-1 или мини-группа)
        ("group", "Group"),               # Групповой чат с управлением
        ("channel", "Channel"),           # Канал (односторонняя трансляция)
        ("announcement", "Announcement"), # Объявления
    ]
    
    type = models.CharField(
        max_length=32,  # ✅ увеличили для кастомных типов
        db_index=True,
        help_text="Chat type: private, group, channel, announcement, or custom"
    )
    
    # Основные поля
    name = models.CharField(
        max_length=255,
        blank=True,
        verbose_name="Chat name",
        help_text="Display name for group/channel chats"
    )
    description = models.TextField(
        blank=True,
        verbose_name="Description"
    )
    avatar = models.ImageField(
        upload_to='chat_avatars/%Y/%m/',
        null=True,
        blank=True,
        verbose_name="Avatar"
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='created_chats',
        verbose_name="Creator"
    )
    
    # ✅ Универсальное название вместо include_all_employees
    include_all_users = models.BooleanField(
        default=False,
        verbose_name="Include all users",
        help_text="Auto-include all active users (for announcements/broadcasts)"
    )
    
    # Прямые участники (M2M)
    participants = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        blank=True,
        related_name="chats",
        verbose_name="Participants",
        help_text="Direct participants (for private chats or explicit membership)"
    )
    
    # ✅ GenericForeignKey вместо жесткой FK на Department
    # Позволяет привязать чат к ЛЮБОЙ модели (Department, Project, Team, etc.)
    context_content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        verbose_name="Context type",
        help_text="Type of related object (e.g., Department, Project, Team)"
    )
    context_object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="Context object ID"
    )
    context_object = GenericForeignKey(
        'context_content_type',
        'context_object_id'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Created at")
    
    # ✅ Опциональное поле для любых флагов (вместо is_main)
    # Значение интерпретируется в вашем проекте
    flags = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Flags",
        help_text="Custom flags: {'is_primary': true, 'is_archived': false, etc.}"
    )
    
    # Модерация
    is_blocked = models.BooleanField(
        default=False,
        verbose_name="Blocked",
        help_text="Chat blocked by admin"
    )
    blocked_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name="Blocked at"
    )
    blocked_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='blocked_chats',
        verbose_name="Blocked by"
    )
    can_reply = models.BooleanField(
        default=True,
        verbose_name="Can reply",
        help_text="Allow replies (False for read-only announcements)"
    )
    
    # ✅ Дополнительные данные для расширения без миграций
    extra_data = models.JSONField(
        default=dict,
        blank=True,
        verbose_name="Extra data",
        help_text="Additional chat metadata (extensible)"
    )
    
    class Meta:
        verbose_name = "Chat"
        verbose_name_plural = "Chats"
        indexes = [
            models.Index(fields=["type", "created_at"]),
            models.Index(fields=["context_content_type", "context_object_id"]),
            models.Index(fields=["created_at"]),
        ]
        # ✅ Только универсальный constraint
        constraints = [
            models.UniqueConstraint(
                fields=["type", "created_by"],
                condition=Q(type="announcement"),
                name="unique_announcement_per_user",
            ),
        ]
    
    def __str__(self):
        """Универсальное строковое представление"""
        if self.name:
            return self.name
        
        if self.type == "private":
            # Показываем первых участников
            participant_names = [
                u.get_full_name() or u.username 
                for u in self.participants.all()[:3]
            ]
            if participant_names:
                names = ", ".join(participant_names)
                count = self.participants.count()
                if count > 3:
                    names += f" +{count - 3} more"
                return f"Private: {names}"
            return "Private chat"
        
        # Для типов с context_object
        if self.context_object:
            return f"{self.get_type_display()}: {self.context_object}"
        
        return f"{self.get_type_display()} chat"
    
    # ✅ Hook-метод для получения участников
    def get_participants(self):
        """
        Получить всех участников чата.
        
        Логика:
        1. Если настроен CHAT_PARTICIPANTS_RESOLVER - вызываем его
        2. Иначе используем базовую логику:
           - private/group: participants + memberships
           - announcement/channel: include_all_users или participants
        
        Переопределите через settings.CHAT_PARTICIPANTS_RESOLVER
        для кастомной логики (например, для department чатов).
        """
        # Пробуем callback из settings
        resolver = getattr(settings, 'CHAT_PARTICIPANTS_RESOLVER', None)
        if resolver:
            try:
                resolver_func = import_string(resolver)
                result = resolver_func(self)
                if result is not None:
                    return result
            except (ImportError, AttributeError) as e:
                import logging
                logging.warning(f"Failed to import CHAT_PARTICIPANTS_RESOLVER: {e}")
        
        # Базовая логика (работает без настройки)
        return self._get_default_participants()
    
    def _get_default_participants(self):
        """
        Дефолтная логика получения участников (без внешних зависимостей).
        """
        User = get_user_model()
        
        if self.type in ["private", "group"]:
            # Прямые участники + активные membership
            from communications.models import ChatMembership
            membership_ids = ChatMembership.objects.filter(
                chat=self,
                is_active=True
            ).values_list("user_id", flat=True)
            
            return User.objects.filter(
                Q(id__in=self.participants.values_list('id', flat=True)) |
                Q(id__in=membership_ids)
            ).distinct()
        
        if self.type in ["announcement", "channel"]:
            # Трансляция: все активные или явные участники
            if self.include_all_users:
                # ✅ Используем is_active если есть, иначе все
                if hasattr(User, 'is_active'):
                    return User.objects.filter(is_active=True)
                return User.objects.all()
            
            # Только явные участники + memberships
            from communications.models import ChatMembership
            membership_ids = ChatMembership.objects.filter(
                chat=self
            ).values_list("user_id", flat=True)
            
            return User.objects.filter(
                Q(id__in=self.participants.values_list('id', flat=True)) |
                Q(id__in=membership_ids)
            ).distinct()
        
        # Для неизвестных типов - только participants
        return self.participants.all()
    
    @classmethod
    def get_chat_type_choices(cls):
        """
        Динамические choices для типов чатов.
        Объединяет базовые типы + кастомные из settings.
        """
        choices = list(cls.CORE_CHAT_TYPES)
        
        # Добавляем кастомные типы из settings
        extra_types = getattr(settings, 'CHAT_EXTRA_TYPES', [])
        if extra_types:
            choices.extend(extra_types)
        
        return choices
    
    def save(self, *args, **kwargs):
        """Валидация типа чата"""
        valid_types = [t[0] for t in self.get_chat_type_choices()]
        if self.type not in valid_types:
            raise ValueError(
                f"Invalid chat type '{self.type}'. "
                f"Valid types: {', '.join(valid_types)}"
            )
        super().save(*args, **kwargs)
```

---

## ⚙️ НАСТРОЙКА В ВАШЕМ ПРОЕКТЕ (settings.py)

```python
# backend/eusrr_backend/settings.py

# ✅ Добавляем EUSRR-специфичные типы чатов
CHAT_EXTRA_TYPES = [
    ('department', 'Department'),
    ('global', 'Global Company'),
]

# ✅ Callback для получения участников специальных типов
CHAT_PARTICIPANTS_RESOLVER = 'employees.utils.resolve_chat_participants'

# Опционально: callback для сжатия аватаров
CHAT_AVATAR_COMPRESSOR = 'common.image_utils.compress_avatar'

# Опционально: автосоздание чатов
CHAT_AUTO_CREATE_FOR_MODELS = {
    'employees.Department': {
        'chat_type': 'department',
        'callback': 'employees.utils.create_department_chat',
    }
}
```

---

## 🔧 КАСТОМНАЯ ЛОГИКА В ВАШЕМ ПРОЕКТЕ

```python
# backend/employees/utils.py

def resolve_chat_participants(chat):
    """
    EUSRR-специфичная логика получения участников.
    Вызывается через CHAT_PARTICIPANTS_RESOLVER.
    """
    from django.contrib.auth import get_user_model
    from django.db.models import Q
    from employees.models import Department, EmployeeDepartment
    
    User = get_user_model()
    
    # Чаты отделов
    if chat.type == 'department':
        # Получаем Department из context_object
        department = chat.context_object
        if isinstance(department, Department):
            # Ваша бизнес-логика
            employee_ids = EmployeeDepartment.objects.filter(
                department=department,
                is_active=True
            ).values_list("employee_id", flat=True)
            
            return User.objects.filter(
                Q(id__in=employee_ids) | Q(id=department.head_id)
            ).distinct()
    
    # Глобальный чат компании
    if chat.type == 'global':
        return User.objects.filter(is_active=True)
    
    # Для остальных типов - вернуть None (будет использован default)
    return None


def create_department_chat(department):
    """
    Создание чата при создании отдела.
    Вызывается из signal в вашем проекте.
    """
    from communications.models import Chat
    from django.contrib.contenttypes.models import ContentType
    
    # Проверяем, есть ли уже главный чат
    ct = ContentType.objects.get_for_model(department)
    existing = Chat.objects.filter(
        type='department',
        context_content_type=ct,
        context_object_id=department.id,
        flags__is_primary=True  # используем flags вместо is_main
    ).exists()
    
    if not existing:
        Chat.objects.create(
            type='department',
            name=f"Чат {department.name}",
            context_object=department,  # GFK автоматически заполнит content_type и object_id
            flags={'is_primary': True},  # EUSRR-специфичный флаг
        )
```

---

## 🔗 SIGNALS В ВАШЕМ ПРОЕКТЕ

```python
# backend/employees/signals.py

from django.db.models.signals import post_save
from django.dispatch import receiver
from employees.models import Department

@receiver(post_save, sender=Department)
def create_department_chat(sender, instance, created, **kwargs):
    """Автосоздание чата для нового отдела"""
    if created:
        from employees.utils import create_department_chat as create_chat
        create_chat(instance)
```

---

## 📊 МИГРАЦИЯ ДАННЫХ

Если нужно мигрировать существующие данные:

```python
# backend/communications/migrations/XXXX_migrate_to_generic_fk.py

from django.db import migrations
from django.contrib.contenttypes.models import ContentType

def migrate_department_to_context(apps, schema_editor):
    """Миграция department FK → context GenericFK"""
    Chat = apps.get_model('communications', 'Chat')
    Department = apps.get_model('employees', 'Department')
    
    department_ct = ContentType.objects.get_for_model(Department)
    
    for chat in Chat.objects.filter(department__isnull=False):
        chat.context_content_type = department_ct
        chat.context_object_id = chat.department_id
        chat.save(update_fields=['context_content_type', 'context_object_id'])


def migrate_is_main_to_flags(apps, schema_editor):
    """Миграция is_main → flags"""
    Chat = apps.get_model('communications', 'Chat')
    
    for chat in Chat.objects.filter(is_main=True):
        flags = chat.flags or {}
        flags['is_primary'] = True
        chat.flags = flags
        chat.save(update_fields=['flags'])


def migrate_include_all_employees(apps, schema_editor):
    """Переименование поля уже в миграции"""
    # Это делается через AlterField, не через data migration
    pass


class Migration(migrations.Migration):
    dependencies = [
        ('communications', 'YYYY_previous_migration'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]
    
    operations = [
        # 1. Добавляем новые поля
        migrations.AddField(
            model_name='chat',
            name='context_content_type',
            field=models.ForeignKey(...),
        ),
        migrations.AddField(
            model_name='chat',
            name='context_object_id',
            field=models.PositiveIntegerField(...),
        ),
        migrations.AddField(
            model_name='chat',
            name='flags',
            field=models.JSONField(default=dict, blank=True),
        ),
        migrations.AddField(
            model_name='chat',
            name='extra_data',
            field=models.JSONField(default=dict, blank=True),
        ),
        
        # 2. Мигрируем данные
        migrations.RunPython(
            migrate_department_to_context,
            reverse_code=migrations.RunPython.noop,
        ),
        migrations.RunPython(
            migrate_is_main_to_flags,
            reverse_code=migrations.RunPython.noop,
        ),
        
        # 3. Переименовываем поля
        migrations.RenameField(
            model_name='chat',
            old_name='include_all_employees',
            new_name='include_all_users',
        ),
        
        # 4. Удаляем старые поля (опционально, можно оставить для совместимости)
        # migrations.RemoveField(
        #     model_name='chat',
        #     name='department',
        # ),
        # migrations.RemoveField(
        #     model_name='chat',
        #     name='is_main',
        # ),
        
        # 5. Удаляем старые constraints
        migrations.RemoveConstraint(
            model_name='chat',
            name='unique_main_department_chat',
        ),
        migrations.RemoveConstraint(
            model_name='chat',
            name='unique_main_global_chat',
        ),
    ]
```

---

## 🎯 ПРИМЕРЫ ИСПОЛЬЗОВАНИЯ

### До (с бизнес-логикой):
```python
# Создание чата отдела
chat = Chat.objects.create(
    type='department',
    name=f'Чат {dept.name}',
    department=dept,  # ← жесткая FK
    is_main=True,     # ← EUSRR флаг
)

# Получение участников
participants = chat.get_participants()  # ← знает про EmployeeDepartment
```

### После (универсально):
```python
# Создание чата отдела
chat = Chat.objects.create(
    type='department',           # ← тип из CHAT_EXTRA_TYPES
    name=f'Чат {dept.name}',
    context_object=dept,          # ← GenericFK (любая модель!)
    flags={'is_primary': True},   # ← гибкие флаги
)

# Получение участников
participants = chat.get_participants()  # ← вызовет ваш resolver

# Создание чата проекта (новое!)
chat = Chat.objects.create(
    type='project',               # ← можно добавить в CHAT_EXTRA_TYPES
    name=f'Проект {project.name}',
    context_object=project,        # ← работает с любой моделью!
)

# Создание чата команды (новое!)
chat = Chat.objects.create(
    type='team',
    name=f'Команда {team.name}',
    context_object=team,
)
```

---

## ✅ ПРЕИМУЩЕСТВА РЕФАКТОРЕННОЙ ВЕРСИИ

1. **Универсальность:**
   - ✅ GenericForeignKey → можно привязать к ЛЮБОЙ модели (Department, Project, Team, Event, etc.)
   - ✅ Динамические типы через settings → расширяемость
   - ✅ JSONField для flags/extra_data → расширение без миграций

2. **Нет жестких зависимостей:**
   - ✅ Нет import employees
   - ✅ Нет FK на Department
   - ✅ Нет знания о EmployeeDepartment, head_id, is_active

3. **Гибкость:**
   - ✅ Кастомная логика через callbacks (CHAT_PARTICIPANTS_RESOLVER)
   - ✅ Работает "из коробки" с базовой логикой
   - ✅ Расширяется без изменения кода пакета

4. **Переиспользуемость:**
   - ✅ Можно использовать в HR-системе (Department)
   - ✅ Можно использовать в Project Management (Project, Team)
   - ✅ Можно использовать в Event Management (Event, Conference)
   - ✅ Можно использовать в E-commerce (Order, Support)

5. **Совместимость:**
   - ✅ Миграция данных без потери
   - ✅ Можно оставить старые поля для совместимости
   - ✅ Постепенный переход

---

## 📋 ЧЕКЛИСТ ИЗМЕНЕНИЙ

### В модели Chat:
- [x] Убрать `from employees.models import Department, EmployeeDepartment`
- [x] Заменить `department = FK(Department)` → `context_object = GenericForeignKey()`
- [x] Переименовать `include_all_employees` → `include_all_users`
- [x] Заменить `is_main` → `flags = JSONField()` с `{'is_primary': True}`
- [x] Добавить `extra_data = JSONField()` для расширений
- [x] Рефакторинг `get_participants()` → hook с callback
- [x] Убрать типы "department", "global" из CHAT_TYPE_CHOICES → сделать CORE_CHAT_TYPES
- [x] Добавить `get_chat_type_choices()` для динамических типов
- [x] Убрать department-специфичные constraints
- [x] Изменить `__str__()` для универсальности
- [x] Увеличить max_length типа с 16 до 32

### В других файлах:
- [ ] Создать `employees/utils.py` с `resolve_chat_participants()` и `create_department_chat()`
- [ ] Переместить signal из `communications/signals.py` в `employees/signals.py`
- [ ] Добавить settings в `settings.py`: `CHAT_EXTRA_TYPES`, `CHAT_PARTICIPANTS_RESOLVER`
- [ ] Создать миграцию для GenericFK и переименования полей
- [ ] Обновить views.py (удалить `from employees.models import Department`)
- [ ] Обновить serializers.py
- [ ] Обновить тесты

---

## 🚀 ИТОГ

**Убрали:**
- ❌ Все импорты employees
- ❌ FK на Department
- ❌ Жесткие типы "department", "global"
- ❌ Поле include_all_employees
- ❌ Поле is_main
- ❌ Department-специфичные constraints
- ❌ Знание о EmployeeDepartment, head_id

**Добавили:**
- ✅ GenericForeignKey для универсальной привязки
- ✅ JSONField flags для гибких флагов
- ✅ JSONField extra_data для расширений
- ✅ Callback-систему для get_participants()
- ✅ Динамические типы через settings
- ✅ Базовую логику, работающую "из коробки"

**Результат:**
Модель Chat теперь **полностью универсальна** и может использоваться в ЛЮБОМ Django проекте, а ваша EUSRR-специфичная логика вынесена в `employees` приложение.
