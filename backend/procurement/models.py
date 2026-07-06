# backend/procurement/models.py
"""
Модели для модуля закупок и инвентаря.

Основные сущности:
- ProcurementRequest: заявка на закупку
- ProcurementItem: позиция в заявке
- Approval: запись о согласовании
- Equipment: единица оборудования/инвентаря
- EquipmentCategory: категория оборудования
- MaintenanceRecord: запись об обслуживании
- Budget: бюджет отдела
- Supplier: поставщик
"""

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models
from django.db.models import Sum
from django.db.models.functions import Coalesce
from django.utils import timezone
from employees.models import Department

from .constants import (
    ApprovalStatus,
    EquipmentStatus,
    MaintenanceType,
    ProcurementFulfillmentStatus,
    ProcurementItemExecutionStatus,
    ProcurementStatus,
    UrgencyLevel,
    get_default_approval_step_name,
)

User = get_user_model()


class ProcurementSettings(models.Model):
    """Настройки модуля закупок."""

    name = models.CharField("Название", max_length=100, default="Основные настройки")
    available_processing_departments = models.ManyToManyField(
        Department,
        blank=True,
        related_name="procurement_processing_settings",
        verbose_name="Доступные отделы-исполнители",
        help_text=(
            "Если список пуст, в форме заявки доступны все отделы. "
            "Заполните список, чтобы ограничить выбор."
        ),
    )
    default_processing_department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="default_procurement_processing_settings",
        verbose_name="Отдел-исполнитель по умолчанию",
        help_text="Этот отдел будет автоматически выбран в новой заявке.",
    )
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Настройки закупок"
        verbose_name_plural = "Настройки закупок"

    def __str__(self):
        return self.name

    @classmethod
    def get_solo(cls):
        settings = cls.objects.first()
        if settings:
            return settings
        return cls.objects.create()

    def clean(self):
        super().clean()
        if (
            self.pk
            and self.default_processing_department_id
            and self.available_processing_departments.exists()
            and not self.available_processing_departments.filter(
                pk=self.default_processing_department_id
            ).exists()
        ):
            raise ValidationError(
                {
                    "default_processing_department": (
                        "Отдел по умолчанию должен входить в список "
                        "доступных отделов-исполнителей."
                    )
                }
            )

    def get_processing_departments_queryset(self):
        departments = self.available_processing_departments.all()
        if departments.exists():
            return departments
        return Department.objects.all()


