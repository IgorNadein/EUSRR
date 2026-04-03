# Отчёт: Рефакторинг чатов EUSRR + Сравнительный анализ

## 1. Что было сделано

### 1.1 Frontend — Декомпозиция монолита `page.tsx`

| Метрика | До | После |
|---|---|---|
| Строк в `page.tsx` | **1 989** | **893** (−55%) |
| `useState` в `page.tsx` | 40+ | 18 (UI-only) |
| `useEffect` в `page.tsx` | 15+ | 10 |
| `useCallback` в `page.tsx` | 20+ | ~12 |
| Выделенные хуки | 0 | 3 новых |

**Новые файлы:**

- `hooks/useMarkRead.ts` — дебаунсированная отметка прочтения с очередью, watermark-синхронизация.
- `hooks/useChatMessages.ts` — состояние сообщений, пагинация, pending/optimistic, unread-трекинг, навигация по дате, возврат к непрочитанным.
- `hooks/useChatScroll.ts` — управление скроллом, floating date, кнопка «вниз», определение позиции.

### 1.2 Исправление бага со счётчиком непрочитанных

**Причина:** `flushMarkRead` после `markChatAsRead` вызывал `getChat(chatId)` и перезаписывал `newMessagesBelowCount` серверным значением (0), из-за чего бейдж исчезал мгновенно.

**Решение:** `onReadAcknowledged` в `useMarkRead` теперь **не трогает** локальный счётчик. Сброс `newMessagesBelowCount` происходит **только** когда пользователь физически доскроллит до низа (`syncScrollToBottomState`). Серверный `chat.unread_count` обновляется отдельно через `setChat(fresh)`.

### 1.3 Backend — N+1 оптимизации

| Проблема | Файл | Решение |
|---|---|---|
| `get_last_message` делал N запросов (1 на чат) | `serializers.py` | Добавлен `Prefetch('messages', ...)` с `to_attr='_prefetched_last_message'` в `ChatViewSet.get_queryset` |
| `get_participant_names` перезапрашивал memberships | `serializers.py` | Теперь использует уже prefetch'нутый `obj.memberships.all()` |
| Дублирующийся `Q(participants=user)` | `viewsets.py` | Удалён дубль |

**Уже было оптимизировано (не трогали):**
- `reactions__user` — prefetch в `MessageViewSet.get_queryset` ✓
- `ChatReadState.unread_count` — денормализовано через сигнал ✓
- `react`/`unreact` — уже используют `select_related('user')` ✓

---

## 2. Оценка нагрузки на БД

### 2.1 Список чатов (`GET /chats/`)

| Ресурс | Запросов (до) | Запросов (после) |
|---|---|---|
| Основной запрос чатов | 1 | 1 |
| Prefetch memberships | 1 | 1 |
| Prefetch user_settings | 1 | 1 |
| Prefetch read_states | 1 | 1 |
| **last_message** | **N** (1 на чат) | **1** (prefetch) |
| **participant_names** | **N** (1 на чат) | **0** (из prefetch) |
| **ИТОГО для 50 чатов** | **~104** | **~5** |

### 2.2 Страница чата (`GET /chats/{id}/`, `GET /messages/`)

| Операция | Запросов |
|---|---|
| Загрузка чата | 5 (chat + 4 prefetch) |
| Загрузка 30 сообщений вокруг anchor | 1 + 4 prefetch = 5 |
| WebSocket new_message | 0 (из памяти) |
| mark-read (дебаунс 300ms) | 1 POST + 1 GET (refresh chat) |
| Реакция | 1 POST + 1 SELECT (summary) |
| **Типичное открытие чата** | **~12 запросов** |

### 2.3 Узкие места (остаются)

1. **`get_last_message` в retrieve** — для единичного `getChat()` prefetch не помогает (1 запрос). Допустимо.
2. **`PollViewSet.vote`** — `option.votes.count()` в цикле (N+1). Нужен `annotate(Count('votes'))`.
3. **`ChatViewSet.create`** — `User.objects.get(id=user_id)` в цикле при добавлении участников. Нужен `User.objects.filter(id__in=...)`.

---

## 3. Сравнение с популярными мессенджерами

### 3.1 Архитектура доставки сообщений

