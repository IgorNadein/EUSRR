# Система ролей в чатах

## Обзор

Система ролей в чатах EUSRR построена на двух уровнях:
1. **Владелец (Owner)** - определяется через `Chat.created_by`, не требует `ChatMembership`
2. **Роли участников** - управляются через модель `ChatMembership`

## Уровни доступа

### 1. Владелец (через `Chat.created_by`)

**Права:**
- Полный контроль над чатом
- Удаление чата
- Изменение ролей участников
- Все права администратора
- **НЕ может покинуть чат** (только удалить)

**Определение:**
```python
is_owner = chat.created_by == user
```

### 2. Администратор (`role='admin'`)

**Права:**
- Управление участниками (добавление/удаление)
- Редактирование чата (название, описание, аватар)
- Закрепление сообщений
- Отправка сообщений
- Может покинуть чат

**Автоматические разрешения:**
```python
can_send_messages = True
can_add_members = True
can_remove_members = True
can_pin_messages = True
```

### 3. Модератор (`role='moderator'`)

**Права:**
- Закрепление сообщений
- Удаление чужих сообщений (через django-rules)
- Отправка сообщений
- Может покинуть чат

**Автоматические разрешения:**
```python
can_send_messages = True
can_add_members = False
can_remove_members = False
can_pin_messages = True
```

### 4. Участник (`role='member'`)

**Права:**
- Отправка сообщений
- Редактирование своих сообщений
- Удаление своих сообщений
- Может покинуть чат

**Автоматические разрешения:**
```python
can_send_messages = True
can_add_members = False
can_remove_members = False
can_pin_messages = False
```

### 5. Гость (`role='guest'`)

**Права:**
- Только чтение
- Реакции на сообщения (если разрешено)
- Может покинуть чат

**Автоматические разрешения:**
```python
can_send_messages = False  # Только чтение
can_add_members = False
can_remove_members = False
can_pin_messages = False
```

## Модель ChatMembership

```python
class ChatMembership(models.Model):
    chat = ForeignKey(Chat)
    user = ForeignKey(User)
    role = CharField(choices=['admin', 'moderator', 'member', 'guest'])
    
    # Автоматические разрешения (устанавливаются при сохранении)
    can_send_messages = BooleanField(default=True)
    can_add_members = BooleanField(default=False)
    can_remove_members = BooleanField(default=False)
    can_pin_messages = BooleanField(default=False)
    
    # Metadata
    joined_at = DateTimeField(auto_now_add=True)
    invited_by = ForeignKey(User, null=True)
    is_active = BooleanField(default=True)
    left_at = DateTimeField(null=True)
```

### Вычисляемые свойства

```python
@property
def can_manage_members(self):
    """Может ли участник управлять другими участниками"""
    return self.can_add_members and self.can_remove_members
```

### Методы управления

```python
# Автоматическая установка прав при создании/изменении роли
membership.set_permissions_for_role()

# Повышение до админа
membership.promote_to_admin()

# Понижение до обычного участника
membership.demote_to_member()
```

## API Endpoints

### Изменение роли участника

```http
POST /api/v1/communications/chats/{chat_id}/change-role/
Content-Type: application/json

{
  "user_id": 123,
  "role": "admin"  // "admin" | "moderator" | "member" | "guest"
}
```

**Права доступа:** Только владелец чата

**Ответ:**
```json
{
  "ok": true,
  "message": "User role changed to admin",
  "membership": {
    "user_id": 123,
    "role": "admin",
    "can_send_messages": true,
    "can_add_members": true,
    "can_remove_members": true,
    "can_pin_messages": true,
    "can_manage_members": true
  }
}
```

### Добавление участника

```http
POST /api/v1/communications/chats/{chat_id}/add-member/
Content-Type: application/json

{
  "user_id": 456
}
```

**Права доступа:** Владелец или администратор

**Создает:** `ChatMembership` с ролью `member` по умолчанию

### Удаление участника

```http
POST /api/v1/communications/chats/{chat_id}/remove-member/
Content-Type: application/json

{
  "user_id": 456
}
```

**Права доступа:** Владелец или администратор

**Действие:** Устанавливает `is_active=False` в `ChatMembership`

## Django-rules предикаты

