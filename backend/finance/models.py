"""Persistence models for the EUSRR payroll integration.

Calculation rules live in the project-independent :mod:`payroll_core` package.
These models resolve EUSRR identities, approval state and immutable snapshots.
"""

from __future__ import annotations

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, RegexValidator
from django.db import models, transaction
from django.db.models import F, Q

from .enums import (
    ApprovalStatus,
    InputSource,
    PayrollComponentKind,
    PayrollPeriodStatus,
    PayrollRunStatus,
)

currency_validator = RegexValidator(
    regex=r"^[A-Z]{3}$",
    message="Валюта должна быть трёхбуквенным кодом в верхнем регистре.",
)
component_code_validator = RegexValidator(
    regex=r"^[A-Z][A-Z0-9_.-]{0,63}$",
    message="Код должен начинаться с A-Z и содержать только A-Z, 0-9, _.-",
)

DEFAULT_DAILY_TARGET_POINTS = Decimal("5")


class PayrollPeriod(models.Model):
    """A calculation and publication period controlled by one active run."""

    code = models.CharField("Код", max_length=32, unique=True)
    name = models.CharField("Название", max_length=120, blank=True)
    date_from = models.DateField("Начало периода")
    date_to = models.DateField("Конец периода")
    pay_date = models.DateField("Дата выплаты", null=True, blank=True)
    currency = models.CharField(
        "Валюта",
        max_length=3,
        default="RUB",
        validators=[currency_validator],
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=PayrollPeriodStatus.choices,
        default=PayrollPeriodStatus.OPEN,
    )
    current_run = models.ForeignKey(
        "PayrollRun",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="active_for_periods",
        verbose_name="Текущая ревизия расчёта",
    )
    lock_version = models.PositiveIntegerField("Версия блокировки", default=0)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_payroll_periods",
        verbose_name="Создал",
    )
    created_at = models.DateTimeField("Создан", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлён", auto_now=True)

    class Meta:
        verbose_name = "Расчётный период"
        verbose_name_plural = "Расчётные периоды"
        ordering = ["-date_from", "-id"]
        indexes = [
            models.Index(
                fields=["status", "date_from"],
                name="pay_period_status_date_idx",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(date_from__lte=F("date_to")),
                name="pay_period_dates_valid",
            ),
            models.UniqueConstraint(
                fields=["date_from", "date_to"],
                name="pay_period_dates_unique",
            ),
        ]
        permissions = [
            ("manage_payroll_inputs", "Может управлять данными для расчёта"),
            ("approve_payroll_inputs", "Может утверждать данные для расчёта"),
            ("calculate_payroll", "Может запускать расчёт зарплаты"),
            ("approve_payroll", "Может утверждать расчёт зарплаты"),
            (
                "override_payroll_approval",
                "Может самоутверждать данные и расчёты зарплаты",
            ),
            ("publish_payroll", "Может публиковать расчётные листки"),
            ("view_all_payroll", "Может просматривать все расчёты"),
            ("audit_payroll", "Может просматривать аудит расчётов"),
        ]

    def __str__(self):
        return self.name or self.code

    def _validate_immutable_fields(self, original=None):
        if self.pk:
            original = original or PayrollPeriod.objects.filter(pk=self.pk).first()
            if original and original.runs.exists():
                immutable_values = (
                    self.code,
                    self.name,
                    self.date_from,
                    self.date_to,
                    self.pay_date,
                    self.currency,
                )
                original_values = (
                    original.code,
                    original.name,
                    original.date_from,
                    original.date_to,
                    original.pay_date,
                    original.currency,
                )
                if immutable_values != original_values:
                    raise ValidationError(
                        "Показываемые сотруднику реквизиты периода нельзя "
                        "менять после расчёта."
                    )

    def clean(self):
        super().clean()
        self._validate_immutable_fields()
        if self.date_from and self.date_to and self.date_from > self.date_to:
            raise ValidationError(
                {"date_to": "Конец периода не может быть раньше начала."}
            )
        if self.date_from and self.date_to:
            overlaps = PayrollPeriod.objects.filter(
                date_from__lte=self.date_to,
                date_to__gte=self.date_from,
            )
            if self.pk:
                overlaps = overlaps.exclude(pk=self.pk)
            if overlaps.exists():
                raise ValidationError("Расчётные периоды не должны пересекаться.")

    @transaction.atomic
    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if self.pk and not self._state.adding:
            original = PayrollPeriod.objects.select_for_update().get(pk=self.pk)
            self._validate_immutable_fields(original)
            if update_fields is None:
                # Full-form saves may carry stale workflow fields. Those fields
                # are changed only by services with explicit update_fields.
                self.status = original.status
                self.current_run_id = original.current_run_id
                self.lock_version = original.lock_version
                self.created_by_id = original.created_by_id
                self.created_at = original.created_at
        return super().save(*args, **kwargs)


class DraftVersionedModel(models.Model):
    """Optimistic version for maker-checker records edited as drafts."""

    lock_version = models.PositiveIntegerField("Версия черновика", default=0)

    class Meta:
        abstract = True

    @transaction.atomic
    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if self.pk and not self._state.adding and update_fields is None:
            current = self.__class__.objects.select_for_update().get(pk=self.pk)
            if (
                current.status != ApprovalStatus.DRAFT
                or self.status != ApprovalStatus.DRAFT
            ):
                raise ValidationError(
                    "Изменять можно только актуальную версию черновика."
                )
            expected_lock_version = getattr(
                self,
                "_expected_lock_version",
                self.lock_version,
            )
            if current.lock_version != expected_lock_version:
                raise ValidationError(
                    "Черновик уже изменён другой операцией; обновите данные."
                )
            self.lock_version = current.lock_version + 1
        result = super().save(*args, **kwargs)
        if hasattr(self, "_expected_lock_version"):
            del self._expected_lock_version
        return result


class EmployeePayRate(DraftVersionedModel):
    """Effective-dated, approved rate event for an employee."""

    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="pay_rates",
        verbose_name="Сотрудник",
    )
    rate_code = models.CharField(
        "Код ставки",
        max_length=64,
        default="BASE",
        validators=[component_code_validator],
    )
    amount = models.DecimalField(
        "Сумма ставки",
        max_digits=19,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    point_rate = models.DecimalField(
        "Цена балла сверх нормы",
        max_digits=19,
        decimal_places=4,
        default=Decimal("0"),
        validators=[MinValueValidator(Decimal("0"))],
    )
    currency = models.CharField(
        "Валюта",
        max_length=3,
        default="RUB",
        validators=[currency_validator],
    )
    effective_from = models.DateField("Действует с")
    revision = models.PositiveIntegerField("Ревизия", default=1)
    status = models.CharField(
        "Статус",
        max_length=16,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.DRAFT,
    )
    replaces = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="replaced_by",
        verbose_name="Заменяет ставку",
    )
    reason = models.TextField("Основание", blank=True)
    source = models.CharField(
        "Источник",
        max_length=16,
        choices=InputSource.choices,
        default=InputSource.MANUAL,
    )
    source_ref = models.CharField(
        "Идентификатор в источнике",
        max_length=255,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_pay_rates",
        verbose_name="Создал",
    )
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approved_pay_rates",
        verbose_name="Утвердил",
    )
    approved_at = models.DateTimeField("Утверждена", null=True, blank=True)
    self_approval_overridden = models.BooleanField(
        "Самоутверждение по особому праву",
        default=False,
        editable=False,
    )
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="voided_pay_rates",
        verbose_name="Аннулировал",
    )
    voided_at = models.DateTimeField("Аннулирована", null=True, blank=True)
    void_reason = models.TextField("Причина аннулирования", blank=True)

    class Meta:
        verbose_name = "Ставка сотрудника"
        verbose_name_plural = "Ставки сотрудников"
        ordering = ["employee_id", "-effective_from", "-revision"]
        indexes = [
            models.Index(
                fields=["employee", "status", "effective_from"],
                name="pay_rate_employee_date_idx",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="pay_rate_amount_positive",
            ),
            models.CheckConstraint(
                condition=Q(point_rate__gte=0),
                name="pay_rate_point_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(approved_by__isnull=True)
                | ~Q(created_by=F("approved_by"))
                | Q(self_approval_overridden=True),
                name="pay_rate_maker_not_approver",
            ),
            models.CheckConstraint(
                condition=Q(self_approval_overridden=False)
                | Q(
                    approved_by__isnull=False,
                    created_by=F("approved_by"),
                ),
                name="pay_rate_self_override_valid",
            ),
            models.CheckConstraint(
                condition=~Q(status=ApprovalStatus.APPROVED)
                | Q(approved_by__isnull=False, approved_at__isnull=False),
                name="pay_rate_approval_complete",
            ),
            models.UniqueConstraint(
                fields=["employee", "rate_code", "effective_from", "revision"],
                name="pay_rate_revision_unique",
            ),
            models.UniqueConstraint(
                fields=["employee", "rate_code", "effective_from"],
                condition=Q(status=ApprovalStatus.APPROVED),
                name="pay_rate_one_approved_event",
            ),
            models.UniqueConstraint(
                fields=["source", "source_ref"],
                condition=~Q(source_ref=""),
                name="pay_rate_source_ref_unique",
            ),
        ]

    def __str__(self):
        return f"{self.employee} — {self.amount} {self.currency}"

    def clean(self):
        super().clean()
        if self.replaces_id:
            if self.pk and self.replaces_id == self.pk:
                raise ValidationError({"replaces": "Ставка не может заменять себя."})
            if self.replaces.employee_id != self.employee_id:
                raise ValidationError(
                    {"replaces": "Заменяемая ставка относится к другому сотруднику."}
                )
            if self.replaces.rate_code != self.rate_code:
                raise ValidationError(
                    {"replaces": "Код заменяемой ставки должен совпадать."}
                )
            if self.replaces.effective_from != self.effective_from:
                raise ValidationError(
                    {"replaces": "Дата начала заменяемой ставки должна совпадать."}
                )
            if self.revision != self.replaces.revision + 1:
                raise ValidationError(
                    {"revision": "Ревизия должна следовать за заменяемой ставкой."}
                )
        if self.status == ApprovalStatus.APPROVED:
            if not self.approved_by_id or not self.approved_at:
                raise ValidationError(
                    "Утверждённая ставка должна содержать автора и время решения."
                )


