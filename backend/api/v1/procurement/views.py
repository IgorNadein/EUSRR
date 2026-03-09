"""
ViewSets для API модуля закупок.
"""

from decimal import Decimal

from django.db.models import Q
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from employees.models import Department
from procurement.constants import ApprovalStatus, ProcurementStatus, EquipmentStatus
from procurement.models import (
    Approval,
    Budget,
    Equipment,
    EquipmentCategory,
    EquipmentTransferLog,
    MaintenanceRecord,
    ProcurementItem,
    ProcurementRequest,
    Supplier,
)
from procurement.services import QRCodeGenerator
from .permissions import (
    CanApproveProcurementRequest,
    CanManageBudget,
    CanManageEquipment,
    CanManageProcurementRequest,
    CanManageSupplier,
)
from .serializers import (
    BudgetSerializer,
    BudgetDetailSerializer,
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
from notifications.signals import notify


class ProcurementRequestViewSet(viewsets.ModelViewSet):
    """ViewSet для заявок на закупку."""

    queryset = ProcurementRequest.objects.select_related(
        'department', 'requestor', 'executor'
    ).prefetch_related('items', 'approvals')
    filter_backends = [
        DjangoFilterBackend,
        filters.SearchFilter,
        filters.OrderingFilter,
    ]
    filterset_fields = ['status', 'urgency', 'department', 'executor']
    search_fields = ['title', 'description']
    ordering_fields = ['created_at', 'status']
    ordering = ['-created_at']

    def get_serializer_class(self):
        """Выбрать сериализатор в зависимости от действия."""
        if self.action == 'create':
            return ProcurementRequestCreateSerializer
        elif self.action in [
            'retrieve', 'submit', 'approve', 'reject',
            'start_work', 'complete', 'cancel'
        ]:
            return ProcurementRequestDetailSerializer
        return ProcurementRequestListSerializer

    def get_permissions(self):
        """Выбрать права доступа в зависимости от действия."""
        if self.action in ['approve', 'reject']:
            permission_classes = [CanApproveProcurementRequest]
        else:
            # Для create, update, delete и остальных действий
            permission_classes = [CanManageProcurementRequest]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """Фильтровать заявки в зависимости от роли пользователя и scope."""
        from datetime import timedelta
        from django.utils import timezone
        
        queryset = super().get_queryset()
        user = self.request.user
        scope = self.request.query_params.get('scope', None)
        period = self.request.query_params.get('period', None)

        # Обработка scope параметра
        if scope == 'mine':
            # Только мои заявки (где я автор)
            queryset = queryset.filter(requestor=user)
        elif scope == 'department':
            # Заявки моего отдела
            queryset = queryset.filter(department__in=user.departments.all())
        elif scope == 'my_work':
            # Заявки, которые я взял в работу (где я исполнитель)
            queryset = queryset.filter(executor=user)
        elif scope == 'available':
            # Доступные заявки - со статусом "Согласовано"
            queryset = queryset.filter(status='approved')
        elif scope == 'all':
            # Все заявки - применяем стандартную логику прав
            pass
        else:
            # Если scope не указан, применяем стандартную логику
            # Админы и пользователи с модельными правами видят все
            if user.is_superuser or user.is_staff:
                pass
            # Пользователи с любыми модельными правами на заявки видят все
            elif (user.has_perm('procurement.view_procurementrequest') or
                  user.has_perm('procurement.change_procurementrequest') or
                  user.has_perm('procurement.delete_procurementrequest')):
                pass
            else:
                # Показываем: свои заявки + заявки отдела + где я approver
                queryset = queryset.filter(
                    Q(requestor=user) |
                    Q(department__in=user.departments.all()) |
                    Q(approvals__approver=user)
                )
        
        # Фильтрация по периоду
        if period:
            now = timezone.now()
            if period == 'today':
                start_date = now.replace(hour=0, minute=0, second=0, microsecond=0)
                queryset = queryset.filter(created_at__gte=start_date)
            elif period == 'week':
                start_date = now - timedelta(days=7)
                queryset = queryset.filter(created_at__gte=start_date)
            elif period == 'month':
                start_date = now - timedelta(days=30)
                queryset = queryset.filter(created_at__gte=start_date)
            elif period == 'quarter':
                start_date = now - timedelta(days=90)
                queryset = queryset.filter(created_at__gte=start_date)

        return queryset.distinct()

    def _check_budget_alert(self, procurement_request):
        """Проверяет бюджет и отправляет алерт если низкий остаток."""
        department = procurement_request.department
        now = timezone.now()
        quarter = (now.month - 1) // 3 + 1
        
        try:
            budget = Budget.objects.get(
                department=department,
                year=now.year,
                quarter=quarter
            )
        except Budget.DoesNotExist:
            return  # Нет бюджета - не отправляем алерт
        
        # Пороговые значения для алертов
        LOW_BUDGET_THRESHOLD = Decimal('0.20')  # 20% остатка
        CRITICAL_BUDGET_THRESHOLD = Decimal('0.10')  # 10% остатка
        
        utilization = budget.utilization_percentage / 100
        remaining_ratio = 1 - utilization
        
        # Получаем руководителя отдела
        dept_head = department.head
        if not dept_head:
            return
        
        if remaining_ratio <= CRITICAL_BUDGET_THRESHOLD:
            # Критический уровень - менее 10%
            notify.send(
                sender=None,
                recipient=dept_head,
                verb='budget_critical',
                description=(
                    f'Бюджет отдела "{department.name}" почти исчерпан! '
                    f'Остаток: {budget.remaining_amount}₽ '
                    f'({remaining_ratio*100:.1f}%)'
                ),
                action_url='/procurement',
                data={'title': '⚠️ Критически низкий бюджет!'},
            )
        elif remaining_ratio <= LOW_BUDGET_THRESHOLD:
            # Низкий уровень - менее 20%
            notify.send(
                sender=None,
                recipient=dept_head,
                verb='budget_low',
                description=(
                    f'Бюджет отдела "{department.name}" снижается. '
                    f'Остаток: {budget.remaining_amount}₽ '
                    f'({remaining_ratio*100:.1f}%)'
                ),
                action_url='/procurement',
                data={'title': 'Низкий остаток бюджета'},
            )

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
                    'required': float(procurement_request.total_cost),
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

        # Уведомления согласующим отправит сигнал post_save(Approval, created=True)

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
        approval.save()  # Сигнал post_save(Approval) отправит уведомление

        # Проверяем, все ли одобрили
        pending_approvals = procurement_request.approvals.filter(
            status=ApprovalStatus.PENDING
        ).count()

        if pending_approvals == 0:
            # Все одобрили - меняем статус заявки
            # Сигнал post_save(ProcurementRequest) отправит уведомление requestor'у
            procurement_request.status = ProcurementStatus.APPROVED
            procurement_request.save()

            # Проверяем бюджет и отправляем алерт если низкий
            self._check_budget_alert(procurement_request)

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
        approval.save()  # Сигнал post_save(Approval) отправит уведомление

        # Меняем статус заявки; сигнал post_save(ProcurementRequest) уведомит requestor'а
        procurement_request.status = ProcurementStatus.REJECTED
        procurement_request.save()

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

    @action(detail=False, methods=['get'])
    def my_work(self, request):
        """Получить заявки, взятые текущим пользователем в работу."""
        queryset = self.filter_queryset(
            self.get_queryset().filter(executor=request.user)
        )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ProcurementRequestListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ProcurementRequestListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def available(self, request):
        """Получить одобренные заявки, доступные для взятия в работу."""
        queryset = self.filter_queryset(
            self.get_queryset().filter(
                status=ProcurementStatus.APPROVED,
                executor__isnull=True
            )
        )
        
        page = self.paginate_queryset(queryset)
        if page is not None:
            serializer = ProcurementRequestListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = ProcurementRequestListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def start_work(self, request, pk=None):
        """Начать работу над заявкой (перевод в статус IN_PROGRESS).
        
        Любой авторизованный пользователь может взять заявку в работу.
        TODO: Позже добавить проверку роли "Закупщик".
        """
        procurement_request = self.get_object()

        # Проверяем текущий статус
        if procurement_request.status != ProcurementStatus.APPROVED:
            return Response(
                {'error': 'Только одобренные заявки можно взять в работу'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Проверяем, что заявка ещё не взята кем-то
        if procurement_request.executor:
            return Response(
                {
                    'error': (
                        f'Заявка уже взята в работу пользователем '
                        f'{procurement_request.executor.get_full_name()}'
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Назначаем исполнителя и меняем статус
        # Сигнал post_save(ProcurementRequest) с IN_PROGRESS отправит уведомления
        procurement_request.executor = request.user
        procurement_request.started_at = timezone.now()
        procurement_request.status = ProcurementStatus.IN_PROGRESS
        procurement_request.save()

        serializer = self.get_serializer(procurement_request)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def complete(self, request, pk=None):
        """Завершить заявку (перевод в статус COMPLETED)."""
        procurement_request = self.get_object()

        # Только исполнитель может завершить заявку
        if procurement_request.executor != request.user:
            return Response(
                {'error': 'Только исполнитель заявки может завершить её'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Проверяем текущий статус
        if procurement_request.status != ProcurementStatus.IN_PROGRESS:
            return Response(
                {'error': 'Только заявки в работе можно завершить'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Меняем статус
        procurement_request.status = ProcurementStatus.COMPLETED
        procurement_request.completed_at = timezone.now()
        procurement_request.save()

        # Списываем бюджет отдела
        self._deduct_budget(procurement_request)
        # Сигнал post_save(ProcurementRequest) с COMPLETED отправит уведомления
        # requestor'у и согласующим

        serializer = self.get_serializer(procurement_request)
        return Response(serializer.data)

    def _deduct_budget(self, procurement_request):
        """Списывает сумму заявки из бюджета отдела."""
        department = procurement_request.department
        now = timezone.now()
        quarter = (now.month - 1) // 3 + 1
        
        # Используем фактическую сумму если есть, иначе общую стоимость позиций
        amount = (
            procurement_request.actual_cost or
            procurement_request.total_cost
        )
        if not amount or amount <= 0:
            return  # Нечего списывать
        
        try:
            budget = Budget.objects.get(
                department=department,
                year=now.year,
                quarter=quarter
            )
        except Budget.DoesNotExist:
            # Нет бюджета - создаём с нулём, чтобы зафиксировать траты
            budget = Budget.objects.create(
                department=department,
                year=now.year,
                quarter=quarter,
                allocated_amount=Decimal('0'),
                spent_amount=Decimal('0')
            )
        
        # Увеличиваем потраченную сумму
        budget.spent_amount = (budget.spent_amount or Decimal('0')) + amount
        budget.save()
        
        # Проверяем и отправляем алерт если бюджет низкий
        self._check_budget_alert(procurement_request)

    @action(detail=True, methods=['post'])
    def cancel(self, request, pk=None):
        """Отменить заявку."""
        procurement_request = self.get_object()

        # Только автор заявки может отменить её
        if procurement_request.requestor != request.user:
            return Response(
                {'error': 'Только автор заявки может отменить её'},
                status=status.HTTP_403_FORBIDDEN
            )

        # Нельзя отменить уже завершённую или отменённую заявку
        if procurement_request.status in [
            ProcurementStatus.COMPLETED,
            ProcurementStatus.CANCELLED,
        ]:
            return Response(
                {'error': 'Эту заявку нельзя отменить'},
                status=status.HTTP_400_BAD_REQUEST
            )

        reason = request.data.get('reason', '')

        # Сохраняем причину на экземпляре, чтобы сигнал мог её использовать
        procurement_request.cancellation_reason = reason or 'не указана'

        # Меняем статус; сигнал post_save(ProcurementRequest) с CANCELLED
        # уведомит согласующих с указанием причины
        procurement_request.status = ProcurementStatus.CANCELLED
        procurement_request.save()

        serializer = self.get_serializer(procurement_request)
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
        if self.action in [
            'create', 'update', 'partial_update', 'destroy',
            'create_equipment', 'link_equipment'
        ]:
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [CanManageProcurementRequest]
        return [permission() for permission in permission_classes]
    
    def perform_create(self, serializer):
        """Проверяем права при создании позиции.
        
        Логика соответствует CanManageProcurementRequest:
        - Админы/Staff могут добавлять в любые заявки в DRAFT
        - Модельные права (change_procurementrequest) → любые заявки в DRAFT
        - Автор заявки → свои заявки в DRAFT
        - Начальник отдела → заявки своего отдела в DRAFT
        """
        from rest_framework.exceptions import PermissionDenied
        
        procurement_request = serializer.validated_data.get('request')
        user = self.request.user
        
        # Проверяем, что заявка в DRAFT
        if not procurement_request.is_editable:
            raise PermissionDenied(
                "Нельзя добавлять позиции в заявку со статусом '{}'".format(
                    procurement_request.get_status_display()
                )
            )
        
        # Админы могут редактировать
        if user.is_superuser or user.is_staff:
            serializer.save()
            return
        
        # Модельные права
        if user.has_perm('procurement.change_procurementrequest'):
            serializer.save()
            return
        
        # Автор заявки
        if procurement_request.requestor == user:
            serializer.save()
            return
        
        # Начальник отдела
        if procurement_request.department.head == user:
            serializer.save()
            return
        
        # Нет прав
        raise PermissionDenied(
            "Вы не можете добавлять позиции в эту заявку"
        )
    
    def _check_item_edit_permission(self, item):
        """Проверка прав на редактирование позиции.
        
        Вынесена в отдельный метод для переиспользования.
        """
        from rest_framework.exceptions import PermissionDenied
        
        user = self.request.user
        procurement_request = item.request
        
        # Проверяем, что заявка в DRAFT
        if not procurement_request.is_editable:
            raise PermissionDenied(
                "Нельзя изменять позиции в заявке со статусом '{}'".format(
                    procurement_request.get_status_display()
                )
            )
        
        # Админы могут редактировать
        if user.is_superuser or user.is_staff:
            return True
        
        # Модельные права
        if user.has_perm('procurement.change_procurementrequest'):
            return True
        
        # Автор заявки
        if procurement_request.requestor == user:
            return True
        
        # Начальник отдела
        if procurement_request.department.head == user:
            return True
        
        # Нет прав
        raise PermissionDenied(
            "Вы не можете изменять позиции в этой заявке"
        )
    
    def perform_update(self, serializer):
        """Проверяем права при обновлении позиции."""
        item = self.get_object()
        self._check_item_edit_permission(item)
        serializer.save()
    
    def perform_destroy(self, instance):
        """Проверяем права при удалении позиции."""
        self._check_item_edit_permission(instance)
        instance.delete()

    @action(detail=True, methods=['post'])
    def create_equipment(self, request, pk=None):
        """Создать оборудование из позиции закупки.
        
        Эндпоинт для ручного создания оборудования после получения товара.
        Требуется: inventory_number, category, department.
        Опционально: serial_number, location, warranty_until, responsible.
        """
        item = self.get_object()
        
        # Проверяем, что заявка завершена
        if item.request.status != ProcurementStatus.COMPLETED:
            return Response(
                {'error': 'Оборудование можно создать только из '
                          'завершённой заявки'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Проверяем, что оборудование еще не создано
        if item.equipment is not None:
            return Response(
                {'error': 'Оборудование для этой позиции уже создано'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Получаем данные из запроса
        inventory_number = request.data.get('inventory_number')
        category_id = request.data.get('category')
        department_id = request.data.get('department')
        serial_number = request.data.get('serial_number', '')
        location = request.data.get('location', '')
        warranty_until = request.data.get('warranty_until')
        responsible_person_id = request.data.get('responsible_person')
        
        # Валидация обязательных полей
        if not inventory_number:
            return Response(
                {'error': 'Укажите инвентарный номер'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not category_id:
            return Response(
                {'error': 'Укажите категорию оборудования'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if not department_id:
            return Response(
                {'error': 'Укажите отдел'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Проверяем уникальность инвентарного номера
        exists = Equipment.objects.filter(
            inventory_number=inventory_number
        ).exists()
        if exists:
            return Response(
                {'error': f'Инвентарный номер "{inventory_number}" '
                          'уже используется'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Создаем оборудование
        from django.utils import timezone
        try:
            equipment = Equipment.objects.create(
                name=item.name,
                inventory_number=inventory_number,
                serial_number=serial_number,
                category_id=category_id,
                department_id=department_id,
                status=EquipmentStatus.AVAILABLE,
                responsible_person_id=responsible_person_id,
                location=location,
                purchase_date=timezone.now().date(),
                warranty_until=warranty_until,
                purchase_cost=item.estimated_unit_price,
                notes=item.description,  # description -> notes
            )
        except Exception as e:
            return Response(
                {'error': f'Ошибка создания оборудования: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Связываем оборудование с позицией закупки
        item.equipment = equipment
        item.save()
        
        return Response({
            'message': 'Оборудование успешно создано',
            'equipment': {
                'id': equipment.id,
                'name': equipment.name,
                'inventory_number': equipment.inventory_number,
            }
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['post'])
    def link_equipment(self, request, pk=None):
        """Связать существующее оборудование с позицией закупки.
        
        Используется после создания оборудования через основной API.
        Требуется: equipment_id.
        """
        item = self.get_object()
        
        # Проверяем, что заявка завершена
        if item.request.status != ProcurementStatus.COMPLETED:
            return Response(
                {'error': 'Связывать оборудование можно только '
                          'с позициями завершённых заявок'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Проверяем, что оборудование ещё не связано
        if item.equipment is not None:
            return Response(
                {'error': 'Оборудование для этой позиции уже связано'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        equipment_id = request.data.get('equipment_id')
        if not equipment_id:
            return Response(
                {'error': 'Укажите ID оборудования'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Находим оборудование
        try:
            equipment = Equipment.objects.get(pk=equipment_id)
        except Equipment.DoesNotExist:
            return Response(
                {'error': 'Оборудование не найдено'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Проверяем, что оборудование ещё не привязано к другой позиции
        if hasattr(equipment, 'procurement_item') and equipment.procurement_item:
            return Response(
                {'error': 'Это оборудование уже связано с другой позицией'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Связываем
        item.equipment = equipment
        item.save()
        
        return Response({
            'message': 'Оборудование успешно связано с позицией',
            'equipment': {
                'id': equipment.id,
                'name': equipment.name,
                'inventory_number': equipment.inventory_number,
            }
        }, status=status.HTTP_200_OK)


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

    def create(self, request, *args, **kwargs):
        """Создание оборудования с поддержкой массового создания.
        
        Если передан параметр quantity > 1, создаётся несколько единиц
        с автоматически сгенерированными инвентарными номерами.
        """
        quantity = int(request.data.get('quantity', 1))
        quantity = max(1, min(quantity, 100))  # Ограничение от 1 до 100
        
        if quantity == 1:
            # Стандартное создание одной единицы
            return super().create(request, *args, **kwargs)
        
        # Массовое создание
        created_equipment = []
        errors = []
        
        for i in range(quantity):
            serializer = self.get_serializer(data=request.data)
            if serializer.is_valid():
                self.perform_create(serializer)
                created_equipment.append(serializer.data)
            else:
                errors.append({'index': i, 'errors': serializer.errors})
        
        if errors and not created_equipment:
            return Response(
                {
                    'detail': 'Не удалось создать оборудование',
                    'errors': errors
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        
        return Response(
            {
                'created_count': len(created_equipment),
                'equipment': created_equipment,
                'errors': errors if errors else None
            },
            status=status.HTTP_201_CREATED
        )

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

    @action(detail=False, methods=['get'], url_path='generate-inventory-number')
    def generate_inventory_number(self, request):
        """Генерация уникального инвентарного номера."""
        from procurement.services import InventoryNumberGenerator
        
        inventory_number = InventoryNumberGenerator.generate()
        return Response({'inventory_number': inventory_number})

    @action(detail=False, methods=['get'], url_path='create-options')
    def create_options(self, request):
        """Возвращает доступные опции для создания оборудования.

        Определяет уровень прав пользователя и возвращает:
        - allowed_departments: список отделов для выбора
        - can_choose_department: может ли пользователь выбирать отдел
        - can_choose_responsible: может ли выбирать ответственного
        - default_responsible: ответственный по умолчанию (если нет выбора)
        """
        from api.v1.permissions import has_dept_perm
        from employees.constants import DeptPerm
        from employees.models import EmployeeDepartment

        user = request.user

        # Определяем уровень прав
        if user.is_staff or user.is_superuser:
            perm_level = 'full'
        elif user.has_perm('procurement.add_equipment'):
            perm_level = 'full'
        elif Department.objects.filter(head_id=user.id).exists():
            perm_level = 'dept_head'
        else:
            # Проверяем скоуп-право
            user_dept_links = EmployeeDepartment.objects.filter(
                employee_id=user.id,
                is_active=True
            ).select_related('department')

            has_scoped = False
            for link in user_dept_links:
                if has_dept_perm(
                    user, link.department_id, DeptPerm.MANAGE_EQUIPMENT
                ):
                    has_scoped = True
                    break

            perm_level = 'scoped' if has_scoped else None

        # Формируем ответ в зависимости от уровня прав
        if perm_level == 'full':
            # Полный доступ — все отделы
            departments = Department.objects.all().values('id', 'name')
            return Response({
                'allowed_departments': list(departments),
                'can_choose_department': True,
                'can_choose_responsible': True,
                'default_responsible': None,
                'permission_level': 'full',
            })

        elif perm_level == 'dept_head':
            # Начальник — только свои отделы
            departments = Department.objects.filter(
                head_id=user.id
            ).values('id', 'name')
            return Response({
                'allowed_departments': list(departments),
                'can_choose_department': False,
                'can_choose_responsible': True,
                'default_responsible': {
                    'id': user.id,
                    'name': user.get_full_name(),
                },
                'permission_level': 'dept_head',
            })

        elif perm_level == 'scoped':
            # Скоуп-право — отделы с правом, ответственный = начальник
            allowed_depts = []
            default_responsible = None

            user_dept_links = EmployeeDepartment.objects.filter(
                employee_id=user.id,
                is_active=True
            ).select_related('department', 'department__head')

            for link in user_dept_links:
                if has_dept_perm(
                    user, link.department_id, DeptPerm.MANAGE_EQUIPMENT
                ):
                    dept = link.department
                    allowed_depts.append({'id': dept.id, 'name': dept.name})
                    if default_responsible is None and dept.head:
                        default_responsible = {
                            'id': dept.head.id,
                            'name': dept.head.get_full_name(),
                        }

            return Response({
                'allowed_departments': allowed_depts,
                'can_choose_department': False,
                'can_choose_responsible': False,
                'default_responsible': default_responsible,
                'permission_level': 'scoped',
            })

        else:
            # Нет прав
            return Response({
                'allowed_departments': [],
                'can_choose_department': False,
                'can_choose_responsible': False,
                'default_responsible': None,
                'permission_level': None,
            })

    @action(detail=True, methods=['post'])
    def transfer(self, request, pk=None):
        """Перевод оборудования в другой отдел или другому пользователю."""
        equipment = self.get_object()

        to_department_id = request.data.get('to_department')
        to_person_id = request.data.get('to_person')
        reason = request.data.get('reason', '')

        if not to_department_id and not to_person_id:
            return Response(
                {'error': 'Укажите отдел или ответственного'},
                status=status.HTTP_400_BAD_REQUEST
            )

        # Сохраняем старые значения
        from_department = equipment.department
        from_person = equipment.responsible_person

        # Обновляем оборудование
        if to_department_id:
            try:
                to_department = Department.objects.get(pk=to_department_id)
                equipment.department = to_department
            except Department.DoesNotExist:
                return Response(
                    {'error': 'Отдел не найден'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            to_department = from_department

        if to_person_id:
            from django.contrib.auth import get_user_model
            User = get_user_model()
            try:
                to_person = User.objects.get(pk=to_person_id)
                equipment.responsible_person = to_person
            except User.DoesNotExist:
                return Response(
                    {'error': 'Пользователь не найден'},
                    status=status.HTTP_404_NOT_FOUND
                )
        else:
            to_person = from_person

        equipment.save()

        # Создаём лог перевода
        EquipmentTransferLog.objects.create(
            equipment=equipment,
            from_department=from_department,
            to_department=to_department,
            from_person=from_person,
            to_person=to_person,
            reason=reason,
            created_by=request.user
        )

        return Response({
            'status': 'transferred',
            'equipment_id': equipment.id,
            'from_department': str(from_department),
            'to_department': str(to_department)
        })

    @action(detail=True, methods=['post'])
    def write_off(self, request, pk=None):
        """Списание оборудования."""
        equipment = self.get_object()
        reason = request.data.get('reason', '')

        if equipment.status == EquipmentStatus.RETIRED:
            return Response(
                {'error': 'Оборудование уже списано'},
                status=status.HTTP_400_BAD_REQUEST
            )

        equipment.status = EquipmentStatus.RETIRED
        equipment.notes = (equipment.notes or '') + f'\n\nСписано: {reason}'
        equipment.save()

        return Response({
            'status': 'written_off',
            'equipment_id': equipment.id
        })

    @action(detail=True, methods=['post'])
    def add_maintenance(self, request, pk=None):
        """Добавить запись об обслуживании."""
        from datetime import date
        equipment = self.get_object()

        maintenance_type = request.data.get('type', 'repair')
        description = request.data.get('description', '')
        cost = request.data.get('cost')
        maintenance_date = request.data.get('date', date.today())

        record = MaintenanceRecord.objects.create(
            equipment=equipment,
            type=maintenance_type,
            description=description,
            cost=cost,
            date=maintenance_date,
            performed_by=request.user
        )

        return Response({
            'status': 'created',
            'maintenance_id': record.id,
            'equipment_id': equipment.id
        }, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'])
    def qr_code(self, request, pk=None):
        """Получить QR-код для оборудования."""
        equipment = self.get_object()

        qr_file = QRCodeGenerator.generate_for_equipment(equipment)

        from django.http import HttpResponse
        response = HttpResponse(qr_file.read(), content_type='image/png')
        response['Content-Disposition'] = (
            f'inline; filename="equipment_{equipment.id}_qr.png"'
        )
        return response

    @action(detail=True, methods=['get'])
    def transfer_history(self, request, pk=None):
        """История переводов оборудования."""
        equipment = self.get_object()

        logs = EquipmentTransferLog.objects.filter(
            equipment=equipment
        ).order_by('-created_at')

        data = [
            {
                'id': log.id,
                'from_department': str(log.from_department),
                'to_department': str(log.to_department),
                'from_person': (
                    str(log.from_person) if log.from_person else None
                ),
                'to_person': (
                    str(log.to_person) if log.to_person else None
                ),
                'reason': log.reason,
                'created_by': str(log.created_by) if log.created_by else None,
                'date': log.created_at.isoformat()
            }
            for log in logs
        ]

        return Response(data)


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
        if self.action == 'my_department':
            # my_department доступен любому авторизованному пользователю
            permission_classes = [permissions.IsAuthenticated]
        else:
            permission_classes = [CanManageBudget]
        return [permission() for permission in permission_classes]

    def get_queryset(self):
        """Фильтровать бюджеты."""
        queryset = super().get_queryset()
        user = self.request.user

        if user.is_superuser or user.is_staff:
            return queryset

        # Руководители видят бюджеты своих отделов
        if user.headed_departments.exists():
            return queryset.filter(
                department__in=user.headed_departments.all()
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

    @action(detail=False, methods=['get'], url_path='my-department')
    def my_department(self, request):
        """Получить бюджет текущего квартала для отдела пользователя."""
        from django.utils import timezone
        
        user = request.user
        now = timezone.now()
        quarter = (now.month - 1) // 3 + 1
        
        # Получаем отдел пользователя
        user_departments = user.departments.all()
        if not user_departments.exists():
            return Response(
                {'detail': 'Вы не состоите ни в одном отделе.'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Берём первый отдел (основной)
        department = user_departments.first()
        
        try:
            budget = Budget.objects.get(
                department=department,
                year=now.year,
                quarter=quarter
            )
        except Budget.DoesNotExist:
            msg = (
                f'Бюджет для {department.name} '
                f'на Q{quarter} {now.year} не найден.'
            )
            return Response(
                {'detail': msg},
                status=status.HTTP_404_NOT_FOUND
            )
        
        serializer = BudgetDetailSerializer(budget)
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


class ProcurementStatsViewSet(viewsets.ViewSet):
    """ViewSet для статистики закупок."""

    permission_classes = [permissions.IsAuthenticated]

    @action(detail=False, methods=['get'])
    def overview(self, request):
        """Общая статистика закупок."""
        from django.db.models import Sum, Count
        from django.utils import timezone

        now = timezone.now()
        month_start = now.replace(day=1, hour=0, minute=0, second=0)
        year_start = now.replace(month=1, day=1, hour=0, minute=0, second=0)

        user = request.user
        
        # Базовый queryset зависит от прав пользователя
        if user.is_superuser or user.is_staff:
            base_qs = ProcurementRequest.objects.all()
        else:
            base_qs = ProcurementRequest.objects.filter(
                Q(requestor=user) |
                Q(department__in=user.departments.all())
            )

        # Подсчёт по статусам
        by_status = dict(
            base_qs.values('status').annotate(
                count=Count('id')
            ).values_list('status', 'count')
        )

        # Подсчёт по срочности
        by_urgency = dict(
            base_qs.values('urgency').annotate(
                count=Count('id')
            ).values_list('urgency', 'count')
        )

        # Общие метрики
        total = base_qs.count()
        pending = base_qs.filter(status=ProcurementStatus.PENDING).count()
        approved_month = base_qs.filter(
            status=ProcurementStatus.APPROVED,
            updated_at__gte=month_start
        ).count()
        completed_month = base_qs.filter(
            status=ProcurementStatus.COMPLETED,
            completed_at__gte=month_start
        ).count()
        
        # Сумма потраченного за год
        spent_year = base_qs.filter(
            status=ProcurementStatus.COMPLETED,
            completed_at__gte=year_start
        ).aggregate(total=Sum('actual_cost'))['total'] or 0

        return Response({
            'total_requests': total,
            'pending_requests': pending,
            'approved_this_month': approved_month,
            'completed_this_month': completed_month,
            'total_spent_this_year': str(spent_year),
            'by_status': by_status,
            'by_urgency': by_urgency,
        })

    @action(detail=False, methods=['get'], url_path='by-department')
    def by_department(self, request):
        """Статистика по отделам."""
        from django.db.models import Sum

        user = request.user
        
        # Только для staff/superuser или руководителей
        if not (user.is_superuser or user.is_staff):
            if not user.headed_departments.exists():
                return Response(
                    {'detail': 'Нет доступа к статистике по отделам.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            departments = user.headed_departments.all()
        else:
            departments = Department.objects.all()

        result = []
        for dept in departments:
            requests = ProcurementRequest.objects.filter(department=dept)
            total = requests.count()
            spent = requests.filter(
                status=ProcurementStatus.COMPLETED
            ).aggregate(total=Sum('actual_cost'))['total'] or 0
            
            # Получаем текущий бюджет
            from django.utils import timezone
            now = timezone.now()
            quarter = (now.month - 1) // 3 + 1
            try:
                budget = Budget.objects.get(
                    department=dept,
                    year=now.year,
                    quarter=quarter
                )
                utilization = float(budget.utilization_percentage)
            except Budget.DoesNotExist:
                utilization = 0.0

            result.append({
                'department': {'id': dept.id, 'name': dept.name},
                'total_requests': total,
                'total_spent': str(spent),
                'budget_utilization': utilization,
            })

        return Response(result)
