"""
Тесты API для оборудования (Equipment).
"""

from decimal import Decimal
from datetime import date, timedelta

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from employees.models import Department, Employee, EmployeeDepartment
from procurement.constants import EquipmentStatus
from procurement.models import Equipment, EquipmentCategory, MaintenanceRecord
from procurement.constants import MaintenanceType


pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    """API клиент"""
    return APIClient()


@pytest.fixture
def department(db):
    """Тестовый отдел."""
    return Department.objects.create(
        name="IT отдел",
        description="Отдел IT"
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
        send_activation_email=False,
    )
    EmployeeDepartment.objects.create(
        employee=user,
        department=department,
        is_active=True
    )
    return user


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
def category(db):
    """Категория оборудования."""
    return EquipmentCategory.objects.create(
        name="Ноутбуки",
        description="Портативные компьютеры",
        icon="bi-laptop"
    )


@pytest.fixture
def equipment(db, category, department, user):
    """Тестовое оборудование."""
    return Equipment.objects.create(
        name="Ноутбук Dell Latitude 5530",
        inventory_number="INV-2026-001",
        serial_number="SN123456789",
        category=category,
        status=EquipmentStatus.AVAILABLE,
        department=department,
        responsible_person=user,
        location="Офис 3.14",
        purchase_date=date(2026, 1, 15),
        warranty_until=date(2029, 1, 15),
        purchase_cost=Decimal("95000.00"),
        notes="Для разработки",
    )


# ==============================================================================
# ТЕСТЫ СПИСКА ОБОРУДОВАНИЯ
# ==============================================================================


class TestEquipmentList:
    """Тесты получения списка оборудования."""

    def test_list_unauthorized(self, api_client):
        """Неавторизованный доступ запрещен."""
        url = reverse('api:v1:procurement:equipment-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_equipment(
        self, api_client, user, equipment
    ):
        """Получение списка оборудования."""
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:equipment-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']
        assert len(results) >= 1
        
        # Проверяем структуру
        item = results[0]
        assert 'inventory_number' in item
        assert 'name' in item
        assert 'status' in item
        assert 'category_name' in item
        assert 'department_name' in item

    def test_filter_by_status(
        self, api_client, user, category, department, equipment
    ):
        """Фильтр по статусу."""
        # Создаем оборудование с разными статусами
        Equipment.objects.create(
            name="Монитор",
            inventory_number="INV-2026-002",
            category=category,
            status=EquipmentStatus.IN_USE,
            department=department,
            purchase_date=date.today(),
            purchase_cost=Decimal("20000.00"),
        )
        
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:equipment-list')
        
        # Фильтр AVAILABLE
        response = api_client.get(url, {'status': EquipmentStatus.AVAILABLE})
        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']
        assert all(r['status'] == EquipmentStatus.AVAILABLE for r in results)

    def test_filter_by_department(
        self, api_client, user, db, category, department, equipment
    ):
        """Фильтр по отделу."""
        other_dept = Department.objects.create(
            name="HR отдел",
            description="Другой отдел"
        )
        Equipment.objects.create(
            name="Принтер",
            inventory_number="INV-2026-003",
            category=category,
            status=EquipmentStatus.AVAILABLE,
            department=other_dept,
            purchase_date=date.today(),
            purchase_cost=Decimal("15000.00"),
        )
        
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:equipment-list')
        
        response = api_client.get(url, {'department': department.id})
        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']
        # Все должны быть из нужного отдела
        assert all(r['department'] == department.id for r in results)

    def test_search_equipment(
        self, api_client, user, equipment
    ):
        """Поиск оборудования."""
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:equipment-list')
        
        response = api_client.get(url, {'search': 'latitude'})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) >= 1


# ==============================================================================
# ТЕСТЫ СОЗДАНИЯ ОБОРУДОВАНИЯ
# ==============================================================================


class TestEquipmentCreate:
    """Тесты создания оборудования."""

    def test_create_equipment_as_staff(
        self, api_client, staff_user, category, department
    ):
        """Создание оборудования staff пользователем."""
        api_client.force_authenticate(user=staff_user)
        url = reverse('api:v1:procurement:equipment-list')
        
        data = {
            'name': 'Монитор LG 27"',
            'inventory_number': 'INV-2026-100',
            'serial_number': 'LG987654321',
            'category': category.id,
            'status': EquipmentStatus.AVAILABLE,
            'department': department.id,
            'location': 'Склад',
            'purchase_date': '2026-02-01',
            'warranty_until': '2029-02-01',
            'purchase_cost': '25000.00',
            'notes': 'Для офиса',
        }
        
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Монитор LG 27"'
        assert response.data['inventory_number'] == 'INV-2026-100'

    def test_create_equipment_regular_user_forbidden(
        self, api_client, user, category, department
    ):
        """Обычный пользователь не может создавать оборудование."""
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:equipment-list')
        
        data = {
            'name': 'Тестовое оборудование',
            'inventory_number': 'INV-2026-999',
            'category': category.id,
            'department': department.id,
            'purchase_date': '2026-02-01',
            'purchase_cost': '10000.00',
        }
        
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_equipment_duplicate_inventory_number(
        self, api_client, staff_user, category, department, equipment
    ):
        """Нельзя создать с дублирующим инвентарным номером."""
        api_client.force_authenticate(user=staff_user)
        url = reverse('api:v1:procurement:equipment-list')
        
        data = {
            'name': 'Другое оборудование',
            'inventory_number': equipment.inventory_number,  # Дубликат!
            'category': category.id,
            'department': department.id,
            'purchase_date': '2026-02-01',
            'purchase_cost': '10000.00',
        }
        
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ==============================================================================
# ТЕСТЫ ДЕТАЛЬНОЙ ИНФОРМАЦИИ
# ==============================================================================


