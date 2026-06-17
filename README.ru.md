**Язык:** [English](README.md) | [Русский](README.ru.md) | [Deutsch](README.de.md) | [Español](README.es.md)

# EUSRR

EUSRR - внутренний корпоративный сервисный портал на Django, Django REST Framework, Next.js, PostgreSQL, Redis, Celery и WebSockets. Проект включает LDAP-интеграцию, уведомления, документооборот, закупочные процессы, календарное планирование и модули самообслуживания сотрудников.

Проект демонстрирует full-stack разработку продукта: backend-архитектуру, REST API, ролевую модель доступа, асинхронные задачи, обновления в реальном времени, структуру frontend-приложения, тестирование, конфигурацию для деплоя и production-style документацию.

## Основные модули

- Справочник сотрудников, профили, отделы, роли и LDAP-синхронизация.
- Заявки и маршруты согласования со статусами и уведомлениями.
- Закупочные процессы, маршруты утверждения, учет позиций и отслеживание поставок.
- Документы, файлы, комментарии и внутреннее взаимодействие.
- Календарь и планирование с общими событиями.
- Коммуникации в реальном времени, WebSocket-уведомления и chat-oriented workflows.
- Интеграция с LogStorm для аналитики посещаемости.

## Стек

- Backend: Python, Django, Django REST Framework, Channels, Celery, Redis, PostgreSQL.
- Frontend: Next.js, React, TypeScript, Tailwind CSS, Recharts, React Table.
- Integrations: LDAP, Web Push, Telegram/Synology-style notification adapters, LogStorm API.
- Testing: pytest для backend-тестов, Node test runner и ESLint для frontend-проверок.
- Deployment: Docker-oriented settings, environment-based configuration, Nginx-ready service layout.

## Структура репозитория

```text
backend/   Django backend, APIs, Celery tasks, migrations, tests, docs
frontend/  Next.js frontend application
docs/      Architecture notes, implementation reports, guides, diagnostics
```

## Локальный запуск

Backend:

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp ../.env.example ../.env
python manage.py migrate
python manage.py runserver
```

Frontend:

```bash
cd frontend
npm install
cp .env.example .env.local
npm run dev
```

Frontend открывается на `http://localhost:3000`. Переменная `NEXT_PUBLIC_BACKEND_URL` должна указывать на backend.

## Проверка

Backend:

```bash
cd backend
pytest
```

Frontend:

```bash
cd frontend
npm test
npm run lint
npm run build
```

## Security Notes

Публичная версия подготовлена как portfolio snapshot. Env-файлы, локальные базы данных, media uploads, certificates, private keys, generated builds и deployment-specific artifacts исключены из version control.

Все credentials должны передаваться через environment variables. Example-файлы содержат только placeholders и не должны использоваться как production secrets.

## Demo Data

Репозиторий не содержит production data. Любые company-specific values нужно заменить локальными demo data перед запуском вне исходной среды.
