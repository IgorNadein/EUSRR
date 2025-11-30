from django.contrib import admin
from .models import (
    Chat,
    ChatMembership,
    ChatUserSettings,
    CrossChatMessage,
    ForwardedMessage,
    Message,
    MessageAttachment,
    MessageReply,
    MessengerIntegration,
    MessengerAccount,
    MessengerMessage,
)


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("author", "content", "created_at")
    can_delete = False
    verbose_name = "Сообщение"
    verbose_name_plural = "Сообщения"


class ChatMembershipInline(admin.TabularInline):
    model = ChatMembership
    extra = 0
    readonly_fields = ("joined_at", "left_at")


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "type",
        "name",
        "department",
        "is_main",
        "created_by",
        "created_at"
    )
    list_filter = ("type", "is_main", "created_at")
    search_fields = ("name", "description", "department__name")
    ordering = ("-created_at",)
    filter_horizontal = ("participants",)
    inlines = [ChatMembershipInline, MessageInline]
    readonly_fields = ("created_at",)

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.is_main:
            return self.readonly_fields + ("type", "department", "is_main")
        return self.readonly_fields


class MessageAttachmentInline(admin.TabularInline):
    model = MessageAttachment
    extra = 0
    readonly_fields = ("uploaded_at", "file_size", "mime_type")


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "chat",
        "author",
        "short_content",
        "is_edited",
        "is_deleted",
        "is_pinned",
        "created_at"
    )
    list_filter = (
        "created_at",
        "is_edited",
        "is_deleted",
        "is_pinned",
        "is_forwarded"
    )
    search_fields = ("content", "author__last_name", "author__first_name")
    ordering = ("-created_at",)
    inlines = [MessageAttachmentInline]
    readonly_fields = ("created_at", "edited_at", "deleted_at")

    def short_content(self, obj):
        return (obj.content[:50] + "...") if len(obj.content) > 50 else obj.content

    short_content.short_description = "Текст"


@admin.register(MessageAttachment)
class MessageAttachmentAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "message",
        "file_name",
        "file_type",
        "file_size",
        "uploaded_at"
    )
    list_filter = ("file_type", "uploaded_at")
    search_fields = ("file_name", "message__content")
    ordering = ("-uploaded_at",)


@admin.register(ChatMembership)
class ChatMembershipAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "chat",
        "user",
        "role",
        "is_active",
        "joined_at"
    )
    list_filter = ("role", "is_active", "joined_at")
    search_fields = ("user__last_name", "user__first_name", "chat__name")
    ordering = ("-joined_at",)


@admin.register(ChatUserSettings)
class ChatUserSettingsAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "chat",
        "is_pinned",
        "notifications_enabled",
        "is_hidden"
    )
    list_filter = ("is_pinned", "notifications_enabled", "is_hidden")
    search_fields = ("user__last_name", "chat__name")


@admin.register(ForwardedMessage)
class ForwardedMessageAdmin(admin.ModelAdmin):
    list_display = (
        "message",
        "original_author",
        "forwarded_by",
        "forward_count",
        "forwarded_at"
    )
    list_filter = ("forwarded_at",)
    search_fields = ("message__content", "original_author__last_name")
    ordering = ("-forwarded_at",)


@admin.register(MessageReply)
class MessageReplyAdmin(admin.ModelAdmin):
    list_display = (
        "message",
        "replied_to",
        "reply_type",
        "is_cross_chat_reply",
        "created_at"
    )
    list_filter = ("reply_type", "is_cross_chat_reply", "created_at")
    ordering = ("-created_at",)


@admin.register(CrossChatMessage)
class CrossChatMessageAdmin(admin.ModelAdmin):
    list_display = (
        "message",
        "sender",
        "target_chat",
        "status",
        "requires_moderation",
        "sent_at"
    )
    list_filter = ("status", "requires_moderation", "sent_at")
    search_fields = ("sender__last_name", "target_chat__name")
    ordering = ("-sent_at",)


# ===== АДМИН-ПАНЕЛЬ ДЛЯ ИНТЕГРАЦИЙ С МЕССЕНДЖЕРАМИ =====

@admin.register(MessengerIntegration)
class MessengerIntegrationAdmin(admin.ModelAdmin):
    list_display = (
        "messenger_type",
        "is_enabled",
        "status",
        "messages_sent",
        "messages_received",
        "last_sync_at",
        "updated_at"
    )
    list_filter = ("messenger_type", "is_enabled", "status")
    search_fields = ("messenger_type",)
    ordering = ("messenger_type",)
    
    fieldsets = (
        ("Основная информация", {
            "fields": ("messenger_type", "is_enabled", "status")
        }),
        ("API Настройки", {
            "fields": ("api_key", "api_secret", "webhook_url", "settings"),
            "classes": ("collapse",)
        }),
        ("Статистика", {
            "fields": (
                "messages_sent",
                "messages_received",
                "last_sync_at",
                "last_error"
            ),
            "classes": ("collapse",)
        }),
        ("Системная информация", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
    
    readonly_fields = (
        "messages_sent",
        "messages_received",
        "last_sync_at",
        "created_at",
        "updated_at"
    )
    
    def get_readonly_fields(self, request, obj=None):
        if obj and obj.status == 'active':
            return self.readonly_fields + ("messenger_type",)
        return self.readonly_fields


@admin.register(MessengerAccount)
class MessengerAccountAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "integration",
        "external_username",
        "phone_number",
        "is_verified",
        "is_active",
        "updated_at"
    )
    list_filter = (
        "integration__messenger_type",
        "is_verified",
        "is_active"
    )
    search_fields = (
        "user__last_name",
        "user__first_name",
        "external_username",
        "phone_number",
        "external_id"
    )
    ordering = ("-created_at",)
    
    fieldsets = (
        ("Пользователь", {
            "fields": ("user", "integration")
        }),
        ("Данные в мессенджере", {
            "fields": (
                "external_id",
                "external_username",
                "phone_number"
            )
        }),
        ("Статус", {
            "fields": ("is_verified", "is_active")
        }),
        ("Дополнительно", {
            "fields": ("metadata",),
            "classes": ("collapse",)
        }),
        ("Системная информация", {
            "fields": ("created_at", "updated_at"),
            "classes": ("collapse",)
        }),
    )
    
    readonly_fields = ("created_at", "updated_at")


@admin.register(MessengerMessage)
class MessengerMessageAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "integration",
        "direction",
        "status",
        "sender_account",
        "content_preview",
        "external_timestamp",
        "synced_at"
    )
    list_filter = (
        "integration__messenger_type",
        "direction",
        "status",
        "external_timestamp"
    )
    search_fields = (
        "external_id",
        "content",
        "sender_account__external_username"
    )
    ordering = ("-external_timestamp",)
    
    fieldsets = (
        ("Основная информация", {
            "fields": (
                "integration",
                "internal_message",
                "external_id"
            )
        }),
        ("Участники", {
            "fields": (
                "sender_account",
                "recipient_account",
                "direction"
            )
        }),
        ("Содержимое", {
            "fields": ("content", "attachments")
        }),
        ("Статус и время", {
            "fields": (
                "status",
                "external_timestamp",
                "synced_at"
            )
        }),
        ("Дополнительно", {
            "fields": ("raw_data",),
            "classes": ("collapse",)
        }),
    )
    
    readonly_fields = ("synced_at",)
    
    def content_preview(self, obj):
        """Превью содержимого сообщения"""
        if len(obj.content) > 50:
            return obj.content[:50] + "..."
        return obj.content
    
    content_preview.short_description = "Содержимое"
