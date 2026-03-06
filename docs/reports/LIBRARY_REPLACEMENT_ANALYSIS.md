# Анализ замены кастомных модулей на готовые библиотеки

**Дата:** 27 февраля 2026  
**Статус:** Рекомендации к внедрению

---

## 🎯 Цель

Снизить объём технического долга через замену кастомных решений на battle-tested библиотеки с активным развитием и поддержкой сообщества.

---

## 📊 Приоритетные замены

### 1. ⭐ **Кэширование (common/cache_decorators.py)** → `django-cacheback` или `django-cacheops`

**Текущая реализация:**
- Кастомные декораторы `@cache_page_per_user`, `@cache_api_response`
- Ручная инвалидация через `invalidate_cache_pattern()`
- Redis-специфичная логика (~130 строк кода)

**Рекомендуемая замена:**
```bash
pip install django-cacheops==7.0.2
```

**Преимущества:**
- ✅ Автоматическая инвалидация при изменении моделей
- ✅ Поддержка queryset кэширования
- ✅ Декораторы per-user/per-args из коробки
- ✅ Интеграция с Django ORM
- ✅ Redis + Django ORM invalidation

**Миграция:**
```python
# Было:
@cache_page_per_user(timeout=300, cache_prefix="feed")
def my_view(request):
    ...

# Станет:
from cacheops import cached_view
@cached_view(timeout=300)
def my_view(request):
    ...
```

**Сложность:** 🟢 Низкая (2-4 часа)  
**Impact:** 🔥 Высокий - используется в feed, api, realtime

---

### 2. ⭐ **Email-рассылки (common/emails.py)** → `django-post_office`

**Текущая реализация:**
- Функция `send_templated_mail()` (~80 строк)
- Синхронная отправка через `EmailMultiAlternatives`
- Ручная обработка HTML/TXT шаблонов
- Нет очереди, приоритизации, статистики

**Рекомендуемая замена:**
```bash
pip install django-post-office==3.8.0
```

**Преимущества:**
- ✅ Очередь отправки с celery/rq/database
- ✅ Планирование (scheduled emails)
- ✅ Админка с логированием и статистикой
- ✅ Шаблоны в БД с переменными
- ✅ Приоритизация писем
- ✅ Batch отправка
- ✅ HTML + Text из коробки

**Миграция:**
```python
# Было:
send_templated_mail(
    subject="Welcome",
    to=["user@example.com"],
    template_base="emails/welcome",
    context={"name": "John"}
)

# Станет:
from post_office import mail
mail.send(
    recipients=["user@example.com"],
    template="welcome",
    context={"name": "John"},
    priority='now'  # или 'high', 'medium', 'low'
)
```

**Сложность:** 🟡 Средняя (4-8 часов)  
**Impact:** 🔥 Высокий - используется в employees, communications, notifications

---

### 3. ⭐ **Обработка изображений (common/image_utils.py)** → `easy-thumbnails` или `sorl-thumbnail`

**Текущая реализация:**
- Функция `compress_image()` (~150 строк)
- Ручное сжатие через Pillow
- EXIF rotation
- Resize с пропорциями

**Рекомендуемая замена:**
```bash
pip install easy-thumbnails==2.10.0
```

**Преимущества:**
- ✅ Автоматическая генерация thumbnails on-demand
- ✅ Async processing через celery
- ✅ Кэширование результатов
- ✅ Водяные знаки, фильтры
- ✅ EXIF rotation из коробки
- ✅ CDN integration

**Миграция:**
```python
# Было:
compressed_data = compress_image(
    data,
    max_width=512,
    max_height=512,
    quality=85
)

# Станет (в модели):
from easy_thumbnails.fields import ThumbnailerImageField

class Employee(models.Model):
    avatar = ThumbnailerImageField(
        upload_to='avatars/',
        resize_source=dict(size=(512, 512), quality=85)
    )
```

**Сложность:** 🟡 Средняя (6-10 часов)  
**Impact:** 🟠 Средний - используется в employees, hikcentral

---

### 4. 🟢 **Права доступа** → Улучшение с `django-rules` или `django-guardian`

**Текущая реализация:**
- Кастомные permissions в api/v1/schedule/permissions.py
- Ручная проверка прав через `has_permission()`

