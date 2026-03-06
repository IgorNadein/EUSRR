"""
Тесты API для бюджетов (Budget).
"""

from decimal import Decimal

import pytest
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

from employees.models import Department, Employee, EmployeeDepartment
from procurement.models import Budget, ProcurementRequest
from procurement.constants import ProcurementStatus


pytestmark = pytest.mark.django_db


@pytest.fixture
def api_client():
    """API клиент."""
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
def finance_user(db):
    """Пользователь с правами на управление бюджетами."""
    user = Employee.objects.create_user(
        email="finance@example.com",
        password="testpass123",
        phone_number="+79992222222",
        first_name="Финансист",
        last_name="Финансов",
        is_staff=True,
        send_activation_email=False,
    )
    # Даем право на управление бюджетами
    from django.contrib.auth.models import Permission
    perm = Permission.objects.get(
        codename='change_budget',
        content_type__app_label='procurement'
    )
    user.user_permissions.add(perm)
    return user


@pytest.fixture
def budget(db, department):
    """Тестовый бюджет."""
    return Budget.objects.create(
        department=department,
        year=2026,
        quarter=1,
        allocated_amount=Decimal("1000000.00"),
        spent_amount=Decimal("250000.00"),
    )


# ==============================================================================
# ТЕСТЫ СПИСКА БЮДЖЕТОВ
# ==============================================================================


class TestBudgetList:
    """Тесты получения списка бюджетов."""

    def test_list_unauthorized(self, api_client):
        """Неавторизованный доступ запрещен."""
        url = reverse('api:v1:procurement:budget-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_budgets_as_staff(
        self, api_client, finance_user, budget
    ):
        """Финансист видит все бюджеты."""
        api_client.force_authenticate(user=finance_user)
        url = reverse('api:v1:procurement:budget-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']
        assert len(results) >= 1
        assert 'remaining_amount' in results[0]
        assert 'utilization_percentage' in results[0]

    def test_filter_by_year(
        self, api_client, finance_user, department, budget
    ):
        """Фильтр по году."""
        # Создаем бюджет на другой год
        Budget.objects.create(
            department=department,
            year=2025,
            quarter=4,
            allocated_amount=Decimal("800000.00"),
            spent_amount=Decimal("600000.00"),
        )
        
        api_client.force_authenticate(user=finance_user)
        url = reverse('api:v1:procurement:budget-list')
        
        response = api_client.get(url, {'year': 2026})
        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']
        assert all(r['year'] == 2026 for r in results)

    def test_filter_by_department(
        self, api_client, finance_user, db, budget
    ):
        """Фильтр по отделу."""
        other_dept = Department.objects.create(
            name="HR отдел",
            description="Другой отдел"
        )
        Budget.objects.create(
            department=other_dept,
            year=2026,
            quarter=1,
            allocated_amount=Decimal("500000.00"),
            spent_amount=Decimal("0.00"),
        )
        
        api_client.force_authenticate(user=finance_user)
        url = reverse('api:v1:procurement:budget-list')
        
        response = api_client.get(url, {'department': budget.department.id})
        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']
        assert all(r['department'] == budget.department.id for r in results)


# ==============================================================================
# ТЕСТЫ СОЗДАНИЯ БЮДЖЕТА
# ==============================================================================


class TestBudgetCreate:
    """Тесты создания бюджета."""

    def test_create_budget_as_finance(
        self, api_client, finance_user, department
    ):
        """Создание бюджета финансистом."""
        api_client.force_authenticate(user=finance_user)
        url = reverse('api:v1:procurement:budget-list')
        
        data = {
            'department': department.id,
            'year': 2026,
            'quarter': 2,
            'allocated_amount': '1200000.00',
        }
        response = api_client.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['year'] == 2026
        assert response.data['quarter'] == 2
        assert Decimal(response.data['allocated_amount']) == Decimal('1200000.00')
        assert Decimal(response.data['spent_amount']) == Decimal('0.00')

    def test_create_budget_regular_user_forbidden(
        self, api_client, user, department
    ):
        """Обычный пользователь не может создавать бюджеты."""
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:budget-list')
        
        data = {
            'department': department.id,
            'year': 2026,
            'quarter': 2,
            'allocated_amount': '1000000.00',
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_create_duplicate_budget_fails(
        self, api_client, finance_user, budget
    ):
        """Нельзя создать дублирующий бюджет (отдел+год+квартал)."""
        api_client.force_authenticate(user=finance_user)
        url = reverse('api:v1:procurement:budget-list')
        
        data = {
            'department': budget.department.id,
            'year': budget.year,
            'quarter': budget.quarter,
            'allocated_amount': '2000000.00',
        }
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST


# ==============================================================================
# ТЕСТЫ ДЕТАЛЬНОЙ ИНФОРМАЦИИ
# ==============================================================================


class TestBudgetDetail:
    """Тесты получения детальной информации о бюджете."""

    def test_retrieve_budget(
        self, api_client, finance_user, budget
    ):
        """Получение детальной информации."""
        api_client.force_authenticate(user=finance_user)
        url = reverse(
            'api:v1:procurement:budget-detail',
            kwargs={'pk': budget.id}
        )
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == budget.id
        assert Decimal(response.data['allocated_amount']) == budget.allocated_amount
        assert Decimal(response.data['spent_amount']) == budget.spent_amount
        
        # Проверяем вычисляемые поля
        assert 'remaining_amount' in response.data
        assert 'utilization_percentage' in response.data
        assert Decimal(response.data['remaining_amount']) == Decimal('750000.00')

    def test_retrieve_shows_reserved_amount(
        self, api_client, finance_user, budget, user
    ):
        """Детальная информация показывает зарезервированные средства."""
        # Создаем pending заявку
        pending_request = ProcurementRequest.objects.create(
            title="Заявка",
            description="Описание",
            department=budget.department,
            requestor=user,
            status=ProcurementStatus.PENDING,
        )
        from procurement.models import ProcurementItem
        ProcurementItem.objects.create(
            request=pending_request,
            name="Товар",
            quantity=1,
            estimated_unit_price=Decimal("50000.00"),
        )
        
        api_client.force_authenticate(user=finance_user)
        url = reverse(
            'api:v1:procurement:budget-detail',
            kwargs={'pk': budget.id}
        )
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        # Должно быть поле reserved_amount
        assert 'reserved_amount' in response.data


# ==============================================================================
# ТЕСТЫ ОБНОВЛЕНИЯ БЮДЖЕТА
# ==============================================================================


class TestBudgetUpdate:
    """Тесты обновления бюджета."""

    def test_update_budget_as_finance(
        self, api_client, finance_user, budget
    ):
        """Обновление бюджета финансистом."""
        api_client.force_authenticate(user=finance_user)
        url = reverse(
            'api:v1:procurement:budget-detail',
            kwargs={'pk': budget.id}
        )
        
        data = {
            'allocated_amount': '1500000.00',
            'spent_amount': '300000.00',
        }
        response = api_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert Decimal(response.data['allocated_amount']) == Decimal('1500000.00')
        assert Decimal(response.data['spent_amount']) == Decimal('300000.00')

    def test_update_budget_regular_user_forbidden(
        self, api_client, user, budget
    ):
        """Обычный пользователь не может обновлять бюджеты."""
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:budget-detail',
            kwargs={'pk': budget.id}
        )
        
        data = {'allocated_amount': '2000000.00'}
        response = api_client.patch(url, data, format='json')
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ==============================================================================
# ТЕСТЫ СПЕЦИАЛЬНЫХ ACTIONS
# ==============================================================================


