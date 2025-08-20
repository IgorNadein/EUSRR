import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_request_comment_add_ok(client, user, request_obj, login):
    login(user)
    url = reverse("requests_app:request_comment_add", args=[request_obj.pk])
    resp = client.post(url, {"text": "Привет!"})
    assert resp.status_code in (302, 303)
    from requests_app.models import RequestComment
    assert RequestComment.objects.filter(request=request_obj, author=user, text="Привет!").exists()


def test_request_comment_add_empty(client, user, request_obj, login):
    login(user)
    url = reverse("requests_app:request_comment_add", args=[request_obj.pk])
    resp = client.post(url, {"text": "   "})
    assert resp.status_code in (302, 303)


def test_request_comment_add_next_is_sanitized(client, user, request_obj, login):
    login(user)
    url = reverse("requests_app:request_comment_add", args=[request_obj.pk])
    resp = client.post(url + "?next=https://evil.tld", {"text": "ok"})
    assert resp.status_code in (302, 303)
    assert "evil.tld" not in resp["Location"]


def test_request_comment_delete_self(client, user, request_obj, login):
    from requests_app.models import RequestComment
    comment = RequestComment.objects.create(request=request_obj, author=user, text="del me")
    login(user)
    url = reverse("requests_app:request_comment_delete", args=[request_obj.pk, comment.pk])
    resp = client.post(url)
    assert resp.status_code in (302, 303)
    assert not RequestComment.objects.filter(pk=comment.pk).exists()


def test_request_comment_delete_forbidden(client, user, other_user, request_obj, login):
    """
    По текущей реализации «чужой» комментарий не виден → 404.
    (Если захочешь именно 403 — поменяем вьюху, чтобы выборка находила комментарий,
    а запрет отдавался PermissionDenied.)
    """
    from requests_app.models import RequestComment
    comment = RequestComment.objects.create(request=request_obj, author=other_user, text="nope")
    login(user)
    url = reverse("requests_app:request_comment_delete", args=[request_obj.pk, comment.pk])
    resp = client.post(url)
    assert resp.status_code == 404
