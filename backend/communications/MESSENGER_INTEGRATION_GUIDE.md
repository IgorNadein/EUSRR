# Настройка интеграции мессенджеров

Этот документ описывает процесс настройки интеграции с WhatsApp, Telegram и WeChat.

## Архитектура

Система интеграции состоит из трех основных компонентов:

1. **MessengerIntegration** - настройки подключения к мессенджеру
2. **MessengerAccount** - привязка аккаунтов сотрудников
3. **MessengerMessage** - синхронизация сообщений

## Шаги настройки

### 1. Доступ к админ-панели

Перейдите в Django Admin: `http://your-domain/admin/communications/`

Вы увидите три новых раздела:
- Интеграции с мессенджерами
- Аккаунты в мессенджерах  
- Сообщения из мессенджеров

### 2. Настройка WhatsApp

#### 2.1. Получение API ключей

**Вариант A: WhatsApp Business API (официальный)**
1. Зарегистрируйтесь на https://business.whatsapp.com/
2. Создайте приложение в Facebook for Developers
3. Получите `WhatsApp Business Account ID` и `Access Token`

**Вариант B: WhatsApp Web API (неофициальный, через Baileys/Whatsapp-web.js)**
1. Используйте библиотеку для Node.js
2. Настройте webhook для получения сообщений
3. Получите QR-код для авторизации

#### 2.2. Настройка в системе

1. Откройте "Интеграции с мессенджерами" → "Добавить"
2. Выберите тип: **WhatsApp**
3. Заполните поля:
   - **Включена**: ✓
   - **Статус**: Active
   - **API ключ**: `<ваш Access Token>`
   - **Webhook URL**: `https://your-domain/communications/webhooks/whatsapp/`
   
4. В разделе "Дополнительные настройки" (JSON):
```json
{
  "phone_number_id": "YOUR_PHONE_NUMBER_ID",
  "business_account_id": "YOUR_BUSINESS_ACCOUNT_ID",
  "verify_token": "YOUR_WEBHOOK_VERIFY_TOKEN"
}
```

#### 2.3. Настройка webhook на стороне WhatsApp

1. В Facebook for Developers → WhatsApp → Configuration
2. Укажите webhook URL: `https://your-domain/communications/webhooks/whatsapp/`
3. Укажите Verify Token (из настроек выше)
4. Подпишитесь на события: `messages`, `message_status`

### 3. Настройка Telegram

#### 3.1. Создание бота

1. Найдите @BotFather в Telegram
2. Отправьте команду `/newbot`
3. Следуйте инструкциям для создания бота
4. Получите **Bot Token** (формат: `123456789:ABCdefGHIjklMNOpqrsTUVwxyz`)

#### 3.2. Настройка в системе

1. Откройте "Интеграции с мессенджерами" → "Добавить"
2. Выберите тип: **Telegram**
3. Заполните поля:
   - **Включена**: ✓
   - **Статус**: Active
   - **API ключ**: `<Bot Token от BotFather>`
   - **Webhook URL**: `https://your-domain/communications/webhooks/telegram/`

4. В разделе "Дополнительные настройки":
```json
{
  "bot_username": "your_bot_name",
  "allowed_updates": ["message", "edited_message", "callback_query"]
}
```

#### 3.3. Установка webhook

Выполните запрос (замените токен):
```bash
curl -X POST "https://api.telegram.org/bot<YOUR_BOT_TOKEN>/setWebhook" \
  -H "Content-Type: application/json" \
  -d '{"url": "https://your-domain/communications/webhooks/telegram/"}'
```

### 4. Настройка WeChat

#### 4.1. Регистрация WeChat Official Account

1. Зарегистрируйтесь на https://mp.weixin.qq.com/
2. Создайте Official Account
3. Получите `AppID` и `AppSecret`

#### 4.2. Настройка в системе

1. Откройте "Интеграции с мессенджерами" → "Добавить"
2. Выберите тип: **WeChat**
3. Заполните поля:
   - **Включена**: ✓
   - **Статус**: Active
   - **API ключ**: `<AppID>`
   - **API секрет**: `<AppSecret>`
   - **Webhook URL**: `https://your-domain/communications/webhooks/wechat/`

4. В разделе "Дополнительные настройки":
```json
{
  "token": "YOUR_TOKEN",
  "encoding_aes_key": "YOUR_ENCODING_AES_KEY"
}
```

## Привязка аккаунтов сотрудников

После настройки интеграции нужно привязать аккаунты сотрудников:

