"""
Сериализаторы для модуля закупок.
"""

from rest_framework import serializers

from .models import (
    Approval,
    Budget,
    Equipment,
    EquipmentCategory,
    MaintenanceRecord,
    ProcurementItem,
    ProcurementRequest,
    Supplier,
)


class ProcurementItemSerializer(serializers.ModelSerializer):
    """Сериализатор для позиций заявки."""

    total_price = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = ProcurementItem
        fields = [
            'id',
            'request',
            'name',
            'description',
            'quantity',
            'unit',
            'estimated_unit_price',
            'total_price',
            'supplier_info',
            'equipment',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'total_price']


class ProcurementItemCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания позиций (без request)."""

    class Meta:
        model = ProcurementItem
        fields = [
            'name',
            'description',
            'quantity',
            'unit',
            'estimated_unit_price',
            'supplier_info',
        ]


class ApprovalSerializer(serializers.ModelSerializer):
    """Сериализатор для согласований."""

    approver_name = serializers.CharField(
        source='approver.get_full_name',
        read_only=True
    )
    role_display = serializers.CharField(
        source='get_role_display',
        read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )

    class Meta:
        model = Approval
        fields = [
            'id',
            'request',
            'approver',
            'approver_name',
            'role',
            'role_display',
            'status',
            'status_display',
            'comment',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
            'approver_name',
            'role_display',
            'status_display',
        ]


class ProcurementRequestListSerializer(serializers.ModelSerializer):
    """Сериализатор для списка заявок (краткий)."""

    department_name = serializers.CharField(
        source='department.name',
        read_only=True
    )
    requestor_name = serializers.CharField(
        source='requestor.get_full_name',
        read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    urgency_display = serializers.CharField(
        source='get_urgency_display',
        read_only=True
    )
    items_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = ProcurementRequest
        fields = [
            'id',
            'title',
            'department',
            'department_name',
            'requestor',
            'requestor_name',
            'status',
            'status_display',
            'urgency',
            'urgency_display',
            'estimated_cost',
            'items_count',
            'created_at',
            'submitted_at',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'submitted_at',
            'department_name',
            'requestor_name',
            'status_display',
            'urgency_display',
            'items_count',
        ]


class ProcurementRequestDetailSerializer(serializers.ModelSerializer):
    """Сериализатор для детальной информации о заявке."""

    department_name = serializers.CharField(
        source='department.name',
        read_only=True
    )
    requestor_name = serializers.CharField(
        source='requestor.get_full_name',
        read_only=True
    )
    requestor_email = serializers.CharField(
        source='requestor.email',
        read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    urgency_display = serializers.CharField(
        source='get_urgency_display',
        read_only=True
    )
    items = ProcurementItemSerializer(many=True, read_only=True)
    approvals = ApprovalSerializer(many=True, read_only=True)
    required_approvals = serializers.ListField(
        source='get_required_approvals',
        read_only=True
    )
    is_editable = serializers.BooleanField(read_only=True)
    budget_available = serializers.SerializerMethodField()

    class Meta:
        model = ProcurementRequest
        fields = [
            'id',
            'title',
            'description',
            'department',
            'department_name',
            'requestor',
            'requestor_name',
            'requestor_email',
            'status',
            'status_display',
            'urgency',
            'urgency_display',
            'estimated_cost',
            'actual_cost',
            'items',
            'approvals',
            'required_approvals',
            'is_editable',
            'budget_available',
            'created_at',
            'updated_at',
            'submitted_at',
            'completed_at',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
            'submitted_at',
            'completed_at',
            'is_editable',
            'budget_available',
        ]

    def get_budget_available(self, obj):
        """Получить информацию о доступности бюджета."""
        available, remaining = obj.check_budget_available()
        return {
            'available': available,
            'remaining': float(remaining),
        }


class ProcurementRequestCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания заявки с позициями."""

    items = ProcurementItemCreateSerializer(many=True)

    class Meta:
        model = ProcurementRequest
        fields = [
            'id',
            'title',
            'description',
            'department',
            'requestor',
            'urgency',
            'estimated_cost',
            'items',
            'status',
            'created_at',
        ]
        read_only_fields = ['id', 'requestor', 'status', 'created_at']

    def create(self, validated_data):
        """Создать заявку с позициями."""
        items_data = validated_data.pop('items')
        request = self.context['request']

        # Создаем заявку
        procurement_request = ProcurementRequest.objects.create(
            requestor=request.user,
            **validated_data
        )

        # Создаем позиции
        for item_data in items_data:
            ProcurementItem.objects.create(
                request=procurement_request,
                **item_data
            )

        return procurement_request


