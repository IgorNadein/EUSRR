# Исправление проблемы кэширования сообщений

## Проблема

При отправке сообщения в чате, затем возврате к списку чатов (кнопка "К чатам") и повторном открытии того же чата - **отправленное сообщение исчезает**.

### Причина

Браузер агрессивно кэширует HTML страницы чатов. Когда вы:
1. Открываете чат → браузер получает HTML с N сообщениями
2. Отправляете сообщение через WebSocket → сообщение добавляется в DOM И сохраняется в БД
3. Возвращаетесь к списку чатов
4. Снова открываете тот же чат → **браузер возвращает закэшированный HTML** (без нового сообщения)

### Диагностика

Сообщение **правильно сохраняется в БД**:
```python
# communications/consumers.py
@database_sync_to_async
def _create_message(self, chat: Chat, user, text: str, reply_to_id=None) -> Message:
    msg = Message.objects.create(  # ✅ Создается в БД
        chat=chat,
        author=user,
        content=text[:2000],
        reply_to_id=reply_to_id
    )
    return msg
```

Но Django view возвращает полный HTML со всеми сообщениями из БД, а браузер его кэширует.

## Решение

Добавлены HTTP заголовки для **запрета кэширования** в двух view:

### 1. ChatDetailView (страница чата)

```python
class ChatDetailView(LoginRequiredMixin, DetailView, FormView):
    # ...
    
    def dispatch(self, request, *args, **kwargs):
        """Добавляем заголовки для отключения кэширования"""
        response = super().dispatch(request, *args, **kwargs)
        # Запрещаем кэширование страницы чата в браузере
        response['Cache-Control'] = (
            'no-cache, no-store, must-revalidate, max-age=0'
        )
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
```

### 2. ChatListView (список чатов)

```python
class ChatListView(LoginRequiredMixin, ListView):
    # ...
    
    def dispatch(self, request, *args, **kwargs):
        """Добавляем заголовки для отключения кэширования"""
        response = super().dispatch(request, *args, **kwargs)
        # Запрещаем кэширование списка чатов
        response['Cache-Control'] = (
            'no-cache, no-store, must-revalidate, max-age=0'
        )
        response['Pragma'] = 'no-cache'
        response['Expires'] = '0'
        return response
```

## HTTP заголовки

### Cache-Control: no-cache, no-store, must-revalidate, max-age=0

- **no-cache** - браузер должен проверить с сервером перед использованием кэша
- **no-store** - полностью запрещает сохранение в кэш
- **must-revalidate** - кэш должен быть проверен после истечения
- **max-age=0** - кэш истекает немедленно

### Pragma: no-cache

- Обратная совместимость с HTTP/1.0

### Expires: 0

- Дата истечения кэша (в прошлом)

## Результат

✅ **До**: Браузер кэшировал HTML чата → при повторном открытии показывал старую версию  
✅ **После**: Браузер запрашивает свежий HTML каждый раз → всегда показывает актуальные сообщения из БД

## Тестирование

### Сценарий 1: Отправка и проверка сообщения

1. Откройте любой чат
2. Отправьте сообщение "Тест 123"
3. Нажмите "К чатам"
4. Снова откройте тот же чат
5. ✅ Сообщение "Тест 123" должно быть видно

### Сценарий 2: Множественная отправка

1. Откройте чат
2. Отправьте 3 сообщения подряд
3. Закройте и откройте чат несколько раз
4. ✅ Все 3 сообщения должны оставаться видимыми

### Сценарий 3: Проверка в разных браузерах

- ✅ Chrome
- ✅ Firefox
- ✅ Edge
- ✅ Safari

### Проверка HTTP заголовков (DevTools)

Откройте DevTools → Network → выберите запрос к `/communications/chats/{id}/`

**Response Headers должны содержать:**
```
Cache-Control: no-cache, no-store, must-revalidate, max-age=0
Pragma: no-cache
Expires: 0
```

## Альтернативные решения (не использованы)

### 1. ❌ Инвалидация Django кэша при создании сообщения

```python
# В consumers.py после создания сообщения
from django.core.cache import cache
cache.delete(f'chat_detail_{chat.id}')
```

**Минус**: Нужно кэшировать view с `@cache_page`, что усложняет код

### 2. ❌ Версионирование URL с timestamp

```javascript
// При возврате к чату добавлять ?v=timestamp
location.href = `/communications/chats/${chatId}/?v=${Date.now()}`;
```

**Минус**: Загрязняет history браузера, не работает с back button

### 3. ❌ Service Worker для управления кэшем

```javascript
// Отлавливать запросы к /communications/chats/ и всегда делать network-first
self.addEventListener('fetch', event => {
  if (event.request.url.includes('/communications/chats/')) {
    event.respondWith(fetch(event.request));
  }
});
```

**Минус**: Требует регистрации Service Worker, сложнее в поддержке

### 4. ✅ HTTP заголовки Cache-Control (выбрано)

**Плюсы**:
- Простое решение
- Работает во всех браузерах
- Не требует изменений в JS
- Соответствует HTTP стандарту

## Влияние на производительность

### Потенциальные проблемы

❌ **Больше запросов к серверу** - каждое открытие чата = новый HTTP запрос  
❌ **Нет оффлайн режима** - без кэша страница не загрузится без интернета

### Оптимизация (если потребуется)

Можно использовать **частичное кэширование**:

```python
response['Cache-Control'] = 'max-age=10, must-revalidate'  # Кэш на 10 сек
```

Или **ETag** для условных запросов:

```python
from django.views.decorators.http import condition

@condition(etag_func=lambda r, *a, **k: f"chat-{kwargs['pk']}-{Chat.objects.get(pk=kwargs['pk']).updated_at.timestamp()}")
class ChatDetailView(...):
    ...
```

Но для текущей задачи полное отключение кэша - оптимальное решение.

## Связанные файлы

- `backend/communications/views.py` - добавлены методы `dispatch()` в ChatDetailView и ChatListView
- `backend/communications/consumers.py` - логика создания сообщений (не изменялась)

## Дата исправления

30 ноября 2025 г.

## Статус

✅ **Исправлено и протестировано**
