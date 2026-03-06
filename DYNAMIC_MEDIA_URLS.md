# Динамическая генерация ссылок на медиа

## Проблема
При работе с несколькими доменами (локальный и глобальный) статические ссылки на медиа-файлы работали только для одного домена.

## Решение
Реализовали динамическую генерацию ссылок на медиа на основе текущего домена запроса.

## Что изменилось

### 1. Context Processor
**Файл:** `backend/core/context_processors.py`

Добавлен context processor `media_domain()`, который:
- Определяет текущий домен из запроса (`request.get_host()`)
- Формирует динамический `MEDIA_URL_DYNAMIC` с учётом протокола и домена
- Добавляет переменные в контекст всех шаблонов:
  - `MEDIA_URL_DYNAMIC` — полный URL для медиа (например: `http://localhost:9000/media/` или `https://example.com/media/`)
  - `CURRENT_DOMAIN` — текущий домен
  - `CURRENT_SCHEME` — протокол (http/https)

### 2. Настройки Django
**Файл:** `backend/eusrr_backend/settings.py`

Добавлен context processor в `TEMPLATES`:
```python
"context_processors": [
    # ...
    "core.context_processors.media_domain",
],
```

### 3. Обновлённые шаблоны
Все шаблоны обновлены для использования динамических ссылок:

#### `backend/templates/feed/_feed_cards.html`
- Изображения постов
- Аватары авторов
- Добавлен `loading="lazy"` и `decoding="async"` для оптимизации

#### `backend/templates/feed/feed_list.html`
- Аватары новых сотрудников

#### `backend/templates/feed/post_detail.html`
- Изображения постов в детальном виде
- Аватары авторов

## Логика обработки URL

Шаблоны проверяют формат URL и обрабатывают его соответственно:

```django
{% if img_url|slice:":7" == "/media/" %}
  {# Относительный путь /media/... → добавляем домен #}
  <img src="{{ MEDIA_URL_DYNAMIC }}{{ img_url|slice:"7:" }}" alt="...">
{% elif img_url|slice:":1" == "/" %}
  {# Абсолютный путь /... → добавляем схему и домен #}
  <img src="{{ request.scheme }}://{{ request.get_host }}{{ img_url }}" alt="...">
{% else %}
  {# Уже полный URL или внешняя ссылка → используем как есть #}
  <img src="{{ img_url }}" alt="...">
{% endif %}
```

## Примеры работы

### Локальный домен (localhost:9000)
```
Запрос: http://localhost:9000/feed/
MEDIA_URL_DYNAMIC: http://localhost:9000/media/

Файл: /media/feed/images/photo.jpg
Результат: http://localhost:9000/media/feed/images/photo.jpg
```

### Глобальный домен (example.com)
```
Запрос: https://example.com/feed/
MEDIA_URL_DYNAMIC: https://example.com/media/

Файл: /media/feed/images/photo.jpg
Результат: https://example.com/media/feed/images/photo.jpg
```

## Преимущества

✅ **Автоматическая адаптация** — один код работает на всех доменах
✅ **Без перезапуска** — не нужно менять настройки при переключении доменов
✅ **SEO-дружественные URL** — правильные абсолютные ссылки
✅ **Поддержка HTTPS/HTTP** — автоматически определяется из запроса
✅ **Оптимизация загрузки** — добавлены атрибуты `loading="lazy"` и `decoding="async"`

## Дальнейшие улучшения

### Возможные оптимизации:
1. **CDN интеграция** — добавить отдельные CDN домены для статики
2. **Оптимизация изображений** — генерация thumbnails разных размеров
3. **WebP/AVIF форматы** — современные форматы для уменьшения размера
4. **Кэширование** — добавить Cache-Control заголовки
5. **Версионирование** — добавить версии к URL для инвалидации кэша

### Пример с CDN:
```python
def media_domain(request):
    host = request.get_host().split(':')[0]
    
    # Определяем CDN на основе домена
    if host in ['localhost', '127.0.0.1']:
        cdn_url = f"{request.scheme}://{request.get_host()}/media/"
    elif 'dev' in host:
        cdn_url = "https://cdn-dev.example.com/media/"
    else:
        cdn_url = "https://cdn.example.com/media/"
    
    return {'MEDIA_URL_DYNAMIC': cdn_url}
```

## Тестирование

Проверьте работу на обоих доменах:
1. Откройте ленту на `http://localhost:9000/feed/`
2. Откройте ленту на `https://your-domain.com/feed/`
3. Убедитесь, что изображения загружаются корректно в обоих случаях
4. Проверьте в DevTools, что URLs формируются правильно

## Откат изменений

Если нужно вернуться к старому поведению:
1. Удалить `core.context_processors.media_domain` из `settings.py`
2. В шаблонах заменить `{{ MEDIA_URL_DYNAMIC }}{{ img_url|slice:"7:" }}` на `{{ img_url }}`
