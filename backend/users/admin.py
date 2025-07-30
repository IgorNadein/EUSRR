from django.contrib import admin
from django.utils.translation import gettext_lazy as _

from .models import Employee, EmployeeAction


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        'last_name', 'first_name', 'phone_number', 'position', 'employment_status', 'is_actually_active'
    )
    list_filter = ('position',)
    search_fields = ('last_name', 'first_name', 'phone_number', 'email')
    readonly_fields = ('created_at', 'updated_at')
    ordering = ('last_name', 'first_name')
    fieldsets = (
        (None, {
            'fields': ('first_name', 'last_name', 'patronymic', 'gender', 'avatar', 'birth_date')
        }),
        (_('Contact Info'), {
            'fields': ('phone_number', 'email', 'telegram', 'whatsapp')
        }),
        (_('Job'), {
            'fields': ('position',)
        }),
        (_('Timestamps'), {
            'fields': ('created_at', 'updated_at'),
            'classes': ('collapse',),
        }),
    )


@admin.register(EmployeeAction)
class EmployeeActionAdmin(admin.ModelAdmin):
    list_display = ('employee', 'action', 'date', 'comment')
    list_filter = ('action', 'date')
    search_fields = ('employee__last_name', 'employee__first_name', 'comment')
    date_hierarchy = 'date'
    ordering = ('-date',)

    def save_model(self, request, obj, form, change):
        # При создании или обновлении записи автоматически обновляем статус сотрудника
        super().save_model(request, obj, form, change)