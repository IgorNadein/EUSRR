# Сравнение реализаций документов: develop vs feature/django-filer-documents

## Краткое резюме

**TL;DR:** Feature ветка в **3 раза сложнее** develop по всем метрикам:
- 8 моделей против 2
- 2613 строк тестов против 888
- FSM workflow с 7 состояниями против простого флага
- django-filer + django-fsm + сложные django-rules против базового DRF

**Вопрос:** Нужна ли эта сложность для use case "публикация регламентов + отслеживание ознакомлений"?

---

## Сравнительная таблица

| Аспект | **develop** (базовая) | **feature** (сложная) |
|--------|----------------------|----------------------|
| **Модели** | 2 | 8 |
| **Строк кода моделей** | ~100 | ~600+ |
| **FSM workflow** | ❌ НЕТ | ✅ 7 состояний |
| **django-filer** | ❌ НЕТ | ✅ Полная интеграция |
| **django-rules** | ⚠️ Шаблон (не работает) | ✅ 6+ predicates |
| **Файлов тестов** | 1 | 5 |
| **Тестовых методов** | 37 | 86 |
| **Строк тестов** | 888 | 2613 |
| **Complexity ratio** | **1x** | **3x** |

---

## 1. Модели данных

### develop: 2 простые модели

```python
# backend/documents/models.py (develop)

class Document(models.Model):
    """Документ для рассылки сотрудникам"""
    title = models.CharField(max_length=255)
    file = models.FileField(upload_to='documents/%Y/%m/%d/')
    description = models.TextField(blank=True)
    uploaded_by = models.ForeignKey(User, ...)
    uploaded_at = models.DateTimeField(auto_now_add=True)
    
    # Targeting
    sent_to_all = models.BooleanField(default=True)
    departments = models.ManyToManyField('employees.Department', ...)
    recipients = models.ManyToManyField(User, ...)

class DocumentAcknowledgement(models.Model):
    """Факт ознакомления с документом"""
    document = models.ForeignKey(Document, ...)
    user = models.ForeignKey(User, ...)
    acknowledged_at = models.DateTimeField(auto_now_add=True)
```

**Философия:** Простота. Загрузил → разослал → отследил ознакомление.

---

### feature: 8 сложных моделей

```python
# backend/documents/models.py (feature)

1. Document (FSM-модель)
   - FilerFileField (django-filer интеграция)
   - FSMField: status (7 состояний)
   - 6 FSM переходов с декораторами
   - Cabinet (папки), DocumentType, tags
   - related_documents (M2M к самой себе)
   - cabinet_path property + методы navigation

2. DocumentAcknowledgement
   - document, user, acknowledged_at

3. DocumentType
   - name, description, icon
   - is_active, requires_approval, max_file_size, allowed_extensions
   - Templates support (title_template, description_template)

4. DocumentMetadata
   - document, created_by
   - metadata_fields (JSONField)
   - Customizable per-document metadata

5. DocumentTag
   - name, color, description
   - Tagging system

6. Cabinet
   - name, description, parent (self-referential)
   - icon, color, can_manage_documents predicate
   - Tree structure (папки в папках)

7. DocumentAuditLog
   - document, user, action, timestamp
   - old_values, new_values (JSONField)
   - Audit trail для всех изменений

8. DocumentComment
   - document, user, comment, created_at
   - parent (nested comments)
   - is_internal flag
```

**Философия:** Полнофункциональная система документооборота с workflow.

---

## 2. FSM Workflow

### develop: Нет workflow

Документ либо создан, либо нет. Всё.

```python
# Document создан → сразу доступен получателям
document = Document.objects.create(
    title="Регламент",
    file=file,
    sent_to_all=True
)
# Готово! Пользователи могут read + acknowledge
```

---

### feature: 7 состояний FSM

