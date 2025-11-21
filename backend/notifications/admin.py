from django.contrib import admin
from django.utils.html import format_html
from .models import (
    NotificationCategory,
    NotificationType,
    Notification,
    UserNotificationSettings,
    NotificationTemplate,
)
from .telegram_models import TelegramUser


@admin.register(NotificationCategory)
class NotificationCategoryAdmin(admin.ModelAdmin):
    list_display = ['name', 'code', 'icon_preview', 'color', 'order', 'is_active']
    list_editable = ['order', 'is_active']
    list_filter = ['is_active']
    search_fields = ['name', 'code', 'description']
    ordering = ['order', 'name']

    def icon_preview(self, obj):
        return format_html('<i class="{}" style="font-size: 1.2em;"></i>', obj.icon)
    icon_preview.short_description = 'Иконка'


@admin.register(NotificationType)
class NotificationTypeAdmin(admin.ModelAdmin):
    list_display = [
        'name',
        'code',
        'category',
        'priority',
        'default_enabled',
        'is_groupable',
        'is_required',
        'is_active',
    ]
    list_filter = [
        'category',
        'priority',
        'default_enabled',
        'is_groupable',
        'is_required',
        'is_active',
    ]
    search_fields = ['name', 'code', 'description']
    list_editable = ['is_active']
    ordering = ['category__order', 'name']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('category', 'code', 'name', 'description', 'is_active')
        }),
        ('Настройки по умолчанию', {
            'fields': ('default_enabled', 'default_channels', 'priority', 'is_required')
        }),
        ('Группировка', {
            'fields': ('is_groupable', 'grouping_window_minutes'),
            'classes': ('collapse',)
        }),
    )


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'recipient_name',
        'title_short',
        'notification_type',
        'is_read',
        'created_at',
        'channels_sent',
    ]
    list_filter = [
        'is_read',
        'is_archived',
        'notification_type__category',
        'notification_type',
        'created_at',
    ]
    search_fields = [
        'title',
        'message',
        'recipient__first_name',
        'recipient__last_name',
        'recipient__email',
    ]
    readonly_fields = [
        'created_at',
        'updated_at',
        'read_at',
        'sent_at',
        'archived_at',
    ]
    date_hierarchy = 'created_at'
    ordering = ['-created_at']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('recipient', 'notification_type', 'title', 'message', 'short_message')
        }),
        ('Связанный объект', {
            'fields': ('content_type', 'object_id'),
            'classes': ('collapse',)
        }),
        ('Действие', {
            'fields': ('action_url', 'action_text')
        }),
        ('Статус', {
            'fields': ('is_read', 'read_at', 'is_archived', 'archived_at')
        }),
        ('Доставка', {
            'fields': (
                'sent_web',
                'sent_email',
                'sent_telegram',
                'sent_whatsapp',
                'sent_wechat',
                'sent_at',
            ),
            'classes': ('collapse',)
        }),
        ('Группировка', {
            'fields': ('group_key', 'is_grouped', 'grouped_count'),
            'classes': ('collapse',)
        }),
        ('Метаданные', {
            'fields': ('metadata', 'created_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def recipient_name(self, obj):
        return obj.recipient.get_full_name() or obj.recipient.username
    recipient_name.short_description = 'Получатель'
    recipient_name.admin_order_field = 'recipient__last_name'
    
    def title_short(self, obj):
        return obj.title[:50] + '...' if len(obj.title) > 50 else obj.title
    title_short.short_description = 'Заголовок'
    
    def channels_sent(self, obj):
        channels = []
        if obj.sent_web:
            channels.append('🌐 Веб')
        if obj.sent_email:
            channels.append('📧 Email')
        if obj.sent_telegram:
            channels.append('✈️ Telegram')
        if obj.sent_whatsapp:
            channels.append('💬 WhatsApp')
        if obj.sent_wechat:
            channels.append('💚 WeChat')
        return ', '.join(channels) if channels else '—'
    channels_sent.short_description = 'Отправлено'
    
    actions = ['mark_as_read', 'mark_as_unread', 'archive_notifications']
    
    def mark_as_read(self, request, queryset):
        count = 0
        for notification in queryset.filter(is_read=False):
            notification.mark_as_read()
            count += 1
        self.message_user(request, f'Отмечено как прочитанное: {count}')
    mark_as_read.short_description = 'Отметить как прочитанное'
    
    def mark_as_unread(self, request, queryset):
        count = queryset.filter(is_read=True).update(is_read=False, read_at=None)
        self.message_user(request, f'Отмечено как непрочитанное: {count}')
    mark_as_unread.short_description = 'Отметить как непрочитанное'
    
    def archive_notifications(self, request, queryset):
        count = 0
        for notification in queryset.filter(is_archived=False):
            notification.archive()
            count += 1
        self.message_user(request, f'Заархивировано: {count}')
    archive_notifications.short_description = 'Архивировать'


@admin.register(UserNotificationSettings)
class UserNotificationSettingsAdmin(admin.ModelAdmin):
    list_display = [
        'user_name',
        'notification_type',
        'is_enabled',
        'channels_enabled',
        'quiet_hours_status',
    ]
    list_filter = [
        'is_enabled',
        'notification_type__category',
        'send_web',
        'send_email',
        'send_telegram',
        'quiet_hours_enabled',
    ]
    search_fields = [
        'user__first_name',
        'user__last_name',
        'user__email',
        'notification_type__name',
    ]
    ordering = ['user__last_name', 'notification_type__category__order']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'notification_type', 'is_enabled')
        }),
        ('Каналы доставки', {
            'fields': ('send_web', 'send_email', 'send_telegram', 'send_whatsapp', 'send_wechat')
        }),
        ('Тихий режим', {
            'fields': ('quiet_hours_enabled', 'quiet_start_time', 'quiet_end_time'),
            'classes': ('collapse',)
        }),
    )
    
    def user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    user_name.short_description = 'Пользователь'
    user_name.admin_order_field = 'user__last_name'
    
    def channels_enabled(self, obj):
        channels = []
        if obj.send_web:
            channels.append('🌐')
        if obj.send_email:
            channels.append('📧')
        if obj.send_telegram:
            channels.append('✈️')
        if obj.send_whatsapp:
            channels.append('💬')
        if obj.send_wechat:
            channels.append('💚')
        return ' '.join(channels) if channels else '—'
    channels_enabled.short_description = 'Каналы'
    
    def quiet_hours_status(self, obj):
        if obj.quiet_hours_enabled and obj.quiet_start_time and obj.quiet_end_time:
            return f'🌙 {obj.quiet_start_time.strftime("%H:%M")} - {obj.quiet_end_time.strftime("%H:%M")}'
        return '—'
    quiet_hours_status.short_description = 'Тихий режим'


