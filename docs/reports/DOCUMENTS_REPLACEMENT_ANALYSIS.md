# Анализ замены приложения documents готовыми решениями

**Дата:** 28 февраля 2026  
**Статус:** 🔍 Анализ завершен  
**Ветка:** `develop` (после мерджа feature/django-rules)

---

## Текущий функционал documents

### Модели:
1. **Document** (88 строк в models.py):
   - `title`, `file`, `description`
   - `uploaded_by` (кто загрузил)
   - `sent_to_all` (разослать всем)
   - `departments` (M2M - отделы-получатели)
   - `recipients` (M2M - конкретные получатели)

2. **DocumentAcknowledgement**:
   - `document`, `user`, `acknowledged_at`
   - Уникальность: (document, user)
   - Трекинг ознакомления с документами

### Функционал:
- ✅ Загрузка файлов (FileField)
- ✅ Рассылка по отделам/сотрудникам
- ✅ Трекинг ознакомления (acknowledged)
- ✅ Уведомления (notification_signals.py)
- ✅ Django Admin с inline ознакомлений
- ✅ API для работы с документами (views.py ~436 строк)
- ✅ Права доступа через django-rules (rules.py)
- ✅ Celery tasks для фоновой обработки

### Размер кастомного кода:
```
models.py:              88 строк
views.py:              436 строк  
admin.py:              131 строк
rules.py:              296 строк
notification_signals:   ~50 строк
tasks.py:              178 строк (закомментированы)
─────────────────────────────────
ИТОГО:                ~1180 строк
```

---

## Доступные Django пакеты

### 1. django-filer ⭐⭐⭐⭐⭐
**GitHub:** https://github.com/django-cms/django-filer  
**Звёзды:** 1.8k ⭐  
**Статус:** Активно развивается  
**Последний релиз:** 2024

#### Возможности:
- ✅ Мощная система управления файлами/папками
- ✅ Thumbnails для изображений
- ✅ ACL (Access Control List) на уровне файлов/папок
- ✅ Групповые права доступа
- ✅ Drag & drop загрузка
- ✅ Поиск по файлам
- ✅ Интеграция с Django Admin
- ✅ REST API (django-filer-rest)

#### Что ОТСУТСТВУЕТ:
- ❌ Рассылка документов по отделам/пользователям
- ❌ Трекинг ознакомления
- ❌ Интеграция с корпоративной структурой
- ❌ Уведомления о новых документах

#### Установка:
```bash
pip install django-filer
pip install easy-thumbnails  # зависимость
```

#### Оценка покрытия: **60%**
Покрывает хранение, права доступа, админку. НЕ покрывает рассылку и ознакомление.

---

### 2. Django Reversion ⭐⭐⭐⭐
**GitHub:** https://github.com/etianen/django-reversion  
**Звёзды:** 3.1k ⭐  
**Статус:** Активно развивается  
**Последний релиз:** 2024

#### Возможности:
- ✅ Версионирование любых моделей
- ✅ История изменений
- ✅ Откат к предыдущим версиям
- ✅ Интеграция с Django Admin
- ✅ Сравнение версий

#### Применимость:
Не замена documents, но полезное дополнение для версионирования документов.

#### Установка:
```bash
pip install django-reversion
```

#### Оценка покрытия: **15%** (только версионирование)

---

### 3. Mayan EDMS 🏢
**GitHub:** https://github.com/mayan-edms/Mayan-EDMS  
**Звёзды:** 2.3k ⭐  
**Статус:** Enterprise-ready DMS  
**Последний релиз:** 2024

#### Возможности:
- ✅ Полноценная система электронного документооборота
- ✅ OCR (распознавание текста)
- ✅ Workflow для согласования
- ✅ Метаданные документов
- ✅ Тегирование и категоризация
- ✅ Поиск по содержимому
- ✅ Права доступа
- ✅ REST API
- ✅ Интеграция с LDAP/AD

#### Недостатки:
- ⚠️ **Отдельное приложение** на Django (не библиотека)
- ⚠️ Сложность интеграции в существующий проект
- ⚠️ Требует PostgreSQL, Redis, Elasticsearch
- ⚠️ Heavyweight решение

