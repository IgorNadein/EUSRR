# Список всех эндпоинтов Django проекта EUSRR

**Дата:** 26 декабря 2025 г.

---

## 🔐 Аутентификация (`/auth/`)

### Frontend Auth
| Метод | URL | Описание | View |
|-------|-----|----------|------|
| GET/POST | `/auth/login/` | Вход по email или телефону | `EmailOrPhoneLoginView` |
| GET/POST | `/auth/logout/` | Подтверждение выхода | `ConfirmLogoutView` |
| GET/POST | `/auth/register/` | Регистрация | `register_view` |
| GET/POST | `/auth/verify-email/` | Подтверждение email | `verify_email_view` |
| POST | `/auth/resend-email/` | Повторная отправка email | `resend_email_view` |
| GET/POST | `/auth/password-reset/` | Сброс пароля | `PasswordResetView` |
| GET | `/auth/password-reset/done/` | Подтверждение отправки | `PasswordResetDoneView` |
| GET/POST | `/auth/reset/<uidb64>/<token>/` | Подтверждение сброса | `PasswordResetConfirmView` |
| GET | `/auth/reset/done/` | Завершение сброса | `PasswordResetCompleteView` |

---

## 📄 Документы (`/documents/`)

### Frontend
| Метод | URL | Описание | View |
|-------|-----|----------|------|
| GET | `/documents/` | Список документов | `DocumentView` |
| POST | `/documents/ack/<int:pk>/` | Подтверждение прочтения | `acknowledge_document` |

---

## 📝 Заявки (`/requests/`)

### Frontend
| Метод | URL | Описание | View |
|-------|-----|----------|------|
| GET | `/requests/` | Список заявок (основной view) | `RequestsView` |
| GET | `/requests/my/` | Мои заявки | `my_requests` |
| GET | `/requests/all/` | Все заявки | `all_requests` |
| GET/POST | `/requests/new/` | Создать заявку | `request_create` |
| GET | `/requests/<int:pk>/` | Детали заявки | `request_detail` |
| POST | `/requests/<int:pk>/process/` | Обработать заявку | `request_process` |
| POST | `/requests/<int:pk>/cancel/` | Отменить заявку | `request_cancel` |
| GET | `/requests/comments/<int:pk>/` | Комментарии к заявке | `request_comments` |
| POST | `/requests/comments/<int:pk>/add/` | Добавить комментарий | `request_comment_add` |
| POST | `/requests/<int:pk>/comments/add/` | Добавить комментарий (альт.) | `request_comment_add` |
| POST | `/requests/<int:pk>/comments/<int:comment_id>/delete/` | Удалить комментарий | `request_comment_delete` |

---

## 👥 Сотрудники (`/employees/`)

### Frontend
| Метод | URL | Описание | View |
|-------|-----|----------|------|
| GET | `/employees/list/` | Список сотрудников | `employee_list` |
| GET | `/employees/me/` | Мой профиль | `employee_profile` |
| GET/POST | `/employees/me/edit/` | Редактировать профиль | `employee_edit_me` |
| GET | `/employees/<int:pk>/` | Профиль сотрудника | `employee_profile` |
| GET/POST | `/employees/<int:pk>/edit/` | Редактировать сотрудника | `employee_edit` |
| GET/POST | `/employees/create/` | Создать сотрудника | `employee_create` |
| GET/POST | `/employees/create/modal/` | Создать (модальное окно) | `employee_create_modal` |

#### Группы
| Метод | URL | Описание | View |
|-------|-----|----------|------|
| POST | `/employees/employees/<int:pk>/groups/bulk/` | Массовое управление группами | `employee_groups_bulk` |
| POST | `/employees/groups/create/` | Создать группу | `group_create` |
| POST | `/employees/groups/delete/` | Удалить группу | `group_delete` |

#### Отделы
| Метод | URL | Описание | View |
|-------|-----|----------|------|
| GET | `/employees/departments/` | Список отделов | `department_list` |
| GET | `/employees/departments/<int:pk>/` | Детали отдела | `department_detail` |
| POST | `/employees/departments/create/` | Создать отдел | `department_create` |
| GET/POST | `/employees/departments/<int:pk>/edit/` | Редактировать отдел | `department_edit` |
| POST | `/employees/departments/<int:pk>/set-head/` | Назначить руководителя | `department_set_head` |
| POST | `/employees/departments/<int:pk>/roles/edit/` | Изменить роль в отделе | `edit_department_role` |
| POST | `/employees/<int:emp_id>/departments/<int:dept_id>/set-role/` | Установить роль члена | `set_member_role` |
| POST | `/employees/departments/<int:pk>/add-member/` | Добавить сотрудника | `department_add_member` |
| POST | `/employees/departments/<int:pk>/remove-member/` | Удалить сотрудника | `department_remove_member` |

