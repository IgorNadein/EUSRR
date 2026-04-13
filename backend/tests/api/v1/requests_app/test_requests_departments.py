# mypy: ignore-errors
from __future__ import annotations

from typing import Any

import pytest
from django.utils.crypto import get_random_string

from employees.models import (
    Department,
    DepartmentPermission,
    DepartmentRole,
    EmployeeDepartment,
)
from tests.test_config import API_REQUESTS_URL


API_BASE = API_REQUESTS_URL


def _grant_dept_perm(user, dept, code: str) -> None:
    """Выдаёт пользователю департаментное право для проверки отсутствия байпаса."""
    perm, _ = DepartmentPermission.objects.get_or_create(
        code=code, defaults={"name": code}
    )
    role, _ = DepartmentRole.objects.get_or_create(
        department=dept, name=f"auto-{code}"
    )
    role.scoped_permissions.add(perm)

    link, _ = EmployeeDepartment.objects.get_or_create(
        employee=user, department=dept, defaults={"is_active": True}
    )
    link.is_active = True
    link.role = role
    link.save(update_fields=["is_active", "role"])


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
    """Два владельца и две заявки в разных отделах."""
    d1, d2 = two_departments
    owner1 = make_user(email=f"owner1-{get_random_string(6).lower()}@example.com")
    owner2 = make_user(email=f"owner2-{get_random_string(6).lower()}@example.com")

    EmployeeDepartment.objects.get_or_create(
        employee=owner1, department=d1, defaults={"is_active": True}
    )
    EmployeeDepartment.objects.get_or_create(
        employee=owner2, department=d2, defaults={"is_active": True}
    )

    req1 = make_request(employee=owner1)
    req2 = make_request(employee=owner2)
    req1.department = d1
    req1.save(update_fields=["department"])
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


@pytest.mark.django_db
def test_department_view_permission_does_not_grant_list_visibility(
    auth_client, make_user, dept_dataset
):
    """Права отдела не раскрывают заявки вне participant-only модели."""
    data = dept_dataset
    manager = make_user(email=f"manager-{get_random_string(6).lower()}@example.com")
    _grant_dept_perm(manager, data["dept1"], "view_request")

    resp = auth_client(manager).get(API_BASE)

    assert resp.status_code == 200
    assert _results(resp.json()) == []


@pytest.mark.django_db
def test_department_view_permission_does_not_grant_detail_visibility(
    auth_client, make_user, dept_dataset
):
    """Даже детальный просмотр требует участия в заявке."""
    data = dept_dataset
    manager = make_user(email=f"manager2-{get_random_string(6).lower()}@example.com")
    _grant_dept_perm(manager, data["dept1"], "view_request")

    resp = auth_client(manager).get(f"{API_BASE}{data['req1'].id}/")

    assert resp.status_code == 403


@pytest.mark.django_db
def test_department_comment_permissions_do_not_grant_comment_access(
    auth_client, make_user, dept_dataset
):
    """Права отдела на комментарии больше не открывают комментарии без участия."""
    data = dept_dataset
    viewer = make_user(email=f"viewer-{get_random_string(6).lower()}@example.com")
    adder = make_user(email=f"adder-{get_random_string(6).lower()}@example.com")

    _grant_dept_perm(viewer, data["dept1"], "view_requestcomment")
    _grant_dept_perm(adder, data["dept1"], "add_requestcomment")

    get_resp = auth_client(viewer).get(f"{API_BASE}{data['req1'].id}/comments/")
    post_resp = auth_client(adder).post(
        f"{API_BASE}{data['req1'].id}/comments/",
        data={"text": "forbidden"},
        format="json",
    )

    assert get_resp.status_code == 403
    assert post_resp.status_code == 403


@pytest.mark.django_db
def test_department_processor_can_approve_only_as_direct_recipient(
    auth_client, make_user, dept_dataset
):
    """Департаментная роль не важна: решает только прямой получатель."""
    data = dept_dataset
    processor = make_user(
        email=f"processor-{get_random_string(6).lower()}@example.com"
    )
    _grant_dept_perm(processor, data["dept1"], "can_process_requests")
    data["req1"].recipients.add(processor)

    resp = auth_client(processor).post(f"{API_BASE}{data['req1'].id}/approve/")

    assert resp.status_code in (200, 201)


@pytest.mark.django_db
def test_department_processor_without_recipient_cannot_approve(
    auth_client, make_user, dept_dataset
):
    """Права отдела без recipients не дают approve даже в своём отделе."""
    data = dept_dataset
    processor = make_user(
        email=f"processor2-{get_random_string(6).lower()}@example.com"
    )
    _grant_dept_perm(processor, data["dept1"], "can_process_requests")

    resp = auth_client(processor).post(f"{API_BASE}{data['req1'].id}/approve/")

    assert resp.status_code == 403