#### Оценка покрытия: **95%**, но НЕ библиотека

---

### 4. django-documents ⚠️
**GitHub:** https://github.com/stefanfoulis/django-documents  
**Звёзды:** ~50 ⭐  
**Статус:** ⚠️ Заброшен (последний коммит 2015)

#### Вердикт: НЕ РЕКОМЕНДУЕТСЯ (устарел)

---

### 5. django-file-manager
**GitHub:** Несколько реализаций, все мелкие  
**Статус:** ⚠️ Нет зрелого решения

#### Вердикт: НЕ РЕКОМЕНДУЕТСЯ

---

### 6. django-wiki ⭐⭐⭐
**GitHub:** https://github.com/django-wiki/django-wiki  
**Звёзды:** 1.8k ⭐  
**Статус:** Активно развивается

#### Возможности:
- ✅ Управление статьями/документами
- ✅ Markdown редактор
- ✅ Версионирование
- ✅ Права доступа
- ✅ Attachments (вложения)
- ✅ Поиск

#### Недостатки:
- ❌ Заточен под wiki-статьи, не под файловый документооборот
- ❌ Нет рассылки по отделам
- ❌ Нет трекинга ознакомления

#### Оценка покрытия: **40%** (если документы = статьи)

---

### 7. django-attachments
**GitHub:** https://github.com/bartTC/django-attachments  
**Звёзды:** ~200 ⭐  
**Статус:** Поддерживается

#### Возможности:
- ✅ Generic файловые вложения к любым моделям
- ✅ Простое API
- ✅ Права доступа

#### Недостатки:
- ❌ Слишком простой (нет рассылки, ознакомления)

#### Оценка покрытия: **25%**

---

## Рекомендации по замене

### Вариант 1: Полная замена на django-filer + кастом (рекомендуется) ⭐

**Что заменяется:**
- Хранение файлов → **django-filer**
- Права доступа → **django-filer ACL + django-rules**
- Версионирование → **django-reversion** (опционально)

**Что остается кастомным:**
- Модель **DocumentDistribution** (кто, кому, когда)
- Модель **DocumentAcknowledgement** (ознакомление)
- Логика рассылки по отделам
- Уведомления через Celery

**Преимущества:**
- ✅ Профессиональное хранилище файлов
- ✅ Готовая админка с drag & drop
- ✅ Thumbnails для превью
- ✅ Папки, теги, поиск
- ✅ Сокращение кода на ~600 строк (views, admin для файлов)

**Недостатки:**
- ⚠️ Нужна миграция данных (Document → filer.File)
- ⚠️ Кастомные модели всё равно нужны (~400 строк)

**Оценка трудозатрат:** 3-5 дней

**Код сокращается с:** 1180 строк → ~580 строк (~50%)

---

### Вариант 2: Интеграция с Mayan EDMS (для enterprise)

**Архитектура:**
```
EUSRR Backend (Django) ← REST API → Mayan EDMS (отдельный сервис)
```

**Что даёт:**
- ✅ Полноценная DMS с OCR, Workflow, метаданными
- ✅ Масштабируемость
- ✅ Профессиональный UI для работы с документами

**Недостатки:**
- ❌ Сложность развертывания (отдельный сервис)
- ❌ Дублирование пользователей (синхронизация)
- ❌ Накладные расходы на интеграцию

**Оценка трудозатрат:** 2-3 недели

**Рекомендуется только если:**
- В компании >500 сотрудников
- Документооборот >10000 документов/год
- Нужен OCR и workflow

---

### Вариант 3: Оставить как есть + улучшения

**Что улучшить в текущем documents:**

1. **Добавить django-filer только для хранения:**
   ```python
   # Вместо FileField использовать FilerFileField
   from filer.fields.file import FilerFileField
   
   class Document(models.Model):
       file = FilerFileField(on_delete=models.CASCADE)
   ```

2. **Добавить версионирование через django-reversion:**
   ```python
   import reversion
   
   @reversion.register()
   class Document(models.Model):
       ...
   ```

3. **Добавить поиск через django-watson** (уже есть в проекте):
   ```python
   import watson
   
   watson.register(Document, fields=('title', 'description'))
   ```

