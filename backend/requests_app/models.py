# backend/requests_app/models.py
import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .constants import MAX_ATTACHMENT_SIZE, SAFE_EXTENSIONS, SAFE_MIME_TYPES

logger = logging.getLogger(__name__)


def attachment_file_size(value):
    """Ограничение размера вложения (10 МБ)."""
    if value and getattr(value, "size", 0) > MAX_ATTACHMENT_SIZE:
        mb = MAX_ATTACHMENT_SIZE // (1024 * 1024)
        raise ValidationError(
            _("Размер файла не должен превышать %(mb)s МБ."), params={"mb": mb}
        )


def attachment_mime_validator(value):
    """
    Доп. проверка MIME-типа. Если python-magic отсутствует — пишем WARNING и
    пропускаем проверку (понижает безопасность).
    """
    if not value:
        return
    try:
        import magic  # type: ignore
    except ImportError:
        logger.warning(
            "python-magic не установлен, проверка MIME-типов вложений отключена. "
            "Это может снизить безопасность обработки файлов."
        )
        return

    # читаем «шапку» файла
    pos = value.file.tell()
    head = value.file.read(2048)
    value.file.seek(pos)

    if not head:
        raise ValidationError(_("Недопустимый файл: пустое содержимое."))

    mime = magic.Magic(mime=True).from_buffer(head)
    if not mime or mime not in SAFE_MIME_TYPES:
        raise ValidationError(
            _("Недопустимый тип файла: %(mime)s."), params={"mime": mime or "unknown"}
        )