class PayrollWorkSettings(models.Model):
    """Global settings for employee-entered daily work metrics."""

    singleton = models.BooleanField(default=True, unique=True, editable=False)
    daily_target_points = models.DecimalField(
        "Дневная норма баллов",
        max_digits=19,
        decimal_places=4,
        default=DEFAULT_DAILY_TARGET_POINTS,
        validators=[MinValueValidator(Decimal("0.0001"))],
        help_text="Единая дневная норма для всех сотрудников.",
    )
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Настройки выработки"
        verbose_name_plural = "Настройки выработки"

    def save(self, *args, **kwargs):
        self.singleton = True
        super().save(*args, **kwargs)

    def __str__(self):
        return f"Дневная норма: {self.daily_target_points}"

    @classmethod
    def get_daily_target_points(cls):
        value = (
            cls.objects.filter(singleton=True)
            .values_list("daily_target_points", flat=True)
            .first()
        )
        return value if value is not None else DEFAULT_DAILY_TARGET_POINTS


class PayrollDailyWorkEntry(models.Model):
    """Employee-entered daily work metrics aggregated into a payroll period."""

    period = models.ForeignKey(
        PayrollPeriod,
        on_delete=models.CASCADE,
        related_name="daily_work_entries",
        verbose_name="Период",
    )
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payroll_daily_work_entries",
        verbose_name="Сотрудник",
    )
    work_date = models.DateField("Дата выработки")
    target_points = models.DecimalField(
        "Норма баллов за день",
        max_digits=19,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    actual_points = models.DecimalField(
        "Фактические баллы за день",
        max_digits=19,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0"))],
    )
    note = models.TextField("Комментарий", blank=True)
    lock_version = models.PositiveIntegerField("Версия записи", default=0)
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)

    class Meta:
        verbose_name = "Ежедневная выработка"
        verbose_name_plural = "Ежедневная выработка"
        ordering = ["-work_date", "-id"]
        indexes = [
            models.Index(
                fields=["period", "employee", "work_date"],
                name="pay_daily_period_employee_idx",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(target_points__gt=0),
                name="pay_daily_target_positive",
            ),
            models.CheckConstraint(
                condition=Q(actual_points__gte=0),
                name="pay_daily_actual_nonnegative",
            ),
            models.UniqueConstraint(
                fields=["period", "employee", "work_date"],
                name="pay_daily_employee_date_unique",
            ),
        ]

    def __str__(self):
        return f"{self.work_date}: {self.employee} ({self.actual_points})"

    def clean(self):
        super().clean()
        if (
            self.period_id
            and self.work_date
            and not self.period.date_from <= self.work_date <= self.period.date_to
        ):
            raise ValidationError(
                {"work_date": "Дата выработки должна входить в расчётный период."}
            )


