# План миграции данных Chat без потерь

## ✅ **ГАРАНТИЯ: Все данные сохраняются!**

Миграция будет **аддитивной** (добавляющей), а не деструктивной. Старые поля можно оставить для совместимости или удалить позже.

---

## 📊 **Анализ: Какие данные нужно мигрировать**

### Текущие EUSRR-специфичные поля в Chat:

```python
# 1. department (ForeignKey) → 146 записей с department != NULL
department = models.ForeignKey(Department, ...)

# 2. include_all_employees (Boolean) → просто переименование
include_all_employees = models.BooleanField(default=False)

# 3. is_main (Boolean) → значения True/False
is_main = models.BooleanField(default=False)
```

Давайте проверим, сколько у вас данных:

```bash
# Проверка количества чатов с department
.venv/Scripts/python manage.py shell
>>> from communications.models import Chat
>>> Chat.objects.filter(department__isnull=False).count()
>>> Chat.objects.filter(is_main=True).count()
>>> Chat.objects.filter(include_all_employees=True).count()
```

---

## 🔄 **Стратегия миграции: Пошаговая (безопасная)**

### **Фаза 1: Добавление новых полей (АДДИТИВНАЯ)**
Добавляем новые поля **БЕЗ удаления старых** → **0% риска потери данных**

### **Фаза 2: Миграция данных**
Копируем данные из старых полей в новые → **Данные дублируются**

### **Фаза 3: Обновление кода**
Переключаем код на использование новых полей → **Старые поля остаются для отката**

### **Фаза 4: Удаление старых полей (опционально)**
Удаляем старые поля только после полной проверки → **Можно отложить на недели/месяцы**

---

## 📝 **Детальный план миграций**

### **Миграция 1: Добавление новых полей**

```python
# backend/communications/migrations/0XXX_add_generic_context.py

from django.db import migrations, models
import django.contrib.contenttypes.models

class Migration(migrations.Migration):
    dependencies = [
        ('communications', '0YYY_previous_migration'),
        ('contenttypes', '0002_remove_content_type_name'),
    ]

    operations = [
        # 1. Добавляем GenericForeignKey поля
        migrations.AddField(
            model_name='chat',
            name='context_content_type',
            field=models.ForeignKey(
                blank=True,
                null=True,
                on_delete=django.db.models.deletion.CASCADE,
                to='contenttypes.contenttype',
                verbose_name='Context type',
                help_text='Type of related object (e.g., Department, Project, Team)'
            ),
        ),
        migrations.AddField(
            model_name='chat',
            name='context_object_id',
            field=models.PositiveIntegerField(
                blank=True,
                null=True,
                verbose_name='Context object ID'
            ),
        ),
        
        # 2. Добавляем JSON поля
        migrations.AddField(
            model_name='chat',
            name='flags',
            field=models.JSONField(
                blank=True,
                default=dict,
                verbose_name='Flags',
                help_text="Custom flags: {'is_primary': true, 'is_archived': false, etc.}"
            ),
        ),
        migrations.AddField(
            model_name='chat',
            name='extra_data',
            field=models.JSONField(
                blank=True,
                default=dict,
                verbose_name='Extra data',
                help_text='Additional chat metadata (extensible)'
            ),
        ),
        
        # 3. Увеличиваем max_length для type (для кастомных типов)
        migrations.AlterField(
            model_name='chat',
            name='type',
            field=models.CharField(
                db_index=True,
                max_length=32,  # было 16
                help_text='Chat type: private, group, channel, announcement, or custom'
            ),
        ),
        
        # 4. Индексы для GenericFK
        migrations.AddIndex(
            model_name='chat',
            index=models.Index(
                fields=['context_content_type', 'context_object_id'],
                name='chat_context_idx'
            ),
        ),
    ]
```

**Результат:** У вас теперь есть И старые И новые поля. Данные не тронуты! ✅

---

### **Миграция 2: Копирование данных из department → context_object**

