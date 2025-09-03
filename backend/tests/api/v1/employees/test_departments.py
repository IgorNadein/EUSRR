# tests/api/v1/employees/test_departments.py
# Вот что покрывает файл тестов, по пунктам:

# 1. Список отделов и доступ

# * **test\_list\_requires\_auth** — проверяет, что `/api/v1/departments/` без авторизации даёт `401`.
# * **test\_list\_ok\_for\_authenticated** — авторизованный пользователь получает `200` и список (2 созданных отдела).
# * **test\_search\_and\_ordering** — работает поиск по `search` (находит только *Beta*), сортировка по `-name` (DESC) и `name` (ASC).

# 2. Аннотация `employees_count`

# * **test\_employees\_count\_adds\_head\_if\_not\_in\_links** — если начальник не присутствует в `EmployeeDepartment`, то `employees_count = активные_ссылки + 1`.
# * **test\_employees\_count\_not\_double\_count\_head\_if\_in\_links** — если начальник есть в активных связях, его не считают второй раз (итого 3).

# 3. Создание и удаление отделов (права staff)

# * **test\_create\_requires\_staff** — POST может только staff: у обычного `403/401`, у staff `201` и отдел создан.
# * **test\_destroy\_requires\_staff** — DELETE может только staff: у обычного `403/401`, у staff `204` и объект удалён.

# 4. PATCH/PUT отдела (объектные права)

# * **test\_partial\_update\_name\_requires\_manage\_perm** — смена `name` требует права `manage_department`: без роли `403`, с ролью — `200` и имя обновлено.
# * **test\_partial\_update\_head\_requires\_change\_head\_perm** — смена руководителя через `PATCH` требует `change_department_head` (одного `manage_department` недостаточно): сначала `403`, после добавления codenam’а — `200` и `head` сменён.
# * **test\_partial\_update\_head\_same\_value\_does\_not\_require\_extra\_perm** — если передан тот же `head_id`, хватает `manage_department`, ответ `200`, `head` не меняется.

# 5. Экшен `set_head`

# * **test\_set\_head\_by\_role\_with\_perm** — роль с `change_department_head` может назначить руководителя: `200`, `head` изменён.
# * **test\_set\_head\_validation\_inactive\_employee** — нельзя назначить неактивного сотрудника (не `actually_active`): `400`.
# * **test\_set\_head\_remove\_with\_null** — `head_id = null` снимает руководителя: `204`, `head` становится `null`.
# * **test\_set\_head\_requires\_perm** — без нужных прав на отдел: `403`.

# 6. Экшен `set_member_role`

# * **test\_set\_member\_role\_happy\_path** — роль с `assign_department_role` может назначать/менять роль участника отдела: `200`, возвращаются `employee_id`, `role_id`, `is_active=True`.
# * **test\_set\_member\_role\_reject\_foreign\_role** — нельзя присвоить роль от другого отдела: `400`.
# * **test\_set\_member\_role\_requires\_perm** — без права `assign_department_role` ответ `403`.
# * **test\_set\_member\_role\_missing\_employee\_id** — отсутствие `employee_id` в payload → `400`.

# Доп. утилиты/фикстуры в файле:

# * `api_client` — DRF `APIClient`.
# * `make_user` — создаёт пользователя напрямую (уникальный телефон, пароль, опции staff/superuser/verified/active).
# * `perm_for_department` — безопасно выдаёт `Permission` для модели Department c нужным `codename`.
# * `make_role` — создаёт роль отдела и добавляет в неё набор codenames.
# * `extract_results` — вытаскивает `results` из пагинированного ответа DRF или возвращает список как есть.

import itertools

import pytest
from django.contrib.auth import get_user_model
from django.urls import reverse
from employees.models import (
    Department,
    DepartmentPermission,
    DepartmentRole,
    EmployeeDepartment,
)
from rest_framework import status
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

User = get_user_model()

# ---------- fixtures / helpers ----------


@pytest.fixture
def api_client():
    return APIClient()


_phone_seq = itertools.count(1000)


def _unique_phone() -> str:
    # +7999000XXX — валидный E.164, и всегда уникальный в рамках тестов
    return f"+7999000{next(_phone_seq):03d}"


def make_user(
    email: str, *, staff=False, superuser=False, verified=True, active=True, **extra
):
    """
    Создаём пользователя напрямую (без менеджера, чтобы не отправлять почту).
    """
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