@admin.register(NotificationTemplate)
class NotificationTemplateAdmin(admin.ModelAdmin):
    list_display = [
        'notification_type',
        'channel',
        'is_active',
        'updated_at',
    ]
    list_filter = [
        'channel',
        'is_active',
        'notification_type__category',
    ]
    search_fields = [
        'notification_type__name',
        'title_template',
        'message_template',
    ]
    ordering = ['notification_type__category__order', 'channel']
    
    fieldsets = (
        ('Основная информация', {
            'fields': ('notification_type', 'channel', 'is_active')
        }),
        ('Шаблоны', {
            'fields': ('title_template', 'message_template', 'action_button_template')
        }),
        ('Email (дополнительно)', {
            'fields': ('html_template',),
            'classes': ('collapse',)
        }),
    )


@admin.register(TelegramUser)
class TelegramUserAdmin(admin.ModelAdmin):
    list_display = [
        'user_name',
        'telegram_username',
        'telegram_id',
        'is_active',
        'is_blocked',
        'linked_at',
    ]
    list_filter = [
        'is_active',
        'is_blocked',
        'linked_at',
    ]
    search_fields = [
        'user__first_name',
        'user__last_name',
        'user__email',
        'telegram_username',
        'telegram_id',
    ]
    readonly_fields = [
        'telegram_id',
        'link_code',
        'link_code_created_at',
        'linked_at',
        'last_interaction_at',
        'updated_at',
    ]
    ordering = ['-linked_at']
    
    fieldsets = (
        ('Пользователь', {
            'fields': ('user', 'is_active')
        }),
        ('Telegram информация', {
            'fields': (
                'telegram_id',
                'telegram_username',
                'first_name',
                'last_name',
                'is_blocked',
            )
        }),
        ('Код привязки', {
            'fields': ('link_code', 'link_code_created_at'),
            'classes': ('collapse',)
        }),
        ('Временные метки', {
            'fields': ('linked_at', 'last_interaction_at', 'updated_at'),
            'classes': ('collapse',)
        }),
    )
    
    def user_name(self, obj):
        return obj.user.get_full_name() or obj.user.username
    user_name.short_description = 'Пользователь'
    user_name.admin_order_field = 'user__last_name'
    
    actions = ['unlink_accounts', 'reactivate_accounts']
    
    def unlink_accounts(self, request, queryset):
        count = queryset.filter(is_active=True).update(is_active=False)
        self.message_user(request, f'Отвязано аккаунтов: {count}')
    unlink_accounts.short_description = 'Отвязать аккаунты'
    
    def reactivate_accounts(self, request, queryset):
        count = queryset.update(is_active=True, is_blocked=False)
        self.message_user(request, f'Реактивировано аккаунтов: {count}')
    reactivate_accounts.short_description = 'Реактивировать'
