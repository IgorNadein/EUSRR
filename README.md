# EUSRR - Корпоративная система управления

Комплексная корпоративная информационная система с интеграцией Active Directory/LDAP для управления сотрудниками, документами, заявками и внутренними коммуникациями.

## Основные возможности

### 🏢 Управление сотрудниками
- Интеграция с Active Directory через LDAP
- Автоматическая синхронизация данных сотрудников
- Управление отделами и должностями
- Профили сотрудников с фотографиями и контактами
- Иерархия отделов с назначением руководителей

### 📄 Система документооборота
- Загрузка и распространение документов
- Отправка документов всем сотрудникам, конкретным отделам или индивидуально
- Автоматические уведомления о новых документах
- Отслеживание ознакомления с документами
- Визуальное выделение неознакомленных документов

### 📬 Система уведомлений
- Веб-уведомления в реальном времени (WebSocket)
- Email-уведомления с настраиваемой периодичностью (мгновенно, ежедневно, еженедельно)
- Telegram-уведомления через бота
- Индивидуальные настройки уведомлений для каждого пользователя
- Звуковые оповещения о новых уведомлениях

### 📋 Система заявок
- Создание и отслеживание заявок
- Назначение ответственных отделов
- История изменений заявок
- Комментарии и обсуждения

### 💬 Внутренние коммуникации
- Лента новостей организации
- Посты с комментариями
- Упоминания сотрудников (@mention)
- Ленты новостей по отделам

### 📅 Календарь событий
- Корпоративный календарь
- События отделов и общеорганизационные события
- Интеграция с календарем на главной странице

## Технологический стек

### Backend
- **Python 3.13.5**
- **Django 5.2.4** - основной веб-фреймворк
- **Django REST Framework** - REST API
- **Django Channels** - WebSocket поддержка
- **PostgreSQL / SQLite** - база данных
- **python-ldap** - интеграция с Active Directory
- **Celery** (опционально) - асинхронные задачи

### Frontend
- **Bootstrap 5** - UI фреймворк
- **Vanilla JavaScript (ES6+)** - модульная архитектура
- **WebSocket** - реальное время
- **Fetch API** - HTTP запросы

### Интеграции
- **Active Directory (LDAP)** - управление пользователями
- **Telegram Bot API** - уведомления в Telegram
- **SMTP (Yandex)** - email-рассылка
- **SMS Gateway** - SMS-уведомления

## Установка и запуск

### Предварительные требования

- Python 3.11+
- PostgreSQL 14+ или SQLite (для разработки)
- Active Directory (опционально, можно отключить через `LDAP_ENABLED=False`)
- Git

### Установка

1. Клонирование репозитория:
```bash
git clone https://github.com/IgorNadein/EUSRR.git
cd EUSRR
```

2. Создание виртуального окружения:
```bash
python -m venv .venv
source .venv/bin/activate  # Linux/Mac
# или
.venv\Scripts\activate  # Windows
```

3. Установка зависимостей:
```bash
cd backend
pip install -r requirements.txt
```

4. Настройка окружения:
```bash
# Скопируйте .env.example в .env и настройте параметры
cp .env.example .env
```

Основные параметры в `.env`:
```env
# База данных
USE_SQLITE=True  # True для SQLite, False для PostgreSQL

# Django
SECRET_KEY=your-secret-key
DEBUG=True
ALLOWED_HOSTS=localhost,127.0.0.1

# LDAP (можно отключить)
LDAP_ENABLED=False  # True для интеграции с AD

# Email
EMAIL_HOST=smtp.yandex.ru
EMAIL_PORT=465
EMAIL_HOST_USER=your-email@yandex.ru
EMAIL_HOST_PASSWORD=your-password

# Telegram (опционально)
TELEGRAM_BOT_TOKEN=your-bot-token
```

5. Применение миграций:
```bash
python manage.py migrate
```

6. Создание суперпользователя:
```bash
python manage.py createsuperuser
```

7. Сбор статических файлов:
```bash
python manage.py collectstatic --noinput
```

### Запуск разработки

```bash
# Запуск сервера разработки
python manage.py runserver 9000

# В отдельном терминале - Telegram бот (опционально)
python manage.py run_telegram_bot
```

Приложение будет доступно по адресу: http://localhost:9000

### Запуск в продакшене

1. Настройте `.env` для продакшена:
```env
DEBUG=False
USE_SQLITE=False
ALLOWED_HOSTS=your-domain.com
LDAP_ENABLED=True
```

2. Используйте WSGI сервер (Gunicorn):
```bash
pip install gunicorn
gunicorn eusrr_backend.wsgi:application --bind 0.0.0.0:8000
```

3. Настройте веб-сервер (Nginx) как reverse proxy

4. Настройте supervisor/systemd для автозапуска

## Структура проекта

