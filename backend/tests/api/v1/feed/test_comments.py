import io
import pytest
from django.urls import reverse
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework import status

from employees.models import Employee
from feed.models import Post, Comment
from feed.constants import TYPE_EMPLOYEE, TYPE_COMPANY


# ---------- helpers ----------

_seq = 1
def _uniq_email(prefix="u"):
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
    return u

def _img_file(name="c.png"):
    # минимальный валидный PNG-хедер достаточно для ImageField в тестах
    return SimpleUploadedFile(name, b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR", content_type="image/png")

def _bin_file(name="a.txt"):
    return SimpleUploadedFile(name, b"hello", content_type="text/plain")


def _items(resp):
    return resp.data["results"] if isinstance(resp.data, dict) and "results" in resp.data else resp.data


# ---------- tests ----------

@pytest.mark.django_db
def test_list_requires_auth_and_filters_ordering(api_client):
    url = reverse("api:v1:comments-list")
    assert api_client.get(url).status_code in (401, 403)

    author = _user()
    api_client.force_authenticate(user=author)
    p = Post.objects.create(author=author, type=TYPE_EMPLOYEE, title="t", body="b")

    c1 = Comment.objects.create(post=p, author=author, text="a")
    c2 = Comment.objects.create(post=p, author=author, text="b")

    # list
    resp = api_client.get(url)
    assert resp.status_code == 200
    ids = [row["id"] for row in _items(resp)]
    assert ids == [c1.id, c2.id]  # по created_at ASC

    # filter by post
    resp = api_client.get(url, {"post": p.id})
    assert resp.status_code == 200
    ids2 = [row["id"] for row in _items(resp)]
    assert ids2 == [c1.id, c2.id]

    # filter by author
    resp = api_client.get(url, {"author": author.id})
    assert resp.status_code == 200
    ids3 = [row["id"] for row in _items(resp)]
    assert ids3 == [c1.id, c2.id]


@pytest.mark.django_db
def test_create_text_only_and_files(api_client):
    user = _user()
    api_client.force_authenticate(user=user)
    p = Post.objects.create(author=user, type=TYPE_COMPANY, title="news", body="b")

    url = reverse("api:v1:comments-list")

    # text only
    resp = api_client.post(url, {"post": p.id, "text": "hi"}, format="multipart")
    assert resp.status_code == status.HTTP_201_CREATED
    assert resp.data["author_id"] == user.id
    assert resp.data["text"] == "hi"
    assert resp.data["image"] is None and resp.data["attachment"] is None

    # image only
    resp = api_client.post(url, {"post": p.id, "image": _img_file()}, format="multipart")
    assert resp.status_code == 201
    assert resp.data["text"] == ""

    # file only
    resp = api_client.post(url, {"post": p.id, "attachment": _bin_file()}, format="multipart")
    assert resp.status_code == 201
    assert resp.data["text"] == ""


@pytest.mark.django_db
def test_create_empty_payload_is_400(api_client):
    user = _user(); api_client.force_authenticate(user=user)
    p = Post.objects.create(author=user, type=TYPE_COMPANY, title="n", body="b")
    url = reverse("api:v1:comments-list")

    resp = api_client.post(url, {"post": p.id, "text": ""}, format="multipart")
    assert resp.status_code == 400
    assert "text" in resp.data  # сообщение об ошибке на поле text


@pytest.mark.django_db
def test_update_permissions_and_validation(api_client):
    author = _user()
    other = _user()
    staff = _user(staff=True)

    p = Post.objects.create(author=author, type=TYPE_COMPANY, title="n", body="b")
    c = Comment.objects.create(post=p, author=author, text="orig")

    url_detail = reverse("api:v1:comments-detail", args=[c.id])

    # не автор -> 403
    api_client.force_authenticate(user=other)
    assert api_client.patch(url_detail, {"text": "x"}, format="json").status_code == 403

    # автор -> 200
    api_client.force_authenticate(user=author)
    resp = api_client.patch(url_detail, {"text": "upd"}, format="json")
    assert resp.status_code == 200
    assert resp.data["text"] == "upd"

    # сделать пустым всё -> 400
    resp = api_client.patch(url_detail, {"text": ""}, format="json")
    assert resp.status_code == 400

    # staff может редактировать чужое
    api_client.force_authenticate(user=staff)
    resp = api_client.patch(url_detail, {"text": "staff-edit"}, format="json")
    assert resp.status_code == 200
    assert resp.data["text"] == "staff-edit"


@pytest.mark.django_db
def test_delete_permissions(api_client):
    author = _user(); staff = _user(staff=True); other = _user()
    p = Post.objects.create(author=author, type=TYPE_COMPANY, title="n", body="b")
    c = Comment.objects.create(post=p, author=author, text="delme")
    url_detail = reverse("api:v1:comments-detail", args=[c.id])

    # другой пользователь -> 403
    api_client.force_authenticate(user=other)
    assert api_client.delete(url_detail).status_code == 403

    # автор -> 204
    api_client.force_authenticate(user=author)
    assert api_client.delete(url_detail).status_code == 204

    # staff тоже может (создадим новый)
    c2 = Comment.objects.create(post=p, author=author, text="del2")
    api_client.force_authenticate(user=staff)
    assert api_client.delete(reverse("api:v1:comments-detail", args=[c2.id])).status_code == 204