```python
# backend/documents/models.py (feature)

class DocumentStatus(models.TextChoices):
    DRAFT = "draft", "Черновик"
    IN_REVIEW = "in_review", "На проверке"
    APPROVED = "approved", "Одобрен"
    PUBLISHED = "published", "Опубликован"
    REJECTED = "rejected", "Отклонён"
    ARCHIVED = "archived", "В архиве"
    UNARCHIVED = "unarchived", "Восстановлен из архива"

# 6 FSM transitions:
@fsm_log_by
@transition(field=status, source='draft', target='in_review',
            permission=lambda instance, user: user.has_perm(...))
def submit_for_review(self, by=None):
    """Черновик → На проверке"""
    ...

@transition(field=status, source='in_review', target='approved', ...)
def approve(self, by=None):
    """На проверке → Одобрен"""
    ...

@transition(field=status, source='in_review', target='rejected', ...)
def reject(self, by=None):
    """На проверке → Отклонён"""
    ...

@transition(field=status, source=['approved', 'rejected'], target='published', ...)
def publish(self, by=None):
    """Одобрен/Отклонён → Опубликован"""
    ...

@transition(field=status, source=['published', 'approved'], target='archived', ...)
def archive(self, by=None):
    """Опубликован/Одобрен → В архиве"""
    ...

@transition(field=status, source='archived', target='draft', ...)
def unarchive(self, by=None):
    """Архив → Черновик"""
    ...
```

**Проблема:** Для use case "публикация регламентов + ознакомление" это избыточно.

**Вопросы:**
- Зачем состояние IN_REVIEW для регламента?
- Кто должен approve регламенты?
- Почему rejected документ можно publish?
- Зачем unarchive возвращает в draft, а не в published?

---

## 3. django-rules Permissions

### develop: Шаблонный код (НЕ РАБОТАЕТ)

```python
# backend/documents/rules.py (develop) - TEMPLATE ONLY!

@rules.predicate
def is_document_owner(user, document):
    """ПРОБЛЕМА: document.created_by не существует в модели!"""
    return document.created_by == user or document.owner == user

@rules.predicate  
def is_document_author(user, document):
    """ПРОБЛЕМА: document.author не существует!"""
    return document.author == user

# Правила определены, но НЕ используются в коде
rules.add_rule('documents.view_document', ...)
rules.add_rule('documents.approve_document', ...)
# ... но нет rules.add_perm(), поэтому Django не видит эти permissions
```

**Вердикт:** Это просто пример/шаблон. Реальные permissions в `api/v1/documents/permissions.py`:

```python
# backend/api/v1/documents/permissions.py (develop)

class DocumentReadOrModelPerms(AdminOrActionOrModelPerms):
    """Простая логика:
    - READ/acknowledge: любой authenticated
    - Фильтрация в queryset: sent_to_all или recipients или departments
    - WRITE: staff или model permissions
    """
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS or action in ('acknowledge', 'download'):
            return request.user.is_authenticated
        return request.user.is_staff or super().has_permission(...)
```

---

### feature: Сложная система django-rules

```python
# backend/documents/rules.py (feature) - РЕАЛЬНО РАБОТАЕТ

# 6+ predicates с object-level permissions:

@rules.predicate
def is_document_uploader(user, document):
    """Автор документа"""
    return document.uploaded_by == user

@rules.predicate
def is_not_document_uploader(user, document):
    """НЕ автор (separation of duties)"""
    return document.uploaded_by != user

@rules.predicate
def can_manage_documents(user):
    """Позиционные права через employee.can_manage_documents"""
    return user.employee.can_manage_documents

@rules.predicate
def can_view_document_in_status(user, document):
    """Видимость зависит от статуса FSM"""
    if document.status == 'published':
        return True
    if document.status == 'draft':
        return document.uploaded_by == user
    # ... etc

# Permissions для каждого FSM action:
rules.add_perm('documents.submit_for_review_document',
    is_superuser | is_document_uploader | can_manage_documents)

rules.add_perm('documents.approve_document',  
    is_superuser | (can_manage_documents & is_not_document_uploader))

rules.add_perm('documents.publish_document',
    is_superuser | (can_manage_documents & is_not_document_uploader))

rules.add_perm('documents.archive_document', ...)
rules.add_perm('documents.unarchive_document', ...)
```

**Два уровня проверки:**

1. **DRF permission class:**
```python
# backend/api/v1/documents/permissions.py (feature)

class DocumentFSMPermission(DjangoModelPermissions):
    def has_object_permission(self, request, view, obj):
        action = view.action
        if action == "submit_for_review":
            return user.has_perm("documents.submit_for_review_document", obj)
        elif action == "approve":
            return user.has_perm("documents.approve_document", obj)
        # ... для каждого FSM action
```

2. **FSM transition decorators:**
```python
@transition(..., permission=lambda instance, user: 
    user.has_perm('documents.approve_document', instance))
def approve(self, by=None):
    ...
```

