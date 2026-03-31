"""
Сериализаторы для модуля закупок.
"""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers

from procurement.constants import get_default_approval_step_name
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
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    step_label = serializers.SerializerMethodField()

    @extend_schema_field(serializers.CharField())
    def get_step_label(self, obj):
        return obj.step_name or get_default_approval_step_name(obj.priority)

    class Meta:
        model = Approval
        fields = [
            'id',
            'request',
            'approver',
            'approver_name',
            'priority',
            'step_name',
            'step_label',
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
            'step_name',
            'step_label',
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
    total_cost = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True
    )
    executor_name = serializers.CharField(
        source='executor.get_full_name',
        read_only=True,
        allow_null=True
    )

    class Meta:
        model = ProcurementRequest
        fields = [
            'id',
            'title',
            'department',
            'department_name',
            'requestor',
            'requestor_name',
            'executor',
            'executor_name',
            'status',
            'status_display',
            'urgency',
            'urgency_display',
            'total_cost',
            'items_count',
            'created_at',
            'submitted_at',
            'started_at',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'submitted_at',
            'started_at',
            'department_name',
            'requestor_name',
            'executor_name',
            'status_display',
            'urgency_display',
            'items_count',
            'total_cost',
        ]

    def update(self, instance, validated_data):
        """
        При обновлении заявки запрещаем изменение requestor и department.
        Эти поля игнорируются при обновлении.
        """
        # Игнорируем попытки изменить requestor
        validated_data.pop('requestor', None)
        # Игнорируем попытки изменить department
        validated_data.pop('department', None)
        return super().update(instance, validated_data)


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
    executor_name = serializers.CharField(
        source='executor.get_full_name',
        read_only=True,
        allow_null=True
    )
    status_display = serializers.CharField(
        source='get_status_display',
        read_only=True
    )
    urgency_display = serializers.CharField(
        source='get_urgency_display',
        read_only=True
    )
    total_cost = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        read_only=True
    )
    items = ProcurementItemSerializer(many=True, read_only=True)
    approvals = ApprovalSerializer(many=True, read_only=True)
    required_approval_priorities = serializers.ListField(
        source='get_required_approval_priorities',
        read_only=True
    )
    is_editable = serializers.BooleanField(read_only=True)

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
            'executor',
            'executor_name',
            'status',
            'status_display',
            'urgency',
            'urgency_display',
            'total_cost',
            'actual_cost',
            'items',
            'approvals',
            'required_approval_priorities',
            'is_editable',
            'created_at',
            'updated_at',
            'submitted_at',
            'started_at',
            'completed_at',
        ]
        read_only_fields = [
            'id',
            'created_at',
            'updated_at',
            'submitted_at',
            'started_at',
            'completed_at',
            'is_editable',
            'total_cost',
            'executor_name',
        ]


class ProcurementRequestCreateSerializer(serializers.ModelSerializer):
    """Сериализатор для создания заявки с позициями."""

    items = ProcurementItemCreateSerializer(many=True, required=False)

    class Meta:
        model = ProcurementRequest
        fields = [
            'id',
            'title',
            'description',
            'department',
            'requestor',
            'urgency',
            'items',
            'status',
            'created_at',
        ]
        read_only_fields = ['id', 'requestor', 'status', 'created_at']

    def create(self, validated_data):
        """Создать заявку с позициями."""
        items_data = validated_data.pop('items', [])
        request = self.context['request']

        # Создаем заявку
        procurement_request = ProcurementRequest.objects.create(
            requestor=request.user,
            **validated_data
        )

        # Создаем позиции (если они переданы)
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

    @extend_schema_field(serializers.IntegerField())
    def get_children_count(self, obj):
        """Количество подкатегорий."""
        return obj.children.count()


