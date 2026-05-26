"""
Сериализаторы для модуля закупок.
"""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from communications import comments_helpers
from procurement.constants import (
    ProcurementItemExecutionStatus,
    ProcurementStatus,
    get_default_approval_step_name,
)
from procurement.services import ProcurementApprovalResolver
from procurement.models import (
    Approval,
    Budget,
    Equipment,
    EquipmentCategory,
    MaintenanceRecord,
    ProcurementItem,
    ProcurementRequest,
    Supplier,
)
from ..employees.serializers import EmployeeBriefSerializer


PROBLEM_ITEM_STATUSES = {
    ProcurementItemExecutionStatus.REJECTED,
    ProcurementItemExecutionStatus.COMPLETED_WITH_ISSUE,
    ProcurementItemExecutionStatus.EDITED,
    ProcurementItemExecutionStatus.DEFECTIVE,
}


def _validate_item_quantities(attrs, instance=None):
    quantity = attrs.get("quantity", getattr(instance, "quantity", None))
    for field in ("ordered_quantity", "received_quantity"):
        value = attrs.get(field, getattr(instance, field, None))
        if value is not None and quantity is not None and value > quantity:
            raise serializers.ValidationError(
                {field: "Не может быть больше количества позиции"}
            )
    return attrs


def _request_items(obj):
    return list(obj.items.all())


def _effective_ordered_quantity(item):
    if item.ordered_quantity is not None:
        return item.ordered_quantity
    if item.execution_status in {
        ProcurementItemExecutionStatus.ORDERED,
        ProcurementItemExecutionStatus.RECEIVED,
    }:
        return item.quantity
    return 0


def _effective_received_quantity(item):
    if item.received_quantity is not None:
        return item.received_quantity
    if item.execution_status == ProcurementItemExecutionStatus.RECEIVED:
        return item.quantity
    return 0


class ProcurementRequestSummaryMixin(serializers.Serializer):
    next_expected_delivery_date = serializers.SerializerMethodField()
    items_total_count = serializers.SerializerMethodField()
    items_received_count = serializers.SerializerMethodField()
    items_problem_count = serializers.SerializerMethodField()
    items_pending_count = serializers.SerializerMethodField()
    total_requested_quantity = serializers.SerializerMethodField()
    total_ordered_quantity = serializers.SerializerMethodField()
    total_received_quantity = serializers.SerializerMethodField()

    @extend_schema_field(serializers.DateField(allow_null=True))
    def get_next_expected_delivery_date(self, obj):
        dated_items = [
            item for item in _request_items(obj)
            if item.expected_delivery_date
        ]
        if not dated_items:
            return None

        pending_dates = [
            item.expected_delivery_date for item in dated_items
            if item.execution_status != ProcurementItemExecutionStatus.RECEIVED
        ]
        if pending_dates:
            return min(pending_dates).isoformat()
        return max(item.expected_delivery_date for item in dated_items).isoformat()

    @extend_schema_field(serializers.IntegerField())
    def get_items_total_count(self, obj):
        return len(_request_items(obj))

    @extend_schema_field(serializers.IntegerField())
    def get_items_received_count(self, obj):
        return sum(
            1 for item in _request_items(obj)
            if item.execution_status == ProcurementItemExecutionStatus.RECEIVED
        )

    @extend_schema_field(serializers.IntegerField())
    def get_items_problem_count(self, obj):
        return sum(
            1 for item in _request_items(obj)
            if item.execution_status in PROBLEM_ITEM_STATUSES
        )

    @extend_schema_field(serializers.IntegerField())
    def get_items_pending_count(self, obj):
        return sum(
            1 for item in _request_items(obj)
            if item.execution_status == ProcurementItemExecutionStatus.PENDING
        )

    @extend_schema_field(serializers.IntegerField())
    def get_total_requested_quantity(self, obj):
        return sum(item.quantity for item in _request_items(obj))

    @extend_schema_field(serializers.IntegerField())
    def get_total_ordered_quantity(self, obj):
        return sum(_effective_ordered_quantity(item) for item in _request_items(obj))

    @extend_schema_field(serializers.IntegerField())
    def get_total_received_quantity(self, obj):
        return sum(_effective_received_quantity(item) for item in _request_items(obj))


