from django.contrib import admin
from .models import Chat, Message


class MessageInline(admin.TabularInline):
    model = Message
    extra = 0
    readonly_fields = ("author", "content", "created_at")
    can_delete = False
    verbose_name = "Сообщение"
    verbose_name_plural = "Сообщения"


@admin.register(Chat)
class ChatAdmin(admin.ModelAdmin):
    list_display = ("type", "department", "is_main", "created_at")
    list_filter = ("type", "is_main", "created_at")
    search_fields = ("department__name",)
    ordering = ("-created_at",)
    filter_horizontal = ("participants",)
    inlines = [MessageInline]

    def get_readonly_fields(self, request, obj=None):
        if obj and obj.is_main:
            return self.readonly_fields + ("type", "department", "is_main")
        return self.readonly_fields


@admin.register(Message)
class MessageAdmin(admin.ModelAdmin):
    list_display = ("chat", "author", "short_content", "created_at")
    list_filter = ("created_at",)
    search_fields = ("content", "author__last_name", "author__first_name")
    ordering = ("-created_at",)

    def short_content(self, obj):
        return (obj.content[:50] + "...") if len(obj.content) > 50 else obj.content

    short_content.short_description = "Текст"
