import pytest
from django.urls import reverse
from model_bakery import baker
from datetime import timedelta
from django.utils import timezone

pytestmark = pytest.mark.django_db


def test_my_requests_filters_by_date_status_type(client, user, hr_user, login):
    from requests_app.models import Request

    login(user)

    now = timezone.now()
    r1 = baker.make(
        Request,
        employee=user,
        status=Request.STATUS_PENDING,
        type=Request.TYPE_VACATION,
        created_at=now - timedelta(days=10),
    )
    r2 = baker.make(
        Request,
        employee=user,
        status=Request.STATUS_PENDING,  # сначала pending
        type=Request.TYPE_SICK,
        created_at=now - timedelta(days=2),
    )
    # корректно апрувим (заполнит approver и decided_at)
    r2.approve(by_user=hr_user)

    url = reverse("requests_app:my_requests")
    params = {
        "status": Request.STATUS_APPROVED,
        "type": Request.TYPE_SICK,
        "from": (now - timedelta(days=5)).date().isoformat(),
        "to": now.date().isoformat(),
    }
    resp = client.get(url, params)
    assert resp.status_code == 200
    page = resp.context["page"]
    objs = list(page.object_list)
    assert {o.pk for o in objs} == {r2.pk}
