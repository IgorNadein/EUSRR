# План системы уведомлений EUSRR

## Дата: 20 ноября 2025
## Статус: Проектирование

---

## 1. Обзор системы

### 1.1 Цели
- ✅ Централизованная система уведомлений для всех событий в системе
- ✅ Гибкие настройки для каждого пользователя
- ✅ Множественные каналы доставки (сайт, email, Telegram, WhatsApp, WeChat)
- ✅ Реальное время через WebSocket
- ✅ История всех уведомлений
- ✅ Группировка и приоритизация

### 1.2 Типы уведомлений

#### Коммуникации (Communications)
- 💬 Новое сообщение в чате
- 📌 Упоминание (@username) в сообщении
- ✏️ Редактирование важного сообщения
- 📎 Новое вложение в чате
- 👥 Добавление в новый чат/группу
- 🔔 Ответ на ваше сообщение

#### Документы (Documents)
- 📄 Новый документ на ознакомление
- ✅ Документ подписан всеми участниками
- ⏰ Напоминание о необходимости ознакомления
- 📝 Комментарий к документу
- 🔄 Обновление документа

#### Заявления (Requests)
- 📋 Новая заявка (для ответственных)
- ✅ Заявка одобрена
- ❌ Заявка отклонена
- 💬 Комментарий к вашей заявке
- 🔄 Изменение статуса заявки
- ⏰ Заявка на рассмотрении долгое время

#### Календарь (Calendar)
- 📅 Новое событие
- ⏰ Напоминание о событии (за час, за день)
- 🔄 Изменение события
- ❌ Отмена события
- 👥 Приглашение на событие

#### Отдел (Department)
- 👥 Новый сотрудник в отделе
- 👋 Сотрудник покинул отдел
- 📊 Изменение структуры отдела
- 👤 Назначен новый руководитель
- 📢 Объявление для отдела

#### Профиль (Profile)
- ✏️ Изменение данных профиля администратором
- 🔑 Изменение пароля
- 📧 Изменение email
- 📱 Привязка нового мессенджера
- 🔐 Вход из нового места/устройства

#### Новости (Feed)
- 📰 Новая новость
- 💬 Комментарий к вашей новости
- ❤️ Реакция на вашу новость

#### Система (System)
- ⚠️ Технические работы
- 📢 Важное объявление
- 🎉 Новый функционал
- 🔒 Изменение политики безопасности

---

## 2. Архитектура базы данных

### 2.1 Модели

#### `NotificationCategory` (Категория уведомлений)
```python
class NotificationCategory(models.Model):
    """Категории уведомлений для группировки"""
    
    CATEGORY_CHOICES = [
        ('communications', 'Коммуникации'),
        ('documents', 'Документы'),
        ('requests', 'Заявления'),
        ('calendar', 'Календарь'),
        ('department', 'Отдел'),
        ('profile', 'Профиль'),
        ('feed', 'Новости'),
        ('system', 'Система'),
    ]
    
    code = models.CharField(max_length=50, unique=True, choices=CATEGORY_CHOICES)
    name = models.CharField(max_length=100)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=50, default='bi-bell')  # Bootstrap icon
    color = models.CharField(max_length=20, default='primary')  # Bootstrap color
    is_active = models.BooleanField(default=True)
    order = models.IntegerField(default=0)
    
    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Категория уведомлений'
        verbose_name_plural = 'Категории уведомлений'
```

#### `NotificationType` (Тип уведомления)
```python
class NotificationType(models.Model):
    """Конкретные типы уведомлений внутри категорий"""
    
    category = models.ForeignKey(NotificationCategory, on_delete=models.CASCADE, related_name='types')
    code = models.CharField(max_length=100, unique=True)  # 'chat_new_message', 'document_ready', etc.
    name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    
    # Настройки по умолчанию для всех пользователей
    default_enabled = models.BooleanField(default=True)
    default_channels = models.JSONField(default=dict)  # {'web': True, 'email': False, 'telegram': False}
    
    # Приоритет
    PRIORITY_CHOICES = [
        ('low', 'Низкий'),
        ('normal', 'Обычный'),
        ('high', 'Высокий'),
        ('urgent', 'Срочный'),
    ]
    priority = models.CharField(max_length=20, choices=PRIORITY_CHOICES, default='normal')
    
    # Можно ли отключить
    is_required = models.BooleanField(default=False)  # Например, системные уведомления нельзя отключить
    
    # Группировка (например, объединять несколько сообщений в одно уведомление)
    is_groupable = models.BooleanField(default=True)
    grouping_window_minutes = models.IntegerField(default=5)  # Группировать за последние 5 минут
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['category__order', 'name']
        verbose_name = 'Тип уведомления'
        verbose_name_plural = 'Типы уведомлений'
```