#### Навыки
| Метод | URL | Описание | View |
|-------|-----|----------|------|
| POST | `/employees/<int:pk>/skill/add/` | Добавить навык | `skill_add` |
| POST | `/employees/<int:pk>/skill/remove/` | Удалить навык | `skill_remove` |

#### Должности
| Метод | URL | Описание | View |
|-------|-----|----------|------|
| POST | `/employees/positions/create/` | Создать должность | `position_create_front` |
| GET | `/employees/positions/<int:pos_id>/` | Детали должности | `position_detail_front` |
| POST | `/employees/positions/<int:pos_id>/update/` | Обновить должность | `position_update_front` |
| POST | `/employees/<int:emp_id>/set-position/` | Установить должность | `employee_set_position_front` |
| POST | `/employees/me/set-position/` | Установить свою должность | `employee_set_position_me_front` |

---

## 💬 Мессенджер (`/communications/`)

### Frontend
| Метод | URL | Описание | View |
|-------|-----|----------|------|
| GET | `/communications/chats/` | Список чатов | `ChatListView` |
| GET | `/communications/chats/<int:pk>/` | Детали чата | `ChatDetailView` |
| GET | `/communications/test/websocket-events/` | Тестирование WebSocket | TemplateView |
| POST | `/communications/chats/start/<int:employee_pk>/` | Начать приватный чат | `start_private_chat` |
| POST | `/communications/start/private/<int:employee_pk>/` | Начать приватный чат (альт.) | `start_private_chat` |
| POST | `/communications/chats/<int:pk>/mark-read/` | Отметить как прочитанное | `chat_mark_read` |

---

## 🔔 Уведомления (`/notifications/`)

### Frontend
| Метод | URL | Описание | View |
|-------|-----|----------|------|
| GET | `/notifications/` | Список уведомлений | `notification_list` |
| GET/POST | `/notifications/settings/` | Настройки уведомлений | `notification_settings` |
| POST | `/notifications/test/create/` | Создать тестовое уведомление | `create_test_notification` |

---

## 🔍 Поиск (`/search/`)

### Frontend
| Метод | URL | Описание | View |
|-------|-----|----------|------|
| GET | `/search/` | Глобальный поиск | `search_view` |

---

## 💰 Финансы (`/finance/`)

### Frontend
| Метод | URL | Описание | View |
|-------|-----|----------|------|
| GET | `/finance/` | Панель финансов | `finance_dashboard` |

---

## 📰 Лента новостей (`/` - feed)

### Frontend
| Метод | URL | Описание | View |
|-------|-----|----------|------|
| GET | `/` | Главная лента | `feed_list` |
| GET | `/departments/<int:pk>/` | Лента отдела | `department_feed` |
| GET | `/employees/<int:pk>/` | Лента сотрудника | `employee_feed` |
| GET | `/post/<int:pk>/` | Детали поста | `post_detail` |
| POST | `/post/<int:pk>/pin/` | Закрепить пост | `pin_post` |
| POST | `/post/<int:pk>/like/` | Лайк/дизлайк поста | `toggle_like` |

---

## 🔌 API (`/api/`)

### Аутентификация API
| Метод | URL | Описание | View |
|-------|-----|----------|------|
| POST | `/api/auth/token/` | Получить JWT токен | `PhoneOrEmailTokenObtainPairView` |
| POST | `/api/auth/token/refresh/` | Обновить JWT токен | `TokenRefreshView` |

---

## 🔌 API v1 (`/api/v1/`)

### Аутентификация
| Метод | URL | Описание | View |
|-------|-----|----------|------|
| POST | `/api/v1/auth/register/` | Регистрация | `RegisterAPIView` |
| POST | `/api/v1/auth/resend-email/` | Повторная отправка email | `ResendEmailAPIView` |
| POST | `/api/v1/auth/verify-email/` | Подтверждение email | `VerifyEmailAPIView` |

### Календарь
| Метод | URL | Описание | ViewSet |
|-------|-----|----------|---------|
| GET/POST | `/api/v1/calendar/events/` | Список/создание событий | `CalendarEventsViewSet` |
| GET/PUT/PATCH/DELETE | `/api/v1/calendar/events/<int:pk>/` | CRUD события | `CalendarEventsViewSet` |

