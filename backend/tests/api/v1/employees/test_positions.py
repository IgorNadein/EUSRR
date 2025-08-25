# tests/api/v1/employees/test_positions.py
from itertools import count

import pytest
from django.contrib.auth.models import Group, Permission
from django.urls import reverse
from employees.models import Employee, Position
from rest_framework import status

# ---------- helpers ----------

_phone_seq = count(1)


def _unique_phone() -> str:
    return f"+7999{next(_phone_seq):07d}"


def _grant_perm(user: Employee, perm_code: str):
    """
    perm_code формат: 'app_label.codename', например 'employees.add_position'
    """
    try:
        app_label, codename = perm_code.split(".", 1)
    except ValueError:
        raise AssertionError("perm_code must be 'app_label.codename'")
    perm = Permission.objects.get(content_type__app_label=app_label, codename=codename)
    user.user_permissions.add(perm)
    user.save()
    return perm


def _make_user(email: str, staff: bool = False, superuser: bool = False) -> Employee:
    # Создаём пользователя через менеджер, контакты не требуются (clean не вызывается на save())
    u = Employee.objects.create_user(
        email=email,
        password="pass12345",
        phone_number=_unique_phone(),
        send_activation_email=False,
        first_name="T",
        last_name="U",
    )
    u.is_staff = staff
    u.is_superuser = superuser
    u.email_verified = True
    u.is_active = True
    u.save(update_fields=["is_staff", "is_superuser", "email_verified", "is_active"])
    return u


# ---------- tests ----------


@pytest.mark.django_db
def test_list_requires_auth(api_client):
    url = reverse("api:api_v1:positions-list")

    # unauth -> 401
    resp = api_client.get(url)
    assert resp.status_code in (status.HTTP_401_UNAUTHORIZED, status.HTTP_403_FORBIDDEN)

    # auth -> 200
    user = _make_user("user@example.com")
    api_client.force_authenticate(user=user)
    Position.objects.create(name="Manager")
    Position.objects.create(name="Engineer")

    resp = api_client.get(url)
    assert resp.status_code == status.HTTP_200_OK
    assert isinstance(resp.data, list)
    names = [p["name"] for p in resp.data]
    assert {"Manager", "Engineer"} <= set(names)


@pytest.mark.django_db
def test_create_permissions(api_client):
    url = reverse("api:api_v1:positions-list")

    # обычный пользователь без прав -> 403
    user = _make_user("user@example.com")
    api_client.force_authenticate(user=user)
    resp = api_client.post(url, {"name": "NewPos"}, format="json")
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # с пермом add_position -> 201
    _grant_perm(user, "employees.add_position")
    resp = api_client.post(url, {"name": "NewPos"}, format="json")
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.data["name"] == "NewPos"

    # staff без специальных прав -> 201 (staff допускается)
    staff = _make_user("staff@example.com", staff=True)
    api_client.force_authenticate(user=staff)
    resp = api_client.post(url, {"name": "StaffPos"}, format="json")
    assert resp.status_code == status.HTTP_201_CREATED


@pytest.mark.django_db
def test_update_permissions_and_search_ordering(api_client):
    p1 = Position.objects.create(name="Alpha", description="one")
    p2 = Position.objects.create(name="Beta", description="two")

    user = _make_user("user@example.com")
    api_client.force_authenticate(user=user)

    # без прав change_position -> 403
    url_detail = reverse("api:api_v1:positions-detail", args=[p1.id])
    resp = api_client.patch(url_detail, {"description": "updated"}, format="json")
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # выдаём change_position -> 200
    _grant_perm(user, "employees.change_position")
    resp = api_client.patch(url_detail, {"description": "updated"}, format="json")
    assert resp.status_code == status.HTTP_200_OK
    p1.refresh_from_db()
    assert p1.description == "updated"

    # проверим search & ordering
    url_list = reverse("api:api_v1:positions-list")
    resp = api_client.get(url_list, {"search": "alp"})
    assert resp.status_code == 200
    assert len(resp.data) == 1
    assert resp.data[0]["name"] == "Alpha"

    resp = api_client.get(url_list, {"ordering": "-name"})
    assert resp.status_code == 200
    names = [row["name"] for row in resp.data]
    assert names == sorted(names, reverse=True)


