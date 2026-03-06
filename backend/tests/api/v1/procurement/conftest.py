"""
Общие fixtures для тестов API модуля procurement.
"""

import pytest
from decimal import Decimal
from datetime import date

from employees.models import Department, Employee, EmployeeDepartment
from procurement.models import (
    Budget,
    Equipment,
    EquipmentCategory,
    ProcurementItem,
    ProcurementRequest,
    Supplier,
)
from procurement.constants import (
    ProcurementStatus,
    UrgencyLevel,
    EquipmentStatus,
)


# ==============================================================================
# ПОЛЬЗОВАТЕЛИ
# ==============================================================================


@pytest.fixture
def user_factory(db):
    """Фабрика для создания пользователей."""
    def _create_user(email, **kwargs):
        defaults = {
            "password": "testpass123",
            "phone_number": f"+7999{email[:7]}",
            "first_name": "Тест",
            "last_name": "Пользователь",
            "send_activation_email": False,
        }
        defaults.update(kwargs)
        return Employee.objects.create_user(email=email, **defaults)
    
    return _create_user


@pytest.fixture
def link_factory(db):
    """Фабрика для связи пользователя с отделом."""
    def _link(employee, department, **kwargs):
        defaults = {"is_active": True}
        defaults.update(kwargs)
        return EmployeeDepartment.objects.create(
            employee=employee,
            department=department,
            **defaults
        )
    
    return _link


# ==============================================================================
# ОТДЕЛЫ И БЮДЖЕТЫ
# ==============================================================================


@pytest.fixture
def department_factory(db):
    """Фабрика для создания отделов."""
    def _create_department(name="Тестовый отдел", **kwargs):
        defaults = {"description": f"Описание {name}"}
        defaults.update(kwargs)
        return Department.objects.create(name=name, **defaults)
    
    return _create_department


@pytest.fixture
def budget_factory(db):
    """Фабрика для создания бюджетов."""
    def _create_budget(department, year=2026, quarter=1, **kwargs):
        defaults = {
            "allocated_amount": Decimal("1000000.00"),
            "spent_amount": Decimal("0.00"),
        }
        defaults.update(kwargs)
        return Budget.objects.create(
            department=department,
            year=year,
            quarter=quarter,
            **defaults
        )
    
    return _create_budget


# ==============================================================================
# ЗАЯВКИ НА ЗАКУПКУ
# ==============================================================================


@pytest.fixture
def procurement_request_factory(db):
    """Фабрика для создания заявок на закупку."""
    def _create_request(department, requestor, **kwargs):
        defaults = {
            "title": "Тестовая заявка",
            "description": "Описание заявки",
            "status": ProcurementStatus.DRAFT,
            "urgency": UrgencyLevel.MEDIUM,
        }
        defaults.update(kwargs)
        return ProcurementRequest.objects.create(
            department=department,
            requestor=requestor,
            **defaults
        )
    
    return _create_request


@pytest.fixture
def procurement_item_factory(db):
    """Фабрика для создания позиций в заявке."""
    def _create_item(request, **kwargs):
        defaults = {
            "name": "Тестовый товар",
            "description": "Описание товара",
            "quantity": 1,
            "unit": "шт",
            "estimated_unit_price": Decimal("10000.00"),
        }
        defaults.update(kwargs)
        return ProcurementItem.objects.create(
            request=request,
            **defaults
        )
    
    return _create_item


# ==============================================================================
# ОБОРУДОВАНИЕ
# ==============================================================================


@pytest.fixture
def category_factory(db):
    """Фабрика для создания категорий оборудования."""
    def _create_category(name="Тестовая категория", **kwargs):
        defaults = {
            "description": f"Описание {name}",
            "icon": "bi-box",
        }
        defaults.update(kwargs)
        return EquipmentCategory.objects.create(name=name, **defaults)
    
    return _create_category


@pytest.fixture
def equipment_factory(db):
    """Фабрика для создания оборудования."""
    counter = {"value": 0}
    
    def _create_equipment(category, department, **kwargs):
        counter["value"] += 1
        defaults = {
            "name": f"Тестовое оборудование {counter['value']}",
            "inventory_number": f"INV-TEST-{counter['value']:04d}",
            "status": EquipmentStatus.AVAILABLE,
            "purchase_date": date.today(),
            "purchase_cost": Decimal("50000.00"),
        }
        defaults.update(kwargs)
        return Equipment.objects.create(
            category=category,
            department=department,
            **defaults
        )
    
    return _create_equipment


# ==============================================================================
# ПОСТАВЩИКИ
# ==============================================================================


@pytest.fixture
def supplier_factory(db):
    """Фабрика для создания поставщиков."""
    def _create_supplier(name="Тестовый поставщик", **kwargs):
        defaults = {
            "contact_person": "Контактное лицо",
            "phone": "+79991112233",
            "email": "supplier@example.com",
            "is_active": True,
        }
        defaults.update(kwargs)
        return Supplier.objects.create(name=name, **defaults)
    
    return _create_supplier
