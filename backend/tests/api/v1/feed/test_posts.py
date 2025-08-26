import pytest
from django.urls import reverse
from django.contrib.auth.models import Permission
from rest_framework import status

from employees.models import Employee, Department, EmployeeDepartment, DepartmentRole
from feed.models import Post
from feed.constants import TYPE_COMPANY, TYPE_DEPARTMENT, TYPE_EMPLOYEE


# ----------------- helpers -----------------

_seq = 1
def _uniq_email(prefix="user"):
    global _seq
    _seq += 1
    return f"{prefix}{_seq}@example.com"

def _uniq_phone():
    global _seq
    _seq += 1
    return f"+7999{_seq:07d}"

def _user(staff=False, superuser=False) -> Employee:
    u = Employee.objects.create_user(
        email=_uniq_email(), password="pass",
        phone_number=_uniq_phone(),
        send_activation_email=False, first_name="T", last_name="U",
    )
    if staff:
        u.is_staff = True
    if superuser:
        u.is_superuser = True
    u.email_verified = True
    u.is_active = True
    u.save(update_fields=["is_staff", "is_superuser", "email_verified", "is_active"])
    # сбрасываем кеши прав на всякий
    for attr in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
        if hasattr(u, attr):
            try: delattr(u, attr)
            except: pass
    return u

def _grant_user_perm(user: Employee, perm_code: str):
    """
    perm_code: 'app_label.codename', напр. 'feed.publish_company_post'
    """
    app_label, codename = perm_code.split(".", 1)
    p = Permission.objects.get(content_type__app_label=app_label, codename=codename)
    user.user_permissions.add(p)
    user.save()
    for attr in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
        if hasattr(user, attr):
            try: delattr(user, attr)
            except: pass
    return p

def _grant_dept_role_perm(user: Employee, dept: Department, perm_code: str):
    """
    Создаёт DepartmentRole с указанным Permission и выдаёт её пользователю в отделе.
    """
    app_label, codename = perm_code.split(".", 1)
    p = Permission.objects.get(content_type__app_label=app_label, codename=codename)
    role = DepartmentRole.objects.create(department=dept, name="Publisher")
    role.permissions.add(p)
    EmployeeDepartment.objects.create(employee=user, department=dept, role=role, is_active=True)
    return role

def _items(resp):
    # поддержка пагинации и без
    if isinstance(resp.data, dict) and "results" in resp.data:
        return resp.data["results"]
    return resp.data


# ----------------- tests -----------------

@pytest.mark.django_db
def test_list_requires_auth(api_client):
    url = reverse("api:api_v1:posts-list")
    assert api_client.get(url).status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    user = _user()
    api_client.force_authenticate(user=user)
    assert api_client.get(url).status_code == status.HTTP_200_OK


@pytest.mark.django_db
def test_create_company_requires_staff_or_perm(api_client):
    url = reverse("api:api_v1:posts-list")
    author = _user()
    api_client.force_authenticate(user=author)

    payload = {
        "type": TYPE_COMPANY,
        "title": "Company News",
        "body": "hello",
        # department не указываем
    }

    # без прав -> 403
    resp = api_client.post(url, payload, format="multipart")
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # выдаём feed.publish_company_post -> 201
    _grant_user_perm(author, "feed.publish_company_post")
    resp = api_client.post(url, payload, format="multipart")
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.data["type"] == TYPE_COMPANY
    assert resp.data.get("department") is None

    # staff тоже может -> 201
    staff = _user(staff=True)
    api_client.force_authenticate(user=staff)
    resp = api_client.post(url, payload, format="multipart")
    assert resp.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_create_department_requires_head_or_role_or_staff(api_client):
    url = reverse("api:api_v1:posts-list")
    dept = Department.objects.create(name="R&D")

    u = _user()
    api_client.force_authenticate(user=u)

    payload = {
        "type": TYPE_DEPARTMENT,
        "title": "Dept News",
        "body": "text",
        "department": dept.id,
    }

    # без прав -> 403
    resp = api_client.post(url, payload, format="multipart")
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # глава отдела -> 201
    head = _user()
    dept.head = head
    dept.save(update_fields=["head"])
    api_client.force_authenticate(user=head)
    resp = api_client.post(url, payload, format="multipart")
    assert resp.status_code == status.HTTP_201_CREATED

    # сотрудник с ролью, имеющей publish_department_post -> 201
    member = _user()
    _grant_dept_role_perm(member, dept, "feed.publish_department_post")
    api_client.force_authenticate(user=member)
    resp = api_client.post(url, payload, format="multipart")
    assert resp.status_code == status.HTTP_201_CREATED

    # staff -> 201
    staff = _user(staff=True)
    api_client.force_authenticate(user=staff)
    resp = api_client.post(url, payload, format="multipart")
    assert resp.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_employee_type_is_forbidden_and_department_field_validation(api_client):
    url = reverse("api:api_v1:posts-list")
    staff = _user(staff=True)
    api_client.force_authenticate(user=staff)
    dept = Department.objects.create(name="Ops")

    # TYPE_EMPLOYEE вообще нельзя
    resp = api_client.post(url, {"type": TYPE_EMPLOYEE, "title": "x", "body": "b"}, format="multipart")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST

    # type=department, но department не указан -> 400
    resp = api_client.post(url, {"type": TYPE_DEPARTMENT, "title": "x", "body": "b"}, format="multipart")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST

    # type!=department, но department указан -> 400
    resp = api_client.post(
        url,
        {"type": TYPE_COMPANY, "title": "x", "body": "b", "department": dept.id},
        format="multipart",
    )
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