#### `Notification` (Уведомление)
```python
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType

class Notification(models.Model):
    """Конкретное уведомление для пользователя"""
    
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='notifications'
    )
    notification_type = models.ForeignKey(NotificationType, on_delete=models.CASCADE)
    
    # Заголовок и текст
    title = models.CharField(max_length=255)
    message = models.TextField()
    short_message = models.CharField(max_length=150, blank=True)  # Для preview
    
    # Связь с объектом (GenericForeignKey)
    content_type = models.ForeignKey(ContentType, on_delete=models.CASCADE, null=True, blank=True)
    object_id = models.PositiveIntegerField(null=True, blank=True)
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Метаданные
    metadata = models.JSONField(default=dict, blank=True)  # Доп. данные для рендеринга
    
    # Ссылка действия
    action_url = models.CharField(max_length=500, blank=True)
    action_text = models.CharField(max_length=100, default='Посмотреть')
    
    # Статусы
    is_read = models.BooleanField(default=False)
    read_at = models.DateTimeField(null=True, blank=True)
    
    is_archived = models.BooleanField(default=False)
    archived_at = models.DateTimeField(null=True, blank=True)
    
    # Доставка
    sent_web = models.BooleanField(default=False)
    sent_email = models.BooleanField(default=False)
    sent_telegram = models.BooleanField(default=False)
    sent_whatsapp = models.BooleanField(default=False)
    sent_wechat = models.BooleanField(default=False)
    
    sent_at = models.DateTimeField(null=True, blank=True)
    
    # Группировка
    group_key = models.CharField(max_length=255, blank=True, db_index=True)  # Ключ для группировки
    is_grouped = models.BooleanField(default=False)
    grouped_count = models.IntegerField(default=1)  # Количество объединенных уведомлений
    
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['recipient', '-created_at']),
            models.Index(fields=['recipient', 'is_read']),
            models.Index(fields=['notification_type', '-created_at']),
            models.Index(fields=['group_key', '-created_at']),
        ]
        verbose_name = 'Уведомление'
        verbose_name_plural = 'Уведомления'
    
    def mark_as_read(self):
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
```

#### `UserNotificationSettings` (Настройки пользователя)
```python
class UserNotificationSettings(models.Model):
    """Персональные настройки уведомлений пользователя"""
    
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notification_settings')
    notification_type = models.ForeignKey(NotificationType, on_delete=models.CASCADE)
    
    # Включено ли уведомление
    is_enabled = models.BooleanField(default=True)
    
    # Каналы доставки
    send_web = models.BooleanField(default=True)  # На сайте
    send_email = models.BooleanField(default=False)
    send_telegram = models.BooleanField(default=False)
    send_whatsapp = models.BooleanField(default=False)
    send_wechat = models.BooleanField(default=False)
    
    # Тихий режим (не беспокоить)
    quiet_hours_enabled = models.BooleanField(default=False)
    quiet_start_time = models.TimeField(null=True, blank=True)  # 22:00
    quiet_end_time = models.TimeField(null=True, blank=True)    # 08:00
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['user', 'notification_type']
        verbose_name = 'Настройка уведомлений пользователя'
        verbose_name_plural = 'Настройки уведомлений пользователей'
```

#### `NotificationTemplate` (Шаблоны)
```python
class NotificationTemplate(models.Model):
    """Шаблоны для разных каналов доставки"""
    
    notification_type = models.ForeignKey(NotificationType, on_delete=models.CASCADE, related_name='templates')
    
    CHANNEL_CHOICES = [
        ('web', 'Веб'),
        ('email', 'Email'),
        ('telegram', 'Telegram'),
        ('whatsapp', 'WhatsApp'),
        ('wechat', 'WeChat'),
    ]
    channel = models.CharField(max_length=20, choices=CHANNEL_CHOICES)
    
    # Шаблоны (используем Django template syntax)
    title_template = models.TextField()
    message_template = models.TextField()
    
    # Для email
    html_template = models.TextField(blank=True)
    
    # Для кнопок действий
    action_button_template = models.CharField(max_length=200, blank=True)
    
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ['notification_type', 'channel']
        verbose_name = 'Шаблон уведомления'
        verbose_name_plural = 'Шаблоны уведомлений'
```