class PayrollWorkRecord(DraftVersionedModel):
    """Approved monthly work metrics and optional Excel control totals."""

    period = models.ForeignKey(
        PayrollPeriod,
        on_delete=models.CASCADE,
        related_name="work_records",
        verbose_name="Период",
    )
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payroll_work_records",
        verbose_name="Сотрудник",
    )
    target_points = models.DecimalField(
        "Норма баллов",
        max_digits=19,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0.0001"))],
    )
    target_points_overridden = models.BooleanField(
        "Норма указана вручную",
        default=True,
        editable=False,
    )
    actual_points = models.DecimalField(
        "Фактические баллы",
        max_digits=19,
        decimal_places=4,
        validators=[MinValueValidator(Decimal("0"))],
    )
    expected_point_amount = models.DecimalField(
        "Контроль: выработка по баллам",
        max_digits=19,
        decimal_places=2,
        null=True,
        blank=True,
    )
    expected_gross = models.DecimalField(
        "Контроль: итого начислено",
        max_digits=19,
        decimal_places=2,
        null=True,
        blank=True,
    )
    expected_recalculated_gross = models.DecimalField(
        "Контроль: перерасчёт",
        max_digits=19,
        decimal_places=2,
        null=True,
        blank=True,
    )
    expected_payable = models.DecimalField(
        "Контроль: к выплате",
        max_digits=19,
        decimal_places=2,
        null=True,
        blank=True,
    )
    revision = models.PositiveIntegerField("Ревизия", default=1)
    status = models.CharField(
        "Статус",
        max_length=16,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.DRAFT,
    )
    replaces = models.OneToOneField(
        "self",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="replaced_by",
        verbose_name="Заменяет запись",
    )
    reason = models.TextField("Основание изменения", blank=True)
    source = models.CharField(
        "Источник",
        max_length=16,
        choices=InputSource.choices,
        default=InputSource.MANUAL,
    )
    source_ref = models.CharField(
        "Идентификатор в источнике",
        max_length=255,
        blank=True,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_payroll_work_records",
        verbose_name="Создал",
    )
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлена", auto_now=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approved_payroll_work_records",
        verbose_name="Утвердил",
    )
    approved_at = models.DateTimeField("Утверждена", null=True, blank=True)
    self_approval_overridden = models.BooleanField(
        "Самоутверждение по особому праву",
        default=False,
        editable=False,
    )
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="voided_payroll_work_records",
        verbose_name="Аннулировал",
    )
    voided_at = models.DateTimeField("Аннулирована", null=True, blank=True)

    class Meta:
        verbose_name = "Выработка за период"
        verbose_name_plural = "Выработка за периоды"
        ordering = ["period_id", "employee_id", "-revision"]
        constraints = [
            models.CheckConstraint(
                condition=Q(target_points__gt=0),
                name="pay_work_target_positive",
            ),
            models.CheckConstraint(
                condition=Q(actual_points__gte=0),
                name="pay_work_actual_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(approved_by__isnull=True)
                | ~Q(created_by=F("approved_by"))
                | Q(self_approval_overridden=True),
                name="pay_work_maker_not_approver",
            ),
            models.CheckConstraint(
                condition=Q(self_approval_overridden=False)
                | Q(
                    approved_by__isnull=False,
                    created_by=F("approved_by"),
                ),
                name="pay_work_self_override_valid",
            ),
            models.CheckConstraint(
                condition=~Q(status=ApprovalStatus.APPROVED)
                | Q(approved_by__isnull=False, approved_at__isnull=False),
                name="pay_work_approval_complete",
            ),
            models.UniqueConstraint(
                fields=["period", "employee", "revision"],
                name="pay_work_revision_unique",
            ),
            models.UniqueConstraint(
                fields=["period", "employee"],
                condition=Q(status=ApprovalStatus.APPROVED),
                name="pay_work_one_approved",
            ),
            models.UniqueConstraint(
                fields=["source", "source_ref"],
                condition=~Q(source_ref=""),
                name="pay_work_source_ref_unique",
            ),
        ]

    def __str__(self):
        return f"{self.period}: {self.employee} ({self.actual_points})"

    def clean(self):
        super().clean()
        if not self.replaces_id:
            return
        if self.pk and self.replaces_id == self.pk:
            raise ValidationError({"replaces": "Запись не может заменять себя."})
        if self.replaces.employee_id != self.employee_id:
            raise ValidationError(
                {"replaces": "Заменяемая запись относится к другому сотруднику."}
            )
        if self.replaces.period_id != self.period_id:
            raise ValidationError(
                {"replaces": "Заменяемая запись относится к другому периоду."}
            )
        if self.revision != self.replaces.revision + 1:
            raise ValidationError(
                {"revision": "Ревизия должна следовать за заменяемой записью."}
            )
        if not self.reason.strip():
            raise ValidationError(
                {"reason": "Для новой ревизии укажите основание изменения."}
            )


