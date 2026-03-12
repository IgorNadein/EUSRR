# Исправление системы прав доступа в Communications

**Дата:** 12.03.2026  
**Статус:** Завершено  
**Тесты:** ✅ Все тесты прошли (6/6 send_message + 6/6 reactions)

## Проблемы

### 1. Пользователь не может добавить участника в групповой чат

При попытке пользователя добавить участника в групповой чат возникала ошибка 403 Forbidden:

```log
[WARNING] communications.rules:66 [is_chat_owner] checking via created_by: 
  user=10, created_by=1, result=False
[WARNING] django.request:253 Forbidden: /api/v1/communications/chats/62/
[WARNING] django.channels.server:191 HTTP POST /api/v1/communications/chats/62/add-member/ 403
```

**Причины:**
- **Неверный `related_name`** в предикате `is_chat_admin`: использовался `chatmembership_set` вместо `memberships`
- **Отсутствие проверки персональных прав**: флаги `can_add_members`, `can_remove_members`, `can_pin_messages` не использовались

### 2. Гость может отправлять сообщения (хотя не должен)

Пользователь с ролью `guest` (can_send_messages=False) мог отправлять сообщения в чат.

```python
# Тест падал
def test_guest_cannot_send_messages(self, guest_client, group_chat_with_roles):
    """Гость НЕ может отправлять сообщения"""
    response = guest_client.post(url, {'chat': chat_id, 'content': 'Message'})
    assert response.status_code == status.HTTP_403_FORBIDDEN  # ❌ Получали 201
```

**Причины:**
- Правило `communications.send_message` не проверяло флаг `can_send_messages`
- `MessagePermission.has_permission()` не проверяло права при создании сообщения

### 3. Гость не может отправлять реакции (хотя должен)

Гость с ролью `guest` не мог ставить реакции (эмодзи) на сообщения, получал ошибку или отклонение.

**Причины:**
- `MessagePermission.has_object_permission()` не обрабатывал custom actions (react, unreact)
- POST запросы на `/messages/{id}/react/` отклонялись как неразрешенные

## Решение

### 1. Исправлен предикат `is_chat_admin`

**Файл:** `backend/communications/rules.py`

```python
@rules.predicate
def is_chat_admin(user, chat):
    """Пользователь является администратором чата"""
    if chat is None:
        return False
    
    # Проверка через admins
    if hasattr(chat, 'admins'):
        return user in chat.admins.all()
    
    # Проверка через membership с ролью admin (только активные)
    if hasattr(chat, 'memberships'):  # ← БЫЛО: chatmembership_set
        result = chat.memberships.filter(
            user=user,
            role__in=['admin', 'moderator'],
            is_active=True
        ).exists()
        logger.warning(
            f"[is_chat_admin] user={user.id}, chat={chat.id}, "
            f"result={result}"
        )
        return result
    
    logger.warning(
        f"[is_chat_admin] no memberships for chat {chat.id}"
    )
    return False
```

### 2. Добавлены новые предикаты для персональных прав

```python
@rules.predicate
def can_add_members_flag(user, chat):
    """Пользователь имеет флаг can_add_members в ChatMembership"""
    if chat is None:
        return False

    if hasattr(chat, 'memberships'):
        result = chat.memberships.filter(
            user=user,
            can_add_members=True,
            is_active=True
        ).exists()
        logger.warning(
            f"[can_add_members_flag] user={user.id}, "
            f"chat={chat.id}, result={result}"
        )
        return result

    return False


@rules.predicate
def can_remove_members_flag(user, chat):
    """Пользователь имеет флаг can_remove_members в ChatMembership"""
    # Аналогично can_add_members_flag
    

@rules.predicate
def can_pin_messages_flag(user, chat):
    """Пользователь имеет флаг can_pin_messages в ChatMembership"""
    # Аналогично can_add_members_flag
```

### 3. Добавлена проверка прав на отправку сообщений

**Файл:** `backend/communications/rules.py`

```python
@rules.predicate
def has_send_messages_permission(user, chat):
    """
    Пользователь имеет право отправлять сообщения в чат
    
    Проверяет:
    1. Если НЕТ ChatMembership - разрешено (для обратной совместимости)
    2. Если ЕСТЬ ChatMembership - проверяется флаг can_send_messages
    """
    if chat is None:
        return False
    
    # Для личных/глобальных чатов без ChatMembership - разрешено всем
    if chat.type in ['private', 'global']:
        return True
    
    # Для чатов с ChatMembership проверяем флаг can_send_messages
    if hasattr(chat, 'memberships'):
### 5. Обновлены правила доступаrn membership.can_send_messages
        except ChatMembership.DoesNotExist:
            # Если нет membership, но пользователь в participants - разрешено
            return chat.participants.filter(pk=user.pk).exists()
    
    # Если нет memberships (старые чаты) - разрешено
    return True


# Обновленное правило
rules.add_rule(
    'communications.send_message',
    is_superuser | (is_chat_member & has_send_messages_permission)
    # ↑ добавлена проверка флага can_send_messages
)
```

