# API v1/schedule - django-scheduler endpoints

Новая система календаря на проверенном решении **django-scheduler**.  
Работает **параллельно** со старым `/api/v1/calendar/`.

---

## 🌐 Endpoints

### Календари

**Список календарей**
```http
GET /api/v1/schedule/calendars/
```

**Создать календарь**
```http
POST /api/v1/schedule/calendars/
Content-Type: application/json

{
  "name": "Мой календарь",
  "slug": "my-calendar"
}
```

**Детали календаря**
```http
GET /api/v1/schedule/calendars/1/
```

---

### События

**Список событий**
```http
GET /api/v1/schedule/events/
GET /api/v1/schedule/events/?calendar=1
GET /api/v1/schedule/events/?start=2026-02-01T00:00:00Z&end=2026-03-01T00:00:00Z
```

**Создать событие**
```http
POST /api/v1/schedule/events/
Content-Type: application/json

{
  "title": "Встреча с клиентом",
  "description": "Обсуждение проекта",
  "start": "2026-02-24T15:00:00+03:00",
  "end": "2026-02-24T16:00:00+03:00",
  "calendar": 1,
  "color_event": "#ff5733"
}
```

**Событие с повторением (rrule)**
```http
POST /api/v1/schedule/events/
Content-Type: application/json

{
  "title": "Еженедельная планёрка",
  "start": "2026-02-24T10:00:00+03:00",
  "end": "2026-02-24T11:00:00+03:00",
  "calendar": 1,
  "rule": 1
}
```

**Получить материализованные вхождения**
```http
GET /api/v1/schedule/events/occurrences/?calendar=1&start=2026-02-01T00:00:00Z&end=2026-03-01T00:00:00Z
```

Возвращает все вхождения recurring событий + обычные события в диапазоне.

---

### Правила повторения (rrule)

**Список правил**
```http
GET /api/v1/schedule/rules/
```

**Создать правило (RFC 5545)**
```http
POST /api/v1/schedule/rules/
Content-Type: application/json

{
  "name": "Каждый понедельник",
  "description": "FREQ=WEEKLY;BYDAY=MO",
  "frequency": "WEEKLY",
  "params": "FREQ=WEEKLY;BYDAY=MO"
}
```

**Примеры rrule:**
- `FREQ=DAILY` - ежедневно
- `FREQ=WEEKLY;BYDAY=MO,WE,FR` - пн, ср, пт
- `FREQ=WEEKLY;INTERVAL=2;BYDAY=TU` - каждые 2 недели по вторникам
- `FREQ=MONTHLY;BYMONTHDAY=15` - 15 числа каждого месяца
- `FREQ=MONTHLY;BYDAY=-1MO` - последний понедельник месяца
- `FREQ=YEARLY;BYMONTH=2;BYMONTHDAY=29` - 29 февраля (високосный год)

---

### Участники встреч

**Список участников события**
```http
GET /api/v1/schedule/relations/?event=1
```

**Добавить участника**
```http
POST /api/v1/schedule/relations/
Content-Type: application/json

{
  "event": 1,
  "content_type": "employees.employee",
  "object_id": 5,
  "distinction": "required"
}
```

**Удалить участника**
```http
DELETE /api/v1/schedule/relations/1/
```

---

### Вхождения (Occurrences)

**Список вхождений**
```http
GET /api/v1/schedule/occurrences/?event=1
```

Occurrences создаются автоматически для recurring событий.

---

## 🔄 Сравнение со старым API

| Старый (calendar_app) | Новый (django-scheduler) |
|----------------------|--------------------------|
| `/api/v1/calendar/events/` | `/api/v1/schedule/events/` |
| `/api/v1/calendar/calendars/` | `/api/v1/schedule/calendars/` |
| `start_date + start_time` | `start` (DateTimeField с timezone) |
| `recurrence` (6 типов) | `rule` (RFC 5545 rrule) |
| ❌ Нет timezone | ✅ pytz timezone |
| ❌ Нет участников | ✅ EventRelation |
| ❌ Нет iCalendar | ✅ RFC 5545 |

---

## ✅ Преимущества нового API

1. **Timezone support** — события с правильными часовыми поясами
2. **RFC 5545 rrule** — стандартные правила повторения
3. **Участники встреч** — EventRelation (кто приглашён, RSVP)
4. **iCalendar export** — интеграция с Outlook/Google/Apple
5. **Проверенный код** — django-scheduler (community support)
6. **Документация** — ReadTheDocs официальная

---

## 🧪 Тестирование

### Создать тестовый календарь

```bash
curl -X POST http://localhost:8000/api/v1/schedule/calendars/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Тестовый календарь",
    "slug": "test-calendar"
  }'
```

### Создать событие

```bash
curl -X POST http://localhost:8000/api/v1/schedule/events/ \
  -H "Authorization: Bearer YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title": "Тестовое событие",
    "start": "2026-02-24T15:00:00+03:00",
    "end": "2026-02-24T16:00:00+03:00",
    "calendar": 1
  }'
```

### Получить события календаря

```bash
curl http://localhost:8000/api/v1/schedule/events/?calendar=1 \
  -H "Authorization: Bearer YOUR_TOKEN"
```

---

## 📚 Следующие шаги

1. ✅ **API создан** — `/api/v1/schedule/` работает
2. ⏳ **Тестирование** — создать события, проверить rrule
3. ⏳ **Фронтенд** — подключить к новому API
4. ⏳ **Миграция данных** — перенести из старого календаря
5. ⏳ **Переключение** — использовать только новый API
6. ⏳ **Удаление старого** — через 2-3 спринта
