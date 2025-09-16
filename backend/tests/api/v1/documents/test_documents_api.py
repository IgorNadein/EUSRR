# backend/tests/api/v1/documents/test_documents_api.py
from __future__ import annotations

"""
Тесты CRUD API документов (/api/v1/documents/ + экшен acknowledge) по чек-листу.

Политика доступа (актуальная):
- Создавать/редактировать/удалять — только админы и обладатели модельных прав.
- Читать/скачивать/ознакомливаться — только аутентифицированные, и только документы,
  предназначенные им (или с sent_to_all=True). Получатели не имеют доступ к документам,
  которые им не предназначались.

Все функции и классы снабжены докстрингами (Google-style).
"""

import itertools
import tempfile
from typing import Iterable

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from documents.models import Document, DocumentAcknowledgement
from rest_framework import status
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

User = get_user_model()

# -------------- helpers / factories --------------

_phone_seq = itertools.count(1000)


def _unique_phone() -> str:
    """Генерирует уникальный валидный E.164 номер в рамках сессии тестов.

    Returns:
        str: Телефонный номер в формате +7999000xxx.
    """
    return f"+7999000{next(_phone_seq):03d}"


def _file(name: str = "doc.pdf", content: bytes = b"x") -> SimpleUploadedFile:
    """Создаёт минимальный загружаемый файл.

    Args:
        name (str): Имя файла.
        content (bytes): Содержимое.

    Returns:
        SimpleUploadedFile: Файл для multipart POST/PATCH.
    """
    return SimpleUploadedFile(
        name=name, content=content, content_type="application/pdf"
    )


def grant_perms(user: User, *codenames: str) -> None:
    """Выдаёт пользователю модельные права по кодовым именам из приложения documents.

    Args:
        user (User): Пользователь.
        *codenames (str): Набор кодов прав (например, "view_document").

    Raises:
        Permission.DoesNotExist: Если указанного права не существует.
    """
    for code in codenames:
        perm = Permission.objects.get(
            codename=code, content_type__app_label="documents"
        )
        user.user_permissions.add(perm)
    user.save(update_fields=[])


def make_document(
    *,
    title: str = "Doc",
    uploaded_by: User,
    description: str = "desc",
    sent_to_all: bool = True,
    recipients: Iterable[User] | None = None,
) -> Document:
    """Создаёт Document напрямую (минует API).

    Args:
        title (str): Заголовок.
        uploaded_by (User): Кто загрузил.
        description (str): Описание.
        sent_to_all (bool): Признак рассылки всем.
        recipients (Iterable[User] | None): Конкретные получатели при sent_to_all=false.

    Returns:
        Document: Созданная модель с прикреплённым файлом.
    """
    doc = Document.objects.create(
        title=title,
        description=description,
        uploaded_by=uploaded_by,
        uploaded_at=timezone.now(),
        sent_to_all=sent_to_all,
        file=_file(),
    )
    if not sent_to_all and recipients:
        doc.recipients.set(recipients)
    return doc


@pytest.fixture
def make_user(user_factory):
    """Фабрика пользователей для тестов API уровня документов.

    Args:
        user_factory (Callable): Фабрика из tests/conftest.py.

    Returns:
        Callable[..., User]: Функция создания Employee.
    """

    def _make(email: str, **extra) -> User:
        return user_factory(email=email, **extra)

    return _make


@pytest.fixture
def auth_client(auth_client_factory):
    """Фабрика DRF-клиентов, аутентифицированных под заданным пользователем.

    Args:
        auth_client_factory: Фабрика из tests/conftest.py.

    Returns:
        Callable[[User|None], APIClient]: Клиент с force_authenticate.
    """
    return auth_client_factory