class TestEquipmentDetail:
    """Тесты получения детальной информации об оборудовании."""

    def test_retrieve_equipment(
        self, api_client, user, equipment
    ):
        """Получение детальной информации."""
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:equipment-detail',
            kwargs={'pk': equipment.id}
        )
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == equipment.id
        assert response.data['name'] == equipment.name
        assert response.data['inventory_number'] == equipment.inventory_number
        assert 'is_under_warranty' in response.data
        assert response.data['is_under_warranty'] is True

    def test_retrieve_with_maintenance_history(
        self, api_client, user, equipment
    ):
        """Детальная информация включает историю ТО."""
        # Создаем записи об обслуживании
        MaintenanceRecord.objects.create(
            equipment=equipment,
            date=date.today() - timedelta(days=30),
            type=MaintenanceType.PLANNED,
            description="Плановое ТО",
            cost=Decimal("5000.00"),
            performed_by=user,
        )
        
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:equipment-detail',
            kwargs={'pk': equipment.id}
        )
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert 'maintenance_history' in response.data
        assert len(response.data['maintenance_history']) >= 1


# ==============================================================================
# ТЕСТЫ ОБНОВЛЕНИЯ ОБОРУДОВАНИЯ
# ==============================================================================


class TestEquipmentUpdate:
    """Тесты обновления оборудования."""

    def test_update_equipment_as_staff(
        self, api_client, staff_user, equipment
    ):
        """Обновление оборудования staff пользователем."""
        api_client.force_authenticate(user=staff_user)
        url = reverse(
            'api:v1:procurement:equipment-detail',
            kwargs={'pk': equipment.id}
        )
        
        data = {
            'location': 'Офис 4.01',
            'notes': 'Перемещено в новый офис',
        }
        response = api_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['location'] == 'Офис 4.01'
        assert 'новый офис' in response.data['notes'].lower()

    def test_update_equipment_regular_user_forbidden(
        self, api_client, user, equipment
    ):
        """Обычный пользователь не может обновлять."""
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:equipment-detail',
            kwargs={'pk': equipment.id}
        )
        
        data = {'location': 'Новое место'}
        response = api_client.patch(url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ==============================================================================
# ТЕСТЫ СПЕЦИАЛЬНЫХ ДЕЙСТВИЙ
# ==============================================================================


class TestEquipmentActions:
    """Тесты специальных действий с оборудованием."""

    def test_transfer_equipment(
        self, api_client, staff_user, equipment, db
    ):
        """Передача оборудования."""
        new_user = Employee.objects.create_user(
            email="newuser@example.com",
            password="testpass123",
            phone_number="+79995555555",
            first_name="Новый",
            last_name="Пользователь",
            send_activation_email=False,
        )
        
        api_client.force_authenticate(user=staff_user)
        url = reverse(
            'api:v1:procurement:equipment-transfer',
            kwargs={'pk': equipment.id}
        )
        
        data = {
            'to_person': new_user.id,
            'to_location': 'Офис 2.10',
            'reason': 'Перевод в другой отдел',
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        
        # Проверяем что ответственный изменился
        equipment.refresh_from_db()
        assert equipment.responsible_person == new_user
        assert equipment.location == 'Офис 2.10'

    def test_generate_qr_code(
        self, api_client, user, equipment
    ):
        """Генерация QR-кода."""
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:equipment-qr-code',
            kwargs={'pk': equipment.id}
        )
        
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        assert 'qr_code' in response.data
        # QR код должен быть в base64
        assert response.data['qr_code'].startswith('data:image/')


# ==============================================================================
# ТЕСТЫ КАТЕГОРИЙ
# ==============================================================================


class TestEquipmentCategories:
    """Тесты API категорий оборудования."""

    def test_list_categories(
        self, api_client, user, category
    ):
        """Список категорий."""
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:equipmentcategory-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) >= 1

    def test_create_category_as_staff(
        self, api_client, staff_user
    ):
        """Создание категории staff пользователем."""
        api_client.force_authenticate(user=staff_user)
        url = reverse('api:v1:procurement:equipmentcategory-list')
        
        data = {
            'name': 'Мониторы',
            'description': 'Все виды мониторов',
            'icon': 'bi-display',
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Мониторы'

    def test_hierarchical_categories(
        self, api_client, staff_user, category
    ):
        """Создание подкатегории."""
        api_client.force_authenticate(user=staff_user)
        url = reverse('api:v1:procurement:equipmentcategory-list')
        
        data = {
            'name': 'Игровые ноутбуки',
            'parent': category.id,
            'description': 'Высокопроизводительные ноутбуки',
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['parent'] == category.id