class PayrollComponent(models.Model):
    """Reusable catalog entry for an explicit payroll input line."""

    code = models.CharField(
        "Код",
        max_length=64,
        unique=True,
        validators=[component_code_validator],
    )
    name = models.CharField("Название", max_length=160)
    kind = models.CharField(
        "Тип",
        max_length=24,
        choices=PayrollComponentKind.choices,
    )
    requires_reason = models.BooleanField("Требует основание", default=False)
    is_active = models.BooleanField("Активен", default=True)
    display_order = models.PositiveIntegerField("Порядок", default=100)

    class Meta:
        verbose_name = "Компонент зарплаты"
        verbose_name_plural = "Компоненты зарплаты"
        ordering = ["display_order", "code"]

    def __str__(self):
        return f"{self.code} — {self.name}"

    semantic_fields = (
        "code",
        "name",
        "kind",
        "requires_reason",
        "display_order",
    )

    def _validate_semantics_immutable(self, original=None):
        if not self.pk:
            return
        original = original or PayrollComponent.objects.get(pk=self.pk)
        if any(
            getattr(self, field_name) != getattr(original, field_name)
            for field_name in self.semantic_fields
        ):
            raise ValidationError(
                "Семантику компонента нельзя менять; создайте новый код."
            )

    def clean(self):
        super().clean()
        self._validate_semantics_immutable()

    @transaction.atomic
    def save(self, *args, **kwargs):
        if self.pk and not self._state.adding:
            original = PayrollComponent.objects.select_for_update().get(pk=self.pk)
            self._validate_semantics_immutable(original)
        return super().save(*args, **kwargs)


