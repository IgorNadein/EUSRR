# backend/requests_app/models.py
import logging

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import FileExtensionValidator
from django.db import models
from django.db.models import F, Q
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from .constants import (
    MAX_ATTACHMENT_SIZE,
    SAFE_EXTENSIONS,
    SAFE_MIME_TYPES,
)
from .enums import FINAL_STATUS, RequestStatus, RequestType

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
    """Заявление сотрудника: тип, даты, статус, согласование и вложение."""

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

    # Устаревшее поле, сохранено для обратной совместимости
    department = models.ForeignKey(
        "employees.Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        verbose_name=_("Основной отдел (устар.)"),
        help_text=_("Устаревшее поле, используйте departments"),
    )

    # Новые поля для множественных получателей
    departments = models.ManyToManyField(
        "employees.Department",
        verbose_name=_("Отделы-получатели"),
        blank=True,
        related_name="received_requests",
        help_text=_("Заявка будет видна всем уполномоченным сотрудникам этих отделов")
    )

    recipients = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Получатели"),
        blank=True,
        related_name="received_requests",
        help_text=_("Сотрудники, которым адресована заявка")
    )

    cc_users = models.ManyToManyField(
        settings.AUTH_USER_MODEL,
        verbose_name=_("Копия (CC)"),
        blank=True,
        related_name="requests_cc",
        help_text=_("Сотрудники в копии (уведомления без обязанности рассмотрения)")
    )

    sent_to_all_department = models.BooleanField(
        _("Всем сотрудникам отделов"),
        default=False,
        help_text=_("Если включено, заявка видна всем в выбранных отделах")
    )

    type = models.CharField(
        _("Тип заявления"), choices=RequestType.choices, max_length=32
    )
    title = models.CharField(_("Тема"), max_length=200, blank=True)
    date_from = models.DateField(_("Дата начала"), null=True, blank=True)
    date_to = models.DateField(_("Дата окончания"), null=True, blank=True)
    comment = models.TextField(_("Комментарий"), blank=True)

    status = models.CharField(_("Статус"),
                              choices=RequestStatus.choices,
                              max_length=16,
                              default=RequestStatus.PENDING)

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
            ("can_view_all_requests", "Можно просмотреть все заявления"),
            ("can_process_requests", "Может одобрять/отклонять заявления"),
        ]
        verbose_name = _("Заявление")
        verbose_name_plural = _("Заявления")
        ordering = ["-created_at"]
        # NOTE: проверь через EXPLAIN, не избыточны ли некоторые индексы для твоих
        # кейсов
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
                condition=Q(
                    date_to__isnull=True) | Q(
                    date_from__isnull=True) | Q(
                    date_from__lte=F("date_to")),
            ),
            models.CheckConstraint(
                name="request_approver_required_on_decision",
                condition=Q(
                    status__in=[
                        RequestStatus.APPROVED,
                        RequestStatus.REJECTED],
                    approver__isnull=False) | Q(
                    status__in=[
                        RequestStatus.DRAFT,
                        RequestStatus.PENDING,
                        RequestStatus.CANCELLED],
                    approver__isnull=True),
            ),
        ]

    def clean(self):
        if self.type in {RequestType.VACATION, RequestType.SICK_LEAVE} and not (
            self.date_from and self.date_to
        ):

            raise ValidationError(
                _("Для выбранного типа укажите даты начала и окончания.")
            )
        if self.type in {RequestType.TRANSFER,
                         RequestType.DISMISSAL} and not self.date_from:
            raise ValidationError(_("Для перевода/увольнения укажите дату начала."))

        if self.approver_id and self.approver_id == self.employee_id:
            raise ValidationError(_("Согласующий не может совпадать с автором заявки."))

    @property
    def display_title(self) -> str:
        """Заголовок для списков: берём title или генерим на лету."""
        return self.title or f"{self.get_type_display()} — {self.employee}"

    @property
    def is_final(self):
        return self.status in FINAL_STATUS

    @property
    def all_recipients(self):
        """Все получатели: основные + CC"""
        User = settings.AUTH_USER_MODEL
        from django.apps import apps
        UserModel = apps.get_model(User)

        recipient_ids = set(self.recipients.values_list('id', flat=True))
        cc_ids = set(self.cc_users.values_list('id', flat=True))
        return UserModel.objects.filter(id__in=recipient_ids | cc_ids)

    @property
    def primary_recipients(self):
        """Только основные получатели (без CC)"""
        return self.recipients.all()

    def is_recipient(self, user):
        """Проверка, является ли пользователь получателем"""
        # Прямой получатель или в копии
        if self.recipients.filter(id=user.id).exists():
            return True
        if self.cc_users.filter(id=user.id).exists():
            return True

        # Если sent_to_all_department и пользователь в одном из отделов
        if self.sent_to_all_department:
            return self.departments.filter(
                employeedepartment__employee=user,
                employeedepartment__is_active=True
            ).exists()

        return False

    def add_recipient(self, user, is_cc=False):
        """Добавить получателя"""
        if is_cc:
            self.cc_users.add(user)
        else:
            self.recipients.add(user)

    def remove_recipient(self, user):
        """Удалить получателя из обеих групп"""
        self.recipients.remove(user)
        self.cc_users.remove(user)

    def approve(self, by_user):
        self.status = RequestStatus.APPROVED
        self.approver = by_user
        self.decided_at = timezone.now()
        self.save(update_fields=["status", "approver", "decided_at", "updated_at"])

    def reject(self, by_user):
        self.status = RequestStatus.REJECTED
        self.approver = by_user
        self.decided_at = timezone.now()
        self.save(update_fields=["status", "approver", "decided_at", "updated_at"])

    def cancel(self):
        self.status = RequestStatus.CANCELLED
        if self.approver_id is not None:
            self.approver = None
        self.decided_at = timezone.now()
        self.save(update_fields=["status", "approver", "decided_at", "updated_at"])

    def save(self, *args, **kwargs) -> None:
        """Синхронизация decided_at/approver с текущим статусом.

        Raises:
            ValueError: Если нарушена согласованность полей (редко).
        """
        if self.status in FINAL_STATUS and not self.decided_at:
            self.decided_at = timezone.now()
        if self.status in {
                RequestStatus.DRAFT,
                RequestStatus.PENDING,
                RequestStatus.CANCELLED} and self.approver_id:
            self.approver = None
        super().save(*args, **kwargs)

    def __str__(self):
        return (
            f"{self.get_type_display()} — {self.employee} ({self.get_status_display()})"
        )