class EquipmentCategorySerializer(serializers.ModelSerializer):
    """Сериализатор для категорий оборудования."""

    full_path = serializers.CharField(read_only=True)
    children_count = serializers.SerializerMethodField()

    class Meta:
        model = EquipmentCategory
        fields = [
            'id',
            'name',
            'parent',
            'description',
            'icon',
            'full_path',
            'children_count',
            'created_at',
        ]
        read_only_fields = ['id', 'created_at', 'full_path']

    def get_children_count(self, obj):
        """Количество подкатегорий."""
        return obj.children.count()


class EquipmentListSerializer(serializers.ModelSerializer):
    """Сериализатор для списка оборудования."""

    category_name = serializers.CharField(
        source='category.name',
        read_only=True
    )
    department_name = serializers.CharField(
        source='department.name',
        read_only=True
    )
    responsible_name = serializers.CharField(
        source='responsible_person.get_full_name',
        read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    is_under_warranty = serializers.BooleanField(read_only=True)

    class Meta:
        model = Equipment
        fields = [
            'id',
            'name',
            'inventory_number',
            'category',
            'category_name',
            'status',
            'status_display',
            'department',
            'department_name',
            'responsible_person',
            'responsible_name',
            'purchase_date',
            'purchase_cost',
            'is_under_warranty',
        ]
        read_only_fields = [
            'id',
            'category_name',
            'department_name',
            'responsible_name',
            'status_display',
            'is_under_warranty',
        ]


class EquipmentDetailSerializer(serializers.ModelSerializer):
    """Сериализатор для детальной информации об оборудовании."""

    category_name = serializers.CharField(
        source='category.name',
        read_only=True
    )
    department_name = serializers.CharField(
        source='department.name',
        read_only=True
    )
    responsible_name = serializers.CharField(
        source='responsible_person.get_full_name',
        read_only=True
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    is_under_warranty = serializers.BooleanField(read_only=True)
    maintenance_count = serializers.SerializerMethodField()

    class Meta:
        model = Equipment
        fields = [
            'id',
            'name',
            'inventory_number',
            'serial_number',
            'category',
            'category_name',
            'status',
            'status_display',
            'department',
            'department_name',
            'responsible_person',
            'responsible_name',
            'location',
            'purchase_date',
            'warranty_until',
            'is_under_warranty',
            'purchase_cost',
            'notes',
            'maintenance_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
            'is_under_warranty',
            'maintenance_count',
        ]

    def get_maintenance_count(self, obj):
        """Количество записей обслуживания."""
        return obj.maintenance_history.count()


class MaintenanceRecordSerializer(serializers.ModelSerializer):
    """Сериализатор для записей обслуживания."""

    equipment_name = serializers.CharField(
        source='equipment.name',
        read_only=True
    )
    equipment_inventory = serializers.CharField(
        source='equipment.inventory_number',
        read_only=True
    )
    performed_by_name = serializers.CharField(
        source='performed_by.get_full_name',
        read_only=True
    )
    type_display = serializers.CharField(
        source='get_type_display',
        read_only=True
    )

    class Meta:
        model = MaintenanceRecord
        fields = [
            'id',
            'equipment',
            'equipment_name',
            'equipment_inventory',
            'date',
            'type',
            'type_display',
            'description',
            'cost',
            'performed_by',
            'performed_by_name',
            'next_maintenance_date',
            'created_at',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'equipment_name',
            'equipment_inventory',
            'performed_by_name',
            'type_display',
        ]


class BudgetSerializer(serializers.ModelSerializer):
    """Сериализатор для бюджетов."""

    department_name = serializers.CharField(
        source='department.name',
        read_only=True
    )
    remaining_amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True
    )
    utilization_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        read_only=True
    )
    quarter_display = serializers.SerializerMethodField()

    class Meta:
        model = Budget
        fields = [
            'id',
            'department',
            'department_name',
            'year',
            'quarter',
            'quarter_display',
            'allocated_amount',
            'spent_amount',
            'remaining_amount',
            'utilization_percentage',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
            'remaining_amount',
            'utilization_percentage',
        ]

    def get_quarter_display(self, obj):
        """Отображение квартала."""
        return f"Q{obj.quarter} {obj.year}"


class SupplierSerializer(serializers.ModelSerializer):
    """Сериализатор для поставщиков."""

    class Meta:
        model = Supplier
        fields = [
            'id',
            'name',
            'contact_person',
            'phone',
            'email',
            'address',
            'website',
            'inn',
            'rating',
            'is_active',
            'notes',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