class ProcurementRequest(models.Model):
    """Заявка на закупку.

    Статусы: DRAFT → PENDING → APPROVED → IN_PROGRESS → COMPLETED
    Альтернативные переходы: → REJECTED, → CANCELLED
    """

    title = models.CharField(
        "Название", max_length=255, help_text="Краткое название заявки"
    )
    description = models.TextField(
        "Описание",
        help_text="Подробное описание и обоснование необходимости закупки",
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="procurement_requests",
        verbose_name="Отдел",
    )
    processing_department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="processing_procurement_requests",
        verbose_name="Отдел-исполнитель",
        help_text="Отдел, который должен обработать заявку",
    )
    requestor = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="procurement_requests",
        verbose_name="Заявитель",
    )
    executor = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="executing_procurements",
        verbose_name="Исполнитель",
        help_text="Кто взял заявку в работу",
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=ProcurementStatus.choices,
        default=ProcurementStatus.DRAFT,
    )
    urgency = models.CharField(
        "Срочность",
        max_length=20,
        choices=UrgencyLevel.choices,
        default=UrgencyLevel.MEDIUM,
    )
    fulfillment_status = models.CharField(
        "Статус исполнения",
        max_length=30,
        choices=ProcurementFulfillmentStatus.choices,
        default=ProcurementFulfillmentStatus.PENDING,
    )
    actual_cost = models.DecimalField(
        "Фактическая стоимость",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    # Даты
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)
    submitted_at = models.DateTimeField(
        "Отправлено на согласование", null=True, blank=True
    )
    started_at = models.DateTimeField("Взято в работу", null=True, blank=True)
    completed_at = models.DateTimeField("Завершено", null=True, blank=True)

    class Meta:
        verbose_name = "Заявка на закупку"
        verbose_name_plural = "Заявки на закупку"
        ordering = ["-created_at"]
        permissions = [
            ("approve_procurementrequest", "Can approve procurement requests"),
            ("view_all_requests", "Can view all department requests"),
            ("execute_procurement", "Can execute approved requests"),
        ]

    def __str__(self):
        return f"#{self.pk} {self.title}"

    def get_required_approval_priorities(self):
        """Возвращает приоритеты обязательных этапов из таблицы маршрутов."""
        return list(
            self.get_required_approval_routes().values_list(
                "priority", flat=True
            )
        )

    def get_required_approval_routes(self):
        """Возвращает queryset обязательных этапов из таблицы маршрутов."""
        return ApprovalRoute.get_applicable_routes(self.total_cost)

    @property
    def total_cost(self):
        """Общая стоимость заявки по уточненным или ориентировочным ценам."""
        effective_unit_price = Coalesce(
            models.F("actual_unit_price"),
            models.F("estimated_unit_price"),
            Decimal("0.00"),
            output_field=models.DecimalField(
                max_digits=12,
                decimal_places=2,
            ),
        )
        line_total = models.ExpressionWrapper(
            effective_unit_price * models.F("quantity"),
            output_field=models.DecimalField(
                max_digits=18,
                decimal_places=2,
            ),
        )
        total = self.items.aggregate(
            total=Sum(
                line_total,
                output_field=models.DecimalField(
                    max_digits=18,
                    decimal_places=2,
                ),
            )
        )["total"]
        return total or Decimal("0.00")

    @property
    def items_count(self):
        """Количество позиций в заявке."""
        return self.items.count()

    @property
    def is_editable(self):
        """Можно ли редактировать заявку."""
        return self.status in [
            ProcurementStatus.DRAFT,
            ProcurementStatus.WAITING,
        ] and self.executor_id is None

    def recalculate_fulfillment_status(self, save=True):
        """Пересчитать рабочий статус заявки по количествам позиций."""
        items = list(self.items.model.objects.filter(request_id=self.pk))
        if not items:
            new_status = ProcurementFulfillmentStatus.PENDING
        elif any(
            item.execution_status in {
                ProcurementItemExecutionStatus.REJECTED,
                ProcurementItemExecutionStatus.COMPLETED_WITH_ISSUE,
                ProcurementItemExecutionStatus.EDITED,
                ProcurementItemExecutionStatus.DEFECTIVE,
            }
            for item in items
        ):
            new_status = ProcurementFulfillmentStatus.ISSUES
        else:
            total_quantity = sum(item.quantity for item in items)
            ordered_quantity = sum(
                item.effective_ordered_quantity for item in items
            )
            received_quantity = sum(
                item.effective_received_quantity for item in items
            )

            if received_quantity >= total_quantity:
                new_status = ProcurementFulfillmentStatus.COMPLETED
            elif received_quantity > 0:
                new_status = ProcurementFulfillmentStatus.PARTIALLY_RECEIVED
            elif ordered_quantity >= total_quantity:
                new_status = ProcurementFulfillmentStatus.ORDERED
            elif ordered_quantity > 0:
                new_status = ProcurementFulfillmentStatus.PARTIALLY_ORDERED
            else:
                new_status = ProcurementFulfillmentStatus.PENDING

        should_close = (
            new_status == ProcurementFulfillmentStatus.COMPLETED
            and self.status in [
                ProcurementStatus.WAITING,
                ProcurementStatus.IN_PROGRESS,
            ]
        )

        if self.fulfillment_status == new_status and not should_close:
            return new_status

        self.fulfillment_status = new_status
        update_fields = ["fulfillment_status", "updated_at"]
        if should_close:
            self.status = ProcurementStatus.COMPLETED
            self.completed_at = timezone.now()
            update_fields.extend(["status", "completed_at"])

        if save:
            self.save(update_fields=update_fields)
        return new_status


