import pytest
from django.contrib.auth.models import Permission
from django.urls import reverse
from employees.models import Employee, Skill
from rest_framework import status
from tests.conftest import _unique_email, _unique_phone
from tests.test_config import DEFAULT_PASSWORD
from tests.api.v1.employees.test_helpers import make_user, grant_permission, make_department, extract_results

# --- helpers ---

def _mk_user(staff=False, superuser=False) -> Employee:
    u = Employee.objects.create_user(
        email=_unique_email(),
        password=DEFAULT_PASSWORD,
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

# --- tests ---

@pytest.mark.django_db
def test_list_search_ordering_requires_auth(api_client):
    url = reverse("api:v1:skills-list")
    # unauth
    resp = api_client.get(url)
    assert resp.status_code in (401, 403)

    # auth
    user = _mk_user()
    api_client.force_authenticate(user=user)
    Skill.objects.create(name="Excel")
    Skill.objects.create(name="SQL")

    resp = api_client.get(url)
    assert resp.status_code == 200
    assert isinstance(resp.data, list)
    assert {s["name"] for s in resp.data} == {"Excel", "SQL"}

    # search
    resp = api_client.get(url, {"search": "ex"})
    assert resp.status_code == 200
    assert len(resp.data) == 1 and resp.data[0]["name"] == "Excel"

    # ordering
    resp = api_client.get(url, {"ordering": "-name"})
    assert resp.status_code == 200
    names = [r["name"] for r in resp.data]
    assert names == sorted(names, reverse=True)

@pytest.mark.django_db
def test_create_allowed_for_regular_user(api_client):
    user = _mk_user()
    api_client.force_authenticate(user=user)
    url = reverse("api:v1:skills-list")
    resp = api_client.post(url, {"name": "Go"}, format="json")
    assert resp.status_code == 201
    assert Skill.objects.filter(name="Go").exists()

@pytest.mark.django_db
def test_update_delete_permissions(api_client, ensure_ldap_disabled):
    user = _mk_user()
    api_client.force_authenticate(user=user)
    s = Skill.objects.create(name="Docker")

    # update -> 403
    url_det = reverse("api:v1:skills-detail", args=[s.id])
    resp = api_client.patch(url_det, {"name": "Docker+"}, format="json")
    assert resp.status_code == 403

    # delete -> 403
    resp = api_client.delete(url_det)
    assert resp.status_code == 403

    # с правом change_skill -> PATCH разрешён
    grant_permission(user, "employees.change_skill")
    resp = api_client.patch(url_det, {"name": "Docker+"}, format="json")
    assert resp.status_code == 200
    s.refresh_from_db()
    assert s.name == "Docker+"

    # с правом delete_skill -> DELETE разрешён
    grant_permission(user, "employees.delete_skill")
    resp = api_client.delete(url_det)
    assert resp.status_code == 204
    assert not Skill.objects.filter(id=s.id).exists()

@pytest.mark.django_db
def test_staff_bypasses_permissions(api_client):
    staff = _mk_user(staff=True)
    api_client.force_authenticate(user=staff)
    s = Skill.objects.create(name="K8s")
    url_det = reverse("api:v1:skills-detail", args=[s.id])
    assert (
        api_client.patch(url_det, {"name": "Kubernetes"}, format="json").status_code
        == 200
    )
    assert api_client.delete(url_det).status_code == 204

@pytest.mark.django_db
def test_bulk_create_by_regular_user(api_client):
    user = _mk_user()
    api_client.force_authenticate(user=user)
    url = reverse("api:v1:skills-bulk-create")

    resp = api_client.post(
        url, {"names": [" Python ", "python", "SQL", ""]}, format="json"
    )
    assert resp.status_code == 201
    data = resp.data
    assert data["created_count"] == 2
    created_names = {row["name"] for row in data["created"]}
    assert created_names == {"Python", "SQL"}

@pytest.mark.django_db
def test_merge_requires_perm_and_reassigns(api_client, ensure_ldap_disabled):
    user = _mk_user()
    api_client.force_authenticate(user=user)

    src = Skill.objects.create(name="Js")
    dst = Skill.objects.create(name="JavaScript")

    e1 = _mk_user()
    e2 = _mk_user()
    e1.skills.add(src)
    e2.skills.add(src)

    url = reverse("api:v1:skills-merge")

    # без прав -> 403
    resp = api_client.post(
        url, {"source_id": src.id, "target_id": dst.id}, format="json"
    )
    assert resp.status_code == 403

    grant_permission(user, "employees.change_skill")
    resp = api_client.post(
        url, {"source_id": src.id, "target_id": dst.id}, format="json"
    )
    assert resp.status_code == 200
    e1.refresh_from_db()
    e2.refresh_from_db()
    assert dst in e1.skills.all() and dst in e2.skills.all()
    assert src not in e1.skills.all() and src not in e2.skills.all()
    assert not Skill.objects.filter(
        id=src.id
    ).exists()  # по умолчанию delete_source=True

@pytest.mark.django_db
def test_merge_same_id_and_invalid_ids(api_client):
    user = _mk_user()
    api_client.force_authenticate(user=user)
    grant_permission(user, "employees.change_skill")
    s = Skill.objects.create(name="A")

    url = reverse("api:v1:skills-merge")
    # same id
    resp = api_client.post(url, {"source_id": s.id, "target_id": s.id}, format="json")
    assert resp.status_code == 400

    # not found
    resp = api_client.post(url, {"source_id": 999999, "target_id": s.id}, format="json")
    assert resp.status_code in (404,)

@pytest.mark.django_db
def test_merge_without_reassign_or_delete(api_client):
    user = _mk_user()
    api_client.force_authenticate(user=user)
    grant_permission(user, "employees.change_skill")

    src = Skill.objects.create(name="ML")
    dst = Skill.objects.create(name="Machine Learning")
    e = _mk_user()
    e.skills.add(src)

    url = reverse("api:v1:skills-merge")
    resp = api_client.post(
        url,
        {
            "source_id": src.id,
            "target_id": dst.id,
            "reassign": False,
            "delete_source": False,
        },
        format="json",
    )
    assert resp.status_code == 200

    e.refresh_from_db()
    # не переназначили
    assert src in e.skills.all()
    assert dst not in e.skills.all()
    # источник не удалили
    assert Skill.objects.filter(id=src.id).exists()

@pytest.mark.django_db
def test_merge_idempotent_if_employee_already_has_target(api_client):
    user = _mk_user()
    api_client.force_authenticate(user=user)
    grant_permission(user, "employees.change_skill")

    src = Skill.objects.create(name="Golang")
    dst = Skill.objects.create(name="Go")
    e = _mk_user()
    e.skills.add(src, dst)

    url = reverse("api:v1:skills-merge")
    resp = api_client.post(
        url, {"source_id": src.id, "target_id": dst.id}, format="json"
    )
    assert resp.status_code == 200

    e.refresh_from_db()
    assert dst in e.skills.all()
    assert src not in e.skills.all()