4. **Улучшить права через django-rules** (уже сделано ✅)

5. **Добавить preview для файлов:**
   ```bash
   pip install django-file-preview
   ```

**Преимущества:**
- ✅ Минимальная переработка
- ✅ Постепенная модернизация
- ✅ Сохранение всей логики

**Недостатки:**
- ❌ Кастомный код остается (~1180 строк)

**Оценка трудозатрат:** 1-2 дня

---

## Сравнительная таблица

| Критерий | Текущий documents | django-filer | Mayan EDMS | Вариант 1 (filer+кастом) |
|----------|-------------------|--------------|------------|--------------------------|
| **Хранение файлов** | ✅ FileField | ⭐⭐⭐⭐⭐ Профессиональное | ⭐⭐⭐⭐⭐ Enterprise | ⭐⭐⭐⭐⭐ Профессиональное |
| **Рассылка по отделам** | ✅ Кастом | ❌ Нет | ⚠️ Сложно | ✅ Кастом (~200 строк) |
| **Трекинг ознакомления** | ✅ Кастом | ❌ Нет | ⚠️ Через workflow | ✅ Кастом (~100 строк) |
| **Права доступа** | ✅ django-rules | ✅ ACL встроен | ✅ Встроено | ✅ filer ACL + rules |
| **Версионирование** | ❌ Нет | ❌ Нет | ✅ Есть | ➕ django-reversion |
| **OCR** | ❌ Нет | ❌ Нет | ✅ Есть | ❌ Нет |
| **Поиск** | ⚠️ Простой | ✅ Есть | ⭐⭐⭐⭐⭐ Elasticsearch | ✅ django-watson |
| **Admin UI** | ⚠️ Базовый | ⭐⭐⭐⭐⭐ Отличный | ⭐⭐⭐⭐⭐ Профессиональный | ⭐⭐⭐⭐⭐ Отличный |
| **Код (строк)** | 1180 | 0 (библиотека) | 0 (сервис) | ~580 |
| **Сложность интеграции** | - | ⭐⭐⭐ Средняя | ⭐⭐⭐⭐⭐ Высокая | ⭐⭐⭐ Средняя |
| **Трудозатраты** | - | 3-5 дней | 2-3 недели | 3-5 дней |

---

## Итоговая рекомендация ⭐

### Рекомендуемый подход: **Вариант 1 (django-filer + кастом)**

**План миграции:**

#### Фаза 1: Подготовка (1 день)
```bash
pip install django-filer
pip install easy-thumbnails
pip install django-reversion  # опционально
```

Настройка settings.py:
```python
INSTALLED_APPS = [
    ...
    'easy_thumbnails',
    'filer',
    'mptt',  # зависимость filer
    'reversion',
]

THUMBNAIL_PROCESSORS = (
    'easy_thumbnails.processors.colorspace',
    'easy_thumbnails.processors.autocrop',
    'filer.thumbnail_processors.scale_and_crop_with_subject_location',
    'easy_thumbnails.processors.filters',
)
```

#### Фаза 2: Создание новых моделей (1 день)
```python
# documents/models_v2.py
from filer.fields.file import FilerFileField
from django.db import models
import reversion

@reversion.register()
class Document(models.Model):
    """Документ с использованием django-filer"""
    title = models.CharField(max_length=255)
    file = FilerFileField(
        on_delete=models.CASCADE,
        related_name='documents'
    )
    description = models.TextField(blank=True)
    
    # Кастомные поля рассылки
    uploaded_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    sent_to_all = models.BooleanField(default=True)
    departments = models.ManyToManyField('employees.Department', blank=True)
    recipients = models.ManyToManyField(User, blank=True, related_name='received_documents')


class DocumentAcknowledgement(models.Model):
    """Трекинг ознакомления - остается без изменений"""
    document = models.ForeignKey(Document, on_delete=models.CASCADE)
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    acknowledged_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        unique_together = ('document', 'user')
```

