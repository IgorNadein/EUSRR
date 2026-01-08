# Инструкция по запуску Celery (Development)

## 📋 Предварительные требования

### 1. Установка Redis

**Windows:**
```bash
# Через WSL2
wsl --install
wsl
sudo apt update
sudo apt install redis-server
redis-server --daemonize yes

# Или скачать с https://github.com/microsoftarchive/redis/releases
```

**Linux/Mac:**
```bash
# Ubuntu/Debian
sudo apt install redis-server
sudo systemctl start redis

# MacOS
brew install redis
brew services start redis
```

**Docker (рекомендуется):**
```bash
docker run -d -p 6379:6379 --name redis redis:7-alpine
```

### 2. Проверка Redis
```bash
redis-cli ping
# Должно вернуть: PONG
```

---

## 🚀 Установка зависимостей

```bash
# Активировать виртуальное окружение
.venv/Scripts/activate  # Windows
source .venv/bin/activate  # Linux/Mac

# Установить новые пакеты
cd backend
pip install -r requirements.txt
```

Новые пакеты:
- `redis` - клиент для Redis
- `django-celery-beat` - периодические задачи
- `django-celery-results` - хранение результатов
- `flower` - веб-интерфейс мониторинга

---

## 🔧 Настройка окружения

### 1. Добавить в `.env`:
```env
# Redis & Celery
REDIS_HOST=localhost
REDIS_PORT=6379
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1
```

### 2. Применить миграции (для django-celery-beat):
```bash
python manage.py migrate django_celery_beat
python manage.py migrate django_celery_results
```

---

## 🏃 Запуск Celery Worker

### Вариант 1: Базовый запуск
```bash
cd backend
celery -A eusrr_backend worker -l info
```

### Вариант 2: С указанием очередей
```bash
celery -A eusrr_backend worker -l info -Q default,notifications,emails
```

### Вариант 3: С autoscale (для production)
```bash
celery -A eusrr_backend worker -l info --autoscale=10,3
# 10 = максимум workers, 3 = минимум workers
```

---

## 🕐 Запуск Celery Beat (периодические задачи)

**Отдельное окно терминала:**
```bash
cd backend
celery -A eusrr_backend beat -l info
```

---

## 🌺 Запуск Flower (мониторинг)

**Отдельное окно терминала:**
```bash
cd backend
celery -A eusrr_backend flower --port=5555
```

Откройте в браузере: http://localhost:5555

---

## 🧪 Тестирование

### 1. Проверка подключения
```bash
cd backend
python manage.py shell
```

```python
from eusrr_backend.celery import debug_task
result = debug_task.delay()
print(f"Task ID: {result.id}")
print(f"Status: {result.status}")
```

### 2. Проверка через Django admin
- Перейти в админку: http://localhost:8000/admin/
- Найти раздел "Periodic Tasks" (от django-celery-beat)
- Создать тестовую задачу

---

## 📊 Мониторинг

### Через Flower (рекомендуется)
- URL: http://localhost:5555
- Видны: активные задачи, история, графики

### Через Redis CLI
```bash
redis-cli
> KEYS *celery*
> LLEN celery
> LRANGE celery 0 10
```

### Через Django shell
```python
from django_celery_results.models import TaskResult
TaskResult.objects.all()
```

---

## 🛑 Остановка

```bash
# Ctrl+C в каждом окне терминала (worker, beat, flower)
# Или через pkill (Linux/Mac)
pkill -f "celery worker"
pkill -f "celery beat"
pkill -f "celery flower"
```

### Остановка Redis
```bash
# Docker
docker stop redis

# Systemd
sudo systemctl stop redis

# WSL
redis-cli shutdown
```

---

## 🐛 Отладка проблем

### Проблема: Worker не запускается
**Решение:**
1. Проверьте Redis: `redis-cli ping`
2. Проверьте `.env` файл
3. Убедитесь что виртуальное окружение активно
4. Проверьте логи: `celery -A eusrr_backend worker -l debug`

### Проблема: Задачи не выполняются
**Решение:**
1. Проверьте очереди: `redis-cli LLEN celery`
2. Проверьте Flower: http://localhost:5555
3. Проверьте worker logs
4. Убедитесь что worker запущен с нужной очередью

### Проблема: Redis connection refused
**Решение:**
1. Убедитесь что Redis запущен
2. Проверьте порт: `netstat -an | grep 6379`
3. Проверьте CELERY_BROKER_URL в .env

---

## 📝 Полезные команды

### Celery
```bash
# Очистить очередь
celery -A eusrr_backend purge

# Инспекция workers
celery -A eusrr_backend inspect active
celery -A eusrr_backend inspect stats

# Список зарегистрированных задач
celery -A eusrr_backend inspect registered
```

### Redis
```bash
# Очистить все данные Celery
redis-cli KEYS "celery*" | xargs redis-cli DEL

# Мониторинг в реальном времени
redis-cli MONITOR
```

---

## 🔄 Development workflow

### Типичный процесс работы:

**Терминал 1: Django**
```bash
.venv/Scripts/python manage.py runserver
```

**Терминал 2: Celery Worker**
```bash
celery -A eusrr_backend worker -l info
```

**Терминал 3: Celery Beat** (если нужны периодические задачи)
```bash
celery -A eusrr_backend beat -l info
```

**Терминал 4: Flower** (опционально)
```bash
celery -A eusrr_backend flower
```

**Терминал 5: Redis** (если запускали вручную)
```bash
redis-server
```

---

## 🎯 Следующие шаги

После успешного запуска:
1. ✅ Создать первую задачу в `notifications/tasks.py`
2. ✅ Протестировать отправку уведомления через Celery
3. ✅ Измерить улучшение производительности
4. ✅ Настроить периодические задачи
5. ✅ Настроить мониторинг в production

---

## 📚 Документация

- Celery: https://docs.celeryq.dev/
- Flower: https://flower.readthedocs.io/
- Django Celery Beat: https://django-celery-beat.readthedocs.io/
- Redis: https://redis.io/docs/
