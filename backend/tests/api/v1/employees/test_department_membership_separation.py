# backend/tests/api/v1/employees/test_department_membership_separation.py
import hashlib
import pytest
from rest_framework.test import APIClient
from rest_framework import status

from employees.models import (
    Department,
    DepartmentRole,
    DepartmentPermission,
    EmployeeDepartment,
    Employee,
)


# =========================
# Helpers
# =========================


def _unique_phone_from_email(email: str) -> str:
    """
    Возвращает детерминированный уникальный номер телефона в формате E.164
    на основе email. Гарантирует уникальность в пределах набора тестов.
    """
    n = int(hashlib.sha256(email.encode("utf-8")).hexdigest(), 16) % 10**9
    # "+79" + 9 цифр = 11-значный номер РФ
    return f"+79{n:09d}"


def make_user(email: str, *, staff: bool = False, superuser: bool = False) -> Employee:
    """
    Фабрика пользователя для тестов. Учитывает ограничение уникальности phone_number.
    """
    return Employee.objects.create(
        email=email,
        phone_number=_unique_phone_from_email(email),
        first_name="T",
        last_name="U",
        is_staff=staff,
        is_superuser=superuser,
        email_verified=True,
        is_active=True,
    )


def ensure_dept_perm(code: str, name: str | None = None) -> DepartmentPermission:
    """
    Создаёт (или возвращает) департаментское право с данным кодом.
    """
    return DepartmentPermission.objects.get_or_create(
        code=code, defaults={"name": name or code}
    )[0]


def make_role(
    dept: Department, name: str, codes: list[str] | None = None
) -> DepartmentRole:
    """
    Создаёт роль отдела и навешивает на неё (опционально) набор департаментских прав.
    """
    role = DepartmentRole.objects.create(department=dept, name=name)
    if codes:
        perms = [ensure_dept_perm(c) for c in codes]
        role.scoped_permissions.add(*perms)
    return role


def grant_manage_in_dept(user: Employee, dept: Department) -> DepartmentRole:
    """
    Выдаёт пользователю роль в отделе с правом manage_department.
    """
    role = make_role(dept, "manager", ["manage_department"])
    EmployeeDepartment.objects.update_or_create(
        employee=user,
        department=dept,
        defaults={"is_active": True, "role": role},
    )
    return role


def grant_assign_in_dept(user: Employee, dept: Department) -> DepartmentRole:
    """
    Выдаёт пользователю роль в отделе с правом assign_department_role.
    """
    role = make_role(dept, "assigner", ["assign_department_role"])
    EmployeeDepartment.objects.update_or_create(
        employee=user,
        department=dept,
        defaults={"is_active": True, "role": role},
    )
    return role


# Утилиты URL с обязательным хвостовым слэшем (APPEND_SLASH=True)
def url_add_member(dept_id: int) -> str:
    """POST /api/v1/departments/{id}/add_member/"""
    return f"/api/v1/departments/{dept_id}/add_member/"


def url_remove_member(dept_id: int) -> str:
    """POST /api/v1/departments/{id}/remove_member/"""
    return f"/api/v1/departments/{dept_id}/remove_member/"


def url_set_member_role(dept_id: int) -> str:
    """POST /api/v1/departments/{id}/set_member_role/"""
    return f"/api/v1/departments/{dept_id}/set_member_role/"


# =========================
# Tests: add_member / remove_member
# =========================