@pytest.fixture
def api_urls():
    """Возвращает именованные URL API документов.

    Returns:
        dict: Словарь с ключами list, detail(id), ack(id).
    """

    def _detail(pk: int) -> str:
        return reverse("api:v1:documents-detail", args=[pk])

    def _ack(pk: int) -> str:
        return reverse("api:v1:documents-acknowledge", args=[pk])

    return {
        "list": reverse("api:v1:documents-list"),
        "detail": _detail,
        "ack": _ack,
    }


@pytest.fixture(autouse=True)
def enable_media_files(settings):
    settings.MEDIA_ROOT = tempfile.mkdtemp()
    settings.DEBUG = True


# -------------------- A. Роли и доступ --------------------


class TestAuthAndPermissions:
    """A. Роли и доступ — статусы для разных ролей и прав."""

    def test_anonymous_all_401(self, api_client: APIClient, api_urls):
        """Аноним: все запросы возвращают 401."""
        list_url = api_urls["list"]
        # list
        assert api_client.get(list_url).status_code == status.HTTP_401_UNAUTHORIZED
        # create
        r = api_client.post(list_url, {"title": "T"}, format="multipart")
        assert r.status_code == status.HTTP_401_UNAUTHORIZED

        # prepare object for other methods
        author = User.objects.create(
            email="auth@example.com", phone_number=_unique_phone()
        )
        d = make_document(uploaded_by=author)

        # detail
        assert (
            api_client.get(api_urls["detail"](d.pk)).status_code
            == status.HTTP_401_UNAUTHORIZED
        )
        # put/patch/delete
        assert (
            api_client.put(
                api_urls["detail"](d.pk), {"title": "X"}, format="json"
            ).status_code
            == 401
        )
        assert (
            api_client.patch(
                api_urls["detail"](d.pk), {"title": "X"}, format="json"
            ).status_code
            == 401
        )
        assert api_client.delete(api_urls["detail"](d.pk)).status_code == 401
        # acknowledge action
        assert api_client.post(api_urls["ack"](d.pk), {}).status_code == 401

    def test_regular_user_access_according_to_policy(
        self, auth_client, make_user, api_urls
    ):
        """Обычный user без модельных прав:
        - list → 200 (пустой список, если нет доступных документов);
        - CRUD → 403;
        - detail/ack чужого документа с sent_to_all=False → 403.
        """
        u = make_user("u@example.com")
        client = auth_client(u)

        list_url = api_urls["list"]
        # list — 200 (даже без прав), но результаты ограничены доступными документами
        assert client.get(list_url).status_code == 200

        # POST (multipart) — запрещено
        resp = client.post(
            list_url,
            {"title": "T", "file": _file(), "sent_to_all": True},
            format="multipart",
        )
        assert resp.status_code == 403

        # object not intended for user
        author = make_user("a@example.com")
        d = make_document(uploaded_by=author, sent_to_all=False)

        # detail & write ops — запрещено
        assert client.get(api_urls["detail"](d.pk)).status_code == 403
        assert (
            client.put(
                api_urls["detail"](d.pk), {"title": "X"}, format="json"
            ).status_code
            == 403
        )
        assert (
            client.patch(
                api_urls["detail"](d.pk), {"title": "X"}, format="json"
            ).status_code
            == 403
        )
        assert client.delete(api_urls["detail"](d.pk)).status_code == 403

        # acknowledge чужого документа (не sent_to_all) — запрещено
        r = client.post(api_urls["ack"](d.pk), {})
        assert r.status_code == 403

    @pytest.mark.parametrize(
        "perm,method,expected",
        [
            ("view_document", "get_list", 200),
            ("view_document", "get_detail", 200),
            ("add_document", "post", 201),
            ("change_document", "put", 200),
            ("change_document", "patch", 200),
            ("delete_document", "delete", 204),
        ],
    )
    def test_users_with_individual_perms(
        self, auth_client, make_user, api_urls, perm, method, expected
    ):
        """Пользователь с конкретным правом получает соответствующий доступ."""
        author = make_user("author@example.com")
        target = make_user("p@example.com")
        grant_perms(target, perm)

        client = auth_client(target)
        list_url = api_urls["list"]

        # set up object
        d = make_document(uploaded_by=author)

        if method == "get_list":
            r = client.get(list_url)
            assert r.status_code == expected
        elif method == "get_detail":
            r = client.get(api_urls["detail"](d.pk))
            assert r.status_code == expected
        elif method == "post":
            data = {"title": "T", "file": _file(), "sent_to_all": True}
            r = client.post(list_url, data, format="multipart")
            assert r.status_code == expected, r.content
        elif method == "put":
            r = client.put(
                api_urls["detail"](d.pk),
                {"title": "X", "description": "D", "sent_to_all": True},
                format="json",
            )
            assert r.status_code == expected
        elif method == "patch":
            r = client.patch(api_urls["detail"](d.pk), {"title": "X"}, format="json")
            assert r.status_code == expected
        elif method == "delete":
            r = client.delete(api_urls["detail"](d.pk))
            assert r.status_code == expected
        else:
            raise AssertionError("unknown method")

    @pytest.mark.parametrize(
        "is_staff,is_superuser", [(True, False), (True, True), (False, True)]
    )
    def test_staff_and_superuser_full_access(
        self, auth_client, make_user, api_urls, is_staff, is_superuser
    ):
        """staff/superuser: полный доступ (все запросы 2xx)."""
        author = make_user("author@example.com")
        admin = make_user("admin@example.com", staff=is_staff, superuser=is_superuser)
        client = auth_client(admin)

        # create
        r = client.post(
            api_urls["list"],
            {"title": "T", "file": _file(), "sent_to_all": True},
            format="multipart",
        )
        assert r.status_code in (200, 201)
        doc_id = r.json().get("id")

        # list/detail
        assert client.get(api_urls["list"]).status_code == 200
        assert client.get(api_urls["detail"](doc_id)).status_code == 200

        # update
        assert (
            client.patch(
                api_urls["detail"](doc_id), {"title": "TT"}, format="json"
            ).status_code
            == 200
        )
        # delete
        assert client.delete(api_urls["detail"](doc_id)).status_code in (200, 204)