**Проблема:** Двойная проверка (DRF + FSM) = больше мест для ошибок.

---

## 4. Тестовое покрытие

### develop: 1 файл, 37 тестов, 888 строк

```
backend/tests/api/v1/documents/test_documents_api.py (888 lines)

Структура тестов:
- TestAuthAndPermissions (4 теста)
  - anonymous → 401
  - regular user access policy
  - users with individual perms
  - staff/superuser full access

- TestCreate (5 тестов)
  - sent_to_all=true
  - sent_to_all=false with recipients (JSON/CSV/list)
  - validations
  - skip nonexistent/inactive recipients

- TestRead (2 теста)
  - list with pagination
  - detail fields + file_url

- TestUpdate (4 теста)
  - update title/description
  - replace file multipart
  - toggle sent_to_all
  - patch recipient_ids

- TestDelete (1 тест)
  - delete + cascade acknowledgements

- TestAcknowledge (3 теста)
  - first acknowledge + repeat
  - detail reflects is_acknowledged
  - forbidden if not recipient

- TestSerialization (1 тест)
  - uploaded_by + recipients shape

- TestErrorsAndEdgeCases (4 теста)
  - wrong content type
  - put/patch/delete without perms
  - get without view_perm
  - big file over limit

- TestPerformance (2 теста)
  - no N+1 in list
  - pagination navigation

- TestSecurityAndPolicy (2+ теста)
  - JWT/session auth
  - policy without perms

Итого: ~37 тестов
```

**Покрытие:** CRUD + permissions + acknowledgement + edge cases

---

### feature: 5 файлов, 86 тестов, 2613 строк

```
backend/tests/api/v1/documents/ (4 файла):

1. test_documents_api.py (~1100 lines)
   - Базовый CRUD (как в develop)
   - + Cabinet management
   - + DocumentType endpoints
   - + Tags, metadata

2. test_fsm_workflow.py (~700 lines, 30+ тестов)
   - TestFSMTransitions
     - submit_for_review
     - approve/reject
     - publish
     - archive/unarchive
   - TestFSMPermissions
     - who can transition
     - FSM + django-rules integration
   - TestAuthorCanSubmitOwnDocument (новые 3 теста)
   - TestSeparationOfDuties (WIP, 2 теста не запускались)

3. test_status_visibility.py (~400 lines)
   - Видимость документов зависит от статуса
   - draft → только автор
   - in_review → автор + managers
   - published → все получатели
   - archived → никто (или только managers)

4. test_new_features.py (~400 lines)
   - Related documents
   - Comments (nested)
   - Audit log
   - Metadata fields

backend/tests/integration/test_related_documents_notifications.py (~13 lines)
   - Integration test для уведомлений

Итого: 86 тестов, 2613 строк
```

**Покрытие:** Всё из develop + FSM + Cabinet + Tags + Comments + Audit + Metadata + Related docs

---

## 5. django-filer Integration

### develop: Plain FileField

```python
file = models.FileField(upload_to='documents/%Y/%m/%d/')
```

- Простое хранение в `/media/documents/YYYY/MM/DD/`
- Нет папок, нет организации

---

### feature: Full django-filer

```python
from filer.fields.file import FilerFileField

class Document(models.Model):
    file = FilerFileField(
        verbose_name=_('Файл'),
        related_name='documents',
        on_delete=models.PROTECT,
        null=True,
        blank=True
    )
    cabinet = models.ForeignKey(Cabinet, ...)  # Folder structure
```

**Возможности:**
- Централизованное хранилище файлов
- Папочная структура (Cabinet → вложенные папки)
- Переиспользование файлов между документами
- Thumbnails для изображений
- Permissions на уровне файлов

**Проблема:** Для use case "регламенты" это избыточно.

---

## 6. API Endpoints

### develop: Простой REST

```
GET    /api/v1/documents/           - список (scope=mine для фильтра)
POST   /api/v1/documents/           - создать
GET    /api/v1/documents/{id}/      - детали
PUT    /api/v1/documents/{id}/      - обновить
PATCH  /api/v1/documents/{id}/      - частичное обновление
DELETE /api/v1/documents/{id}/      - удалить
POST   /api/v1/documents/{id}/acknowledge/      - ознакомиться
GET    /api/v1/documents/{id}/acknowledgements/ - ведомость (staff only)
```

**8 endpoints**, стандартный REST.

---

### feature: Extended REST + FSM actions

