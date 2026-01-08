# Анализ функции "Уведомления" в контекстном меню чатов

**Дата проверки:** 8 января 2026 г.  
**Файл:** `templates/includes/components/chat_menu.html`  
**Элемент:** `<a data-action="notifications">`

---

## 🔍 Что найдено

### 1. HTML элемент (UI)

**Местоположение:** `backend/templates/includes/components/chat_menu.html:22`

```html
<a class="dropdown-item" href="#" data-action="notifications">
  <i class="bi-bell me-2"></i>Уведомления
</a>
```

**Используется в:**
- `templates/includes/components/chat_card.html` (строка 25)
- `templates/communications/chat_list.html` (6 раз - для каждого типа чатов)

**Статус:** ✅ Элемент есть, отображается в меню каждого чата

---

### 2. JavaScript обработчик

**Файл:** `backend/static/js/components/chatMenuActions.js`

**Функция:** `handleNotificationsAction()` (строка 110)

```javascript
function handleNotificationsAction(chatId, chatName) {
  showDevMessage('Функция настройки уведомлений находится в разработке', 'info');
  
  // TODO: Реализовать API endpoint для управления уведомлениями
  /*
  fetch(`/communications/api/chat/${chatId}/notifications/`, {
    method: 'POST',
    headers: {
      'Content-Type': 'application/json',
      'X-CSRFToken': getCsrfToken()
    },
    body: JSON.stringify({ enabled: false })
  })
  .then(response => response.json())
  .then(data => {
    if (data.ok) {
      console.log('Notifications updated');
    }
  });
  */
}
```

**Статус:** 🔴 **ЗАГЛУШКА!** Показывает toast уведомление "Функция настройки уведомлений находится в разработке"

**Что происходит при клике:**
1. Пользователь кликает на "Уведомления"
2. Dropdown меню закрывается
3. Показывается blue toast с иконкой info: "Функция настройки уведомлений находится в разработке"
4. Никакие API не вызываются
5. Никакие настройки не меняются

---

### 3. API Endpoint

**Ожидаемый URL:** `/api/v1/communications/chats/<chat_id>/notifications/`

**Статус:** ❌ **НЕ СУЩЕСТВУЕТ!**

Проверено в:
- ✅ `backend/api/v1/urls.py` - маршрута нет
- ✅ `backend/api/v1/communications/views.py` - функции нет

**Существующий похожий endpoint:**
```python
# Есть для закрепления (PIN):
path("communications/chats/<int:chat_id>/pin/", pin_chat, name="pin_chat")

# НЕТ для уведомлений:
# path("communications/chats/<int:chat_id>/notifications/", toggle_notifications, name="toggle_notifications")
```

---

### 4. Backend модель

**Модель:** `ChatUserSettings` в `communications/models.py:304`

```python
class ChatUserSettings(models.Model):
    """Персональные настройки пользователя для чата"""
    chat = models.ForeignKey(Chat, on_delete=models.CASCADE, related_name='user_settings')
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    
    # Закрепление
    is_pinned = models.BooleanField(default=False, verbose_name="Закреплен")
    pinned_at = models.DateTimeField(null=True, blank=True, verbose_name="Время закрепления")
    pin_order = models.IntegerField(default=0, verbose_name="Порядок закрепленных")
    
    # Уведомления ✅
    notifications_enabled = models.BooleanField(default=True, verbose_name="Уведомления")
    
    # Кастомное название (если пользователь переименовал)
    custom_name = models.CharField(max_length=255, blank=True, verbose_name="Свое название")
    
    # Скрыть чат
    is_hidden = models.BooleanField(default=False, verbose_name="Скрыт")
    
    class Meta:
        unique_together = [('chat', 'user')]
        ordering = ['-is_pinned', '-pinned_at']
```

**Статус:** ✅ **Поле `notifications_enabled` существует!**

---

### 5. Использование в сигналах

**Файл:** `backend/communications/notification_signals.py`

**Проблема:** ❌ **Поле `notifications_enabled` НЕ ПРОВЕРЯЕТСЯ!**

