from django.contrib import admin

from .models import (
    Task,
    TaskActivity,
    TaskBoard,
    TaskColumn,
    TaskLabel,
    TaskLinkedObject,
    TaskUserSettings,
)


class TaskColumnInline(admin.TabularInline):
    model = TaskColumn
    extra = 0
    fields = ["name", "position", "color", "is_done", "is_archived"]


class TaskLabelInline(admin.TabularInline):
    model = TaskLabel
    extra = 0
    fields = ["name", "color"]


@admin.register(TaskBoard)
class TaskBoardAdmin(admin.ModelAdmin):
    list_display = ["name", "created_by", "is_archived", "created_at"]
    list_filter = ["is_archived", "created_at"]
    search_fields = ["name", "description"]
    filter_horizontal = ["members", "departments"]
    inlines = [TaskColumnInline, TaskLabelInline]


@admin.register(TaskColumn)
class TaskColumnAdmin(admin.ModelAdmin):
    list_display = ["name", "board", "position", "is_done", "is_archived"]
    list_filter = ["is_done", "is_archived", "board"]
    search_fields = ["name", "board__name"]


@admin.register(TaskLabel)
class TaskLabelAdmin(admin.ModelAdmin):
    list_display = ["name", "board", "color"]
    list_filter = ["board"]
    search_fields = ["name", "board__name"]


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "board",
        "column",
        "assignee",
        "priority",
        "due_date",
        "completed_at",
    ]
    list_filter = ["board", "column", "priority", "due_date"]
    search_fields = ["title", "description", "assignee__email"]
    filter_horizontal = ["labels"]


@admin.register(TaskLinkedObject)
class TaskLinkedObjectAdmin(admin.ModelAdmin):
    list_display = ["task", "kind", "content_type", "object_id", "created_by", "created_at"]
    list_filter = ["kind", "content_type", "created_at"]
    search_fields = ["task__title", "created_by__email", "object_id"]


@admin.register(TaskActivity)
class TaskActivityAdmin(admin.ModelAdmin):
    list_display = ["task", "action", "actor", "object_kind", "object_id", "created_at"]
    list_filter = ["action", "object_kind", "created_at"]
    search_fields = ["task__title", "actor__email", "object_id"]


@admin.register(TaskUserSettings)
class TaskUserSettingsAdmin(admin.ModelAdmin):
    list_display = ["user", "default_board", "updated_at"]
    search_fields = ["user__email", "user__first_name", "user__last_name", "default_board__name"]
    autocomplete_fields = ["user", "default_board"]
