# Django-FSM интеграция для Documents

**Дата:** 28 февраля 2026  
**Версия:** django-fsm==3.0.1  
**Статус:** ✅ Реализовано и протестировано

---

## Обзор

Django-FSM добавляет workflow управление для документов с поддержкой строгих переходов между состояниями.

### Состояния документа

```python
class Document.Status:
    DRAFT = 'draft'           # Черновик (по умолчанию)
    IN_REVIEW = 'in_review'   # На рассмотрении
    APPROVED = 'approved'     # Одобрен
    PUBLISHED = 'published'   # Опубликован
    ARCHIVED = 'archived'     # Архивирован
    REJECTED = 'rejected'     # Отклонен
```

### Диаграмма переходов

```
┌──────────┐
│  draft   │ (создание документа)
└─────┬────┘
      │ submit_for_review()
      ↓
┌──────────────┐
│  in_review   │ ←────────────────┐
└──────┬───────┘                  │
       │                          │
       ├─→ approve() ──→ ┌──────────┐
       │                 │ approved │
       │                 └────┬─────┘
       │                      │ publish()
       └─→ reject() ──→       ↓
           ┌──────────┐    ┌───────────┐
           │ rejected │    │ published │
           └──────────┘    └─────┬─────┘
                                 │
                                 ├─→ archive() ──→ ┌──────────┐
                                 │                  │ archived │
                                 │                  └────┬─────┘
                                 │                       │
                                 │   unarchive() ←───────┘
                                 └───────────────────────┘
```

**Примечание:** Из любого состояния (draft, in_review) можно вернуться в draft через `return_to_draft()`.

---

## Использование

### В коде Python

```python
from documents.models import Document

# Создание документа (статус = draft)
doc = Document.objects.create(
    title="Новый документ",
    uploaded_by=user
)
print(doc.status)  # 'draft'

# Отправка на рассмотрение
doc.submit_for_review()
doc.save()
print(doc.status)  # 'in_review'

# Одобрение
doc.approve()
doc.save()
print(doc.status)  # 'approved'

# Публикация (отправка уведомлений)
doc.publish()
doc.save()
print(doc.status)  # 'published'

# Архивирование
doc.archive()
doc.save()
print(doc.status)  # 'archived'
```

### Проверка доступных переходов

```python
from django_fsm import get_available_FIELD_transitions

# Получить список доступных transitions
transitions = get_available_FIELD_transitions(doc, Document.status)

for transition in transitions:
    print(f"{transition.name}: {transition.source} → {transition.target}")
```

### Обработка недопустимых переходов

```python
from django_fsm import TransitionNotAllowed

try:
    doc.publish()  # Если doc.status != 'approved'
    doc.save()
except TransitionNotAllowed:
    print("Невозможно опубликовать документ из текущего состояния")
```

---

## API эндпоинты

Все transitions доступны через REST API:

### 1. Отправить на рассмотрение
```http
POST /api/v1/documents/{id}/submit-for-review/
```
**Переход:** draft → in_review

### 2. Одобрить
```http
POST /api/v1/documents/{id}/approve/
```
**Переход:** in_review → approved

### 3. Отклонить
```http
POST /api/v1/documents/{id}/reject/
```
**Переход:** in_review → rejected

### 4. Опубликовать
```http
POST /api/v1/documents/{id}/publish/
```
**Переход:** approved → published  
**Действие:** Отправляются уведомления получателям

### 5. Вернуть в черновики
```http
POST /api/v1/documents/{id}/return-to-draft/
```
**Переход:** draft/in_review → draft

### 6. Архивировать
```http
POST /api/v1/documents/{id}/archive/
```
**Переход:** published → archived

### 7. Разархивировать
```http
POST /api/v1/documents/{id}/unarchive/
```
**Переход:** archived → published

### Пример запроса

```bash
curl -X POST \
  http://localhost:8000/api/v1/documents/42/approve/ \
  -H "Authorization: Bearer <token>"
```

**Ответ:**
```json
{
  "id": 42,
  "title": "Документ",
  "status": "Одобрен",
  "status_code": "approved",
  "uploaded_at": "2026-02-28T10:00:00Z",
  ...
}
```

**Ошибка (недопустимый переход):**
```json
{
  "error": "Can't switch from draft to approved"
}
```

---

## Админка Django

### Отображение статуса

