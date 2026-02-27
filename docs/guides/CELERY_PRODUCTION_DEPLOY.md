# Celery Production Deployment Guide

Инструкция по развертыванию Celery на production сервере с использованием Git + Gunicorn + systemd.

## 📋 Предварительные требования

- Ubuntu/Debian сервер
- Установленный Redis
- Django приложение на Gunicorn
- Доступ по SSH
- Права sudo

## 🚀 Шаг 1: Деплой кода

### 1.1. Push изменений на сервер

```bash
# На локальной машине
git push origin master
```

### 1.2. На production сервере

```bash
# Переход в директорию проекта
cd /path/to/EUSRR

# Получение обновлений
git pull origin master

# Активация виртуального окружения
source .venv/bin/activate

# Установка новых зависимостей
cd backend
pip install -r requirements.txt

# Применение миграций
python manage.py migrate

# Сбор статики (если нужно)
python manage.py collectstatic --noinput

# Перезапуск Gunicorn
sudo systemctl restart gunicorn
```

## 🔧 Шаг 2: Установка и настройка Redis

### 2.1. Установка Redis (если еще не установлен)

```bash
sudo apt update
sudo apt install redis-server -y
```

### 2.2. Настройка Redis

Отредактируйте конфигурацию:
```bash
sudo nano /etc/redis/redis.conf
```

Найдите и измените:
```conf
# Привязка к localhost (безопасность)
bind 127.0.0.1

# Включить persistence
save 900 1
save 300 10
save 60 10000

# Максимальная память (опционально)
maxmemory 256mb
maxmemory-policy allkeys-lru
```

### 2.3. Включение и запуск Redis

```bash
sudo systemctl enable redis-server
sudo systemctl start redis-server
sudo systemctl status redis-server
```

Проверка работы:
```bash
redis-cli ping
# Должен вернуть: PONG
```

## 📝 Шаг 3: Создание systemd сервисов для Celery

### 3.1. Создание пользователя для Celery (опционально, но рекомендуется)

```bash
sudo useradd -r -s /bin/false celery
```

Или используйте существующего пользователя (например, `www-data` или пользователя под которым работает gunicorn).

### 3.2. Создание директорий для логов

```bash
sudo mkdir -p /var/log/celery
sudo mkdir -p /var/run/celery

# Права доступа (замените 'your_user' на вашего пользователя)
sudo chown -R your_user:your_user /var/log/celery
sudo chown -R your_user:your_user /var/run/celery
```

### 3.3. Celery Worker Service

Создайте файл `/etc/systemd/system/celery.service`:

```bash
sudo nano /etc/systemd/system/celery.service
```

Содержимое файла:

```ini
[Unit]
Description=Celery Worker for EUSRR
After=network.target redis.service

[Service]
Type=forking
User=your_user
Group=your_group
WorkingDirectory=/path/to/EUSRR/backend
Environment="PATH=/path/to/EUSRR/.venv/bin"

# Celery Worker
ExecStart=/path/to/EUSRR/.venv/bin/celery -A eusrr_backend worker \
    --loglevel=info \
    --logfile=/var/log/celery/worker.log \
    --pidfile=/var/run/celery/worker.pid \
    --concurrency=4 \
    --detach

ExecStop=/path/to/EUSRR/.venv/bin/celery -A eusrr_backend control shutdown
ExecReload=/bin/kill -HUP $MAINPID

# Автоматический перезапуск при падении
Restart=always
RestartSec=10s

# Ограничения ресурсов (опционально)
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
```

**Важно:** Замените:
- `your_user` и `your_group` - на реального пользователя (например, `www-data`)
- `/path/to/EUSRR` - на реальный путь к проекту

### 3.4. Celery Beat Service (для периодических задач)

Создайте файл `/etc/systemd/system/celery-beat.service`:

```bash
sudo nano /etc/systemd/system/celery-beat.service
```

Содержимое:

