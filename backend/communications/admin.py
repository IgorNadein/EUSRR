from django.contrib import admin
from .models import (
    AvailableReaction,
    Chat,
    ChatMembership,
    ChatUserSettings,
    CrossChatMessage,
    ForwardedMessage,
    Message,
    MessageAttachment,
    MessageReaction,
    MessageReply,
    Poll,
    PollOption,
    PollVote,
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


@admin.register(MessageReaction)
class MessageReactionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "message",
        "user",
        "emoji",
        "created_at"
    )
    list_filter = ("emoji", "created_at")
    search_fields = ("message__content", "user__last_name", "emoji")
    ordering = ("-created_at",)
    readonly_fields = ("created_at",)


@admin.register(AvailableReaction)
class AvailableReactionAdmin(admin.ModelAdmin):
    list_display = (
        "emoji",
        "name",
        "order",
        "is_active",
        "created_at"
    )
    list_filter = ("is_active", "created_at")
    search_fields = ("emoji", "name")
    ordering = ("order", "created_at")
    list_editable = ("order", "is_active")
    readonly_fields = ("created_at",)
    
    fieldsets = (
        ("Основное", {
            "fields": ("emoji", "name", "is_active")
        }),
        ("Отображение", {
            "fields": ("order",)
        }),
        ("Информация", {
            "fields": ("created_at",),
            "classes": ("collapse",)
        }),
    )


class PollOptionInline(admin.TabularInline):
    model = PollOption
    extra = 0
    readonly_fields = ("vote_count", "created_at")
    ordering = ["position"]


class PollVoteInline(admin.TabularInline):
    model = PollVote
    extra = 0
    readonly_fields = ("voter", "option", "voted_at")
    can_delete = False


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "question_short",
        "author",
        "total_voters",
        "is_closed",
        "created_at"
    )
    list_filter = (
        "is_anonymous",
        "is_multiple_choice",
        "is_quiz",
        "is_closed",
        "created_at"
    )
    search_fields = ("question", "author__last_name")
    ordering = ("-created_at",)
    readonly_fields = (
        "created_at",
        "updated_at",
        "closed_at",
        "total_voters"
    )
    inlines = [PollOptionInline, PollVoteInline]
    
    def question_short(self, obj):
        return (
            obj.question[:50] + "..."
            if len(obj.question) > 50
            else obj.question
        )
    question_short.short_description = "Вопрос"


@admin.register(PollOption)
class PollOptionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "poll_question_short",
        "text",
        "vote_count",
        "is_correct"
    )
    list_filter = ("is_correct", "created_at")
    search_fields = ("text", "poll__question")
    ordering = ("poll", "position")
    readonly_fields = ("vote_count", "created_at")
    
    def poll_question_short(self, obj):
        return (
            obj.poll.question[:30] + "..."
            if len(obj.poll.question) > 30
            else obj.poll.question
        )
    poll_question_short.short_description = "Голосование"


@admin.register(PollVote)
class PollVoteAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "poll_question_short",
        "voter",
        "option_text_short",
        "voted_at"
    )
    list_filter = ("voted_at",)
    search_fields = (
        "poll__question",
        "voter__last_name",
        "option__text"
    )
    ordering = ("-voted_at",)
    readonly_fields = ("voted_at",)
    
    def poll_question_short(self, obj):
        return (
            obj.poll.question[:30] + "..."
            if len(obj.poll.question) > 30
            else obj.poll.question
        )
    poll_question_short.short_description = "Голосование"
    
    def option_text_short(self, obj):
        return (
            obj.option.text[:20] + "..."
            if len(obj.option.text) > 20
            else obj.option.text
        )
    option_text_short.short_description = "Вариант"
