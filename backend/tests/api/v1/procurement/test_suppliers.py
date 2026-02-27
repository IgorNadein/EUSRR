"""
Тесты API для поставщиков (Supplier).
"""

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from employees.models import Employee
from procurement.models import Supplier


pytestmark = pytest.mark.django_db


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
def supplier(db):
    """Тестовый поставщик."""
    return Supplier.objects.create(
        name="ООО \"Компьютеры\"",
        contact_person="Иванов Иван",
        phone="+79991234567",
        email="info@computers.ru",
        website="https://computers.ru",
        inn="7701234567",
        address="Москва, ул. Ленина, д. 1",
        rating=Decimal("4.50"),
        is_active=True,
        notes="Основной поставщик IT-оборудования",
    )


# ==============================================================================
# ТЕСТЫ СПИСКА ПОСТАВЩИКОВ
# ==============================================================================


class TestSupplierList:
    """Тесты получения списка поставщиков."""

    def test_list_unauthorized(self, api_client):
        """Неавторизованный доступ запрещен."""
        url = reverse('api:v1:procurement:supplier-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_suppliers(
        self, api_client, user, supplier
    ):
        """Получение списка поставщиков."""
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:supplier-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']
        assert len(results) >= 1
        
        # Проверяем структуру
        item = results[0]
        assert 'name' in item
        assert 'contact_person' in item
        assert 'phone' in item
        assert 'email' in item
        assert 'rating' in item
        assert 'is_active' in item

    def test_search_suppliers(
        self, api_client, user, supplier
    ):
        """Поиск поставщиков."""
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:supplier-list')
        
        response = api_client.get(url, {'search': 'компьютер'})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) >= 1

    def test_filter_active_suppliers(
        self, api_client, user, db
    ):
        """Фильтр только активных поставщиков."""
        # Создаем активного и неактивного
        Supplier.objects.create(
            name="Активный поставщик",
            is_active=True,
        )
        Supplier.objects.create(
            name="Неактивный поставщик",
            is_active=False,
        )
        
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:supplier-list')
        
        response = api_client.get(url, {'is_active': 'true'})
        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']
        assert all(r['is_active'] for r in results)


# ==============================================================================
# ТЕСТЫ СОЗДАНИЯ ПОСТАВЩИКА
# ==============================================================================


class TestSupplierCreate:
    """Тесты создания поставщика."""

    def test_create_supplier_as_staff(
        self, api_client, staff_user
    ):
        """Создание поставщика staff пользователем."""
        api_client.force_authenticate(user=staff_user)
        url = reverse('api:v1:procurement:supplier-list')
        
        data = {
            'name': 'ООО "Новый поставщик"',
            'contact_person': 'Петров Петр',
            'phone': '+79997654321',
            'email': 'new@supplier.ru',
            'website': 'https://newsupplier.ru',
            'inn': '7707654321',
            'address': 'Санкт-Петербург, Невский пр., д. 10',
            'rating': '5.00',
            'notes': 'Проверенный поставщик',
        }
        
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'ООО "Новый поставщик"'
        assert response.data['inn'] == '7707654321'

    def test_create_supplier_regular_user_forbidden(
        self, api_client, user
    ):
        """Обычный пользователь не может создавать поставщиков."""
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:supplier-list')
        
        data = {
            'name': 'Тестовый поставщик',
            'email': 'test@supplier.ru',
        }
        
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_supplier_minimum_data(
        self, api_client, staff_user
    ):
        """Создание поставщика с минимальными данными."""
        api_client.force_authenticate(user=staff_user)
        url = reverse('api:v1:procurement:supplier-list')
        
        data = {
            'name': 'Минимальный поставщик',
        }
        
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['name'] == 'Минимальный поставщик'
        assert response.data['is_active'] is True  # По умолчанию


# ==============================================================================
# ТЕСТЫ ДЕТАЛЬНОЙ ИНФОРМАЦИИ
# ==============================================================================


