from django.db import models
from django.conf import settings
from django.utils import timezone
from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType


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
    
    code = models.CharField(
        max_length=50, 
        unique=True, 
        choices=CATEGORY_CHOICES,
        verbose_name='Код'
    )
    name = models.CharField(max_length=100, verbose_name='Название')
    description = models.TextField(blank=True, verbose_name='Описание')
    icon = models.CharField(
        max_length=50, 
        default='bi-bell',
        verbose_name='Иконка',
        help_text='Bootstrap icon класс'
    )
    color = models.CharField(
        max_length=20, 
        default='primary',
        verbose_name='Цвет',
        help_text='Bootstrap цвет'
    )
    is_active = models.BooleanField(default=True, verbose_name='Активна')
    order = models.IntegerField(default=0, verbose_name='Порядок')
    
    class Meta:
        ordering = ['order', 'name']
        verbose_name = 'Категория уведомлений'
        verbose_name_plural = 'Категории уведомлений'
        db_table = 'notifications_category'
    
    def __str__(self):
        return self.name


class NotificationType(models.Model):
    """Конкретные типы уведомлений внутри категорий"""
    
    category = models.ForeignKey(
        NotificationCategory, 
        on_delete=models.CASCADE, 
        related_name='types',
        verbose_name='Категория'
    )
    code = models.CharField(
        max_length=100, 
        unique=True,
        verbose_name='Код',
        help_text='Уникальный код типа, например: chat_new_message'
    )
    name = models.CharField(max_length=200, verbose_name='Название')
    description = models.TextField(blank=True, verbose_name='Описание')
    
    # Настройки по умолчанию для всех пользователей
    default_enabled = models.BooleanField(
        default=True,
        verbose_name='Включено по умолчанию'
    )
    default_channels = models.JSONField(
        default=dict,
        verbose_name='Каналы по умолчанию',
        help_text='{"web": true, "email": false, "telegram": false}'
    )
    
    # Приоритет
    PRIORITY_CHOICES = [
        ('low', 'Низкий'),
        ('normal', 'Обычный'),
        ('high', 'Высокий'),
        ('urgent', 'Срочный'),
    ]
    priority = models.CharField(
        max_length=20, 
        choices=PRIORITY_CHOICES, 
        default='normal',
        verbose_name='Приоритет'
    )
    
    # Можно ли отключить
    is_required = models.BooleanField(
        default=False,
        verbose_name='Обязательное',
        help_text='Нельзя отключить (например, системные уведомления)'
    )
    
    # Группировка
    is_groupable = models.BooleanField(
        default=True,
        verbose_name='Можно группировать',
        help_text='Объединять несколько похожих уведомлений'
    )
    grouping_window_minutes = models.IntegerField(
        default=5,
        verbose_name='Окно группировки (минуты)',
        help_text='Группировать уведомления за последние N минут'
    )
    
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлен')
    
    class Meta:
        ordering = ['category__order', 'name']
        verbose_name = 'Тип уведомления'
        verbose_name_plural = 'Типы уведомлений'
        db_table = 'notifications_type'
    
    def __str__(self):
        return f'{self.category.name}: {self.name}'


class Notification(models.Model):
    """Конкретное уведомление для пользователя"""
    
    recipient = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='notifications',
        verbose_name='Получатель'
    )
    notification_type = models.ForeignKey(
        NotificationType, 
        on_delete=models.CASCADE,
        verbose_name='Тип'
    )
    
    # Заголовок и текст
    title = models.CharField(max_length=255, verbose_name='Заголовок')
    message = models.TextField(verbose_name='Сообщение')
    short_message = models.CharField(
        max_length=150, 
        blank=True,
        verbose_name='Краткое сообщение',
        help_text='Для превью'
    )
    
    # Связь с объектом (GenericForeignKey)
    content_type = models.ForeignKey(
        ContentType, 
        on_delete=models.CASCADE, 
        null=True, 
        blank=True,
        verbose_name='Тип объекта'
    )
    object_id = models.PositiveIntegerField(
        null=True, 
        blank=True,
        verbose_name='ID объекта'
    )
    content_object = GenericForeignKey('content_type', 'object_id')
    
    # Метаданные
    metadata = models.JSONField(
        default=dict, 
        blank=True,
        verbose_name='Метаданные',
        help_text='Дополнительные данные для рендеринга'
    )
    
    # Ссылка действия
    action_url = models.CharField(
        max_length=500, 
        blank=True,
        verbose_name='Ссылка действия'
    )
    action_text = models.CharField(
        max_length=100, 
        default='Посмотреть',
        verbose_name='Текст кнопки'
    )
    
    # Статусы
    is_read = models.BooleanField(
        default=False,
        verbose_name='Прочитано',
        db_index=True
    )
    read_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name='Прочитано когда'
    )
    
    is_archived = models.BooleanField(
        default=False,
        verbose_name='В архиве'
    )
    archived_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name='Заархивировано когда'
    )
    
    # Доставка
    sent_web = models.BooleanField(default=False, verbose_name='Отправлено на сайт')
    sent_email = models.BooleanField(default=False, verbose_name='Отправлено на email')
    sent_telegram = models.BooleanField(default=False, verbose_name='Отправлено в Telegram')
    sent_whatsapp = models.BooleanField(default=False, verbose_name='Отправлено в WhatsApp')
    sent_wechat = models.BooleanField(default=False, verbose_name='Отправлено в WeChat')
    
    sent_at = models.DateTimeField(
        null=True, 
        blank=True,
        verbose_name='Отправлено когда'
    )
    
    # Группировка
    group_key = models.CharField(
        max_length=255, 
        blank=True, 
        db_index=True,
        verbose_name='Ключ группировки',
        help_text='Для объединения похожих уведомлений'
    )
    is_grouped = models.BooleanField(
        default=False,
        verbose_name='Сгруппировано'
    )
    grouped_count = models.IntegerField(
        default=1,
        verbose_name='Количество в группе',
        help_text='Сколько уведомлений объединено'
    )
    
    created_at = models.DateTimeField(
        auto_now_add=True, 
        db_index=True,
        verbose_name='Создано'
    )
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    
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
        db_table = 'notifications_notification'
    
    def __str__(self):
        return f'{self.recipient.get_short_name()}: {self.title}'
    
    def mark_as_read(self):
        """Отметить как прочитанное"""
        if not self.is_read:
            self.is_read = True
            self.read_at = timezone.now()
            self.save(update_fields=['is_read', 'read_at'])
    
    def archive(self):
        """Заархивировать уведомление"""
        if not self.is_archived:
            self.is_archived = True
            self.archived_at = timezone.now()
            self.save(update_fields=['is_archived', 'archived_at'])


