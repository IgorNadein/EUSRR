"""
Тесты API для заявок на закупку (ProcurementRequest).
"""

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from employees.models import Department, Employee, EmployeeDepartment
from procurement.constants import (
    ApprovalStatus,
    ProcurementStatus,
    UrgencyLevel,
)
from procurement.models import (
    Approval,
    ApprovalRoute,
    Budget,
    ProcurementItem,
    ProcurementRequest,
)


pytestmark = pytest.mark.django_db

HEAD_PRIORITY = 1
FINANCE_PRIORITY = 2
DIRECTOR_PRIORITY = 3


@pytest.fixture
def api_client():
    """API клиент."""
    return APIClient()


@pytest.fixture
def department(db):
    """Тестовый отдел."""
    return Department.objects.create(
        name="IT отдел",
        description="Отдел информационных технологий"
    )


@pytest.fixture
def user(db, department):
    """Обычный пользователь."""
    user = Employee.objects.create_user(
        email="user@example.com",
        password="testpass123",
        phone_number="+79991111111",
        first_name="Иван",
        last_name="Иванов",
        is_active=True,
        email_verified=True,
        send_activation_email=False,
    )
    # Связываем с отделом
    EmployeeDepartment.objects.create(
        employee=user,
        department=department,
        is_active=True
    )
    return user


@pytest.fixture
def department_head(db, department):
    """Руководитель отдела."""
    head = Employee.objects.create_user(
        email="head@example.com",
        password="testpass123",
        phone_number="+79992222222",
        first_name="Петр",
        last_name="Петров",
        is_active=True,
        email_verified=True,
        send_activation_email=False,
    )
    # Назначаем руководителем отдела (автоматически создаст EmployeeDepartment)
    department.head = head
    department.save()
    return head


@pytest.fixture
def staff_user(db):
    """Staff пользователь."""
    return Employee.objects.create_user(
        email="staff@example.com",
        password="testpass123",
        phone_number="+79993333333",
        first_name="Админ",
        last_name="Админов",
        is_staff=True,
        is_active=True,
        email_verified=True,
        send_activation_email=False,
    )


@pytest.fixture
def budget(db, department):
    """Бюджет отдела."""
    return Budget.objects.create(
        department=department,
        year=2026,
        quarter=1,
        allocated_amount=Decimal("500000.00"),
        spent_amount=Decimal("0.00"),
    )


@pytest.fixture
def procurement_request(db, department, user):
    """Тестовая заявка."""
    return ProcurementRequest.objects.create(
        title="Закупка ноутбуков",
        description="Нужны новые ноутбуки для разработчиков",
        department=department,
        requestor=user,
        status=ProcurementStatus.DRAFT,
        urgency=UrgencyLevel.MEDIUM,
    )


@pytest.fixture
def procurement_item(db, procurement_request):
    """Позиция в заявке."""
    return ProcurementItem.objects.create(
        request=procurement_request,
        name="Ноутбук Dell XPS 15",
        description="i7, 32GB RAM, 1TB SSD",
        quantity=3,
        unit="шт",
        estimated_unit_price=Decimal("120000.00"),
        supplier_info="https://example.com/dell-xps-15",
    )


# ==============================================================================
# ТЕСТЫ СПИСКА ЗАЯВОК
# ==============================================================================


