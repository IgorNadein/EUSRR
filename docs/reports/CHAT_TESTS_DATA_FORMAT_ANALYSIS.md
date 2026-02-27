# Анализ формата данных в тестах чата

**Дата:** 12.01.2026  
**Статус:** Требуется обновление

## Проблема

Текущие тесты используют **упрощённую структуру данных**, которая не соответствует реальным данным, приходящим с бэкэнда.

### Текущий формат в тестах (устаревший):

```javascript
{
    id: 100,
    chat_id: 1,
    sender: { id: 1, username: 'user1' },
    content: 'Test message',
    created_at: '2024-01-01T10:00:00Z'  // ISO строка
}
```

### Реальный формат с бэкэнда (из `serialize_message()`):

```javascript
{
    // Основные поля
    id: 681,
    content: "Текст сообщения",
    author_id: 1,
    author_name: "Самый главный admin",
    author_url: "/employees/1/",
    avatar: "/media/users/avatars/avatar_1.jpg",
    created: "12.01.2026 16:00",
    created_ts: 1736688000000,  // Миллисекунды
    
    // Флаги состояния
    is_edited: false,
    edited_at: null,
    is_deleted: false,
    is_pinned: false,
    is_forwarded: false,
    is_system: false,
    has_attachments: false,
    
    // Реакции
    reactions_summary: {
        '👍': {
            count: 3,
            users: [1, 2, 3],
            user_names: ['User1', 'User2', 'User3']
        }
    },
    
    // Ответ на сообщение
    reply_to: {
        id: 621,
        content: "Текст оригинального сообщения...",
        author_name: "Самый главный admin"
    },
    
    // Вложения
    attachments: [
        {
            id: 1,
            file_name: "document.pdf",
            file_type: "application/pdf",
            file_url: "/media/attachments/document.pdf",
            file_size: 1024000,
            mime_type: "application/pdf",
            thumbnail: null
        }
    ],
    
    // Пересылка
    forwarded_from: {
        author_id: 2,
        author_name: "Другой пользователь",
        message_id: 500,
        created_at: "11.01.2026 15:00",
        created_ts: 1736601600000,
        chat_name: "Другой чат"
    },
    
    // Голосование
    poll: {
        id: 1,
        question: "Вопрос?",
        is_anonymous: false,
        is_multiple_choice: false,
        is_quiz: false,
        is_closed: false,
        closes_at: null,
        total_voters: 5,
        options: [
            {
                id: 1,
                text: "Вариант 1",
                position: 0,
                vote_count: 3,
                percentage: 0
            }
        ]
    }
}
```

## Ключевые различия

| Поле | Тесты (старое) | Бэкэнд (реальное) | Проблема |
|------|----------------|-------------------|----------|
| `sender` | `{ id, username }` | ❌ Не существует | Тесты используют несуществующее поле |
| `author_id` | ❌ Отсутствует | ✅ Присутствует | Критично для работы |
| `author_name` | ❌ Отсутствует | ✅ Присутствует | Критично для отображения |
| `created_at` | ISO строка | ❌ Не используется | Конвертируется в `created_ts` |
| `created_ts` | ❌ Отсутствует | Миллисекунды | Критично для сортировки |
| `is_edited`, `is_deleted`, etc. | ❌ Отсутствуют | ✅ Присутствуют | Важно для функциональности |
| `reactions_summary` | ❌ Отсутствует | ✅ Присутствует | Реакции не тестируются |
| `reply_to` | ❌ Отсутствует | ✅ Присутствует | Ответы не тестируются |
| `attachments` | ❌ Отсутствует | ✅ Присутствует | Вложения не тестируются |

## Логи реальных запросов

Из бэкэнд логов видно реальные API вызовы:

```
[INFO] GET /api/v1/communications/chats/10/messages/around/?around_id=1768222792363&limit=20
[INFO] GET /api/v1/communications/chats/10/messages/?before_id=681&limit=20
[INFO] GET /api/v1/communications/chats/10/messages/?before_id=661&limit=20
[DEBUG] serialize_message: added reply_to id=621, author=Самый главный admin
```

**Особенности:**
- Используется `around_id` для начальной загрузки вокруг сообщения
- Параметр `before_id` для дозагрузки истории
- Limit по умолчанию = 20 сообщений
- Реальные ID сообщений: 681, 661, 641, 612, 527, 506, 477, 453
- Сообщения содержат `reply_to` с полной информацией

## Решение

### 1. ✅ Создана функция `createRealisticMessage()`

