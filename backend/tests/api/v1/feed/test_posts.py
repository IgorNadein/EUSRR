from __future__ import annotations

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from employees.models import DepartmentPermission
from employees.models import (
    DepartmentRole,
    EmployeeDepartment,
    RoleAssignment,
)
from feed.models import Post
from rest_framework import status

from tests.test_config import API_POSTS_URL

pytestmark = pytest.mark.django_db


def _department_post_payload(department_id: int, **extra):
    payload = {
        "type": "department",
        "department": department_id,
        "title": "Новость отдела",
        "body": "Важное объявление",
    }
    payload.update(extra)
    return payload


def _grant_department_feed_role(user, department):
    permission, _ = DepartmentPermission.objects.get_or_create(
        code="manage_department_feed",
        defaults={"name": "Редактировать публикации отдела"},
    )
    role = DepartmentRole.objects.create(
        department=department,
        name=f"Feed manager {user.id}",
    )
    role.scoped_permissions.add(permission)
    RoleAssignment.objects.create(
        employee=user,
        role=role,
        is_active=True,
    )
    return role


def test_create_department_post_notifies_active_members_and_role_only(
    monkeypatch,
    auth_client_factory,
    make_user,
    department_factory,
):
    author = make_user("author@example.com")
    department = department_factory(name="Finance", head=author)
    member = make_user("member@example.com")
    role_only = make_user("roleonly@example.com")
    inactive_member = make_user("inactive@example.com", active=False)

    EmployeeDepartment.objects.create(
        employee=member,
        department=department,
        is_active=True,
    )
    EmployeeDepartment.objects.create(
        employee=inactive_member,
        department=department,
        is_active=True,
    )

    role = DepartmentRole.objects.create(
        department=department,
        name="Observer",
    )
    RoleAssignment.objects.create(
        employee=role_only,
        role=role,
        is_active=True,
    )

    captured = []

    def _capture_notify(*args, **kwargs):
        captured.append(kwargs)

    monkeypatch.setattr("feed.notifications.handlers.notify.send", _capture_notify)

    client = auth_client_factory(author)
    response = client.post(
        API_POSTS_URL,
        _department_post_payload(department.id),
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    post = Post.objects.get(id=response.data["id"])
    assert post.department_id == department.id

    recipient_ids = {payload["recipient"].id for payload in captured}
    assert member.id in recipient_ids
    assert role_only.id in recipient_ids
    assert inactive_member.id not in recipient_ids
    assert author.id not in recipient_ids


def test_create_department_post_with_attachment_and_empty_body(
    auth_client_factory,
    make_user,
    department_factory,
):
    author = make_user("head@example.com")
    department = department_factory(name="HR", head=author)
    attachment = SimpleUploadedFile(
        "memo.txt",
        b"department announcement",
        content_type="text/plain",
    )

    client = auth_client_factory(author)
    response = client.post(
        API_POSTS_URL,
        _department_post_payload(
            department.id,
            body="",
            attachment=attachment,
        ),
        format="multipart",
    )

    assert response.status_code == status.HTTP_201_CREATED
    post = Post.objects.get(id=response.data["id"])
    assert post.attachment.name
    assert post.body == ""


def test_create_department_post_requires_department_not_403(
    auth_client_factory,
    make_user,
):
    author = make_user("author@example.com", staff=True)
    client = auth_client_factory(author)

    response = client.post(
        API_POSTS_URL,
        {
            "type": "department",
            "title": "Без отдела",
            "body": "Тело",
        },
        format="json",
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "department" in response.data


def test_department_post_requires_publish_permission(
    auth_client_factory,
    make_user,
    department_factory,
):
    user = make_user("plain@example.com")
    department = department_factory(name="Legal")
    client = auth_client_factory(user)

    response = client.post(
        API_POSTS_URL,
        _department_post_payload(department.id),
        format="json",
    )

    assert response.status_code == status.HTTP_403_FORBIDDEN


def test_active_department_member_can_create_department_post(
    auth_client_factory,
    make_user,
    department_factory,
):
    user = make_user("member-publisher@example.com")
    department = department_factory(name="Operations")
    EmployeeDepartment.objects.create(
        employee=user,
        department=department,
        is_active=True,
    )

    client = auth_client_factory(user)
    response = client.post(
        API_POSTS_URL,
        _department_post_payload(department.id),
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert Post.objects.filter(id=response.data["id"], department=department).exists()


def test_any_role_assignment_can_create_department_post(
    auth_client_factory,
    make_user,
    department_factory,
):
    user = make_user("roleonly-publisher@example.com")
    department = department_factory(name="Support")
    role = DepartmentRole.objects.create(
        department=department,
        name="Observer",
    )
    RoleAssignment.objects.create(
        employee=user,
        role=role,
        is_active=True,
    )

    client = auth_client_factory(user)
    response = client.post(
        API_POSTS_URL,
        _department_post_payload(department.id),
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert Post.objects.filter(id=response.data["id"], department=department).exists()


def test_department_post_patch_requires_manage_feed_permission(
    auth_client_factory,
    make_user,
    department_factory,
):
    author = make_user("author-edit@example.com")
    editor = make_user("editor@example.com")
    member_without_perm = make_user("member-without-feed@example.com")
    department = department_factory(name="Accounting", head=author)
    post = Post.objects.create(
        author=author,
        department=department,
        type="department",
        title="До редактирования",
        body="body",
    )

    EmployeeDepartment.objects.create(
        employee=member_without_perm,
        department=department,
        is_active=True,
    )
    _grant_department_feed_role(editor, department)

    member_client = auth_client_factory(member_without_perm)
    response = member_client.patch(
        f"{API_POSTS_URL}{post.id}/",
        {"title": "Не должно пройти"},
        format="json",
    )
    assert response.status_code == status.HTTP_403_FORBIDDEN

    editor_client = auth_client_factory(editor)
    response = editor_client.patch(
        f"{API_POSTS_URL}{post.id}/",
        {"title": "После редактирования"},
        format="json",
    )
    assert response.status_code == status.HTTP_200_OK

    post.refresh_from_db()
    assert post.title == "После редактирования"


def test_department_post_delete_requires_manage_feed_permission(
    auth_client_factory,
    make_user,
    department_factory,
):
    author = make_user("author-delete@example.com")
    editor = make_user("feed-editor@example.com")
    member_without_perm = make_user("member-without-delete@example.com")
    department = department_factory(name="Finance", head=author)
    post = Post.objects.create(
        author=author,
        department=department,
        type="department",
        title="Удаляемый пост",
        body="body",
    )

    EmployeeDepartment.objects.create(
        employee=member_without_perm,
        department=department,
        is_active=True,
    )
    _grant_department_feed_role(editor, department)

    member_client = auth_client_factory(member_without_perm)
    response = member_client.delete(f"{API_POSTS_URL}{post.id}/")
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert Post.objects.filter(id=post.id).exists()

    editor_client = auth_client_factory(editor)
    response = editor_client.delete(f"{API_POSTS_URL}{post.id}/")
    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Post.objects.filter(id=post.id).exists()


def test_list_department_posts_filtered_by_department(
    auth_client_factory,
    make_user,
    department_factory,
):
    viewer = make_user("viewer@example.com")
    department_a = department_factory(name="Dept A")
    department_b = department_factory(name="Dept B")

    Post.objects.create(
        author=viewer,
        department=department_a,
        type="department",
        title="A1",
        body="one",
    )
    Post.objects.create(
        author=viewer,
        department=department_b,
        type="department",
        title="B1",
        body="two",
    )

    client = auth_client_factory(viewer)
    response = client.get(API_POSTS_URL, {"type": "department", "department": department_a.id})

    assert response.status_code == status.HTTP_200_OK
    payload = response.data["results"] if isinstance(response.data, dict) else response.data
    assert len(payload) == 1
    assert payload[0]["department_id"] == department_a.id


def test_department_pin_scope_is_separate_from_global_feed(
    auth_client_factory,
    make_user,
    department_factory,
):
    moderator = make_user("moderator@example.com", staff=True)
    department = department_factory(name="Finance")
    post = Post.objects.create(
        author=moderator,
        department=department,
        type="department",
        title="Scoped pin",
        body="body",
    )

    client = auth_client_factory(moderator)
    response = client.post(f"{API_POSTS_URL}{post.id}/pin/?scope=department")

    assert response.status_code == status.HTTP_200_OK
    post.refresh_from_db()
    assert post.pinned_department is True
    assert post.pinned_global is False

    global_list = client.get(API_POSTS_URL)
    global_payload = (
        global_list.data["results"]
        if isinstance(global_list.data, dict)
        else global_list.data
    )
    scoped_global = next(item for item in global_payload if item["id"] == post.id)
    assert scoped_global["pinned"] is False
    assert scoped_global["pinned_global"] is False
    assert scoped_global["pinned_department"] is True

    department_list = client.get(
        API_POSTS_URL,
        {
            "type": "department",
            "department": department.id,
            "pin_scope": "department",
        },
    )
    department_payload = (
        department_list.data["results"]
        if isinstance(department_list.data, dict)
        else department_list.data
    )
    scoped_department = next(
        item for item in department_payload if item["id"] == post.id
    )
    assert scoped_department["pinned"] is True


def test_global_pin_scope_is_separate_from_department_feed(
    auth_client_factory,
    make_user,
    department_factory,
):
    moderator = make_user("chief@example.com", staff=True)
    department = department_factory(name="HR")
    post = Post.objects.create(
        author=moderator,
        department=department,
        type="department",
        title="Global scoped pin",
        body="body",
    )

    client = auth_client_factory(moderator)
    response = client.post(f"{API_POSTS_URL}{post.id}/pin/?scope=global")

    assert response.status_code == status.HTTP_200_OK
    post.refresh_from_db()
    assert post.pinned_global is True
    assert post.pinned_department is False

    department_list = client.get(
        API_POSTS_URL,
        {
            "type": "department",
            "department": department.id,
            "pin_scope": "department",
        },
    )
    department_payload = (
        department_list.data["results"]
        if isinstance(department_list.data, dict)
        else department_list.data
    )
    scoped_department = next(
        item for item in department_payload if item["id"] == post.id
    )
    assert scoped_department["pinned"] is False


def test_department_pin_scope_rejected_for_non_department_post(
    auth_client_factory,
    make_user,
):
    moderator = make_user("staff@example.com", staff=True)
    post = Post.objects.create(
        author=moderator,
        type="company",
        title="Company post",
        body="body",
    )

    client = auth_client_factory(moderator)
    response = client.post(f"{API_POSTS_URL}{post.id}/pin/?scope=department")

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "detail" in response.data
