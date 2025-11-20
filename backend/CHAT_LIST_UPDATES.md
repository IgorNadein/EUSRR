# Обновления списка чатов и модала создания

## Дата: 2024
## Статус: Завершено

---

## Обзор изменений

Список чатов (`chat_list.html`) и модал создания чатов обновлены для поддержки нового функционала мессенджера со всеми 6 типами чатов.

---

## 1. Обновленный шаблон `chat_list.html`

### 1.1. Добавлены новые стили
```django
{% block extra_css %}
  ...
  <link rel="stylesheet" href="{% static 'css/components/chat-list-enhanced.css' %}">
{% endblock %}
```

### 1.2. Добавлена секция "Закрепленные чаты"
```django
<div class="feed-card chat-section mb-3" data-sec="pinned" id="pinnedSection" style="display:none;">
  <div class="feed-hd">
    <div class="feed-ava" style="width:44px;height:44px;">
      <i class="bi-pin-angle-fill text-warning"></i>
    </div>
    <div class="feed-meta flex-grow-1">
      <h6 class="mb-0 text-secondary">Закрепленные</h6>
    </div>
  </div>
  <div id="sec-pinned" class="list-chats"></div>
</div>
```
- Изначально скрыта (`display:none`)
- Будет заполняться JavaScript'ом через `chat-list-enhanced.js`
- Закрепленные чаты отображаются первыми

### 1.3. Обновлены существующие секции
**Глобальный чат:**
- ✅ Добавлен условный вывод аватара: `{% if chat.avatar %}<img>{% else %}<i>{% endif %}`
- ✅ Использование `chat.name|default:"Глобальный чат"`

**Отделы:**
- ✅ Аватар чата (если задан)
- ✅ Отображение `chat.name` для департаментов

**Личные чаты:**
- ✅ Аватар собеседника
- ✅ Корректная структура с `position-relative` для `stretched-link`

### 1.4. Добавлены новые секции

#### Группы (`data-sec="group"`)
- Иконка: `bi-people-fill`
- Отображает чаты с `chat.type == 'group'`
- Поддержка аватара группы
- Показывает название группы, количество сообщений, последнее сообщение

#### Каналы (`data-sec="channel"`)
- Иконка: `bi-broadcast`
- Отображает чаты с `chat.type == 'channel'`
- Поддержка аватара канала
- Показывает название, описание, метрики

#### Объявления (`data-sec="announcement"`)
- Иконка: `bi-megaphone`
- Отображает чаты с `chat.type == 'announcement'`
- Поддержка аватара
- Показывает название, описание, метрики

### 1.5. Все секции имеют:
- `data-chat-id="{{ chat.pk }}"` - ID чата для WebSocket
- `data-type="..."` - тип чата для фильтрации
- `data-last-ts="..."` - timestamp последнего сообщения для сортировки
- `data-haystack="..."` - текст для поиска
- `data-unread` - бейдж непрочитанных сообщений (скрывается если 0)
- Атрибуты для последнего сообщения: `data-last-time`, `data-last-author`, `data-last-preview`

---

## 2. Обновленный модал создания чатов

### 2.1. Селектор типа чата
```html
<select class="form-select" id="chatTypeSelect">
  <option value="private">Личный чат</option>
  <option value="group">Группа</option>
  <option value="channel">Канал</option>
  <option value="announcement">Объявления</option>
</select>
```

### 2.2. Поля для группы/канала/объявлений
```html
<div id="groupFieldsSection" style="display:none;">
  <div class="mb-3">
    <label for="chatNameInput" class="form-label">Название чата <span class="text-danger">*</span></label>
    <input type="text" class="form-control" id="chatNameInput" placeholder="Введите название">
  </div>
  <div class="mb-3">
    <label for="chatDescInput" class="form-label">Описание</label>
    <textarea class="form-control" id="chatDescInput" rows="3" placeholder="Краткое описание чата"></textarea>
  </div>
</div>
```
- Отображаются только для `group`, `channel`, `announcement`
- Скрыты для `private`