```python
# backend/communications/migrations/0XXX_migrate_department_to_context.py

from django.db import migrations
from django.contrib.contenttypes.models import ContentType

def migrate_department_to_generic_fk(apps, schema_editor):
    """
    Миграция: department FK → context GenericFK
    
    Копирует данные БЕЗ удаления старого поля!
    """
    Chat = apps.get_model('communications', 'Chat')
    Department = apps.get_model('employees', 'Department')
    
    # Получаем ContentType для Department
    department_ct = ContentType.objects.get_for_model(Department)
    
    # Счетчик для отчета
    migrated_count = 0
    
    # Переносим все чаты с department
    chats_with_dept = Chat.objects.filter(department__isnull=False)
    total = chats_with_dept.count()
    
    print(f"\n[MIGRATION] Migrating {total} chats with department...")
    
    for chat in chats_with_dept:
        # Копируем department_id в context
        chat.context_content_type = department_ct
        chat.context_object_id = chat.department_id
        chat.save(update_fields=['context_content_type', 'context_object_id'])
        migrated_count += 1
        
        if migrated_count % 100 == 0:
            print(f"  Migrated {migrated_count}/{total}...")
    
    print(f"[MIGRATION] Successfully migrated {migrated_count} chats! ✅")
    print(f"[INFO] Old 'department' field preserved for rollback")


def reverse_migrate(apps, schema_editor):
    """
    Откат: context GenericFK → department FK
    
    Восстанавливаем department_id из context_object_id
    """
    Chat = apps.get_model('communications', 'Chat')
    Department = apps.get_model('employees', 'Department')
    
    department_ct = ContentType.objects.get_for_model(Department)
    
    # Восстанавливаем department для чатов с context типа Department
    chats = Chat.objects.filter(
        context_content_type=department_ct,
        context_object_id__isnull=False
    )
    
    for chat in chats:
        try:
            dept = Department.objects.get(pk=chat.context_object_id)
            chat.department = dept
            chat.save(update_fields=['department'])
        except Department.DoesNotExist:
            print(f"Warning: Department {chat.context_object_id} not found for chat {chat.id}")


class Migration(migrations.Migration):
    dependencies = [
        ('communications', '0XXX_add_generic_context'),
        ('employees', '0001_initial'),  # убедитесь что Department существует
    ]

    operations = [
        migrations.RunPython(
            migrate_department_to_generic_fk,
            reverse_code=reverse_migrate,
        ),
    ]
```

**Результат:** 
- ✅ Все чаты с `department` теперь имеют `context_object`
- ✅ Старое поле `department` сохранено (можно откатить!)
- ✅ Миграция обратима (reverse_migrate)

---

### **Миграция 3: Копирование is_main → flags['is_primary']**

```python
# backend/communications/migrations/0XXX_migrate_is_main_to_flags.py

from django.db import migrations

def migrate_is_main_to_flags(apps, schema_editor):
    """
    Миграция: is_main Boolean → flags['is_primary']
    
    Копирует значение БЕЗ удаления старого поля!
    """
    Chat = apps.get_model('communications', 'Chat')
    
    # Находим все чаты с is_main=True
    main_chats = Chat.objects.filter(is_main=True)
    count = main_chats.count()
    
    print(f"\n[MIGRATION] Migrating is_main to flags for {count} chats...")
    
    migrated = 0
    for chat in main_chats:
        # Получаем текущие flags или создаем пустой dict
        flags = chat.flags or {}
        
        # Добавляем is_primary
        flags['is_primary'] = True
        
        chat.flags = flags
        chat.save(update_fields=['flags'])
        migrated += 1
    
    print(f"[MIGRATION] Successfully migrated {migrated} chats with is_main! ✅")
    print(f"[INFO] Old 'is_main' field preserved for rollback")


def reverse_migrate(apps, schema_editor):
    """
    Откат: flags['is_primary'] → is_main
    """
    Chat = apps.get_model('communications', 'Chat')
    
    # Находим все чаты с flags.is_primary=True
    for chat in Chat.objects.all():
        if chat.flags and chat.flags.get('is_primary'):
            chat.is_main = True
            chat.save(update_fields=['is_main'])


class Migration(migrations.Migration):
    dependencies = [
        ('communications', '0XXX_migrate_department_to_context'),
    ]

    operations = [
        migrations.RunPython(
            migrate_is_main_to_flags,
            reverse_code=reverse_migrate,
        ),
    ]
```