```
# Base CRUD (как в develop)
GET    /api/v1/documents/
POST   /api/v1/documents/
GET    /api/v1/documents/{id}/
PUT    /api/v1/documents/{id}/
PATCH  /api/v1/documents/{id}/
DELETE /api/v1/documents/{id}/

# FSM actions (новые)
POST   /api/v1/documents/{id}/submit_for_review/
POST   /api/v1/documents/{id}/approve/
POST   /api/v1/documents/{id}/reject/
POST   /api/v1/documents/{id}/publish/
POST   /api/v1/documents/{id}/archive/
POST   /api/v1/documents/{id}/unarchive/

# Acknowledgement
POST   /api/v1/documents/{id}/acknowledge/
GET    /api/v1/documents/{id}/acknowledgements/

# Cabinet management (новые)
GET    /api/v1/cabinets/
POST   /api/v1/cabinets/
GET    /api/v1/cabinets/{id}/
PUT    /api/v1/cabinets/{id}/
DELETE /api/v1/cabinets/{id}/
GET    /api/v1/cabinets/{id}/documents/

# Tags (новые)
GET    /api/v1/documents/tags/
POST   /api/v1/documents/tags/

# Types (новые)
GET    /api/v1/documents/types/
POST   /api/v1/documents/types/

# Comments (новые)
GET    /api/v1/documents/{id}/comments/
POST   /api/v1/documents/{id}/comments/
DELETE /api/v1/documents/{id}/comments/{comment_id}/

# Audit log (новые)
GET    /api/v1/documents/{id}/audit_log/

# Related documents (новые)
POST   /api/v1/documents/{id}/add_related/
POST   /api/v1/documents/{id}/remove_related/
```

**~25+ endpoints** (в 3 раза больше).

---

## 7. Use Case Analysis

### Исходное требование
> "Система для публикации регламентов с отслеживанием ознакомлений"

### Что нужно для этого use case?

**Минимум (MVP):**
1. ✅ Загрузить документ (файл + название + описание)
2. ✅ Выбрать получателей (всем / отделам / конкретным)
3. ✅ Опубликовать (сделать доступным)
4. ✅ Пользователи видят документы
5. ✅ Пользователи нажимают "Ознакомлен"
6. ✅ Ведомость ознакомлений (кто прочитал, кто нет)

**Есть в develop:** ✅ ВСЁ!

### Что добавлено в feature, но НЕ нужно для use case?

| Фича | Нужна? | Почему нет |
|------|--------|------------|
| FSM workflow (7 states) | ❌ | Регламенты не требуют approval workflow |
| draft → in_review → approved | ❌ | Кто будет approving? Зачем? |
| django-filer | ❌ | Файлы и так хранятся, папки не критичны |
| Cabinet (folders) | 🤔 | Nice to have, но не критично |
| DocumentType | ❌ | Overengineering, достаточно тегов |
| DocumentMetadata (JSONField) | ❌ | Custom fields не требуются |
| DocumentTag | 🤔 | Может быть полезно, но не критично |
| DocumentComment | ❌ | Комментарии к регламентам? Зачем? |
| DocumentAuditLog | 🤔 | Audit trail полезен, но не для MVP |
| Related documents | ❌ | Усложняет UI, не критично |
| Separation of duties | ❌ | Если нет approval, то не нужно |

**Вердикт:** 80% feature branch не нужно для use case "регламенты".

---

## 8. Complexity Metrics

### Code Complexity

```bash
# develop branch
backend/documents/models.py:         ~100 lines (2 модели)
backend/documents/rules.py:          ~290 lines (шаблон, не используется)
backend/api/v1/documents/views.py:   ~213 lines (1 ViewSet)
backend/api/v1/documents/serializers.py: ~393 lines (2 serializers + 1 Field)
backend/api/v1/documents/permissions.py: ~50 lines (1 permission class)
TOTAL: ~1046 lines

# feature branch  
backend/documents/models.py:         ~600+ lines (8 моделей + FSM)
backend/documents/rules.py:          ~200+ lines (6+ predicates, работающие)
backend/api/v1/documents/views.py:   ~500+ lines (3+ ViewSets)
backend/api/v1/documents/serializers.py: ~800+ lines (10+ serializers)
backend/api/v1/documents/permissions.py: ~150+ lines (2+ permission classes)
+ admin.py, signals.py, etc.
TOTAL: ~2500+ lines (2.5x сложнее)
```

