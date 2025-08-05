from django.contrib import admin
from .models import (
    Employee, EmployeeAction, Department, EmployeePosition,
    Absence, Skill, Education
)
from django.utils.html import format_html


class EmployeeActionInline(admin.TabularInline):
    model = EmployeeAction
    extra = 0
    fields = ('action', 'date', 'comment')
    readonly_fields = ('action', 'date', 'comment')
    can_delete = False
    show_change_link = True


class EmployeePositionInline(admin.TabularInline):
    model = EmployeePosition
    extra = 0
    fields = ('department', 'title', 'date_from', 'date_to', 'is_active')
    readonly_fields = ('is_active',)
    show_change_link = True


class AbsenceInline(admin.TabularInline):
    model = Absence
    extra = 0
    fields = ('type', 'date_from', 'date_to', 'status', 'comment')
    readonly_fields = ()
    show_change_link = True


class EducationInline(admin.TabularInline):
    model = Education
    extra = 0
    fields = ('institution', 'degree', 'graduation_year')
    show_change_link = True


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    list_display = (
        'last_name', 'first_name', 'patronymic', 'gender', 'phone_number',
        'email', 'department_list', 'current_position', 'employment_status',
        'is_actually_active', 'created_at'
    )
    list_filter = ('gender', 'positions__department', 'actions__action')
    search_fields = (
        'last_name', 'first_name', 'patronymic', 'email', 'phone_number',
        'telegram', 'whatsapp', 'wechat'
    )
    readonly_fields = ('created_at', 'updated_at',
                       'employment_status', 'is_actually_active', 'avatar_preview')
    inlines = [EmployeeActionInline, EmployeePositionInline,
               AbsenceInline, EducationInline]
    filter_horizontal = ('skills',)
    fieldsets = (
        (None, {
            'fields': (
                ('last_name', 'first_name', 'patronymic'),
                ('gender', 'birth_date'),
                ('avatar', 'avatar_preview'),
                ('phone_number', 'email'),
                ('telegram', 'whatsapp', 'wechat'),
                ('skills',),
                ('created_at', 'updated_at'),
            )
        }),
        ('Служебная информация', {
            'fields': (
                'employment_status',
                'is_actually_active',
            )
        }),
    )

    def department_list(self, obj):
        departments = set(
            p.department.name for p in obj.positions.all() if p.is_active)
        return ", ".join(departments) if departments else "—"
    department_list.short_description = "Отдел(ы)"

    def current_position(self, obj):
        active_positions = obj.positions.filter(date_to__isnull=True)
        return ", ".join(p.title for p in active_positions) if active_positions else "—"
    current_position.short_description = "Должность(и)"

    def avatar_preview(self, obj):
        if obj.avatar:
            return format_html('<img src="{}" style="height:64px;width:64px;border-radius:50%;" />', obj.avatar.url)
        return "—"
    avatar_preview.short_description = "Аватар"

    # Отображаем статус трудоустройства через @property
    def employment_status(self, obj):
        return obj.employment_status
    employment_status.short_description = "Статус"

    def is_actually_active(self, obj):
        return obj.is_actually_active
    is_actually_active.boolean = True
    is_actually_active.short_description = "Работает?"


@admin.register(EmployeeAction)
class EmployeeActionAdmin(admin.ModelAdmin):
    list_display = ('employee', 'action', 'date', 'comment')
    list_filter = ('action',)
    search_fields = ('employee__last_name', 'employee__first_name', 'comment')
    date_hierarchy = 'date'


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ('name', 'head', 'created_at', 'description')
    search_fields = ('name',)
    list_filter = ('head',)
    readonly_fields = ('created_at',)


@admin.register(EmployeePosition)
class EmployeePositionAdmin(admin.ModelAdmin):
    list_display = ('employee', 'department', 'title',
                    'date_from', 'date_to', 'is_active')
    list_filter = ('department',)
    search_fields = ('employee__last_name', 'employee__first_name', 'title')
    readonly_fields = ('is_active',)

    def is_active(self, obj):
        return obj.is_active
    is_active.boolean = True
    is_active.short_description = "Текущая?"


@admin.register(Absence)
class AbsenceAdmin(admin.ModelAdmin):
    list_display = ('employee', 'type', 'date_from',
                    'date_to', 'status', 'comment')
    list_filter = ('type', 'status')
    search_fields = ('employee__last_name', 'employee__first_name', 'comment')


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ('name', 'employee_count')
    search_fields = ('name',)

    def employee_count(self, obj):
        return obj.employees.count()
    employee_count.short_description = "Кол-во сотрудников"


@admin.register(Education)
class EducationAdmin(admin.ModelAdmin):
    list_display = ('employee', 'institution', 'degree', 'graduation_year')
    search_fields = ('employee__last_name', 'institution', 'degree')
    list_filter = ('graduation_year',)