---

## 3. Этапы реализации

### Этап 1: Базовая инфраструктура (Week 1-2)
**Цель:** Создать основу системы уведомлений

#### Задачи:
1. ✅ Создать приложение `notifications`
2. ✅ Создать модели:
   - `NotificationCategory`
   - `NotificationType`
   - `Notification`
   - `UserNotificationSettings`
   - `NotificationTemplate`
3. ✅ Создать миграции
4. ✅ Настроить Django Admin для всех моделей
5. ✅ Создать начальные данные (fixtures) с типами уведомлений

**Файлы:**
```
notifications/
├── __init__.py
├── models.py
├── admin.py
├── apps.py
├── migrations/
├── fixtures/
│   └── initial_notification_types.json
└── management/
    └── commands/
        └── create_notification_types.py
```

---

### Этап 2: Сервисный слой (Week 2-3)
**Цель:** Создать API для создания и управления уведомлениями

#### Задачи:
1. ✅ Создать `NotificationService` для создания уведомлений
2. ✅ Создать `NotificationSender` для отправки по каналам
3. ✅ Создать систему шаблонов
4. ✅ Реализовать группировку уведомлений
5. ✅ Создать Celery tasks для асинхронной отправки

**Файлы:**
```python
# notifications/services.py
class NotificationService:
    @staticmethod
    def create_notification(
        recipient,
        notification_type_code,
        title,
        message,
        content_object=None,
        action_url='',
        metadata=None
    ):
        """Создать и отправить уведомление"""
        pass
    
    @staticmethod
    def send_notification(notification):
        """Отправить уведомление по всем каналам"""
        pass
    
    @staticmethod
    def mark_as_read(notification_id, user):
        """Отметить как прочитанное"""
        pass
    
    @staticmethod
    def mark_all_as_read(user, category=None):
        """Отметить все как прочитанные"""
        pass

# notifications/senders.py
class WebNotificationSender:
    def send(self, notification):
        """Отправка через WebSocket"""
        pass

class EmailNotificationSender:
    def send(self, notification):
        """Отправка через email"""
        pass

class TelegramNotificationSender:
    def send(self, notification):
        """Отправка через Telegram бота"""
        pass

# notifications/tasks.py
from celery import shared_task

@shared_task
def send_notification_async(notification_id):
    """Асинхронная отправка уведомления"""
    pass

@shared_task
def cleanup_old_notifications():
    """Очистка старых уведомлений (старше 90 дней)"""
    pass
```

---

### Этап 3: WebSocket реального времени (Week 3)
**Цель:** Уведомления в реальном времени на сайте

#### Задачи:
1. ✅ Создать WebSocket consumer для уведомлений
2. ✅ Подключить к routing
3. ✅ Создать фронтенд компонент для колокольчика
4. ✅ Создать всплывающие toast-уведомления
5. ✅ Звуковые уведомления (опционально)

**Файлы:**
```python
# notifications/consumers.py
class NotificationConsumer(AsyncWebsocketConsumer):
    async def connect(self):
        self.user = self.scope['user']
        await self.channel_layer.group_add(
            f'notifications_{self.user.id}',
            self.channel_name
        )
        await self.accept()
    
    async def notification_new(self, event):
        """Отправить новое уведомление"""
        await self.send(text_data=json.dumps({
            'type': 'new_notification',
            'notification': event['notification']
        }))

# notifications/routing.py
from django.urls import re_path
from . import consumers

websocket_urlpatterns = [
    re_path(r'^ws/notifications/$', consumers.NotificationConsumer.as_asgi()),
]
```

**Frontend:**
```javascript
// static/js/notifications.js
class NotificationManager {
    constructor() {
        this.ws = null;
        this.unreadCount = 0;
        this.connectWebSocket();
    }
    
    connectWebSocket() {
        const wsUrl = `ws://${window.location.host}/ws/notifications/`;
        this.ws = new WebSocket(wsUrl);
        
        this.ws.onmessage = (e) => {
            const data = JSON.parse(e.data);
            if (data.type === 'new_notification') {
                this.handleNewNotification(data.notification);
            }
        };
    }
    
    handleNewNotification(notification) {
        // Обновить счетчик
        this.updateBadge();
        
        // Показать toast
        this.showToast(notification);
        
        // Воспроизвести звук
        this.playSound();
    }
}
```

---

### Этап 4: UI компоненты (Week 4)
**Цель:** Интерфейс для просмотра и управления уведомлениями

#### Задачи:
1. ✅ Обновить navbar с счетчиком уведомлений
2. ✅ Создать dropdown список уведомлений
3. ✅ Создать страницу всех уведомлений
4. ✅ Создать страницу настроек уведомлений
5. ✅ Фильтрация по категориям
6. ✅ Поиск в уведомлениях

**Компоненты:**
```
templates/notifications/
├── notification_dropdown.html     # Dropdown в navbar
├── notification_list.html         # Полный список
├── notification_settings.html     # Настройки
└── includes/
    ├── notification_item.html     # Карточка уведомления
    └── notification_toast.html    # Toast-уведомление
