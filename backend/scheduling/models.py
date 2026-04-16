from django.contrib.contenttypes.fields import GenericForeignKey
from django.contrib.contenttypes.models import ContentType
from django.db import models
from django.db.models import Q


class CalendarBinding(models.Model):
    class BindingType(models.TextChoices):
        DEFAULT = "default", "Обычный"
        DEPARTMENT = "department", "Отдел"

    calendar = models.OneToOneField(
        "schedule.Calendar",
        on_delete=models.CASCADE,
        related_name="binding",
        verbose_name="Календарь",
    )
    type = models.CharField(
        max_length=32,
        choices=BindingType.choices,
        default=BindingType.DEFAULT,
        db_index=True,
        verbose_name="Тип привязки",
    )
    context_content_type = models.ForeignKey(
        ContentType,
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        verbose_name="Тип контекста",
    )
    context_object_id = models.PositiveIntegerField(
        null=True,
        blank=True,
        verbose_name="ID объекта контекста",
    )
    context_object = GenericForeignKey(
        "context_content_type",
        "context_object_id",
    )
    flags = models.JSONField(default=dict, blank=True, verbose_name="Флаги")
    extra_data = models.JSONField(
        default=dict, blank=True, verbose_name="Доп. данные"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Привязка календаря"
        verbose_name_plural = "Привязки календарей"
        constraints = [
            models.UniqueConstraint(
                fields=["type", "context_content_type", "context_object_id"],
                condition=Q(
                    type="department",
                    context_content_type__isnull=False,
                    context_object_id__isnull=False,
                ),
                name="uniq_department_calendar_binding",
            ),
        ]
        indexes = [
            models.Index(fields=["type"], name="calendar_binding_type_idx"),
            models.Index(
                fields=["context_content_type", "context_object_id"],
                name="calendar_binding_context_idx",
            ),
        ]

    def __str__(self) -> str:
        target = self.context_object or self.calendar
        return f"{self.type}: {target}"