class ProcurementRequestView(models.Model):
    """Персональная отметка просмотра заявки пользователем."""

    request = models.ForeignKey(
        ProcurementRequest,
        on_delete=models.CASCADE,
        related_name="view_states",
        verbose_name="Заявка",
    )
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="procurement_request_views",
        verbose_name="Пользователь",
    )
    is_viewed = models.BooleanField("Просмотрено", default=True)
    viewed_at = models.DateTimeField(
        "Просмотрено в",
        null=True,
        blank=True,
    )
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Отметка просмотра заявки"
        verbose_name_plural = "Отметки просмотра заявок"
        constraints = [
            models.UniqueConstraint(
                fields=["request", "user"],
                name="unique_procurement_request_view_user",
            ),
        ]

    def __str__(self):
        return f"{self.request_id}: {self.user_id} viewed={self.is_viewed}"


class ProcurementItem(models.Model):
    """Позиция в заявке на закупку."""

    request = models.ForeignKey(
        ProcurementRequest,
        on_delete=models.CASCADE,
        related_name="items",
        verbose_name="Заявка",
    )
    name = models.CharField(
        "Название", max_length=255, help_text="Название товара или услуги"
    )
    description = models.TextField(
        "Описание",
        blank=True,
        help_text="Подробное описание, технические характеристики",
    )
    quantity = models.PositiveIntegerField(
        "Количество", default=1, validators=[MinValueValidator(1)]
    )
    unit = models.CharField(
        "Единица измерения",
        max_length=50,
        default="шт",
        help_text="Например: шт, кг, л, упак, м",
    )
    estimated_unit_price = models.DecimalField(
        "Цена за единицу",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    supplier_info = models.TextField(
        "Информация о поставщике",
        blank=True,
        help_text="Ссылки на товар, контакты поставщика",
    )
    links = models.JSONField(
        "Ссылки",
        default=list,
        blank=True,
        help_text="Список ссылок на позицию",
    )
    expected_delivery_dates = models.JSONField(
        "Ожидаемые даты поступления",
        default=list,
        blank=True,
        help_text="Список ожидаемых дат поступления в формате YYYY-MM-DD",
    )
    actual_unit_price = models.DecimalField(
        "Фактическая цена за единицу",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    ordered_quantity = models.PositiveIntegerField(
        "Заказанное количество",
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Сколько единиц заказал исполнитель",
    )
    received_quantity = models.PositiveIntegerField(
        "Полученное количество",
        null=True,
        blank=True,
        validators=[MinValueValidator(0)],
        help_text="Сколько единиц фактически получено",
    )
    execution_status = models.CharField(
        "Статус выполнения",
        max_length=30,
        choices=ProcurementItemExecutionStatus.choices,
        default=ProcurementItemExecutionStatus.PENDING,
    )
    executor_comment = models.TextField(
        "Комментарий исполнителя",
        blank=True,
    )
    equipment = models.OneToOneField(
        "Equipment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="procurement_item",
        verbose_name="Оборудование",
        help_text="Связь с оборудованием после закупки",
    )
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Позиция заявки"
        verbose_name_plural = "Позиции заявок"
        ordering = ["id"]

    def __str__(self):
        return f"{self.name} ({self.quantity} {self.unit})"

    @property
    def effective_ordered_quantity(self):
        if self.ordered_quantity is not None:
            return self.ordered_quantity
        if self.execution_status in {
            ProcurementItemExecutionStatus.ORDERED,
            ProcurementItemExecutionStatus.RECEIVED,
        }:
            return self.quantity
        return 0

    @property
    def effective_received_quantity(self):
        if self.received_quantity is not None:
            return self.received_quantity
        if self.execution_status == ProcurementItemExecutionStatus.RECEIVED:
            return self.quantity
        return 0

    @property
    def execution_status_display(self):
        problem_statuses = {
            ProcurementItemExecutionStatus.REJECTED,
            ProcurementItemExecutionStatus.COMPLETED_WITH_ISSUE,
            ProcurementItemExecutionStatus.EDITED,
            ProcurementItemExecutionStatus.DEFECTIVE,
        }
        if self.execution_status in problem_statuses:
            return self.get_execution_status_display()
        if self.effective_received_quantity > 0:
            if self.effective_received_quantity < self.quantity:
                return "Получено частично"
            return ProcurementItemExecutionStatus.RECEIVED.label
        if self.effective_ordered_quantity > 0:
            if self.effective_ordered_quantity < self.quantity:
                return "Заказано частично"
            return ProcurementItemExecutionStatus.ORDERED.label
        return self.get_execution_status_display()

    @property
    def total_price(self):
        """Общая стоимость позиции по фактической или ориентировочной цене."""
        unit_price = self.actual_unit_price
        if unit_price is None:
            unit_price = self.estimated_unit_price
        if unit_price is None:
            return Decimal("0.00")
        return unit_price * self.quantity

    def clean(self):
        super().clean()
        if (
            self.ordered_quantity is not None
            and self.ordered_quantity > self.quantity
        ):
            raise ValidationError(
                {"ordered_quantity": "Не может быть больше количества позиции"}
            )
        if (
            self.received_quantity is not None
            and self.received_quantity > self.quantity
        ):
            raise ValidationError(
                {"received_quantity": "Не может быть больше количества позиции"}
            )

    @staticmethod
    def _mark_update_field(update_fields, field):
        if update_fields is not None:
            update_fields.add(field)

    def _sync_execution_status_from_quantities(self, update_fields=None):
        workflow_statuses = {
            ProcurementItemExecutionStatus.PENDING,
            ProcurementItemExecutionStatus.ORDERED,
            ProcurementItemExecutionStatus.RECEIVED,
        }
        if self.execution_status not in workflow_statuses:
            return

        ordered_quantity = self.ordered_quantity or 0
        received_quantity = self.received_quantity or 0

        if received_quantity > 0 and self.ordered_quantity is None:
            self.ordered_quantity = min(received_quantity, self.quantity)
            self._mark_update_field(update_fields, "ordered_quantity")
            ordered_quantity = self.ordered_quantity
        elif received_quantity > 0 and ordered_quantity < received_quantity:
            self.ordered_quantity = min(received_quantity, self.quantity)
            self._mark_update_field(update_fields, "ordered_quantity")
            ordered_quantity = self.ordered_quantity

        new_status = self.execution_status
        if received_quantity > 0:
            new_status = (
                ProcurementItemExecutionStatus.RECEIVED
                if received_quantity >= self.quantity
                else ProcurementItemExecutionStatus.ORDERED
            )
        elif ordered_quantity > 0:
            new_status = ProcurementItemExecutionStatus.ORDERED
        elif self.execution_status in {
            ProcurementItemExecutionStatus.ORDERED,
            ProcurementItemExecutionStatus.RECEIVED,
        }:
            new_status = ProcurementItemExecutionStatus.PENDING

        if new_status != self.execution_status:
            self.execution_status = new_status
            self._mark_update_field(update_fields, "execution_status")

    def save(self, *args, **kwargs):
        update_fields = kwargs.get("update_fields")
        if update_fields is not None:
            update_fields = set(update_fields)
            kwargs["update_fields"] = update_fields

        if (
            self.execution_status == ProcurementItemExecutionStatus.ORDERED
            and self.ordered_quantity is None
        ):
            self.ordered_quantity = self.quantity
            self._mark_update_field(update_fields, "ordered_quantity")
        if self.execution_status == ProcurementItemExecutionStatus.RECEIVED:
            if self.ordered_quantity is None:
                self.ordered_quantity = self.quantity
                self._mark_update_field(update_fields, "ordered_quantity")
            if self.received_quantity is None:
                self.received_quantity = self.quantity
                self._mark_update_field(update_fields, "received_quantity")
        self._sync_execution_status_from_quantities(update_fields=update_fields)
        super().save(*args, **kwargs)
        if self.request_id:
            self.request.recalculate_fulfillment_status(save=True)

    def delete(self, *args, **kwargs):
        request = self.request
        result = super().delete(*args, **kwargs)
        request.recalculate_fulfillment_status(save=True)
        return result


class ApprovalRoute(models.Model):
    """Правило получения согласующего для этапа с заданным приоритетом."""

    class ResolverType(models.TextChoices):
        DEPARTMENT_HEAD = "department_head", "Руководитель отдела"
        FIXED_EMPLOYEE = "fixed_employee", "Конкретный сотрудник"

    priority = models.PositiveSmallIntegerField(
        "Приоритет",
        unique=True,
        db_index=True,
        help_text="Чем меньше число, тем раньше этап в цепочке согласования.",
    )
    min_amount = models.DecimalField(
        "Минимальная сумма заявки",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
        validators=[MinValueValidator(Decimal("0.00"))],
        help_text=(
            "Пусто = этап обязателен для любой суммы. "
            "Иначе этап включается при сумме не меньше указанной."
        ),
    )
    name = models.CharField(
        "Название этапа",
        max_length=150,
        blank=True,
        help_text="Необязательно. Если заполнено, будет показано в интерфейсе.",
    )
    resolver_type = models.CharField(
        "Тип резолва",
        max_length=20,
        choices=ResolverType.choices,
        default=ResolverType.FIXED_EMPLOYEE,
    )
    employee = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="approval_routes",
        verbose_name="Согласующий",
        null=True,
        blank=True,
    )

    class Meta:
        verbose_name = "Маршрут согласования"
        verbose_name_plural = "Маршруты согласования"
        ordering = ["priority", "id"]

    @classmethod
    def get_applicable_routes(cls, total_cost):
        return cls.objects.filter(
            models.Q(min_amount__isnull=True)
            | models.Q(min_amount__lte=total_cost)
        ).order_by("priority", "id")

    def __str__(self):
        threshold = "" if self.min_amount is None else f" от {self.min_amount}"
        if self.resolver_type == self.ResolverType.DEPARTMENT_HEAD:
            return f"Этап {self.priority}{threshold} → руководитель отдела"
        return f"Этап {self.priority}{threshold} → {self.employee}"

    def clean(self):
        super().clean()
        if (
            self.resolver_type == self.ResolverType.FIXED_EMPLOYEE
            and not self.employee_id
        ):
            raise ValidationError(
                {"employee": "Для статического этапа укажите сотрудника."}
            )
        if (
            self.resolver_type == self.ResolverType.DEPARTMENT_HEAD
            and self.employee_id
        ):
            raise ValidationError(
                {
                    "employee": (
                        "Для этапа руководителя отдела "
                        "сотрудник не указывается."
                    )
                }
            )


class Approval(models.Model):
    """Запись о согласовании заявки."""

    request = models.ForeignKey(
        ProcurementRequest,
        on_delete=models.CASCADE,
        related_name="approvals",
        verbose_name="Заявка",
    )
    approver = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="procurement_approvals",
        verbose_name="Согласующий",
    )
    priority = models.PositiveSmallIntegerField(
        "Приоритет",
        db_index=True,
    )
    step_name = models.CharField(
        "Название этапа",
        max_length=150,
        blank=True,
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=ApprovalStatus.choices,
        default=ApprovalStatus.PENDING,
    )
    comment = models.TextField("Комментарий", blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Согласование"
        verbose_name_plural = "Согласования"
        ordering = ["priority", "created_at", "id"]
        unique_together = [("request", "priority")]

    def __str__(self):
        return f"Этап {self.priority} - {self.get_status_display()}"

    def save(self, *args, **kwargs):
        if not self.step_name:
            route = (
                ApprovalRoute.objects.filter(priority=self.priority)
                .only(
                    "name",
                    "resolver_type",
                )
                .first()
            )
            if route and route.name:
                self.step_name = route.name
            else:
                resolver_type = route.resolver_type if route else None
                self.step_name = get_default_approval_step_name(
                    self.priority,
                    resolver_type=resolver_type,
                )
        super().save(*args, **kwargs)


class EquipmentCategory(models.Model):
    """Категория оборудования (иерархическая)."""

    name = models.CharField("Название", max_length=100, unique=True)
    parent = models.ForeignKey(
        "self",
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="children",
        verbose_name="Родительская категория",
    )
    description = models.TextField("Описание", blank=True)
    icon = models.CharField(
        "Иконка Bootstrap",
        max_length=50,
        blank=True,
        help_text="Например: bi-laptop, bi-printer",
    )
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Категория оборудования"
        verbose_name_plural = "Категории оборудования"
        ordering = ["name"]

    def __str__(self):
        if self.parent:
            return f"{self.parent.name} → {self.name}"
        return self.name

    @property
    def full_path(self):
        """Полный путь категории."""
        if self.parent:
            return f"{self.parent.full_path} → {self.name}"
        return self.name


class Equipment(models.Model):
    """Единица оборудования/инвентаря."""

    name = models.CharField("Название", max_length=255)
    inventory_number = models.CharField(
        "Инвентарный номер",
        max_length=50,
        unique=True,
        help_text="Например: INV-2024-0001",
    )
    serial_number = models.CharField(
        "Серийный номер",
        max_length=100,
        blank=True,
        help_text="Серийный номер производителя",
    )
    category = models.ForeignKey(
        EquipmentCategory,
        on_delete=models.PROTECT,
        related_name="equipment",
        verbose_name="Категория",
    )
    status = models.CharField(
        "Статус",
        max_length=20,
        choices=EquipmentStatus.choices,
        default=EquipmentStatus.AVAILABLE,
    )
    department = models.ForeignKey(
        Department,
        on_delete=models.PROTECT,
        related_name="equipment",
        verbose_name="Отдел",
    )
    responsible_person = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="responsible_equipment",
        verbose_name="Ответственный",
    )
    location = models.CharField(
        "Расположение",
        max_length=255,
        blank=True,
        help_text="Например: Офис 3.14, Стеллаж А-5",
    )
    purchase_date = models.DateField("Дата покупки")
    warranty_until = models.DateField("Гарантия до", null=True, blank=True)
    purchase_cost = models.DecimalField(
        "Стоимость покупки",
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.01"))],
    )
    notes = models.TextField("Примечания", blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Оборудование"
        verbose_name_plural = "Оборудование"
        ordering = ["-created_at"]

    def __str__(self):
        return f"{self.inventory_number} - {self.name}"

    @property
    def is_under_warranty(self):
        """Находится ли под гарантией."""
        if not self.warranty_until:
            return False
        return timezone.now().date() <= self.warranty_until


class MaintenanceRecord(models.Model):
    """Запись о техническом обслуживании оборудования."""

    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        related_name="maintenance_history",
        verbose_name="Оборудование",
    )
    date = models.DateField("Дата обслуживания")
    type = models.CharField(
        "Тип обслуживания", max_length=20, choices=MaintenanceType.choices
    )
    description = models.TextField("Описание", help_text="Что было сделано")
    cost = models.DecimalField(
        "Стоимость",
        max_digits=10,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    performed_by = models.ForeignKey(
        User,
        on_delete=models.PROTECT,
        related_name="performed_maintenance",
        verbose_name="Выполнил",
    )
    next_maintenance_date = models.DateField(
        "Следующее ТО", null=True, blank=True
    )
    created_at = models.DateTimeField("Создано", auto_now_add=True)

    class Meta:
        verbose_name = "Запись обслуживания"
        verbose_name_plural = "Записи обслуживания"
        ordering = ["-date"]

    def __str__(self):
        return (
            f"{self.equipment.inventory_number} - "
            f"{self.get_type_display()} ({self.date})"
        )


class EquipmentTransferLog(models.Model):
    """Лог передачи/перемещения оборудования."""

    TRANSFER_TYPES = [
        ("assignment", "Назначение ответственного"),
        ("transfer", "Перемещение"),
        ("return", "Возврат"),
    ]

    equipment = models.ForeignKey(
        Equipment,
        on_delete=models.CASCADE,
        related_name="transfer_logs",
        verbose_name="Оборудование",
    )
    from_department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfers_out",
        verbose_name="Из отдела",
    )
    to_department = models.ForeignKey(
        Department,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfers_in",
        verbose_name="В отдел",
    )
    from_person = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipment_given",
        verbose_name="От кого",
    )
    to_person = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="equipment_received",
        verbose_name="Кому",
    )
    from_location = models.CharField("Откуда", max_length=255, blank=True)
    to_location = models.CharField("Куда", max_length=255, blank=True)
    transfer_type = models.CharField(
        "Тип передачи",
        max_length=20,
        choices=TRANSFER_TYPES,
        default="transfer",
    )
    reason = models.TextField("Причина/комментарий", blank=True)
    created_at = models.DateTimeField("Дата передачи", auto_now_add=True)
    created_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="transfers_created",
        verbose_name="Кто оформил",
    )

    class Meta:
        verbose_name = "Лог передачи"
        verbose_name_plural = "Логи передач"
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.equipment.inventory_number}: "
            f"{self.from_person or 'Склад'} → {self.to_person or 'Склад'}"
        )