@pytest.mark.django_db
def test_update_and_delete_permissions_match_create_rules(api_client):
    dept = Department.objects.create(name="QA")
    head = _user()
    dept.head = head
    dept.save(update_fields=["head"])

    # создаём пост отдела от лица главы
    api_client.force_authenticate(user=head)
    url = reverse("api:api_v1:posts-list")
    resp = api_client.post(
        url,
        {"type": TYPE_DEPARTMENT, "title": "t1", "body": "b1", "department": dept.id},
        format="multipart",
    )
    assert resp.status_code == status.HTTP_201_CREATED
    post_id = resp.data["id"]

    url_detail = reverse("api:api_v1:posts-detail", args=[post_id])

    # другой обычный пользователь не может править/удалять
    stranger = _user()
    api_client.force_authenticate(user=stranger)
    assert api_client.patch(url_detail, {"title": "nope"}, format="json").status_code == status.HTTP_403_FORBIDDEN
    assert api_client.delete(url_detail).status_code == status.HTTP_403_FORBIDDEN

    # выдаём этому пользователю роль с правом публикации в отделе -> теперь может править
    _grant_dept_role_perm(stranger, dept, "feed.publish_department_post")
    assert api_client.patch(url_detail, {"title": "ok"}, format="json").status_code == status.HTTP_200_OK

    # и удалять
    assert api_client.delete(url_detail).status_code == status.HTTP_204_NO_CONTENT


@pytest.mark.django_db
def test_list_by_author_shows_all_authors_posts(api_client):
    # автор со всеми нужными правами, чтобы создавать через API
    author = _user()
    _grant_user_perm(author, "feed.publish_company_post")
    dept = Department.objects.create(name="Support")
    _grant_dept_role_perm(author, dept, "feed.publish_department_post")

    api_client.force_authenticate(user=author)
    url = reverse("api:api_v1:posts-list")

    # company пост
    r1 = api_client.post(
        url, {"type": TYPE_COMPANY, "title": "c", "body": "b"}, format="multipart"
    )
    assert r1.status_code == status.HTTP_201_CREATED

    # department пост
    r2 = api_client.post(
        url,
        {"type": TYPE_DEPARTMENT, "title": "d", "body": "b", "department": dept.id},
        format="multipart",
    )
    assert r2.status_code == status.HTTP_201_CREATED

    # выборка по author
    lurl = f"{url}?author={author.id}"
    resp = api_client.get(lurl)
    assert resp.status_code == status.HTTP_200_OK
    items = _items(resp)
    ids = {row["id"] for row in items}
    assert ids == {r1.data["id"], r2.data["id"]}

    # убедимся, что тип employee не проходит (на всякий)
    assert all(row["type"] in (TYPE_COMPANY, TYPE_DEPARTMENT) for row in items)
