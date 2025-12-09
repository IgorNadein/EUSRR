"""
Тесты для моделей модуля закупок.
"""

from datetime import date, timedelta
from decimal import Decimal

import pytest
from django.contrib.auth import get_user_model

from employees.models import Department
from procurement.constants import (
    ApprovalRole,
    EquipmentStatus,
    ProcurementStatus,
    UrgencyLevel,
)
from procurement.models import (
    Budget,
    Equipment,
    EquipmentCategory,
    ProcurementItem,
    ProcurementRequest,
    Supplier,
)

User = get_user_model()


@pytest.fixture
def department(db):
    """Создать тестовый отдел."""
    return Department.objects.create(
        name="Тестовый отдел", description="Для тестов"
    )


@pytest.fixture
def user(db):
    """Создать тестового пользователя."""
    return User.objects.create_user(
        email="test@example.com",
        password="testpass123",
        phone_number="+79991234567",
        send_activation_email=False,
        first_name="Тест",
        last_name="Тестов",
    )


@pytest.fixture
def budget(db, department):
    """Создать тестовый бюджет."""
    # Создаем бюджет для текущего квартала
    from django.utils import timezone
    now = timezone.now()
    quarter = (now.month - 1) // 3 + 1
    
    return Budget.objects.create(
        department=department,
        year=now.year,
        quarter=quarter,
        allocated_amount=Decimal("100000.00"),
        spent_amount=Decimal("30000.00"),
    )


@pytest.mark.django_db
class TestProcurementRequest:
    """Тесты модели ProcurementRequest."""

    def test_create_procurement_request(self, department, user):
        """Тест создания заявки на закупку."""
        request = ProcurementRequest.objects.create(
            title="Покупка ноутбуков",
            description="Нужны 5 ноутбуков для отдела",
            department=department,
            requestor=user,
            status=ProcurementStatus.DRAFT,
            urgency=UrgencyLevel.MEDIUM,
            estimated_cost=Decimal("250000.00"),
        )

        assert request.id is not None
        assert request.title == "Покупка ноутбуков"
        assert request.is_editable is True
        assert request.items_count == 0

    def test_get_required_approvals_low(self, department, user):
        """Тест получения уровней согласования для малой суммы."""
        request = ProcurementRequest.objects.create(
            title="Канцтовары",
            department=department,
            requestor=user,
            estimated_cost=Decimal("5000.00"),
        )

        approvals = request.get_required_approvals()
        assert len(approvals) == 1
        assert ApprovalRole.DEPARTMENT_HEAD in approvals

    def test_get_required_approvals_medium(self, department, user):
        """Тест получения уровней согласования для средней суммы."""
        request = ProcurementRequest.objects.create(
            title="Оргтехника",
            department=department,
            requestor=user,
            estimated_cost=Decimal("30000.00"),
        )

        approvals = request.get_required_approvals()
        assert len(approvals) == 2
        assert ApprovalRole.DEPARTMENT_HEAD in approvals
        assert ApprovalRole.FINANCE_MANAGER in approvals

    def test_get_required_approvals_high(self, department, user):
        """Тест получения уровней согласования для большой суммы."""
        request = ProcurementRequest.objects.create(
            title="Серверное оборудование",
            department=department,
            requestor=user,
            estimated_cost=Decimal("500000.00"),
        )

        approvals = request.get_required_approvals()
        assert len(approvals) == 3
        assert ApprovalRole.DEPARTMENT_HEAD in approvals
        assert ApprovalRole.FINANCE_MANAGER in approvals
        assert ApprovalRole.DIRECTOR in approvals

    def test_check_budget_available(self, department, user, budget):
        """Тест проверки доступности бюджета."""
        request = ProcurementRequest.objects.create(
            title="Покупка",
            department=department,
            requestor=user,
            estimated_cost=Decimal("50000.00"),
        )

        available, remaining = request.check_budget_available()
        assert available is True
        assert remaining == Decimal("70000.00")

    def test_is_editable_draft(self, department, user):
        """Тест: черновик можно редактировать."""
        request = ProcurementRequest.objects.create(
            title="Черновик",
            department=department,
            requestor=user,
            status=ProcurementStatus.DRAFT,
        )

        assert request.is_editable is True

    def test_is_not_editable_pending(self, department, user):
        """Тест: заявку на согласовании редактировать нельзя."""
        request = ProcurementRequest.objects.create(
            title="На согласовании",
            department=department,
            requestor=user,
            status=ProcurementStatus.PENDING,
        )

        assert request.is_editable is False