class Budget(models.Model):
    """Бюджет отдела на квартал."""

    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="budgets",
        verbose_name="Отдел",
    )
    year = models.PositiveIntegerField("Год", help_text="Например: 2025")
    quarter = models.PositiveIntegerField(
        "Квартал",
        choices=[
            (1, "1 квартал"),
            (2, "2 квартал"),
            (3, "3 квартал"),
            (4, "4 квартал"),
        ],
    )
    allocated_amount = models.DecimalField(
        "Выделено",
        max_digits=14,
        decimal_places=2,
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    spent_amount = models.DecimalField(
        "Потрачено",
        max_digits=14,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Бюджет"
        verbose_name_plural = "Бюджеты"
        ordering = ["-year", "-quarter"]
        unique_together = [("department", "year", "quarter")]

    def __str__(self):
        return f"{self.department.name} - {self.year} Q{self.quarter}"

    @property
    def remaining_amount(self):
        """Остаток бюджета."""
        allocated = self.allocated_amount or Decimal("0.00")
        return allocated - self.spent_amount

    @property
    def reserved_amount(self):
        """Сумма зарезервированная pending заявками."""
        # Суммируем total_cost всех pending заявок через их позиции
        pending_requests = self.department.procurement_requests.filter(
            status=ProcurementStatus.PENDING,
            created_at__year=self.year,
            created_at__month__in=self._quarter_months(),
        )

        total = Decimal("0.00")
        for req in pending_requests:
            total += req.total_cost
        return total

    @property
    def available_amount(self):
        """Доступный бюджет (с учётом резерва)."""
        return self.remaining_amount - self.reserved_amount

    def _quarter_months(self):
        """Получить месяцы квартала."""
        return {
            1: [1, 2, 3],
            2: [4, 5, 6],
            3: [7, 8, 9],
            4: [10, 11, 12],
        }[self.quarter]

    @property
    def utilization_percentage(self):
        """Процент использования бюджета."""
        allocated = self.allocated_amount or Decimal("0.00")
        if allocated == 0:
            return Decimal("0.00")
        return (self.spent_amount / allocated * 100).quantize(Decimal("0.01"))

    def can_spend(self, amount):
        """Проверка возможности потратить сумму."""
        return self.remaining_amount >= amount


class Supplier(models.Model):
    """Поставщик товаров/услуг."""

    name = models.CharField("Название", max_length=255)
    contact_person = models.CharField(
        "Контактное лицо", max_length=255, blank=True
    )
    phone = models.CharField("Телефон", max_length=50, blank=True)
    email = models.EmailField("Email", blank=True)
    address = models.TextField("Адрес", blank=True)
    website = models.URLField("Веб-сайт", blank=True)
    inn = models.CharField(
        "ИНН",
        max_length=12,
        blank=True,
        help_text="ИНН организации (10 или 12 цифр)",
    )
    rating = models.DecimalField(
        "Рейтинг",
        max_digits=3,
        decimal_places=2,
        default=Decimal("0.00"),
        validators=[MinValueValidator(Decimal("0.00"))],
    )
    is_active = models.BooleanField("Активен", default=True)
    notes = models.TextField("Примечания", blank=True)
    created_at = models.DateTimeField("Создано", auto_now_add=True)
    updated_at = models.DateTimeField("Обновлено", auto_now=True)

    class Meta:
        verbose_name = "Поставщик"
        verbose_name_plural = "Поставщики"
        ordering = ["name"]

    def __str__(self):
        return self.name