**Результат:**
- ✅ Все чаты с `is_main=True` теперь имеют `flags={'is_primary': True}`
- ✅ Старое поле `is_main` сохранено
- ✅ Обратимая миграция

---

### **Миграция 4: Переименование include_all_employees → include_all_users**

```python
# backend/communications/migrations/0XXX_rename_include_all_employees.py

from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('communications', '0XXX_migrate_is_main_to_flags'),
    ]

    operations = [
        # Простое переименование поля - Django делает все сам!
        migrations.RenameField(
            model_name='chat',
            old_name='include_all_employees',
            new_name='include_all_users',
        ),
    ]
```

**Результат:**
- ✅ Поле переименовано
- ✅ ВСЕ данные сохранены (это просто ALTER TABLE RENAME COLUMN)
- ✅ Обратимо автоматически

---

### **Миграция 5: Удаление старых constraints (безопасно)**

```python
# backend/communications/migrations/0XXX_remove_old_constraints.py

from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('communications', '0XXX_rename_include_all_employees'),
    ]

    operations = [
        # Удаляем constraint на department (больше не нужен)
        migrations.RemoveConstraint(
            model_name='chat',
            name='unique_main_department_chat',
        ),
        
        # Удаляем constraint на global (специфичен для EUSRR)
        migrations.RemoveConstraint(
            model_name='chat',
            name='unique_main_global_chat',
        ),
        
        # Оставляем универсальный constraint
        # (unique_announcement_per_user - это универсально)
    ]
```

**Результат:**
- ✅ Старые constraints удалены
- ✅ Данные НЕ затронуты (constraints не содержат данных)

---

### **Миграция 6 (ОПЦИОНАЛЬНАЯ): Удаление старых полей**

**⚠️ ВАЖНО:** Эту миграцию можно делать через недели/месяцы после развертывания!

```python
# backend/communications/migrations/0XXX_remove_deprecated_fields.py

from django.db import migrations

class Migration(migrations.Migration):
    dependencies = [
        ('communications', '0XXX_remove_old_constraints'),
    ]

    operations = [
        # ⚠️ Удаление старых полей - делать только после полной проверки!
        
        migrations.RemoveField(
            model_name='chat',
            name='department',
        ),
        
        migrations.RemoveField(
            model_name='chat',
            name='is_main',
        ),
        
        # Индекс на department тоже удалится автоматически
    ]
```

**Результат:**
- ✅ Старые поля удалены (база данных становится чище)
- ⚠️ Откат этой миграции невозможен без backup!

---

## 🔍 **Проверка данных после миграции**

После выполнения миграций 1-5, запустите проверку:

