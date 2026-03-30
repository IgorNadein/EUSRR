"""
Тесты прав доступа для API оборудования.

Сценарии:
1. Создание оборудования:
   - Админ/staff → может выбирать любой отдел и ответственного
   - Модельные права (add_equipment) → может выбирать любой отдел и ответственного
   - Начальник отдела → только свой отдел, ответственный по умолчанию он сам (может выбрать из отдела)
   - Уполномоченный (скоуп-право) → только свой отдел, ответственный = начальник (без выбора)
   - Обычный сотрудник → нет доступа

2. Изменение/удаление:
   - Админ/staff → любое оборудование
   - Модельные права → любое оборудование
   - Начальник отдела → только своего отдела
   - Уполномоченный → только своего отдела
   - Ответственный → только изменение (не удаление)

3. Валидация:
   - Ответственный ДОЛЖЕН состоять в отделе оборудования
"""

import pytest
from decimal import Decimal
from datetime import date

from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.test import APIClient

from employees.models import (
    Department,
    DepartmentPermission,
    DepartmentRole,
    EmployeeDepartment,
)
from employees.constants import DeptPerm
from procurement.models import Equipment, EquipmentCategory

User = get_user_model()

# Код права для управления оборудованием в отделе
MANAGE_EQUIPMENT_CODE = DeptPerm.MANAGE_EQUIPMENT


# =============================================================================
# Helpers
# =============================================================================

_phone_counter = 0


def unique_phone() -> str:
    """Генерирует уникальный телефон."""
    global _phone_counter
    _phone_counter += 1
    return f"+7999{_phone_counter:07d}"


def make_user(
    email: str,
    staff: bool = False,
    superuser: bool = False,
    verified: bool = True,
) -> User:
    """Создаёт пользователя."""
    return User.objects.create_user(
        email=email,
        password="testpass123",
        phone_number=unique_phone(),
        first_name="Test",
        last_name="User",
        is_staff=staff,
        is_superuser=superuser,
        is_active=True,
        email_verified=verified,
        send_activation_email=False,
    )


def make_department(name: str, head: User = None) -> Department:
    """Создаёт отдел."""
    return Department.objects.create(name=name, head=head)


def ensure_dept_perm(code: str, name: str = None) -> DepartmentPermission:
    """Получает или создаёт скоуп-право отдела."""
    perm, _ = DepartmentPermission.objects.get_or_create(
        code=code,
        defaults={"name": name or code}
    )
    return perm


def make_role(
    dept: Department,
    name: str,
    codes: list[str] = None
) -> DepartmentRole:
    """Создаёт роль в отделе с указанными скоуп-правами."""
    role = DepartmentRole.objects.create(department=dept, name=name)
    if codes:
        perms = [ensure_dept_perm(c) for c in codes]
        role.scoped_permissions.add(*perms)
    return role


def add_user_to_dept(
    user: User,
    dept: Department,
    role: DepartmentRole = None,
    is_active: bool = True
) -> EmployeeDepartment:
    """Добавляет пользователя в отдел с ролью."""
    link, _ = EmployeeDepartment.objects.update_or_create(
        employee=user,
        department=dept,
        defaults={"is_active": is_active, "role": role}
    )
    return link


def grant_model_permission(user: User, perm_codename: str, model_class) -> None:
    """Выдаёт модельное право пользователю."""
    ct = ContentType.objects.get_for_model(model_class)
    # Используем get() чтобы получить существующий permission
    # Permissions создаются Django при миграциях
    perm = Permission.objects.get(content_type=ct, codename=perm_codename)
    user.user_permissions.add(perm)
    # Очищаем кэш прав пользователя
    if hasattr(user, '_perm_cache'):
        del user._perm_cache
    if hasattr(user, '_user_perm_cache'):
        del user._user_perm_cache


def make_category(name: str = "Компьютеры") -> EquipmentCategory:
    """Создаёт категорию оборудования."""
    cat, _ = EquipmentCategory.objects.get_or_create(
        name=name,
        defaults={"icon": "bi-laptop"}
    )
    return cat