class PayrollInputLine(DraftVersionedModel):
    """Append-only bonus, correction, deduction or recorded payment input."""

    period = models.ForeignKey(
        PayrollPeriod,
        on_delete=models.CASCADE,
        related_name="input_lines",
        verbose_name="Период выплаты",
    )
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payroll_input_lines",
        verbose_name="Сотрудник",
    )
    component = models.ForeignKey(
        PayrollComponent,
        on_delete=models.PROTECT,
        related_name="input_lines",
        verbose_name="Компонент",
    )
    amount = models.DecimalField(
        "Сумма",
        max_digits=19,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    relates_to_period = models.ForeignKey(
        PayrollPeriod,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="retro_input_lines",
        verbose_name="Относится к периоду",
        help_text="Заполняется для перерасчёта прошлого периода.",
    )
    reason = models.TextField("Основание", blank=True)
    status = models.CharField(
        "Статус",
        max_length=16,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.DRAFT,
    )
    reversal_of = models.OneToOneField(
        "self",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="reversed_by",
        verbose_name="Сторнирует строку",
    )
    source = models.CharField(
        "Источник",
        max_length=16,
        choices=InputSource.choices,
        default=InputSource.MANUAL,
    )
    source_ref = models.CharField(
        "Идентификатор в источнике",
        max_length=255,
        blank=True,
    )
    idempotency_key = models.UUIDField(
        "Ключ идемпотентности",
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="created_payroll_input_lines",
        verbose_name="Создал",
    )
    created_at = models.DateTimeField("Создана", auto_now_add=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approved_payroll_input_lines",
        verbose_name="Утвердил",
    )
    approved_at = models.DateTimeField("Утверждена", null=True, blank=True)
    self_approval_overridden = models.BooleanField(
        "Самоутверждение по особому праву",
        default=False,
        editable=False,
    )
    voided_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="voided_payroll_input_lines",
        verbose_name="Аннулировал",
    )
    voided_at = models.DateTimeField("Аннулирована", null=True, blank=True)
    void_reason = models.TextField("Причина аннулирования", blank=True)

    class Meta:
        verbose_name = "Строка начисления/удержания"
        verbose_name_plural = "Строки начислений/удержаний"
        ordering = ["period_id", "employee_id", "component__display_order", "id"]
        indexes = [
            models.Index(
                fields=["period", "employee", "status"],
                name="pay_input_period_employee_idx",
            )
        ]
        constraints = [
            models.CheckConstraint(
                condition=Q(amount__gt=0),
                name="pay_input_amount_positive",
            ),
            models.CheckConstraint(
                condition=Q(approved_by__isnull=True)
                | ~Q(created_by=F("approved_by"))
                | Q(self_approval_overridden=True),
                name="pay_input_maker_not_approver",
            ),
            models.CheckConstraint(
                condition=Q(self_approval_overridden=False)
                | Q(
                    approved_by__isnull=False,
                    created_by=F("approved_by"),
                ),
                name="pay_input_self_override_valid",
            ),
            models.CheckConstraint(
                condition=~Q(status=ApprovalStatus.APPROVED)
                | Q(approved_by__isnull=False, approved_at__isnull=False),
                name="pay_input_approval_complete",
            ),
            models.UniqueConstraint(
                fields=["source", "source_ref"],
                condition=~Q(source_ref=""),
                name="pay_input_source_ref_unique",
            ),
        ]

    def __str__(self):
        return f"{self.employee}: {self.component.code} {self.amount}"

    def clean(self):
        super().clean()
        if self.reversal_of_id:
            raise ValidationError(
                {
                    "reversal_of": (
                        "Связанное сторно ещё не поддерживается. Используйте "
                        "утверждённую корректировку с обязательным основанием."
                    )
                }
            )
        if self.component_id and self.component.requires_reason and not self.reason:
            raise ValidationError({"reason": "Для компонента требуется основание."})
        if self.relates_to_period_id == self.period_id:
            raise ValidationError(
                {"relates_to_period": "Для текущего периода это поле не требуется."}
            )
        if self.relates_to_period_id and not self.reason:
            raise ValidationError(
                {"reason": "Для перерасчёта прошлого периода укажите основание."}
            )