class BudgetSerializer(serializers.ModelSerializer):
    """Сериализатор бюджета отдела."""

    department_name = serializers.CharField(
        source='department.name',
        read_only=True
    )
    remaining_amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True
    )
    reserved_amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True
    )
    available_amount = serializers.DecimalField(
        max_digits=14,
        decimal_places=2,
        read_only=True
    )
    utilization_percentage = serializers.DecimalField(
        max_digits=5,
        decimal_places=2,
        read_only=True
    )

    class Meta:
        model = Budget
        fields = [
            'id',
            'department',
            'department_name',
            'year',
            'quarter',
            'allocated_amount',
            'spent_amount',
            'remaining_amount',
            'reserved_amount',
            'available_amount',
            'utilization_percentage',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields


class EquipmentListSerializer(serializers.ModelSerializer):
    """Сериализатор для списка оборудования."""

    category_name = serializers.CharField(
        source='category.name',
        read_only=True
    )
    category_icon = serializers.CharField(
        source='category.icon',
        read_only=True,
        default='bi-box-seam'
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
    comments_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = Equipment
        fields = [
            'id',
            'name',
            'inventory_number',
            'serial_number',
            'category',
            'category_name',
            'category_icon',
            'status',
            'status_display',
            'department',
            'department_name',
            'responsible_person',
            'responsible_name',
            'location',
            'purchase_date',
            'purchase_cost',
            'notes',
            'is_under_warranty',
            'comments_count',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'inventory_number',
            'category_name',
            'category_icon',
            'department_name',
            'responsible_name',
            'status_display',
            'is_under_warranty',
            'comments_count',
            'created_at',
            'updated_at',
        ]

    def create(self, validated_data):
        """Автоматическая генерация инвентарного номера при создании."""
        import re
        from datetime import datetime

        year = datetime.now().year
        prefix = f"INV-{year}-"

        # Находим максимальный номер с текущим префиксом
        last_equipment = Equipment.objects.filter(
            inventory_number__startswith=prefix
        ).order_by('-inventory_number').first()

        if last_equipment:
            match = re.search(r'(\d+)$', last_equipment.inventory_number)
            if match:
                next_num = int(match.group(1)) + 1
            else:
                next_num = 1
        else:
            next_num = 1

        validated_data['inventory_number'] = f"{prefix}{next_num:04d}"
        return super().create(validated_data)

    def _get_user_permission_level(self, user):
        """Определяет уровень прав пользователя.

        Возвращает:
            'full' - админ/модельные права (свободный выбор отдела/ответственного)
            'dept_head' - начальник отдела (свой отдел, выбор ответственного)
            'scoped' - скоуп-право (свой отдел, ответственный = начальник)
            None - нет прав на создание
        """
        from api.v1.permissions import has_dept_perm
        from employees.constants import DeptPerm
        from employees.models import Department, EmployeeDepartment

        if not user or not user.is_authenticated:
            return None

        # Админ или модельные права = полный доступ
        if (user.is_staff or user.is_superuser or
                user.has_perm('procurement.add_equipment')):
            return 'full'

        # Проверяем, является ли начальником какого-то отдела
        headed_depts = Department.objects.filter(head_id=user.id)
        if headed_depts.exists():
            return 'dept_head'

        # Проверяем скоуп-право в активных отделах
        user_dept_links = EmployeeDepartment.objects.filter(
            employee_id=user.id,
            is_active=True
        ).select_related('department', 'role')

        for link in user_dept_links:
            if has_dept_perm(
                user, link.department_id, DeptPerm.MANAGE_EQUIPMENT
            ):
                return 'scoped'

        return None

    def _get_user_allowed_departments(self, user, perm_level):
        """Возвращает отделы, где пользователь может создать оборудование."""
        from employees.models import Department, EmployeeDepartment

        if perm_level == 'full':
            return list(Department.objects.all())

        if perm_level == 'dept_head':
            return list(Department.objects.filter(head_id=user.id))

        if perm_level == 'scoped':
            from api.v1.permissions import has_dept_perm
            from employees.constants import DeptPerm

            result = []
            user_dept_links = EmployeeDepartment.objects.filter(
                employee_id=user.id,
                is_active=True
            ).select_related('department')

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
        - full (админ/модельные права): свободный выбор отдела и ответственного
        - dept_head (начальник): только свой отдел, выбор ответственного из отдела
        - scoped (скоуп-право): только свой отдел, ответственный = начальник
        """
        request = self.context.get('request')
        user = request.user if request else None

        # При update (есть instance) используем облегчённую валидацию
        if self.instance is not None:
            return self._validate_update(attrs, user)

        # Создание — полная проверка прав
        perm_level = self._get_user_permission_level(user)

        # Проверяем отдел
        department = attrs.get('department')

        if perm_level == 'full':
            # Полный доступ — можно указать любой отдел
            pass

        elif perm_level == 'dept_head':
            # Начальник — только свои отделы
            allowed_depts = self._get_user_allowed_departments(
                user, perm_level
            )
            allowed_ids = [d.id for d in allowed_depts]

            if department and department.id not in allowed_ids:
                raise serializers.ValidationError({
                    'department': 'Вы можете создавать оборудование '
                                  'только в своём отделе.'
                })

            # Если отдел не указан — берём первый
            if not department and allowed_depts:
                attrs['department'] = allowed_depts[0]
                department = allowed_depts[0]

            # Ответственный по умолчанию — сам начальник
            resp = attrs.get('responsible_person')
            if resp is None:
                attrs['responsible_person'] = user

        elif perm_level == 'scoped':
            # Скоуп-право — только свой отдел, ответственный = начальник
            allowed_depts = self._get_user_allowed_departments(
                user, perm_level
            )
            allowed_ids = [d.id for d in allowed_depts]

            if department and department.id not in allowed_ids:
                raise serializers.ValidationError({
                    'department': 'Вы можете создавать оборудование '
                                  'только в своём отделе.'
                })

            # Если отдел не указан — берём первый
            if not department and allowed_depts:
                attrs['department'] = allowed_depts[0]
                department = allowed_depts[0]

            # Ответственный ВСЕГДА = начальник отдела (без выбора)
            if department and department.head:
                attrs['responsible_person'] = department.head
            else:
                attrs['responsible_person'] = None

        else:
            # Нет прав — ошибка
            raise serializers.ValidationError({
                'non_field_errors': 'У вас нет прав на создание оборудования.'
            })

        # Валидация ответственного
        return self._validate_responsible_in_department(attrs)

    def _validate_update(self, attrs, user):
        """Валидация при обновлении (облегчённая)."""
        # При update не проверяем права создания,
        # только валидацию ответственного если он меняется
        department = attrs.get('department', self.instance.department)
        responsible = attrs.get('responsible_person')

        # Если меняется ответственный — проверяем принадлежность к отделу
        if responsible is not None:
            attrs['department'] = department  # Для валидации
            attrs['responsible_person'] = responsible
            return self._validate_responsible_in_department(attrs)

        return attrs

    def _validate_responsible_in_department(self, attrs):
        """Проверяет, что ответственный состоит в отделе оборудования."""
        from employees.models import EmployeeDepartment

        department = attrs.get('department')
        responsible = attrs.get('responsible_person')

        if department and responsible:
            # Проверяем, что ответственный в этом отделе
            is_in_dept = (
                # Он начальник отдела
                department.head_id == responsible.id or
                # Или состоит в отделе
                EmployeeDepartment.objects.filter(
                    employee_id=responsible.id,
                    department_id=department.id,
                    is_active=True
                ).exists()
            )

            if not is_in_dept:
                raise serializers.ValidationError({
                    'responsible_person': (
                        'Ответственный должен состоять в том же отделе, '
                        'что и оборудование.'
                    )
                })

        return attrs


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

    @extend_schema_field(serializers.IntegerField())
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
