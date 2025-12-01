# Реализация голосований (Polls) в мессенджере

## Обзор

Добавлена полная система голосований в мессенджер EUSRR, реализованная по примеру современных мессенджеров (Telegram, WhatsApp).

## Возможности

### Типы голосований:
1. **Обычное голосование** - выбор одного варианта
2. **Множественный выбор** - выбор нескольких вариантов
3. **Анонимное голосование** - не показывается кто голосовал
4. **Викторина** - с правильным ответом, который показывается после голосования

### Функции:
- Создание голосования с 2-10 вариантами ответа
- Визуализация результатов в реальном времени (прогресс-бары)
- Автоматическое закрытие голосования по времени
- Отображение количества проголосовавших
- Изменение голоса (можно переголосовать)
- Real-time обновление через WebSocket

## Структура базы данных

### Модели (backend/communications/models.py)

#### Poll
```python
- message: OneToOne -> Message (связь с сообщением)
- author: FK -> User (создатель)
- question: CharField (вопрос)
- is_anonymous: Boolean (анонимность)
- is_multiple_choice: Boolean (множественный выбор)
- is_quiz: Boolean (викторина)
- allows_custom_answers: Boolean (свои варианты)
- is_closed: Boolean (закрыто)
- closed_at: DateTime (время закрытия)
- closes_at: DateTime (автозакрытие)
- total_voters: Integer (количество проголосовавших)
```

#### PollOption
```python
- poll: FK -> Poll
- text: CharField (текст варианта)
- position: Integer (порядок)
- vote_count: Integer (количество голосов)
- is_correct: Boolean (правильный для викторин)
```

#### PollVote
```python
- poll: FK -> Poll
- option: FK -> PollOption
- voter: FK -> User
- voted_at: DateTime
UniqueConstraint: poll + voter + option
```

## API Endpoints

### 1. Создать голосование
```http
POST /api/v1/communications/polls/create/

Body:
{
  "chat_id": 1,
  "question": "Какой язык программирования лучше?",
  "options": ["Python", "JavaScript", "Go", "Rust"],
  "is_anonymous": false,
  "is_multiple_choice": false,
  "is_quiz": false,
  "correct_option_index": null,  // для викторин
  "closes_in_minutes": 60  // опционально
}

Response:
{
  "success": true,
  "poll_id": 123,
  "message_id": 456
}
```

### 2. Проголосовать
```http
POST /api/v1/communications/polls/{poll_id}/vote/

Body:
{
  "poll_id": 123,
  "option_ids": [1]  // или [1, 2] для множественного
}

Response:
{
  "success": true,
  "results": {
    "question": "...",
    "total_voters": 10,
    "is_closed": false,
    "options": [...]
  }
}
```

### 3. Закрыть голосование
```http
POST /api/v1/communications/polls/{poll_id}/close/

Body:
{
  "poll_id": 123
}

Response:
{
  "success": true
}
```

### 4. Получить результаты
```http
GET /api/v1/communications/polls/{poll_id}/results/

Response:
{
  "question": "...",
  "total_voters": 10,
  "is_closed": false,
  "is_anonymous": false,
  "is_multiple_choice": false,
  "is_quiz": false,
  "user_voted_option_ids": [1],
  "options": [
    {
      "id": 1,
      "text": "Python",
      "vote_count": 5,
      "percentage": 50.0,
      "is_correct": false,
      "voters": [...]  // если не анонимное
    }
  ]
}
```

## Frontend компоненты

### JavaScript модуль (chatPoll.js)
```javascript
import ChatPoll from './components/chatPoll.js';

// Инициализация
const chatPoll = new ChatPoll({
    chatId: 1
});

// Создание голосования через модальное окно
// (автоматически привязано к кнопке "Создать голосование")

// Голосование
await chatPoll.vote(pollId, [optionId]);

// Закрытие
await chatPoll.closePoll(pollId);

// Рендер HTML
const html = ChatPoll.renderPoll(pollData, userVotedOptionIds);
```

### CSS стили (chat-polls.css)
- `.poll-widget` - контейнер голосования
- `.poll-question` - вопрос
- `.poll-option` - вариант ответа
- `.poll-option.voted` - выбранный вариант
- `.poll-option-result` - результат с прогресс-баром
- `.poll-footer` - подвал с информацией

## UI/UX

### Меню вложений
В меню прикрепления файлов (bi-paperclip) добавлен пункт:
```html
<li>
  <a class="dropdown-item" href="#" id="createPoll">
    <i class="bi-bar-chart text-warning me-2"></i>
    Создать голосование
  </a>
</li>
```