```javascript
createRealisticMessage(overrides = {}) {
    const defaults = {
        id: Math.floor(Math.random() * 10000),
        content: 'Тестовое сообщение',
        author_id: 1,
        author_name: 'Тестовый пользователь',
        author_url: '/employees/1/',
        avatar: '/media/users/avatars/default.jpg',
        created: '12.01.2026 16:00',
        created_ts: Date.now(),
        is_edited: false,
        edited_at: null,
        is_deleted: false,
        is_pinned: false,
        is_forwarded: false,
        is_system: false,
        has_attachments: false,
        reactions_summary: {},
        reply_to: null,
        forwarded_from: null,
        attachments: [],
        poll: null
    };
    return { ...defaults, ...overrides };
}
```

### 2. ⏳ Обновление тестов (в процессе)

**Обновлено:**
- ✅ `testMessageStore()` - тесты 1-10 обновлены с реалистичными данными
- ✅ Добавлены тесты для `reply_to`, `attachments`, `reactions_summary`

**Требуется обновить:**
- ⏳ `testMessageStore()` - тесты 11-23 (оптимистичные сообщения, события, сортировка, дублика ты)
- ⏳ `testMessageLoader()` - все 20 тестов
- ⏳ `testScrollManager()` - все 10 тестов
- ⏳ `testMessageRenderer()` - все 8 тестов
- ⏳ `testChatController()` - все 11 тестов
- ⏳ `testIntegration()` - все 8 тестов
- ⏳ `testPerformance()` - все 5 тестов
- ⏳ `testAdvanced()` - все 23 теста (особенно важно)
- ⏳ `testScrollStability()` - все 8 тестов (критично)

### 3. Дополнительные тесты для реальных данных

Необходимо добавить тесты для:

```javascript
// Тест reply_to в реальном формате
const msgWithReply = this.createRealisticMessage({
    id: 682,
    content: 'Ответ на предыдущее',
    reply_to: {
        id: 681,
        content: 'Оригинальное сообщение...',
        author_name: 'Другой пользователь'
    }
});

// Тест вложений в реальном формате
const msgWithAttachments = this.createRealisticMessage({
    id: 683,
    has_attachments: true,
    attachments: [
        {
            id: 1,
            file_name: 'report.pdf',
            file_type: 'application/pdf',
            file_url: '/media/attachments/report.pdf',
            file_size: 2048576,
            mime_type: 'application/pdf',
            thumbnail: null
        }
    ]
});

// Тест реакций в реальном формате
const msgWithReactions = this.createRealisticMessage({
    id: 684,
    reactions_summary: {
        '👍': { count: 5, users: [1, 2, 3, 4, 5], user_names: ['User1', 'User2', ...] },
        '❤️': { count: 2, users: [1, 3], user_names: ['User1', 'User3'] }
    }
});
```

## Критичность

🔴 **ВЫСОКАЯ КРИТИЧНОСТЬ**

**Почему:**
1. Тесты сейчас **НЕ проверяют реальную работу** системы
2. Код может работать с тестовыми данными, но **падать на реальных**
3. Важные функции не тестируются: реакции, ответы, вложения
4. `created_ts` критичен для сортировки и отображения дат

## Следующие шаги

1. ✅ Создана `createRealisticMessage()`
2. ⏳ Обновить все 113 тестов на использование реального формата
3. ⏳ Добавить тесты для API endpoint'ов (`/around/`, `/before_id/`)
4. ⏳ Добавить тесты для edge cases с реальными данными
5. ⏳ Протестировать на реальных данных из production

## Примеры обновления

### До (неправильно):

```javascript
const msg = {
    id: 100,
    chat_id: 1,
    sender: { id: 1, username: 'user1' },
    content: 'Test',
    created_at: '2024-01-01T10:00:00Z'
};
```

### После (правильно):

```javascript
const msg = this.createRealisticMessage({
    id: 100,
    chat_id: 1,
    author_id: 1,
    author_name: 'Иван Иванов',
    content: 'Тест',
    created_ts: new Date('2024-01-01T10:00:00Z').getTime()
});
```

## Статистика

- **Всего мест с `created_at:`** 36
- **Всего мест с `sender:`** ~100+
- **Обновлено:** ~10
- **Осталось обновить:** ~126

## Вывод

Тесты требуют **масштабного обновления** для соответствия реальным данным с бэкэнда. Текущая версия тестов проверяет работу с упрощённым форматом, который не используется в production.

**Рекомендация:** Продолжить обновление всех тестов с использованием `createRealisticMessage()` для полного соответствия реальным данным.
