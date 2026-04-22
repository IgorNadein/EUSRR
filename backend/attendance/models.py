from django.conf import settings
from django.db import models


class AttendanceAnalysisRun(models.Model):
    STATUS_SUCCESS = "success"
    STATUS_FAILED = "failed"
    STATUS_CHOICES = (
        (STATUS_SUCCESS, "Успешно"),
        (STATUS_FAILED, "Ошибка"),
    )

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attendance_analysis_runs",
        verbose_name="Сотрудник",
    )
    period_start = models.DateField("Начало периода")
    period_end = models.DateField("Конец периода")
    status = models.CharField(
        "Статус",
        max_length=16,
        choices=STATUS_CHOICES,
        default=STATUS_SUCCESS,
    )
    schedule_payload = models.JSONField("График", null=True, blank=True)
    request_payload = models.JSONField("Запрос", default=dict, blank=True)
    response_payload = models.JSONField("Ответ", default=dict, blank=True)
    error = models.TextField("Ошибка", blank=True)
    triggered_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="triggered_attendance_analysis_runs",
        verbose_name="Запустил",
    )
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        ordering = ["-created_at", "-id"]
        verbose_name = "Запуск анализа посещаемости"
        verbose_name_plural = "Запуски анализа посещаемости"
        indexes = [
            models.Index(fields=["employee", "period_start", "period_end"]),
            models.Index(fields=["created_at"]),
        ]

    def __str__(self) -> str:
        return f"{self.employee_id}: {self.period_start} - {self.period_end}"


class AttendanceRecord(models.Model):
    analysis_run = models.ForeignKey(
        AttendanceAnalysisRun,
        on_delete=models.CASCADE,
        related_name="records",
        verbose_name="Запуск анализа",
    )
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="attendance_records",
        verbose_name="Сотрудник",
    )
    date = models.DateField("Дата")
    display_name = models.CharField("Имя из анализа", max_length=255, blank=True)
    arrival_time = models.CharField(
        "Время прихода",
        max_length=32,
        blank=True,
        null=True,
    )
    departure_time = models.CharField(
        "Время ухода",
        max_length=32,
        blank=True,
        null=True,
    )
    work_hours = models.FloatField("Отработано часов", null=True, blank=True)
    expected_hours = models.FloatField("Ожидаемо часов", null=True, blank=True)
    is_workday = models.BooleanField("Рабочий день", default=True)
    is_late = models.BooleanField("Опоздание", default=False)
    late_minutes = models.IntegerField("Минут опоздания", null=True, blank=True)
    is_early_leave = models.BooleanField("Ранний уход", default=False)
    early_leave_minutes = models.IntegerField(
        "Минут раннего ухода",
        null=True,
        blank=True,
    )
    is_underwork = models.BooleanField("Недоработка", default=False)
    underwork_hours = models.FloatField("Часов недоработки", null=True, blank=True)
    is_overtime = models.BooleanField("Переработка", default=False)
    overtime_hours = models.FloatField("Часов переработки", null=True, blank=True)
    is_absent = models.BooleanField("Отсутствие", default=False)
    statuses = models.JSONField("Статусы", default=list, blank=True)
    employee_issues = models.JSONField("Проблемы сотрудника", default=list, blank=True)
    technical_issues = models.JSONField(
        "Технические проблемы", default=list, blank=True
    )
    personnel_status = models.CharField(
        "Кадровое состояние",
        max_length=64,
        default="normal",
        blank=True,
    )
    personnel_status_label = models.CharField(
        "Кадровое состояние для отображения",
        max_length=128,
        blank=True,
    )
    personnel_action = models.ForeignKey(
        "employees.EmployeeAction",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="attendance_records",
        verbose_name="Кадровое событие",
    )
    effective_is_workday = models.BooleanField(
        "Рабочий день с учетом кадрового состояния",
        default=True,
    )
    is_manually_edited = models.BooleanField(
        "Изменено вручную",
        default=False,
    )
    manual_edit_payload = models.JSONField(
        "Ручная корректировка",
        default=dict,
        blank=True,
    )
    manual_edited_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="manual_attendance_edits",
        verbose_name="Изменил вручную",
    )
    manual_edited_at = models.DateTimeField(
        "Время ручного изменения",
        null=True,
        blank=True,
    )
    raw_data = models.JSONField("Исходная запись анализа", default=dict, blank=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        ordering = ["-date", "-id"]
        verbose_name = "Запись посещаемости"
        verbose_name_plural = "Записи посещаемости"
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "date"],
                name="attendance_record_employee_date_unique",
            ),
        ]
        indexes = [
            models.Index(fields=["employee", "date"]),
            models.Index(fields=["analysis_run"]),
            models.Index(fields=["personnel_status"]),
            models.Index(
                fields=["is_manually_edited"],
                name="attendance__is_manu_07f532_idx",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.employee_id}: {self.date}"