```python
# Проверка ролей
is_chat_owner(user, chat)      # created_by == user
is_chat_admin(user, chat)      # role in ['admin', 'moderator']
is_chat_member(user, chat)     # participant или active membership

# Правила доступа
'communications.view_chat'          -> is_superuser | is_chat_member
'communications.change_chat'        -> is_superuser | is_chat_owner | is_chat_admin
'communications.delete_chat'        -> is_superuser | is_chat_owner | is_chat_admin
'communications.add_members'        -> is_superuser | is_chat_owner | is_chat_admin
'communications.remove_members'     -> is_superuser | is_chat_owner | is_chat_admin
'communications.change_member_role' -> is_superuser | is_chat_owner
'communications.leave_chat'         -> is_chat_member & ~is_chat_owner
```

## Создание чата с ролями

При создании чата через API:

```python
# 1. Создается чат
chat = Chat.objects.create(
    type='group',
    name='My Group',
    created_by=request.user
)

# 2. Создатель добавляется в participants
chat.participants.add(request.user)

# 3. Создается ChatMembership с ролью admin
ChatMembership.objects.create(
    chat=chat,
    user=request.user,
    role='admin',  # Автоматически для создателя
    invited_by=request.user
)
# Права устанавливаются автоматически при save()
```

## Frontend Integration

### TypeScript типы

```typescript
interface ChatMembership {
  id: number;
  user: number;
  user_name?: string;
  role: 'admin' | 'moderator' | 'member' | 'guest';
  joined_at: string;
  can_send_messages: boolean;
  can_add_members: boolean;
  can_remove_members: boolean;
  can_pin_messages: boolean;
  can_manage_members?: boolean;
}
```

### API клиент

```typescript
// Изменить роль
await apiClient.changeChatMemberRole(chatId, userId, 'admin');

// Проверка прав
const isOwner = chat.created_by === currentUserId;
const isAdmin = chat.memberships?.some(
  m => m.user === currentUserId && m.role === 'admin'
);
const canEdit = isOwner || isAdmin;
```

## Типы чатов и роли

### Group (Групповой)
- Полная поддержка ролей
- `ChatMembership` для всех участников

### Channel (Канал)
- Полная поддержка ролей
- `ChatMembership` для всех участников
- Обычно админы публикуют, участники читают

### Announcement (Объявления)
- Полная поддержка ролей
- `chat.can_reply = False` - только реакции
- Только админы могут писать

### Private (Личный)
- Роли НЕ используются
- Все участники равноправны

### Global (Глобальный)
- Роли НЕ используются
- Доступ для всех активных пользователей

## Миграция существующих чатов

Если у вас есть чаты без `ChatMembership` для создателей:

```python
from communications.models import Chat, ChatMembership

# Для всех групповых чатов, каналов и объявлений
for chat in Chat.objects.filter(type__in=['group', 'channel', 'announcement']):
    if chat.created_by:
        # Создаем membership для создателя если его нет
        ChatMembership.objects.get_or_create(
            chat=chat,
            user=chat.created_by,
            defaults={
                'role': 'admin',
                'invited_by': chat.created_by
            }
        )
```

## Best Practices

1. **Всегда проверяйте права через django-rules**, а не напрямую через поля
2. **Используйте `set_permissions_for_role()`** при изменении ролей
3. **Владелец определяется через `created_by`**, а не через role='owner'
4. **Для личных чатов** не используйте `ChatMembership`
5. **При добавлении участников** создавайте `ChatMembership` для групп/каналов/объявлений

## Примеры использования

### Проверка прав на фронтенде

```typescript
// Может ли редактировать чат
const canEditChat = chat.created_by === user.id || 
  chat.memberships?.some(m => m.user === user.id && m.role === 'admin');

// Может ли управлять участниками
const canManageMembers = chat.created_by === user.id ||
  chat.memberships?.some(m => m.user === user.id && m.can_manage_members);
```

### Назначение модератора

```python
from communications.models import ChatMembership

membership = ChatMembership.objects.get(chat=chat, user=user)
membership.role = 'moderator'
membership.set_permissions_for_role()
membership.save()
```

### Лишение права писать (мут)

```python
membership = ChatMembership.objects.get(chat=chat, user=user)
membership.can_send_messages = False
membership.save()
```