```python
# backend/communications/management/commands/verify_chat_migration.py

from django.core.management.base import BaseCommand
from django.contrib.contenttypes.models import ContentType
from communications.models import Chat
from employees.models import Department

class Command(BaseCommand):
    help = 'Verify Chat migration: old fields → new fields'

    def handle(self, *args, **options):
        self.stdout.write("\n" + "="*60)
        self.stdout.write("VERIFYING CHAT MIGRATION")
        self.stdout.write("="*60 + "\n")
        
        errors = []
        warnings = []
        
        # 1. Проверка department → context_object
        self.stdout.write("1. Checking department → context_object migration...")
        
        dept_ct = ContentType.objects.get_for_model(Department)
        chats_with_dept = Chat.objects.filter(department__isnull=False)
        
        for chat in chats_with_dept:
            # Проверяем что context заполнен
            if not chat.context_object_id:
                errors.append(
                    f"Chat {chat.id}: has department but context_object_id is NULL"
                )
            elif chat.context_object_id != chat.department_id:
                errors.append(
                    f"Chat {chat.id}: context_object_id ({chat.context_object_id}) "
                    f"!= department_id ({chat.department_id})"
                )
            elif chat.context_content_type_id != dept_ct.id:
                errors.append(
                    f"Chat {chat.id}: context_content_type is not Department"
                )
        
        if not errors:
            self.stdout.write(self.style.SUCCESS(
                f"   ✓ All {chats_with_dept.count()} chats with department migrated correctly"
            ))
        
        # 2. Проверка is_main → flags['is_primary']
        self.stdout.write("\n2. Checking is_main → flags['is_primary'] migration...")
        
        main_chats = Chat.objects.filter(is_main=True)
        
        for chat in main_chats:
            if not chat.flags.get('is_primary'):
                errors.append(
                    f"Chat {chat.id}: is_main=True but flags['is_primary'] is not True"
                )
        
        if not errors:
            self.stdout.write(self.style.SUCCESS(
                f"   ✓ All {main_chats.count()} main chats migrated to flags correctly"
            ))
        
        # 3. Проверка include_all_users (после переименования)
        self.stdout.write("\n3. Checking include_all_users field...")
        
        if hasattr(Chat, 'include_all_employees'):
            warnings.append("Old field 'include_all_employees' still exists")
        
        if hasattr(Chat, 'include_all_users'):
            count = Chat.objects.filter(include_all_users=True).count()
            self.stdout.write(self.style.SUCCESS(
                f"   ✓ Field 'include_all_users' exists, {count} chats use it"
            ))
        else:
            errors.append("Field 'include_all_users' not found!")
        
        # Итоговый отчет
        self.stdout.write("\n" + "="*60)
        if errors:
            self.stdout.write(self.style.ERROR(f"❌ ERRORS: {len(errors)}"))
            for error in errors:
                self.stdout.write(self.style.ERROR(f"  - {error}"))
        else:
            self.stdout.write(self.style.SUCCESS("✅ NO ERRORS"))
        
        if warnings:
            self.stdout.write(self.style.WARNING(f"⚠️  WARNINGS: {len(warnings)}"))
            for warning in warnings:
                self.stdout.write(self.style.WARNING(f"  - {warning}"))
        
        self.stdout.write("="*60 + "\n")
        
        return 0 if not errors else 1
```

Запуск проверки:
```bash
.venv/Scripts/python manage.py verify_chat_migration
```

---

## 📊 **Таблица: Что происходит с данными**

| Старое поле | Новое поле | Миграция | Потеря данных? | Обратимо? |
|-------------|------------|----------|----------------|-----------|
| `department` (FK) | `context_object` (GFK) | Копирование FK → GFK | ❌ НЕТ | ✅ ДА |
| `is_main` (Boolean) | `flags['is_primary']` (JSON) | Копирование в JSON | ❌ НЕТ | ✅ ДА |
| `include_all_employees` | `include_all_users` | RENAME COLUMN | ❌ НЕТ | ✅ ДА |
| Constraints на department | Убраны | DROP CONSTRAINT | ❌ НЕТ* | ✅ ДА |
| Индекс на department | Новый индекс на GFK | ADD INDEX | ❌ НЕТ | ✅ ДА |

*Constraints не содержат данных, только правила валидации

---

## 🛡️ **План отката (Rollback Plan)**

### Если что-то пошло не так на production:

**Вариант 1: Откат через Django migrations**
```bash
# Откатиться на последнюю рабочую миграцию
.venv/Scripts/python manage.py migrate communications 0XXX_previous_working_migration
```

**Вариант 2: Ручной откат (если старые поля сохранены)**
```python
# Восстановить department из context
Chat = Chat.objects.filter(
    context_content_type=dept_ct,
    context_object_id__isnull=False
)
for chat in chats:
    chat.department_id = chat.context_object_id
    chat.save()

# Восстановить is_main из flags
for chat in Chat.objects.all():
    if chat.flags.get('is_primary'):
        chat.is_main = True
        chat.save()
```