# -------------------- B. Создание (POST) --------------------


@pytest.mark.django_db
class TestCreate:
    """B. Создание документа multipart/form-data."""

    def test_create_sent_to_all_true(
        self, auth_client, make_user, api_urls, monkeypatch
    ):
        """Успех: sent_to_all=true → 201 и корректное тело ответа + вызов notify() один раз."""
        uploader = make_user("uploader@example.com", staff=True)
        client = auth_client(uploader)

        called = {"n": 0, "doc": None}

        def fake_notify(doc):
            called["n"] += 1
            called["doc"] = doc

        # замокаем side-effect
        monkeypatch.setattr(
            "documents.notification.notify_users_about_document",
            fake_notify,
            raising=False,
        )

        data = {"title": "Title", "file": _file(), "sent_to_all": True}
        r = client.post(api_urls["list"], data, format="multipart")
        assert r.status_code in (200, 201), r.content
        body = r.json()
        assert {"id", "title", "file_url", "sent_to_all"} <= body.keys()
        assert body["sent_to_all"] is True
        assert body["title"] == "Title"
        assert isinstance(body["id"], int)
        assert body["file_url"]

        # notify был вызван один раз уже c назначенными получателями
        assert called["n"] == 1
        assert isinstance(called["doc"], Document)

    def test_create_sent_to_all_false_with_recipients_variants(
        self, auth_client, make_user, api_urls
    ):
        """sent_to_all=false + recipient_ids (repeat / JSON / CSV) → 201; recipient_count = числу активных."""
        uploader = make_user("uploader@example.com", staff=True)
        client = auth_client(uploader)

        # активные
        r1 = make_user("r1@example.com", active=True)
        r2 = make_user("r2@example.com", active=True)
        # неактивный
        r3 = make_user("r3@example.com", active=False)

        list_url = api_urls["list"]

        # 1) repeat-params
        data1 = {
            "title": "T1",
            "file": _file(),
            "sent_to_all": False,
            "recipient_ids": [r1.id, r2.id, r3.id],
        }
        resp1 = client.post(list_url, data1, format="multipart")
        assert resp1.status_code in (200, 201), resp1.content
        body1 = resp1.json()
        assert body1.get("recipient_count") == 2  # только активные
        # 2) JSON-массив
        data2 = {
            "title": "T2",
            "file": _file(name="f2.pdf"),
            "sent_to_all": False,
            "recipient_ids": f"[{r1.id},{r3.id}]",
        }
        resp2 = client.post(list_url, data2, format="multipart")
        assert resp2.status_code in (200, 201), resp2.content
        assert resp2.json().get("recipient_count") == 1
        # 3) CSV-строка
        data3 = {
            "title": "T3",
            "file": _file(name="f3.pdf"),
            "sent_to_all": False,
            "recipient_ids": f"{r1.id},{r2.id},{999999}",
        }
        resp3 = client.post(list_url, data3, format="multipart")
        assert resp3.status_code in (200, 201), resp3.content
        assert resp3.json().get("recipient_count") == 2

    def test_create_validations(self, auth_client, make_user, api_urls):
        """Валидации обязательных полей и recipient_ids."""
        uploader = make_user("uploader@example.com", staff=True)
        client = auth_client(uploader)
        url = api_urls["list"]

        # нет title
        r = client.post(url, {"file": _file(), "sent_to_all": True}, format="multipart")
        assert r.status_code == 400

        # нет file
        r = client.post(url, {"title": "T", "sent_to_all": True}, format="multipart")
        assert r.status_code == 400

        # sent_to_all=false и пустые recipient_ids → 400
        r = client.post(url, {"title": "T", "sent_to_all": False}, format="multipart")
        assert r.status_code == 400

    def test_create_skips_nonexistent_or_inactive_recipients(
        self, auth_client, make_user, api_urls
    ):
        """recipient_ids с несуществующими/неактивными → создаётся без них; в recipients их нет."""
        uploader = make_user("uploader@example.com", staff=True)
        client = auth_client(uploader)

        active = make_user("a@example.com", active=True)
        inactive = make_user("i@example.com", active=False)

        r = client.post(
            api_urls["list"],
            {
                "title": "T",
                "file": _file(),
                "sent_to_all": False,
                "recipient_ids": [active.id, inactive.id, 999999],
            },
            format="multipart",
        )
        assert r.status_code in (200, 201)
        doc_id = r.json()["id"]
        doc = Document.objects.get(pk=doc_id)
        ids = set(doc.recipients.values_list("id", flat=True))
        assert active.id in ids
        assert inactive.id not in ids