### Документы
| Метод | URL | Описание | ViewSet |
|-------|-----|----------|---------|
| GET/POST | `/api/v1/documents/` | Список/создание документов | `DocumentViewSet` |
| GET/PUT/PATCH/DELETE | `/api/v1/documents/<int:pk>/` | CRUD документа | `DocumentViewSet` |

### Заявки
| Метод | URL | Описание | ViewSet |
|-------|-----|----------|---------|
| GET/POST | `/api/v1/requests/` | Список/создание заявок | `RequestViewSet` |
| GET/PUT/PATCH/DELETE | `/api/v1/requests/<int:pk>/` | CRUD заявки | `RequestViewSet` |

### Отделы
| Метод | URL | Описание | ViewSet |
|-------|-----|----------|---------|
| GET/POST | `/api/v1/departments/` | Список/создание отделов | `DepartmentViewSet` |
| GET/PUT/PATCH/DELETE | `/api/v1/departments/<int:pk>/` | CRUD отдела | `DepartmentViewSet` |

### Сотрудники
| Метод | URL | Описание | ViewSet |
|-------|-----|----------|---------|
| GET/POST | `/api/v1/employees/` | Список/создание сотрудников | `EmployeeViewSet` |
| GET/PUT/PATCH/DELETE | `/api/v1/employees/<int:pk>/` | CRUD сотрудника | `EmployeeViewSet` |
| GET/POST | `/api/v1/employee-actions/` | Действия сотрудников | `EmployeeActionViewSet` |

### Должности
| Метод | URL | Описание | ViewSet |
|-------|-----|----------|---------|
| GET/POST | `/api/v1/positions/` | Список/создание должностей | `PositionViewSet` |
| GET/PUT/PATCH/DELETE | `/api/v1/positions/<int:pk>/` | CRUD должности | `PositionViewSet` |

### Роли в отделах
| Метод | URL | Описание | ViewSet |
|-------|-----|----------|---------|
| GET/POST | `/api/v1/department-roles/` | Список/создание ролей | `DepartmentRoleViewSet` |
| GET/PUT/PATCH/DELETE | `/api/v1/department-roles/<int:pk>/` | CRUD роли | `DepartmentRoleViewSet` |

### Навыки
| Метод | URL | Описание | ViewSet |
|-------|-----|----------|---------|
| GET/POST | `/api/v1/skills/` | Список/создание навыков | `SkillViewSet` |
| GET/PUT/PATCH/DELETE | `/api/v1/skills/<int:pk>/` | CRUD навыка | `SkillViewSet` |

### Группы
| Метод | URL | Описание | ViewSet |
|-------|-----|----------|---------|
| GET/POST | `/api/v1/groups/` | Список/создание групп | `GroupViewSet` |
| GET/PUT/PATCH/DELETE | `/api/v1/groups/<int:pk>/` | CRUD группы | `GroupViewSet` |

### Лента
| Метод | URL | Описание | ViewSet |
|-------|-----|----------|---------|
| GET/POST | `/api/v1/posts/` | Список/создание постов | `PostViewSet` |
| GET/PUT/PATCH/DELETE | `/api/v1/posts/<int:pk>/` | CRUD поста | `PostViewSet` |
| GET/POST | `/api/v1/comments/` | Список/создание комментариев | `CommentViewSet` |
| GET/PUT/PATCH/DELETE | `/api/v1/comments/<int:pk>/` | CRUD комментария | `CommentViewSet` |

### Мессенджер API
| Метод | URL | Описание | View |
|-------|-----|----------|------|
| GET | `/api/v1/communications/chats/` | Список чатов пользователя | `get_user_chats` |
| POST | `/api/v1/communications/chats/create/` | Создать чат | `create_chat` |
| GET | `/api/v1/communications/chats/<int:pk>/messages/` | Загрузить сообщения чата | `load_chat_messages` |
| POST | `/api/v1/communications/chats/<int:chat_id>/pin/` | Закрепить/открепить чат | `pin_chat` |
| POST | `/api/v1/communications/upload-message/` | Отправить сообщение с файлами | `upload_message_with_attachments` |

#### Реакции
| Метод | URL | Описание | View |
|-------|-----|----------|------|
| GET | `/api/v1/communications/reactions/available/` | Доступные реакции | `get_available_reactions` |
| GET | `/api/v1/communications/messages/<int:message_id>/reactions/` | Реакции на сообщение | `get_message_reactions` |
| POST | `/api/v1/communications/messages/<int:message_id>/react/` | Добавить реакцию | `add_reaction` |
| DELETE | `/api/v1/communications/messages/<int:message_id>/unreact/` | Удалить реакцию | `remove_reaction` |