def perm_for_department(code: str) -> DepartmentPermission:
    """Безопасно получаем/создаём скоуп-право отдела по коду."""
    p, _ = DepartmentPermission.objects.get_or_create(
        code=code, defaults={"name": code}
    )
    return p


def make_role(
    dept: Department, name="mgr", codes: list[str] | None = None
) -> DepartmentRole:
    r = DepartmentRole.objects.create(department=dept, name=name)
    if codes:
        r.scoped_permissions.add(*[perm_for_department(c) for c in codes])
    return r


def extract_results(data):
    if isinstance(data, dict) and "results" in data:
        return data["results"]
    return data


# ---------- tests: auth/list/basic ----------


def test_list_requires_auth(api_client: APIClient):
    url = reverse("api:v1:departments-list")
    resp = api_client.get(url)
    assert resp.status_code == status.HTTP_401_UNAUTHORIZED


def test_list_ok_for_authenticated(api_client: APIClient):
    user = make_user("u@example.com")
    api_client.force_authenticate(user=user)

    Department.objects.create(name="A")
    Department.objects.create(name="B")

    url = reverse("api:v1:departments-list")
    resp = api_client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    items = extract_results(resp.json())
    assert isinstance(items, list)
    assert len(items) == 2


def test_search_and_ordering(api_client: APIClient):
    user = make_user("u@example.com")
    api_client.force_authenticate(user=user)

    Department.objects.create(name="Alpha", description="first")
    Department.objects.create(name="Beta", description="second")
    Department.objects.create(name="Gamma", description="third")

    base = reverse("api:v1:departments-list")

    # поиск
    resp = api_client.get(base, {"search": "be"})
    assert resp.status_code == 200
    names = [d["name"] for d in extract_results(resp.json())]
    assert names == ["Beta"]

    # сортировка DESC по name
    resp = api_client.get(base, {"ordering": "-name"})
    names = [d["name"] for d in extract_results(resp.json())]
    assert names == ["Gamma", "Beta", "Alpha"]

    # и ASC для симметрии
    resp = api_client.get(base, {"ordering": "name"})
    names = [d["name"] for d in extract_results(resp.json())]
    assert names == ["Alpha", "Beta", "Gamma"]


# ---------- tests: employees_count annotation ----------


def test_employees_count_adds_head_if_not_in_links(api_client: APIClient):
    user = make_user("u@example.com")
    api_client.force_authenticate(user=user)

    head = make_user("head@example.com")
    d = Department.objects.create(name="Dept", head=head)

    e1 = make_user("e1@example.com")
    e2 = make_user("e2@example.com")
    EmployeeDepartment.objects.create(employee=e1, department=d, is_active=True)
    EmployeeDepartment.objects.create(employee=e2, department=d, is_active=True)

    url = reverse("api:v1:departments-detail", args=[d.pk])
    resp = api_client.get(url)
    assert resp.status_code == 200
    data = resp.json()
    assert data["employees_count"] == 3  # 2 + head вне связей


def test_employees_count_not_double_count_head_if_in_links(api_client: APIClient):
    user = make_user("u@example.com")
    api_client.force_authenticate(user=user)

    head = make_user("head@example.com")
    d = Department.objects.create(name="Dept", head=head)

    e1 = make_user("e1@example.com")
    e2 = make_user("e2@example.com")
    EmployeeDepartment.objects.create(employee=e1, department=d, is_active=True)
    EmployeeDepartment.objects.create(employee=e2, department=d, is_active=True)

    url = reverse("api:v1:departments-detail", args=[d.pk])
    resp = api_client.get(url)
    assert resp.status_code == 200
    data = resp.json()
    assert data["employees_count"] == 3


# ---------- tests: create/destroy ----------


def test_create_requires_staff(api_client: APIClient):
    user = make_user("u@example.com")
    api_client.force_authenticate(user=user)

    url = reverse("api:v1:departments-list")

    # не staff
    resp = api_client.post(url, {"name": "New"}, format="json")
    assert resp.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED)

    # staff
    admin = make_user("admin@example.com", staff=True)
    api_client.force_authenticate(user=admin)
    resp = api_client.post(url, {"name": "New"}, format="json")
    assert resp.status_code == status.HTTP_201_CREATED
    assert Department.objects.filter(name="New").exists()


