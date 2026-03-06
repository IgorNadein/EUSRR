"""
Тесты для полного жизненного цикла заявок на закупку.
Тестируются endpoints: start_work, complete, cancel, create_equipment.
"""

import pytest
from django.utils import timezone
from rest_framework import status

from notifications.models import NotificationCategory, NotificationType
from procurement.constants import (
    ApprovalStatus,
    EquipmentStatus,
    ProcurementStatus,
    UrgencyLevel,
)
from procurement.models import (
    Approval,
    Budget,
    Equipment,
    EquipmentCategory,
    ProcurementItem,
    ProcurementRequest,
)


@pytest.mark.django_db
class TestRequestLifecycle:
    """Тесты жизненного цикла заявок: start_work, complete, cancel."""

    @pytest.fixture(autouse=True)
    def setup(
        self, api_client, department_factory, user_factory, link_factory
    ):
        """Подготовка данных для тестов."""
        # Создаем категорию и типы уведомлений
        category, _ = NotificationCategory.objects.get_or_create(
            code='procurement',
            defaults={
                'name': 'Закупки',
                'icon': 'bi-cart',
                'color': 'success',
                'order': 10,
            }
        )

        notification_types = [
            'procurement_pending_approval',
            'procurement_approved',
            'procurement_rejected',
            'procurement_in_progress',
            'procurement_completed',
            'procurement_cancelled',
            'procurement_stage_approved',
        ]

        for type_code in notification_types:
            NotificationType.objects.get_or_create(
                code=type_code,
                defaults={
                    'category': category,
                    'name': type_code.replace('_', ' ').title(),
                    'description': f'Уведомление {type_code}',
                    'priority': 'normal',
                    'default_channels': {
                        'web': True, 'email': False, 'telegram': False
                    },
                }
            )

        # Создаем отдел
        self.department = department_factory(name="IT отдел")

        # Создаем пользователей
        self.requestor = user_factory(
            email="requestor@test.com",
            first_name="Иван",
            last_name="Иванов",
        )
        link_factory(self.requestor, self.department, is_active=True)

        self.other_user = user_factory(
            email="other@test.com",
            first_name="Петр",
            last_name="Петров",
        )
        link_factory(self.other_user, self.department, is_active=True)

        self.dept_head = user_factory(
            email="head@test.com",
            first_name="Анна",
            last_name="Сидорова",
        )
        self.department.head = self.dept_head
        self.department.save()

        # Создаем бюджет
        Budget.objects.create(
            department=self.department,
            year=timezone.now().year,
            quarter=(timezone.now().month - 1) // 3 + 1,
            allocated_amount=100000,
            spent_amount=0,
        )

        self.client = api_client

    def _create_request(self, request_status=ProcurementStatus.DRAFT):
        """Хелпер для создания заявки."""
        request = ProcurementRequest.objects.create(
            title='Тестовая заявка',
            description='Описание',
            department=self.department,
            requestor=self.requestor,
            status=request_status,
            urgency=UrgencyLevel.MEDIUM,
        )
        ProcurementItem.objects.create(
            request=request,
            name='Тестовый товар',
            quantity=1,
            unit='шт',
            estimated_unit_price=5000,
        )
        return request

    # ===== start_work tests =====

    def test_start_work_success(self):
        """Тест начала работы над одобренной заявкой."""
        request = self._create_request(ProcurementStatus.APPROVED)

        # Добавляем approval (для уведомления)
        Approval.objects.create(
            request=request,
            approver=self.dept_head,
            role='department_head',
            status=ApprovalStatus.APPROVED,
        )

        self.client.force_authenticate(user=self.requestor)

        response = self.client.post(
            f'/api/procurement/requests/{request.id}/start_work/'
        )

        assert response.status_code == status.HTTP_200_OK
        request.refresh_from_db()
        assert request.status == ProcurementStatus.IN_PROGRESS

    def test_start_work_by_another_user(self):
        """Любой авторизованный пользователь может взять заявку в работу."""
        request = self._create_request(ProcurementStatus.APPROVED)

        self.client.force_authenticate(user=self.other_user)

        response = self.client.post(
            f'/api/procurement/requests/{request.id}/start_work/'
        )

        # Любой авторизованный может взять в работу
        assert response.status_code == status.HTTP_200_OK
        request.refresh_from_db()
        assert request.status == ProcurementStatus.IN_PROGRESS
        assert request.executor == self.other_user

    def test_start_work_wrong_status(self):
        """Нельзя начать работу над неодобренной заявкой."""
        request = self._create_request(ProcurementStatus.PENDING)

        self.client.force_authenticate(user=self.requestor)

        response = self.client.post(
            f'/api/procurement/requests/{request.id}/start_work/'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'одобрен' in response.data['error'].lower()

    # ===== complete tests =====

    def test_complete_success(self):
        """Тест завершения заявки исполнителем."""
        request = self._create_request(ProcurementStatus.IN_PROGRESS)
        # Устанавливаем исполнителя
        request.executor = self.requestor
        request.save()

        Approval.objects.create(
            request=request,
            approver=self.dept_head,
            role='department_head',
            status=ApprovalStatus.APPROVED,
        )

        self.client.force_authenticate(user=self.requestor)

        response = self.client.post(
            f'/api/procurement/requests/{request.id}/complete/'
        )

        assert response.status_code == status.HTTP_200_OK
        request.refresh_from_db()
        assert request.status == ProcurementStatus.COMPLETED

    def test_complete_forbidden_for_non_executor(self):
        """Только исполнитель может завершить заявку."""
        request = self._create_request(ProcurementStatus.IN_PROGRESS)
        # Исполнитель - requestor, но пытается завершить other_user
        request.executor = self.requestor
        request.save()

        self.client.force_authenticate(user=self.other_user)

        response = self.client.post(
            f'/api/procurement/requests/{request.id}/complete/'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_complete_wrong_status(self):
        """Нельзя завершить заявку, которая не в работе."""
        request = self._create_request(ProcurementStatus.APPROVED)
        # Даже с исполнителем, если статус неверный - ошибка
        request.executor = self.requestor
        request.save()

        self.client.force_authenticate(user=self.requestor)

        response = self.client.post(
            f'/api/procurement/requests/{request.id}/complete/'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'в работе' in response.data['error'].lower()

    # ===== cancel tests =====

    def test_cancel_draft_success(self):
        """Тест отмены черновика."""
        request = self._create_request(ProcurementStatus.DRAFT)

        self.client.force_authenticate(user=self.requestor)

        response = self.client.post(
            f'/api/procurement/requests/{request.id}/cancel/',
            {'reason': 'Передумал'}
        )

        assert response.status_code == status.HTTP_200_OK
        request.refresh_from_db()
        assert request.status == ProcurementStatus.CANCELLED

    def test_cancel_pending_success(self):
        """Тест отмены заявки на согласовании."""
        request = self._create_request(ProcurementStatus.PENDING)

        Approval.objects.create(
            request=request,
            approver=self.dept_head,
            role='department_head',
            status=ApprovalStatus.PENDING,
        )

        self.client.force_authenticate(user=self.requestor)

        response = self.client.post(
            f'/api/procurement/requests/{request.id}/cancel/',
            {'reason': 'Нашли другое решение'}
        )

        assert response.status_code == status.HTTP_200_OK
        request.refresh_from_db()
        assert request.status == ProcurementStatus.CANCELLED

    def test_cancel_in_progress_success(self):
        """Тест отмены заявки в работе."""
        request = self._create_request(ProcurementStatus.IN_PROGRESS)

        self.client.force_authenticate(user=self.requestor)

        response = self.client.post(
            f'/api/procurement/requests/{request.id}/cancel/'
        )

        assert response.status_code == status.HTTP_200_OK
        request.refresh_from_db()
        assert request.status == ProcurementStatus.CANCELLED

    def test_cannot_cancel_completed(self):
        """Нельзя отменить завершённую заявку."""
        request = self._create_request(ProcurementStatus.COMPLETED)

        self.client.force_authenticate(user=self.requestor)

        response = self.client.post(
            f'/api/procurement/requests/{request.id}/cancel/'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cannot_cancel_already_cancelled(self):
        """Нельзя отменить уже отменённую заявку."""
        request = self._create_request(ProcurementStatus.CANCELLED)

        self.client.force_authenticate(user=self.requestor)

        response = self.client.post(
            f'/api/procurement/requests/{request.id}/cancel/'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_cancel_forbidden_for_non_requestor(self):
        """Только автор заявки может отменить её."""
        request = self._create_request(ProcurementStatus.PENDING)

        self.client.force_authenticate(user=self.other_user)

        response = self.client.post(
            f'/api/procurement/requests/{request.id}/cancel/'
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestCreateEquipmentFromItem:
    """Тесты создания оборудования из позиции закупки."""

    @pytest.fixture(autouse=True)
    def setup(
        self, api_client, department_factory, user_factory, link_factory
    ):
        """Подготовка данных для тестов."""
        # Создаем отдел
        self.department = department_factory(name="IT отдел")

        # Создаем пользователя
        self.requestor = user_factory(
            email="requestor@test.com",
            first_name="Иван",
            last_name="Иванов",
        )
        link_factory(self.requestor, self.department, is_active=True)

        # Создаем категорию оборудования
        self.category = EquipmentCategory.objects.create(
            name='Компьютерное оборудование',
            description='Компьютеры и периферия'
        )

        self.client = api_client

    def _create_completed_request_with_item(self):
        """Хелпер: создаёт завершённую заявку с позицией."""
        request = ProcurementRequest.objects.create(
            title='Закупка оборудования',
            description='Описание',
            department=self.department,
            requestor=self.requestor,
            status=ProcurementStatus.COMPLETED,
            urgency=UrgencyLevel.MEDIUM,
        )
        item = ProcurementItem.objects.create(
            request=request,
            name='Ноутбук Dell XPS',
            description='Мощный ноутбук для разработки',
            quantity=1,
            unit='шт',
            estimated_unit_price=50000,
        )
        return request, item

    def test_create_equipment_success(self):
        """Тест успешного создания оборудования из позиции."""
        _, item = self._create_completed_request_with_item()

        self.client.force_authenticate(user=self.requestor)

        response = self.client.post(
            f'/api/procurement/items/{item.id}/create_equipment/',
            {
                'inventory_number': 'INV-2025-0001',
                'category': self.category.id,
                'department': self.department.id,
                'serial_number': 'SN123456',
                'location': 'Офис 3.14',
            },
            format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert 'equipment' in response.data
        assert response.data['equipment']['name'] == 'Ноутбук Dell XPS'

        # Проверяем связь item -> equipment
        item.refresh_from_db()
        assert item.equipment is not None
        assert item.equipment.inventory_number == 'INV-2025-0001'
        assert item.equipment.category == self.category

    def test_create_equipment_requires_inventory_number(self):
        """Инвентарный номер обязателен."""
        _, item = self._create_completed_request_with_item()

        self.client.force_authenticate(user=self.requestor)

        response = self.client.post(
            f'/api/procurement/items/{item.id}/create_equipment/',
            {
                'category': self.category.id,
                'department': self.department.id,
            },
            format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'инвентарн' in response.data['error'].lower()

    def test_create_equipment_requires_category(self):
        """Категория обязательна."""
        _, item = self._create_completed_request_with_item()

        self.client.force_authenticate(user=self.requestor)

        response = self.client.post(
            f'/api/procurement/items/{item.id}/create_equipment/',
            {
                'inventory_number': 'INV-2025-0002',
                'department': self.department.id,
            },
            format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'категор' in response.data['error'].lower()

    def test_create_equipment_requires_department(self):
        """Отдел обязателен."""
        _, item = self._create_completed_request_with_item()

        self.client.force_authenticate(user=self.requestor)

        response = self.client.post(
            f'/api/procurement/items/{item.id}/create_equipment/',
            {
                'inventory_number': 'INV-2025-0003',
                'category': self.category.id,
            },
            format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'отдел' in response.data['error'].lower()

    def test_cannot_create_equipment_from_non_completed_request(self):
        """Нельзя создать оборудование из незавершённой заявки."""
        request = ProcurementRequest.objects.create(
            title='Заявка в работе',
            description='Ещё не завершена',
            department=self.department,
            requestor=self.requestor,
            status=ProcurementStatus.IN_PROGRESS,
            urgency=UrgencyLevel.MEDIUM,
        )
        item = ProcurementItem.objects.create(
            request=request,
            name='Монитор',
            quantity=1,
            unit='шт',
            estimated_unit_price=10000,
        )

        self.client.force_authenticate(user=self.requestor)

        response = self.client.post(
            f'/api/procurement/items/{item.id}/create_equipment/',
            {
                'inventory_number': 'INV-2025-0004',
                'category': self.category.id,
                'department': self.department.id,
            },
            format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'завершённ' in response.data['error'].lower()

    def test_cannot_create_equipment_twice(self):
        """Нельзя создать оборудование дважды для одной позиции."""
        _, item = self._create_completed_request_with_item()

        # Создаём оборудование вручную
        equipment = Equipment.objects.create(
            name='Существующее',
            inventory_number='INV-EXISTING',
            category=self.category,
            department=self.department,
            status=EquipmentStatus.AVAILABLE,
            purchase_date=timezone.now().date(),
            purchase_cost=50000,
        )
        item.equipment = equipment
        item.save()

        self.client.force_authenticate(user=self.requestor)

        response = self.client.post(
            f'/api/procurement/items/{item.id}/create_equipment/',
            {
                'inventory_number': 'INV-2025-0005',
                'category': self.category.id,
                'department': self.department.id,
            },
            format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'уже создано' in response.data['error'].lower()

    def test_duplicate_inventory_number_rejected(self):
        """Дублирующийся инвентарный номер отклоняется."""
        _, item = self._create_completed_request_with_item()

        # Создаём существующее оборудование с этим номером
        Equipment.objects.create(
            name='Существующее оборудование',
            inventory_number='INV-DUPLICATE',
            category=self.category,
            department=self.department,
            status=EquipmentStatus.AVAILABLE,
            purchase_date=timezone.now().date(),
            purchase_cost=10000,
        )

        self.client.force_authenticate(user=self.requestor)

        response = self.client.post(
            f'/api/procurement/items/{item.id}/create_equipment/',
            {
                'inventory_number': 'INV-DUPLICATE',
                'category': self.category.id,
                'department': self.department.id,
            },
            format='json'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'используется' in response.data['error'].lower()
