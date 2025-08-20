import pytest
from django.urls import reverse
from django import forms

pytestmark = pytest.mark.django_db


def test_request_process_approve_and_soft_fields(client, hr_user, request_obj, login, monkeypatch):
    from requests_app.models import Request
    login(hr_user)

    import requests_app.views as v
    class _FormStub(forms.Form):
        status = forms.CharField(required=False)
        comment = forms.CharField(required=False)
        def __init__(self, data=None, files=None, instance=None, user=None):
            super().__init__(data=data, files=files)
            self.instance = instance
            self.user = user
            self.changed_data = [k for k in ("comment", "attachment") if data and k in data]
        def is_valid(self):
            self.cleaned_data = {
                "status": self.data.get("status"),
                "comment": self.data.get("comment"),
            }
            return True
    monkeypatch.setattr(v, "RequestStatusForm", _FormStub)

    url = reverse("requests_app:request_process", args=[request_obj.pk])
    payload = {"status": Request.STATUS_APPROVED, "comment": "ok-comment"}
    resp = client.post(url, payload, follow=True)
    assert resp.status_code in (200, 302, 303)

    request_obj.refresh_from_db()
    assert request_obj.status == Request.STATUS_APPROVED
    assert getattr(request_obj, "comment", None) == "ok-comment"


def test_request_process_invalid_status(client, hr_user, request_obj, login, monkeypatch):
    from requests_app.models import Request
    login(hr_user)

    import requests_app.views as v
    class _FormStub(forms.Form):
        status = forms.CharField(required=False)
        comment = forms.CharField(required=False)
        def __init__(self, data=None, files=None, instance=None, user=None):
            super().__init__(data=data, files=files)
            self.instance = instance
            self.user = user
            self.changed_data = []
        def is_valid(self):
            self.cleaned_data = {"status": self.data.get("status"), "comment": self.data.get("comment")}
            return True
    monkeypatch.setattr(v, "RequestStatusForm", _FormStub)

    url = reverse("requests_app:request_process", args=[request_obj.pk])
    old_status = request_obj.status
    for bad in (Request.STATUS_DRAFT, Request.STATUS_PENDING):
        resp = client.post(url, {"status": bad})
        assert resp.status_code == 200  # остаёмся на форме с ошибкой
        request_obj.refresh_from_db()
        assert request_obj.status == old_status  # статус не изменился
