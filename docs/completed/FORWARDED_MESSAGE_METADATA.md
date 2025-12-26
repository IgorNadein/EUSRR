# Отображение метаданных пересланных сообщений

## Запрос пользователя

"При пересылке сообщений как-то можно смотреть кто отправитель и во сколько сообщение было отправлено в оригинальном чате?"

## Проблема

При пересылке сообщений в текущей реализации отображалось только:
- ✅ Автор оригинального сообщения (`forwarded_from_author`)
- ✅ ID оригинального сообщения (`forwarded_from_message_id`)

**НЕ отображалось:**
- ❌ Дата и время оригинального сообщения
- ❌ Название чата, из которого переслано сообщение

## Решение

Добавлены новые поля в модель `Message` и обновлен UI для отображения полной информации о пересылке.

### 1. Новые поля модели (backend/communications/models.py)

```python
class Message(models.Model):
    # ... существующие поля
    
    # Флаги для специальных типов сообщений
    is_forwarded = models.BooleanField(default=False)
    forwarded_from_message_id = models.IntegerField(...)
    forwarded_from_author = models.ForeignKey(...)
    
    # 🆕 Новые поля
    forwarded_from_created_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Дата создания исходного сообщения при пересылке"
    )
    forwarded_from_chat_name = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="Название исходного чата при пересылке"
    )
```

### 2. Обновлена логика пересылки (backend/api/v1/communications/views.py)

```python
def forward_messages(request):
    # ...
    for original_msg in messages:
        # Получаем название исходного чата
        source_chat_name = original_msg.chat.name or "Чат"
        if original_msg.chat.type == "private":
            # Для личных чатов показываем "от кого"
            other_user = original_msg.chat.get_other_user(request.user)
            if other_user:
                source_chat_name = (
                    other_user.get_full_name() or
                    other_user.username
                )
        
        # Создаем переслаанное сообщение с метаданными
        forwarded_msg = Message.objects.create(
            chat=target_chat,
            author=request.user,
            content=forwarded_content,
            is_forwarded=True,
            forwarded_from_message_id=original_msg.id,
            forwarded_from_author=original_msg.author,
            forwarded_from_created_at=original_msg.created_at,  # 🆕
            forwarded_from_chat_name=source_chat_name,          # 🆕
        )
```

### 3. Обновлена сериализация WebSocket (backend/communications/consumers.py)

```python
def serialize_message(m: Message) -> dict:
    # ...
    
    # Информация о пересылке
    if m.is_forwarded and m.forwarded_from_author:
        forwarded_data = {
            "author_id": m.forwarded_from_author.id,
            "author_name": (
                m.forwarded_from_author.get_full_name()
                or m.forwarded_from_author.username
            ),
            "message_id": m.forwarded_from_message_id,
        }
        
        # 🆕 Добавляем дату оригинального сообщения
        if m.forwarded_from_created_at:
            forwarded_data["created_at"] = (
                m.forwarded_from_created_at.strftime("%d.%m.%Y %H:%M")
            )
            forwarded_data["created_ts"] = int(
                m.forwarded_from_created_at.timestamp() * 1000
            )
        
        # 🆕 Добавляем название исходного чата
        if m.forwarded_from_chat_name:
            forwarded_data["chat_name"] = m.forwarded_from_chat_name
        
        data["forwarded_from"] = forwarded_data
```

### 4. Обновлен UI шаблон (backend/static/js/components/chatMessageTemplates.js)

```javascript
export function createMessageElement(msg, options = {}) {
  // ...
  
  // 🆕 Формирование информации о пересылке
  let forwardedHTML = '';
  if (msg.is_forwarded && msg.forwarded_from) {
    const fwd = msg.forwarded_from;
    const fwdAuthor = esc(fwd.author_name || 'Неизвестный');
    const fwdTime = fwd.created_at ? fwd.created_at : '';
    const fwdChat = fwd.chat_name ? ` из «${esc(fwd.chat_name)}»` : '';
    
    forwardedHTML = `
      <div class="forwarded-indicator small text-secondary mb-2 d-flex align-items-center">
        <i class="bi-arrow-90deg-right me-2"></i>
        <div>
          <div>Переслано от <strong>${fwdAuthor}</strong>${fwdChat}</div>
          ${fwdTime ? `<div class="small opacity-75">${fwdTime}</div>` : ''}
        </div>
      </div>`;
  }
  
  const bubble = `
    <div class="...">
      <div class="mt-1 bubble ...">
        ${forwardedHTML}  <!-- 🆕 Отображается вверху сообщения -->
        ${text ? text : ''}
        ${attachmentsHTML}
      </div>
    </div>`;
}
```

### 5. Добавлены стили (backend/static/css/components/chat-detail.css)

```css
/* Индикатор пересланного сообщения */
.forwarded-indicator {
  padding: 8px 10px;
  border-left: 3px solid currentColor;
  opacity: 0.7;
  background: rgba(0, 0, 0, 0.05);
  border-radius: 6px;
}

.bubble-me .forwarded-indicator {
  background: rgba(255, 255, 255, 0.1);
  border-left-color: rgba(255, 255, 255, 0.6);
}

/* Темная тема */
[data-bs-theme="dark"] .forwarded-indicator {
  background: rgba(255, 255, 255, 0.05);
}

[data-bs-theme="dark"] .bubble-me .forwarded-indicator {
  background: rgba(255, 255, 255, 0.08);
}
```

## Визуальное представление

