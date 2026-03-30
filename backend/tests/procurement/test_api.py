"""
Тесты для API модуля закупок.
"""

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from employees.models import Department, Employee
from procurement.constants import ProcurementStatus, UrgencyLevel
from procurement.models import (
    Budget,
    Equipment,
    EquipmentCategory,
    ProcurementRequest,
    Supplier,
)


@pytest.fixture
def api_client():
    """API клиент."""
    return APIClient()


@pytest.fixture
def user(db):
    """Обычный пользователь."""
    return Employee.objects.create_user(
        email="user@example.com",
        password="testpass123",
        phone_number="+79991111111",
        first_name="Иван",
        last_name="Иванов",
        send_activation_email=False,
    )


@pytest.fixture
def staff_user(db):
    """Staff пользователь."""
    return Employee.objects.create_user(
        email="staff@example.com",
        password="testpass123",
        phone_number="+79992222222",
        first_name="Админ",
        last_name="Админов",
        is_staff=True,
        send_activation_email=False,
    )


@pytest.fixture
def department(db):
    """Тестовый отдел."""
    return Department.objects.create(
        name="Тестовый отдел",
        description="Для тестов"
    )


@pytest.fixture
def procurement_request(db, department, user):
    """Тестовая заявка."""
    return ProcurementRequest.objects.create(
        title="Тестовая заявка",
        description="Описание",
        department=department,
        requestor=user,
        status=ProcurementStatus.DRAFT,
        urgency=UrgencyLevel.MEDIUM,
    )


@pytest.mark.django_db
class TestProcurementRequestAPI:
    """Тесты API заявок на закупку."""

    def test_list_requests_unauthorized(self, api_client):
        """Тест: неавторизованный доступ запрещен."""
        url = reverse('procurement:procurementrequest-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_requests_authorized(
        self, api_client, user, procurement_request
    ):
        """Тест: авторизованный пользователь видит свои заявки."""
        api_client.force_authenticate(user=user)
        url = reverse('procurement:procurementrequest-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['title'] == "Тестовая заявка"

    def test_create_request(
        self, api_client, user, department, link_factory
    ):
        """Тест: создание заявки."""
        # Связываем пользователя с отделом (необходимо для создания заявки)
        link_factory(user, department, is_active=True)
        
        api_client.force_authenticate(user=user)
        url = reverse('procurement:procurementrequest-list')
        
        data = {
            'title': 'Новая заявка',
            'description': 'Нужны компьютеры',
            'department': department.id,
            'urgency': UrgencyLevel.HIGH,
            'items': [
                {
                    'name': 'Ноутбук',
                    'quantity': 2,
                    'unit': 'шт',
                    'estimated_unit_price': '50000.00',
                }
            ]
        }
        
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'Новая заявка'
        assert response.data['requestor'] == user.id

    def test_retrieve_request(
        self, api_client, user, procurement_request
    ):
        """Тест: получение детальной информации о заявке."""
        api_client.force_authenticate(user=user)
        url = reverse(
            'procurement:procurementrequest-detail',
            kwargs={'pk': procurement_request.id}
        )
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == procurement_request.id
        assert response.data['title'] == "Тестовая заявка"
        assert 'total_cost' in response.data
        assert 'required_approval_priorities' in response.data
        assert 'is_editable' in response.data

    def test_update_own_request_draft(
        self, api_client, user, procurement_request
    ):
        """Тест: обновление своей заявки в статусе DRAFT."""
        api_client.force_authenticate(user=user)
        url = reverse(
            'procurement:procurementrequest-detail',
            kwargs={'pk': procurement_request.id}
        )
        
        data = {'title': 'Обновленная заявка'}
        response = api_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == 'Обновленная заявка'


@pytest.mark.django_db
class TestEquipmentAPI:
    """Тесты API оборудования."""

    def test_list_equipment(
        self, api_client, user, department
    ):
        """Тест: список оборудования."""
        api_client.force_authenticate(user=user)
        
        # Создаем категорию и оборудование
        category = EquipmentCategory.objects.create(name="Компьютеры")
        Equipment.objects.create(
            name="Ноутбук Dell",
            inventory_number="INV-2025-001",
            category=category,
            department=department,
            purchase_date="2025-01-01",
            purchase_cost=Decimal("80000.00"),
        )
        
        url = reverse('procurement:equipment-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1

    def test_create_equipment_staff_only(
        self, api_client, user, staff_user, department
    ):
        """Тест: создание оборудования только для staff."""
        category = EquipmentCategory.objects.create(name="Техника")
        
        # Обычный пользователь не может создать
        api_client.force_authenticate(user=user)
        url = reverse('procurement:equipment-list')
        
        data = {
            'name': 'Принтер HP',
            'inventory_number': 'INV-2025-002',
            'category': category.id,
            'department': department.id,
            'purchase_date': '2025-01-01',
            'purchase_cost': '20000.00',
        }
        
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN
        
        # Staff может создать
        api_client.force_authenticate(user=staff_user)
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
class TestBudgetAPI:
    """Тесты API бюджетов."""

    def test_list_budgets_staff(
        self, api_client, staff_user, department
    ):
        """Тест: список бюджетов для staff."""
        api_client.force_authenticate(user=staff_user)
        
        Budget.objects.create(
            department=department,
            year=2025,
            quarter=4,
            allocated_amount=Decimal("500000.00"),
        )
        
        url = reverse('procurement:budget-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1

    def test_list_budgets_regular_user(
        self, api_client, user
    ):
        """Тест: обычный пользователь не видит бюджеты (нет прав)."""
        api_client.force_authenticate(user=user)
        
        url = reverse('procurement:budget-list')
        response = api_client.get(url)
        
        # Обычный пользователь не имеет доступа к бюджетам
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestSupplierAPI:
    """Тесты API поставщиков."""

    def test_list_suppliers(self, api_client, user):
        """Тест: список поставщиков."""
        api_client.force_authenticate(user=user)
        
        Supplier.objects.create(
            name="ООО Тестовый поставщик",
            rating=Decimal("4.50"),
        )
        
        url = reverse('procurement:supplier-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1

    def test_top_rated_suppliers(self, api_client, user):
        """Тест: лучшие поставщики."""
        api_client.force_authenticate(user=user)
        
        Supplier.objects.create(
            name="Отличный поставщик",
            rating=Decimal("4.80"),
            is_active=True,
        )
        Supplier.objects.create(
            name="Плохой поставщик",
            rating=Decimal("2.50"),
            is_active=True,
        )
        
        url = reverse('procurement:supplier-top-rated')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        # Должен вернуть только с рейтингом >= 4.0
        assert len(response.data) == 1
        assert response.data[0]['name'] == "Отличный поставщик"


@pytest.mark.django_db
class TestEquipmentCategoryAPI:
    """Тесты API категорий оборудования."""

    def test_category_tree(self, api_client, user):
        """Тест: дерево категорий."""
        api_client.force_authenticate(user=user)
        
        parent = EquipmentCategory.objects.create(name="Компьютеры")
        EquipmentCategory.objects.create(
            name="Ноутбуки",
            parent=parent
        )
        
        url = reverse('procurement:equipmentcategory-tree')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        # Должен вернуть только корневые категории
        assert len(response.data) == 1
        assert response.data[0]['name'] == "Компьютеры"
