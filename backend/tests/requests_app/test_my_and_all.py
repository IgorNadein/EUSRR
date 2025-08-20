import pytest
from django.urls import reverse
from model_bakery import baker

pytestmark = pytest.mark.django_db


def test_my_requests_shows_only_own(client, user, other_user, login):
    from requests_app.models import Request
    mine = baker.make(Request, employee=user, status=Request.STATUS_PENDING, _quantity=2)
    other = baker.make(Request, employee=other_user, status=Request.STATUS_PENDING, _quantity=3)

    login(user)
    resp = client.get(reverse("requests_app:my_requests"))
    assert resp.status_code == 200
    page = resp.context["page"]
    ids = {obj.pk for obj in page.object_list}
    assert set(r.pk for r in mine).issubset(ids)
    assert not any(r.pk in ids for r in other)


def test_all_requests_requires_hr(client, user, hr_user, login):
    # гость → редирект на логин
    resp = client.get(reverse("requests_app:all_requests"))
    assert resp.status_code in (302, 303)

    # не-HR → тоже редирект на логин (так работает user_passes_test без raise_exception)
    login(user)
    resp = client.get(reverse("requests_app:all_requests"))
    assert resp.status_code in (302, 303)

    # HR → ок
    login(hr_user)
    resp = client.get(reverse("requests_app:all_requests"))
    assert resp.status_code == 200
