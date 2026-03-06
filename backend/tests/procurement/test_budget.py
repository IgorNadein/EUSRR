"""
Тесты для Budget - reserved_amount, my_department, stats endpoints.
"""
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth.models import Permission

import pytest
from rest_framework import status

from procurement.models import (
    Budget,
    ProcurementRequest,
    ProcurementItem,
)
from procurement.constants import ProcurementStatus, UrgencyLevel


@pytest.mark.django_db
class TestBudgetReservedAmount:
    """Тесты для reserved_amount и available_amount."""

    @pytest.fixture(autouse=True)
    def setup(self, department_factory, user_factory, link_factory):
        """Настройка тестовых данных."""
        self.department = department_factory(name='IT Reserved Test')
        now = timezone.now()
        self.quarter = (now.month - 1) // 3 + 1
        
        self.budget = Budget.objects.create(
            department=self.department,
            year=now.year,
            quarter=self.quarter,
            allocated_amount=Decimal('100000.00'),
            spent_amount=Decimal('20000.00'),
        )
        
        self.user = user_factory(
            email='budgetuser@test.com',
            first_name='Test',
            last_name='User',
        )
        link_factory(self.user, self.department, is_active=True)

    def test_reserved_amount_no_pending(self):
        """Тест: reserved_amount = 0 если нет pending заявок."""
        assert self.budget.reserved_amount == Decimal('0.00')

    def test_reserved_amount_with_pending(self):
        """Тест: reserved_amount считает сумму pending заявок."""
        # Создаём pending заявки с позициями
        request1 = ProcurementRequest.objects.create(
            title='Заявка 1',
            description='Описание',
            department=self.department,
            requestor=self.user,
            status=ProcurementStatus.PENDING,
            urgency=UrgencyLevel.LOW,
        )
        ProcurementItem.objects.create(
            request=request1,
            name='Товар 1',
            quantity=1,
            unit='шт',
            estimated_unit_price=Decimal('5000.00'),
        )
        
        request2 = ProcurementRequest.objects.create(
            title='Заявка 2',
            description='Описание',
            department=self.department,
            requestor=self.user,
            status=ProcurementStatus.PENDING,
            urgency=UrgencyLevel.MEDIUM,
        )
        ProcurementItem.objects.create(
            request=request2,
            name='Товар 2',
            quantity=1,
            unit='шт',
            estimated_unit_price=Decimal('3000.00'),
        )
        
        # reserved должен быть 8000
        assert self.budget.reserved_amount == Decimal('8000.00')

    def test_available_amount(self):
        """Тест: available_amount = remaining - reserved."""
        request = ProcurementRequest.objects.create(
            title='Pending заявка',
            description='Описание',
            department=self.department,
            requestor=self.user,
            status=ProcurementStatus.PENDING,
            urgency=UrgencyLevel.LOW,
        )
        ProcurementItem.objects.create(
            request=request,
            name='Товар',
            quantity=1,
            unit='шт',
            estimated_unit_price=Decimal('10000.00'),
        )
        
        # remaining = 100000 - 20000 = 80000
        # reserved = 10000
        # available = 80000 - 10000 = 70000
        assert self.budget.remaining_amount == Decimal('80000.00')
        assert self.budget.reserved_amount == Decimal('10000.00')
        assert self.budget.available_amount == Decimal('70000.00')


