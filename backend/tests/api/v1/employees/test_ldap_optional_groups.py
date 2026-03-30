"""Тесты GroupViewSet в режиме без LDAP write-back."""

import itertools

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APIClient

User = get_user_model()
pytestmark = pytest.mark.django_db

_phone_seq = itertools.count(5000)


def _unique_phone() -> str:
    return f"+7999555{next(_phone_seq):04d}"


def make_user(email, **kwargs):
    user = User.objects.create(
        email=email,
        phone_number=kwargs.pop("phone_number", _unique_phone()),
        first_name=kwargs.pop("first_name", "Test"),
        last_name=kwargs.pop("last_name", "User"),
        is_staff=kwargs.pop("staff", False),
        is_superuser=kwargs.pop("superuser", False),
        is_active=kwargs.pop("active", True),
        email_verified=kwargs.pop("verified", True),
        **kwargs,
    )
    user.set_password("pass")
    user.save()
    return user


@pytest.fixture
def api_client():
    return APIClient()


@pytest.fixture
def admin_user():
    return make_user("admin@test.com", staff=True, superuser=True)


def test_create_group_without_ldap(api_client, admin_user, settings):
    settings.LDAP_ENABLED = False
    api_client.force_authenticate(user=admin_user)

    response = api_client.post(
        reverse("api:v1:groups-list"),
        {"name": "TestGroup"},
        format="json",
    )

    assert response.status_code == status.HTTP_201_CREATED
    assert Group.objects.filter(name="TestGroup").exists()


def test_add_members_without_ldap(api_client, admin_user, settings):
    settings.LDAP_ENABLED = False
    group = Group.objects.create(name="TestGroup")
    user1 = make_user("user1@test.com")
    user2 = make_user("user2@test.com")
    api_client.force_authenticate(user=admin_user)

    response = api_client.post(
        reverse("api:v1:groups-add-members", args=[group.id]),
        {"member_ids": [user1.id, user2.id]},
        format="json",
    )

    assert response.status_code == status.HTTP_200_OK
    assert response.data["db_added"] == 2
    assert sorted(response.data["ok_user_ids"]) == sorted([user1.id, user2.id])
    assert group.user_set.count() == 2


def test_destroy_group_without_ldap(api_client, admin_user, settings):
    settings.LDAP_ENABLED = False
    group = Group.objects.create(name="TestGroup")
    api_client.force_authenticate(user=admin_user)

    response = api_client.delete(reverse("api:v1:groups-detail", args=[group.id]))

    assert response.status_code == status.HTTP_204_NO_CONTENT
    assert not Group.objects.filter(id=group.id).exists()


def test_get_members_without_ldap(api_client, admin_user, settings):
    settings.LDAP_ENABLED = False
    group = Group.objects.create(name="TestGroup")
    user1 = make_user("user1@test.com", first_name="User", last_name="One")
    user2 = make_user("user2@test.com", first_name="User", last_name="Two")
    group.user_set.add(user1, user2)
    api_client.force_authenticate(user=admin_user)

    response = api_client.get(reverse("api:v1:groups-members", args=[group.id]))

    assert response.status_code == status.HTTP_200_OK
    assert len(response.data["employees"]) == 2
    assert {item["id"] for item in response.data["employees"]} == {user1.id, user2.id}