def make_equipment(
    name: str,
    dept: Department,
    category: EquipmentCategory,
    responsible: User = None,
    inventory_number: str = None
) -> Equipment:
    """Создаёт оборудование."""
    if not inventory_number:
        count = Equipment.objects.count()
        inventory_number = f"INV-2025-{count + 1:04d}"
    
    return Equipment.objects.create(
        name=name,
        inventory_number=inventory_number,
        category=category,
        department=dept,
        responsible_person=responsible,
        purchase_date=date.today(),
        purchase_cost=Decimal("10000.00"),
    )


def equipment_create_url() -> str:
    """URL для создания оборудования."""
    return reverse("procurement:equipment-list")


def equipment_detail_url(pk: int) -> str:
    """URL для конкретного оборудования."""
    return reverse("procurement:equipment-detail", args=[pk])


def valid_equipment_data(
    category: EquipmentCategory,
    dept: Department,
    responsible: User = None,
    name: str = "Ноутбук Dell"
) -> dict:
    """Валидные данные для создания оборудования."""
    data = {
        "name": name,
        "category": category.id,
        "department": dept.id,
        "purchase_date": date.today().isoformat(),
        "purchase_cost": "50000.00",
    }
    if responsible:
        data["responsible_person"] = responsible.id
    return data


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def category(db) -> EquipmentCategory:
    return make_category()


@pytest.fixture
def admin_user(db) -> User:
    """Администратор (staff)."""
    return make_user("admin@example.com", staff=True)


@pytest.fixture
def superuser(db) -> User:
    """Суперпользователь."""
    return make_user("super@example.com", superuser=True)


@pytest.fixture
def model_perm_user(db) -> User:
    """Пользователь с модельными правами на оборудование."""
    user = make_user("modelperm@example.com")
    grant_model_permission(user, "add_equipment", Equipment)
    grant_model_permission(user, "change_equipment", Equipment)
    grant_model_permission(user, "delete_equipment", Equipment)
    # Перезагружаем из БД для обновления кэша прав
    user = User.objects.get(pk=user.pk)
    return user


@pytest.fixture
def dept_it(db) -> Department:
    """IT отдел (без начальника изначально)."""
    return make_department("IT отдел")


@pytest.fixture
def dept_hr(db) -> Department:
    """HR отдел."""
    return make_department("HR отдел")


@pytest.fixture
def dept_head(db, dept_it) -> User:
    """Начальник IT отдела."""
    user = make_user("head@example.com")
    dept_it.head = user
    dept_it.save()
    add_user_to_dept(user, dept_it)
    return user


@pytest.fixture
def dept_member(db, dept_it) -> User:
    """Обычный сотрудник IT отдела (без особых прав)."""
    user = make_user("member@example.com")
    add_user_to_dept(user, dept_it)
    return user


@pytest.fixture
def authorized_member(db, dept_it) -> User:
    """Уполномоченный сотрудник IT отдела (со скоуп-правом)."""
    user = make_user("authorized@example.com")
    role = make_role(dept_it, "Ответственный за оборудование", [MANAGE_EQUIPMENT_CODE])
    add_user_to_dept(user, dept_it, role=role)
    return user


@pytest.fixture
def other_dept_head(db, dept_hr) -> User:
    """Начальник HR отдела."""
    user = make_user("hr_head@example.com")
    dept_hr.head = user
    dept_hr.save()
    add_user_to_dept(user, dept_hr)
    return user


@pytest.fixture
def random_user(db) -> User:
    """Случайный пользователь без отдела."""
    return make_user("random@example.com")


# =============================================================================
# Tests: Создание оборудования - кто может
# =============================================================================

