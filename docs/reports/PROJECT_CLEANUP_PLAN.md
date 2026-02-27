# План наведения порядка в проекте EUSRR

**Дата создания:** 26 декабря 2025 г.
**Статус:** Требуется выполнение

---

## 🎯 Критические задачи (безопасность)

### 1. **КРИТИЧНО: Защита секретных данных**
**Приоритет:** 🔴 ВЫСОКИЙ

**Проблема:** Файл `backend/.env` содержит реальные секретные данные в открытом виде:
- SECRET_KEY Django
- Токены Telegram бота
- SMS API токены
- Пароли баз данных
- Email конфигурация

**Действия:**
- [ ] Создать `backend/.env.example` с шаблонами переменных
- [ ] Убедиться что `.env` в `.gitignore`
- [ ] Проверить историю git - не был ли `.env` закоммичен
- [ ] Если был - сменить все токены и пароли
- [ ] Добавить документацию по настройке окружения

---

## 📁 Структура и организация

### 2. **Реорганизация документации (100+ MD файлов)**
**Приоритет:** 🟡 СРЕДНИЙ

**Проблема:** В корне проекта 47+ MD файлов без структуры

**Предлагаемая структура:**
```
docs/
├── completed/           # 22 завершенных задачи
│   ├── refactoring/
│   ├── fixes/
│   └── features/
├── guides/              # 4 активных гайда
├── architecture/        # 2 архитектурных документа
├── diagnostic/          # 4 диагностических гайда
└── in-progress/         # Активные задачи
```

**Файлы для архивирования (завершенные):**
- BASE_TEMPLATE_REFACTORING_COMPLETE.md
- CHAT_LIST_REFACTORING_COMPLETE.md
- DOCUMENTS_REFACTORING_COMPLETE.md
- JS_MODULES_REFACTORING_COMPLETE.md
- REFACTORING_SUMMARY.md
- CHAT_CACHING_FIX.md
- CHAT_LIST_BUGS_FIX.md
- FOUC_FIX.md
- MESSAGE_NEWLINES_FIX.md
- POLL_WEBSOCKET_FIX.md
- WEBSOCKET_ERROR_FIX.md
- WEBSOCKET_KEEPALIVE_FIX.md
- AVATAR_CROPPER_IMPLEMENTATION.md
- FEED_AJAX_REFACTORING.md
- FORWARDED_MESSAGE_METADATA.md
- MESSAGE_EDITING_FULL_RERENDER.md
- MESSAGE_RENDERING_REFACTORING.md
- MESSAGE_SELECTION_FORWARDING.md
- MESSAGE_SENDING_REFACTORING.md
- POLLS_IMPLEMENTATION.md
- REACTIONS_FROM_DATABASE.md
- REPLY_UPDATE_ON_EDIT.md

**Дубликаты для объединения:**

1. **Кэширование** (3 файла → 1):
   - CACHE_OPTIMIZATION_SUMMARY.md
   - CACHING_SETUP.md  
   - API_REFACTORING_TESTING.md
   → Объединить в `docs/guides/CACHING_COMPLETE.md`

2. **Chat List** (2 файла):
   - CHAT_LIST_RENDERING_ANALYSIS.md (удалить)
   - CHAT_LIST_REFACTORING_COMPLETE.md (оставить)

3. **Base Template** (2 файла):
   - BASE_TEMPLATE_REFACTORING.md (удалить)
   - BASE_TEMPLATE_REFACTORING_COMPLETE.md (оставить)

4. **IP ограничения** (2 файла → 1):
   - IP_RESTRICTIONS_README.md
   - IP_REGISTRATION_RESTRICTIONS.md
   → Объединить в `docs/guides/IP_RESTRICTIONS.md`

5. **Редактирование сообщений** (4 файла → 1):
   - MESSAGE_EDITING_ANALYSIS.md
   - MESSAGE_EDITING_FULL_RERENDER.md
   - EDITING_ATTACHMENTS_TROUBLESHOOTING.md
   - REPLY_UPDATE_ON_EDIT.md
   → Объединить в `docs/completed/MESSAGE_EDITING_COMPLETE.md`