### До:
```
┌─────────────────────────────────────┐
│ Иван Петров · 15:30                 │
│ ┌─────────────────────────────────┐ │
│ │ Привет! Как дела?               │ │
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

### После (переслано из другого чата):
```
┌─────────────────────────────────────┐
│ Вы · 16:45                          │
│ ┌─────────────────────────────────┐ │
│ │ ↱ Переслано от Мария Иванова    │ │ 🆕
│ │   из «Техподдержка»              │ │ 🆕
│ │   25.11.2025 14:20               │ │ 🆕
│ │                                  │ │
│ │ Привет! Как дела?                │ │
│ └─────────────────────────────────┘ │
└─────────────────────────────────────┘
```

## Примеры отображения

### 1. Пересылка из группового чата
```
↱ Переслано от Алексей Сидоров
  из «Разработка»
  30.11.2025 10:15
```

### 2. Пересылка из личного чата
```
↱ Переслано от Елена Смирнова
  из «Елена Смирнова»
  29.11.2025 18:45
```

### 3. Пересылка из объявления
```
↱ Переслано от HR Отдел
  из «Важные новости»
  28.11.2025 09:00
```

### 4. Старые пересланные сообщения (без новых полей)
```
↱ Переслано от Дмитрий Козлов
```
(без даты и чата - для совместимости со старыми данными)

## Миграция базы данных

```bash
# Создание миграции
python manage.py makemigrations communications --name add_forwarded_metadata

# Применение миграции
python manage.py migrate communications
```

### Результат миграции:
```sql
ALTER TABLE communications_message 
ADD COLUMN forwarded_from_created_at DATETIME NULL;

ALTER TABLE communications_message 
ADD COLUMN forwarded_from_chat_name VARCHAR(255) NULL;
```

## Совместимость

### Обратная совместимость

✅ **Старые пересланные сообщения** (созданные до обновления):
- Отображаются БЕЗ даты и названия чата
- Показывается только автор: "Переслано от {имя}"

✅ **Новые пересланные сообщения** (после обновления):
- Отображаются СО всеми метаданными
- Показывается: автор, дата/время, чат

### Получение названия чата

**Групповые/Департаменты/Каналы:**
```python
source_chat_name = original_msg.chat.name or "Чат"
# Результат: "Разработка", "HR отдел", etc.
```

**Личные чаты:**
```python
other_user = original_msg.chat.get_other_user(request.user)
source_chat_name = other_user.get_full_name() or other_user.username
# Результат: "Иван Петров", "ivanov"
```

**Объявления:**
```python
source_chat_name = original_msg.chat.name  # Название объявления
# Результат: "Важные новости", "Обновление системы"
```

## Тестирование

### Сценарий 1: Пересылка из группового чата

1. Откройте групповой чат "Разработка"
2. Найдите сообщение от "Алексей Сидоров" (30.11.2025 10:15)
3. Выделите сообщение (ПКМ → Переслать)
4. Выберите целевой чат
5. ✅ В целевом чате должно отображаться:
   ```
   ↱ Переслано от Алексей Сидоров
     из «Разработка»
     30.11.2025 10:15
   ```

### Сценарий 2: Пересылка из личного чата

1. Откройте личный чат с "Елена Смирнова"
2. Выделите сообщение
3. Перешлите в групповой чат
4. ✅ Должно показать:
   ```
   ↱ Переслано от Елена Смирнова
     из «Елена Смирнова»
     [дата и время]
   ```

### Сценарий 3: Множественная пересылка

1. Выделите 3 сообщения
2. Перешлите их в другой чат
3. ✅ Все 3 сообщения должны иметь:
   - Индикатор пересылки
   - Оригинального автора
   - Дату оригинала
   - Название исходного чата

### Сценарий 4: Старые пересланные сообщения

1. Найдите старое переслаанное сообщение (до обновления)
2. ✅ Должно отображаться только:
   ```
   ↱ Переслано от [автор]
   ```
   (без даты и чата)

### Сценарий 5: Темная тема

1. Переключите тему на темную
2. Откройте чат с пересланными сообщениями
3. ✅ Проверьте контрастность и читаемость:
   - Фон индикатора должен быть видимым
   - Текст должен быть читаемым
   - Граница слева должна быть заметной

## Технические детали

### Размер данных

**forwarded_from_created_at:**
- Тип: `DATETIME`
- Размер: 8 байт
- Nullable: `TRUE`

**forwarded_from_chat_name:**
- Тип: `VARCHAR(255)`
- Размер: до 255 символов
- Nullable: `TRUE`

### Производительность

**Impact:** Минимальный
- Добавлены 2 nullable поля (не влияет на существующие строки)
- Нет индексов (не нужны для этих полей)
- Нет JOIN запросов (данные денормализованы для скорости)

### Денормализация данных

**Почему сохраняем `chat_name` а не `chat_id`?**
- ✅ Быстрее (не нужен JOIN)
- ✅ Надежнее (чат может быть удален)
- ✅ Историчность (название могло измениться)

**Почему сохраняем `created_at` а не ссылку на сообщение?**
- ✅ Историчность (оригинальное сообщение может быть удалено)
- ✅ Производительность (не нужен запрос к другой таблице)

## Связанные файлы

1. **backend/communications/models.py** - модель Message
2. **backend/api/v1/communications/views.py** - forward_messages view
3. **backend/communications/consumers.py** - serialize_message функция
4. **backend/static/js/components/chatMessageTemplates.js** - createMessageElement
5. **backend/static/css/components/chat-detail.css** - .forwarded-indicator стили
6. **backend/communications/migrations/0018_add_forwarded_metadata.py** - миграция

## Дата реализации

30 ноября 2025 г.

## Статус

✅ **Реализовано и готово к тестированию**