class PayrollRun(models.Model):
    """Immutable calculation revision plus its controlled workflow state."""

    period = models.ForeignKey(
        PayrollPeriod,
        on_delete=models.CASCADE,
        related_name="runs",
        verbose_name="Период",
    )
    revision = models.PositiveIntegerField("Ревизия")
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=PayrollRunStatus.choices,
        default=PayrollRunStatus.CALCULATED,
    )
    supersedes = models.ForeignKey(
        "self",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="superseded_by_runs",
        verbose_name="Пересчитывает ревизию",
    )
    recalculation_reason = models.TextField(
        "Основание перерасчёта",
        blank=True,
    )
    idempotency_key = models.UUIDField(
        "Ключ идемпотентности",
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    ruleset_id = models.CharField("Набор правил", max_length=120)
    ruleset_version = models.CharField("Версия правил", max_length=64)
    ruleset_hash = models.CharField("Хэш правил", max_length=64)
    calculator_version = models.CharField("Версия калькулятора", max_length=64)
    input_hash = models.CharField("Хэш входных данных", max_length=64)
    result_hash = models.CharField("Хэш результата", max_length=64)
    employee_count = models.PositiveIntegerField("Сотрудников", default=0)
    gross_total = models.DecimalField(
        "Всего начислено",
        max_digits=21,
        decimal_places=2,
        default=Decimal("0"),
    )
    deduction_total = models.DecimalField(
        "Всего удержано",
        max_digits=21,
        decimal_places=2,
        default=Decimal("0"),
    )
    payable_total = models.DecimalField(
        "Всего к выплате",
        max_digits=21,
        decimal_places=2,
        default=Decimal("0"),
    )
    requested_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="requested_payroll_runs",
        verbose_name="Запустил",
    )
    requested_at = models.DateTimeField("Рассчитан", auto_now_add=True)
    approved_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="approved_payroll_runs",
        verbose_name="Утвердил",
    )
    approved_at = models.DateTimeField("Утверждён", null=True, blank=True)
    self_approval_overridden = models.BooleanField(
        "Самоутверждение по особому праву",
        default=False,
        editable=False,
    )
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="published_payroll_runs",
        verbose_name="Опубликовал",
    )
    published_at = models.DateTimeField("Опубликован", null=True, blank=True)

    class Meta:
        verbose_name = "Запуск расчёта"
        verbose_name_plural = "Запуски расчёта"
        ordering = ["-period__date_from", "-revision"]
        indexes = [
            models.Index(
                fields=["period", "status", "revision"],
                name="pay_run_period_status_idx",
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["period", "revision"],
                name="pay_run_revision_unique",
            ),
            models.UniqueConstraint(
                fields=["period"],
                condition=Q(status=PayrollRunStatus.PUBLISHED),
                name="pay_run_one_published_per_period",
            ),
            models.CheckConstraint(
                condition=Q(approved_by__isnull=True)
                | ~Q(requested_by=F("approved_by"))
                | Q(self_approval_overridden=True),
                name="pay_run_maker_not_approver",
            ),
            models.CheckConstraint(
                condition=Q(self_approval_overridden=False)
                | Q(
                    approved_by__isnull=False,
                    requested_by=F("approved_by"),
                ),
                name="pay_run_self_override_valid",
            ),
            models.CheckConstraint(
                condition=~Q(
                    status__in=[
                        PayrollRunStatus.APPROVED,
                        PayrollRunStatus.PUBLISHED,
                    ]
                )
                | Q(approved_by__isnull=False, approved_at__isnull=False),
                name="pay_run_approval_complete",
            ),
            models.CheckConstraint(
                condition=~Q(status=PayrollRunStatus.PUBLISHED)
                | Q(published_by__isnull=False, published_at__isnull=False),
                name="pay_run_publication_complete",
            ),
            models.CheckConstraint(
                condition=Q(gross_total__gte=0),
                name="pay_run_gross_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(deduction_total__gte=0),
                name="pay_run_deduction_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(payable_total__gte=0),
                name="pay_run_payable_nonnegative",
            ),
        ]

    def __str__(self):
        return f"{self.period} / ревизия {self.revision}"

    def clean(self):
        super().clean()
        if not self.supersedes_id:
            return
        if self.pk and self.supersedes_id == self.pk:
            raise ValidationError({"supersedes": "Расчёт не может заменять себя."})
        if self.supersedes.period_id != self.period_id:
            raise ValidationError(
                {"supersedes": "Заменяемый расчёт относится к другому периоду."}
            )
        if self.revision != self.supersedes.revision + 1:
            raise ValidationError(
                {"revision": "Ревизия должна следовать за заменяемым расчётом."}
            )