# -------------------- C. Чтение (GET) --------------------


class TestRead:
    """C. Чтение: list/detail, структура, пагинация, file_url."""

    def test_get_list_with_view_perm_and_pagination(
        self, auth_client, make_user, api_urls
    ):
        """GET list с правом view_document → 200 + DRF пагинация и page_size=20."""
        author = make_user("author@example.com")
        viewer = make_user("viewer@example.com")
        grant_perms(viewer, "view_document")
        client = auth_client(viewer)

        for i in range(25):
            make_document(uploaded_by=author, title=f"D{i:02d}")

        r1 = client.get(api_urls["list"])
        assert r1.status_code == 200
        data = r1.json()
        assert {"count", "next", "previous", "results"} <= data.keys()
        assert len(data["results"]) == 20

        # вторая страница
        r2 = client.get(api_urls["list"], {"page": 2})
        assert r2.status_code == 200
        assert len(r2.json()["results"]) == 5

        # проверим базовые поля
        sample = data["results"][0]
        expected = {
            "id",
            "title",
            "description",
            "uploaded_by",
            "uploaded_at",
            "sent_to_all",
            "recipients",
            "file_url",
            "is_acknowledged",
        }
        assert expected <= set(sample.keys())

    def test_get_detail_fields_and_file_url(
        self, auth_client, make_user, api_urls, settings
    ):
        """GET detail возвращает нужные поля; is_acknowledged=false до отметки; file_url внутри MEDIA_URL."""
        author = make_user("author@example.com")
        viewer = make_user("viewer@example.com")
        grant_perms(viewer, "view_document")
        client = auth_client(viewer)

        doc = make_document(uploaded_by=author, title="T")
        r = client.get(api_urls["detail"](doc.pk))
        assert r.status_code == 200
        body = r.json()
        assert body["is_acknowledged"] is False
        assert body["file_url"]

        from urllib.parse import urlparse

        parsed_url = urlparse(body["file_url"])
        assert bool(parsed_url.scheme)
        assert bool(parsed_url.netloc)
        assert parsed_url.path.startswith(settings.MEDIA_URL)
        expected_path = f"{settings.MEDIA_URL}{doc.file.name}"
        expected_url = f"http://testserver{expected_path}"
        assert (
            body["file_url"] == expected_url
        ), f"Ожидался URL: {expected_url}, получен: {body['file_url']}"