class ProcurementItemSerializer(serializers.ModelSerializer):
    """Сериализатор для позиций заявки."""

    estimated_unit_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    ordered_quantity = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
    )
    received_quantity = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
    )
    initial_comment = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
    )
    total_price = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    execution_status_display = serializers.CharField(
        source="get_execution_status_display", read_only=True
    )
    comments_count = serializers.SerializerMethodField()

    @extend_schema_field(serializers.IntegerField())
    def get_comments_count(self, obj):
        annotated_count = getattr(obj, "comments_count", None)
        if annotated_count is not None:
            return annotated_count

        from communications.comments_helpers import get_comment_count

        return get_comment_count(obj)

    class Meta:
        model = ProcurementItem
        fields = [
            "id",
            "request",
            "name",
            "description",
            "quantity",
            "unit",
            "estimated_unit_price",
            "total_price",
            "ordered_quantity",
            "received_quantity",
            "supplier_info",
            "links",
            "expected_delivery_date",
            "actual_unit_price",
            "execution_status",
            "execution_status_display",
            "executor_comment",
            "initial_comment",
            "comments_count",
            "equipment",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "total_price",
            "execution_status_display",
            "comments_count",
        ]

    def validate(self, attrs):
        return _validate_item_quantities(attrs, self.instance)

    def create(self, validated_data):
        initial_comment = validated_data.pop("initial_comment", "").strip()
        item = super().create(validated_data)
        request = self.context.get("request")
        author = getattr(request, "user", None)
        if initial_comment and author and author.is_authenticated:
            comments_helpers.create_comment(
                obj=item,
                author=author,
                content=initial_comment,
            )
        return item


class ProcurementItemCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания позиций (без request)."""

    estimated_unit_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        required=False,
        allow_null=True,
    )
    ordered_quantity = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
    )
    received_quantity = serializers.IntegerField(
        required=False,
        allow_null=True,
        min_value=0,
    )
    initial_comment = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
    )

    class Meta:
        model = ProcurementItem
        fields = [
            "name",
            "description",
            "quantity",
            "unit",
            "estimated_unit_price",
            "ordered_quantity",
            "received_quantity",
            "supplier_info",
            "links",
            "expected_delivery_date",
            "actual_unit_price",
            "execution_status",
            "executor_comment",
            "initial_comment",
        ]

    def validate(self, attrs):
        return _validate_item_quantities(attrs, self.instance)


class ApprovalSerializer(serializers.ModelSerializer):
    """Сериализатор для согласований."""

    approver = EmployeeBriefSerializer(read_only=True)
    approver_name = serializers.CharField(
        source="approver.get_full_name", read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    step_label = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField())
    def get_step_label(self, obj):
        return obj.step_name or get_default_approval_step_name(obj.priority)

    class Meta:
        model = Approval
        fields = [
            "id",
            "request",
            "approver",
            "approver_name",
            "priority",
            "step_name",
            "step_label",
            "status",
            "status_display",
            "comment",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "approver_name",
            "step_name",
            "step_label",
            "status_display",
        ]


class ProcurementRequestListSerializer(
    ProcurementRequestSummaryMixin,
    serializers.ModelSerializer,
):
    """Сериализатор для списка заявок (краткий)."""

    department_name = serializers.CharField(
        source="department.name", read_only=True
    )
    processing_department_name = serializers.CharField(
        source="processing_department.name", read_only=True, allow_null=True
    )
    requestor_name = serializers.CharField(
        source="requestor.get_full_name", read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    urgency_display = serializers.CharField(
        source="get_urgency_display", read_only=True
    )
    fulfillment_status_display = serializers.CharField(
        source="get_fulfillment_status_display", read_only=True
    )
    items_count = serializers.IntegerField(read_only=True)
    total_cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    executor_name = serializers.CharField(
        source="executor.get_full_name", read_only=True, allow_null=True
    )
    comments_count = serializers.IntegerField(read_only=True, default=0)
    can_current_user_approve = serializers.SerializerMethodField()

    @extend_schema_field(serializers.BooleanField())
    def get_can_current_user_approve(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return ProcurementApprovalResolver.user_can_approve(user, obj)

    class Meta:
        model = ProcurementRequest
        fields = [
            "id",
            "title",
            "department",
            "department_name",
            "processing_department",
            "processing_department_name",
            "requestor",
            "requestor_name",
            "executor",
            "executor_name",
            "status",
            "status_display",
            "urgency",
            "urgency_display",
            "fulfillment_status",
            "fulfillment_status_display",
            "total_cost",
            "items_count",
            "next_expected_delivery_date",
            "items_total_count",
            "items_received_count",
            "items_problem_count",
            "items_pending_count",
            "total_requested_quantity",
            "total_ordered_quantity",
            "total_received_quantity",
            "comments_count",
            "can_current_user_approve",
            "created_at",
            "submitted_at",
            "started_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "submitted_at",
            "started_at",
            "department_name",
            "processing_department_name",
            "requestor_name",
            "executor_name",
            "status_display",
            "urgency_display",
            "fulfillment_status",
            "fulfillment_status_display",
            "items_count",
            "total_cost",
            "next_expected_delivery_date",
            "items_total_count",
            "items_received_count",
            "items_problem_count",
            "items_pending_count",
            "total_requested_quantity",
            "total_ordered_quantity",
            "total_received_quantity",
            "comments_count",
            "can_current_user_approve",
        ]

    def update(self, instance, validated_data):
        """
        При обновлении заявки запрещаем изменение requestor и department.
        Эти поля игнорируются при обновлении.
        """
        # Игнорируем попытки изменить requestor
        validated_data.pop("requestor", None)
        # Игнорируем попытки изменить department
        validated_data.pop("department", None)
        return super().update(instance, validated_data)


class ProcurementRequestDetailSerializer(
    ProcurementRequestSummaryMixin,
    serializers.ModelSerializer,
):
    """Сериализатор для детальной информации о заявке."""

    department_name = serializers.CharField(
        source="department.name", read_only=True
    )
    processing_department_name = serializers.CharField(
        source="processing_department.name", read_only=True, allow_null=True
    )
    requestor_name = serializers.CharField(
        source="requestor.get_full_name", read_only=True
    )
    requestor_email = serializers.CharField(
        source="requestor.email", read_only=True
    )
    executor_name = serializers.CharField(
        source="executor.get_full_name", read_only=True, allow_null=True
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    urgency_display = serializers.CharField(
        source="get_urgency_display", read_only=True
    )
    fulfillment_status_display = serializers.CharField(
        source="get_fulfillment_status_display", read_only=True
    )
    total_cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, read_only=True
    )
    items = ProcurementItemSerializer(many=True, read_only=True)
    approvals = ApprovalSerializer(many=True, read_only=True)
    required_approval_priorities = serializers.ListField(
        source="get_required_approval_priorities", read_only=True
    )
    is_editable = serializers.BooleanField(read_only=True)
    comments_count = serializers.IntegerField(read_only=True, default=0)
    can_current_user_approve = serializers.SerializerMethodField()

    @extend_schema_field(serializers.BooleanField())
    def get_can_current_user_approve(self, obj):
        request = self.context.get("request")
        user = getattr(request, "user", None)
        return ProcurementApprovalResolver.user_can_approve(user, obj)

    class Meta:
        model = ProcurementRequest
        fields = [
            "id",
            "title",
            "description",
            "department",
            "department_name",
            "processing_department",
            "processing_department_name",
            "requestor",
            "requestor_name",
            "requestor_email",
            "executor",
            "executor_name",
            "status",
            "status_display",
            "urgency",
            "urgency_display",
            "fulfillment_status",
            "fulfillment_status_display",
            "total_cost",
            "actual_cost",
            "next_expected_delivery_date",
            "items_total_count",
            "items_received_count",
            "items_problem_count",
            "items_pending_count",
            "total_requested_quantity",
            "total_ordered_quantity",
            "total_received_quantity",
            "items",
            "approvals",
            "required_approval_priorities",
            "is_editable",
            "comments_count",
            "can_current_user_approve",
            "created_at",
            "updated_at",
            "submitted_at",
            "started_at",
            "completed_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "submitted_at",
            "started_at",
            "completed_at",
            "is_editable",
            "total_cost",
            "next_expected_delivery_date",
            "items_total_count",
            "items_received_count",
            "items_problem_count",
            "items_pending_count",
            "total_requested_quantity",
            "total_ordered_quantity",
            "total_received_quantity",
            "executor_name",
            "fulfillment_status",
            "processing_department_name",
            "fulfillment_status_display",
            "comments_count",
            "can_current_user_approve",
        ]


class ProcurementRequestCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания заявки с позициями."""

    description = serializers.CharField(
        required=False,
        allow_blank=True,
    )
    items = ProcurementItemCreateSerializer(many=True, required=False)

    class Meta:
        model = ProcurementRequest
        fields = [
            "id",
            "title",
            "description",
            "department",
            "processing_department",
            "requestor",
            "urgency",
            "items",
            "status",
            "created_at",
        ]
        read_only_fields = ["id", "requestor", "status", "created_at"]

    def validate(self, attrs):
        if (
            not attrs.get("processing_department")
            and not attrs.get("description", "").strip()
        ):
            raise serializers.ValidationError(
                {"description": "Укажите описание и обоснование."}
            )
        return attrs

    def create(self, validated_data):
        """Создать заявку с позициями."""
        items_data = validated_data.pop("items", [])
        request = self.context["request"]
        has_processing_department = bool(
            validated_data.get("processing_department")
        )

        if has_processing_department:
            validated_data["status"] = ProcurementStatus.WAITING

        procurement_request = ProcurementRequest(
            requestor=request.user,
            **validated_data,
        )
        procurement_request._notification_actor = request.user
        procurement_request.save()

        # Создаем позиции (если они переданы)
        for item_data in items_data:
            initial_comment = item_data.pop("initial_comment", "").strip()
            item = ProcurementItem.objects.create(
                request=procurement_request, **item_data
            )
            if initial_comment:
                comments_helpers.create_comment(
                    obj=item,
                    author=request.user,
                    content=initial_comment,
                )

        return procurement_request