class TestProcurementRequestList:
    """Тесты получения списка заявок."""

    def test_list_unauthorized(self, api_client):
        """Неавторизованный доступ запрещен."""
        url = reverse('api:v1:procurement:procurementrequest-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_own_requests(
        self, api_client, user, procurement_request
    ):
        """Пользователь видит свои заявки."""
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:procurementrequest-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']
        assert len(results) == 1
        assert results[0]['id'] == procurement_request.id
        assert results[0]['title'] == "Закупка ноутбуков"

    def test_list_department_requests(
        self, api_client, department_head, procurement_request
    ):
        """Руководитель видит заявки своего отдела."""
        api_client.force_authenticate(user=department_head)
        url = reverse('api:v1:procurement:procurementrequest-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        # Руководитель может видеть заявки отдела через scope=department
        
    def test_filter_by_status(
        self, api_client, user, department, procurement_request
    ):
        """Фильтрация по статусу."""
        # Создаем заявку с другим статусом
        ProcurementRequest.objects.create(
            title="Другая заявка",
            description="Описание",
            department=department,
            requestor=user,
            status=ProcurementStatus.PENDING,
        )
        
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:procurementrequest-list')
        
        # Фильтр DRAFT
        response = api_client.get(url, {'status': ProcurementStatus.DRAFT})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['status'] == ProcurementStatus.DRAFT

    def test_search_by_title(
        self, api_client, user, procurement_request
    ):
        """Поиск по названию."""
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:procurementrequest-list')
        
        response = api_client.get(url, {'search': 'ноутбук'})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1


# ==============================================================================
# ТЕСТЫ СОЗДАНИЯ ЗАЯВОК
# ==============================================================================


class TestProcurementRequestCreate:
    """Тесты создания заявок."""

    def test_create_request_with_items(
        self, api_client, user, department
    ):
        """Создание заявки с позициями."""
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:procurementrequest-list')
        
        data = {
            'title': 'Закупка мониторов',
            'description': 'Нужны мониторы для офиса',
            'department': department.id,
            'urgency': UrgencyLevel.LOW,
            'items': [
                {
                    'name': 'Монитор 27"',
                    'quantity': 5,
                    'unit': 'шт',
                    'estimated_unit_price': '25000.00',
                    'description': '4K, IPS',
                },
                {
                    'name': 'Монитор 24"',
                    'quantity': 10,
                    'unit': 'шт',
                    'estimated_unit_price': '18000.00',
                },
            ]
        }
        
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'Закупка мониторов'
        assert response.data['requestor'] == user.id
        assert response.data['status'] == ProcurementStatus.DRAFT
        
        # Проверяем что позиции созданы
        request_id = response.data['id']
        request = ProcurementRequest.objects.get(id=request_id)
        assert request.items.count() == 2
        assert request.total_cost == Decimal('305000.00')  # 5*25k + 10*18k

    def test_create_request_wrong_department(
        self, api_client, user, db
    ):
        """Нельзя создать заявку для чужого отдела."""
        other_dept = Department.objects.create(
            name="HR отдел", description="Другой отдел"
        )
        
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:procurementrequest-list')
        
        data = {
            'title': 'Заявка',
            'description': 'Описание',
            'department': other_dept.id,
            'urgency': UrgencyLevel.MEDIUM,
            'items': []
        }
        
        response = api_client.post(url, data, format='json')
        # Должна быть ошибка валидации
        assert response.status_code in [
            status.HTTP_400_BAD_REQUEST,
            status.HTTP_403_FORBIDDEN
        ]


# ==============================================================================
# ТЕСТЫ ДЕТАЛЬНОЙ ИНФОРМАЦИИ
# ==============================================================================


class TestProcurementRequestDetail:
    """Тесты получения детальной информации."""

    def test_retrieve_own_request(
        self, api_client, user, procurement_request, procurement_item
    ):
        """Получение своей заявки."""
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': procurement_request.id}
        )
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == procurement_request.id
        assert response.data['title'] == "Закупка ноутбуков"
        assert 'items' in response.data
        assert len(response.data['items']) == 1
        assert 'total_cost' in response.data
        assert 'is_editable' in response.data
        assert response.data['is_editable'] is True

    def test_retrieve_other_request_forbidden(
        self, api_client, db, procurement_request
    ):
        """Нельзя просмотреть чужую заявку (обычному пользователю)."""
        other_user = Employee.objects.create_user(
            email="other@example.com",
            password="testpass123",
            phone_number="+79994444444",
            first_name="Другой",
            last_name="Пользователь",
            send_activation_email=False,
        )
        
        api_client.force_authenticate(user=other_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': procurement_request.id}
        )
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


# ==============================================================================
# ТЕСТЫ ОБНОВЛЕНИЯ ЗАЯВОК
# ==============================================================================


