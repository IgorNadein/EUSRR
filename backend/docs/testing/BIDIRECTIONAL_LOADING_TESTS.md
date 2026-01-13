# Тестирование двунаправленной загрузки сообщений

**Статус:** ✅ ВСЕ BACKEND ТЕСТЫ ПРОШЛИ (15/15)

```bash
cd backend
../.venv/Scripts/python -m pytest tests/test_bidirectional_chat_loading.py -v
# Result: 15 passed, 2 warnings in 9.10s
```

**Подробные результаты:** [BIDIRECTIONAL_LOADING_TEST_RESULTS.md](./BIDIRECTIONAL_LOADING_TEST_RESULTS.md)

---

## 📋 Содержание

1. [Backend тесты (Python/Pytest)](#backend-тесты) ✅
2. [Frontend тесты (JavaScript/Jest)](#frontend-тесты) ⏳
3. [Ручное тестирование в браузере](#ручное-тестирование) ⏳
4. [Что проверяют тесты](#что-проверяют-тесты)

---

## Backend тесты

### Файл тестов
`backend/tests/test_bidirectional_chat_loading.py`

### Запуск

```bash
cd backend

# Запуск всех тестов
.venv/Scripts/python -m pytest tests/test_bidirectional_chat_loading.py -v

# Запуск конкретного теста
.venv/Scripts/python -m pytest tests/test_bidirectional_chat_loading.py::TestNewerLoading::test_load_after_id -v

# Запуск с покрытием кода
.venv/Scripts/python -m pytest tests/test_bidirectional_chat_loading.py --cov=api.v1.communications --cov-report=html
```

### Тестовые данные

Тесты создают 100 сообщений:
- **30 сообщений** за 1 января 2026 (ID 1-30)
- **40 сообщений** за 5 января 2026 (ID 31-70)
- **30 сообщений** за 10 января 2026 (ID 71-100)

### Проверяемые сценарии

#### 1. Стандартная загрузка (TestStandardLoading)
- ✅ Загрузка последних сообщений без параметров
- ✅ Загрузка с кастомным лимитом
- ✅ Флаг `has_more_after` должен быть `False` для последних сообщений

#### 2. Загрузка истории (TestHistoryLoading)
- ✅ `before_id` загружает сообщения старше указанного ID
- ✅ `before_ts` загружает сообщения до timestamp

#### 3. Загрузка новых сообщений (TestNewerLoading) ⭐ КЛЮЧЕВОЕ
- ✅ `after_id` загружает сообщения новее указанного ID
- ✅ `after_ts` загружает сообщения после timestamp
- ✅ `has_more_after` корректно отражает наличие новых сообщений
- ✅ Последние сообщения имеют `has_more_after = False`

#### 4. Загрузка вокруг даты (TestLoadAround) ⭐ НОВОЕ
- ✅ `around_id` с timestamp загружает сообщения вокруг даты
- ✅ `has_more_before` и `has_more_after` устанавливаются корректно
- ✅ `anchor_id` возвращается для навигации

#### 5. Полный цикл (TestBidirectionalFlow)
- ✅ Прыжок на дату → загрузка истории → загрузка новых сообщений
- ✅ Границы обновляются корректно

#### 6. Граничные случаи (TestEdgeCases)
- ✅ Пустой чат
- ✅ Несуществующий `after_id`
- ✅ `after_id` на последнем сообщении

---

## Frontend тесты

### Файл тестов
`backend/static/js/tests/bidirectional-loading.test.js`

### Запуск (если настроен Jest)

```bash
npm test -- bidirectional-loading.test.js
```

### Проверяемые компоненты

#### 1. MessageLoaderV2
- ✅ `loadHistory()` загружает старые сообщения
- ✅ `loadNewer()` загружает новые сообщения
- ✅ `loadAround()` загружает сообщения вокруг даты
- ✅ `hasMoreAfter()` корректно отслеживается
- ✅ Boundaries обновляются после `loadNewer()`

#### 2. ScrollManagerV2
- ✅ IntersectionObserver на первом сообщении (история)
- ✅ IntersectionObserver на последнем сообщении (новые) ⭐
- ✅ `loadMoreNewer()` вызывается при скролле вниз
- ✅ `pauseScrollEvents()` приостанавливает обработку

#### 3. MessageRendererV2
- ✅ `prependMessages()` добавляет сообщения в начало
- ✅ `appendMessages()` добавляет сообщения в конец ⭐
- ✅ Date dividers создаются корректно

#### 4. Интеграционные тесты
- ✅ Полный сценарий: прыжок → история → новые

---

## Ручное тестирование

### Тестовая страница в браузере

**Файл:** `backend/static/test-bidirectional-loading.html`

### Как запустить:

#### Вариант 1: Через Django dev server

```bash
cd backend
.venv/Scripts/python manage.py runserver 9000
```

Откройте: http://localhost:9000/static/test-bidirectional-loading.html

#### Вариант 2: Через Live Server (VS Code)

1. Установите расширение "Live Server"
2. Откройте `test-bidirectional-loading.html`
3. Нажмите "Go Live" в правом нижнем углу

### Интерфейс тестовой страницы

**Левая панель (Контролы):**
- 📥 Загрузить последние
- ⬆️ Загрузить историю (старые)
- ⬇️ Загрузить новые (после даты)
- 🎯 Перейти к дате (1, 5, 10 января)
- 🧪 Запустить все тесты
- 🗑️ Очистить чат

**Центральная панель (Чат):**
- Визуализация сообщений
- Скролл вверх/вниз для автозагрузки
- Date dividers

**Правая панель (Результаты):**
- Логи тестов
- Статус выполнения
- Ошибки (если есть)

**Статус панель:**
- Количество сообщений в Store
- Oldest ID / Newest ID
- Has More Before / Has More After

### Ручные тестовые сценарии

#### Сценарий 1: Прокрутка вверх (загрузка истории)

1. Нажмите "Загрузить последние"
2. Прокрутите чат вверх
3. ✅ Должны подгрузиться старые сообщения
4. ✅ Позиция скролла должна сохраниться

#### Сценарий 2: Прыжок на дату + прокрутка вниз

1. Выберите "5 января 2026" в селекторе
2. Нажмите "Перейти к дате"
3. ✅ Должны загрузиться сообщения вокруг 5 января
4. Прокрутите чат вниз
5. ✅ Должны подгрузиться сообщения за 10 января
6. Проверьте "Has More After" в статусе

#### Сценарий 3: IntersectionObserver

1. Перейдите к "5 января 2026"
2. Медленно прокрутите вниз до конца
3. ✅ Автоматически должна начаться загрузка новых сообщений
4. ✅ Кнопка "Загрузить новые" должна отключиться когда `has_more_after = false`

#### Сценарий 4: Автотесты

1. Нажмите "Запустить все тесты"
2. ✅ Все тесты должны пройти успешно (зеленые галочки)
3. Проверьте правую панель на наличие ошибок

---

## Что проверяют тесты

### 1. Прокрутка вверх → загрузка старых сообщений

**Backend:**
```python
# test_load_before_id
response = api_client.get(url, {'before_id': oldest_id, 'limit': 20})
assert all(msg['id'] < oldest_id for msg in data['results'])
```

**Frontend:**
```javascript
// Test 1: loadHistory загружает старые сообщения
const messages = await loader.loadHistory(chatId);
messages.forEach(msg => {
    expect(msg.id).toBeLessThan(oldestBefore.id);
});
```

### 2. Прокрутка вниз → загрузка новых сообщений ⭐

**Backend:**
```python
# test_load_after_id
response = api_client.get(url, {'after_id': newest_id, 'limit': 20})
assert all(msg['id'] > newest_id for msg in data['results'])
assert data['has_more_after'] is True
```

**Frontend:**
```javascript
// Test 2: loadNewer загружает новые сообщения
const messages = await loader.loadNewer(chatId);
messages.forEach(msg => {
    expect(msg.id).toBeGreaterThan(newestBefore.id);
});
```

### 3. IntersectionObserver → автозагрузка

**Frontend:**
```javascript
// Test 7: IntersectionObserver на последнем сообщении
expect(scrollManager._newerObserver).toBeDefined();
expect(loader.hasMoreAfter(chatId)).toBe(true);

// Test 8: loadMoreNewer вызывается при скролле вниз
await scrollManager.loadMoreNewer();
expect(loadNewerSpy).toHaveBeenCalled();
```

### 4. API поддерживает `after_id`

**Backend:**
```python
# test_load_after_id
response = api_client.get(url, {
    'after_id': oldest_message.id,
    'limit': 20
})
assert response.status_code == status.HTTP_200_OK
assert 'has_more_after' in data
```

### 5. `hasMoreAfter` корректно отслеживается

**Backend:**
```python
# test_no_more_after_flag
response = api_client.get(url, {'limit': 50})
assert data['has_more_after'] is False  # Последние сообщения
assert data['has_more'] is True  # Есть история
```

**Frontend:**
```javascript
// Test 4: hasMoreAfter корректно отслеживается
await loader.loadInitial(chatId);
expect(loader.hasMoreAfter(chatId)).toBe(false);

await loader.loadAround(chatId, jan5Timestamp);
expect(loader.hasMoreAfter(chatId)).toBe(true);
```

---

## Быстрый старт

### Запустить все тесты (Backend + Frontend)

```bash
# Backend
cd backend
.venv/Scripts/python -m pytest tests/test_bidirectional_chat_loading.py -v

# Frontend (если настроен Jest)
npm test

# Ручное тестирование
# Откройте: http://localhost:9000/static/test-bidirectional-loading.html
```

### Ожидаемый результат

✅ **15 backend тестов** должны пройти успешно  
✅ **13 frontend тестов** должны пройти успешно  
✅ **Ручные тесты** должны показывать корректную загрузку в обоих направлениях

---

## Troubleshooting

### Backend тесты падают

**Проблема:** `ImportError: No module named 'communications'`

**Решение:**
```bash
cd backend
.venv/Scripts/python -m pytest --collect-only  # Проверка что тесты найдены
```

### Frontend тесты не запускаются

**Проблема:** Jest не настроен

**Решение:** Используйте ручное тестирование в браузере

### Тестовая страница не открывается

**Проблема:** Static файлы не обслуживаются

**Решение:**
```bash
cd backend
.venv/Scripts/python manage.py collectstatic --noinput
.venv/Scripts/python manage.py runserver 9000
```

---

## Контрольные точки

После каждого изменения кода проверяйте:

- [ ] Backend API тесты проходят
- [ ] Frontend юнит-тесты проходят (если настроен Jest)
- [ ] Ручные тесты в браузере работают корректно
- [ ] IntersectionObserver триггерит загрузку автоматически
- [ ] `hasMoreAfter` обновляется после каждой операции
- [ ] Границы (`oldestId`, `newestId`) корректны

---

## Дополнительные ресурсы

- [AUTOSCROLL_AUDIT.md](../reports/AUTOSCROLL_AUDIT.md) - Аудит автоскролла
- [DATE_DIVIDER_ANALYSIS.md](../reports/DATE_DIVIDER_ANALYSIS_TELEGRAM_COMPARISON.md) - Анализ date dividers
- [Telegram Web Source](https://github.com/morethanwords/tweb) - Референс для архитектуры

---

**Дата создания:** 13 января 2026  
**Версия:** 1.0