class TestSupplierDetail:
    """Тесты получения детальной информации о поставщике."""

    def test_retrieve_supplier(
        self, api_client, user, supplier
    ):
        """Получение детальной информации."""
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:supplier-detail',
            kwargs={'pk': supplier.id}
        )
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == supplier.id
        assert response.data['name'] == supplier.name
        assert response.data['inn'] == supplier.inn
        assert Decimal(response.data['rating']) == supplier.rating


# ==============================================================================
# ТЕСТЫ ОБНОВЛЕНИЯ ПОСТАВЩИКА
# ==============================================================================


class TestSupplierUpdate:
    """Тесты обновления поставщика."""

    def test_update_supplier_as_staff(
        self, api_client, staff_user, supplier
    ):
        """Обновление поставщика staff пользователем."""
        api_client.force_authenticate(user=staff_user)
        url = reverse(
            'api:v1:procurement:supplier-detail',
            kwargs={'pk': supplier.id}
        )
        
        data = {
            'rating': '4.80',
            'notes': 'Обновленная информация о поставщике',
        }
        response = api_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert Decimal(response.data['rating']) == Decimal('4.80')
        assert 'Обновленная' in response.data['notes']

    def test_update_supplier_regular_user_forbidden(
        self, api_client, user, supplier
    ):
        """Обычный пользователь не может обновлять поставщиков."""
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:supplier-detail',
            kwargs={'pk': supplier.id}
        )
        
        data = {'rating': '5.00'}
        response = api_client.patch(url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_deactivate_supplier(
        self, api_client, staff_user, supplier
    ):
        """Деактивация поставщика."""
        api_client.force_authenticate(user=staff_user)
        url = reverse(
            'api:v1:procurement:supplier-detail',
            kwargs={'pk': supplier.id}
        )
        
        data = {'is_active': False}
        response = api_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['is_active'] is False


# ==============================================================================
# ТЕСТЫ УДАЛЕНИЯ
# ==============================================================================


class TestSupplierDelete:
    """Тесты удаления поставщика."""

    def test_delete_supplier_as_staff(
        self, api_client, staff_user, supplier
    ):
        """Удаление поставщика staff пользователем."""
        api_client.force_authenticate(user=staff_user)
        url = reverse(
            'api:v1:procurement:supplier-detail',
            kwargs={'pk': supplier.id}
        )
        
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Supplier.objects.filter(id=supplier.id).exists()

    def test_delete_supplier_regular_user_forbidden(
        self, api_client, user, supplier
    ):
        """Обычный пользователь не может удалять поставщиков."""
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:supplier-detail',
            kwargs={'pk': supplier.id}
        )
        
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Supplier.objects.filter(id=supplier.id).exists()


# ==============================================================================
# ТЕСТЫ БИЗНЕС-ЛОГИКИ
# ==============================================================================


class TestSupplierBusinessLogic:
    """Тесты бизнес-логики поставщиков."""

    def test_rating_validation(
        self, api_client, staff_user
    ):
        """Валидация рейтинга (не может быть отрицательным)."""
        api_client.force_authenticate(user=staff_user)
        url = reverse('api:v1:procurement:supplier-list')
        
        data = {
            'name': 'Поставщик с плохим рейтингом',
            'rating': '-1.00',
        }
        
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_inn_format(
        self, api_client, staff_user, supplier
    ):
        """ИНН должен быть корректным (10 или 12 цифр)."""
        api_client.force_authenticate(user=staff_user)
        url = reverse(
            'api:v1:procurement:supplier-detail',
            kwargs={'pk': supplier.id}
        )
        
        # ИНН из 10 цифр - валиден
        data = {'inn': '1234567890'}
        response = api_client.patch(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
        
        # ИНН из 12 цифр - валиден
        data = {'inn': '123456789012'}
        response = api_client.patch(url, data, format='json')
        assert response.status_code == status.HTTP_200_OK