```python
@receiver(post_save, sender=Message)
def create_message_notifications(sender, instance, created, **kwargs):
    """Создает уведомления при создании нового сообщения"""
    if not created or instance.is_system or instance.is_deleted:
        return
    
    chat = instance.chat
    author = instance.author
    content = instance.content
    
    # Получаем всех участников чата кроме автора
    if chat.type in ['announcement', 'channel', 'department', 'global']:
        participants = chat.get_participants.exclude(id=author.id)
    else:
        participants = chat.participants.exclude(id=author.id)
    
    # ❌ ПРОБЛЕМА: Не проверяется ChatUserSettings.notifications_enabled!
    # Уведомления отправляются ВСЕМ участникам независимо от их настроек
    
    for recipient in recipients_for_new_message:
        NotificationService.create_notification(
            recipient=recipient,
            notification_type_code='chat_new_message',
            title=f'Новое сообщение от {author.get_full_name() or author.username}',
            message=truncate_message(content, 100),
            # ...
        )
```

**Должно быть:**
```python
for recipient in recipients_for_new_message:
    # Проверяем настройки уведомлений пользователя для этого чата
    chat_settings = ChatUserSettings.objects.filter(
        chat=chat,
        user=recipient
    ).first()
    
    # Пропускаем, если уведомления отключены
    if chat_settings and not chat_settings.notifications_enabled:
        continue
    
    NotificationService.create_notification(...)
```

---

## 📊 Сводная таблица статусов

| Компонент | Статус | Описание |
|-----------|--------|----------|
| **HTML элемент** | ✅ Есть | Кнопка "Уведомления" в меню чата |
| **JavaScript обработчик** | 🔴 Заглушка | Показывает toast "в разработке" |
| **API endpoint** | ❌ Нет | `/communications/chats/<id>/notifications/` не существует |
| **Backend функция** | ❌ Нет | `toggle_chat_notifications()` не реализована |
| **Модель ChatUserSettings** | ✅ Есть | Поле `notifications_enabled` существует |
| **Проверка в сигналах** | ❌ Нет | Настройки не проверяются при отправке |
| **Маршрут в urls.py** | ❌ Нет | Не зарегистрирован |

---

## ❌ Вердикт: ПОЛНОСТЬЮ НЕ РАБОТАЕТ

### Что реально происходит:

1. **При клике на "Уведомления":**
   - ✅ Меню закрывается
   - ✅ Показывается toast "Функция в разработке"
   - ❌ API не вызывается
   - ❌ Настройки не меняются
   - ❌ Ничего не сохраняется

2. **При отправке сообщения в чат:**
   - ✅ Сигнал срабатывает
   - ✅ Уведомления создаются
   - ❌ Настройка `notifications_enabled` **ИГНОРИРУЕТСЯ**
   - ❌ Уведомления приходят **ВСЕМ** независимо от настроек

3. **При попытке отключить уведомления:**
   - ❌ Функция не реализована
   - ❌ Изменить настройки невозможно (нет UI)
   - ❌ База данных не обновляется

---

## 🔧 Что нужно реализовать

### Шаг 1: Создать API endpoint

**Файл:** `backend/api/v1/communications/views.py`

Добавить функцию:

```python
@login_required
@require_POST
def toggle_chat_notifications(request, chat_id):
    """Включение/выключение уведомлений для чата"""
    import json
    
    chat = get_object_or_404(Chat, pk=chat_id)
    
    # Проверка доступа к чату
    if not user_can_access_chat(chat, request.user):
        return JsonResponse(
            {'ok': False, 'error': 'Access denied'}, 
            status=403
        )
    
    try:
        data = json.loads(request.body)
    except json.JSONDecodeError:
        return JsonResponse(
            {'ok': False, 'error': 'Invalid JSON'}, 
            status=400
        )
    
    enabled = data.get('enabled', True)
    
    settings, created = ChatUserSettings.objects.get_or_create(
        chat=chat,
        user=request.user
    )
    
    settings.notifications_enabled = enabled
    settings.save()
    
    return JsonResponse({
        'ok': True, 
        'enabled': enabled,
        'message': f'Уведомления {"включены" if enabled else "отключены"}'
    })
```

### Шаг 2: Добавить маршрут

**Файл:** `backend/api/v1/urls.py`

После строки с `pin_chat` добавить:

```python
path(
    "communications/chats/<int:chat_id>/notifications/",
    toggle_chat_notifications,
    name="toggle_chat_notifications"
),
```