```

---

### Этап 5: Интеграция с модулями (Week 5-6)
**Цель:** Добавить уведомления во все существующие модули

#### 5.1 Communications (Чаты)
```python
# communications/signals.py
from django.db.models.signals import post_save
from django.dispatch import receiver
from notifications.services import NotificationService

@receiver(post_save, sender=Message)
def notify_new_message(sender, instance, created, **kwargs):
    if created:
        # Получить участников чата, кроме автора
        recipients = instance.chat.participants.exclude(id=instance.author.id)
        
        for recipient in recipients:
            # Проверить, упомянут ли пользователь
            is_mentioned = f'@{recipient.username}' in instance.content
            
            notification_type = 'chat_mention' if is_mentioned else 'chat_new_message'
            
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_code=notification_type,
                title=f'Новое сообщение от {instance.author.get_full_name()}',
                message=instance.content[:100],
                content_object=instance,
                action_url=f'/communications/chat/{instance.chat.id}/',
                metadata={
                    'chat_id': instance.chat.id,
                    'chat_name': str(instance.chat),
                    'author_name': instance.author.get_full_name(),
                }
            )
```

#### 5.2 Documents
```python
@receiver(post_save, sender=DocumentAcknowledgement)
def notify_document_ready(sender, instance, created, **kwargs):
    if created:
        NotificationService.create_notification(
            recipient=instance.user,
            notification_type_code='document_ready',
            title='Новый документ на ознакомление',
            message=f'Документ "{instance.document.title}" требует вашего ознакомления',
            content_object=instance.document,
            action_url=f'/documents/{instance.document.id}/',
        )
```

#### 5.3 Requests (Заявления)
```python
@receiver(post_save, sender=Request)
def notify_request_status_change(sender, instance, created, **kwargs):
    if not created and instance.tracker.has_changed('status'):
        NotificationService.create_notification(
            recipient=instance.created_by,
            notification_type_code='request_status_changed',
            title=f'Статус заявки изменен',
            message=f'Ваша заявка "{instance.title}" теперь: {instance.get_status_display()}',
            content_object=instance,
            action_url=f'/requests/{instance.id}/',
        )
```

#### 5.4 Calendar
```python
@receiver(post_save, sender=Event)
def notify_event_created(sender, instance, created, **kwargs):
    if created:
        for participant in instance.participants.all():
            NotificationService.create_notification(
                recipient=participant,
                notification_type_code='event_created',
                title='Новое событие в календаре',
                message=f'{instance.title} - {instance.start_date.strftime("%d.%m.%Y %H:%M")}',
                content_object=instance,
                action_url='/calendar/',
            )
```

---

### Этап 6: API для настроек (Week 6)
**Цель:** REST API для управления настройками

#### Задачи:
```python
# notifications/api_views.py
from rest_framework.decorators import api_view
from rest_framework.response import Response

@api_view(['GET'])
def get_notifications(request):
    """Получить список уведомлений с пагинацией"""
    pass

@api_view(['GET'])
def get_unread_count(request):
    """Получить количество непрочитанных"""
    pass

@api_view(['POST'])
def mark_as_read(request, notification_id):
    """Отметить как прочитанное"""
    pass

@api_view(['POST'])
def mark_all_as_read(request):
    """Отметить все как прочитанные"""
    pass

@api_view(['GET'])
def get_settings(request):
    """Получить настройки пользователя"""
    pass

@api_view(['POST'])
def update_settings(request):
    """Обновить настройки"""
    pass