**Рекомендуемая замена:**
```bash
pip install django-rules==4.1.0
```

**Преимущества:**
- ✅ Декларативные правила в одном месте
- ✅ Computed permissions (динамические)
- ✅ Интеграция с Django admin
- ✅ Тестируемость правил
- ✅ Поддержка @permission_required декоратора

**Сложность:** 🟢 Низкая (2-4 часа)  
**Impact:** 🟠 Средний - новая фича, не ломает существующее

---

### 5. 🟢 **API Client (api/client.py)** → `httpx` (async) или улучшение через `requests-cache`

**Текущая:**
```python
# api/client.py - синхронный requests
response = requests.get(url, headers=headers)
```

**Рекомендация:**
```bash
pip install requests-cache==1.2.1
```

**Преимущества:**
- ✅ Transparent HTTP caching
- ✅ SQLite/Redis/MongoDB backends
- ✅ ETags, Cache-Control support
- ✅ Экономия внешних API запросов

**Сложность:** 🟢 Минимальная (1-2 часа)  
**Impact:** 🟠 Средний - используется в bots, hikcentral, external_sync

---

## 📈 Уже используемые библиотеки (хорошо)

✅ **django-service-objects** - Service Layer Pattern (добавлен)  
✅ **django-scheduler** - Календарь и события  
✅ **django-watson** - Full-text search  
✅ **django-filter** - API фильтрация  
✅ **django-simple-history** - Версионирование моделей  
✅ **celery** + **redis** - Асинхронные задачи  
✅ **django-celery-beat** - Планировщик задач  
✅ **django-push-notifications** - Push уведомления  
✅ **django-channels** - WebSocket  
✅ **djangorestframework** - REST API  

---

## ⚠️ Модули, которые НЕ стоит заменять

### `common/external_sync_mixin.py`
**Причина:** Специфичная бизнес-логика синхронизации с внешними системами (HikCentral и др.). Слишком кастомная, нет универсальной библиотеки.

### `ldap_sync/`
**Причина:** Уже используется `ldap3==2.9.1` - отличная библиотека. Наш код - обертка с бизнес-логикой.

### `search/`
**Причина:** Уже используется `django-watson==1.6.3` для full-text search. Допилить существующее.

---

## 🎯 План внедрения (рекомендуемый порядок)

### Фаза 1: Quick Wins (1-2 недели)
1. ✅ **django-service-objects** - УЖЕ ВНЕДРЕНО (employees/services/)
2. 🔲 **requests-cache** - минимальные изменения, моментальный эффект
3. 🔲 **django-rules** - новая фича, не ломает старое

### Фаза 2: Core Improvements (2-3 недели)
4. 🔲 **django-cacheops** - заменяет common/cache_decorators.py
5. 🔲 **django-post-office** - заменяет common/emails.py

### Фаза 3: Media Optimization (1-2 недели)
6. 🔲 **easy-thumbnails** - заменяет common/image_utils.py

---

## 📊 Метрики улучшения

| Метрика | До | После (прогноз) |
|---------|-----|------------------|
| **Кастомный код** | ~360 строк | ~50 строк |
| **Тесты** | 11 (6 passing) | ~30 (библиотечные + наши) |
| **Maintenance** | Высокий | Низкий (community-driven) |
| **Багов** | Средне | Низко |
| **Документация** | Минимальная | Полная (от библиотек) |

---

## 🔗 Ссылки на библиотеки

- [django-cacheops](https://github.com/Suor/django-cacheops) - 2.4k ⭐
- [django-post-office](https://github.com/ui/django-post_office) - 1.1k ⭐
- [easy-thumbnails](https://github.com/SmileyChris/easy-thumbnails) - 1.4k ⭐
- [django-rules](https://github.com/dfunckt/django-rules) - 2.1k ⭐
- [requests-cache](https://github.com/requests-cache/requests-cache) - 2.2k ⭐

---

## ✅ След шаги

1. **Утверждение плана** - выбрать приоритетные библиотеки
2. **PoC** - proof of concept на dev окружении для каждой библиотеки
3. **Миграция** - поэтапно по фазам с тестированием
4. **Cleanup** - удаление старого кода, обновление документации

---

**Подготовил:** AI Assistant  
**Дата:** 27.02.2026  
**Версия:** 1.0