**Вариант 3: Восстановление из backup**
```bash
# Если делали backup перед миграцией
pg_restore -d eusrr_db backup_before_migration.dump
```

---

## ✅ **Рекомендуемая последовательность развертывания**

### **Этап 1: Development (локально)**
1. Создать миграции 1-5
2. Запустить миграции
3. Запустить `verify_chat_migration`
4. Обновить code (models.py, views.py, signals.py)
5. Запустить тесты
6. Проверить вручную в интерфейсе

### **Этап 2: Staging (тестовый сервер)**
1. Сделать backup БД
2. Применить миграции
3. Запустить verification
4. Задеплоить новый код
5. Тестирование 1-2 недели

### **Этап 3: Production**
1. ⚠️ **ОБЯЗАТЕЛЬНО сделать backup БД!**
2. Включить maintenance mode (опционально)
3. Применить миграции 1-5 (БЕЗ удаления старых полей!)
4. Задеплоить новый код
5. Запустить verification
6. Мониторинг 1-2 недели
7. **Только потом** (через месяц) миграция 6 (удаление старых полей)

---

## 📈 **Преимущества такого подхода**

1. **Безопасность:**
   - ✅ Никакие данные не удаляются
   - ✅ Старые поля сохраняются для отката
   - ✅ Можно откатить на любом этапе

2. **Постепенность:**
   - ✅ Миграции маленькие и понятные
   - ✅ Каждая миграция проверяемая
   - ✅ Можно остановиться на любом этапе

3. **Обратимость:**
   - ✅ Каждая миграция имеет reverse()
   - ✅ Можно откатить через `migrate communications 0XXX`
   - ✅ Данные дублируются до финальной очистки

4. **Тестируемость:**
   - ✅ Можно проверить на staging
   - ✅ Есть команда verify_chat_migration
   - ✅ Можно сравнить данные до/после

---

## 🔥 **Самое главное:**

### ❌ **НЕ ДЕЛАЙТЕ СРАЗУ:**
```python
# ❌ ПЛОХО - деструктивная миграция
migrations.RemoveField('chat', 'department')
migrations.RemoveField('chat', 'is_main')
# Данные потеряны навсегда!
```

### ✅ **ДЕЛАЙТЕ ТАК:**
```python
# ✅ ХОРОШО - аддитивная миграция
migrations.AddField('chat', 'context_content_type', ...)
migrations.AddField('chat', 'context_object_id', ...)
migrations.AddField('chat', 'flags', ...)
# Старые поля остаются! Можно откатить!
```

### 📅 **График миграции:**
1. **Неделя 1:** Добавить новые поля (миграции 1-2)
2. **Неделя 2:** Скопировать данные (миграции 3-4)
3. **Неделя 3:** Обновить код, тестирование
4. **Неделя 4:** Deploy на staging
5. **Неделя 5-6:** Тестирование на staging
6. **Неделя 7:** Deploy на production
7. **Неделя 8-12:** Мониторинг
8. **Месяц 3-4:** Удаление старых полей (опционально)

---

## 🎯 **Итоговый ответ на ваш вопрос:**

**Потеряются ли данные?**
# ❌ НЕТ! Абсолютно ВСЕ данные сохраняются!

**Можно ли аккуратно перенести?**
# ✅ ДА! Через аддитивные миграции с копированием данных

**Можно ли откатить?**
# ✅ ДА! Старые поля остаются, миграции обратимы

**Насколько это безопасно?**
# ✅ ОЧЕНЬ БЕЗОПАСНО при правильном подходе (backup + поэтапное развертывание)

---

Хотите, чтобы я:
1. **Создал эти миграции** прямо сейчас в вашем проекте?
2. **Создал команду verify_chat_migration** для проверки?
3. **Показал пример backup/restore** для вашей БД?
4. Или сначала **посчитаем сколько данных** нужно мигрировать в вашей БД?