def test_destroy_requires_staff(api_client: APIClient):
    d = Department.objects.create(name="X")
    url = reverse("api:v1:departments-detail", args=[d.pk])

    user = make_user("u@example.com")
    api_client.force_authenticate(user=user)
    resp = api_client.delete(url)
    assert resp.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_401_UNAUTHORIZED)

    admin = make_user("admin@example.com", staff=True)
    api_client.force_authenticate(user=admin)
    resp = api_client.delete(url)
    assert resp.status_code == status.HTTP_204_NO_CONTENT
    assert not Department.objects.filter(pk=d.pk).exists()


# ---------- tests: update/partial_update perms ----------


def test_partial_update_name_requires_manage_perm(api_client: APIClient):
    head = make_user("head@example.com")
    d = Department.objects.create(name="Dept", head=head)

    emp = make_user("e@example.com")
    api_client.force_authenticate(user=emp)
    EmployeeDepartment.objects.create(employee=emp, department=d, is_active=True)

    url = reverse("api:v1:departments-detail", args=[d.pk])
    # без прав
    assert (
        api_client.patch(url, {"name": "New Name"}, format="json").status_code
        == status.HTTP_403_FORBIDDEN
    )

    # даём manage_department
    r = make_role(d, "mgr", ["manage_department"])
    link = EmployeeDepartment.objects.get(employee=emp, department=d)
    link.role = r
    link.save()

    resp = api_client.patch(url, {"name": "New Name"}, format="json")
    assert resp.status_code == status.HTTP_200_OK
    d.refresh_from_db()
    assert d.name == "New Name"


def test_partial_update_head_requires_change_head_perm(api_client: APIClient):
    a = make_user("a@example.com")  # текущий head
    b = make_user("b@example.com")  # кандидат
    d = Department.objects.create(name="Dept", head=a)

    emp = make_user("e@example.com")
    api_client.force_authenticate(user=emp)
    r_manage = make_role(d, "mgr", ["manage_department"])
    EmployeeDepartment.objects.create(
        employee=emp, department=d, is_active=True, role=r_manage
    )

    url = reverse("api:v1:departments-detail", args=[d.pk])
    # только manage → 403
    assert (
        api_client.patch(url, {"head_id": b.id}, format="json").status_code
        == status.HTTP_403_FORBIDDEN
    )

    # добавляем change_department_head → 200
    r_full = make_role(d, "boss", ["manage_department", "change_department_head"])
    link = EmployeeDepartment.objects.get(employee=emp, department=d)
    link.role = r_full
    link.save()

    assert (
        api_client.patch(url, {"head_id": b.id}, format="json").status_code
        == status.HTTP_200_OK
    )
    d.refresh_from_db()
    assert d.head_id == b.id


def test_partial_update_head_same_value_does_not_require_extra_perm(
    api_client: APIClient,
):
    a = make_user("a@example.com")
    d = Department.objects.create(name="Dept", head=a)

    emp = make_user("e@example.com")
    api_client.force_authenticate(user=emp)
    r_manage = make_role(d, "mgr", ["manage_department"])
    EmployeeDepartment.objects.create(
        employee=emp, department=d, is_active=True, role=r_manage
    )

    url = reverse("api:v1:departments-detail", args=[d.pk])
    assert (
        api_client.patch(url, {"head_id": a.id}, format="json").status_code
        == status.HTTP_200_OK
    )
    d.refresh_from_db()
    assert d.head_id == a.id


# ---------- tests: action set_head ----------


def test_set_head_by_role_with_perm(api_client: APIClient):
    head = make_user("head@example.com")
    d = Department.objects.create(name="Dept", head=head)
    candidate = make_user("cand@example.com")

    manager = make_user("m@example.com")
    api_client.force_authenticate(user=manager)
    r = make_role(d, "changer", ["change_department_head"])
    EmployeeDepartment.objects.create(
        employee=manager, department=d, is_active=True, role=r
    )

    url = reverse("api:v1:departments-set-head", args=[d.pk])
    resp = api_client.post(url, {"head_id": candidate.id}, format="json")
    assert resp.status_code == 200
    d.refresh_from_db()
    assert d.head_id == candidate.id


def test_set_head_validation_inactive_employee(api_client: APIClient):
    head = make_user("head@example.com")
    d = Department.objects.create(name="Dept", head=head)
    inactive = make_user(
        "inactive@example.com", verified=False
    )  # is_actually_active=False

    manager = make_user("m@example.com")
    api_client.force_authenticate(user=manager)
    r = make_role(d, "changer", ["change_department_head"])
    EmployeeDepartment.objects.create(
        employee=manager, department=d, is_active=True, role=r
    )

    url = reverse("api:v1:departments-set-head", args=[d.pk])
    assert (
        api_client.post(url, {"head_id": inactive.id}, format="json").status_code
        == status.HTTP_400_BAD_REQUEST
    )


