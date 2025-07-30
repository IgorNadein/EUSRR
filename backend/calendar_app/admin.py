from django.contrib import admin
from .models import CompanyEvent


@admin.register(CompanyEvent)
class CompanyEventAdmin(admin.ModelAdmin):
    list_display = ('title', 'date', 'recurrence', 'created_by')
    list_filter = ('recurrence', 'date', 'created_by')
    search_fields = ('title', 'description', 'created_by__username', 'created_by__phone_number')
    date_hierarchy = 'date'
    ordering = ('recurrence', 'date')
    fieldsets = (
        (None, {
            'fields': ('title', 'description', 'date', 'recurrence')
        }),
        ('Meta', {
            'fields': ('created_by',),
            'classes': ('collapse',),
        }),
    )
    readonly_fields = ('created_by',)

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)
