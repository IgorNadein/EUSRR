# mypy: ignore-errors
from __future__ import annotations

from typing import Any, Iterable

import pytest
from django.db import transaction
from django.utils.crypto import get_random_string

from tests.test_config import API_REQUESTS_URL

# Константа API
API_BASE = API_REQUESTS_URL


from employees.models import (
    Department,
    DepartmentRole,
    DepartmentPermission,
    EmployeeDepartment,
)


def _grant_dept_perm(user, dept, code: str) -> None:
    """Выдаёт пользователю департаментное право `code` для отдела `dept`.

    Делает так:
    - создаёт/находит DepartmentPermission(code)
    - создаёт/находит DepartmentRole(department=dept, name='auto-{code}')
    - добавляет право в role.scoped_permissions
    - создаёт/активирует EmployeeDepartment(user, dept, role=эта_роль)
    """
    perm, _ = DepartmentPermission.objects.get_or_create(
        code=code, defaults={"name": code}
    )
    role, _ = DepartmentRole.objects.get_or_create(department=dept, name=f"auto-{code}")
    role.scoped_permissions.add(perm)

    link, _ = EmployeeDepartment.objects.get_or_create(
        employee=user, department=dept, defaults={"is_active": True}
    )
    link.is_active = True
    link.role = role
    link.save(update_fields=["is_active", "role"])


# ЗАМЕНИТЕ фикстуры two_departments / dept_dataset на версии ниже
# (главное — создаём EmployeeDepartment для владельцев):

import pytest
from django.utils.crypto import get_random_string


def _random_email(prefix: str) -> str:
    return f"{prefix}-{get_random_string(6).lower()}@example.com"


def _results(payload: Any):
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "results" in payload:
        return payload["results"] or []
    return []


@pytest.fixture
def two_departments(db):
    d1 = Department.objects.create(name=f"Dept A {get_random_string(4)}")
    d2 = Department.objects.create(name=f"Dept B {get_random_string(4)}")
    return d1, d2


@pytest.fixture
def dept_dataset(db, make_user, make_request, two_departments):
    """owner1 в dept1 + его заявка; owner2 в dept2 + его заявка.
    Привязка к отделам — через EmployeeDepartment (is_active=True).
    """
    d1, d2 = two_departments
    owner1 = make_user(email=_random_email("owner1"))
    owner2 = make_user(email=_random_email("owner2"))

    EmployeeDepartment.objects.get_or_create(
        employee=owner1, department=d1, defaults={"is_active": True}
    )
    EmployeeDepartment.objects.get_or_create(
        employee=owner2, department=d2, defaults={"is_active": True}
    )

    req1 = make_request(employee=owner1)
    req2 = make_request(employee=owner2)
    # Если у Request есть FK department (есть) — выставим для консистентности:
    if hasattr(req1, "department_id"):
        req1.department = d1
        req1.save(update_fields=["department"])
    if hasattr(req2, "department_id"):
        req2.department = d2
        req2.save(update_fields=["department"])

    return {
        "dept1": d1,
        "dept2": d2,
        "owner1": owner1,
        "owner2": owner2,
        "req1": req1,
        "req2": req2,
    }


# ---------- Тесты видимости ----------


@pytest.mark.django_db
def test_dept_viewer_sees_only_own_department_requests(
    auth_client, make_user, dept_dataset
):
    """Роль/право отдела 'view_request': видит заявки своего отдела и не видит чужой."""
    data = dept_dataset
    manager = make_user(email=_random_email("manager-view"))
    # Привязываем менеджера к dept1, если у пользователя есть поле department
    if hasattr(manager, "department_id"):
        setattr(manager, "department", data["dept1"])
        manager.save(update_fields=["department"])

    _grant_dept_perm(manager, data["dept1"], "view_request")

    client = auth_client(manager)
    resp = client.get(API_BASE)
    assert resp.status_code == 200, resp.content
    items = _results(resp.json())
    ids = {x["id"] for x in items}

    assert data["req1"].id in ids, "должен видеть заявки своего отдела"
    assert data["req2"].id not in ids, "не должен видеть заявки другого отдела"


@pytest.mark.django_db
def test_dept_viewer_cannot_retrieve_other_department_request(
    auth_client, make_user, dept_dataset
):
    """Роль/право отдела 'view_request': детальный просмотр чужого отдела запрещён."""
    data = dept_dataset
    manager = make_user(email=_random_email("manager-view2"))
    if hasattr(manager, "department_id"):
        setattr(manager, "department", data["dept1"])
        manager.save(update_fields=["department"])

    _grant_dept_perm(manager, data["dept1"], "view_request")

    client = auth_client(manager)
    # Чужой отдел
    resp = client.get(f"{API_BASE}{data['req2'].id}/")
    assert resp.status_code == 403, resp.content


# ---------- Статусные экшены (approve/reject) ----------