| Фича | Telegram | WhatsApp | Slack | **EUSRR** |
|---|---|---|---|---|
| Транспорт | MTProto (custom) | Signal Protocol | WebSocket | **WebSocket** |
| Оффлайн-очередь | Push + pull при connect | Push + pull | Pull при connect | **Pull при connect** (fallback sync) |
| E2E шифрование | Secret Chats only | Да | Enterprise only | **Нет** (корп. сеть) |
| Оптимистичные сообщения | Да | Да | Да | **Да** ✓ |
| Pending → Delayed → Failed | Да (часы/галочки) | Да | Нет | **Да** ✓ |

### 3.2 Управление прочтением

| Фича | Telegram | WhatsApp | Slack | **EUSRR** |
|---|---|---|---|---|
| Подсчёт непрочитанных | Денормализован | Денормализован | Денормализован (badge API) | **Денормализован** (`ChatReadState.unread_count`) ✓ |
| Mark-as-read | При открытии (2с задержка) | При открытии | При фокусе канала | **При скролле до сообщения** (300ms debounce) |
| Двойные галочки (read receipt) | Да | Да | Нет | **Да** (`is_read`, `read_by`) ✓ |
| Кто прочитал | Нет (кроме групп Premium) | Нет | Hover-подсказка | **Модальное окно** ✓ |

### 3.3 Пагинация и скролл

| Фича | Telegram | WhatsApp | Slack | **EUSRR** |
|---|---|---|---|---|
| Пагинация | Бикурсорная (around + offset) | Local-first DB (SQLite) | Cursor-based | **Бикурсорная** (`before_id`/`after_id`/`around_id`) ✓ |
| Навигация по дате | Да (календарь) | Да (jump to date) | Нет | **Да** ✓ |
| Scroll restoration | position-to-bottom | Anchor-based | Виртуализация | **Anchor-based** (`getSnapshotBeforeUpdate`) ✓ |
| Виртуализация списка | Нет (native) | Нет (native) | Да | **Нет** ⚠️ |

### 3.4 Реакции

| Фича | Telegram | WhatsApp | Slack | **EUSRR** |
|---|---|---|---|---|
| Быстрые реакции | 5 недавних + picker | 6 недавних + picker | Несколько + picker | **5 недавних + 40 emoji** ✓ |
| Custom emoji | Premium | Нет | Workspace emoji | **Нет** |
| Реакция-нотификация | Push | Push | Push | **WebSocket** ✓ |

### 3.5 Что есть у конкурентов, но нет у EUSRR

| Фича | Приоритет | Сложность |
|---|---|---|
| **Виртуализация списка сообщений** (react-window) | Высокий (>1000 сообщений = тормоза) | Средняя |
| **Реал-тайм обновление списка чатов** (unread badge без перезагрузки) | Высокий | Низкая (WS уже есть) |
| **Threads** (ветки обсуждений) | Средний | Высокая |
| **Поиск по сообщениям** | Средний | Средняя |
| **Голосовые сообщения** | Низкий | Средняя |
| **Пересланные сообщения (UI)** | Низкий | Низкая |

### 3.6 Что у EUSRR лучше аналогов

1. **Система ролей в чатах** (admin/moderator/member/guest) — нет у Telegram/WhatsApp в таком виде.
2. **Интеграция с оргструктурой** — чаты отделов, привязка к LDAP.
3. **Контекстные чаты** (комментарии к постам/документам) — нет у классических мессенджеров.
4. **Управление доступом** — гости без права отправки, модерация контента.

---

## 4. Рекомендации по дальнейшим улучшениям

### Высокий приоритет

1. **Виртуализация списка сообщений** — при >500 сообщений DOM замедляется. Использовать `@tanstack/react-virtual` или `react-window`.
2. **WebSocket обновление списка чатов** — `wsManager` уже существует; нужен подписчик на `new_message` для обновления `last_message` и `unread_count` в списке без перезагрузки.
3. **Annotate poll vote counts** — `PollViewSet.vote` имеет N+1 на `option.votes.count()`. Заменить на `annotate(Count('votes'))`.

### Средний приоритет

4. **State management** — рассмотреть Zustand или TanStack Query для кеширования чатов/сообщений между страницами.
5. **Bulk create memberships** — `ChatViewSet.create` делает N запросов при добавлении участников.
6. **Поиск по сообщениям** — PostgreSQL full-text search (`SearchVector`, `SearchQuery`).

### Низкий приоритет

7. Удалить дублирование WebSocket логики (`useWebSocket` vs `wsManager`).
8. Typed API client вместо `any` в `createMessagesApi`.
