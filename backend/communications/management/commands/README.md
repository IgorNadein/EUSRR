# Communications Management Commands

## manage_chat_permissions

Управление правами участников в чатах.

### Примеры использования

#### Показать участников чата

```bash
cd backend
.venv/Scripts/python manage.py manage_chat_permissions --chat-id 62 --list
```

#### Назначить администратора

```bash
.venv/Scripts/python manage.py manage_chat_permissions \\
    --chat-id 62 \\
    --user-id 10 \\
    --role admin
```

#### Назначить модератора с правом закреплять сообщения

```bash
.venv/Scripts/python manage.py manage_chat_permissions \\
    --chat-id 62 \\
    --user-id 10 \\
    --role moderator \\
    --can-pin-messages
```

#### Дать обычному участнику право добавлять новых участников

```bash
.venv/Scripts/python manage.py manage_chat_permissions \\
    --chat-id 62 \\
    --user-id 10 \\
    --role member \\
    --can-add-members
```

#### Дать все персональные права

```bash
.venv/Scripts/python manage.py manage_chat_permissions \\
    --chat-id 62 \\
    --user-id 10 \\
    --can-add-members \\
    --can-remove-members \\
    --can-pin-messages
```

#### Удалить права пользователя

```bash
.venv/Scripts/python manage.py manage_chat_permissions \\
    --chat-id 62 \\
    --user-id 10 \\
    --remove
```

### Роли

- **admin** 🔴 - Администратор (полные права на управление чатом)
- **moderator** 🟠 - Модератор (модерация контента)
- **member** 🟢 - Участник (обычные права)
- **guest** ⚪ - Гость (ограниченный доступ)

### Персональные права

- `--can-add-members` - Может добавлять участников
- `--can-remove-members` - Может удалять участников
- `--can-pin-messages` - Может закреплять сообщения

### Опции

- `--chat-id` - ID чата (обязательно)
- `--user-id` - ID пользователя (обязательно для всех операций кроме --list)
- `--role` - Роль: admin, moderator, member, guest
- `--list` - Показать список участников
- `--remove` - Удалить права (деактивировать membership)

---

## check_chats

Проверка и очистка чатов с некорректными типами.

### Примеры использования

#### Найти все чаты с некорректными типами

```bash
.venv/bin/python manage.py check_chats --find
```

#### Проверить конкретный чат

```bash
.venv/bin/python manage.py check_chats --check 6
```

#### Удалить все чаты с некорректными типами (с подтверждением)

```bash
.venv/bin/python manage.py check_chats --cleanup
```

#### Удалить все чаты с некорректными типами (без подтверждения)

```bash
.venv/bin/python manage.py check_chats --cleanup --no-confirm
```

#### Удалить конкретный чат

```bash
.venv/bin/python manage.py check_chats --delete 6
```

### Допустимые типы чатов

- `private` - Личный диалог
- `group` - Групповой чат
- `channel` - Канал
- `announcement` - Объявления
- `global` - Глобальный чат
- `comments` - Комментарии

### Опции

- `--find` - Найти все чаты с некорректными типами
- `--check CHAT_ID` - Проверить конкретный чат по ID
- `--cleanup` - Удалить все чаты с некорректными типами
- `--delete CHAT_ID` - Удалить конкретный чат по ID
- `--no-confirm` - Не запрашивать подтверждение при удалении

---

## Другие команды

- `init_reactions.py` - Инициализация реакций
- `verify_chat_migration.py` - Проверка миграции чатов
- `populate_image_dimensions.py` - Заполнение размеров изображений
- `update_department_chat_names.py` - Обновление названий чатов отделов