class PayrollStatement(models.Model):
    """Employee result snapshot. Amount fields never change after creation."""

    run = models.ForeignKey(
        PayrollRun,
        on_delete=models.CASCADE,
        related_name="statements",
        verbose_name="Запуск",
    )
    public_id = models.UUIDField(
        "Публичный идентификатор",
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payroll_statements",
        verbose_name="Сотрудник",
    )
    supersedes = models.OneToOneField(
        "self",
        on_delete=models.RESTRICT,
        null=True,
        blank=True,
        related_name="superseded_by_statement",
        verbose_name="Заменяет листок",
    )
    employee_snapshot = models.JSONField("Снимок сотрудника", default=dict)
    currency = models.CharField(
        "Валюта",
        max_length=3,
        validators=[currency_validator],
    )
    point_delta = models.DecimalField(
        "Отклонение баллов",
        max_digits=19,
        decimal_places=4,
        null=True,
        blank=True,
    )
    gross_before_adjustments = models.DecimalField(
        "Начислено до корректировок",
        max_digits=21,
        decimal_places=2,
    )
    adjustment_total = models.DecimalField(
        "Корректировки",
        max_digits=21,
        decimal_places=2,
    )
    gross_total = models.DecimalField(
        "Итого начислено",
        max_digits=21,
        decimal_places=2,
    )
    deduction_total = models.DecimalField(
        "Удержания",
        max_digits=21,
        decimal_places=2,
    )
    net_pay = models.DecimalField(
        "После удержаний",
        max_digits=21,
        decimal_places=2,
    )
    payment_total = models.DecimalField(
        "Уже выплачено",
        max_digits=21,
        decimal_places=2,
    )
    payable = models.DecimalField(
        "К выплате",
        max_digits=21,
        decimal_places=2,
    )
    input_hash = models.CharField("Хэш входных данных", max_length=64)
    result_hash = models.CharField("Хэш результата", max_length=64)
    input_snapshot = models.JSONField("Входной снимок", default=dict)
    result_snapshot = models.JSONField("Результат расчёта", default=dict)
    created_at = models.DateTimeField("Создан", auto_now_add=True)

    class Meta:
        verbose_name = "Расчётный листок"
        verbose_name_plural = "Расчётные листки"
        ordering = ["-run__period__date_from", "employee_id"]
        indexes = [
            models.Index(
                fields=["employee", "run"],
                name="pay_statement_employee_idx",
            )
        ]
        constraints = [
            models.UniqueConstraint(
                fields=["run", "employee"],
                name="pay_statement_run_employee_unique",
            ),
            models.CheckConstraint(
                condition=Q(gross_before_adjustments__gte=0),
                name="pay_statement_pre_gross_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(gross_total__gte=0),
                name="pay_statement_gross_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(deduction_total__gte=0),
                name="pay_statement_deduction_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(payment_total__gte=0),
                name="pay_statement_payment_nonnegative",
            ),
            models.CheckConstraint(
                condition=Q(payable__gte=0),
                name="pay_statement_payable_nonnegative",
            ),
        ]

    def __str__(self):
        return f"{self.run.period}: {self.employee}"

    def clean(self):
        super().clean()
        if not self.supersedes_id:
            return
        if self.pk and self.supersedes_id == self.pk:
            raise ValidationError({"supersedes": "Листок не может заменять себя."})
        if self.supersedes.employee_id != self.employee_id:
            raise ValidationError(
                {"supersedes": "Заменяемый листок принадлежит другому сотруднику."}
            )
        if self.supersedes.run.period_id != self.run.period_id:
            raise ValidationError(
                {"supersedes": "Заменяемый листок относится к другому периоду."}
            )


