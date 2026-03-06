"""
Тесты для workflow согласований модуля закупок.
"""

import pytest
from django.contrib.auth.models import Permission
from rest_framework import status

from notifications.models import NotificationCategory, NotificationType
from procurement.constants import (
    ApprovalStatus,
    ProcurementStatus,
    UrgencyLevel,
)
from procurement.models import (
    Approval,
    Budget,
    ProcurementItem,
    ProcurementRequest,
)


@pytest.mark.django_db
class TestProcurementWorkflow:
    """Тесты workflow согласований."""

    @pytest.fixture(autouse=True)
    def setup(
        self, api_client, department_factory, user_factory, link_factory
    ):
        """Подготовка данных для тестов."""
        # Создаем категорию и типы уведомлений для закупок
        category, _ = NotificationCategory.objects.get_or_create(
            code='procurement',
            defaults={
                'name': 'Закупки',
                'icon': 'bi-cart',
                'color': 'success',
                'order': 10,
            }
        )

        # Создаем типы уведомлений
        notification_types = [
            'procurement_new_request',
            'procurement_pending_approval',
            'procurement_approved',
            'procurement_rejected',
            'procurement_completed',
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
                        'web': True,
                        'email': False,
                        'telegram': False
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

        self.dept_head = user_factory(
            email="head@test.com",
            first_name="Петр",
            last_name="Петров",
        )
        self.department.head = self.dept_head
        self.department.save()

        self.finance = user_factory(
            email="finance@test.com",
            first_name="Мария",
            last_name="Сидорова",
        )
        # Даем права на бюджеты
        perm = Permission.objects.get(codename='change_budget')
        self.finance.user_permissions.add(perm)

        self.director = user_factory(
            email="director@test.com",
            first_name="Сергей",
            last_name="Сергеев",
            superuser=True,
        )

        # Создаем бюджет
        Budget.objects.create(
            department=self.department,
            year=2025,
            quarter=4,
            allocated_amount=100000,
            spent_amount=0,
        )

        self.client = api_client

    def test_create_draft_request(self):
        """Тест создания черновика заявки."""
        self.client.force_authenticate(user=self.requestor)

        data = {
            'title': 'Закупка ноутбуков',
            'description': 'Нужны новые ноутбуки для разработчиков',
            'department': self.department.id,
            'urgency': UrgencyLevel.MEDIUM,
            'items': [
                {
                    'name': 'Ноутбук Dell XPS 15',
                    'quantity': 2,
                    'unit': 'шт',
                    'estimated_unit_price': 80000,
                }
            ],
        }

        response = self.client.post(
            '/api/procurement/requests/',
            data,
            format='json'
        )

        assert response.status_code == status.HTTP_201_CREATED
        # Проверяем, что заявка создана
        assert 'title' in response.data
        assert response.data['title'] == 'Закупка ноутбуков'

        # Проверяем в базе данных
        request = ProcurementRequest.objects.get(
            title='Закупка ноутбуков'
        )
        assert request.status == ProcurementStatus.DRAFT
        assert request.is_editable is True
        assert request.items.count() == 1

    def test_submit_request_creates_approvals(self):
        """Тест отправки заявки создает записи согласований."""
        # Создаем заявку
        request = ProcurementRequest.objects.create(
            title='Закупка оборудования',
            description='Тестовая заявка',
            department=self.department,
            requestor=self.requestor,
            status=ProcurementStatus.DRAFT,
            urgency=UrgencyLevel.MEDIUM,
        )
        ProcurementItem.objects.create(
            request=request,
            name='Монитор',
            quantity=1,
            unit='шт',
            estimated_unit_price=15000,
        )

        self.client.force_authenticate(user=self.requestor)

        response = self.client.post(
            f'/api/procurement/requests/{request.id}/submit/'
        )

        if response.status_code != status.HTTP_200_OK:
            print(f"Error response: {response.data}")
        assert response.status_code == status.HTTP_200_OK
        request.refresh_from_db()
        assert request.status == ProcurementStatus.PENDING

        # Проверяем создание согласований
        approvals = request.approvals.all()
        # Для суммы 15,000 нужно 2 согласования
        # (руководитель + финансы)
        assert approvals.count() == 2

    def test_cannot_submit_without_items(self):
        """Тест: нельзя отправить заявку без позиций."""
        request = ProcurementRequest.objects.create(
            title='Пустая заявка',
            description='Без позиций',
            department=self.department,
            requestor=self.requestor,
            status=ProcurementStatus.DRAFT,
            urgency=UrgencyLevel.LOW,
        )

        self.client.force_authenticate(user=self.requestor)

        response = self.client.post(
            f'/api/procurement/requests/{request.id}/submit/'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'позиц' in response.data['error'].lower()

    def test_cannot_submit_without_budget(self):
        """Тест: нельзя отправить заявку если нет бюджета."""
        # Создаем заявку на сумму больше бюджета
        request = ProcurementRequest.objects.create(
            title='Дорогая заявка',
            description='Превышает бюджет',
            department=self.department,
            requestor=self.requestor,
            status=ProcurementStatus.DRAFT,
            urgency=UrgencyLevel.HIGH,
        )
        ProcurementItem.objects.create(
            request=request,
            name='Очень дорогое оборудование',
            quantity=1,
            unit='шт',
            estimated_unit_price=200000,
        )

        self.client.force_authenticate(user=self.requestor)

        response = self.client.post(
            f'/api/procurement/requests/{request.id}/submit/'
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'бюджет' in response.data['error'].lower()

    def test_approve_by_department_head(self):
        """Тест одобрения заявки руководителем отдела."""
        # Создаем заявку и отправляем на согласование
        request = ProcurementRequest.objects.create(
            title='Заявка на согласование',
            description='Тест',
            department=self.department,
            requestor=self.requestor,
            status=ProcurementStatus.PENDING,
            urgency=UrgencyLevel.MEDIUM,
        )
        ProcurementItem.objects.create(
            request=request,
            name='Клавиатура',
            quantity=1,
            unit='шт',
            estimated_unit_price=3000,
        )

        # Создаем согласование для руководителя
        Approval.objects.create(
            request=request,
            approver=self.dept_head,
            role='department_head',
            status=ApprovalStatus.PENDING,
        )

        self.client.force_authenticate(user=self.dept_head)

        response = self.client.post(
            f'/api/procurement/requests/{request.id}/approve/',
            {'comment': 'Одобряю'},
        )

        assert response.status_code == status.HTTP_200_OK
        
        # Проверяем статус согласования
        approval = request.approvals.get(approver=self.dept_head)
        assert approval.status == ApprovalStatus.APPROVED
        assert approval.comment == 'Одобряю'

        # Проверяем статус заявки (должна быть одобрена)
        request.refresh_from_db()
        assert request.status == ProcurementStatus.APPROVED

    def test_reject_by_approver(self):
        """Тест отклонения заявки согласующим."""
        request = ProcurementRequest.objects.create(
            title='Заявка на отклонение',
            description='Будет отклонена',
            department=self.department,
            requestor=self.requestor,
            status=ProcurementStatus.PENDING,
            urgency=UrgencyLevel.LOW,
        )

        Approval.objects.create(
            request=request,
            approver=self.dept_head,
            role='department_head',
            status=ApprovalStatus.PENDING,
        )

        self.client.force_authenticate(user=self.dept_head)

        response = self.client.post(
            f'/api/procurement/requests/{request.id}/reject/',
            {'comment': 'Не обоснована необходимость'},
        )

        assert response.status_code == status.HTTP_200_OK

        # Проверяем статус согласования
        approval = request.approvals.get(approver=self.dept_head)
        assert approval.status == ApprovalStatus.REJECTED
        assert 'обоснована' in approval.comment

        # Проверяем статус заявки
        request.refresh_from_db()
        assert request.status == ProcurementStatus.REJECTED

    def test_multi_level_approval(self):
        """Тест многоуровневого согласования."""
        # Создаем заявку на 45,000₽ (нужно 2 уровня)
        request = ProcurementRequest.objects.create(
            title='Средняя по стоимости заявка',
            description='Требует 2 согласования',
            department=self.department,
            requestor=self.requestor,
            status=ProcurementStatus.PENDING,
            urgency=UrgencyLevel.MEDIUM,
        )
        ProcurementItem.objects.create(
            request=request,
            name='Сервер',
            quantity=1,
            unit='шт',
            estimated_unit_price=45000,
        )

        # Создаем 2 согласования
        Approval.objects.create(
            request=request,
            approver=self.dept_head,
            role='department_head',
            status=ApprovalStatus.PENDING,
        )
        Approval.objects.create(
            request=request,
            approver=self.finance,
            role='finance_manager',
            status=ApprovalStatus.PENDING,
        )

        # 1. Одобряет руководитель отдела
        self.client.force_authenticate(user=self.dept_head)
        response = self.client.post(
            f'/api/procurement/requests/{request.id}/approve/',
            {'comment': 'От отдела одобряю'},
        )
        assert response.status_code == status.HTTP_200_OK

        request.refresh_from_db()
        # Заявка еще на согласовании (не все одобрили)
        assert request.status == ProcurementStatus.PENDING

        # 2. Одобряет финансовый менеджер
        self.client.force_authenticate(user=self.finance)
        response = self.client.post(
            f'/api/procurement/requests/{request.id}/approve/',
            {'comment': 'От финансов одобряю'},
        )
        print(f"DEBUG 2: Response status: {response.status_code}")
        if response.status_code != status.HTTP_200_OK:
            print(f"DEBUG 2: Response data: {response.data}")
        assert response.status_code == status.HTTP_200_OK

        request.refresh_from_db()
        # Теперь заявка одобрена
        assert request.status == ProcurementStatus.APPROVED

    def test_cannot_approve_without_permission(self):
        """Тест: нельзя согласовать без прав."""
        request = ProcurementRequest.objects.create(
            title='Чужая заявка',
            description='Не могу согласовать',
            department=self.department,
            requestor=self.requestor,
            status=ProcurementStatus.PENDING,
            urgency=UrgencyLevel.LOW,
        )

        Approval.objects.create(
            request=request,
            approver=self.dept_head,
            role='department_head',
            status=ApprovalStatus.PENDING,
        )

        # Пытаемся одобрить от лица другого пользователя
        self.client.force_authenticate(user=self.finance)

        response = self.client.post(
            f'/api/procurement/requests/{request.id}/approve/'
        )

        # Должна быть ошибка - 404 или 403/400
        # 404 если заявка не в queryset, 403/400 если нет прав
        assert response.status_code in [
            status.HTTP_404_NOT_FOUND,
            status.HTTP_403_FORBIDDEN,
            status.HTTP_400_BAD_REQUEST,
        ]

    def test_cannot_edit_after_submit(self):
        """Тест: нельзя редактировать после отправки."""
        request = ProcurementRequest.objects.create(
            title='Отправленная заявка',
            description='Уже на согласовании',
            department=self.department,
            requestor=self.requestor,
            status=ProcurementStatus.PENDING,
            urgency=UrgencyLevel.MEDIUM,
        )

        assert request.is_editable is False

        self.client.force_authenticate(user=self.requestor)

        response = self.client.patch(
            f'/api/procurement/requests/{request.id}/',
            {'title': 'Новое название'},
        )

        # Должна быть ошибка прав доступа
        assert response.status_code == status.HTTP_403_FORBIDDEN