@pytest.mark.django_db
def test_dept_processor_can_approve_own_department_request(
    auth_client, make_user, dept_dataset
):
    """Пользователь с департаментным правом обработки может approve в своём отделе."""
    data = dept_dataset
    processor = make_user(email=_random_email("processor"))
    if hasattr(processor, "department_id"):
        setattr(processor, "department", data["dept1"])
        processor.save(update_fields=["department"])

    for code in ("can_process_requests",):
        _grant_dept_perm(processor, data["dept1"], code)

    data["req1"].recipients.add(processor)

    client = auth_client(processor)
    resp = client.post(f"{API_BASE}{data['req1'].id}/approve/")
    assert resp.status_code in (200, 201), resp.content


@pytest.mark.django_db
def test_dept_processor_cannot_approve_other_department_request(
    auth_client, make_user, dept_dataset
):
    """Пользователь с департаментным правом обработки НЕ может approve в чужом отделе."""
    data = dept_dataset
    processor = make_user(email=_random_email("processor2"))
    if hasattr(processor, "department_id"):
        setattr(processor, "department", data["dept1"])
        processor.save(update_fields=["department"])

    for code in ("can_process_requests", "change_request"):
        _grant_dept_perm(processor, data["dept1"], code)

    client = auth_client(processor)
    resp = client.post(f"{API_BASE}{data['req2'].id}/approve/")
    assert resp.status_code == 403, resp.content


# ---------- Комментарии по отделам ----------


@pytest.mark.django_db
def test_dept_comment_viewer_can_read_comments_in_department(
    auth_client, make_user, dept_dataset
):
    """Право отдела 'view_requestcomment' даёт доступ к GET /comments/ в своём отделе."""
    data = dept_dataset
    viewer = make_user(email=_random_email("comm-view"))
    if hasattr(viewer, "department_id"):
        setattr(viewer, "department", data["dept1"])
        viewer.save(update_fields=["department"])

    _grant_dept_perm(viewer, data["dept1"], "view_requestcomment")

    client = auth_client(viewer)
    resp = client.get(f"{API_BASE}{data['req1'].id}/comments/")
    assert resp.status_code == 200, resp.content


@pytest.mark.django_db
def test_dept_comment_adder_can_post_in_department(
    auth_client, make_user, dept_dataset
):
    """Право отдела 'add_requestcomment' даёт доступ к POST /comments/ в своём отделе."""
    data = dept_dataset
    adder = make_user(email=_random_email("comm-add"))
    if hasattr(adder, "department_id"):
        setattr(adder, "department", data["dept1"])
        adder.save(update_fields=["department"])

    _grant_dept_perm(adder, data["dept1"], "add_requestcomment")

    client = auth_client(adder)
    resp = client.post(
        f"{API_BASE}{data['req1'].id}/comments/", data={"text": "ok"}, format="json"
    )
    assert resp.status_code == 201, resp.content


@pytest.mark.django_db
def test_dept_comment_viewer_forbidden_in_other_department(
    auth_client, make_user, dept_dataset
):
    """Право отдела 'view_requestcomment' НЕ раскрывает комментарии чужого отдела."""
    data = dept_dataset
    viewer = make_user(email=_random_email("comm-view2"))
    if hasattr(viewer, "department_id"):
        setattr(viewer, "department", data["dept1"])
        viewer.save(update_fields=["department"])

    _grant_dept_perm(viewer, data["dept1"], "view_requestcomment")

    client = auth_client(viewer)
    resp = client.get(f"{API_BASE}{data['req2'].id}/comments/")
    assert resp.status_code == 403, resp.content


# ---------- Создание/валидация department ----------


@pytest.mark.django_db
def test_regular_user_cannot_set_foreign_department_on_create(
    auth_client, regular_user, two_departments
):
    """Обычный пользователь не должен уметь подставлять чужой department при создании.

    Ожидаем: либо игнор (проставится свой отдел), либо 400/403.
    """
    d1, d2 = two_departments
    # Привяжем пользователя к dept1, если поле есть:
    if hasattr(regular_user, "department_id"):
        setattr(regular_user, "department", d1)
        regular_user.save(update_fields=["department"])

    client = auth_client(regular_user)
    payload = {
        "type": "vacation",
        "title": "Попытка в чужой отдел",
        "comment": "…",
        # пробуем подменить отдел
        "department": getattr(d2, "id", None),
    }
    resp = client.post(API_BASE, data=payload, format="json")

    # Допустимы два корректных варианта поведения: запрет или игнор чужого отдела.
    if resp.status_code in (400, 403):
        return
    assert resp.status_code == 201, resp.content
    data = resp.json()
    # Если заявка создалась — проверяем, что отдел НЕ чужой
    if (
        "department" in data
        and isinstance(data["department"], dict)
        and "id" in data["department"]
    ):
        assert data["department"]["id"] != getattr(d2, "id", -1)