```ini
[Unit]
Description=Celery Beat Scheduler for EUSRR
After=network.target redis.service celery.service

[Service]
Type=simple
User=your_user
Group=your_group
WorkingDirectory=/path/to/EUSRR/backend
Environment="PATH=/path/to/EUSRR/.venv/bin"

ExecStart=/path/to/EUSRR/.venv/bin/celery -A eusrr_backend beat \
    --loglevel=info \
    --logfile=/var/log/celery/beat.log \
    --pidfile=/var/run/celery/beat.pid

# Автоматический перезапуск
Restart=always
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

## 🔄 Шаг 4: Запуск и проверка Celery

### 4.1. Перезагрузка systemd конфигурации

```bash
sudo systemctl daemon-reload
```

### 4.2. Включение автозапуска

```bash
sudo systemctl enable celery
sudo systemctl enable celery-beat
```

### 4.3. Запуск сервисов

```bash
sudo systemctl start celery
sudo systemctl start celery-beat
```

### 4.4. Проверка статуса

```bash
# Celery Worker
sudo systemctl status celery

# Celery Beat
sudo systemctl status celery-beat

# Логи Worker
sudo tail -f /var/log/celery/worker.log

# Логи Beat
sudo tail -f /var/log/celery/beat.log
```

### 4.5. Проверка работы через Celery CLI

```bash
cd /path/to/EUSRR/backend
source ../.venv/bin/activate

# Проверка активных workers
celery -A eusrr_backend inspect active

# Статистика
celery -A eusrr_backend inspect stats

# Список зарегистрированных задач
celery -A eusrr_backend inspect registered
```

## 📊 Шаг 5: Мониторинг с Flower (опционально)

### 5.1. Создание Flower Service

```bash
sudo nano /etc/systemd/system/celery-flower.service
```

Содержимое:

```ini
[Unit]
Description=Celery Flower Monitoring for EUSRR
After=network.target redis.service celery.service

[Service]
Type=simple
User=your_user
Group=your_group
WorkingDirectory=/path/to/EUSRR/backend
Environment="PATH=/path/to/EUSRR/.venv/bin"

ExecStart=/path/to/EUSRR/.venv/bin/celery -A eusrr_backend flower \
    --port=5555 \
    --address=127.0.0.1 \
    --basic_auth=admin:your_secure_password

Restart=always
RestartSec=10s

