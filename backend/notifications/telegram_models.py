"""
Модели для интеграции с Telegram
"""
from django.db import models
from django.conf import settings
from django.utils import timezone


class TelegramUser(models.Model):
    """Связь пользователя системы с Telegram аккаунтом"""
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='telegram_account',
        verbose_name='Пользователь'
    )
    
    telegram_id = models.BigIntegerField(
        unique=True,
        null=True,
        blank=True,
        verbose_name='Telegram ID',
        help_text='Уникальный ID пользователя в Telegram'
    )
    
    telegram_username = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        verbose_name='Telegram Username',
        help_text='@username пользователя в Telegram'
    )
    
    first_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Имя в Telegram'
    )
    
    last_name = models.CharField(
        max_length=100,
        blank=True,
        verbose_name='Фамилия в Telegram'
    )
    
    # Код для привязки аккаунта
    link_code = models.CharField(
        max_length=10,
        blank=True,
        null=True,
        unique=True,
        verbose_name='Код привязки',
        help_text='Временный код для привязки аккаунта'
    )
    
    link_code_created_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Код создан'
    )
    
    # Статус
    is_active = models.BooleanField(
        default=True,
        verbose_name='Активен'
    )
    
    is_blocked = models.BooleanField(
        default=False,
        verbose_name='Заблокирован',
        help_text='Пользователь заблокировал бота'
    )
    
    # Даты
    linked_at = models.DateTimeField(
        auto_now_add=True,
        verbose_name='Привязан'
    )
    
    last_interaction_at = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='Последнее взаимодействие'
    )
    
    updated_at = models.DateTimeField(
        auto_now=True,
        verbose_name='Обновлено'
    )
    
    class Meta:
        verbose_name = 'Telegram аккаунт'
        verbose_name_plural = 'Telegram аккаунты'
        db_table = 'notifications_telegram_user'
        indexes = [
            models.Index(fields=['telegram_id']),
            models.Index(fields=['link_code']),
            models.Index(fields=['user']),
        ]
    
    def __str__(self):
        if self.telegram_username:
            username = f"@{self.telegram_username}"
        elif self.telegram_id:
            username = str(self.telegram_id)
        else:
            username = "не привязан"
        return f'{self.user.get_short_name()} ({username})'
    
    def generate_link_code(self):
        """Генерирует уникальный код для привязки аккаунта"""
        import random
        import string
        
        # Генерируем 6-значный код
        code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        # Проверяем уникальность
        while TelegramUser.objects.filter(link_code=code).exists():
            code = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        
        self.link_code = code
        self.link_code_created_at = timezone.now()
        self.save(update_fields=['link_code', 'link_code_created_at'])
        
        return code
    
    def is_link_code_valid(self):
        """Проверяет, действителен ли код привязки (не старше 15 минут)"""
        if not self.link_code or not self.link_code_created_at:
            return False
        
        age = timezone.now() - self.link_code_created_at
        return age.total_seconds() < 900  # 15 минут
    
    def clear_link_code(self):
        """Удаляет код привязки"""
        self.link_code = None
        self.link_code_created_at = None
        self.save(update_fields=['link_code', 'link_code_created_at'])
    
    def update_last_interaction(self):
        """Обновляет время последнего взаимодействия"""
        self.last_interaction_at = timezone.now()
        self.save(update_fields=['last_interaction_at'])
