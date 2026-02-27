# tests/api/v1/employees/test_employees_fields_in_list.py
import itertools

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from employees.models import (Department, DepartmentRole, EmployeeDepartment,
                              Position)
from rest_framework import status
from rest_framework.test import APIClient
from tests.conftest import _unique_phone

pytestmark = pytest.mark.django_db
User = get_user_model()

# --- локальные хелперы (не импортируем из других тестов) ---

@pytest.fixture
def api():
    return APIClient()

_phone_seq = itertools.count(3000)

@pytest.fixture
def make_user(
    email: str,
    *,
    staff: bool = False,
    superuser: bool = False,
    verified: bool = True,
    active: bool = True,
    **extra,
) -> User:
    """Fixture для создания пользователей."""
    u = User.objects.create(
        email=email,
        phone_number=extra.pop("phone_number", _unique_phone()),
        first_name=extra.pop("first_name", "FN"),
        last_name=extra.pop("last_name", "LN"),
        is_staff=staff,
        is_superuser=superuser,
        is_active=active,
        email_verified=verified,
        **extra,
    )
    u.set_password("pass")
    u.save()
    return u

def extract_results(data):
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data

def _get_item(items, emp_id):
    for it in items:
        if it.get("id") == emp_id:
            return it
    return None

# --- тесты полей списка ---

def test_list_includes_basic_fields(api):
    """
    В элементе списка должны быть:
      - first_name, last_name
      - avatar (ключ существует, значение может быть пустым)
      - должность: либо position {id,name}, либо position_id
    """
    me = make_user("me@example.com")
    api.force_authenticate(user=me)

    pos = Position.objects.create(name="Developer")
    emp = make_user(
        "emp@example.com", first_name="Ivan", last_name="Ivanov", position=pos
    )

    url = reverse("api:v1:employees-list")
    r = api.get(url)
    assert r.status_code == status.HTTP_200_OK
    items = extract_results(r.json())

    row = _get_item(items, emp.id)
    assert row is not None, "В ответе нет созданного сотрудника"

    assert row.get("first_name") == "Ivan"
    assert row.get("last_name") == "Ivanov"
    assert "avatar" in row, "Поле 'avatar' должно присутствовать (может быть пустым)"

    if "position" in row and isinstance(row["position"], dict):
        assert row["position"].get("id") == pos.id
        assert row["position"].get("name") == "Developer"
    elif "position_id" in row:
        assert row["position_id"] == pos.id
    else:
        raise AssertionError(
            "Ожидали 'position' (объект) или 'position_id' в списке сотрудников"
        )

def test_list_departments_include_role(api):
    """
    У сотрудника в списке есть departments[], и для отдела с назначенной
    ролью присутствует одно из полей: role / role_id / role_name.
    """
    me = make_user("me@example.com")
    api.force_authenticate(user=me)

    emp = make_user("emp@example.com", first_name="Petr", last_name="Petrov")

    dept1 = Department.objects.create(name="QA")
    role = DepartmentRole.objects.create(department=dept1, name="Tester")
    EmployeeDepartment.objects.create(
        employee=emp, department=dept1, role=role, is_active=True
    )

    dept2 = Department.objects.create(name="Support")
    EmployeeDepartment.objects.create(
        employee=emp, department=dept2, is_active=True
    )  # без роли

    url = reverse("api:v1:employees-list")
    r = api.get(url)
    assert r.status_code == status.HTTP_200_OK
    items = extract_results(r.json())

    row = _get_item(items, emp.id)
    assert row is not None, "В ответе нет созданного сотрудника"
    assert "departments" in row and isinstance(
        row["departments"], list
    ), "Нужно поле 'departments' со списком"

    depts = {d.get("id"): d for d in row["departments"]}
    assert dept1.id in depts and dept2.id in depts, "Оба отдела должны присутствовать"

    d1 = depts[dept1.id]
    has_role_id = d1.get("role_id") == role.id
    has_role_name = d1.get("role_name") == role.name
    has_role_obj = isinstance(d1.get("role"), dict) and (
        d1["role"].get("id") == role.id or d1["role"].get("name") == role.name
    )
    assert (
        has_role_id or has_role_name or has_role_obj
    ), "В отделе должна вернуться роль: role_id/role_name/role{id|name}"

    d2 = depts[dept2.id]
    assert (
        (d2.get("role") in (None, {}))
        or (d2.get("role_id") in (None,))
        or ("role_name" not in d2)
    ), "Во втором отделе роль не назначена — поле роли должно быть пустым/отсутствовать"
