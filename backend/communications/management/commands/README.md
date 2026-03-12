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

## Другие команды

- `init_reactions.py` - Инициализация реакций
- `verify_chat_migration.py` - Проверка миграции чатов
- `populate_image_dimensions.py` - Заполнение размеров изображений
- `update_department_chat_names.py` - Обновление названий чатов отделов