### 4. Добавлена проверка в MessagePermission

**Файл:** `backend/communications/api/permissions.py`

```python
class MessagePermission(permissions.BasePermission):
    """
    Проверка прав доступа к сообщениям через django-rules
    
    Правила:
    - GET - доступ к чату сообщения
    - POST создание - участник чата + can_send_messages
    - POST react/unreact - участник чата (включая гостей)  # ← НОВОЕ
    - PUT/PATCH - автор сообщения
    - DELETE - автор или админ чата
    """
    
    def has_permission(self, request, view):
        """Базовая проверка при создании сообщения"""
        if not (request.user and request.user.is_authenticated):
            return False
        
        # При создании сообщения проверяем права на отправку в чат
        if request.method == 'POST' and view.action in ['create', 'upload']:
            chat_id = (
                request.data.get('chat') or
                request.data.get('chat_id')
            )
            
            if chat_id:
                try:
                    from ..models import Chat
                    chat = Chat.objects.get(pk=chat_id)
                    
                    # ✅ Проверка через django-rules
                    return rules.test_rule(
                        'communications.send_message',
                        request.user,
                        chat
                    )
                except Chat.DoesNotExist:
                    return False
        
        return True
    
    def has_object_permission(self, request, view, obj):
        """Проверка прав на конкретное сообщение"""
        # ✅ НОВОЕ: Реакции доступны всем участникам чата (включая гостей)
        if hasattr(view, 'action') and view.action in ['react', 'unreact']:
            return rules.test_rule(
                'communications.view_message',
                request.user,
                obj
            )
        
        # Просмотр - доступ к чату
        if request.method in permissions.SAFE_METHODS:
            return rules.test_rule(
                'communications.view_message',
                request.user,
                obj
            )
        
        # Редактирование - автор
        if request.method in ['PUT', 'PATCH']:
            return rules.test_rule(
                'communications.change_message',
                request.user,
                obj
            )
        
        # Удаление - автор или админ
        if request.method == 'DELETE':
            return rules.test_rule(
                'communications.delete_message',
                request.user,
                obj
            )
        
        return False
```

```python
# Добавление участников в чат
rules.add_rule(
    'communications.add_members',
    is_superuser | is_chat_owner | is_chat_admin | can_add_members_flag
    # ↑ добавлен новый предикат
)

# Удаление участников из чата
rules.add_rule(
    'communications.remove_members',
    is_superuser | is_chat_owner | is_chat_admin | can_remove_members_flag
    # ↑ добавлен новый предикат
)

# Закрепление сообщений
rules.add_rule(
    'communications.pin_message',
    is_superuser | is_chat_owner | is_chat_admin | can_pin_messages_flag
    # ↑ добавлен новый предикат
)
```

## Иерархия прав

Теперь система поддерживает **три уровня прав доступа**:

### 1. 🔴 Владелец чата (`Chat.created_by`)
- **Полные права** на управление чатом
- Может изменять настройки, добавлять/удалять участников
- Не может покинуть чат (владелец не может уйти)

### 2. 🟠 Администратор/Модератор (`ChatMembership.role`)
- **Роль `admin`**: широкие права на управление чатом
- **Роль `moderator`**: модерация контента, может удалять чужие сообщения
- Назначается через поле `role` в таблице `ChatMembership`

### 3. 🟢 Персональные права (`ChatMembership` флаги)
- `can_add_members` - может добавлять участников
- `can_remove_members` - может удалять участников
- `can_pin_messages` - может закреплять сообщения
- `can_send_messages` - может отправлять сообщения

## Как использовать

### Назначить администратора через Django Admin or Shell

```python
from communications.models import Chat, ChatMembership
from employees.models import Employee

chat = Chat.objects.get(pk=62)
user = Employee.objects.get(pk=10)

# Создать или обновить membership
membership, created = ChatMembership.objects.get_or_create(
    chat=chat,
    user=user,
    defaults={
        'role': 'admin',  # или 'moderator', 'member', 'guest'
        'can_add_members': True,
        'can_remove_members': True,
        'can_pin_messages': True,
        'invited_by': chat.created_by
    }
)

if not created:
    # Обновить существующий membership
    membership.role = 'admin'
    membership.can_add_members = True
    membership.can_remove_members = True
    membership.can_pin_messages = True
    membership.save()

print(f"✅ Пользователь {user.get_full_name()} назначен администратором чата")
```

### Назначить персональные права (без роли admin)

