import pytest
from django.urls import reverse

pytestmark = pytest.mark.django_db


def test_safe_back_url_on_delete_external_next_blocked(client, user, request_obj, login):
    # Создадим собственный комментарий, чтобы было что удалять
    from requests_app.models import RequestComment
    comment = RequestComment.objects.create(request=request_obj, author=user, text="x")
    login(user)

    url = reverse("requests_app:request_comment_delete", args=[request_obj.pk, comment.pk])
    resp = client.post(url + "?next=https://attacker.tld/path")
    assert resp.status_code in (302, 303)
    # Нельзя увести наружу
    assert "attacker.tld" not in resp["Location"]
