# Инструкции для GitHub Copilot

## О проекте

**EUSRR** - корпоративная система управления на Django с интеграцией LDAP, документооборотом, мессенджером и системой заявок.

### Технологический стек:
- **Backend**: Django 5.2.4, Django REST Framework, Django Channels (WebSocket)
- **Frontend**: Bootstrap 5, Vanilla JavaScript (ES6+ модули)
- **База данных**: PostgreSQL / SQLite (для разработки)
- **Python**: 3.12+ (текущая версия в venv: 3.12.10)

### Структура проекта:
- `backend/` - Django приложение
- `backend/manage.py` - управление Django проектом
- `backend/eusrr_backend/` - основные настройки
- `backend/api/`, `employees/`, `documents/`, `feed/`, `requests_app/` и др. - Django приложения

## Виртуальное окружение Python

В этом проекте используется виртуальное окружение Python, расположенное в `.venv/`.

### Важные правила при работе с Python:

1. **Всегда используйте полный путь** к Python и pip из виртуального окружения
2. **Никогда не используйте** команды `python` или `pip` без указания полного пути

### Примеры:

❌ **Неправильно:**
```bash
python manage.py runserver
pip install django
```

✅ **Правильно:**
```bash
.venv/Scripts/python manage.py runserver
.venv/Scripts/pip install django
```

### Пути к исполняемым файлам:

- Python: `.venv/Scripts/python`
- pip: `.venv/Scripts/pip`

**Всегда используй эти полные пути вместо команд `python` и `pip`**

## Правила работы с документацией

### ⚠️ КРИТИЧНО: НЕ создавай новые MD файлы в корневых папках!

**Проблема:** Создание отчетов и документации в корне проекта или корне backend/ захламляет структуру.

### Правила размещения документации:

❌ **НЕПРАВИЛЬНО:**
```
PROJECT_REPORT.md                    # В корне проекта
backend/AUDIT_REPORT.md              # В корне backend/
backend/CLEANUP_SUMMARY.md           # В корне backend/
```

✅ **ПРАВИЛЬНО:**
```
docs/reports/PROJECT_REPORT.md       # Отчеты в специальной папке
backend/docs/reports/AUDIT_REPORT.md # Отчеты backend в своей папке
docs/in-progress/TASK_PROGRESS.md    # Активные задачи
```

### Структура для новой документации:

**Корневая документация проекта:**
- `docs/completed/` - завершенные задачи и фичи
- `docs/guides/` - руководства разработчика
- `docs/architecture/` - архитектурная документация
- `docs/diagnostic/` - диагностические гайды
- `docs/in-progress/` - активные задачи
- `docs/reports/` - отчеты и аудиты

**Backend документация:**
- `backend/docs/guides/` - руководства по backend
- `backend/docs/troubleshooting/` - решение проблем
- `backend/docs/architecture/` - архитектура backend
- `backend/docs/testing/` - тестовая документация
- `backend/docs/reports/` - отчеты и аудиты backend

### Когда создаешь новый MD файл:

1. **Определи тип документа:**
   - Отчет/аудит → `docs/reports/` или `backend/docs/reports/`
   - Гайд → `docs/guides/` или `backend/docs/guides/`
   - Завершенная задача → `docs/completed/`
   - Активная задача → `docs/in-progress/`

2. **НИКОГДА не создавай в корне проекта или корне backend/**

3. **Исключения (единственные файлы в корне):**
   - `README.md` - главная документация (уже существует)
   - Только по явному запросу пользователя

### Примеры правильного создания:

```python
# Отчет об аудите backend
create_file("backend/docs/reports/CLEANUP_AUDIT.md", ...)

# Отчет о реорганизации docs
create_file("docs/reports/REORGANIZATION_REPORT.md", ...)

# Новый гайд
create_file("docs/guides/NEW_FEATURE_GUIDE.md", ...)

# Прогресс активной задачи
create_file("docs/in-progress/FEATURE_X_PROGRESS.md", ...)
```
