# Диагностика прав доступа в чатах (Communications)

## Быстрая проверка

### 1. Проверить роль пользователя в чате

```bash
cd backend
.venv/bin/python manage.py manage_chat_permissions --chat-id <ID> --list
```

Вывод покажет:
- 🔴 admin - полные права
- 🟠 moderator - модерация контента
- 🟢 member - обычный участник
- ⚪ guest - только чтение

**Флаги:**
- ➕ add - может добавлять участников
- ➖ remove - может удалять участников
- 📌 pin - может закреплять сообщения

### 2. Типичные проблемы и решения

#### Проблема: Пользователь не может добавить участника (403)

```log
[WARNING] communications.rules:66 [is_chat_owner] checking via created_by: 
  user=10, created_by=1, result=False
[WARNING] HTTP POST /api/v1/communications/chats/{id}/add-member/ 403
```

**Решение:**
```bash
# Назначить администратором
.venv/bin/python manage.py manage_chat_permissions \\
    --chat-id <ID> --user-id <USER_ID> --role admin

# ИЛИ дать персональное право
.venv/bin/python manage.py manage_chat_permissions \\
    --chat-id <ID> --user-id <USER_ID> --can-add-members
```

#### Проблема: Гость может отправлять сообщения (хотя не должен)

```python
# Проверить через тест
.venv/bin/python -m pytest \\
    tests/api/v1/communications/test_chat_roles.py::TestSendMessagePermissions::test_guest_cannot_send_messages -v
```

**Ожидаемый результат:** `PASSED` (403 Forbidden при попытке отправки)

**Если тест падает:**
- Проверить, что правило `communications.send_message` использует `has_send_messages_permission`
- Проверить, что `MessagePermission.has_permission()` проверяет права при POST

#### Проблема: Гость не может ставить реакции (хотя должен)

```python
# Проверить через тест
.venv/bin/python -m pytest \\
    tests/api/v1/communications/test_chat_roles.py::TestReactionPermissions::test_guest_can_react -v
```

**Ожидаемый результат:** `PASSED` (200 OK при попытке поставить реакцию)

**Если тест падает:**
- Проверить, что `MessagePermission.has_object_permission()` обрабатывает actions `['react', 'unreact']`
- Проверить, что для реакций достаточно права `communications.view_message`

#### Проблема: Участник с can_add_members=True всё равно не может добавить

**Проверить:**
1. Флаг `is_active=True` в ChatMembership
2. Пользователь находится в `chat.participants`
3. Правило `communications.add_members` включает `can_add_members_flag`

```python
# Проверка через Django shell
from communications.models import Chat, ChatMembership
chat = Chat.objects.get(pk=<ID>)
membership = ChatMembership.objects.get(chat=chat, user_id=<USER_ID>)

print(f"Role: {membership.role}")
print(f"can_add_members: {membership.can_add_members}")
print(f"is_active: {membership.is_active}")
print(f"In participants: {chat.participants.filter(pk=<USER_ID>).exists()}")
```

### 3. Иерархия проверки прав на отправку сообщений

```
MessageViewSet.create() 
  ↓
MessagePermission.has_permission()  ← ✅ Проверка chat_id + django-rules
  ↓
rules.test_rule('communications.send_message', user, chat)
  ↓
is_superuser | (is_chat_member & has_send_messages_permission)
  ↓
has_send_messages_permission:
  1. Если chat.type in ['private', 'global'] → True
  2. Если есть ChatMembership → проверка membership.can_send_messages
  3. Если нет ChatMembership, но в participants → True (совместимость)
  4. Иначе → True (старые чаты)
```

### 3.1. Иерархия проверки прав на реакции

```
MessageViewSet.react()
  ↓
MessagePermission.has_object_permission()  ← ✅ Проверка action='react'
  ↓
rules.test_rule('communications.view_message', user, message)
  ↓
is_superuser | can_access_message_chat
  ↓
can_access_message_chat: is_chat_member(user, message.chat)
  ↓
Результат: Любой участник чата (включая гостей) может ставить реакции
```

### 4. Иерархия проверки прав на добавление участников

```
ChatViewSet.add_member()
  ↓
rules.test_rule('communications.add_members', user, chat)
  ↓
is_superuser | is_chat_owner | is_chat_admin | can_add_members_flag
  ↓
is_chat_owner: chat.created_by == user
is_chat_admin: membership.role in ['admin', 'moderator'] AND is_active=True
can_add_members_flag: membership.can_add_members=True AND is_active=True
```

### 5. Логирование для отладки

Все проверки прав записываются с уровнем WARNING:

```log
[is_chat_admin] user=10, chat=62, result=True
[can_add_members_flag] user=10, chat=62, result=True
[has_send_messages_permission] user=10, chat=62, can_send=False
```

**Включить логи:**
```python
# settings.py
LOGGING = {
    'loggers': {
        'communications.rules': {
            'handlers': ['console'],
            'level': 'WARNING',
            'propagate': False,
        },
    },
}
```

### 6. Частые команды

# Запустить тесты реакций
.venv/bin/python -m pytest tests/api/v1/communications/test_chat_roles.py::TestReactionPermissions -v

```bash
# Показать участников чата
.venv/bin/python manage.py manage_chat_permissions --chat-id 62 --list

# Назначить администратора
.venv/bin/python manage.py manage_chat_permissions --chat-id 62 --user-id 10 --role admin

# Дать право добавлять участников
.venv/bin/python manage.py manage_chat_permissions --chat-id 62 --user-id 10 --can-add-members

# Запустить тесты ролей
.venv/bin/python -m pytest tests/api/v1/communications/test_chat_roles.py -v

# Запустить тесты отправки сообщений
.venv/bin/python -m pytest tests/api/v1/communications/test_chat_roles.py::TestSendMessagePermissions -v
```

### 7. Файлы для проверки

- `backend/communications/rules.py` - django-rules предикаты и правила
- `backend/communications/api/permissions.py` - DRF permission classes
- `backend/communications/api/viewsets.py` - ChatViewSet, MessageViewSet
- `backend/communications/models.py` - Chat, ChatMembership
- `backend/tests/api/v1/communications/test_chat_roles.py` - тесты ролей

### 8. Контрольная сумма (если что-то сломалось)

Проверить, что предикаты существуют:

```python
# Django shell
import rules
predicates = [
    'is_chat_member',
    'is_chat_owner',
    'is_chat_admin',
    'can_add_members_flag',
    'can_remove_members_flag',
    'can_pin_messages_flag',
    'has_send_messages_permission',
]

for pred in predicates:
    exists = pred in dir(rules)  # Упрощенная проверка
    print(f"{pred}: {'✅' if exists else '❌'}")
```

**Все предикаты должны существовать!**