# -------------------- D. Обновление (PUT/PATCH) --------------------


class TestUpdate:
    """D. Обновление документа (PUT/PATCH)."""

    def test_update_title_description(self, auth_client, make_user, api_urls):
        """PUT/PATCH обновляют title/description."""
        author = make_user("author@example.com")
        editor = make_user("editor@example.com")
        grant_perms(editor, "change_document")
        client = auth_client(editor)

        d = make_document(uploaded_by=author, title="Old", description="old")
        r = client.patch(
            api_urls["detail"](d.pk),
            {"title": "New", "description": "new"},
            format="json",
        )
        assert r.status_code == 200
        d.refresh_from_db()
        assert d.title == "New"
        assert d.description == "new"

    def test_replace_file_multipart_patch(self, auth_client, make_user, api_urls):
        """Заменить file (multipart PATCH) → file_url изменился."""
        author = make_user("author@example.com")
        editor = make_user("editor@example.com")
        grant_perms(editor, "change_document")
        client = auth_client(editor)
        d = make_document(uploaded_by=author)  # sent_to_all=True по умолчанию

        # получим старый url через detail (этап API)
        r1 = client.get(api_urls["detail"](d.pk))
        old_url = r1.json()["file_url"]

        r2 = client.patch(
            api_urls["detail"](d.pk),
            {"file": _file(name="new.pdf")},
            format="multipart",
        )
        assert r2.status_code == 200
        new_url = r2.json()["file_url"]
        assert new_url != old_url

    def test_toggle_sent_to_all_affects_recipients(
        self, auth_client, make_user, api_urls
    ):
        """Переключение sent_to_all ↔ влияет на recipients."""
        author = make_user("author@example.com")
        editor = make_user("editor@example.com")
        r1 = make_user("r1@example.com")
        r2 = make_user("r2@example.com")
        grant_perms(editor, "change_document")
        client = auth_client(editor)

        d = make_document(uploaded_by=author, sent_to_all=False, recipients=[r1, r2])

        # false -> true -> recipients очищены
        r = client.patch(api_urls["detail"](d.pk), {"sent_to_all": True}, format="json")
        assert r.status_code == 200
        d.refresh_from_db()
        assert d.sent_to_all is True
        assert d.recipients.count() == 0

        # true -> false с recipient_ids
        r = client.patch(
            api_urls["detail"](d.pk),
            {"sent_to_all": False, "recipient_ids": [r2.id]},
            format="json",
        )
        assert r.status_code == 200
        d.refresh_from_db()
        assert d.sent_to_all is False
        assert list(d.recipients.values_list("id", flat=True)) == [r2.id]

    def test_patch_only_recipient_ids_replaces_list(
        self, auth_client, make_user, api_urls
    ):
        """Частичный PATCH только recipient_ids (при sent_to_all=false) → замена списка."""
        author = make_user("author@example.com")
        editor = make_user("editor@example.com")
        a = make_user("a@example.com")
        b = make_user("b@example.com")
        c = make_user("c@example.com")
        grant_perms(editor, "change_document")
        client = auth_client(editor)

        d = make_document(uploaded_by=author, sent_to_all=False, recipients=[a, b])
        r = client.patch(
            api_urls["detail"](d.pk), {"recipient_ids": [c.id]}, format="json"
        )
        assert r.status_code == 200
        d.refresh_from_db()
        assert list(d.recipients.values_list("id", flat=True)) == [c.id]