### 2.3. Секция выбора участников
```html
<div id="recipientSection">
  <label class="form-label">Выберите участников</label>
  <div id="chatRecipients" class="recipient-picker" data-api-employees="...">
    ...
  </div>
</div>
```
- Для `private`: maxSelections = 1 (один собеседник)
- Для `group`: maxSelections = 100 (множественный выбор)
- Для `channel`/`announcement`: скрыта (участники опциональны)

### 2.4. Логика создания (JavaScript)

**Переключение типа чата:**
```javascript
chatTypeSelect.addEventListener('change', function() {
  const type = this.value;
  
  if(type === 'private') {
    recipientSection.style.display = 'block';
    groupFieldsSection.style.display = 'none';
    chatPicker.setMaxSelections(1);
  } else if(type === 'group') {
    recipientSection.style.display = 'block';
    groupFieldsSection.style.display = 'block';
    chatPicker.setMaxSelections(100);
  } else {
    // channel, announcement
    recipientSection.style.display = 'none';
    groupFieldsSection.style.display = 'block';
  }
});
```

**Создание чата:**
```javascript
if(type === 'private') {
  // Используем старый endpoint для личных чатов
  window.location.href = `/communications/start_private_chat/${employeeId}/`;
} else {
  // Используем новый API для остальных типов
  const res = await fetch('/communications/api/chat/create/', {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': csrftoken
    },
    body: JSON.stringify({
      type: type,
      name: name,
      description: description,
      participant_ids: participant_ids  // Только для группы
    })
  });
}
```

---

## 3. Обновленные фильтры (`_filters.html`)

```html
<select name="chat_type" class="form-select" id="chatTypeFilter">
  <option value="all" selected>Все</option>
  <option value="pinned">Закрепленные</option>
  <option value="global">Глобальный</option>
  <option value="department">Отделы</option>
  <option value="private">Личные</option>
  <option value="group">Группы</option>
  <option value="channel">Каналы</option>
  <option value="announcement">Объявления</option>
</select>
```

**Логика фильтрации:**
```javascript
function applyTypeFilter() {
  const selectedType = chatTypeFilter?.value || 'all';
  const sections = document.querySelectorAll('.chat-section');
  
  sections.forEach(section => {
    const sectionType = section.dataset.sec;
    if (selectedType === 'all' || selectedType === sectionType) {
      section.style.display = '';
    } else {
      section.style.display = 'none';
    }
  });
}
```

---

## 4. Обновления RecipientPicker

### 4.1. Добавлена поддержка `maxSelections`
```javascript
constructor(root, options) {
  ...
  this.maxSelections = options.maxSelections || null; // null = без ограничений
  ...
}
```

### 4.2. Проверка лимита при выборе
```javascript
if (checkbox.checked) {
  if (this.maxSelections && this.selected.size >= this.maxSelections) {
    checkbox.checked = false;
    alert(`Можно выбрать не более ${this.maxSelections} получателей`);
    return;
  }
  this.selected.set(id, payload);
}
```

### 4.3. Новые методы

**`getSelected()`** - получить выбранных с полными данными:
```javascript
getSelected() {
  return Array.from(this.selected.values());
}
```

**`setMaxSelections(max)`** - изменить лимит динамически:
```javascript
setMaxSelections(max) {
  this.maxSelections = max;
  // Если превышен лимит, сбрасываем лишние выборы
  if (max && this.selected.size > max) {
    const toKeep = Array.from(this.selected.entries()).slice(0, max);
    this.selected.clear();
    toKeep.forEach(([id, data]) => this.selected.set(id, data));
    this._renderSelected();
    this.elResults.querySelectorAll('input[type=checkbox][data-id]').forEach(checkbox => {
      const id = Number(checkbox.dataset.id);
      checkbox.checked = this.selected.has(id);
    });
  }
}
```

---

## 5. Подключение chat-list-enhanced.js

```html
<script src="{% static 'js/chat-list-enhanced.js' %}"></script>
```

**Что делает `chat-list-enhanced.js`:**
- ✅ WebSocket подключение для реального времени
- ✅ Обновление последних сообщений в списке
- ✅ Перемещение чатов в секцию "Закрепленные"
- ✅ Контекстное меню (правый клик): закрепить, уведомления, скрыть, прочитать
- ✅ Индикаторы печати в списке
- ✅ API вызов `togglePinChat()` для закрепления
- ✅ Анимации обновления чатов