### Модальное окно создания
- Поле ввода вопроса (до 500 символов)
- Динамический список вариантов (2-10)
- Кнопки добавления/удаления вариантов
- Чекбоксы настроек (анонимность, множественный выбор, викторина)
- Выбор правильного ответа (для викторин)
- Таймер автозакрытия (опционально)

### Отображение голосования в сообщении
**До голосования:**
- Вопрос (жирным)
- Кнопки с вариантами ответа
- Информация о настройках

**После голосования:**
- Вопрос
- Прогресс-бары с процентами
- Галочка на выбранном варианте
- Список проголосовавших (если не анонимное)
- Кнопка "Отменить голос" (если не закрыто)

## WebSocket интеграция

### Отправка нового голосования
```python
channel_layer.group_send(f'chat_{chat_id}', {
    'type': 'chat_message',
    'message': {
        'id': message.id,
        'content': '📊 Вопрос',
        'poll': {
            'id': poll.id,
            'question': '...',
            'options': [...]
        }
    }
})
```

### Обновление результатов
```python
channel_layer.group_send(f'chat_{chat_id}', {
    'type': 'poll_update',
    'poll_id': poll.id,
    'message_id': message.id,
    'results': poll.get_results()
})
```

## Миграция

```bash
cd backend
python manage.py migrate communications
```

Миграция `0019_add_polls.py` создаст:
- Таблицу `communications_poll`
- Таблицу `communications_polloption`
- Таблицу `communications_pollvote`
- Индексы для производительности
- Констрейнт уникальности голоса

## Админка Django

Зарегистрированы модели:
- `PollAdmin` - управление голосованиями
- `PollOptionAdmin` - управление вариантами
- `PollVoteAdmin` - просмотр голосов

Доступно:
- Просмотр всех голосований с фильтрами
- Inline редактирование вариантов
- Просмотр списка проголосовавших
- Ручное закрытие голосований

## Следующие шаги (опционально)

1. **Добавить поддержку пользовательских вариантов**
   - Пользователи могут добавлять свои варианты
   - Модерация новых вариантов

2. **Уведомления**
   - Уведомление о новом голосовании
   - Уведомление о закрытии голосования
   - Напоминание проголосовать

3. **Статистика**
   - Экспорт результатов в CSV/Excel
   - Визуализация (графики, диаграммы)
   - История голосований

4. **Расширенные настройки**
   - Ограничение по ролям (кто может создавать)
   - Видимость результатов до закрытия
   - Комментарии к вариантам

## Тестирование

### Ручное тестирование:
1. Открыть чат
2. Нажать на скрепку → "Создать голосование"
3. Заполнить форму, добавить варианты
4. Отправить
5. Проголосовать в другом браузере/инкогнито
6. Проверить обновление результатов в реальном времени

### Тестовые сценарии:
- [ ] Создание обычного голосования
- [ ] Создание анонимного голосования
- [ ] Создание с множественным выбором
- [ ] Создание викторины
- [ ] Голосование в открытом голосовании
- [ ] Изменение голоса
- [ ] Закрытие голосования (автором)
- [ ] Автозакрытие по времени
- [ ] Real-time обновление для других пользователей
- [ ] Отображение в мобильной версии

## Troubleshooting

### Голосование не создаётся
- Проверить миграции: `python manage.py migrate`
- Проверить CSRF токен в запросе
- Проверить права пользователя на отправку в чат

### Результаты не обновляются
- Проверить WebSocket соединение (консоль браузера)
- Проверить Channels/Redis настройки
- Проверить channel_layer в consumers.py

### Стили не применяются
- Проверить подключение chat-polls.css в шаблоне
- Очистить staticfiles: `python manage.py collectstatic --clear`
- Проверить загрузку в DevTools → Network

## Файлы изменений

### Backend:
- `communications/models.py` - модели Poll, PollOption, PollVote
- `communications/migrations/0019_add_polls.py` - миграция
- `communications/admin.py` - админка для голосований
- `api/v1/communications/poll_views.py` - API endpoints
- `api/v1/urls.py` - маршруты API

### Frontend:
- `static/js/components/chatPoll.js` - основной модуль
- `static/css/components/chat-polls.css` - стили
- `static/js/chat-detail-enhanced.js` - интеграция
- `templates/communications/chat_detail.html` - UI (модалка, кнопка)

## Производительность

### Оптимизации:
- Индексы на poll, option, voter
- Денормализация vote_count (избегаем COUNT на каждый запрос)
- Денормализация total_voters
- Prefetch для результатов с вариантами и голосами

### Рекомендации:
- Для больших чатов (>1000 участников) кешировать результаты
- Периодически обновлять vote_count через Celery задачу
- Ограничить частоту обновлений WebSocket (throttling)

---

**Автор:** GitHub Copilot  
**Дата:** 30 ноября 2025 г.