# -------------------- E. Удаление (DELETE) --------------------


class TestDelete:
    """E. Удаление документа."""

    def test_delete_and_cascade_acknowledgements(
        self, auth_client, make_user, api_urls
    ):
        """DELETE → 204; последующий GET → 404; каскад: DocumentAcknowledgement удалены."""
        author = make_user("author@example.com")
        deleter = make_user("deleter@example.com")
        grant_perms(deleter, "delete_document")
        client = auth_client(deleter)

        d = make_document(uploaded_by=author)
        # создадим ack
        ack_user = make_user("ack@example.com")
        DocumentAcknowledgement.objects.create(document=d, user=ack_user)

        r = client.delete(api_urls["detail"](d.pk))
        assert r.status_code in (200, 204)

        # detail теперь 404 (в некоторых реализациях 403 — зависит от политики; оставляем как есть)
        r2 = client.get(api_urls["detail"](d.pk))
        assert r2.status_code == 404

        # каскад: записей нет
        assert not DocumentAcknowledgement.objects.filter(document=d).exists()


# -------------------- F. Экшен acknowledge --------------------


class TestAcknowledge:
    """F. Экшен POST /{id}/acknowledge/ — идемпотентность и политика доступа."""

    def test_ack_first_and_repeat(self, auth_client, make_user, api_urls):
        """Первый вызов создаёт запись, повторный — already=true (200 оба раза).
        Допустимо для документов с sent_to_all=True (общерассылка).
        """
        author = make_user("author@example.com")
        any_user = make_user("u@example.com")
        client = auth_client(any_user)

        d = make_document(
            uploaded_by=author, sent_to_all=True
        )  # доступен всем аутентифицированным

        r1 = client.post(api_urls["ack"](d.pk), {})
        assert r1.status_code == 200
        assert r1.json() == {"ok": True, "already": False}
        assert (
            DocumentAcknowledgement.objects.filter(document=d, user=any_user).count()
            == 1
        )

        # повторный
        r2 = client.post(api_urls["ack"](d.pk), {})
        assert r2.status_code == 200
        assert r2.json() == {"ok": True, "already": True}
        assert (
            DocumentAcknowledgement.objects.filter(document=d, user=any_user).count()
            == 1
        )

    def test_detail_reflects_is_acknowledged(self, auth_client, make_user, api_urls):
        """GET detail после отметки → is_acknowledged=true."""
        author = make_user("author@example.com")
        viewer = make_user("viewer@example.com")
        grant_perms(viewer, "view_document")
        client = auth_client(viewer)

        d = make_document(uploaded_by=author)
        # пока false
        assert client.get(api_urls["detail"](d.pk)).json()["is_acknowledged"] is False
        # отметим
        other = make_user("x@example.com")  # не влияет на viewer
        DocumentAcknowledgement.objects.create(document=d, user=viewer)
        assert client.get(api_urls["detail"](d.pk)).json()["is_acknowledged"] is True

    def test_ack_forbidden_if_not_recipient_and_not_sent_to_all(
        self, auth_client, make_user, api_urls
    ):
        """Пользователь вне recipients при sent_to_all=false — не может ACK (403)."""
        author = make_user("author@example.com")
        u = make_user("u@example.com")
        client = auth_client(u)

        r = client.post(
            api_urls["ack"](make_document(uploaded_by=author, sent_to_all=False).pk), {}
        )
        assert r.status_code == 403