[Install]
WantedBy=multi-user.target
```

### 5.2. Запуск Flower

```bash
sudo systemctl daemon-reload
sudo systemctl enable celery-flower
sudo systemctl start celery-flower
```

### 5.3. Настройка Nginx для Flower (если нужен внешний доступ)

```nginx
# /etc/nginx/sites-available/flower
server {
    listen 80;
    server_name flower.yourdomain.com;

    location / {
        proxy_pass http://127.0.0.1:5555;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        
        # Basic Auth на уровне Nginx (двойная защита)
        auth_basic "Flower Monitoring";
        auth_basic_user_file /etc/nginx/.htpasswd;
    }
}
```

Создание пароля:
```bash
sudo apt install apache2-utils
sudo htpasswd -c /etc/nginx/.htpasswd admin
```

## 🔧 Шаг 6: Настройка логирования

### 6.1. Ротация логов с logrotate

Создайте файл `/etc/logrotate.d/celery`:

```bash
sudo nano /etc/logrotate.d/celery
```

Содержимое:

```
/var/log/celery/*.log {
    daily
    rotate 14
    compress
    delaycompress
    notifempty
    missingok
    copytruncate
    create 0640 your_user your_group
}
```

## 🔄 Обновление после изменений кода

Создайте скрипт `/path/to/EUSRR/deploy.sh`:

```bash
#!/bin/bash
set -e

echo "🚀 Начало деплоя..."

# Переход в директорию проекта
cd /path/to/EUSRR

# Pull изменений
echo "📥 Получение изменений из Git..."
git pull origin master

# Активация venv
source .venv/bin/activate

# Установка зависимостей
echo "📦 Установка зависимостей..."
cd backend
pip install -r requirements.txt

# Миграции
echo "🗃️ Применение миграций..."
python manage.py migrate

# Сбор статики
echo "📁 Сбор статических файлов..."
python manage.py collectstatic --noinput

# Перезапуск сервисов
echo "🔄 Перезапуск сервисов..."
sudo systemctl restart gunicorn
sudo systemctl restart celery
sudo systemctl restart celery-beat

# Проверка статуса
echo "✅ Проверка статусов сервисов..."
sudo systemctl status gunicorn --no-pager
sudo systemctl status celery --no-pager
sudo systemctl status celery-beat --no-pager

echo "✅ Деплой завершен!"
```

Права на выполнение:
```bash
chmod +x /path/to/EUSRR/deploy.sh
```

Использование:
```bash
/path/to/EUSRR/deploy.sh
```

## 🐛 Troubleshooting

### Проблема: Worker не запускается

**Проверка логов:**
```bash
sudo journalctl -u celery -n 50 --no-pager
tail -f /var/log/celery/worker.log
```

**Типичные причины:**
1. Неправильный путь к проекту в service файле
2. Redis не запущен: `sudo systemctl status redis-server`
3. Ошибки в коде: проверьте импорты в `eusrr_backend/celery.py`
4. Права доступа: проверьте владельца файлов и директорий

### Проблема: Задачи не выполняются

**Проверка очереди Redis:**
```bash
redis-cli
> KEYS celery*
> LLEN celery
```

**Проверка воркеров:**
```bash
celery -A eusrr_backend inspect active
celery -A eusrr_backend inspect registered
```

### Проблема: Database is locked (PostgreSQL)

Если используете PostgreSQL на production:
```python
# settings.py
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': 'eusrr_db',
        'USER': 'eusrr_user',
        'PASSWORD': 'password',
        'HOST': 'localhost',
        'PORT': '5432',
        'CONN_MAX_AGE': 600,  # Переиспользование соединений
    }
}
```

## 📈 Мониторинг производительности

### Проверка нагрузки на Celery

```bash
# CPU и память workers
ps aux | grep celery

# Количество задач в очереди
celery -A eusrr_backend inspect reserved

# Активные задачи
celery -A eusrr_backend inspect active
```

### Настройка алертов

Используйте Flower + Prometheus + Grafana для полноценного мониторинга:
- http://localhost:5555 - Flower dashboard
- Настройка метрик: [Flower + Prometheus](https://flower.readthedocs.io/en/latest/prometheus-integration.html)

## 🔒 Безопасность

### 1. Ограничение доступа к Redis

```bash
# /etc/redis/redis.conf
bind 127.0.0.1
requirepass your_strong_password
```

Обновите в Django settings:
```python
CELERY_BROKER_URL = 'redis://:your_strong_password@localhost:6379/0'
```

### 2. Firewall правила

```bash
# Разрешить только локальный доступ к Redis
sudo ufw deny 6379
sudo ufw allow from 127.0.0.1 to any port 6379
```

### 3. Ограничение ресурсов

В systemd service файлах добавьте:
```ini
[Service]
# Максимум памяти (512MB)
MemoryMax=512M
# CPU quota (50%)
CPUQuota=50%
```

## 📚 Полезные команды

```bash
# Перезапуск всех Celery сервисов
sudo systemctl restart celery celery-beat

# Просмотр логов в реальном времени
sudo journalctl -u celery -f

# Очистка очереди Redis (осторожно!)
celery -A eusrr_backend purge

# Завершение всех активных задач
celery -A eusrr_backend control revoke_all

# Graceful restart worker
celery -A eusrr_backend control shutdown
sudo systemctl start celery
```

## ✅ Чеклист после деплоя

- [ ] Redis запущен и доступен
- [ ] Celery worker работает (`systemctl status celery`)
- [ ] Celery beat работает (если используются периодические задачи)
- [ ] Задачи выполняются (проверить через Flower или логи)
- [ ] Уведомления приходят пользователям
- [ ] Логи пишутся корректно
- [ ] Ротация логов настроена
- [ ] Мониторинг настроен (Flower)
- [ ] Backup конфигураций сделан

## 📞 Контакты и поддержка

При возникновении проблем:
1. Проверьте логи: `/var/log/celery/worker.log`
2. Проверьте systemd: `sudo journalctl -u celery -n 100`
3. Проверьте Redis: `redis-cli ping`
4. Документация Celery: https://docs.celeryq.dev/

---

**Последнее обновление:** 8 января 2026  
**Версия:** 1.0