6. **Рендеринг сообщений** (2 файла → 1):
   - MESSAGE_RENDERING_REFACTORING.md
   - MESSAGE_SENDING_REFACTORING.md
   → Объединить в `docs/completed/MESSAGE_SYSTEM_REFACTORING_COMPLETE.md`

7. **Документы** (2 файла):
   - DOCUMENTS_MODAL_ANALYSIS.md (удалить)
   - DOCUMENTS_REFACTORING_COMPLETE.md (оставить)

8. **Опросы** (2 файла):
   - POLL_LOADING_ANALYSIS.md (удалить)
   - POLLS_IMPLEMENTATION.md (оставить)

**Файлы для удаления:**
- SELECTION_FIXES.md (пустой файл)

**Действия:**
- [ ] Создать структуру папок `docs/`
- [ ] Переместить завершенные задачи в `docs/completed/`
- [ ] Переместить гайды в `docs/guides/`
- [ ] Объединить дубликаты
- [ ] Удалить устаревшие файлы
- [ ] Оставить в корне только README.md

---

### 3. **Чистка тестовых и диагностических скриптов**
**Приоритет:** 🟡 СРЕДНИЙ

**Проблема:** В `backend/` более 20 тестовых скриптов вперемешку с основным кодом

**Найденные файлы:**
```
backend/
├── test_*.py (22 файла)
├── check_*.py (5 файлов)
├── analyze_*.py (1 файл)
├── create_test_data.py
├── diagnose_page.py
├── diagnostic_summary.py
├── generate_notification.py
├── quick_test.py
├── render_test_page.py
├── simple_create_users.py
└── ...
```

**Действия:**
- [ ] Переместить все `test_*.py` в `backend/tests/manual/`
- [ ] Переместить `check_*.py` в `backend/scripts/diagnostic/`
- [ ] Переместить утилиты в `backend/scripts/utils/`
- [ ] Создать README в каждой папке со списком скриптов
- [ ] Удалить неиспользуемые скрипты

---

## 💻 Код и разработка

### 4. **Завершить TODO в коде**
**Приоритет:** 🟠 СРЕДНЕ-ВЫСОКИЙ

**Найдено:** 10 TODO/FIXME комментариев

**Python (10 штук):**

1. **realtime/consumers.py:606**
   ```python
   # TODO: Реализовать логику голосования
   ```

2. **realtime/consumers.py:747**
   ```python
   # TODO: Реализовать через Redis для производительности
   ```

3. **feed/notification_signals.py:130**
   ```python
   # TODO: реализовать систему подписок
   ```

4. **employees/ldap/services/sync_service.py:437**
   ```python
   # TODO: Реализовать через UserService
   ```

5. **employees/ldap/services/user_service.py:123**
   ```python
   # TODO: Убрать после полного рефакторинга
   ```

6. **documents/views.py:305**
   ```python
   # TODO: добавить проверку членства в отделе через отдельный API запрос
   ```

7-10. **api/v1/communications/poll_views.py** (4 штуки):
   ```python
   # TODO: проверить права пользователя на отправку в чат (L80)
   # TODO: проверить user_can_access_chat (L242)
   # TODO: проверить модераторские права (L343)
   # TODO: user_can_access_chat (L385)
   ```

**JavaScript (5 штук):**

1-4. **chatMenuActions.js** (4 штуки):
   ```javascript
   // TODO: Реализовать API endpoint для закрепления (L77)
   // TODO: Реализовать API endpoint для управления уведомлениями (L109)
   // TODO: Создать страницу редактирования чата (L134)
   // TODO: Реализовать API endpoint для удаления (L144)
   ```

5. **requestCrudHandler.js:161**
   ```javascript
   alert(message); // TODO: заменить на toast-уведомление
   ```

**Действия:**
- [ ] Создать GitHub Issues для каждого TODO
- [ ] Приоритизировать задачи
- [ ] Реализовать критичные TODO (проверки прав доступа)
- [ ] Удалить устаревшие TODO после рефакторинга

---

### 5. **Рефакторинг LDAP модуля**
**Приоритет:** 🟡 СРЕДНИЙ

**Найдено:** Много NOTE комментариев о необходимости рефакторинга

**Проблемные файлы:**
- `employees/ldap/services/user_service.py:591` - метод >150 строк
- `employees/ldap/directory_service.py` - постепенный рефакторинг в процессе