class EquipmentCategorySerializer(serializers.ModelSerializer):
    """Сериализатор для категорий оборудования."""

    full_path = serializers.CharField(read_only=True)
    children_count = serializers.SerializerMethodField()

    class Meta:
        model = EquipmentCategory
        fields = [
            "id",
            "name",
            "parent",
            "description",
            "icon",
            "full_path",
            "children_count",
            "created_at",
        ]
        read_only_fields = ["id", "created_at", "full_path"]

    @extend_schema_field(serializers.IntegerField())
    def get_children_count(self, obj):
        """Количество подкатегорий."""
        return obj.children.count()


class BudgetSerializer(serializers.ModelSerializer):
    """Сериализатор бюджета отдела."""

    department_name = serializers.CharField(
        source="department.name", read_only=True
    )
    remaining_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    reserved_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    available_amount = serializers.DecimalField(
        max_digits=14, decimal_places=2, read_only=True
    )
    utilization_percentage = serializers.DecimalField(
        max_digits=5, decimal_places=2, read_only=True
    )

    class Meta:
        model = Budget
        fields = [
            "id",
            "department",
            "department_name",
            "year",
            "quarter",
            "allocated_amount",
            "spent_amount",
            "remaining_amount",
            "reserved_amount",
            "available_amount",
            "utilization_percentage",
            "created_at",
            "updated_at",
        ]
        read_only_fields = fields