@pytest.mark.django_db
def test_delete_permissions(api_client):
    pos = Position.objects.create(name="ToDelete")
    user = _make_user("user@example.com")
    api_client.force_authenticate(user=user)
    url_detail = reverse("api:api_v1:positions-detail", args=[pos.id])

    # без delete_position -> 403
    resp = api_client.delete(url_detail)
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # с delete_position -> 204
    _grant_perm(user, "employees.delete_position")
    resp = api_client.delete(url_detail)
    assert resp.status_code == status.HTTP_204_NO_CONTENT
    assert not Position.objects.filter(id=pos.id).exists()


@pytest.mark.django_db
def test_set_groups_requires_special_perm(api_client):
    pos = Position.objects.create(name="RoleOwner")
    grp1 = Group.objects.create(name="grp1")
    grp2 = Group.objects.create(name="grp2")

    user = _make_user("user@example.com")
    api_client.force_authenticate(user=user)

    url_set = reverse("api:api_v1:positions-set-groups", args=[pos.id])

    # даже с change_position НЕЛЬЗЯ менять группы — нужен assign_position_groups
    _grant_perm(user, "employees.change_position")
    resp = api_client.post(url_set, {"groups": [grp1.id, grp2.id]}, format="json")
    assert resp.status_code == status.HTTP_403_FORBIDDEN

    # выдаём спец-пермиссию -> 200
    _grant_perm(user, "employees.assign_position_groups")
    resp = api_client.post(url_set, {"groups": [grp1.id, grp2.id]}, format="json")
    assert resp.status_code == status.HTTP_200_OK
    assert set(pos.groups.values_list("id", flat=True)) == {grp1.id, grp2.id}


@pytest.mark.django_db
def test_add_and_remove_groups_and_permissions_endpoint(api_client):
    # используем гарантированно существующие права
    perm_view_employee = Permission.objects.get(
        content_type__app_label="employees", codename="view_employee"
    )
    perm_view_group = Permission.objects.get(
        content_type__app_label="auth", codename="view_group"
    )

    gA = Group.objects.create(name="A")
    gA.permissions.add(perm_view_employee)

    gB = Group.objects.create(name="B")
    gB.permissions.add(perm_view_group)

    pos = Position.objects.create(name="Aggregator")

    user = _make_user("manager@example.com")
    api_client.force_authenticate(user=user)
    _grant_perm(user, "employees.assign_position_groups")

    # add_groups
    url_add = reverse("api:api_v1:positions-add-groups", args=[pos.id])
    resp = api_client.post(url_add, {"groups": [gA.id]}, format="json")
    assert resp.status_code == 200
    assert set(pos.groups.values_list("id", flat=True)) == {gA.id}

    # add_groups (добавим B, продублируем A -> в наборе A,B без дублей)
    resp = api_client.post(url_add, {"groups": [gA.id, gB.id]}, format="json")
    assert resp.status_code == 200
    assert set(pos.groups.values_list("id", flat=True)) == {gA.id, gB.id}

    # permissions endpoint
    url_perms = reverse("api:api_v1:positions-permissions", args=[pos.id])
    resp = api_client.get(url_perms)
    assert resp.status_code == 200
    codes = {row["codename"] for row in resp.data["results"]}
    assert "employees.view_employee" in codes
    assert "auth.view_group" in codes

    # remove_groups (уберём A)
    url_rm = reverse("api:api_v1:positions-remove-groups", args=[pos.id])
    resp = api_client.post(url_rm, {"groups": [gA.id]}, format="json")
    assert resp.status_code == 200
    assert set(pos.groups.values_list("id", flat=True)) == {gB.id}

    # retrieve содержит groups_verbose
    url_detail = reverse("api:api_v1:positions-detail", args=[pos.id])
    resp = api_client.get(url_detail)
    assert resp.status_code == 200
    assert "groups_verbose" in resp.data
    assert any(g["name"] == "B" for g in resp.data["groups_verbose"])


@pytest.mark.django_db
def test_groups_payload_validation(api_client):
    pos = Position.objects.create(name="Validator")
    user = _make_user("user@example.com")
    api_client.force_authenticate(user=user)
    _grant_perm(user, "employees.assign_position_groups")

    url_set = reverse("api:api_v1:positions-set-groups", args=[pos.id])

    # groups не список -> 400
    resp = api_client.post(url_set, {"groups": "not-a-list"}, format="json")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST

    # часть групп не существует -> 400
    resp = api_client.post(url_set, {"groups": [9999]}, format="json")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