def test_set_head_remove_with_null(api_client: APIClient):
    head = make_user("head@example.com")
    d = Department.objects.create(name="Dept", head=head)

    manager = make_user("m@example.com")
    api_client.force_authenticate(user=manager)
    r = make_role(d, "changer", ["change_department_head"])
    EmployeeDepartment.objects.create(
        employee=manager, department=d, is_active=True, role=r
    )

    url = reverse("api:v1:departments-set-head", args=[d.pk])
    assert (
        api_client.post(url, {"head_id": None}, format="json").status_code
        == status.HTTP_204_NO_CONTENT
    )
    d.refresh_from_db()
    assert d.head_id is None


def test_set_head_requires_perm(api_client: APIClient):
    head = make_user("head@example.com")
    d = Department.objects.create(name="Dept", head=head)
    candidate = make_user("cand@example.com")

    emp = make_user("e@example.com")
    api_client.force_authenticate(user=emp)
    EmployeeDepartment.objects.create(
        employee=emp, department=d, is_active=True
    )  # без роли

    url = reverse("api:v1:departments-set-head", args=[d.pk])
    assert (
        api_client.post(url, {"head_id": candidate.id}, format="json").status_code
        == status.HTTP_403_FORBIDDEN
    )


# ---------- tests: action set_member_role ----------


def test_set_member_role_happy_path(api_client: APIClient):
    d = Department.objects.create(name="Dept")

    manager = make_user("m@example.com")
    api_client.force_authenticate(user=manager)
    r_assign = make_role(d, "assigner", ["assign_department_role"])
    EmployeeDepartment.objects.create(
        employee=manager, department=d, is_active=True, role=r_assign
    )

    emp = make_user("e@example.com")
    EmployeeDepartment.objects.create(employee=emp, department=d, is_active=True)

    r_worker = make_role(d, "worker", [])

    url = reverse("api:v1:departments-set-member-role", args=[d.pk])
    payload = {"employee_id": emp.id, "role_id": r_worker.id, "is_active": True}
    resp = api_client.post(url, payload, format="json")
    assert resp.status_code == 200
    data = resp.json()
    assert data["employee_id"] == emp.id
    assert data["role_id"] == r_worker.id
    assert data["is_active"] is True


def test_set_member_role_reject_foreign_role(api_client: APIClient):
    d1 = Department.objects.create(name="D1")
    d2 = Department.objects.create(name="D2")

    manager = make_user("m@example.com")
    api_client.force_authenticate(user=manager)
    r_assign = make_role(d1, "assigner", ["assign_department_role"])
    EmployeeDepartment.objects.create(
        employee=manager, department=d1, is_active=True, role=r_assign
    )

    emp = make_user("e@example.com")
    EmployeeDepartment.objects.create(employee=emp, department=d1, is_active=True)

    foreign_role = make_role(d2, "other", [])

    url = reverse("api:v1:departments-set-member-role", args=[d1.pk])
    resp = api_client.post(
        url, {"employee_id": emp.id, "role_id": foreign_role.id}, format="json"
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_set_member_role_requires_perm(api_client: APIClient):
    d = Department.objects.create(name="Dept")
    manager = make_user("m@example.com")
    api_client.force_authenticate(user=manager)
    EmployeeDepartment.objects.create(
        employee=manager, department=d, is_active=True
    )  # без прав

    emp = make_user("e@example.com")
    EmployeeDepartment.objects.create(employee=emp, department=d, is_active=True)
    role = make_role(d, "worker", [])

    url = reverse("api:v1:departments-set-member-role", args=[d.pk])
    resp = api_client.post(
        url, {"employee_id": emp.id, "role_id": role.id}, format="json"
    )
    assert resp.status_code == status.HTTP_403_FORBIDDEN


def test_set_member_role_missing_employee_id(api_client: APIClient):
    d = Department.objects.create(name="Dept")
    manager = make_user("m@example.com")
    api_client.force_authenticate(user=manager)
    r_assign = make_role(d, "assigner", ["assign_department_role"])
    EmployeeDepartment.objects.create(
        employee=manager, department=d, is_active=True, role=r_assign
    )

    url = reverse("api:v1:departments-set-member-role", args=[d.pk])
    resp = api_client.post(url, {"role_id": None}, format="json")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
