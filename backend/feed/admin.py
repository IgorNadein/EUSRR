from django.contrib import admin
from .models import Post


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "type",
        "author",
        "department",
        "created_at",
        "pinned",
    ]
    list_filter = ["type", "department", "pinned"]
    search_fields = ["title", "body", "author__last_name"]
