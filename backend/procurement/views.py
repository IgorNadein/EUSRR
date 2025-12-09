"""
ViewSets для API модуля закупок.
"""

from django.db.models import Q
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from .constants import ApprovalStatus, ProcurementStatus
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
from .permissions import (
    CanApproveProcurementRequest,
    CanCreateProcurementRequest,
    CanEditOwnProcurementRequest,
    CanManageBudget,
    CanManageEquipment,
    CanManageSupplier,
)
from .serializers import (
    BudgetSerializer,
    EquipmentCategorySerializer,
    EquipmentDetailSerializer,
    EquipmentListSerializer,
    MaintenanceRecordSerializer,
    ProcurementItemSerializer,
    ProcurementRequestCreateSerializer,
    ProcurementRequestDetailSerializer,
    ProcurementRequestListSerializer,
    SupplierSerializer,
)
from notifications.services import NotificationService


class ProcurementRequestViewSet(viewsets.ModelViewSet):
    """ViewSet для заявок на закупку."""

    queryset = ProcurementRequest.objects.select_related(
        'department', 'requestor'
    ).prefetch_related('items', 'approvals')
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ['status', 'urgency', 'department']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'estimated_cost', 'status']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """Выбрать сериализатор в зависимости от действия."""
        if self.action == 'create':
            return ProcurementRequestCreateSerializer
        elif self.action in ['retrieve', 'submit', 'approve', 'reject']:
            return ProcurementRequestDetailSerializer
        return ProcurementRequestListSerializer

    def get_permissions(self):
        """Выбрать права доступа в зависимости от действия."""
        if self.action == 'create':
            permission_classes = [CanCreateProcurementRequest]
        elif self.action in ['update', 'partial_update', 'destroy']:
            permission_classes = [CanEditOwnProcurementRequest]
        elif self.action in ['approve', 'reject']:
            permission_classes = [CanApproveProcurementRequest]
        else:
            permission_classes = [CanCreateProcurementRequest]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """Фильтровать заявки в зависимости от роли пользователя."""
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_superuser or user.is_staff:
            return queryset

        # Показываем: свои заявки + заявки отдела + где я approver
        return queryset.filter(
            Q(requestor=user) |
            Q(department__in=user.departments.all()) |
            Q(approvals__approver=user)
        ).distinct()

    @action(detail=True, methods=['post'])
    def submit(self, request, pk=None):
        """Отправить заявку на согласование."""
        procurement_request = self.get_object()

        # Проверки
        if procurement_request.requestor != request.user:
            return Response(
                {'error': 'Вы не можете отправить чужую заявку'},
                status=status.HTTP_403_FORBIDDEN
            )

        if not procurement_request.is_editable:
            return Response(
                {'error': 'Заявка уже отправлена на согласование'},
                status=status.HTTP_400_BAD_REQUEST
            )

        if procurement_request.items.count() == 0:
            return Response(
                {'error': 'Добавьте хотя бы одну позицию в заявку'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Проверка бюджета
        available, remaining = procurement_request.check_budget_available()
        if not available:
            return Response(
                {
                    'error': 'Недостаточно бюджета',
                    'remaining': float(remaining),
                    'required': float(procurement_request.estimated_cost),
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Меняем статус
        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()

        # Создаем записи согласований
        required_approvals = procurement_request.get_required_approvals()
        from procurement.constants import ApprovalRole

        created_approvals = []
        for role in required_approvals:
            # Определяем согласующего
            approver = None
            if role == ApprovalRole.DEPARTMENT_HEAD:
                approver = procurement_request.department.head
            elif role == ApprovalRole.FINANCE_MANAGER:
                # Найдем первого пользователя с правом на бюджеты
                from employees.models import Employee
                from django.db.models import Q
                approver = Employee.objects.filter(
                    is_active=True
                ).filter(
                    Q(groups__permissions__codename='change_budget') |
                    Q(user_permissions__codename='change_budget')
                ).distinct().first()
            elif role == ApprovalRole.DIRECTOR:
                # Найдем директора (суперпользователя)
                from employees.models import Employee
                approver = Employee.objects.filter(
                    is_superuser=True
                ).first()

            if approver:
                approval = Approval.objects.create(
                    request=procurement_request,
                    approver=approver,
                    role=role,
                    status=ApprovalStatus.PENDING
                )
                created_approvals.append(approval)

        # Отправляем уведомления согласующим через NotificationService
        for approval in created_approvals:
            NotificationService.create_notification(
                recipient=approval.approver,
                notification_type_code='procurement_pending_approval',
                title="Требуется согласование заявки",
                message=(
                    f'Заявка "{procurement_request.title}" '
                    f'ожидает вашего согласования. '
                    f'Сумма: {procurement_request.estimated_cost}₽'
                ),
                action_url=f'/procurement/requests/{procurement_request.id}/',
                send_immediately=True,
            )

        serializer = self.get_serializer(procurement_request)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Одобрить заявку."""
        procurement_request = self.get_object()

        # Проверяем права
        self.check_object_permissions(request, procurement_request)

        # Находим согласование текущего пользователя
        approval = procurement_request.approvals.filter(
            approver=request.user,
            status=ApprovalStatus.PENDING
        ).first()

        if not approval:
            return Response(
                {'error': 'У вас нет прав на согласование этой заявки'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Одобряем
        approval.status = ApprovalStatus.APPROVED
        approval.comment = request.data.get('comment', '')
        approval.save()

        # Отправляем уведомление о согласовании
        NotificationService.create_notification(
            recipient=procurement_request.requestor,
            notification_type_code='procurement_stage_approved',
            title="Этап согласования пройден",
            message=(
                f'{request.user.get_full_name()} одобрил '
                f'заявку "{procurement_request.title}".'
            ),
            action_url=f'/procurement/requests/{procurement_request.id}/',
            send_immediately=True,
        )

        # Проверяем, все ли одобрили
        pending_approvals = procurement_request.approvals.filter(
            status=ApprovalStatus.PENDING
        ).count()

        if pending_approvals == 0:
            # Все одобрили - меняем статус заявки
            procurement_request.status = ProcurementStatus.APPROVED
            procurement_request.save()

            # Отправляем уведомление о полном одобрении
            NotificationService.create_notification(
                recipient=procurement_request.requestor,
                notification_type_code='procurement_approved',
                title="Заявка одобрена",
                message=(
                    f'Ваша заявка "{procurement_request.title}" '
                    f'была полностью одобрена. Можно приступать к закупке.'
                ),
                action_url=f'/procurement/requests/{procurement_request.id}/',
                send_immediately=True,
            )

        serializer = self.get_serializer(procurement_request)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Отклонить заявку."""
        procurement_request = self.get_object()

        # Проверяем права
        self.check_object_permissions(request, procurement_request)

        # Находим согласование текущего пользователя
        approval = procurement_request.approvals.filter(
            approver=request.user,
            status=ApprovalStatus.PENDING
        ).first()

        if not approval:
            return Response(
                {'error': 'У вас нет прав на согласование этой заявки'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Отклоняем
        approval.status = ApprovalStatus.REJECTED
        approval.comment = request.data.get('comment', '')
        approval.save()

        # Меняем статус заявки
        procurement_request.status = ProcurementStatus.REJECTED
        procurement_request.save()

        # Отправляем уведомление об отклонении
        NotificationService.create_notification(
            recipient=procurement_request.requestor,
            notification_type_code='procurement_rejected',
            title="Заявка отклонена",
            message=(
                f'{request.user.get_full_name()} отклонил '
                f'заявку "{procurement_request.title}". '
                f'Причина: {approval.comment}'
            ),
            action_url=f'/procurement/requests/{procurement_request.id}/',
            send_immediately=True,
        )

        serializer = self.get_serializer(procurement_request)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def my_requests(self, request):
        """Получить заявки текущего пользователя."""
        queryset = self.get_queryset().filter(requestor=request.user)
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def pending_approvals(self, request):
        """Получить заявки, ожидающие согласования текущим польз."""
        # Находим заявки где есть pending approval для текущего юзера
        queryset = self.get_queryset().filter(
            approvals__approver=request.user,
            approvals__status=ApprovalStatus.PENDING
        )
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class ProcurementItemViewSet(viewsets.ModelViewSet):
    """ViewSet для позиций заявок."""

    queryset = ProcurementItem.objects.select_related('request')
    serializer_class = ProcurementItemSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter]
    filterset_fields = ['request']
    search_fields = ['name', 'description']

    def get_permissions(self):
        """Только создатель заявки может редактировать позиции."""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            permission_classes = [CanEditOwnProcurementRequest]
        else:
            permission_classes = [CanCreateProcurementRequest]
        return [permission() for permission in permission_classes]


class EquipmentCategoryViewSet(viewsets.ModelViewSet):
    """ViewSet для категорий оборудования."""

    queryset = EquipmentCategory.objects.prefetch_related('children')
    serializer_class = EquipmentCategorySerializer
    filter_backends = [filters.SearchFilter, filters.OrderingFilter]
    search_fields = ['name', 'description']
    ordering = ['name']

    @action(detail=True, methods=['get'])
    def children(self, request, pk=None):
        """Получить подкатегории."""
        category = self.get_object()
        serializer = self.get_serializer(
            category.children.all(), many=True
        )
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def tree(self, request):
        """Получить дерево категорий."""
        # Получаем только корневые категории
        root_categories = self.get_queryset().filter(parent=None)
        serializer = self.get_serializer(root_categories, many=True)
        return Response(serializer.data)


class EquipmentViewSet(viewsets.ModelViewSet):
    """ViewSet для оборудования."""

    queryset = Equipment.objects.select_related(
        'category', 'department', 'responsible_person'
    )
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ['status', 'category', 'department']
    search_fields = [
        'name',
        'inventory_number',
        'serial_number',
        'location',
    ]
    ordering_fields = ['purchase_date', 'name']
    ordering = ['-purchase_date']

    def get_serializer_class(self):
        """Выбрать сериализатор."""
        if self.action == 'retrieve':
            return EquipmentDetailSerializer
        return EquipmentListSerializer

    def get_permissions(self):
        """Права доступа."""
        permission_classes = [CanManageEquipment]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['get'])
    def my_equipment(self, request):
        """Оборудование, за которое отвечает текущий пользователь."""
        queryset = self.get_queryset().filter(
            responsible_person=request.user
        )
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def warranty_expiring(self, request):
        """Оборудование с истекающей гарантией (< 30 дней)."""
        from datetime import date, timedelta
        threshold = date.today() + timedelta(days=30)

        queryset = self.get_queryset().filter(
            warranty_until__lte=threshold,
            warranty_until__gte=date.today()
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class MaintenanceRecordViewSet(viewsets.ModelViewSet):
    """ViewSet для записей обслуживания."""

    queryset = MaintenanceRecord.objects.select_related(
        'equipment', 'performed_by'
    )
    serializer_class = MaintenanceRecordSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.OrderingFilter,
    ]
    filterset_fields = ['equipment', 'type', 'performed_by']
    ordering_fields = ['date']
    ordering = ['-date']

    def perform_create(self, serializer):
        """При создании записи устанавливаем performed_by."""
        serializer.save(performed_by=self.request.user)


class BudgetViewSet(viewsets.ModelViewSet):
    """ViewSet для бюджетов."""

    queryset = Budget.objects.select_related('department')
    serializer_class = BudgetSerializer
    filter_backends = [DjangoFilterBackend, filters.OrderingFilter]
    filterset_fields = ['department', 'year', 'quarter']
    ordering_fields = ['year', 'quarter']
    ordering = ['-year', '-quarter']

    def get_permissions(self):
        """Права доступа."""
        permission_classes = [CanManageBudget]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """Фильтровать бюджеты."""
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_superuser or user.is_staff:
            return queryset

        # Руководители видят бюджеты своих отделов
        if user.led_departments.exists():
            return queryset.filter(
                department__in=user.led_departments.all()
            )

        return queryset.none()

    @action(detail=False, methods=['get'])
    def current_quarter(self, request):
        """Получить бюджеты текущего квартала."""
        from django.utils import timezone
        now = timezone.now()
        quarter = (now.month - 1) // 3 + 1

        queryset = self.get_queryset().filter(
            year=now.year,
            quarter=quarter
        )
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)


class SupplierViewSet(viewsets.ModelViewSet):
    """ViewSet для поставщиков."""

    queryset = Supplier.objects.all()
    serializer_class = SupplierSerializer
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ['is_active']
    search_fields = ['name', 'contact_person', 'inn']
    ordering_fields = ['name', 'rating']
    ordering = ['name']

    def get_permissions(self):
        """Права доступа."""
        permission_classes = [CanManageSupplier]
        return [permission() for permission in permission_classes]

    @action(detail=False, methods=['get'])
    def top_rated(self, request):
        """Получить поставщиков с лучшим рейтингом."""
        queryset = self.get_queryset().filter(
            is_active=True,
            rating__gte=4.0
        ).order_by('-rating')[:10]
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