#### Операции с сообщениями
| Метод | URL | Описание | View |
|-------|-----|----------|------|
| PUT/PATCH | `/api/v1/communications/messages/<int:message_id>/edit/` | Редактировать сообщение | `edit_message` |
| DELETE | `/api/v1/communications/messages/<int:message_id>/delete/` | Удалить сообщение | `delete_message` |
| POST | `/api/v1/communications/messages/forward/` | Переслать сообщения | `forward_messages` |
| POST | `/api/v1/communications/messages/bulk-delete/` | Массовое удаление | `bulk_delete_messages` |

#### Опросы
| Метод | URL | Описание | View |
|-------|-----|----------|------|
| POST | `/api/v1/communications/polls/create/` | Создать опрос | `create_poll` |
| POST | `/api/v1/communications/polls/<int:poll_id>/vote/` | Проголосовать | `vote_poll` |
| POST | `/api/v1/communications/polls/<int:poll_id>/close/` | Закрыть опрос | `close_poll` |
| GET | `/api/v1/communications/polls/<int:poll_id>/results/` | Результаты опроса | `get_poll_results` |

### Уведомления API
| Метод | URL | Описание | View |
|-------|-----|----------|------|
| GET | `/api/notifications/` | Список уведомлений | `get_notifications` |
| GET | `/api/notifications/count/` | Количество непрочитанных | `get_unread_count` |
| POST | `/api/notifications/<int:notification_id>/read/` | Отметить как прочитанное | `mark_as_read` |
| POST | `/api/notifications/read-all/` | Отметить все прочитанными | `mark_all_as_read` |
| DELETE | `/api/notifications/<int:notification_id>/` | Удалить уведомление | `delete_notification` |
| GET | `/api/notifications/categories/` | Категории уведомлений | `get_categories` |
| GET | `/api/notifications/settings/` | Получить настройки | `get_user_settings` |
| PUT | `/api/notifications/settings/update/` | Обновить настройки | `update_user_settings` |
| PUT | `/api/notifications/settings/category/update/` | Обновить настройки категории | `update_category_settings` |

#### Telegram интеграция
| Метод | URL | Описание | View |
|-------|-----|----------|------|
| GET | `/api/notifications/telegram/status/` | Статус привязки Telegram | `get_telegram_link_status` |
| POST | `/api/notifications/telegram/generate-code/` | Сгенерировать код привязки | `generate_telegram_link_code` |
| POST | `/api/notifications/telegram/unlink/` | Отвязать Telegram аккаунт | `unlink_telegram` |

---

## 🎯 Админка

| URL | Описание |
|-----|----------|
| `/admin/` | Django Admin Panel |

---

## 📊 Статистика

**Всего эндпоинтов:** ~158+

### По разделам:
- **Аутентификация (Frontend):** 9
- **Аутентификация (API):** 5
- **Документы:** 2
- **Заявки (Frontend):** 11
- **Заявки (API):** ViewSet (5 методов)
- **Сотрудники (Frontend):** 24
- **Сотрудники (API):** 3 ViewSets + endpoints
- **Мессенджер (Frontend):** 6
- **Мессенджер (API):** 19
- **Уведомления (Frontend):** 3
- **Уведомления (API):** 12 (9 основных + 3 Telegram)
- **Поиск:** 1
- **Финансы:** 1
- **Лента (Frontend):** 6
- **Лента (API):** 2 ViewSets
- **Календарь (API):** 1 ViewSet
- **Прочие ViewSets:** 7
- **WebSocket:** 1 endpoint

---

## 🔗 WebSocket

### Realtime (Django Channels)
- **URL Pattern:** `ws://your-domain/ws/` (WebSocket)
- **Consumer:** `UserConsumer` (realtime.consumers)
- **Функции:** 
  - Чаты и сообщения в реальном времени
  - Уведомления в реальном времени
  - Обновление бейджей
  - Онлайн-статус пользователей
  - Другие real-time события

---

## 📝 Примечания

1. **ViewSet endpoints** включают стандартные операции CRUD:
   - `list` (GET на коллекцию)
   - `create` (POST на коллекцию)
   - `retrieve` (GET на элемент)
   - `update` (PUT на элемент)
   - `partial_update` (PATCH на элемент)
   - `destroy` (DELETE на элемент)

2. **Namespace structure:**
   ```
   api:v1:endpoint_name
   auth_front:login
   employees:profile
   communications:chat_list
   etc.
   ```

3. **API Authentication:**
   - JWT токены для API (`/api/auth/token/`)
   - Session auth для Frontend views

4. **Media files:** Доступны по `/media/` (настроено через `static()`)

---

**Сгенерировано:** 26 декабря 2025 г.