class UserNotificationSettings(models.Model):
    """Персональные настройки уведомлений пользователя"""
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, 
        on_delete=models.CASCADE, 
        related_name='notification_settings',
        verbose_name='Пользователь'
    )
    notification_type = models.ForeignKey(
        NotificationType, 
        on_delete=models.CASCADE,
        verbose_name='Тип уведомления'
    )
    
    # Включено ли уведомление
    is_enabled = models.BooleanField(
        default=True,
        verbose_name='Включено'
    )
    
    # Каналы доставки
    send_web = models.BooleanField(
        default=True,
        verbose_name='Отправлять на сайт'
    )
    send_email = models.BooleanField(
        default=False,
        verbose_name='Отправлять на email'
    )
    send_telegram = models.BooleanField(
        default=False,
        verbose_name='Отправлять в Telegram'
    )
    send_whatsapp = models.BooleanField(
        default=False,
        verbose_name='Отправлять в WhatsApp'
    )
    send_wechat = models.BooleanField(
        default=False,
        verbose_name='Отправлять в WeChat'
    )
    
    # Тихий режим (не беспокоить)
    quiet_hours_enabled = models.BooleanField(
        default=False,
        verbose_name='Тихий режим включен'
    )
    quiet_start_time = models.TimeField(
        null=True, 
        blank=True,
        verbose_name='Начало тихого режима',
        help_text='Например, 22:00'
    )
    quiet_end_time = models.TimeField(
        null=True, 
        blank=True,
        verbose_name='Конец тихого режима',
        help_text='Например, 08:00'
    )
    
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создано')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлено')
    
    class Meta:
        unique_together = ['user', 'notification_type']
        verbose_name = 'Настройка уведомлений пользователя'
        verbose_name_plural = 'Настройки уведомлений пользователей'
        db_table = 'notifications_user_settings'
    
    def __str__(self):
        return f'{self.user.get_short_name()}: {self.notification_type.name}'


class NotificationTemplate(models.Model):
    """Шаблоны для разных каналов доставки"""
    
    notification_type = models.ForeignKey(
        NotificationType, 
        on_delete=models.CASCADE, 
        related_name='templates',
        verbose_name='Тип уведомления'
    )
    
    CHANNEL_CHOICES = [
        ('web', 'Веб'),
        ('email', 'Email'),
        ('telegram', 'Telegram'),
        ('whatsapp', 'WhatsApp'),
        ('wechat', 'WeChat'),
    ]
    channel = models.CharField(
        max_length=20, 
        choices=CHANNEL_CHOICES,
        verbose_name='Канал'
    )
    
    # Шаблоны (используем Django template syntax)
    title_template = models.TextField(
        verbose_name='Шаблон заголовка',
        help_text='Django template синтаксис'
    )
    message_template = models.TextField(
        verbose_name='Шаблон сообщения',
        help_text='Django template синтаксис'
    )
    
    # Для email
    html_template = models.TextField(
        blank=True,
        verbose_name='HTML шаблон',
        help_text='Для email'
    )
    
    # Для кнопок действий
    action_button_template = models.CharField(
        max_length=200, 
        blank=True,
        verbose_name='Шаблон кнопки действия'
    )
    
    is_active = models.BooleanField(default=True, verbose_name='Активен')
    created_at = models.DateTimeField(auto_now_add=True, verbose_name='Создан')
    updated_at = models.DateTimeField(auto_now=True, verbose_name='Обновлен')
    
    class Meta:
        unique_together = ['notification_type', 'channel']
        verbose_name = 'Шаблон уведомления'
        verbose_name_plural = 'Шаблоны уведомлений'
        db_table = 'notifications_template'
    
    def __str__(self):
        return f'{self.notification_type.name} - {self.get_channel_display()}'