#### Фаза 3: Миграция данных (1 день)
```python
# documents/management/commands/migrate_to_filer.py
from django.core.management.base import BaseCommand
from documents.models import Document as OldDocument
from documents.models_v2 import Document as NewDocument
from filer.models import File as FilerFile

class Command(BaseCommand):
    def handle(self, *args, **options):
        for old_doc in OldDocument.objects.all():
            # Создаем FilerFile
            filer_file = FilerFile.objects.create(
                file=old_doc.file,
                name=old_doc.title,
                owner=old_doc.uploaded_by
            )
            
            # Создаем новый Document
            new_doc = NewDocument.objects.create(
                title=old_doc.title,
                file=filer_file,
                description=old_doc.description,
                uploaded_by=old_doc.uploaded_by,
                uploaded_at=old_doc.uploaded_at,
                sent_to_all=old_doc.sent_to_all
            )
            
            # Копируем M2M связи
            new_doc.departments.set(old_doc.departments.all())
            new_doc.recipients.set(old_doc.recipients.all())
            
            # Копируем ознакомления
            for ack in old_doc.acknowledgements.all():
                DocumentAcknowledgement.objects.create(
                    document=new_doc,
                    user=ack.user,
                    acknowledged_at=ack.acknowledged_at
                )
```

#### Фаза 4: Обновление Admin (0.5 дня)
```python
# documents/admin.py
from django.contrib import admin
from filer.admin import FolderAdmin as BaseFolderAdmin
from .models_v2 import Document, DocumentAcknowledgement

@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    # Используем встроенный виджет filer для file
    list_display = ('title', 'file_thumbnail', 'uploaded_at', 'sent_to_all')
    filter_horizontal = ('recipients', 'departments')
    
    def file_thumbnail(self, obj):
        if obj.file and obj.file.icons:
            return obj.file.icons['32']
        return '-'
    file_thumbnail.short_description = 'Preview'
```

#### Фаза 5: Тестирование (1 день)
- Загрузка документов
- Рассылка по отделам
- Ознакомление
- Права доступа
- API endpoints

#### Фаза 6: Деплой и откат старой версии (0.5 дня)

---

## Экономия ресурсов

### Код:
- **Было:** 1180 строк кастомного кода
- **Станет:** ~580 строк (50% сокращение)
- **Удаляется:**
  - ~300 строк views (файловые операции → filer)
  - ~150 строк admin (виджеты → filer)
  - ~150 строк кастомной логики (папки, права → filer)

### Функционал:
- **Добавляется бесплатно:**
  - ✅ Drag & drop загрузка
  - ✅ Thumbnails и превью
  - ✅ Папки и категории
  - ✅ Продвинутый поиск
  - ✅ Массовые операции
  - ✅ ACL на уровне файлов
  - ✅ REST API для файлов

### Поддержка:
- **Было:** 100% кастомный код (баги и развитие на вас)
- **Станет:** 50% библиотечный код (поддержка сообществом)

---

## Альтернатива: Минимальные улучшения (если нет времени на рефакторинг)

Если полная замена не вариант, сделайте минимальные улучшения:

1. **Добавьте preview файлов:**
   ```bash
   pip install django-file-upload-preview
   ```

2. **Добавьте версионирование:**
   ```bash
   pip install django-reversion
   ```

3. **Улучшите поиск через watson:**
   ```python
   watson.register(Document, fields=('title', 'description'))
   ```

4. **Добавьте экспорт списка:** 
   ```bash
   pip install django-import-export
   ```

**Трудозатраты:** 4-6 часов  
**Результат:** +версионирование, +поиск, +экспорт (без рефакторинга)

---

## Вывод

**НЕТ полной готовой замены** для вашего приложения documents, так как специфичная логика (рассылка по отделам + трекинг ознакомления) уникальна для корпоративных систем.

**Рекомендуемый путь:** 
1. Используйте **django-filer** для хранения файлов (50% функционала)
2. Оставьте кастомные модели для рассылки и ознакомления (50% функционала)
3. Добавьте **django-reversion** для версионирования (бонус)

**Экономия:** ~600 строк кода + профессиональное хранилище файлов  
**Трудозатраты:** 3-5 дней  
**ROI:** Высокий (улучшение UX + сокращение кода)

---

**Автор:** GitHub Copilot  
**Дата:** 28 февраля 2026