# -------------------- G. Сериализация и данные --------------------


class TestSerialization:
    """G. Сериализация: uploaded_by/recipients поля и скачивание файла."""

    def test_uploaded_by_and_recipients_shape(self, auth_client, make_user, api_urls):
        """uploaded_by и recipients[] содержат id, full_name, email; full_name корректен."""
        author = make_user("author@example.com", first_name="Иван", last_name="Иванов")
        viewer = make_user("viewer@example.com")
        grant_perms(viewer, "view_document")
        client = auth_client(viewer)

        r1 = make_user("r1@example.com", first_name="Петр", last_name="Петров")
        r2 = make_user("r2@example.com", first_name="Сидор", last_name="Сидоров")
        d = make_document(uploaded_by=author, sent_to_all=False, recipients=[r1, r2])

        body = client.get(api_urls["detail"](d.pk)).json()
        ub = body["uploaded_by"]
        assert {"id", "full_name", "email"} <= ub.keys()
        assert "Иван" in ub["full_name"]

        rec = body["recipients"]
        assert isinstance(rec, list) and rec
        assert {"id", "full_name", "email"} <= rec[0].keys()
        full_names = [x["full_name"] for x in rec]
        assert any("Петр" in fn for fn in full_names)

    def test_file_url_downloadable_in_dev(
        self, client, auth_client, make_user, api_urls
    ):
        """Интеграционный: можно скачать файл по file_url (если DEBUG и MEDIA настроены)."""
        author = make_user("author@example.com")
        viewer = make_user("viewer@example.com")
        grant_perms(viewer, "view_document")
        api = auth_client(viewer)

        d = make_document(uploaded_by=author)
        file_url = api.get(api_urls["detail"](d.pk)).json()["file_url"]

        # обычный Django client (без APIClient) для скачивания
        resp = client.get(file_url)
        assert resp.status_code == 200


# -------------------- H. Ошибки/краевые случаи --------------------


class TestErrorsAndEdgeCases:
    """H. Неудачные Content-Type, perms и размер файла."""

    def test_wrong_content_type_on_create(self, auth_client, make_user, api_urls):
        """Неверный Content-Type (JSON без файла) → 400 или 415 (фиксируем фактическое поведение)."""
        uploader = make_user("uploader@example.com", staff=True)
        client = auth_client(uploader)
        r = client.post(
            api_urls["list"], {"title": "X", "sent_to_all": True}, format="json"
        )
        assert r.status_code in (400, 415)

    def test_put_patch_delete_without_perms(self, auth_client, make_user, api_urls):
        """Попытка PUT/PATCH/DELETE без прав → 403."""
        user = make_user("u@example.com")
        client = auth_client(user)
        author = make_user("a@example.com")
        d = make_document(uploaded_by=author)
        assert (
            client.put(
                api_urls["detail"](d.pk), {"title": "X"}, format="json"
            ).status_code
            == 403
        )
        assert (
            client.patch(
                api_urls["detail"](d.pk), {"title": "X"}, format="json"
            ).status_code
            == 403
        )
        assert client.delete(api_urls["detail"](d.pk)).status_code == 403

    def test_get_without_view_perm(self, auth_client, make_user, api_urls):
        """GET list/detail без view_document:
        - list → 200 (выдаёт только доступные документы, обычно пусто);
        - detail чужого документа при sent_to_all=false → 403.
        """
        user = make_user("u@example.com")
        client = auth_client(user)
        author = make_user("a@example.com")
        d = make_document(uploaded_by=author, sent_to_all=False)
        assert client.get(api_urls["list"]).status_code == 200
        assert client.get(api_urls["detail"](d.pk)).status_code == 403

    def test_big_file_over_limit_if_configured(
        self, auth_client, make_user, api_urls, settings
    ):
        """Большой файл > лимита → ожидаем 413 или 400 (если лимит включён); иначе 201."""
        uploader = make_user("uploader@example.com", staff=True)
        client = auth_client(uploader)

        big = SimpleUploadedFile("big.bin", b"x" * (5 * 1024 * 1024))  # 5 MB
        r = client.post(
            api_urls["list"],
            {"title": "Big", "file": big, "sent_to_all": True},
            format="multipart",
        )
        if getattr(settings, "DATA_UPLOAD_MAX_MEMORY_SIZE", None):
            assert r.status_code in (400, 413)
        else:
            # фиксируем текущий результат при отсутствии лимита
            assert r.status_code in (200, 201)