@pytest.mark.django_db
class TestBudgetMyDepartmentEndpoint:
    """Тесты для /budgets/my-department/ endpoint."""

    @pytest.fixture(autouse=True)
    def setup(
        self, api_client, department_factory, user_factory, link_factory
    ):
        """Настройка тестовых данных."""
        self.client = api_client
        
        self.department = department_factory(name='IT My Dept Test')
        
        now = timezone.now()
        self.quarter = (now.month - 1) // 3 + 1
        
        self.budget = Budget.objects.create(
            department=self.department,
            year=now.year,
            quarter=self.quarter,
            allocated_amount=Decimal('100000.00'),
            spent_amount=Decimal('30000.00'),
        )
        
        self.user = user_factory(
            email='mydeptuser@test.com',
            first_name='Test',
            last_name='User',
        )
        link_factory(self.user, self.department, is_active=True)
        self.user_factory = user_factory

    def test_my_department_success(self):
        """Тест: получение бюджета своего отдела."""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.get('/api/procurement/budgets/my-department/')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['department'] == self.department.id
        allocated = Decimal(response.data['allocated_amount'])
        assert allocated == Decimal('100000.00')
        spent = Decimal(response.data['spent_amount'])
        assert spent == Decimal('30000.00')
        remaining = Decimal(response.data['remaining_amount'])
        assert remaining == Decimal('70000.00')
        assert 'reserved_amount' in response.data
        assert 'available_amount' in response.data

    def test_my_department_no_department(self):
        """Тест: 404 если пользователь не в отделе."""
        user_no_dept = self.user_factory(
            email='nodept@test.com',
            first_name='No',
            last_name='Dept',
        )
        self.client.force_authenticate(user=user_no_dept)
        
        response = self.client.get('/api/procurement/budgets/my-department/')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_my_department_no_budget(self):
        """Тест: 404 если нет бюджета на текущий квартал."""
        # Удаляем бюджет
        self.budget.delete()
        
        self.client.force_authenticate(user=self.user)
        
        response = self.client.get('/api/procurement/budgets/my-department/')
        
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestProcurementStatsEndpoints:
    """Тесты для /stats/ endpoints."""

    @pytest.fixture(autouse=True)
    def setup(
        self, api_client, department_factory, user_factory, link_factory
    ):
        """Настройка тестовых данных."""
        self.client = api_client
        
        self.department = department_factory(name='IT Stats Test')
        
        self.user = user_factory(
            email='statsuser@test.com',
            first_name='Test',
            last_name='User',
        )
        link_factory(self.user, self.department, is_active=True)
        
        self.staff_user = user_factory(
            email='statsstaff@test.com',
            first_name='Staff',
            last_name='User',
        )
        self.staff_user.is_staff = True
        self.staff_user.save()
        
        # Создаём несколько заявок
        for i in range(3):
            ProcurementRequest.objects.create(
                title=f'Заявка {i+1}',
                description='Описание',
                department=self.department,
                requestor=self.user,
                status=ProcurementStatus.PENDING,
                urgency=UrgencyLevel.MEDIUM,
            )

    def test_stats_overview(self):
        """Тест: получение общей статистики."""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.get('/api/procurement/stats/overview/')
        
        assert response.status_code == status.HTTP_200_OK
        assert 'total_requests' in response.data
        assert 'pending_requests' in response.data
        assert 'by_status' in response.data
        assert 'by_urgency' in response.data

    def test_stats_by_department_staff(self):
        """Тест: статистика по отделам для staff."""
        self.client.force_authenticate(user=self.staff_user)
        
        response = self.client.get('/api/procurement/stats/by-department/')
        
        assert response.status_code == status.HTTP_200_OK
        assert isinstance(response.data, list)

    def test_stats_by_department_regular_user(self):
        """Тест: 403 для обычного пользователя."""
        self.client.force_authenticate(user=self.user)
        
        response = self.client.get('/api/procurement/stats/by-department/')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_stats_by_department_head(self):
        """Тест: руководитель отдела видит статистику своих отделов."""
        # Делаем пользователя руководителем
        self.department.head = self.user
        self.department.save()
        
        self.client.force_authenticate(user=self.user)
        
        response = self.client.get('/api/procurement/stats/by-department/')
        
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]['department']['id'] == self.department.id


@pytest.mark.django_db
class TestBudgetAlerts:
    """Тесты для алертов бюджета."""

    @pytest.fixture(autouse=True)
    def setup(
        self, api_client, department_factory, user_factory, link_factory
    ):
        """Настройка тестовых данных."""
        self.client = api_client
        
        self.department = department_factory(name='IT Alerts Test')
        
        now = timezone.now()
        self.quarter = (now.month - 1) // 3 + 1
        
        # Бюджет почти исчерпан (95% использовано)
        self.budget = Budget.objects.create(
            department=self.department,
            year=now.year,
            quarter=self.quarter,
            allocated_amount=Decimal('100000.00'),
            spent_amount=Decimal('95000.00'),  # 95% использовано
        )
        
        self.requestor = user_factory(
            email='alertsrequestor@test.com',
            first_name='Requestor',
            last_name='User',
        )
        link_factory(self.requestor, self.department, is_active=True)
        
        # Руководитель отдела
        self.dept_head = user_factory(
            email='alertshead@test.com',
            first_name='Department',
            last_name='Head',
        )
        link_factory(self.dept_head, self.department, is_active=True)
        self.department.head = self.dept_head
        self.department.save()
        
        # Даём права на approve
        perm = Permission.objects.get(codename='approve_procurementrequest')
        self.dept_head.user_permissions.add(perm)

    def test_budget_utilization_above_90(self):
        """Тест: бюджет используется более чем на 90%."""
        assert self.budget.utilization_percentage == Decimal('95.00')
        assert self.budget.remaining_amount == Decimal('5000.00')