### Test Complexity

```bash
# develop: 1 file, 37 tests, 888 lines
# feature: 5 files, 86 tests, 2613 lines (3x сложнее)
```

### Maintenance Cost

| Аспект | develop | feature | Разница |
|--------|---------|---------|---------|
| Новый разработчик onboarding | 1 день | 3-5 дней | **3-5x** |
| Время на bug fix | 30 мин | 1-2 часа | **2-4x** |
| Regression risk | Низкий | Средний-Высокий | FSM + много связей |
| Documentation need | Минимально | Критично | Без доки не разобраться |

---

## 9. Проблемы feature branch

### 1. Неясный Use Case
- FSM workflow для чего? Кто approves регламенты?
- Зачем draft, если регламент разрабатывается в Word?
- Separation of duties - для каких процессов?

### 2. Over-engineering
- 8 моделей вместо 2
- 3x больше кода
- 3x больше тестов
- 3x сложнее поддержка

### 3. Неполная реализация
- Separation of duties в WIP состоянии
- 2 теста не запускались: `test_author_cannot_approve_own_document`, `test_author_cannot_publish_own_document`
- FSM permissions не до конца продуманы (почему reject → publish?)

### 4. UX вопросы
- Пользователь создаёт документ → статус draft
- Что дальше? Кнопка "Submit for review"?
- Кто получит уведомление о review?
- Где UI для approve/reject?
- Как пользователь понимает, что документ в архиве?

---

## 10. Рекомендации

### Вариант A: Использовать develop (простой)

**Преимущества:**
- ✅ Работает сейчас
- ✅ Покрывает 100% use case "регламенты + ознакомление"
- ✅ Простой, понятный код
- ✅ 37 тестов уже есть
- ✅ Быстрый onboarding

**Недостатки:**
- ❌ Нет папок (Cabinet)
- ❌ Нет тегов
- ❌ Нет audit trail

**Recommendation:** Добавить к develop минимум фич из feature:
1. Cabinet (папки) - полезно для организации
2. Tags - полезно для категоризации
3. Audit log - полезно для compliance

**Estimated effort:** 1-2 дня (vs 2-3 недели доработки feature)

---

### Вариант B: Упростить feature branch

**Что оставить:**
- ✅ Cabinet (папки) - полезно
- ✅ DocumentTag - полезно
- ✅ DocumentAcknowledgement - критично
- 🤔 DocumentType - можно оставить, но упростить

**Что убрать:**
- ❌ FSM workflow (все 7 состояний)
- ❌ Separation of duties
- ❌ DocumentComment
- ❌ DocumentMetadata (JSONField)
- ❌ Related documents
- ❌ DocumentAuditLog (можно добавить позже)

**Заменить FSM на:**
```python
class Document(models.Model):
    is_published = models.BooleanField(default=True)
    # Если нужен draft: is_published=False
```

**Estimated effort:** 3-5 дней удаления кода + рефакторинг тестов

---

### Вариант C: Оставить feature, но закончить separation of duties

**Преимущества:**
- ✅ Полнофункциональная система
- ✅ FSM workflow готов
- ✅ Cabinet, Tags, Comments

**Недостатки:**
- ❌ Нужно дописать separation of duties (1-2 дня)
- ❌ Нужно продумать UX для FSM (кнопки, уведомления)
- ❌ Нужна документация (1 день)
- ❌ Нужно обучать пользователей (сложный workflow)

**Estimated effort:** 1 неделя до production-ready

---

## 11. Финальный вопрос

**Перед тем как выбрать вариант, ответьте на вопросы:**

1. **Кто будет approving регламенты?**
   - Если никто → FSM не нужен
   - Если юристы/руководители → FSM нужен

2. **Где создаются регламенты?**
   - Если в Word/Google Docs → draft в системе не нужен
   - Если в системе → draft может быть полезен

3. **Нужны ли комментарии к регламентам?**
   - Обычно нет (discussion в другом месте)

4. **Нужны ли связанные документы (related)?**
   - Для регламентов обычно нет

5. **Нужен ли audit trail каждого изменения?**
   - Для compliance - да
   - Для внутренних регламентов - может быть избыточно

6. **Есть ли у пользователей файловые шары?**
   - Если да → зачем дублировать хранение?
   - Может лучше ссылки на файловые шары?

---

## 12. Сравнение по чек-листу "Публикация регламентов"

