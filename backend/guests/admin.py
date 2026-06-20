from django.contrib import admin

from .models import Guest, GuestVisit, GuestVisitEvent


@admin.register(Guest)
class GuestAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "full_name",
        "organization",
        "email",
        "phone",
        "ldap_enabled",
        "is_active",
    )
    list_filter = ("ldap_enabled", "is_active", "organization")
    search_fields = (
        "id",
        "last_name",
        "first_name",
        "patronymic",
        "email",
        "phone",
        "organization",
    )
    readonly_fields = (
        "id",
        "ldap_last_synced_at",
        "ldap_last_error",
        "created_at",
        "updated_at",
    )


class GuestVisitEventInline(admin.TabularInline):
    model = GuestVisitEvent
    extra = 0
    readonly_fields = (
        "actor",
        "event_type",
        "from_status",
        "to_status",
        "comment",
        "metadata",
        "created_at",
    )
    can_delete = False


@admin.register(GuestVisit)
class GuestVisitAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "guest",
        "inviter",
        "status",
        "access_starts_at",
        "access_expires_at",
        "unlimited",
        "inviter_inactive",
    )
    list_filter = ("status", "unlimited", "all_day", "inviter_inactive")
    search_fields = (
        "guest__id",
        "guest__last_name",
        "guest__first_name",
        "guest__organization",
        "inviter__email",
        "purpose",
    )
    readonly_fields = (
        "created_at",
        "updated_at",
        "submitted_at",
        "decided_at",
        "cancelled_at",
        "revoked_at",
        "expired_at",
        "inviter_snapshot_name",
        "inviter_snapshot_email",
    )
    inlines = [GuestVisitEventInline]


@admin.register(GuestVisitEvent)
class GuestVisitEventAdmin(admin.ModelAdmin):
    list_display = ("id", "visit", "event_type", "actor", "created_at")
    list_filter = ("event_type", "created_at")
    search_fields = ("visit__guest__last_name", "visit__guest__id", "comment")
    readonly_fields = (
        "visit",
        "actor",
        "event_type",
        "from_status",
        "to_status",
        "comment",
        "metadata",
        "created_at",
    )

