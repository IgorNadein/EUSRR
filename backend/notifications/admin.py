"""
Admin для упрощенной системы уведомлений
"""

from django.contrib import admin
from django.utils.html import format_html
from django.utils.safestring import mark_safe
from .models import Notification, UserChannelPreferences


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    """Admin для модели Notification"""
    
    list_display = [
        'id',
        'get_actor_display',
        'verb',
        'get_recipient_display',
        'unread',
        'public',
        'deleted',
        'emailed',
        'timestamp',
    ]
    
    list_filter = [
        'unread',
        'public',
        'deleted',
        'emailed',
        'verb',
        'timestamp',
    ]
    
    search_fields = [
        'recipient__username',
        'recipient__first_name',
        'recipient__last_name',
        'recipient__email',
        'verb',
        'description',
    ]
    
    readonly_fields = [
        'get_actor_info',
        'get_action_object_info',
        'get_target_info',
        'timestamp',
        'timestamp_read',
    ]
    
    fieldsets = (
        ('Основная информация', {
            'fields': (
                'recipient',
                'verb',
                'description',
                'action_url',
            )
        }),
        ('Связанные объекты', {
            'fields': (
                'get_actor_info',
                'get_action_object_info',
                'get_target_info',
            ),
            'classes': ('collapse',),
        }),
        ('Дополнительные данные', {
            'fields': (
                'data',
            ),
            'classes': ('collapse',),
        }),
        ('Статусы', {
            'fields': (
                'unread',
                'timestamp_read',
                'public',
                'deleted',
                'emailed',
            )
        }),
        ('Временные метки', {
            'fields': (
                'timestamp',
            )
        }),
    )
    
    date_hierarchy = 'timestamp'
    
    actions = [
        'mark_as_read',
        'mark_as_unread',
        'mark_as_deleted',
        'mark_as_not_deleted',
    ]
    
    def get_actor_display(self, obj):
        """Отображение актора в списке"""
        if obj.actor:
            return format_html(
                '<span title="{}">{}</span>',
                obj.actor_content_type.model,
                str(obj.actor)[:50]
            )
        return '-'
    get_actor_display.short_description = 'Актор'
    
    def get_recipient_display(self, obj):
        """Отображение получателя"""
        return format_html(
            '<a href="/admin/employees/employee/{}/change/">{}</a>',
            obj.recipient.id,
            obj.recipient.get_short_name()
        )
    get_recipient_display.short_description = 'Получатель'
    
    def get_actor_info(self, obj):
        """Подробная информация об акторе"""
        if not obj.actor:
            return '-'
        
        info = f"""
        <strong>Тип:</strong> {obj.actor_content_type.model}<br>
        <strong>ID:</strong> {obj.actor_object_id}<br>
        <strong>Объект:</strong> {obj.actor}
        """
        return mark_safe(info)
    get_actor_info.short_description = 'Информация об акторе'
    
    def get_action_object_info(self, obj):
        """Подробная информация об объекте действия"""
        if not obj.action_object:
            return '-'
        
        info = f"""
        <strong>Тип:</strong> {obj.action_object_content_type.model}<br>
        <strong>ID:</strong> {obj.action_object_object_id}<br>
        <strong>Объект:</strong> {obj.action_object}
        """
        return mark_safe(info)
    get_action_object_info.short_description = 'Объект действия'
    
    def get_target_info(self, obj):
        """Подробная информация о целевом объекте"""
        if not obj.target:
            return '-'
        
        info = f"""
        <strong>Тип:</strong> {obj.target_content_type.model}<br>
        <strong>ID:</strong> {obj.target_object_id}<br>
        <strong>Объект:</strong> {obj.target}
        """
        return mark_safe(info)
    get_target_info.short_description = 'Целевой объект'
    
    # === Actions ===
    
    @admin.action(description='Отметить как прочитанные')
    def mark_as_read(self, request, queryset):
        """Отметить выбранные уведомления как прочитанные"""
        count = 0
        for notification in queryset:
            if notification.unread:
                notification.mark_as_read()
                count += 1
        
        self.message_user(request, f'Отмечено как прочитанные: {count} уведомлений')
    
    @admin.action(description='Отметить как непрочитанные')
    def mark_as_unread(self, request, queryset):
        """Отметить выбранные уведомления как непрочитанные"""
        count = 0
        for notification in queryset:
            if not notification.unread:
                notification.mark_as_unread()
                count += 1
        
        self.message_user(request, f'Отмечено как непрочитанные: {count} уведомлений')
    
    @admin.action(description='Пометить как удаленные')
    def mark_as_deleted(self, request, queryset):
        """Пометить как удаленные (мягкое удаление)"""
        count = queryset.filter(deleted=False).update(deleted=True)
        self.message_user(request, f'Помечено как удаленные: {count} уведомлений')
    
    @admin.action(description='Восстановить удаленные')
    def mark_as_not_deleted(self, request, queryset):
        """Восстановить удаленные"""
        count = queryset.filter(deleted=True).update(deleted=False)
        self.message_user(request, f'Восстановлено: {count} уведомлений')


@admin.register(UserChannelPreferences)
class UserChannelPreferencesAdmin(admin.ModelAdmin):
    """Admin для настроек каналов пользователя"""
    
    list_display = [
        'user',
        'web_enabled',
        'email_enabled',
        'push_enabled',
        'email_frequency',
        'dnd_enabled',
        'get_disabled_verbs_count',
    ]
    
    list_filter = [
        'web_enabled',
        'email_enabled',
        'push_enabled',
        'email_frequency',
        'dnd_enabled',
    ]
    
    search_fields = [
        'user__username',
        'user__first_name',
        'user__last_name',
        'user__email',
    ]
    
    fieldsets = (
        ('Пользователь', {
            'fields': ('user',)
        }),
        ('Каналы доставки', {
            'fields': (
                'web_enabled',
                'email_enabled',
                'push_enabled',
            )
        }),
        ('Email настройки', {
            'fields': (
                'email_frequency',
            )
        }),
        ('Режим "Не беспокоить"', {
            'fields': (
                'dnd_enabled',
                'dnd_start_time',
                'dnd_end_time',
            )
        }),
        ('Фильтры', {
            'fields': (
                'disabled_verbs',
            ),
            'classes': ('collapse',),
        }),
    )
    
    readonly_fields = []
    
    def get_disabled_verbs_count(self, obj):
        """Количество отключенных типов"""
        count = len(obj.disabled_verbs)
        if count == 0:
            return '-'
        return format_html(
            '<span title="{}">{} типов</span>',
            ', '.join(obj.disabled_verbs),
            count
        )
    get_disabled_verbs_count.short_description = 'Отключено типов'