```
EUSRR/
├── backend/                      # Django проект
│   ├── api/                      # REST API
│   │   └── v1/                   # API версия 1
│   │       ├── documents/        # API документов
│   │       ├── employees/        # API сотрудников
│   │       └── ...
│   ├── documents/                # Приложение документов
│   ├── employees/                # Приложение сотрудников
│   ├── notifications/            # Система уведомлений
│   ├── requests_app/             # Система заявок
│   ├── feed/                     # Лента новостей
│   ├── calendar_app/             # Календарь событий
│   ├── communications/           # Коммуникации
│   ├── static/                   # Статические файлы
│   │   ├── css/                  # Стили
│   │   └── js/                   # JavaScript модули
│   ├── templates/                # HTML шаблоны
│   ├── media/                    # Загруженные файлы
│   └── eusrr_backend/            # Настройки Django
└── README.md                     # Этот файл
```

## Основные функции

### Работа с документами

1. **Создание документа:**
   - Загрузка файла
   - Выбор получателей (все/отделы/конкретные сотрудники)
   - Автоматические уведомления

2. **Отслеживание ознакомления:**
   - Клик на документ автоматически отмечает ознакомление
   - Визуальное выделение неознакомленных документов
   - Ведомость ознакомлений для администраторов

### Система уведомлений

1. **Веб-уведомления:**
   - Звуковое оповещение
   - Счётчик непрочитанных
   - Список в реальном времени

2. **Email-уведомления:**
   - Мгновенная отправка
   - Ежедневный дайджест
   - Еженедельный дайджест

3. **Telegram-уведомления:**
   - Привязка аккаунта через код
   - Мгновенная отправка важных уведомлений

### LDAP интеграция

- Двусторонняя синхронизация данных
- Создание пользователей в AD
- Управление отделами через OU
- Автоматическое обновление при изменениях

## API Документация

REST API доступен по адресу `/api/v1/`

Основные эндпоинты:
- `/api/v1/employees/` - Сотрудники
- `/api/v1/departments/` - Отделы
- `/api/v1/documents/` - Документы
- `/api/v1/requests/` - Заявки
- `/api/v1/calendar/events/` - События календаря
- `/api/notifications/` - Уведомления

Документация API: `/api/docs/` (если установлен drf-spectacular)

## Разработка

### Создание миграций
```bash
python manage.py makemigrations
python manage.py migrate
```

### Запуск тестов
```bash
pytest
# или
python manage.py test
```

### Линтинг кода
```bash
flake8 .
black .
isort .
```

## Настройка уведомлений

### Email
Настройте SMTP в `.env`:
```env
EMAIL_HOST=smtp.yandex.ru
EMAIL_PORT=465
EMAIL_USE_SSL=true
EMAIL_HOST_USER=your-email@yandex.ru
EMAIL_HOST_PASSWORD=your-app-password
DEFAULT_FROM_EMAIL=Company <your-email@yandex.ru>
```

### Telegram
1. Создайте бота через @BotFather
2. Получите токен
3. Настройте в `.env`:
```env
TELEGRAM_BOT_TOKEN=123456789:ABCdefGHIjklMNOpqrsTUVwxyz
TELEGRAM_BOT_USERNAME=your_bot_name
```
4. Запустите бота:
```bash
python manage.py run_telegram_bot
```

### Отложенная отправка
Для дайджестов используйте команду:
```bash
python manage.py send_pending_notifications --batch-size=100
```

Настройте cron для автоматического запуска:
```bash
# Ежедневно в 9:00
0 9 * * * /path/to/python /path/to/manage.py send_pending_notifications
```

## Безопасность

- Используйте HTTPS в продакшене
- Настройте CORS правильно
- Используйте сильные пароли
- Регулярно обновляйте зависимости
- Настройте файрвол
- Используйте переменные окружения для секретов

## Лицензия

Проприетарное ПО © 2024-2025 Robotail

## Контакты

- Автор: Игорь Надеин
- GitHub: [@IgorNadein](https://github.com/IgorNadein)
- Проект: [EUSRR](https://github.com/IgorNadein/EUSRR)

## Changelog

### v2.0.0 (21.11.2025)
- ✨ Добавлена возможность отправки документов на отделы
- ✨ Визуальное выделение неознакомленных документов
- ✨ Автоматическое ознакомление при клике на документ
- ✨ Адаптивная мобильная версия
- 🐛 Исправлена фильтрация "Мои документы" для загрузивших
- 🐛 Исправлена ведомость ознакомлений с учётом отделов
- 🔧 Добавлена поддержка массовых рассылок с порогом

### v1.0.0
- 🎉 Первый релиз
- ✨ Базовая система документооборота
- ✨ Интеграция с LDAP
- ✨ Система уведомлений
- ✨ Управление заявками
