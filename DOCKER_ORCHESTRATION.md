# EUSRR Docker Orchestration Guide

## Обзор архитектуры

Проект EUSRR теперь имеет полную оркестрацию с использованием Docker Compose:

```
┌─────────────┐
│   Nginx     │ :80 - Reverse Proxy
│  (Gateway)  │
└──────┬──────┘
       │
       ├──────────┐
       │          │
┌──────▼──────┐ ┌─▼────────────┐
│   Frontend  │ │   Backend    │
│  (Next.js)  │ │   (Django)   │
│    :3000    │ │    :8000     │
└──────┬──────┘ └──┬─────┬─────┘
       │           │     │
       └───────┬───┘     │
               │         │
        ┌──────▼───┐  ┌──▼────┐
        │   Redis  │  │   DB  │
        │  :6379   │  │ :5432 │
        └──────────┘  └────────┘
```

## Сервисы

### 1. **db** (PostgreSQL 16)
- Порт: `5432`
- База данных Django
- Persistent volume: `postgres_data`

### 2. **redis** (Redis 7)
- Порт: `6379`
- Кэш и Channels backend
- Persistent volume: `redis_data`

### 3. **web** (Django Backend)
- Порт: `8000`
- ASGI сервер (Daphne)
- REST API + WebSocket
- Подключается к `db` и `redis`

### 4. **celery** (Celery Worker)
- Фоновые задачи
- Подключается к `redis` и `db`

### 5. **celery-beat** (Celery Scheduler)
- Планировщик задач
- Django Celery Beat

### 6. **frontend** (Next.js)
- Порт: `3000`
- Корпоративный фронтенд
- Использует `web` backend через proxy

### 7. **nginx** (Reverse Proxy)
- Порт: `80` (основной вход)
- Маршрутизация:
  - `/` → Frontend (Next.js)
  - `/api/` → Backend API
  - `/admin/` → Django Admin
  - `/ws/` → WebSocket
  - `/static/`, `/media/` → Статика

## Быстрый старт

### Запуск всех сервисов

```bash
# Создайте .env файл из примера
cp .env.example .env

# Запустите все сервисы
docker-compose up -d

# Просмотр логов
docker-compose logs -f
```

### Доступ к приложению

- **Основной вход (через Nginx)**: http://localhost
- **Frontend напрямую**: http://localhost:3000
- **Backend API**: http://localhost:8000/api/
- **Django Admin**: http://localhost/admin/

### Остановка

```bash
# Остановка всех сервисов
docker-compose down

# Остановка с удалением volumes
docker-compose down -v
```

## Конфигурация

### Environment Variables

Основные переменные в `.env`:

```env
# Database
POSTGRES_DB=eusrr
POSTGRES_USER=eusrr_user
POSTGRES_PASSWORD=change-me-postgres-password

# Django
DEBUG=True
SECRET_KEY=dev-secret-key
ALLOWED_HOSTS=localhost,127.0.0.1,web,nginx

# Ports
WEB_PORT=8000
FRONTEND_PORT=3000
NGINX_PORT=80
```

### Frontend Environment

Файл `corp.front/.env.local`:

```env
NEXT_PUBLIC_API_URL=http://web:8000
NEXT_PUBLIC_WS_URL=ws://web:8000
```

## Разработка

### Режим разработки

```bash
# Backend отдельно (с hot-reload)
cd backend
../.venv/Scripts/python manage.py runserver

# Frontend отдельно (с hot-reload)
cd corp.front
npm run dev
```

### Режим Production

```bash
# Полная оркестрация через Docker
docker-compose up -d
```

## Миграции и первичная настройка

```bash
# Выполнить миграции
docker-compose exec web python manage.py migrate

# Создать суперпользователя
docker-compose exec web python manage.py createsuperuser

# Собрать статику
docker-compose exec web python manage.py collectstatic --noinput
```

## Мониторинг

```bash
# Статус сервисов
docker-compose ps

# Логи конкретного сервиса
docker-compose logs -f web
docker-compose logs -f frontend
docker-compose logs -f nginx

# Использование ресурсов
docker stats
```

## Отладка

### Проверка сети

```bash
# Проверить связь frontend → backend
docker-compose exec frontend ping web

# Проверить связь backend → db
docker-compose exec web pg_isready -h db -U eusrr_user
```

### Доступ к контейнерам

```bash
# Backend shell
docker-compose exec web bash
docker-compose exec web python manage.py shell

# Frontend shell
docker-compose exec frontend sh

# Database
docker-compose exec db psql -U eusrr_user -d eusrr
```

## Volumes

Persistent данные сохраняются в volumes:

- `postgres_data` - база данных
- `redis_data` - Redis данные
- `static_volume` - статические файлы Django
- `media_volume` - загруженные медиафайлы

## Сеть

Все сервисы находятся в сети `eusrr_network` и могут обращаться друг к другу по именам сервисов:

- `web` - Django backend
- `frontend` - Next.js frontend
- `db` - PostgreSQL
- `redis` - Redis
- `nginx` - Nginx

## Nginx маршрутизация

- `location /` - Next.js фронтенд
- `location /api/` - Django REST API
- `location /admin/` - Django Admin
- `location /ws/` - WebSocket (Django Channels)
- `location /static/` - Статические файлы
- `location /media/` - Медиа файлы
- `location /health` - Health check endpoint

## Production Deployment

Для production окружения:

1. Обновите `.env`:
   - Установите `DEBUG=False`
   - Смените `SECRET_KEY`
   - Обновите `ALLOWED_HOSTS`
   - Используйте надежные пароли БД

2. Настройте HTTPS (добавьте SSL в nginx)

3. Используйте внешние managed сервисы для БД и Redis (опционально)

4. Настройте backup для volumes

## Troubleshooting

### Frontend не может подключиться к backend

Проверьте переменные окружения в `corp.front/.env.local` и убедитесь, что используется правильный URL для Docker сети.

### Backend не запускается

```bash
# Проверьте логи
docker-compose logs web

# Проверьте подключение к БД
docker-compose exec web python manage.py check --database default
```

### Nginx 502 Bad Gateway

Убедитесь, что `web` и `frontend` сервисы запущены:

```bash
docker-compose ps
```

## Файлы конфигурации

- `docker-compose.yml` - Оркестрация сервисов
- `nginx.conf` - Конфигурация Nginx
- `backend/Dockerfile` - Django image
- `corp.front/Dockerfile` - Next.js image
- `.env.example` - Шаблон переменных окружения
- `corp.front/.env.example` - Шаблон для frontend

---

**Дата создания**: 19 февраля 2025
**Версия**: 1.0