class PayrollStatementLine(models.Model):
    """A rounded line copied from the core result for a statement."""

    statement = models.ForeignKey(
        PayrollStatement,
        on_delete=models.CASCADE,
        related_name="lines",
        verbose_name="Расчётный листок",
    )
    position = models.PositiveIntegerField("Позиция")
    line_id = models.CharField("Идентификатор строки", max_length=160)
    code = models.CharField("Код", max_length=64)
    label = models.CharField("Название", max_length=160)
    kind = models.CharField(
        "Тип",
        max_length=24,
        choices=PayrollComponentKind.choices,
    )
    amount = models.DecimalField(
        "Сумма",
        max_digits=21,
        decimal_places=2,
    )
    source_ref = models.CharField("Источник", max_length=255)
    reason = models.TextField("Основание", blank=True)
    source_period_from = models.DateField(
        "Период-источник: начало",
        null=True,
        blank=True,
    )
    source_period_to = models.DateField(
        "Период-источник: конец",
        null=True,
        blank=True,
    )
    is_retro = models.BooleanField("Перерасчёт прошлого периода", default=False)
    calculated = models.BooleanField("Рассчитана ядром", default=False)

    class Meta:
        verbose_name = "Строка расчётного листка"
        verbose_name_plural = "Строки расчётных листков"
        ordering = ["statement_id", "position"]
        constraints = [
            models.UniqueConstraint(
                fields=["statement", "position"],
                name="pay_statement_line_position_unique",
            ),
            models.UniqueConstraint(
                fields=["statement", "line_id"],
                name="pay_statement_line_id_unique",
            ),
            models.CheckConstraint(
                condition=Q(amount__gte=0),
                name="pay_statement_line_amount_nonnegative",
            ),
        ]

    def __str__(self):
        return f"{self.statement_id}: {self.code} {self.amount}"


class PayrollStatementAcknowledgement(models.Model):
    """Acknowledgement of a payslip, explicitly not proof of bank payment."""

    statement = models.OneToOneField(
        PayrollStatement,
        on_delete=models.CASCADE,
        related_name="acknowledgement",
        verbose_name="Расчётный листок",
    )
    employee = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="payroll_acknowledgements",
        verbose_name="Сотрудник",
    )
    content_hash = models.CharField("Хэш подтверждённого листка", max_length=64)
    idempotency_key = models.UUIDField(
        "Ключ идемпотентности",
        default=uuid.uuid4,
        unique=True,
        editable=False,
    )
    viewed_at = models.DateTimeField("Просмотрен", null=True, blank=True)
    acknowledged_at = models.DateTimeField(
        "Получение подтверждено",
        null=True,
        blank=True,
    )
    disputed_at = models.DateTimeField("Оспорен", null=True, blank=True)
    dispute_reason = models.TextField("Причина оспаривания", blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Подтверждение расчётного листка"
        verbose_name_plural = "Подтверждения расчётных листков"

    def __str__(self):
        return f"{self.employee}: листок {self.statement_id}"

    def clean(self):
        super().clean()
        if self.statement_id and self.employee_id != self.statement.employee_id:
            raise ValidationError(
                {"employee": "Подтвердить листок может только его сотрудник."}
            )
        if self.statement_id and self.content_hash != self.statement.result_hash:
            raise ValidationError(
                {"content_hash": "Хэш не совпадает с расчётным листком."}
            )


class PayrollAuditEvent(models.Model):
    """Append-only redacted audit trail for payroll commands and reads."""

    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="payroll_audit_events",
        verbose_name="Инициатор",
    )
    action = models.CharField("Действие", max_length=80)
    object_type = models.CharField("Тип объекта", max_length=80)
    object_id = models.CharField("Идентификатор объекта", max_length=80)
    period = models.ForeignKey(
        PayrollPeriod,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="audit_events",
        verbose_name="Период",
    )
    before_hash = models.CharField("Хэш до", max_length=64, blank=True)
    after_hash = models.CharField("Хэш после", max_length=64, blank=True)
    metadata = models.JSONField("Безопасные метаданные", default=dict, blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Событие аудита зарплаты"
        verbose_name_plural = "События аудита зарплаты"
        ordering = ["-created_at", "-id"]
        indexes = [
            models.Index(
                fields=["object_type", "object_id", "created_at"],
                name="pay_audit_object_time_idx",
            ),
            models.Index(
                fields=["period", "created_at"],
                name="pay_audit_period_time_idx",
            ),
        ]

    def __str__(self):
        return f"{self.action}: {self.object_type}#{self.object_id}"