### Автоматическая привязка

Сотрудники могут сами привязать аккаунты:
1. Перейти в профиль → "Мессенджеры"
2. Выбрать мессенджер
3. Следовать инструкциям (QR-код, код подтверждения и т.д.)

### Ручная привязка (админ)

1. Откройте "Аккаунты в мессенджерах" → "Добавить"
2. Выберите пользователя
3. Выберите интеграцию
4. Укажите:
   - **External ID**: ID пользователя в мессенджере
   - **External Username**: Имя/никнейм
   - **Phone Number**: Телефон (для WhatsApp)
5. Установите галочку "Подтвержден"

## Синхронизация сообщений

### Настройка Celery задач

Добавьте в `celery.py`:

```python
from celery.schedules import crontab

app.conf.beat_schedule = {
    'sync-messenger-messages': {
        'task': 'communications.tasks.sync_messenger_messages',
        'schedule': 60.0,  # каждую минуту
    },
}
```

### Ручная синхронизация

Через Django shell:

```python
from communications.services.messenger_sync import MessengerSyncService

# Синхронизация всех мессенджеров
sync_service = MessengerSyncService()
sync_service.sync_all()

# Синхронизация конкретного мессенджера
sync_service.sync_messenger('whatsapp')
```

## Webhook эндпоинты

Система автоматически создает эндпоинты для получения входящих сообщений:

- **WhatsApp**: `POST /communications/webhooks/whatsapp/`
- **Telegram**: `POST /communications/webhooks/telegram/`
- **WeChat**: `POST /communications/webhooks/wechat/`

Эти URL должны быть доступны извне (HTTPS обязателен для production).

## Безопасность

### Шифрование API ключей

В production используйте `django-cryptography` для шифрования:

```python
# settings.py
INSTALLED_APPS = [
    ...
    'django_cryptography',
]

# Генерация ключа
from cryptography.fernet import Fernet
FIELD_ENCRYPTION_KEY = Fernet.generate_key().decode()
```

Обновите модель:
```python
from django_cryptography.fields import encrypt

class MessengerIntegration(models.Model):
    api_key = encrypt(models.CharField(max_length=500))
    api_secret = encrypt(models.CharField(max_length=500))
```

### Проверка подписи webhook

Всегда проверяйте подпись входящих запросов:

```python
# views.py
def verify_whatsapp_signature(request):
    signature = request.headers.get('X-Hub-Signature-256')
    # Проверка HMAC
    ...
```

## Мониторинг

### Просмотр статистики

В админ-панели "Интеграции с мессенджерами" отображается:
- Количество отправленных сообщений
- Количество полученных сообщений
- Время последней синхронизации
- Последняя ошибка (если есть)

### Логирование

Все операции логируются:

```python
import logging
logger = logging.getLogger('communications.messenger')

# В settings.py
LOGGING = {
    'loggers': {
        'communications.messenger': {
            'level': 'INFO',
            'handlers': ['file'],
        },
    },
}
```

## Troubleshooting

### Проблема: Webhook не получает сообщения

1. Проверьте, что URL доступен извне:
   ```bash
   curl https://your-domain/communications/webhooks/telegram/
   ```

2. Проверьте SSL сертификат (должен быть валидным)

3. Проверьте логи Django:
   ```bash
   tail -f logs/django.log | grep webhook
   ```

### Проблема: Сообщения не синхронизируются

1. Проверьте статус интеграции (должен быть "Active")
2. Проверьте поле "Последняя ошибка"
3. Запустите синхронизацию вручную через shell
4. Проверьте Celery tasks (если используется)

### Проблема: Неверный API ключ

1. Перегенерируйте ключ в соответствующем сервисе
2. Обновите в админ-панели
3. Измените статус на "Active" после обновления

## Дальнейшее развитие

### Планируемые функции

- [ ] Групповые чаты в мессенджерах
- [ ] Отправка медиа-файлов
- [ ] Голосовые сообщения
- [ ] Статусы доставки
- [ ] Typing indicators
- [ ] Реакции на сообщения
- [ ] Шаблоны сообщений для WhatsApp Business

### API endpoints для разработчиков

```
POST /api/v1/messenger/send/
GET /api/v1/messenger/accounts/
GET /api/v1/messenger/messages/
POST /api/v1/messenger/link-account/
```

Документация API: `https://your-domain/api/docs/`

## Поддержка

При возникновении проблем:
1. Проверьте документацию мессенджера
2. Проверьте логи системы
3. Обратитесь к системному администратору
