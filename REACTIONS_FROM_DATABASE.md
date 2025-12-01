# Система управления реакциями из БД

## Обзор

Система доступных реакций теперь полностью управляется через базу данных вместо жёсткого кодирования в JavaScript.

## Архитектура

### Backend

#### Модель `AvailableReaction`
```python
# communications/models.py
class AvailableReaction(models.Model):
    emoji = models.CharField(max_length=10, unique=True)
    name = models.CharField(max_length=50)
    order = models.IntegerField(default=0)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
```

**Поля:**
- `emoji` - Unicode эмодзи (👍, ❤️, и т.д.)
- `name` - Человекочитаемое название ("Лайк", "Сердце")
- `order` - Порядок отображения (меньше = выше)
- `is_active` - Вкл/выкл реакцию без удаления
- `created_at` - Дата добавления

#### API Endpoint

**GET** `/api/v1/communications/reactions/available/`

**Response:**
```json
{
  "ok": true,
  "reactions": [
    {
      "emoji": "👍",
      "name": "Лайк",
      "order": 1
    },
    {
      "emoji": "❤️",
      "name": "Сердце",
      "order": 2
    }
  ]
}
```

**Требования:**
- Требуется авторизация (`@login_required`)
- Возвращает только активные реакции (`is_active=True`)
- Отсортировано по полю `order`

#### Admin-панель

```python
# communications/admin.py
@admin.register(AvailableReaction)
class AvailableReactionAdmin(admin.ModelAdmin):
    list_display = ('emoji', 'name', 'order', 'is_active', 'created_at')
    list_editable = ('order', 'is_active')
    ordering = ('order', 'created_at')
```

**Возможности:**
- Добавление/удаление реакций через admin
- Редактирование порядка прямо в списке
- Быстрое включение/выключение реакций
- Поиск по эмодзи и названию

### Frontend

#### ReactionsConfig (Синглтон)
```javascript
// static/js/config/reactionsConfig.js
import reactionsConfig from './config/reactionsConfig.js';

// Загрузка из API
await reactionsConfig.load();

// Получить массив эмодзи
const emojis = reactionsConfig.getEmojis(); // ['👍', '❤️', ...]

// Проверить доступность
if (reactionsConfig.isAvailable('👍')) { ... }

// Получить название
const name = reactionsConfig.getName('👍'); // "Лайк"
```

**Особенности:**
- Загружается один раз при инициализации чата
- Кэширует результат (повторные вызовы `.load()` возвращают кэш)
- Fallback на дефолтные реакции при ошибке API
- Promise-based (поддержка async/await)

#### Использование в chat-detail-enhanced.js

```javascript
// До инициализации компонентов загружаем реакции
await reactionsConfig.load();
const availableEmojis = reactionsConfig.getEmojis();

// Передаём в MessageContextMenu
const contextMenu = new MessageContextMenu({
    currentUserId: meId,
    emojis: availableEmojis,  // ← Из БД!
    onReactionSelect: async (messageId, emoji) => {
        await reactions.addReaction(messageId, emoji);
    }
});
```

## Инициализация

### 1. Создание миграции
```bash
cd backend
python manage.py makemigrations communications
python manage.py migrate communications
```

### 2. Добавление дефолтных реакций
```bash
python manage.py init_reactions
```

Эта команда создаст 8 стандартных реакций:
- 👍 Лайк
- ❤️ Сердце
- 😂 Смех
- 😮 Удивление
- 😢 Грусть
- 🙏 Спасибо
- 👏 Аплодисменты
- 🔥 Огонь

### 3. Проверка
```bash
python check_reactions.py
```

## Управление реакциями

### Через Admin-панель

1. Перейти в `/admin/communications/availablereaction/`
2. Добавить новую реакцию:
   - Emoji: вставить эмодзи (Ctrl+V)
   - Name: название на русском
   - Order: порядковый номер
   - Is active: ✓
3. Сохранить

**Изменение порядка:**
- В списке реакций отредактировать поле "Order"
- Нажать "Сохранить" внизу страницы

**Отключение реакции:**
- Снять галочку "Is active"
- Нажать "Сохранить"

### Программно