```python
membership, created = ChatMembership.objects.get_or_create(
    chat=chat,
    user=user,
    defaults={
        'role': 'member',  # обычный участник
**Тесты отправки сообщений:**
```
test_owner_can_send_messages PASSED              ✅
test_admin_can_send_messages PASSED              ✅
test_moderator_can_send_messages PASSED          ✅
test_member_can_send_messages PASSED             ✅
test_guest_cannot_send_messages PASSED           ✅ (было: FAILED)
test_non_member_cannot_send_messages PASSED      ✅
```

**Тесты отправки реакций:**
```
test_owner_can_react PASSED                      ✅
test_admin_can_react PASSED                      ✅
test_moderator_can_react PASSED                  ✅
test_member_can_react PASSED                     ✅
test_guest_can_react PASSED                      ✅ (НОВЫЙ)
test_non_member_cannot_react PASSED        

```python
import rules

# Проверка прав на добавление участников
can_add = rules.test_rule('communications.add_members', user, chat)
print(f"Can add members: {can_add}")

# Проверка прав на изменение чата
can_change = rules.test_rule('communications.change_chat', user, chat)
print(f"Can change chat: {can_change}")
```

## API Endpoints

После исправления следующие endpoints доступны пользователям с правами:

- `POST /api/v1/communications/chats/{id}/add-member/` - добавить участника
  - Требует: `is_superuser | is_chat_owner | is_chat_admin | can_add_members_flag`

- `POST /api/v1/communications/chats/{id}/remove-member/` - удалить участника  
  - Требует: `is_superuser | is_chat_owner | is_chat_admin | can_remove_members_flag`

- `PATCH /api/v1/communications/chats/{id}/` - изменить чат
  - Требует: `is_superuser | is_chat_owner | is_chat_admin`

- `POST /api/v1/communications/chats/{id}/pin/` - закрепить чат
  - Требует: `is_superuser | is_chat_owner | is_chat_admin | can_pin_messages_flag`

## Тестирование

### Запуск тестов

```bash
cd backend
.venv/bin/python -m pytest tests/api/v1/communications/test_chat_roles.py::TestSendMessagePermissions -v
```

### Результаты (все пройдены ✅)

```
test_owner_can_send_messages PASSED              ✅
**Отправка сообщений:**
1. ✅ Владелец чата может отправлять сообщения
2. ✅ Администратор (role=admin) может отправлять сообщения
3. ✅ Модератор (role=moderator) может отправлять сообщения
4. ✅ Обычный участник (role=member) может отправлять сообщения
5. ✅ Гость (role=guest) НЕ может отправлять сообщения
6. ✅ Не-участник чата НЕ может отправлять сообщения

**Реакции (эмодзи):**
7. ✅ Владелец чата может ставить реакции
8. ✅ Администратор может ставить реакции
9. ✅ Модератор может ставить реакции
10. ✅ Обычный участник может ставить реакции
11. ✅ Гость МОЖЕТ ставить реакции (даже без can_send_messages)
12. ✅ Не-участник чата НЕ может ставить реакции

**Управление участниками:**
13. ✅ Владелец чата может добавлять участников  
14. ✅ Администратор (role=admin) может добавлять участников
15. ✅ Модератор (role=moderator) может добавлять участников
16. ✅ Обычный участник с can_add_members=True может добавлять участников
17
1. ✅ Владелец чата может отправлять сообщения
2. ✅ Администратор (role=admin) может отправлять сообщения
3. ✅ Модератор (role=moderator) может отправлять сообщения
4. ✅ Обычный участник (role=member) может отправлять сообщения
5. ✅ Гость (role=guest) НЕ может отправлять сообщения
6. ✅ Не-участник чата НЕ может отправлять сообщения
7. ✅ Владелец чата может добавлять участников  
8. ✅ Администратор (role=admin) может добавлять участников
9. ✅ Модератор (role=moderator) может добавлять участников
10. ✅ Обычный участник с can_add_members=True может добавлять участников
11. ❌ Обычный участник без прав НЕ может добавлять участников

## Логирование

Все проверки прав записываются в лог с уровнем WARNING:

```log
[can_add_members_flag] user=10, chat=62, result=True
[is_chat_admin] user=10, chat=62, result=True
```

Это помогает отладить проблемы с правами доступа.

## Совместимость

✅ Изменения **обратно совместимы**:
- Старые чаты без ChatMembership работают как раньше
- Личные чаты (type=private) используют только поле `participants`
- Глобальные чаты (type=global) доступны всем
- Групповые чаты (type=group) используют ChatMembership

## Примечания

- Роль `owner` в ChatMembership НЕ используется - владелец определяется через `Chat.created_by`
- Флаг `is_active=False` означает, что пользователь покинул чат
- При добавлении участника автоматически создается запись в ChatMembership с role='member'