@pytest.mark.django_db
def test_add_member_requires_manage_and_does_not_assign_role(api_client: APIClient):
    """
    add_member:
      - 401 без авторизации
      - 403 с правом assign_department_role (но без manage_department)
      - 200 с manage_department
      - не назначает роль (role остаётся None)
    """
    d = Department.objects.create(name="Dept")
    target = make_user("target@example.com")
    url = url_add_member(d.pk)

    # 401
    resp = api_client.post(url, {"employee_id": target.id}, format="json")
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # 403: есть только право назначать роли
    assigner = make_user("assigner@example.com")
    api_client.force_authenticate(assigner)
    grant_assign_in_dept(assigner, d)
    resp = api_client.post(url, {"employee_id": target.id}, format="json")
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # 200: manage_department
    manager = make_user("manager@example.com")
    api_client.force_authenticate(manager)
    grant_manage_in_dept(manager, d)
    resp = api_client.post(url, {"employee_id": target.id}, format="json")
    assert resp.status_code == status.HTTP_200_OK

    link = EmployeeDepartment.objects.get(employee_id=target.id, department_id=d.id)
    assert link.is_active is True
    assert link.role_id is None  # add_member не должен трогать роль


@pytest.mark.django_db
def test_remove_member_requires_manage_and_does_not_touch_role(api_client: APIClient):
    """
    remove_member:
      - 403 при отсутствии manage_department (даже если есть assign_department_role)
      - 200 с manage_department
      - не трогает role (оставляет как есть)
    """
    d = Department.objects.create(name="Dept")
    target = make_user("target2@example.com")
    some_role = make_role(d, "any")
    EmployeeDepartment.objects.create(
        employee=target, department=d, is_active=True, role=some_role
    )

    url = url_remove_member(d.pk)

    assigner = make_user("assigner2@example.com")
    api_client.force_authenticate(assigner)
    grant_assign_in_dept(assigner, d)
    resp = api_client.post(url, {"employee_id": target.id}, format="json")
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    manager = make_user("manager2@example.com")
    api_client.force_authenticate(manager)
    grant_manage_in_dept(manager, d)
    resp = api_client.post(url, {"employee_id": target.id}, format="json")
    assert resp.status_code == status.HTTP_200_OK

    link = EmployeeDepartment.objects.get(employee=target, department=d)
    assert link.is_active is False
    assert link.role_id == some_role.id  # роль не менялась


# =========================
# Tests: set_member_role (строгое разделение)
# =========================