В списке документов:
- **status_badge** - цветной индикатор статуса
  - 🟢 Одобрен (зеленый)
  - 🔵 Опубликован (синий)
  - 🔴 Отклонен (красный)
  - ⚪ Черновик (серый)
  - 🔷 На рассмотрении (голубой)

### Доступные переходы

В форме редактирования документа:
- Секция **Workflow** (свернута по умолчанию)
- Поле **Доступные переходы** - список возможных переходов из текущего состояния

---

## Интеграция с уведомлениями

### Автоматическая отправка при публикации

При вызове `doc.publish()`:
1. Статус меняется на `published`
2. Срабатывают сигналы из `documents/notification_signals.py`
3. Уведомления отправляются:
   - Всем сотрудникам (если `sent_to_all=True`)
   - Конкретным получателям (если указаны)
   - Сотрудникам отделов (если указаны departments)

### Отложенная публикация

Можно создать документ в статусе `draft`, пройти через `in_review` → `approved`, и опубликовать позже:

```python
# Создание черновика
doc = Document.objects.create(title="Важный документ", status='draft')

# Рассмотрение и одобрение
doc.submit_for_review()
doc.save()
doc.approve()
doc.save()

# Публикация когда готово (например, в определенное время)
doc.publish()  # Уведомления отправятся здесь
doc.save()
```

---

## Фильтрация по статусам

### В Django ORM

```python
# Все черновики
drafts = Document.objects.filter(status=Document.Status.DRAFT)

# Опубликованные документы
published = Document.objects.filter(status=Document.Status.PUBLISHED)

# Документы на рассмотрении или одобренные
pending = Document.objects.filter(
    status__in=[Document.Status.IN_REVIEW, Document.Status.APPROVED]
)
```

### В API

```http
GET /api/v1/documents/?status=published
GET /api/v1/documents/?status=draft
```

---

## Тестирование

### Юнит-тесты

```python
from documents.models import Document

def test_fsm_transitions():
    doc = Document.objects.create(title="Test", status='draft')
    
    # Проверка начального состояния
    assert doc.status == 'draft'
    
    # Переход draft → in_review
    doc.submit_for_review()
    doc.save()
    assert doc.status == 'in_review'
    
    # Переход in_review → approved
    doc.approve()
    doc.save()
    assert doc.status == 'approved'
    
    # Переход approved → published
    doc.publish()
    doc.save()
    assert doc.status == 'published'
```

### Результаты

```
✅ Все 16 юнит-тестов проходят
✅ FSM transitions работают корректно
✅ API эндпоинты доступны
```

---

## Миграция существующих данных

При применении миграции `0006_add_fsm_status.py`:
- Всем существующим документам присваивается статус `draft`
- Можно массово обновить статус:

```python
# Опубликовать все старые документы
Document.objects.filter(status='draft').update(status='published')
```

---

## Расширение функционала

### Добавление новых состояний

```python
class Document(models.Model):
    class Status(models.TextChoices):
        # Existing...
        CANCELLED = 'cancelled', _('Отменен')  # Новое состояние
    
    @transition(field=status, source='*', target=Status.CANCELLED)
    def cancel(self):
        """Отменить документ из любого состояния."""
        pass
```

### Добавление условий перехода

```python
@transition(
    field=status,
    source=Status.IN_REVIEW,
    target=Status.APPROVED,
    conditions=[lambda doc: doc.file is not None]  # Только если файл загружен
)
def approve(self):
    """Одобрить документ (только с файлом)."""
    pass
```

### Добавление побочных эффектов

```python
@transition(field=status, source=Status.APPROVED, target=Status.PUBLISHED)
def publish(self):
    """Опубликовать и отправить email."""
    # Побочный эффект: отправка email
    send_mail(
        'Документ опубликован',
        f'Документ "{self.title}" был опубликован',
        'noreply@company.com',
        [user.email for user in self.recipients.all()]
    )
```

---

## Заключение

Django-FSM успешно интегрирован в приложение documents:

✅ **6 состояний** документа с четкими переходами  
✅ **7 transitions** с защитой от недопустимых переходов  
✅ **API эндпоинты** для всех transitions  
✅ **Админка** с визуальными индикаторами  
✅ **Интеграция** с системой уведомлений  
✅ **Тесты** проходят успешно

**Следующие шаги:**
- Добавить права доступа к transitions (например, approve только для модераторов)
- Логирование всех изменений статусов
- UI для workflow в frontend приложении