class EquipmentListSerializer(serializers.ModelSerializer):
    """Сериализатор для списка оборудования."""

    category_name = serializers.CharField(
        source="category.name", read_only=True
    )
    category_icon = serializers.CharField(
        source="category.icon", read_only=True, default="bi-box-seam"
    )
    department_name = serializers.CharField(
        source="department.name", read_only=True
    )
    responsible_name = serializers.CharField(
        source="responsible_person.get_full_name", read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    is_under_warranty = serializers.BooleanField(read_only=True)
    comments_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Equipment
        fields = [
            "id",
            "name",
            "inventory_number",
            "serial_number",
            "category",
            "category_name",
            "category_icon",
            "status",
            "status_display",
            "department",
            "department_name",
            "responsible_person",
            "responsible_name",
            "location",
            "purchase_date",
            "purchase_cost",
            "notes",
            "is_under_warranty",
            "comments_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "inventory_number",
            "category_name",
            "category_icon",
            "department_name",
            "responsible_name",
            "status_display",
            "is_under_warranty",
            "comments_count",
            "created_at",
            "updated_at",
        ]

    def create(self, validated_data):
        """Автоматическая генерация инвентарного номера при создании."""
        import re
        from datetime import datetime

        year = datetime.now().year
        prefix = f"INV-{year}-"

        # Находим максимальный номер с текущим префиксом
        last_equipment = (
            Equipment.objects.filter(inventory_number__startswith=prefix)
            .order_by("-inventory_number")
            .first()
        )

        if last_equipment:
            match = re.search(r"(\d+)$", last_equipment.inventory_number)
            if match:
                next_num = int(match.group(1)) + 1
            else:
                next_num = 1
        else:
            next_num = 1

        validated_data["inventory_number"] = f"{prefix}{next_num:04d}"
        return super().create(validated_data)

    def _get_user_permission_level(self, user):
        """Определяет уровень прав пользователя.

        Возвращает:
            'full' - админ/модельные права
                (свободный выбор отдела/ответственного)
            'dept_head' - начальник отдела
                (свой отдел, выбор ответственного)
            'scoped' - скоуп-право (свой отдел, ответственный = начальник)
            None - нет прав на создание
        """
        from api.v1.permissions import has_dept_perm
        from employees.constants import DeptPerm
        from employees.models import Department, EmployeeDepartment

        if not user or not user.is_authenticated:
            return None

        # Админ или модельные права = полный доступ
        if (
            user.is_staff
            or user.is_superuser
            or user.has_perm("procurement.add_equipment")
        ):
            return "full"

        # Проверяем, является ли начальником какого-то отдела
        headed_depts = Department.objects.filter(head_id=user.id)
        if headed_depts.exists():
            return "dept_head"

        # Проверяем скоуп-право в активных отделах
        user_dept_links = EmployeeDepartment.objects.filter(
            employee_id=user.id, is_active=True
        ).select_related("department", "role")

        for link in user_dept_links:
            if has_dept_perm(
                user, link.department_id, DeptPerm.MANAGE_EQUIPMENT
            ):
                return "scoped"

        return None

    def _get_user_allowed_departments(self, user, perm_level):
        """Возвращает отделы, где пользователь может создать оборудование."""
        from employees.models import Department, EmployeeDepartment

        if perm_level == "full":
            return list(Department.objects.all())

        if perm_level == "dept_head":
            return list(Department.objects.filter(head_id=user.id))

        if perm_level == "scoped":
            from api.v1.permissions import has_dept_perm
            from employees.constants import DeptPerm

            result = []
            user_dept_links = EmployeeDepartment.objects.filter(
                employee_id=user.id, is_active=True
            ).select_related("department")

            for link in user_dept_links:
                if has_dept_perm(
                    user, link.department_id, DeptPerm.MANAGE_EQUIPMENT
                ):
                    result.append(link.department)
            return result

        return []

    def validate(self, attrs):
        """Проверка и автозаполнение полей в зависимости от прав.

        Уровни прав:
                - full (админ/модельные права): свободный выбор отдела
                    и ответственного
                - dept_head (начальник): только свой отдел,
                    выбор ответственного из отдела
        - scoped (скоуп-право): только свой отдел, ответственный = начальник
        """
        request = self.context.get("request")
        user = request.user if request else None

        # При update (есть instance) используем облегчённую валидацию
        if self.instance is not None:
            return self._validate_update(attrs, user)

        # Создание — полная проверка прав
        perm_level = self._get_user_permission_level(user)

        # Проверяем отдел
        department = attrs.get("department")

        if perm_level == "full":
            # Полный доступ — можно указать любой отдел
            pass

        elif perm_level == "dept_head":
            # Начальник — только свои отделы
            allowed_depts = self._get_user_allowed_departments(user, perm_level)
            allowed_ids = [d.id for d in allowed_depts]

            if department and department.id not in allowed_ids:
                raise serializers.ValidationError(
                    {
                        "department": "Вы можете создавать оборудование "
                        "только в своём отделе."
                    }
                )

            # Если отдел не указан — берём первый
            if not department and allowed_depts:
                attrs["department"] = allowed_depts[0]
                department = allowed_depts[0]

            # Ответственный по умолчанию — сам начальник
            resp = attrs.get("responsible_person")
            if resp is None:
                attrs["responsible_person"] = user

        elif perm_level == "scoped":
            # Скоуп-право — только свой отдел, ответственный = начальник
            allowed_depts = self._get_user_allowed_departments(user, perm_level)
            allowed_ids = [d.id for d in allowed_depts]

            if department and department.id not in allowed_ids:
                raise serializers.ValidationError(
                    {
                        "department": "Вы можете создавать оборудование "
                        "только в своём отделе."
                    }
                )

            # Если отдел не указан — берём первый
            if not department and allowed_depts:
                attrs["department"] = allowed_depts[0]
                department = allowed_depts[0]

            # Ответственный ВСЕГДА = начальник отдела (без выбора)
            if department and department.head:
                attrs["responsible_person"] = department.head
            else:
                attrs["responsible_person"] = None

        else:
            # Нет прав — ошибка
            raise serializers.ValidationError(
                {"non_field_errors": "У вас нет прав на создание оборудования."}
            )

        # Валидация ответственного
        return self._validate_responsible_in_department(attrs)

    def _validate_update(self, attrs, user):
        """Валидация при обновлении (облегчённая)."""
        # При update не проверяем права создания,
        # только валидацию ответственного если он меняется
        department = attrs.get("department", self.instance.department)
        responsible = attrs.get("responsible_person")

        # Если меняется ответственный — проверяем принадлежность к отделу
        if responsible is not None:
            attrs["department"] = department  # Для валидации
            attrs["responsible_person"] = responsible
            return self._validate_responsible_in_department(attrs)

        return attrs

    def _validate_responsible_in_department(self, attrs):
        """Проверяет, что ответственный состоит в отделе оборудования."""
        from employees.models import EmployeeDepartment

        department = attrs.get("department")
        responsible = attrs.get("responsible_person")

        if department and responsible:
            # Проверяем, что ответственный в этом отделе
            is_in_dept = (
                # Он начальник отдела
                department.head_id == responsible.id
                or
                # Или состоит в отделе
                EmployeeDepartment.objects.filter(
                    employee_id=responsible.id,
                    department_id=department.id,
                    is_active=True,
                ).exists()
            )

            if not is_in_dept:
                raise serializers.ValidationError(
                    {
                        "responsible_person": (
                            "Ответственный должен состоять в том же отделе, "
                            "что и оборудование."
                        )
                    }
                )

        return attrs


class EquipmentDetailSerializer(serializers.ModelSerializer):
    """Сериализатор для детальной информации об оборудовании."""

    category_name = serializers.CharField(
        source="category.name", read_only=True
    )
    department_name = serializers.CharField(
        source="department.name", read_only=True
    )
    responsible_name = serializers.CharField(
        source="responsible_person.get_full_name", read_only=True
    )
    status_display = serializers.CharField(
        source="get_status_display", read_only=True
    )
    is_under_warranty = serializers.BooleanField(read_only=True)
    maintenance_count = serializers.SerializerMethodField()

    class Meta:
        model = Equipment
        fields = [
            "id",
            "name",
            "inventory_number",
            "serial_number",
            "category",
            "category_name",
            "status",
            "status_display",
            "department",
            "department_name",
            "responsible_person",
            "responsible_name",
            "location",
            "purchase_date",
            "warranty_until",
            "is_under_warranty",
            "purchase_cost",
            "notes",
            "maintenance_count",
            "created_at",
            "updated_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "updated_at",
            "is_under_warranty",
            "maintenance_count",
        ]

    @extend_schema_field(serializers.IntegerField())
    def get_maintenance_count(self, obj):
        """Количество записей обслуживания."""
        return obj.maintenance_history.count()


class MaintenanceRecordSerializer(serializers.ModelSerializer):
    """Сериализатор для записей обслуживания."""

    equipment_name = serializers.CharField(
        source="equipment.name", read_only=True
    )
    equipment_inventory = serializers.CharField(
        source="equipment.inventory_number", read_only=True
    )
    performed_by_name = serializers.CharField(
        source="performed_by.get_full_name", read_only=True
    )
    type_display = serializers.CharField(
        source="get_type_display", read_only=True
    )

    class Meta:
        model = MaintenanceRecord
        fields = [
            "id",
            "equipment",
            "equipment_name",
            "equipment_inventory",
            "date",
            "type",
            "type_display",
            "description",
            "cost",
            "performed_by",
            "performed_by_name",
            "next_maintenance_date",
            "created_at",
        ]
        read_only_fields = [
            "id",
            "created_at",
            "equipment_name",
            "equipment_inventory",
            "performed_by_name",
            "type_display",
        ]


class SupplierSerializer(serializers.ModelSerializer):
    """Сериализатор для поставщиков."""

    class Meta:
        model = Supplier
        fields = [
            "id",
            "name",
            "contact_person",
            "phone",
            "email",
            "address",
            "website",
            "inn",
            "rating",
            "is_active",
            "notes",
            "created_at",
            "updated_at",
        ]
        read_only_fields = ["id", "created_at", "updated_at"]


class ProcurementOverviewStatsSerializer(serializers.Serializer):
    total_requests = serializers.IntegerField()
    pending_requests = serializers.IntegerField()
    approved_this_month = serializers.IntegerField()
    completed_this_month = serializers.IntegerField()
    total_spent_this_year = serializers.CharField()
    by_status = serializers.DictField(child=serializers.IntegerField())
    by_urgency = serializers.DictField(child=serializers.IntegerField())


class ProcurementDepartmentStatsSerializer(serializers.Serializer):
    department = serializers.DictField()
    total_requests = serializers.IntegerField()
    total_spent = serializers.CharField()