```

---

### Этап 7: Email рассылка (Week 7)
**Цель:** Отправка уведомлений на email

#### Задачи:
1. ✅ Создать HTML-шаблоны для email
2. ✅ Настроить Celery задачи для пакетной отправки
3. ✅ Дайджест уведомлений (раз в день/неделю)
4. ✅ Настройки частоты email

**Шаблоны:**
```django
{# notifications/email/base.html #}
<!DOCTYPE html>
<html>
<head>
    <style>
        /* Email styles */
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <img src="{{ BRAND_LOGO }}" alt="{{ BRAND_NAME }}">
        </div>
        {% block content %}{% endblock %}
        <div class="footer">
            <a href="{{ settings_url }}">Настроить уведомления</a>
        </div>
    </div>
</body>
</html>
```

---

### Этап 8: Telegram бот (Week 8-9)
**Цель:** Отправка уведомлений через Telegram

#### Задачи:
1. ✅ Создать Telegram бота (python-telegram-bot)
2. ✅ Реализовать привязку аккаунта
3. ✅ Отправка уведомлений
4. ✅ Интерактивные кнопки в Telegram
5. ✅ Настройки через бота

**Структура:**
```python
# notifications/telegram_bot.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, CommandHandler, CallbackQueryHandler

class NotificationBot:
    def __init__(self, token):
        self.app = ApplicationBuilder().token(token).build()
        self.register_handlers()
    
    def register_handlers(self):
        self.app.add_handler(CommandHandler('start', self.start))
        self.app.add_handler(CommandHandler('settings', self.settings))
        self.app.add_handler(CallbackQueryHandler(self.button_callback))
    
    async def start(self, update: Update, context):
        """Команда /start для привязки"""
        pass
    
    async def settings(self, update: Update, context):
        """Настройки уведомлений"""
        pass
    
    def send_notification(self, telegram_id, notification):
        """Отправить уведомление"""
        pass
```

---

### Этап 9: Оптимизация и производительность (Week 10)
**Цель:** Оптимизировать систему для большой нагрузки

#### Задачи:
1. ✅ Кеширование счетчиков (Redis)
2. ✅ Пакетная отправка
3. ✅ Индексы БД
4. ✅ Архивирование старых уведомлений
5. ✅ Rate limiting для защиты от спама
6. ✅ Мониторинг производительности

---

## 4. Технологический стек

### Backend
- **Django**: Основной фреймворк
- **Django Channels**: WebSocket для real-time
- **Celery**: Асинхронные задачи
- **Redis**: Кеширование, message broker для Celery
- **PostgreSQL**: Основная БД

### Frontend
- **Bootstrap 5**: UI компоненты
- **Bootstrap Icons**: Иконки
- **Vanilla JavaScript**: Реальное время
- **Service Workers**: Push уведомления (будущее)

### Внешние сервисы
- **SMTP**: Email рассылка
- **Telegram Bot API**: Telegram уведомления
- **WhatsApp Business API**: WhatsApp (будущее)
- **WeChat API**: WeChat (будущее)

---

## 5. Структура проекта

```
backend/
├── notifications/
│   ├── __init__.py
│   ├── models.py                    # Модели
│   ├── admin.py                     # Django Admin
│   ├── apps.py
│   ├── services.py                  # Бизнес-логика
│   ├── senders.py                   # Отправка по каналам
│   ├── tasks.py                     # Celery задачи
│   ├── consumers.py                 # WebSocket consumers
│   ├── routing.py                   # WebSocket routing
│   ├── telegram_bot.py              # Telegram бот
│   ├── api_views.py                 # REST API
│   ├── urls.py                      # URL patterns
│   ├── views.py                     # Django views
│   ├── serializers.py               # DRF serializers
│   ├── signals.py                   # Django signals
│   ├── fixtures/
│   │   └── initial_data.json
│   ├── management/
│   │   └── commands/
│   │       ├── create_notification_types.py
│   │       └── run_telegram_bot.py
│   ├── migrations/
│   └── tests/
│       ├── test_models.py
│       ├── test_services.py
│       └── test_api.py
│
├── templates/
│   └── notifications/
│       ├── notification_list.html
│       ├── notification_settings.html
│       ├── notification_dropdown.html
│       ├── email/
│       │   ├── base.html
│       │   ├── new_message.html
│       │   └── digest.html
│       └── includes/
│           ├── notification_item.html
│           └── notification_toast.html
│
└── static/
    ├── js/
    │   ├── notifications.js         # Главный класс
    │   └── notification-toast.js    # Toast компонент
    ├── css/
    │   └── notifications.css
    └── sounds/
        └── notification.mp3
```

---

## 6. API Endpoints

### REST API
```
GET    /api/notifications/                   # Список уведомлений
GET    /api/notifications/unread/            # Только непрочитанные
GET    /api/notifications/count/             # Счетчик
POST   /api/notifications/{id}/read/         # Отметить прочитанным
POST   /api/notifications/read-all/          # Все прочитанными
DELETE /api/notifications/{id}/              # Удалить
POST   /api/notifications/archive-all/       # Архивировать все

GET    /api/notifications/settings/          # Настройки пользователя
PUT    /api/notifications/settings/          # Обновить настройки
GET    /api/notifications/types/             # Доступные типы
```

### WebSocket
```
ws://domain/ws/notifications/                # Real-time уведомления

Сообщения:
{
  "type": "new_notification",
  "notification": {...}
}

{
  "type": "mark_read",
  "notification_id": 123
}

{
  "type": "count_update",
  "count": 5
}
```

---

## 7. Примеры использования

### 7.1 Создание уведомления в коде
```python
from notifications.services import NotificationService

# Простое уведомление
NotificationService.create_notification(
    recipient=user,
    notification_type_code='chat_new_message',
    title='Новое сообщение',
    message='У вас новое сообщение в чате',
    action_url='/communications/chat/123/',
)

# С привязкой к объекту
NotificationService.create_notification(
    recipient=user,
    notification_type_code='document_ready',
    title='Документ на ознакомление',
    message=document.title,
    content_object=document,
    action_url=f'/documents/{document.id}/',
    metadata={
        'deadline': document.deadline.isoformat(),
        'priority': 'high'
    }
)
```

### 7.2 Использование в signals
```python
from django.db.models.signals import post_save
from django.dispatch import receiver
from notifications.services import NotificationService

@receiver(post_save, sender=Message)
def notify_chat_participants(sender, instance, created, **kwargs):
    if created:
        recipients = instance.chat.participants.exclude(id=instance.author.id)
        
        for recipient in recipients:
            NotificationService.create_notification(
                recipient=recipient,
                notification_type_code='chat_new_message',
                title=f'{instance.author.get_full_name()}',
                message=instance.content,
                content_object=instance,
                action_url=f'/communications/chat/{instance.chat.id}/',
            )
```

---

## 8. Приоритеты и сроки

### MVP (Минимально работающий продукт) - 4 недели
- ✅ Базовые модели
- ✅ Уведомления на сайте (WebSocket)
- ✅ Интеграция с чатами
- ✅ Базовые настройки

### V1.0 - 6 недель
- ✅ Email уведомления
- ✅ Интеграция со всеми модулями
- ✅ Полные настройки
- ✅ UI компоненты

### V2.0 - 10 недель
- ✅ Telegram бот
- ✅ Группировка уведомлений
- ✅ Дайджесты
- ✅ Оптимизация

### V3.0 - Будущее
- ⏳ WhatsApp интеграция
- ⏳ WeChat интеграция
- ⏳ Push уведомления (PWA)
- ⏳ Мобильное приложение

---

## 9. Безопасность и приватность

### 9.1 Защита данных
- Уведомления видны только получателю
- Шифрование sensitive данных
- Регулярная очистка старых уведомлений
- GDPR compliance

### 9.2 Rate Limiting
```python
from django_ratelimit.decorators import ratelimit

@ratelimit(key='user', rate='100/h')
def create_notification_view(request):
    """Ограничение: 100 уведомлений в час на пользователя"""
    pass
```

### 9.3 Permissions
```python
class NotificationPermission:
    @staticmethod
    def can_send_to(sender, recipient, notification_type):
        """Проверка прав на отправку уведомления"""
        # Например, обычный пользователь не может слать system уведомления
        if notification_type.category.code == 'system':
            return sender.is_staff
        return True
```

---

## 10. Мониторинг и аналитика

### Метрики
- Количество отправленных уведомлений (по типам)
- Процент прочитанных уведомлений
- Среднее время до прочтения
- Популярные типы уведомлений
- Предпочитаемые каналы пользователей

### Логирование
```python
import logging

logger = logging.getLogger('notifications')

logger.info(f'Notification sent: {notification.id} to {recipient.id}')
logger.warning(f'Failed to send to Telegram: {telegram_id}')
logger.error(f'Email delivery failed: {error}')
```

---

## Заключение

Система уведомлений - критически важный компонент для engagement пользователей. План рассчитан на поэтапную реализацию с возможностью использования базового функционала уже через 4 недели.

**Следующий шаг:** Начать с Этапа 1 - создание моделей и базовой инфраструктуры.