---

## 6. Структура данных чата в шаблоне

### Доступные атрибуты:
```django
chat.pk                    # ID чата
chat.type                  # 'private', 'group', 'department', 'channel', 'announcement', 'global'
chat.name                  # Название (для всех кроме private)
chat.description           # Описание
chat.avatar                # ImageField (опционально)
chat.participants.all      # QuerySet участников (для private)
chat.department            # ForeignKey (для department)
chat.messages.count        # Количество сообщений
chat.unread_count          # Непрочитанные (вычисляется во view)
chat.last_message.0        # Последнее сообщение (вычисляется)
  .created_at
  .author
  .content
```

---

## 7. Тестирование

### Чек-лист для проверки:
- [ ] Отображение всех 6 секций чатов (закрепленные, глобальный, отделы, личные, группы, каналы, объявления)
- [ ] Аватары показываются корректно
- [ ] Фильтр по типу чата работает
- [ ] Поиск находит чаты по названию/участникам
- [ ] Модал создания:
  - [ ] Переключение типа чата меняет отображаемые поля
  - [ ] Для личного чата: выбор 1 собеседника → редирект на `/start_private_chat/`
  - [ ] Для группы: выбор участников, название, описание → POST `/api/chat/create/`
  - [ ] Для канала/объявлений: только название, описание → POST `/api/chat/create/`
- [ ] RecipientPicker:
  - [ ] Ограничение выбора работает (1 для private, 100 для group)
  - [ ] `getSelected()` возвращает массив объектов
  - [ ] `setMaxSelections()` корректно обрезает выбор
- [ ] WebSocket обновления (`chat-list-enhanced.js`):
  - [ ] Последние сообщения обновляются в реальном времени
  - [ ] Закрепление чата работает
  - [ ] Контекстное меню открывается
  - [ ] Индикаторы печати отображаются

---

## 8. Следующие шаги

1. **Обновить `chat_detail.html`:**
   - Подключить `chat-detail-enhanced.js`
   - Добавить UI для реакций, ответов, пересылки
   - Добавить редактирование/удаление сообщений
   - Добавить быстрые реакции на hover

2. **Создать view для API `/api/chat/create/`:**
   - Проверить, что endpoint существует в `api_views.py`
   - Убедиться в правильной авторизации
   - Добавить создание ChatMembership с ролью 'owner' для создателя

3. **Тестирование интеграции:**
   - Создание чатов всех типов
   - Отправка сообщений
   - Real-time обновления через WebSocket

4. **Оптимизация:**
   - Добавить пагинацию для больших списков чатов
   - Кеширование аватаров
   - Lazy loading для секций

---

## 9. API Endpoints используемые в шаблоне

### Существующие:
- `POST /communications/start_private_chat/<user_id>/` - создание личного чата (старый endpoint)
- `GET /api/v1/employees/` - список сотрудников для RecipientPicker

### Новые (из api_views.py):
- `POST /communications/api/chat/create/` - создание group/channel/announcement
  ```json
  {
    "type": "group",
    "name": "Название группы",
    "description": "Описание",
    "participant_ids": [1, 2, 3]
  }
  ```
  
- `POST /communications/api/chat/<chat_id>/pin/` - закрепление чата
  ```json
  {
    "pinned": true
  }
  ```

---

## 10. Известные ограничения

1. **Глобальный чат:** может быть только один, создается вручную через админку
2. **Департаментные чаты:** привязаны к `Department`, создаются автоматически
3. **Аватары:** размер файла ограничен настройками Django `FILE_UPLOAD_MAX_MEMORY_SIZE`
4. **RecipientPicker:** поддерживает только сотрудников из `/api/v1/employees/`, не внешних пользователей

---

## Заключение

Шаблон `chat_list.html` и модал создания теперь полностью поддерживают:
- ✅ 6 типов чатов (private, group, department, channel, announcement, global)
- ✅ Закрепленные чаты
- ✅ Аватары чатов
- ✅ Гибкое создание с разными полями в зависимости от типа
- ✅ Фильтрация и поиск
- ✅ Подготовку для real-time обновлений через WebSocket

Следующий шаг - обновление `chat_detail.html` для отображения расширенных возможностей сообщений.