```python
from communications.models import AvailableReaction

# Добавить новую реакцию
AvailableReaction.objects.create(
    emoji='🎉',
    name='Праздник',
    order=9,
    is_active=True
)

# Изменить порядок
reaction = AvailableReaction.objects.get(emoji='👍')
reaction.order = 1
reaction.save()

# Отключить реакцию
reaction.is_active = False
reaction.save()

# Удалить реакцию (не рекомендуется, лучше is_active=False)
reaction.delete()
```

## Data Flow

```
[БД] AvailableReaction
  ↓
[Backend API] /api/v1/communications/reactions/available/
  ↓
[Frontend] reactionsConfig.load()
  ↓
[Cache] reactionsConfig.reactions
  ↓
[Component] MessageContextMenu({ emojis: [...] })
  ↓
[UI] Контекстное меню с реакциями
```

## Преимущества

1. **Централизованное управление** - одно место для изменений
2. **Без deploy** - изменения через admin без перезапуска
3. **Гибкость** - разные реакции для разных чатов (будущее)
4. **Локализация** - названия реакций на нужном языке
5. **Аналитика** - можно отслеживать популярность реакций
6. **Валидация** - можно проверять доступность эмодзи перед использованием

## Миграция со старого подхода

### Было (hardcoded):
```javascript
const contextMenu = new MessageContextMenu({
    emojis: ['👍', '❤️', '😂', '😮', '😢', '🙏', '👏', '🔥']
});
```

### Стало (из БД):
```javascript
await reactionsConfig.load();
const contextMenu = new MessageContextMenu({
    emojis: reactionsConfig.getEmojis()
});
```

## Совместимость

- **Fallback** - если API недоступен, используются дефолтные реакции
- **Кэширование** - одна загрузка на сессию чата
- **Promise-safe** - множественные вызовы `.load()` возвращают один промис

## Расширения

### Реакции по категориям чата
```python
class AvailableReaction(models.Model):
    ...
    chat_types = models.JSONField(
        default=list,
        help_text="['personal', 'group', 'department']"
    )
```

### Кастомные реакции
```python
class AvailableReaction(models.Model):
    ...
    is_custom = models.BooleanField(default=False)
    uploaded_by = models.ForeignKey('employees.Employee', ...)
    image = models.ImageField(...)  # Для не-эмодзи реакций
```

### Статистика
```python
class ReactionStats(models.Model):
    reaction = models.ForeignKey(AvailableReaction, ...)
    usage_count = models.IntegerField(default=0)
    last_used = models.DateTimeField(...)
```

## Troubleshooting

### Реакции не загружаются
1. Проверить консоль браузера: `[ReactionsConfig] Loading...`
2. Проверить Network tab: `/api/v1/communications/reactions/available/`
3. Проверить авторизацию (требуется `@login_required`)
4. Проверить наличие реакций в БД: `python check_reactions.py`

### Старые реакции всё ещё показываются
1. Очистить кэш браузера (Ctrl+Shift+Delete)
2. Hard reload (Ctrl+Shift+R)
3. Проверить что используется новый `chat-detail-enhanced.js`

### Ошибка "reactionsConfig is not defined"
1. Проверить импорт в `chat-detail-enhanced.js`:
   ```javascript
   import reactionsConfig from './config/reactionsConfig.js';
   ```
2. Проверить что файл существует: `static/js/config/reactionsConfig.js`

## Производительность

- **Запросов к БД:** 1 на загрузку страницы чата
- **Кэш frontend:** Да (весь сеанс)
- **Кэш backend:** Можно добавить Redis (будущее)
- **Размер ответа:** ~200-500 байт (8 реакций)
- **Время загрузки:** <50ms

## Тестирование

```bash
# Проверка БД
python check_reactions.py

# Проверка API (через curl, нужна авторизация)
curl -X GET http://localhost:9000/api/v1/communications/reactions/available/ \
     -H "Cookie: sessionid=YOUR_SESSION"

# Проверка frontend (открыть консоль браузера)
# Должны увидеть:
# [ReactionsConfig] ✓ Loaded reactions from API: [...]
```

## Команды управления

```bash
# Инициализация дефолтных реакций
python manage.py init_reactions

# Проверка состояния
python check_reactions.py

# Сброс порядка (будущее)
python manage.py reset_reaction_order

# Импорт из JSON (будущее)
python manage.py import_reactions reactions.json
```