class TestProcurementRequestUpdate:
    """Тесты обновления заявок."""

    def test_update_draft_request(
        self, api_client, user, procurement_request
    ):
        """Обновление заявки в статусе DRAFT."""
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': procurement_request.id}
        )
        
        data = {
            'title': 'Обновленное название',
            'urgency': UrgencyLevel.HIGH,
        }
        response = api_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == 'Обновленное название'
        assert response.data['urgency'] == UrgencyLevel.HIGH

    def test_cannot_update_submitted_request(
        self, api_client, user, procurement_request
    ):
        """Нельзя обновить отправленную заявку."""
        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()
        
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': procurement_request.id}
        )
        
        data = {'title': 'Новое название'}
        response = api_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ==============================================================================
# ТЕСТЫ WORKFLOW ДЕЙСТВИЙ
# ==============================================================================


class TestProcurementRequestWorkflow:
    """Тесты workflow действий с заявками."""

    @pytest.fixture(autouse=True)
    def approval_authorities(self, department_head, user):
        director = Employee.objects.create_user(
            email='director@example.com',
            password='testpass123',
            phone_number='+79995555555',
            first_name='Сергей',
            last_name='Сергеев',
            is_staff=True,
            is_superuser=True,
            is_active=True,
            email_verified=True,
            send_activation_email=False,
        )
        ApprovalRoute.objects.create(
            priority=HEAD_PRIORITY,
            resolver_type=ApprovalRoute.ResolverType.DEPARTMENT_HEAD,
        )
        ApprovalRoute.objects.create(
            priority=FINANCE_PRIORITY,
            min_amount=Decimal('10000.00'),
            name='Финансовый контроль',
            resolver_type=ApprovalRoute.ResolverType.FIXED_EMPLOYEE,
            employee=user,
        )
        ApprovalRoute.objects.create(
            priority=DIRECTOR_PRIORITY,
            min_amount=Decimal('50000.00'),
            name='Финальное одобрение',
            resolver_type=ApprovalRoute.ResolverType.FIXED_EMPLOYEE,
            employee=director,
        )

    def test_submit_request(
        self, api_client, user, procurement_request, procurement_item, budget
    ):
        """Отправка заявки на согласование."""
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': procurement_request.id}
        )
        
        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        
        # Проверяем статус изменен
        procurement_request.refresh_from_db()
        assert procurement_request.status == ProcurementStatus.PENDING
        assert procurement_request.submitted_at is not None
        assert list(
            procurement_request.approvals.order_by('priority').values_list('priority', flat=True)
        ) == [1, 2, 3]
        assert list(
            procurement_request.approvals.order_by('priority').values_list('step_name', flat=True)
        ) == [
            'Руководитель отдела',
            'Финансовый контроль',
            'Финальное одобрение',
        ]

    @pytest.mark.parametrize(
        ("unit_price", "expected_priorities"),
        [
            (Decimal("12.00"), [HEAD_PRIORITY]),
            (Decimal("12000.00"), [HEAD_PRIORITY, FINANCE_PRIORITY]),
            (Decimal("120000.00"), [HEAD_PRIORITY, FINANCE_PRIORITY, DIRECTOR_PRIORITY]),
        ],
    )
    def test_submit_request_applies_amount_thresholds(
        self, api_client, user, department, unit_price, expected_priorities
    ):
        """Маршруты согласования включаются по порогам суммы заявки."""
        procurement_request = ProcurementRequest.objects.create(
            title="Пороговая заявка",
            description="Проверка маршрутов",
            department=department,
            requestor=user,
            status=ProcurementStatus.DRAFT,
            urgency=UrgencyLevel.MEDIUM,
        )
        ProcurementItem.objects.create(
            request=procurement_request,
            name="Тестовая позиция",
            quantity=1,
            unit="шт",
            estimated_unit_price=unit_price,
        )

        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': procurement_request.id}
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        procurement_request.refresh_from_db()
        assert list(
            procurement_request.approvals.order_by('priority').values_list('priority', flat=True)
        ) == expected_priorities

    def test_submit_request_without_department_head_returns_explicit_error(
        self, api_client, user, department
    ):
        """Если обязательный этап = руководитель отдела, ошибка должна быть явной."""
        department.head = None
        department.save(update_fields=["head"])

        procurement_request = ProcurementRequest.objects.create(
            title="Заявка без начальника отдела",
            description="Проверка понятной ошибки",
            department=department,
            requestor=user,
            status=ProcurementStatus.DRAFT,
            urgency=UrgencyLevel.MEDIUM,
        )
        ProcurementItem.objects.create(
            request=procurement_request,
            name="Тестовая позиция",
            quantity=1,
            unit="шт",
            estimated_unit_price=Decimal("12.00"),
        )

        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': procurement_request.id}
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "department_head_missing"
        assert "не назначен руководитель" in response.data["error"].lower()
        assert response.data["missing_priorities"] == [HEAD_PRIORITY]
        assert response.data["missing_routes"][0]["reason"] == "department_head_missing"

    def test_submit_returns_manual_step_name(
        self, api_client, user, procurement_request, procurement_item, budget
    ):
        """Ручное название этапа сохраняется в согласовании и отдаётся в API."""
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': procurement_request.id}
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        approvals = sorted(response.data['approvals'], key=lambda item: item['priority'])
        assert approvals[1]['step_name'] == 'Финансовый контроль'
        assert approvals[1]['step_label'] == 'Финансовый контроль'

    def test_submit_without_items_fails(
        self, api_client, user, procurement_request
    ):
        """Нельзя отправить заявку без позиций."""
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': procurement_request.id}
        )
        
        response = api_client.post(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'позицию' in response.data['error'].lower()

    def test_approve_request_by_head(
        self, api_client, department_head, procurement_request,
        procurement_item, budget
    ):
        """Согласование заявки руководителем."""
        # Отправляем заявку
        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()
        
        # Создаем запись согласования
        Approval.objects.create(
            request=procurement_request,
            approver=department_head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.PENDING,
        )
        
        api_client.force_authenticate(user=department_head)
        url = reverse(
            'api:v1:procurement:procurementrequest-approve',
            kwargs={'pk': procurement_request.id}
        )
        
        response = api_client.post(url, {'comment': 'Одобрено'})
        assert response.status_code == status.HTTP_200_OK

    def test_finance_cannot_approve_before_head(
        self, api_client, user, department_head, procurement_request,
        procurement_item, budget
    ):
        """Финансовый этап недоступен, пока не завершён предыдущий."""
        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()

        Approval.objects.create(
            request=procurement_request,
            approver=department_head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.PENDING,
        )
        Approval.objects.create(
            request=procurement_request,
            approver=user,
            priority=FINANCE_PRIORITY,
            status=ApprovalStatus.PENDING,
        )

        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-approve',
            kwargs={'pk': procurement_request.id}
        )

        response = api_client.post(url, {'comment': 'Рано'})
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_reject_request(
        self, api_client, department_head, procurement_request,
        procurement_item
    ):
        """Отклонение заявки."""
        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()
        
        Approval.objects.create(
            request=procurement_request,
            approver=department_head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.PENDING,
        )
        
        api_client.force_authenticate(user=department_head)
        url = reverse(
            'api:v1:procurement:procurementrequest-reject',
            kwargs={'pk': procurement_request.id}
        )
        
        data = {'comment': 'Недостаточно обоснования'}
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        
        procurement_request.refresh_from_db()
        assert procurement_request.status == ProcurementStatus.REJECTED

    def test_cancel_own_request(
        self, api_client, user, procurement_request
    ):
        """Отмена своей заявки."""
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-cancel',
            kwargs={'pk': procurement_request.id}
        )
        
        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        
        procurement_request.refresh_from_db()
        assert procurement_request.status == ProcurementStatus.CANCELLED


# ==============================================================================
# ТЕСТЫ УДАЛЕНИЯ
# ==============================================================================


class TestProcurementRequestDelete:
    """Тесты удаления заявок."""

    def test_delete_draft_request(
        self, api_client, user, procurement_request
    ):
        """Удаление черновика."""
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': procurement_request.id}
        )
        
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        assert not ProcurementRequest.objects.filter(
            id=procurement_request.id
        ).exists()

    def test_cannot_delete_submitted_request(
        self, api_client, user, procurement_request
    ):
        """Нельзя удалить отправленную заявку."""
        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()
        
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': procurement_request.id}
        )
        
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