class Request(models.Model):

    TYPE_VACATION = "vacation"
    TYPE_SICK = "sick_leave"
    TYPE_TRANSFER = "transfer"
    TYPE_DISMISSAL = "dismissal"
    TYPE_OTHER = "other"

    TYPE_CHOICES = [
        (TYPE_VACATION, _("Отпуск")),
        (TYPE_SICK, _("Больничный")),
        (TYPE_TRANSFER, _("Перевод")),
        (TYPE_DISMISSAL, _("Увольнение")),
        (TYPE_OTHER, _("Другое")),
    ]

    STATUS_DRAFT = "draft"
    STATUS_PENDING = "pending"
    STATUS_APPROVED = "approved"
    STATUS_REJECTED = "rejected"
    STATUS_CANCELLED = "cancelled"

    STATUS_CHOICES = [
        (STATUS_DRAFT, _("Черновик")),
        (STATUS_PENDING, _("На рассмотрении")),
        (STATUS_APPROVED, _("Одобрено")),
        (STATUS_REJECTED, _("Отклонено")),
        (STATUS_CANCELLED, _("Отменено")),
    ]

    FINAL_STATUS_SET = {STATUS_APPROVED, STATUS_REJECTED, STATUS_CANCELLED}

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="requests",
        verbose_name=_("Автор"),
    )
    approver = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        related_name="approved_requests",
        null=True,
        blank=True,
        verbose_name=_("Согласующий"),
    )
    department = models.ForeignKey(
        "employees.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Отдел"),
    )

    type = models.CharField(_("Тип заявления"), choices=TYPE_CHOICES, max_length=32)
    title = models.CharField(_("Тема"), max_length=200, blank=True)
    date_from = models.DateField(_("Дата начала"), null=True, blank=True)
    date_to = models.DateField(_("Дата окончания"), null=True, blank=True)
    comment = models.TextField(_("Комментарий"), blank=True)

    status = models.CharField(
        _("Статус"),
        choices=STATUS_CHOICES,
        max_length=16,
        default=STATUS_PENDING,
    )

    attachment = models.FileField(
        _("Вложение"),
        upload_to="requests/attachments/%Y/%m/",
        blank=True,
        null=True,
        validators=[
            FileExtensionValidator(allowed_extensions=SAFE_EXTENSIONS),
            attachment_file_size,
            attachment_mime_validator,
        ],
    )

    created_at = models.DateTimeField(_("Создано"), auto_now_add=True)
    updated_at = models.DateTimeField(_("Обновлено"), auto_now=True)
    decided_at = models.DateTimeField(_("Решение принято"), null=True, blank=True)

    class Meta:
        permissions = [
            ("can_view_all_requests", "Can view all requests"),
            ("can_process_requests", "Can approve/reject requests"),
        ]
        verbose_name = _("Заявление")
        verbose_name_plural = _("Заявления")
        ordering = ["-created_at"]
        # NOTE: проверь через EXPLAIN, не избыточны ли некоторые индексы для твоих кейсов
        indexes = [
            models.Index(fields=["status", "created_at"]),
            models.Index(fields=["type", "created_at"]),
            models.Index(fields=["employee", "created_at"]),
            models.Index(
                fields=["decided_at"],
                name="req_decided_idx",
                condition=Q(decided_at__isnull=False),
            ),
        ]
        constraints = [
            models.CheckConstraint(
                name="request_date_range_valid",
                condition=Q(date_to__isnull=True)
                | Q(date_from__isnull=True)
                | Q(date_from__lte=F("date_to")),
            ),
            models.CheckConstraint(
                name="request_approver_required_on_decision",
                condition=Q(status__in=["approved", "rejected"], approver__isnull=False)
                | Q(
                    status__in=["draft", "pending", "cancelled"], approver__isnull=True
                ),
            ),
        ]

    def clean(self):
        if self.type in {self.TYPE_VACATION, self.TYPE_SICK} and not (
            self.date_from and self.date_to
        ):
            raise ValidationError(
                _("Для выбранного типа укажите даты начала и окончания.")
            )
        if (
            self.type in {self.TYPE_TRANSFER, self.TYPE_DISMISSAL}
            and not self.date_from
        ):
            raise ValidationError(_("Для перевода/увольнения укажите дату начала."))

        if self.approver_id and self.approver_id == self.employee_id:
            raise ValidationError(_("Согласующий не может совпадать с автором заявки."))

    @property
    def display_title(self) -> str:
        """Заголовок для списков: берём title или генерим на лету."""
        return self.title or f"{self.get_type_display()} — {self.employee}"

    @property
    def is_final(self):
        return self.status in self.FINAL_STATUS_SET

    def approve(self, by_user):
        self.status = self.STATUS_APPROVED
        self.approver = by_user
        self.decided_at = timezone.now()
        self.save(update_fields=["status", "approver", "decided_at", "updated_at"])

    def reject(self, by_user):
        self.status = self.STATUS_REJECTED
        self.approver = by_user
        self.decided_at = timezone.now()
        self.save(update_fields=["status", "approver", "decided_at", "updated_at"])

    def cancel(self):
        self.status = self.STATUS_CANCELLED
        if self.approver_id is not None:
            self.approver = None
        self.decided_at = timezone.now()
        self.save(update_fields=["status", "approver", "decided_at", "updated_at"])

    def save(self, *args, **kwargs):
        """
        Страховка на случай изменения статуса напрямую:
        - финальные статусы → ставим decided_at, если пусто;
        - draft/pending/cancelled → чистим approver (в синхроне с БД-constraint).
        """
        if self.status in self.FINAL_STATUS_SET and not self.decided_at:
            self.decided_at = timezone.now()
        if (
            self.status
            in {self.STATUS_DRAFT, self.STATUS_PENDING, self.STATUS_CANCELLED}
            and self.approver_id
        ):
            self.approver = None
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.get_type_display()} — {self.employee} ({self.get_status_display()})"
        )


class RequestComment(models.Model):
    request = models.ForeignKey(
        Request,
        on_delete=models.CASCADE,
        related_name="comments",
        verbose_name=_("Заявка"),
    )
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        verbose_name=_("Автор"),
    )
    text = models.TextField(_("Комментарий"))
    created_at = models.DateTimeField(_("Создано"), auto_now_add=True)

    class Meta:
        verbose_name = _("Комментарий к заявке")
        verbose_name_plural = _("Комментарии к заявкам")
        ordering = ["created_at"]
        indexes = [models.Index(fields=["created_at"])]

    def __str__(self):
        return f"Комментарий {self.author} к заявке #{self.request_id}"