### Шаг 3: Обновить JavaScript

**Файл:** `backend/static/js/components/chatMenuActions.js`

Заменить функцию `handleNotificationsAction`:

```javascript
async function handleNotificationsAction(chatId, chatName) {
  try {
    // Получаем текущее состояние (можно хранить в data-атрибуте)
    const chatRow = document.querySelector(`[data-chat-id="${chatId}"]`);
    const currentlyEnabled = chatRow?.dataset.notificationsEnabled !== 'false';
    
    // Переключаем состояние
    const newState = !currentlyEnabled;
    
    const response = await fetch(`/api/v1/communications/chats/${chatId}/notifications/`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'X-CSRFToken': getCsrfToken()
      },
      body: JSON.stringify({ enabled: newState })
    });
    
    const data = await response.json();
    
    if (data.ok) {
      // Обновляем data-атрибут
      if (chatRow) {
        chatRow.dataset.notificationsEnabled = newState.toString();
      }
      
      // Показываем toast с результатом
      showSuccessMessage(data.message || `Уведомления ${newState ? 'включены' : 'отключены'}`);
      
      // Можно добавить визуальный индикатор (иконка колокольчика с перечеркиванием)
      updateNotificationsIcon(chatRow, newState);
    } else {
      showErrorMessage(data.error || 'Ошибка при изменении настроек');
    }
  } catch (error) {
    console.error('Notifications toggle error:', error);
    showErrorMessage('Ошибка при изменении настроек уведомлений');
  }
}
```

### Шаг 4: Обновить сигналы

**Файл:** `backend/communications/notification_signals.py`

В функции `create_message_notifications` после получения списка участников добавить проверку:

```python
# Фильтруем получателей с учетом их настроек уведомлений
filtered_recipients = []
for recipient in recipients_for_new_message:
    # Проверяем настройки уведомлений для этого чата
    chat_settings = ChatUserSettings.objects.filter(
        chat=chat,
        user=recipient
    ).first()
    
    # Если настройки не найдены - по умолчанию уведомления включены
    # Если найдены - проверяем флаг
    if not chat_settings or chat_settings.notifications_enabled:
        filtered_recipients.append(recipient)

# Отправляем уведомления только отфильтрованным получателям
for recipient in filtered_recipients:
    NotificationService.create_notification(...)
```

### Шаг 5: Добавить индикатор в UI (опционально)

В `templates/includes/components/chat_card.html` добавить визуальный индикатор:

```html
<div class="chat-row" 
     data-chat-id="{{ chat.pk }}"
     data-notifications-enabled="{% if chat_settings.notifications_enabled %}true{% else %}false{% endif %}">
  
  {# ... существующий код ... #}
  
  {# Индикатор отключенных уведомлений #}
  {% if not chat_settings.notifications_enabled %}
    <i class="bi-bell-slash text-muted" title="Уведомления отключены"></i>
  {% endif %}
</div>
```

---

## 📝 Приоритет реализации

**Оценка работы:** 2-3 часа

**Сложность:** 🟡 Средняя

**Приоритет:** 🟡 Средний (не критично, но желательно)

**Зависимости:** Нет

**Блокирует:** Ничего

---

## ✅ Чек-лист реализации

- [ ] Создать функцию `toggle_chat_notifications()` в `views.py`
- [ ] Добавить маршрут в `urls.py`
- [ ] Импортировать функцию в начале `urls.py`
- [ ] Обновить JavaScript в `chatMenuActions.js`
- [ ] Добавить проверку в `notification_signals.py`
- [ ] Протестировать включение/выключение уведомлений
- [ ] Убедиться, что уведомления не приходят при отключенных настройках
- [ ] Добавить индикатор в UI (опционально)
- [ ] Создать миграцию если изменяли модель (не требуется)

---

## 🎯 Результат после реализации

После реализации пользователи смогут:

1. ✅ Кликнуть на "Уведомления" в меню чата
2. ✅ Увидеть toggle для включения/выключения
3. ✅ Сохранить свой выбор
4. ✅ Перестать получать уведомления от выбранного чата
5. ✅ Увидеть визуальный индикатор (иконка колокольчика)

**Уведомления будут приходить только от тех чатов, где они включены!**