@pytest.mark.django_db
def test_set_member_role_requires_assign_not_manage(api_client: APIClient):
    """
    set_member_role:
      - 403 с manage_department, если нет assign_department_role
      - 200 с assign_department_role
    """
    d = Department.objects.create(name="Dept")
    worker = make_user("worker@example.com")
    EmployeeDepartment.objects.create(employee=worker, department=d, is_active=True)
    role = make_role(d, "Worker")

    # 403: только manage_department
    manager = make_user("manager3@example.com")
    api_client.force_authenticate(manager)
    grant_manage_in_dept(manager, d)
    resp = api_client.post(
        url_set_member_role(d.pk),
        {"employee_id": worker.id, "role_id": role.id},
        format="json",
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # 200: assign_department_role
    assigner = make_user("assigner3@example.com")
    api_client.force_authenticate(assigner)
    grant_assign_in_dept(assigner, d)
    resp = api_client.post(
        url_set_member_role(d.pk),
        {"employee_id": worker.id, "role_id": role.id},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK

    link = EmployeeDepartment.objects.get(employee=worker, department=d)
    assert link.role_id == role.id


@pytest.mark.django_db
def test_set_member_role_does_not_create_membership_and_does_not_toggle_active(
    api_client: APIClient,
):
    """
    Проверяем отсутствие пересечения функционала у set_member_role:
      - не создаёт членство, если связи нет (ожидаем ошибку)
      - не меняет is_active (игнорирует попытки передать is_active)
    """
    d = Department.objects.create(name="Dept")
    role = make_role(d, "Worker")

    outsider = make_user("outsider@example.com")

    assigner = make_user("assigner4@example.com")
    api_client.force_authenticate(assigner)
    grant_assign_in_dept(assigner, d)

    # 1) Нельзя создать членство через set_member_role
    resp = api_client.post(
        url_set_member_role(d.pk),
        {"employee_id": outsider.id, "role_id": role.id},
        format="json",
    )
    assert resp.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND)
    assert not EmployeeDepartment.objects.filter(
        employee=outsider, department=d
    ).exists()

    # 2) is_active не должен переключаться через set_member_role
    worker = make_user("worker2@example.com")
    link = EmployeeDepartment.objects.create(
        employee=worker, department=d, is_active=True
    )
    resp = api_client.post(
        url_set_member_role(d.pk),
        {"employee_id": worker.id, "role_id": role.id, "is_active": False},
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK
    link.refresh_from_db()
    assert link.is_active is True, "set_member_role не должен менять is_active"
    assert link.role_id == role.id


# =========================
# Доп. тест: авторизация и отсутствие пересечений
# =========================


@pytest.mark.django_db
def test_all_three_actions_require_auth_and_permissions(api_client: APIClient):
    """
    Ещё одна сетка проверок:
      - без авторизации все три эндпоинта возвращают 401
      - пользователь с manage_department не может set_member_role (403)
      - пользователь с assign_department_role не может add/remove (403)
    """
    d = Department.objects.create(name="Dept")
    worker = make_user("worker3@example.com")
    EmployeeDepartment.objects.create(employee=worker, department=d, is_active=True)
    role = make_role(d, "WorkerX")

    # 401 без авторизации
    for url, payload in [
        (url_add_member(d.pk), {"employee_id": worker.id}),
        (url_remove_member(d.pk), {"employee_id": worker.id}),
        (url_set_member_role(d.pk), {"employee_id": worker.id, "role_id": role.id}),
    ]:
        resp = api_client.post(url, payload, format="json")
        assert resp.status_code == status.HTTP_401_UNAUTHORIZED

    # Менеджер отдела
    manager = make_user("manager4@example.com")
    grant_manage_in_dept(manager, d)
    api_client.force_authenticate(manager)
    # может add/remove
    assert (
        api_client.post(
            url_add_member(d.pk), {"employee_id": worker.id}, format="json"
        ).status_code
        == 200
    )
    assert (
        api_client.post(
            url_remove_member(d.pk), {"employee_id": worker.id}, format="json"
        ).status_code
        == 200
    )
    # но не может set_member_role
    assert (
        api_client.post(
            url_set_member_role(d.pk),
            {"employee_id": worker.id, "role_id": role.id},
            format="json",
        ).status_code
        == 403
    )

    # Назначающий роли
    assigner = make_user("assigner5@example.com")
    grant_assign_in_dept(assigner, d)
    api_client.force_authenticate(assigner)
    # может set_member_role
    assert (
        api_client.post(
            url_set_member_role(d.pk),
            {"employee_id": worker.id, "role_id": role.id},
            format="json",
        ).status_code
        == 200
    )
    # но не может add/remove
    assert (
        api_client.post(
            url_add_member(d.pk), {"employee_id": worker.id}, format="json"
        ).status_code
        == 403
    )
    assert (
        api_client.post(
            url_remove_member(d.pk), {"employee_id": worker.id}, format="json"
        ).status_code
        == 403
    )


@pytest.mark.django_db
def test_add_member_ignores_role_parameter(api_client: APIClient):
    """
    add_member не должен назначать роль даже если клиент прислал role_id.
    """
    d = Department.objects.create(name="Dept")
    target = make_user("roleless@example.com")
    role = make_role(d, "ShouldNotBeAssigned")

    manager = make_user("managerX@example.com")
    api_client.force_authenticate(manager)
    grant_manage_in_dept(manager, d)

    resp = api_client.post(
        url_add_member(d.pk),
        {"employee_id": target.id, "role_id": role.id},  # попытка подсунуть роль
        format="json",
    )
    assert resp.status_code == status.HTTP_200_OK

    link = EmployeeDepartment.objects.get(employee=target, department=d)
    assert link.is_active is True
    assert link.role_id is None, "add_member не должен трогать роль"