# -------------------- I. Производительность/фильтры --------------------


class TestPerformance:
    """I. N+1 и пагинация."""

    def test_no_n_plus_one_in_list(
        self, django_assert_num_queries, auth_client, make_user, api_urls
    ):
        """Листинг с prefetch/select_related: количество SQL не растёт линейно."""
        author = make_user("author@example.com")
        viewer = make_user("viewer@example.com")
        grant_perms(viewer, "view_document")
        client = auth_client(viewer)

        # создадим 1 и 10 документов
        make_document(uploaded_by=author, title="one")
        for i in range(10):
            make_document(uploaded_by=author, title=f"doc{i:02d}")

        # допуская кэш/хитрости, выставим безопасный порог
        with django_assert_num_queries(10, exact=False):
            r = client.get(api_urls["list"])
            assert r.status_code == 200

    def test_pagination_navigation(self, auth_client, make_user, api_urls):
        """Навигация по страницам с глобальной DRF-пагинацией."""
        author = make_user("author@example.com")
        viewer = make_user("viewer@example.com")
        grant_perms(viewer, "view_document")
        client = auth_client(viewer)

        for i in range(45):
            make_document(uploaded_by=author, title=f"D{i}")

        # page=1
        r1 = client.get(api_urls["list"], {"page": 1})
        assert r1.status_code == 200
        # page=3 (последняя)
        r3 = client.get(api_urls["list"], {"page": 3})
        assert r3.status_code == 200


# -------------------- J. Совместимость и безопасность --------------------


class TestSecurityAndPolicy:
    """J. Базовая совместимость по авторизации и политика acknowledge."""

    def test_jwt_or_session_happy_path(self, api_client: APIClient):
        """Проверка базовой настройки DRF: IsAuthenticated + DjangoModelPermissions включены глобально.

        Тест не бьёт конкретный endpoint, а страхует глобальную конфигурацию.
        """
        from django.conf import settings as dj_settings

        assert "rest_framework.permissions.IsAuthenticated" in str(
            dj_settings.REST_FRAMEWORK.get("DEFAULT_PERMISSION_CLASSES", [])
        )
        assert "rest_framework.permissions.DjangoModelPermissions" in str(
            dj_settings.REST_FRAMEWORK.get("DEFAULT_PERMISSION_CLASSES", [])
        )

    def test_policy_without_perms_list_is_200_detail_and_ack_require_access(
        self, auth_client, make_user, api_urls
    ):
        """Пользователь без perms:
        - list → 200 (покажет только доступные доки);
        - detail чужого документа (sent_to_all=false) → 403;
        - ack чужого документа (sent_to_all=false) → 403.
        """
        u = make_user("u@example.com")
        client = auth_client(u)
        author = make_user("a@example.com")
        d = make_document(uploaded_by=author, sent_to_all=False)

        assert client.get(api_urls["list"]).status_code == 200
        assert client.get(api_urls["detail"](d.pk)).status_code == 403

        r = client.post(api_urls["ack"](d.pk), {})
        assert r.status_code == 403