@pytest.mark.django_db
class TestEquipmentCreateAccess:
    """Тесты: кто может создавать оборудование."""

    def test_unauthenticated_cannot_create(self, api_client, category, dept_it):
        """Неаутентифицированный пользователь не может создавать."""
        data = valid_equipment_data(category, dept_it)
        response = api_client.post(equipment_create_url(), data, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_admin_can_create(self, api_client, admin_user, category, dept_it):
        """Админ может создавать оборудование."""
        api_client.force_authenticate(user=admin_user)
        data = valid_equipment_data(category, dept_it)
        response = api_client.post(equipment_create_url(), data, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_superuser_can_create(self, api_client, superuser, category, dept_it):
        """Суперпользователь может создавать оборудование."""
        api_client.force_authenticate(user=superuser)
        data = valid_equipment_data(category, dept_it)
        response = api_client.post(equipment_create_url(), data, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_model_perm_user_can_create(
        self, api_client, model_perm_user, category, dept_it
    ):
        """Пользователь с модельными правами может создавать."""
        api_client.force_authenticate(user=model_perm_user)
        data = valid_equipment_data(category, dept_it)
        response = api_client.post(equipment_create_url(), data, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_dept_head_can_create_in_own_dept(
        self, api_client, dept_head, category, dept_it
    ):
        """Начальник отдела может создавать в своём отделе."""
        api_client.force_authenticate(user=dept_head)
        data = valid_equipment_data(category, dept_it)
        response = api_client.post(equipment_create_url(), data, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_dept_head_cannot_create_in_other_dept(
        self, api_client, dept_head, category, dept_hr
    ):
        """Начальник отдела НЕ может создавать в чужом отделе."""
        api_client.force_authenticate(user=dept_head)
        data = valid_equipment_data(category, dept_hr)
        response = api_client.post(equipment_create_url(), data, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_authorized_member_can_create_in_own_dept(
        self, api_client, authorized_member, category, dept_it
    ):
        """Уполномоченный сотрудник может создавать в своём отделе."""
        api_client.force_authenticate(user=authorized_member)
        data = valid_equipment_data(category, dept_it)
        response = api_client.post(equipment_create_url(), data, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_authorized_member_cannot_create_in_other_dept(
        self, api_client, authorized_member, category, dept_hr
    ):
        """Уполномоченный НЕ может создавать в чужом отделе."""
        api_client.force_authenticate(user=authorized_member)
        data = valid_equipment_data(category, dept_hr)
        response = api_client.post(equipment_create_url(), data, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_regular_member_cannot_create(
        self, api_client, dept_member, category, dept_it
    ):
        """Обычный сотрудник БЕЗ прав не может создавать."""
        api_client.force_authenticate(user=dept_member)
        data = valid_equipment_data(category, dept_it)
        response = api_client.post(equipment_create_url(), data, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_random_user_cannot_create(
        self, api_client, random_user, category, dept_it
    ):
        """Пользователь без отдела не может создавать."""
        api_client.force_authenticate(user=random_user)
        data = valid_equipment_data(category, dept_it)
        response = api_client.post(equipment_create_url(), data, format="json")
        assert response.status_code == status.HTTP_403_FORBIDDEN


# =============================================================================
# Tests: Создание - выбор отдела
# =============================================================================

@pytest.mark.django_db
class TestEquipmentCreateDepartmentChoice:
    """Тесты: кто может выбирать отдел при создании."""

    def test_admin_can_choose_any_department(
        self, api_client, admin_user, category, dept_it, dept_hr
    ):
        """Админ может указать любой отдел."""
        api_client.force_authenticate(user=admin_user)
        
        # Создаём в IT отделе
        data1 = valid_equipment_data(category, dept_it, name="Оборудование IT")
        response1 = api_client.post(equipment_create_url(), data1, format="json")
        assert response1.status_code == status.HTTP_201_CREATED
        assert response1.data["department"] == dept_it.id
        
        # Создаём в HR отделе
        data2 = valid_equipment_data(category, dept_hr, name="Оборудование HR")
        response2 = api_client.post(equipment_create_url(), data2, format="json")
        assert response2.status_code == status.HTTP_201_CREATED
        assert response2.data["department"] == dept_hr.id

    def test_model_perm_user_can_choose_any_department(
        self, api_client, model_perm_user, category, dept_it, dept_hr
    ):
        """Пользователь с модельными правами может указать любой отдел."""
        api_client.force_authenticate(user=model_perm_user)
        
        data = valid_equipment_data(category, dept_hr)
        response = api_client.post(equipment_create_url(), data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["department"] == dept_hr.id

    def test_dept_head_department_is_forced_to_own(
        self, api_client, dept_head, category, dept_it, dept_hr
    ):
        """Начальник отдела: попытка указать чужой отдел → запрет или замена на свой."""
        api_client.force_authenticate(user=dept_head)
        
        # Пытаемся создать в HR отделе, но мы начальник IT
        data = valid_equipment_data(category, dept_hr)
        response = api_client.post(equipment_create_url(), data, format="json")
        
        # Должно быть либо 403, либо автозамена на свой отдел
        # Выбираем вариант с 403
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_authorized_member_department_is_forced(
        self, api_client, authorized_member, category, dept_it, dept_hr
    ):
        """Уполномоченный: отдел автоматически = его отдел, попытка указать другой → ошибка."""
        api_client.force_authenticate(user=authorized_member)
        
        data = valid_equipment_data(category, dept_hr)
        response = api_client.post(equipment_create_url(), data, format="json")
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


# =============================================================================
# Tests: Создание - выбор ответственного
# =============================================================================

@pytest.mark.django_db
class TestEquipmentCreateResponsibleChoice:
    """Тесты: кто может выбирать ответственного при создании."""

    def test_admin_can_choose_any_responsible_in_dept(
        self, api_client, admin_user, category, dept_it, dept_member
    ):
        """Админ может указать любого сотрудника из отдела как ответственного."""
        api_client.force_authenticate(user=admin_user)
        
        data = valid_equipment_data(category, dept_it, responsible=dept_member)
        response = api_client.post(equipment_create_url(), data, format="json")
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["responsible_person"] == dept_member.id

    def test_dept_head_can_choose_responsible_from_own_dept(
        self, api_client, dept_head, category, dept_it, dept_member
    ):
        """Начальник может выбрать ответственного из своего отдела."""
        api_client.force_authenticate(user=dept_head)
        
        data = valid_equipment_data(category, dept_it, responsible=dept_member)
        response = api_client.post(equipment_create_url(), data, format="json")
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["responsible_person"] == dept_member.id

    def test_dept_head_default_responsible_is_self(
        self, api_client, dept_head, category, dept_it
    ):
        """Начальник: если ответственный не указан, по умолчанию он сам."""
        api_client.force_authenticate(user=dept_head)
        
        data = valid_equipment_data(category, dept_it)
        # Не указываем responsible_person
        response = api_client.post(equipment_create_url(), data, format="json")
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["responsible_person"] == dept_head.id

    def test_authorized_member_responsible_is_forced_to_head(
        self, api_client, authorized_member, category, dept_it, dept_head, dept_member
    ):
        """Уполномоченный: ответственный автоматически = начальник, нельзя выбрать другого."""
        api_client.force_authenticate(user=authorized_member)
        
        # Пытаемся указать другого ответственного
        data = valid_equipment_data(category, dept_it, responsible=dept_member)
        response = api_client.post(equipment_create_url(), data, format="json")
        
        # Должно либо заменить на начальника, либо вернуть ошибку
        if response.status_code == status.HTTP_201_CREATED:
            # Автозамена на начальника
            assert response.data["responsible_person"] == dept_head.id
        else:
            # Или ошибка валидации
            assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_authorized_member_default_responsible_is_head(
        self, api_client, authorized_member, category, dept_it, dept_head
    ):
        """Уполномоченный: если ответственный не указан, это начальник."""
        api_client.force_authenticate(user=authorized_member)
        
        data = valid_equipment_data(category, dept_it)
        response = api_client.post(equipment_create_url(), data, format="json")
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["responsible_person"] == dept_head.id


# =============================================================================
# Tests: Валидация ответственного - принадлежность к отделу
# =============================================================================

@pytest.mark.django_db
class TestEquipmentResponsibleValidation:
    """Тесты: ответственный должен состоять в отделе оборудования."""

    def test_responsible_must_be_in_department(
        self, api_client, admin_user, category, dept_it, other_dept_head
    ):
        """Ответственный ДОЛЖЕН быть в том же отделе, что и оборудование."""
        api_client.force_authenticate(user=admin_user)
        
        # other_dept_head состоит в HR, а мы создаём в IT
        data = valid_equipment_data(category, dept_it, responsible=other_dept_head)
        response = api_client.post(equipment_create_url(), data, format="json")
        
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "responsible_person" in response.data or "responsible" in str(response.data)

    def test_responsible_in_same_department_is_valid(
        self, api_client, admin_user, category, dept_it, dept_member
    ):
        """Ответственный из того же отдела — валидно."""
        api_client.force_authenticate(user=admin_user)
        
        data = valid_equipment_data(category, dept_it, responsible=dept_member)
        response = api_client.post(equipment_create_url(), data, format="json")
        
        assert response.status_code == status.HTTP_201_CREATED

    def test_dept_head_is_valid_responsible(
        self, api_client, admin_user, category, dept_it, dept_head
    ):
        """Начальник отдела — валидный ответственный."""
        api_client.force_authenticate(user=admin_user)
        
        data = valid_equipment_data(category, dept_it, responsible=dept_head)
        response = api_client.post(equipment_create_url(), data, format="json")
        
        assert response.status_code == status.HTTP_201_CREATED


# =============================================================================
# Tests: Изменение оборудования
# =============================================================================

@pytest.mark.django_db
class TestEquipmentUpdateAccess:
    """Тесты: кто может изменять оборудование."""

    def test_admin_can_update_any_equipment(
        self, api_client, admin_user, category, dept_it, dept_head
    ):
        """Админ может изменять любое оборудование."""
        equipment = make_equipment("Laptop", dept_it, category, dept_head)
        
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            equipment_detail_url(equipment.id),
            {"name": "Updated Laptop"},
            format="json"
        )
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Updated Laptop"

    def test_model_perm_user_can_update_any(
        self, api_client, model_perm_user, category, dept_it, dept_head
    ):
        """Пользователь с модельными правами может изменять любое оборудование."""
        equipment = make_equipment("Laptop", dept_it, category, dept_head)
        
        api_client.force_authenticate(user=model_perm_user)
        response = api_client.patch(
            equipment_detail_url(equipment.id),
            {"name": "Updated"},
            format="json"
        )
        
        assert response.status_code == status.HTTP_200_OK

    def test_dept_head_can_update_own_dept_equipment(
        self, api_client, dept_head, category, dept_it
    ):
        """Начальник отдела может изменять оборудование своего отдела."""
        equipment = make_equipment("Laptop", dept_it, category, dept_head)
        
        api_client.force_authenticate(user=dept_head)
        response = api_client.patch(
            equipment_detail_url(equipment.id),
            {"name": "Updated"},
            format="json"
        )
        
        assert response.status_code == status.HTTP_200_OK

    def test_dept_head_cannot_update_other_dept_equipment(
        self, api_client, dept_head, category, dept_hr, other_dept_head
    ):
        """Начальник НЕ может изменять оборудование чужого отдела."""
        equipment = make_equipment("Laptop HR", dept_hr, category, other_dept_head)
        
        api_client.force_authenticate(user=dept_head)
        response = api_client.patch(
            equipment_detail_url(equipment.id),
            {"name": "Hacked"},
            format="json"
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_authorized_member_can_update_own_dept(
        self, api_client, authorized_member, category, dept_it, dept_head
    ):
        """Уполномоченный может изменять оборудование своего отдела."""
        equipment = make_equipment("Laptop", dept_it, category, dept_head)
        
        api_client.force_authenticate(user=authorized_member)
        response = api_client.patch(
            equipment_detail_url(equipment.id),
            {"name": "Updated by authorized"},
            format="json"
        )
        
        assert response.status_code == status.HTTP_200_OK

    def test_responsible_person_can_update(
        self, api_client, dept_member, category, dept_it
    ):
        """Ответственный может изменять своё оборудование."""
        equipment = make_equipment("Laptop", dept_it, category, dept_member)
        
        api_client.force_authenticate(user=dept_member)
        response = api_client.patch(
            equipment_detail_url(equipment.id),
            {"location": "Офис 305"},
            format="json"
        )
        
        assert response.status_code == status.HTTP_200_OK

    def test_regular_member_cannot_update_not_their_equipment(
        self, api_client, dept_member, category, dept_it, dept_head
    ):
        """Обычный сотрудник НЕ может изменять чужое оборудование."""
        equipment = make_equipment("Laptop", dept_it, category, dept_head)
        
        api_client.force_authenticate(user=dept_member)
        response = api_client.patch(
            equipment_detail_url(equipment.id),
            {"name": "Hacked"},
            format="json"
        )
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


# =============================================================================
# Tests: Удаление оборудования
# =============================================================================

@pytest.mark.django_db
class TestEquipmentDeleteAccess:
    """Тесты: кто может удалять оборудование."""

    def test_admin_can_delete(
        self, api_client, admin_user, category, dept_it, dept_head
    ):
        """Админ может удалять любое оборудование."""
        equipment = make_equipment("Laptop", dept_it, category, dept_head)
        
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(equipment_detail_url(equipment.id))
        
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_model_perm_user_can_delete(
        self, api_client, model_perm_user, category, dept_it, dept_head
    ):
        """Пользователь с модельными правами может удалять."""
        equipment = make_equipment("Laptop", dept_it, category, dept_head)
        
        api_client.force_authenticate(user=model_perm_user)
        response = api_client.delete(equipment_detail_url(equipment.id))
        
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_dept_head_can_delete_own_dept_equipment(
        self, api_client, dept_head, category, dept_it
    ):
        """Начальник может удалять оборудование своего отдела."""
        equipment = make_equipment("Laptop", dept_it, category, dept_head)
        
        api_client.force_authenticate(user=dept_head)
        response = api_client.delete(equipment_detail_url(equipment.id))
        
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_dept_head_cannot_delete_other_dept(
        self, api_client, dept_head, category, dept_hr, other_dept_head
    ):
        """Начальник НЕ может удалять оборудование чужого отдела."""
        equipment = make_equipment("Laptop", dept_hr, category, other_dept_head)
        
        api_client.force_authenticate(user=dept_head)
        response = api_client.delete(equipment_detail_url(equipment.id))
        
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_authorized_member_cannot_delete(
        self, api_client, authorized_member, category, dept_it, dept_head
    ):
        """Уполномоченный НЕ может удалять оборудование (только создание/изменение)."""
        equipment = make_equipment("Laptop", dept_it, category, dept_head)
        
        api_client.force_authenticate(user=authorized_member)
        response = api_client.delete(equipment_detail_url(equipment.id))
        
        # Уполномоченный может только создавать и изменять, но не удалять
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_responsible_cannot_delete(
        self, api_client, dept_member, category, dept_it
    ):
        """Ответственный НЕ может удалять своё оборудование."""
        equipment = make_equipment("Laptop", dept_it, category, dept_member)
        
        api_client.force_authenticate(user=dept_member)
        response = api_client.delete(equipment_detail_url(equipment.id))
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


# =============================================================================
# Tests: Просмотр оборудования
# =============================================================================

@pytest.mark.django_db
class TestEquipmentViewAccess:
    """Тесты: просмотр оборудования."""

    def test_unauthenticated_cannot_view(self, api_client, category, dept_it, dept_head):
        """Неаутентифицированный не может просматривать."""
        equipment = make_equipment("Laptop", dept_it, category, dept_head)
        response = api_client.get(equipment_detail_url(equipment.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_any_authenticated_can_view_list(
        self, api_client, dept_member, category, dept_it, dept_head
    ):
        """Любой аутентифицированный сотрудник может просматривать список."""
        make_equipment("Laptop", dept_it, category, dept_head)
        
        api_client.force_authenticate(user=dept_member)
        response = api_client.get(equipment_create_url())
        
        assert response.status_code == status.HTTP_200_OK

    def test_any_authenticated_can_view_detail(
        self, api_client, random_user, category, dept_it, dept_head
    ):
        """Любой аутентифицированный может просматривать детали."""
        equipment = make_equipment("Laptop", dept_it, category, dept_head)
        
        api_client.force_authenticate(user=random_user)
        response = api_client.get(equipment_detail_url(equipment.id))
        
        assert response.status_code == status.HTTP_200_OK


# =============================================================================
# Tests: API для получения доступных опций
# =============================================================================

@pytest.mark.django_db
class TestEquipmentCreateOptions:
    """Тесты: эндпоинт для получения доступных опций при создании."""

    def test_admin_gets_all_departments(
        self, api_client, admin_user, dept_it, dept_hr
    ):
        """Админ получает все отделы для выбора."""
        api_client.force_authenticate(user=admin_user)
        
        url = reverse("procurement:equipment-create-options")
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data["can_choose_department"] is True
        assert response.data["can_choose_responsible"] is True
        dept_ids = [d["id"] for d in response.data["allowed_departments"]]
        assert dept_it.id in dept_ids
        assert dept_hr.id in dept_ids

    def test_dept_head_gets_only_own_department(
        self, api_client, dept_head, dept_it, dept_hr
    ):
        """Начальник получает только свой отдел."""
        api_client.force_authenticate(user=dept_head)
        
        url = reverse("procurement:equipment-create-options")
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data["can_choose_department"] is False
        assert response.data["can_choose_responsible"] is True
        dept_ids = [d["id"] for d in response.data["allowed_departments"]]
        assert dept_ids == [dept_it.id]

    def test_authorized_member_gets_limited_options(
        self, api_client, authorized_member, dept_it, dept_head
    ):
        """Уполномоченный получает свой отдел и НЕ может выбирать ответственного."""
        api_client.force_authenticate(user=authorized_member)
        
        url = reverse("procurement:equipment-create-options")
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data["can_choose_department"] is False
        assert response.data["can_choose_responsible"] is False
        assert response.data["default_responsible"]["id"] == dept_head.id

    def test_regular_member_cannot_access(self, api_client, dept_member):
        """Обычный сотрудник без прав не получает опции (или получает пустой ответ)."""
        api_client.force_authenticate(user=dept_member)
        
        url = reverse("procurement:equipment-create-options")
        response = api_client.get(url)
        
        # Либо 403, либо пустой список отделов
        if response.status_code == status.HTTP_200_OK:
            assert response.data["allowed_departments"] == []
        else:
            assert response.status_code == status.HTTP_403_FORBIDDEN


# =============================================================================
# Tests: Массовое создание
# =============================================================================

@pytest.mark.django_db
class TestEquipmentBulkCreate:
    """Тесты: массовое создание оборудования."""

    def test_admin_can_bulk_create(
        self, api_client, admin_user, category, dept_it, dept_head
    ):
        """Админ может массово создавать."""
        api_client.force_authenticate(user=admin_user)
        
        data = valid_equipment_data(category, dept_it, responsible=dept_head)
        data["quantity"] = 3
        
        response = api_client.post(equipment_create_url(), data, format="json")
        
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["created_count"] == 3

    def test_bulk_create_generates_unique_inventory_numbers(
        self, api_client, admin_user, category, dept_it, dept_head
    ):
        """При массовом создании генерируются уникальные инвентарные номера."""
        api_client.force_authenticate(user=admin_user)
        
        data = valid_equipment_data(category, dept_it, responsible=dept_head)
        data["quantity"] = 3
        
        response = api_client.post(equipment_create_url(), data, format="json")
        
        inventory_numbers = [eq["inventory_number"] for eq in response.data["equipment"]]
        assert len(set(inventory_numbers)) == 3  # Все уникальные

    def test_authorized_member_bulk_create_uses_dept_head(
        self, api_client, authorized_member, category, dept_it, dept_head
    ):
        """Уполномоченный при массовом создании — ответственный всегда начальник."""
        api_client.force_authenticate(user=authorized_member)
        
        data = valid_equipment_data(category, dept_it)
        data["quantity"] = 2
        
        response = api_client.post(equipment_create_url(), data, format="json")
        
        assert response.status_code == status.HTTP_201_CREATED
        for eq in response.data["equipment"]:
            assert eq["responsible_person"] == dept_head.id
