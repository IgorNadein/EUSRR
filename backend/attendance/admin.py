from django.contrib import admin

from attendance.models import AttendanceAnalysisRun, AttendanceRecord


@admin.register(AttendanceAnalysisRun)
class AttendanceAnalysisRunAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "employee",
        "period_start",
        "period_end",
        "status",
        "triggered_by",
        "created_at",
    )
    list_filter = ("status", "created_at")
    search_fields = ("employee__email", "employee__first_name", "employee__last_name")
    readonly_fields = ("created_at",)


@admin.register(AttendanceRecord)
class AttendanceRecordAdmin(admin.ModelAdmin):
    list_display = (
        "employee",
        "date",
        "is_workday",
        "arrival_time",
        "departure_time",
        "work_hours",
        "is_late",
        "is_absent",
        "is_overtime",
        "updated_at",
    )
    list_filter = (
        "is_workday",
        "is_late",
        "is_absent",
        "is_overtime",
        "date",
    )
    search_fields = ("employee__email", "employee__first_name", "employee__last_name")
    readonly_fields = ("updated_at",)