| Задача | develop | feature | Нужно? |
|--------|---------|---------|--------|
| Загрузить файл | ✅ FileField | ✅ FilerFile | ✅ |
| Навание/описание | ✅ | ✅ | ✅ |
| Организация (папки) | ❌ | ✅ Cabinet | 🤔 Nice to have |
| Выбрать получателей | ✅ sent_to_all/departments/recipients | ✅ Same | ✅ |
| Опубликовать | ✅ Сразу после create | ⚠️ draft → ... → publish | ✅ Simpler! |
| Видят получатели | ✅ Сразу | ⚠️ Только после publish | ✅ Simpler! |
| Кнопка "Ознакомлен" | ✅ | ✅ | ✅ |
| Ведомость ознакомлений | ✅ | ✅ | ✅ |
| Версионирование | ❌ | ❌ (но есть audit) | 🤔 Позже |
| Уведомления | ❌ (но легко добавить) | ❌ (тоже не готово) | ✅ Нужно! |

**Вывод:** develop проще и покрывает базовый use case. feature добавляет сложность без явной пользы.

---

## 13. Conclusion

### Текущая ситуация
- develop работает, проста, покрывает 100% базового use case
- feature в 3 раза сложнее, но не даёт критичных преимуществ для use case "регламенты"
- feature в WIP состоянии (separation of duties не закончена)

### Вопрос к пользователю
> "Зачем нам FSM workflow draft → in_review → approved → published для публикации регламентов?"

Если ответ "не нужен" → **Вариант A: develop + минимум из feature**

Если ответ "нужен approval process" → **Вариант C: доделать feature**

### Рекомендация агента: **Вариант A**

**Почему:**
1. Use case "регламенты" не требует сложного workflow
2. develop работает и тестируется
3. Можно добавить Cabinet + Tags за 1-2 дня
4. Быстрее time-to-market
5. Проще поддержка
6. Проще обучение пользователей

**Что добавить к develop:**
```python
# backend/documents/models.py (develop + improvements)

class Cabinet(models.Model):
    """Папка для организации документов"""
    name = models.CharField(max_length=255)
    parent = models.ForeignKey('self', null=True, blank=True)

class DocumentTag(models.Model):
    """Тег для категоризации"""
    name = models.CharField(max_length=100, unique=True)
    color = models.CharField(max_length=7, default='#007bff')

class Document(models.Model):
    # ... existing fields ...
    cabinet = models.ForeignKey(Cabinet, null=True, blank=True)
    tags = models.ManyToManyField(DocumentTag, blank=True)
```

**Estimated effort:** 1-2 дня → production ready

vs

**feature branch completion:** 1 неделя → production ready (но сложнее)

---

## Приложение: Метрики по файлам

### develop branch

```
backend/documents/
├── models.py (100 lines, 2 models)
├── rules.py (290 lines, template/example)
├── admin.py
├── views.py
└── ...

backend/api/v1/documents/
├── views.py (213 lines, 1 ViewSet)
├── serializers.py (393 lines, 2 serializers)
├── permissions.py (50 lines, 1 class)
└── urls.py

backend/tests/api/v1/documents/
└── test_documents_api.py (888 lines, 37 tests)

TOTAL FILES: ~8
TOTAL LINES: ~1900
TOTAL TESTS: 37
COMPLEXITY: Low
```

### feature branch

```
backend/documents/
├── models.py (600+ lines, 8 models)
├── rules.py (200+ lines, 6+ predicates)
├── admin.py (enlarged)
├── signals.py (new)
├── tasks.py (new)
└── ...

backend/api/v1/documents/
├── views.py (500+ lines, 3+ ViewSets)
├── serializers.py (800+ lines, 10+ serializers)
├── permissions.py (150+ lines, 2+ classes)
└── urls.py (enlarged)

backend/tests/api/v1/documents/
├── test_documents_api.py (~1100 lines)
├── test_fsm_workflow.py (~700 lines)
├── test_status_visibility.py (~400 lines)
└── test_new_features.py (~400 lines)

backend/tests/integration/
└── test_related_documents_notifications.py

TOTAL FILES: ~15+
TOTAL LINES: ~4200+
TOTAL TESTS: 86
COMPLEXITY: High
```

---

**Дата создания:** 2025-01-XX  
**Автор:** AI Agent после анализа обеих веток  
**Статус:** Ожидание решения пользователя
