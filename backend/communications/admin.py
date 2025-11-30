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