@pytest.mark.django_db
class TestProcurementItem:
    """Тесты модели ProcurementItem."""

    def test_create_procurement_item(self, department, user):
        """Тест создания позиции заявки."""
        request = ProcurementRequest.objects.create(
            title="Заявка", department=department, requestor=user
        )

        item = ProcurementItem.objects.create(
            request=request,
            name="Ноутбук Dell XPS 15",
            quantity=3,
            unit="шт",
            estimated_unit_price=Decimal("80000.00"),
        )

        assert item.id is not None
        assert item.total_price == Decimal("240000.00")
        assert request.items_count == 1

    def test_total_price_calculation(self, department, user):
        """Тест расчета общей стоимости позиции."""
        request = ProcurementRequest.objects.create(
            title="Заявка", department=department, requestor=user
        )

        item = ProcurementItem.objects.create(
            request=request,
            name="Кабель HDMI",
            quantity=10,
            unit="шт",
            estimated_unit_price=Decimal("500.50"),
        )

        assert item.total_price == Decimal("5005.00")


@pytest.mark.django_db
class TestBudget:
    """Тесты модели Budget."""

    def test_create_budget(self, department):
        """Тест создания бюджета."""
        budget = Budget.objects.create(
            department=department,
            year=2025,
            quarter=2,
            allocated_amount=Decimal("200000.00"),
        )

        assert budget.id is not None
        assert budget.remaining_amount == Decimal("200000.00")
        assert budget.utilization_percentage == Decimal("0.00")

    def test_remaining_amount(self, budget):
        """Тест расчета остатка бюджета."""
        assert budget.remaining_amount == Decimal("70000.00")

    def test_utilization_percentage(self, budget):
        """Тест расчета процента использования."""
        assert budget.utilization_percentage == Decimal("30.00")

    def test_can_spend_true(self, budget):
        """Тест: можно потратить сумму в пределах бюджета."""
        assert budget.can_spend(Decimal("50000.00")) is True

    def test_can_spend_false(self, budget):
        """Тест: нельзя потратить сумму сверх бюджета."""
        assert budget.can_spend(Decimal("80000.00")) is False


@pytest.mark.django_db
class TestEquipment:
    """Тесты модели Equipment."""

    def test_create_equipment(self, department, user):
        """Тест создания оборудования."""
        category = EquipmentCategory.objects.create(name="Компьютеры")

        equipment = Equipment.objects.create(
            name="Ноутбук Dell",
            inventory_number="INV-2025-0001",
            serial_number="SN123456",
            category=category,
            status=EquipmentStatus.AVAILABLE,
            department=department,
            responsible_person=user,
            purchase_date=date.today(),
            warranty_until=date.today() + timedelta(days=365),
            purchase_cost=Decimal("80000.00"),
        )

        assert equipment.id is not None
        assert equipment.is_under_warranty is True
        assert str(equipment) == "INV-2025-0001 - Ноутбук Dell"

    def test_is_under_warranty_true(self, department, user):
        """Тест: оборудование на гарантии."""
        category = EquipmentCategory.objects.create(name="Техника")
        equipment = Equipment.objects.create(
            name="Принтер",
            inventory_number="INV-2025-0002",
            category=category,
            department=department,
            purchase_date=date.today(),
            warranty_until=date.today() + timedelta(days=30),
            purchase_cost=Decimal("20000.00"),
        )

        assert equipment.is_under_warranty is True

    def test_is_under_warranty_false(self, department, user):
        """Тест: гарантия истекла."""
        category = EquipmentCategory.objects.create(name="Техника")
        equipment = Equipment.objects.create(
            name="Старый принтер",
            inventory_number="INV-2024-0001",
            category=category,
            department=department,
            purchase_date=date.today() - timedelta(days=400),
            warranty_until=date.today() - timedelta(days=35),
            purchase_cost=Decimal("20000.00"),
        )

        assert equipment.is_under_warranty is False


@pytest.mark.django_db
class TestEquipmentCategory:
    """Тесты модели EquipmentCategory."""

    def test_create_category(self):
        """Тест создания категории."""
        category = EquipmentCategory.objects.create(
            name="Оргтехника", description="Принтеры, сканеры"
        )

        assert category.id is not None
        assert category.full_path == "Оргтехника"

    def test_hierarchical_categories(self):
        """Тест иерархических категорий."""
        parent = EquipmentCategory.objects.create(name="Компьютеры")
        child = EquipmentCategory.objects.create(
            name="Ноутбуки", parent=parent
        )

        assert child.full_path == "Компьютеры → Ноутбуки"
        assert str(child) == "Компьютеры → Ноутбуки"


@pytest.mark.django_db
class TestSupplier:
    """Тесты модели Supplier."""

    def test_create_supplier(self):
        """Тест создания поставщика."""
        supplier = Supplier.objects.create(
            name="ООО Рога и Копыта",
            contact_person="Иван Иванов",
            phone="+7 (999) 123-45-67",
            email="info@rogakopyta.ru",
            inn="1234567890",
            rating=Decimal("4.50"),
        )

        assert supplier.id is not None
        assert supplier.is_active is True
        assert str(supplier) == "ООО Рога и Копыта"