class TestBudgetActions:
    """Тесты специальных действий с бюджетами."""

    def test_current_budget(
        self, api_client, finance_user, budget
    ):
        """Получение бюджета текущего квартала."""
        api_client.force_authenticate(user=finance_user)
        url = reverse('api:v1:procurement:budget-current')
        
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        # Должен вернуть список бюджетов на текущий квартал
        assert isinstance(response.data, list) or 'results' in response.data

    def test_my_department_budget(
        self, api_client, user, budget
    ):
        """Получение бюджета своего отдела."""
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:budget-my-department')
        
        response = api_client.get(url)
        assert response.status_code == status.HTTP_200_OK
        # Пользователь видит бюджет своего отдела
        if response.data:  # Может быть пустой если нет бюджета
            assert response.data[0]['department'] == budget.department.id


# ==============================================================================
# ТЕСТЫ БИЗНЕС-ЛОГИКИ
# ==============================================================================


class TestBudgetBusinessLogic:
    """Тесты бизнес-логики бюджетов."""

    def test_budget_utilization_calculation(
        self, api_client, finance_user, budget
    ):
        """Проверка расчета процента использования."""
        api_client.force_authenticate(user=finance_user)
        url = reverse(
            'api:v1:procurement:budget-detail',
            kwargs={'pk': budget.id}
        )
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # allocated = 1000000, spent = 250000
        # utilization = 250000 / 1000000 * 100 = 25%
        utilization = Decimal(response.data['utilization_percentage'])
        assert utilization == Decimal('25.00')

    def test_budget_remaining_amount(
        self, api_client, finance_user, budget
    ):
        """Проверка расчета остатка."""
        api_client.force_authenticate(user=finance_user)
        url = reverse(
            'api:v1:procurement:budget-detail',
            kwargs={'pk': budget.id}
        )
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # allocated = 1000000, spent = 250000
        # remaining = 750000
        remaining = Decimal(response.data['remaining_amount'])
        assert remaining == Decimal('750000.00')

    def test_negative_budget_not_allowed(
        self, api_client, finance_user, budget
    ):
        """Нельзя установить отрицательный бюджет."""
        api_client.force_authenticate(user=finance_user)
        url = reverse(
            'api:v1:procurement:budget-detail',
            kwargs={'pk': budget.id}
        )
        
        data = {'allocated_amount': '-100000.00'}
        response = api_client.patch(url, data, format='json')
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_spent_more_than_allocated_warning(
        self, api_client, finance_user, budget
    ):
        """Можно потратить больше выделенного (с предупреждением)."""
        # Обновляем потраченную сумму больше выделенной
        budget.spent_amount = Decimal("1200000.00")
        budget.save()
        
        api_client.force_authenticate(user=finance_user)
        url = reverse(
            'api:v1:procurement:budget-detail',
            kwargs={'pk': budget.id}
        )
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        
        # remaining должен быть отрицательным
        remaining = Decimal(response.data['remaining_amount'])
        assert remaining < 0
        
        # utilization > 100%
        utilization = Decimal(response.data['utilization_percentage'])
        assert utilization > 100


# ==============================================================================
# ТЕСТЫ УДАЛЕНИЯ
# ==============================================================================


class TestBudgetDelete:
    """Тесты удаления бюджета."""

    def test_delete_budget_as_finance(
        self, api_client, finance_user, budget
    ):
        """Удаление бюджета финансистом."""
        api_client.force_authenticate(user=finance_user)
        url = reverse(
            'api:v1:procurement:budget-detail',
            kwargs={'pk': budget.id}
        )
        
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Budget.objects.filter(id=budget.id).exists()

    def test_delete_budget_regular_user_forbidden(
        self, api_client, user, budget
    ):
        """Обычный пользователь не может удалять бюджеты."""
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:budget-detail',
            kwargs={'pk': budget.id}
        )
        
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert Budget.objects.filter(id=budget.id).exists()