**Действия:**
- [ ] Завершить рефакторинг UserService
- [ ] Разбить большие методы на более мелкие
- [ ] Удалить устаревший код после рефакторинга

---

### 6. **Улучшение тестирования**
**Приоритет:** 🟢 НИЗКИЙ

**Обнаружено:** 75+ тестовых файлов

**Проблемы:**
- Тесты разбросаны по разным местам
- Нет единой документации по запуску тестов
- Некоторые тесты пропущены (требуют мокирования LDAP)

**Действия:**
- [ ] Создать `docs/testing/TESTING_GUIDE.md`
- [ ] Документировать команды запуска тестов
- [ ] Настроить CI/CD для автоматического тестирования
- [ ] Добавить покрытие кода тестами

---

## 🔧 Конфигурация и инфраструктура

### 7. **Настройка виртуального окружения**
**Приоритет:** ✅ ВЫПОЛНЕНО

- [x] Создано виртуальное окружение `.venv/`
- [x] Настроена автоматическая активация в VS Code
- [x] Создан файл инструкций `.github/copilot-instructions.md`

---

### 8. **Обновление зависимостей**
**Приоритет:** 🟢 НИЗКИЙ

**Текущие версии выглядят актуальными:**
- Django 5.2.4 ✅
- Python 3.12.10 ✅
- Bootstrap 5.3.3 ✅
- Node packages актуальны ✅

**Действия:**
- [ ] Периодически проверять обновления безопасности
- [ ] Настроить Dependabot в GitHub

---

### 9. **Docker и развертывание**
**Приоритет:** 🟡 СРЕДНИЙ

**Найдено:**
- Dockerfile существует
- docker-compose.test.yml присутствует
- Основной docker-compose.yml отсутствует в корне

**Действия:**
- [ ] Проверить работоспособность Docker конфигурации
- [ ] Создать production-ready docker-compose.yml
- [ ] Документировать процесс развертывания
- [ ] Добавить health checks в контейнеры

---

### 10. **Настройка .gitignore**
**Приоритет:** 🟢 НИЗКИЙ

**Текущее состояние:** Базовый .gitignore присутствует

**Рекомендации:**
- [ ] Проверить что все временные файлы игнорируются
- [ ] Добавить `.vscode/` (опционально)
- [ ] Убедиться что `node_modules/` игнорируется
- [ ] Добавить `media/` для локальной разработки

---

## 📊 Итоговая статистика

**Найдено проблем:**
- 🔴 Критичных: 1 (секретные данные)
- 🟠 Высокий приоритет: 1 (TODO в коде)
- 🟡 Средний приоритет: 5 (структура, скрипты, LDAP, Docker, documents)
- 🟢 Низкий приоритет: 3 (тестирование, зависимости, gitignore)

**Файлы для реорганизации:**
- 47 MD файлов в корне
- 22 завершенных задачи для архивирования
- 14 дубликатов для объединения
- 27+ тестовых скриптов для перемещения

**TODO в коде:**
- 10 Python TODO
- 5 JavaScript TODO

---

## 🎬 Рекомендуемый порядок выполнения

1. **Безопасность (день 1)** - Защита .env файла
2. **Структура документации (день 1-2)** - Создание папок и перемещение файлов
3. **Чистка скриптов (день 2)** - Организация тестовых файлов
4. **Критичные TODO (неделя 1)** - Проверки прав доступа в API
5. **Рефакторинг LDAP (неделя 2-3)** - Улучшение кода
6. **Docker и CI/CD (неделя 3-4)** - Инфраструктура
7. **Остальные TODO (ongoing)** - По мере необходимости

---

## 💡 Дополнительные рекомендации

### Автоматизация
- Настроить pre-commit hooks для проверки кода
- Добавить автоматическое форматирование (black, isort)
- Настроить линтеры (flake8, eslint)

### Мониторинг
- Добавить логирование критичных операций
- Настроить Sentry для отслеживания ошибок
- Добавить метрики производительности

### Документация
- Создать CONTRIBUTING.md для новых разработчиков
- Документировать API через Swagger/OpenAPI
- Добавить архитектурные диаграммы

---

**Примечание:** Этот план можно выполнять поэтапно. Начните с критичных задач (безопасность) и постепенно двигайтесь к улучшениям.
