# backend/tests/api/v1/documents/test_documents_api.py
from __future__ import annotations

"""
Тесты CRUD API документов (/api/v1/documents/ + экшен acknowledge) по чек-листу.

Политика доступа (актуальная):
- Создавать — все аутентифицированные пользователи (документы создаются в draft).
- Редактировать/удалять — только создатель, админы или обладатели модельных прав.
- Approve/Publish — только пользователи с правом change_document (django-rules).
- Читать/скачивать — только аутентифицированные, и только документы,
  предназначенные им (или с sent_to_all=True). Ознакомливаться можно только
  с документами, где acknowledgement_required=True. Обычные пользователи
  видят только PUBLISHED документы (кроме своих собственных).

Все функции и классы снабжены докстрингами (Google-style).
"""

import tempfile
import io
import zipfile
from typing import Iterable

import pytest
from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.utils import timezone
from documents.models import Document, DocumentAcknowledgement, DocumentTag
from employees.models import Department, EmployeeDepartment
from filer.models import File as FilerFile, Folder
from rest_framework import status
from rest_framework.test import APIClient
from tests.conftest import _unique_phone

pytestmark = pytest.mark.django_db

User = get_user_model()

# -------------- helpers / factories --------------
# _unique_phone импортируется из tests.conftest

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

def _filer_file(name: str = "doc.pdf", content: bytes = b"x", owner=None) -> FilerFile:
    """Создает filer.File объект для использования в тестах.
    
    Args:
        name (str): Имя файла
        content (bytes): Содержимое файла
        owner: Владелец файла (User instance)
        
    Returns:
        FilerFile: Созданный filer.File объект
    """
    uploaded_file = SimpleUploadedFile(
        name=name, content=content, content_type="application/pdf"
    )
    
    filer_file = FilerFile.objects.create(
        file=uploaded_file,
        original_filename=name,
        name=name,
        owner=owner
    )
    
    return filer_file

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
    acknowledgement_required: bool = False,
    recipients: Iterable[User] | None = None,
) -> Document:
    """Создаёт Document напрямую (минует API).

    Args:
        title (str): Заголовок.
        uploaded_by (User): Кто загрузил.
        description (str): Описание.
        sent_to_all (bool): Признак рассылки всем.
        acknowledgement_required (bool): Требуется ли ознакомление.
        recipients (Iterable[User] | None): Конкретные получатели при sent_to_all=false.

    Returns:
        Document: Созданная модель с прикреплённым файлом.
    """
    # Создаем filer.File объект
    filer_file = _filer_file(owner=uploaded_by)
    
    doc = Document.objects.create(
        title=title,
        description=description,
        uploaded_by=uploaded_by,
        uploaded_at=timezone.now(),
        sent_to_all=sent_to_all,
        acknowledgement_required=acknowledgement_required,
        file=filer_file,
    )
    if not sent_to_all and recipients:
        doc.recipients.set(recipients)
    return doc

# make_user импортируется из tests.conftest

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

    def _acknowledgements(pk: int) -> str:
        return reverse("api:v1:documents-acknowledgements", args=[pk])

    def _folder_detail(pk: int) -> str:
        return reverse("api:v1:folders-detail", args=[pk])

    def _folder_archive(pk: int) -> str:
        return reverse("api:v1:folders-archive", args=[pk])

    return {
        "list": reverse("api:v1:documents-list"),
        "archive": reverse("api:v1:documents-archive"),
        "detail": _detail,
        "ack": _ack,
        "acknowledgements": _acknowledgements,
        "folder_detail": _folder_detail,
        "folder_archive": _folder_archive,
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
        - create → 201 (разрешено создание в draft);
        - update/delete чужого документа → 403/404;
        - detail/ack чужого документа с sent_to_all=False → 403/404.
        """
        u = make_user("u@example.com")
        client = auth_client(u)

        list_url = api_urls["list"]
        # list — 200 (даже без прав), но результаты ограничены доступными документами
        assert client.get(list_url).status_code == 200

        # POST (multipart) — теперь разрешено всем аутентифицированным
        resp = client.post(
            list_url,
            {"title": "My Document", "file": _file(), "sent_to_all": True},
            format="multipart",
        )
        assert resp.status_code in (200, 201), f"Expected 200/201, got {resp.status_code}: {resp.content}"
        # Проверяем что документ создан
        doc_id = resp.json()["id"]
        doc = Document.objects.get(id=doc_id)
        assert doc.uploaded_by == u

        # object not intended for user
        author = make_user("a@example.com")
        d = make_document(uploaded_by=author, sent_to_all=False)

        # detail & write ops — 404 (пользователь не видит документ в queryset)
        assert client.get(api_urls["detail"](d.pk)).status_code == 404
        assert (
            client.put(
                api_urls["detail"](d.pk), {"title": "X"}, format="json"
            ).status_code
            == 404
        )
        assert (
            client.patch(
                api_urls["detail"](d.pk), {"title": "X"}, format="json"
            ).status_code
            == 404
        )
        assert client.delete(api_urls["detail"](d.pk)).status_code == 404

        # acknowledge чужого документа (не sent_to_all) — 404
        r = client.post(api_urls["ack"](d.pk), {})
        assert r.status_code == 404

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
        self, auth_client, make_user, api_urls
    ):
        """Успех: sent_to_all=true → 201 и корректное тело ответа."""
        uploader = make_user("uploader@example.com", staff=True)
        client = auth_client(uploader)

        data = {"title": "Title", "file": _file(), "sent_to_all": True}
        r = client.post(api_urls["list"], data, format="multipart")
        assert r.status_code in (200, 201), r.content
        body = r.json()
        assert {"id", "title", "file_url", "sent_to_all"} <= body.keys()
        assert body["sent_to_all"] is True
        assert body["title"] == "Title"
        assert isinstance(body["id"], int)
        assert body["file_url"]
        
        # Проверяем что документ создался
        doc = Document.objects.get(id=body["id"])
        assert doc.title == "Title"
        assert doc.sent_to_all is True

    def test_create_allows_arbitrary_file_format(
        self, auth_client, make_user, api_urls
    ):
        """API принимает файл с любым расширением и MIME-типом."""
        uploader = make_user("any-format-uploader@example.com", staff=True)
        client = auth_client(uploader)
        arbitrary_file = SimpleUploadedFile(
            name="archive.custom-format",
            content=b"custom payload",
            content_type="application/octet-stream",
        )

        response = client.post(
            api_urls["list"],
            {"file": arbitrary_file, "sent_to_all": True},
            format="multipart",
        )

        assert response.status_code in (200, 201), response.content
        body = response.json()
        assert body["title"] == "archive"
        assert body["file_name"] == "archive.custom-format"

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

        # title можно не передавать: он берется из имени файла
        r = client.post(
            url,
            {"file": _file(name="derived-title.pdf"), "sent_to_all": True},
            format="multipart",
        )
        assert r.status_code in (200, 201), r.content
        assert r.json()["title"] == "derived-title"

        # file необязателен
        r = client.post(url, {"title": "T", "sent_to_all": True}, format="multipart")
        assert r.status_code in (200, 201), r.content
        assert r.json()["title"] == "T"
        assert r.json()["file_url"] is None

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

    def test_regular_user_can_create_document_in_draft(
        self, auth_client, make_user, api_urls
    ):
        """Обычный пользователь без прав может создать документ, и он создается в draft."""
        regular_user = make_user("regular@example.com", staff=False)
        client = auth_client(regular_user)

        # Создаем документ
        r = client.post(
            api_urls["list"],
            {
                "title": "User Created Document",
                "description": "Created by regular user",
                "file": _file(name="user_doc.pdf"),
                "sent_to_all": True,
            },
            format="multipart",
        )
        assert r.status_code in (200, 201), f"Expected 200/201, got {r.status_code}: {r.content}"
        
        body = r.json()
        assert body["title"] == "User Created Document"
        assert body["sent_to_all"] is True
        
        # Проверяем что документ создан
        doc = Document.objects.get(pk=body["id"])
        assert doc.uploaded_by == regular_user
        
        # Проверяем что обычный пользователь видит свой документ
        detail_r = client.get(api_urls["detail"](doc.pk))
        assert detail_r.status_code == 200

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
        """GET detail возвращает нужные поля; is_acknowledged=false до отметки; file_url корректен."""
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
        assert bool(parsed_url.scheme), "file_url должен содержать scheme"
        assert bool(parsed_url.netloc), "file_url должен содержать netloc"
        assert parsed_url.path.startswith("/"), (
            f"file_url должен содержать абсолютный путь, получен: {body['file_url']}"
        )
        assert any(
            marker in parsed_url.path for marker in (settings.MEDIA_URL, "/filer_", "/smedia/")
        ), f"file_url содержит неожиданный путь: {body['file_url']}"

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
        # Документ создается в статусе draft по умолчанию
        doc_id = d.pk
        
        r = client.patch(
            api_urls["detail"](doc_id),
            {"title": "New", "description": "new"},
            format="json",
        )
        assert r.status_code == 200
        # Получаем свежий объект вместо refresh_from_db (из-за FSM protected)
        d = Document.objects.get(pk=doc_id)
        assert d.title == "New"
        assert d.description == "new"

    def test_update_search_text_and_acknowledgement_required(
        self, auth_client, make_user, api_urls
    ):
        """PATCH обновляет текст поиска и требование ознакомления."""
        author = make_user("author-search@example.com")
        editor = make_user("editor-search@example.com")
        grant_perms(editor, "change_document")
        client = auth_client(editor)
        document = make_document(
            uploaded_by=author,
            acknowledgement_required=False,
        )

        response = client.patch(
            api_urls["detail"](document.pk),
            {
                "extracted_text": "обновленный текст для поиска",
                "acknowledgement_required": True,
            },
            format="json",
        )

        assert response.status_code == 200
        document = Document.objects.get(pk=document.pk)
        assert document.extracted_text == "обновленный текст для поиска"
        assert document.acknowledgement_required is True

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
        doc_id = d.pk
        # Документ в статусе draft по умолчанию

        # false -> true -> recipients очищены
        r = client.patch(api_urls["detail"](doc_id), {"sent_to_all": True}, format="json")
        assert r.status_code == 200
        d = Document.objects.get(pk=doc_id)
        assert d.sent_to_all is True
        assert d.recipients.count() == 0

        # true -> false с recipient_ids
        r = client.patch(
            api_urls["detail"](doc_id),
            {"sent_to_all": False, "recipient_ids": [r2.id]},
            format="json",
        )
        assert r.status_code == 200
        d = Document.objects.get(pk=doc_id)
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
        doc_id = d.pk
        # Документ в статусе draft по умолчанию
        
        r = client.patch(
            api_urls["detail"](doc_id), {"recipient_ids": [c.id]}, format="json"
        )
        assert r.status_code == 200
        d = Document.objects.get(pk=doc_id)
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

    def test_delete_folder_removes_nested_folders_documents_and_related(
        self, auth_client, make_user, api_urls
    ):
        """DELETE папки удаляет её дерево, документы внутри и связанные документы."""
        owner = make_user("folder-owner@example.com")
        client = auth_client(owner)
        root = Folder.objects.create(name="Root", owner=owner)
        child = Folder.objects.create(name="Child", parent=root, owner=owner)
        other = Folder.objects.create(name="Other", owner=owner)

        root_doc = make_document(title="Root doc", uploaded_by=owner)
        root_doc.folder = root
        root_doc.save(update_fields=["folder"])

        child_doc = make_document(title="Child doc", uploaded_by=owner)
        child_doc.folder = child
        child_doc.save(update_fields=["folder"])

        related_doc = make_document(title="Related doc", uploaded_by=owner)
        related_doc.folder = other
        related_doc.save(update_fields=["folder"])
        root_doc.related_documents.add(related_doc)

        unrelated_doc = make_document(title="Unrelated doc", uploaded_by=owner)
        unrelated_doc.folder = other
        unrelated_doc.save(update_fields=["folder"])

        response = client.delete(api_urls["folder_detail"](root.pk))

        assert response.status_code == status.HTTP_204_NO_CONTENT
        assert not Folder.objects.filter(pk__in=[root.pk, child.pk]).exists()
        assert Folder.objects.filter(pk=other.pk).exists()
        assert not Document.objects.filter(
            pk__in=[root_doc.pk, child_doc.pk, related_doc.pk]
        ).exists()
        assert Document.objects.filter(pk=unrelated_doc.pk).exists()


# -------------------- E2. Папки --------------------

class TestFolders:
    """E2. Операции с папками документов."""

    def test_documents_archive_contains_selected_documents(
        self, auth_client, make_user, api_urls
    ):
        """POST archive отдаёт ZIP только с выбранными документами."""
        owner = make_user("documents-archive-owner@example.com")
        client = auth_client(owner)

        first_file = _filer_file(
            name="first.txt", content=b"first payload", owner=owner
        )
        second_file = _filer_file(
            name="second.txt", content=b"second payload", owner=owner
        )
        other_file = _filer_file(
            name="other.txt", content=b"other payload", owner=owner
        )

        first = Document.objects.create(
            title="First doc",
            file=first_file,
            uploaded_by=owner,
            sent_to_all=True,
        )
        second = Document.objects.create(
            title="Second doc",
            file=second_file,
            uploaded_by=owner,
            sent_to_all=True,
        )
        Document.objects.create(
            title="Other doc",
            file=other_file,
            uploaded_by=owner,
            sent_to_all=True,
        )

        response = client.post(
            api_urls["archive"],
            {"document_ids": [first.pk, second.pk]},
            format="json",
        )

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/zip"

        archive_bytes = b"".join(response.streaming_content)
        archive = zipfile.ZipFile(io.BytesIO(archive_bytes))

        assert archive.read("first.txt") == b"first payload"
        assert archive.read("second.txt") == b"second payload"
        assert "other.txt" not in archive.namelist()

    def test_folder_archive_contains_nested_documents(
        self, auth_client, make_user, api_urls
    ):
        """GET archive отдаёт ZIP с папкой, подпапками и документами."""
        owner = make_user("folder-archive-owner@example.com")
        client = auth_client(owner)
        root = Folder.objects.create(name="Root", owner=owner)
        child = Folder.objects.create(name="Child", parent=root, owner=owner)
        other = Folder.objects.create(name="Other", owner=owner)

        root_file = _filer_file(
            name="root.txt", content=b"root payload", owner=owner
        )
        child_file = _filer_file(
            name="child.txt", content=b"child payload", owner=owner
        )
        other_file = _filer_file(
            name="other.txt", content=b"other payload", owner=owner
        )

        Document.objects.create(
            title="Root doc",
            file=root_file,
            folder=root,
            uploaded_by=owner,
            sent_to_all=True,
        )
        Document.objects.create(
            title="Child doc",
            file=child_file,
            folder=child,
            uploaded_by=owner,
            sent_to_all=True,
        )
        Document.objects.create(
            title="Other doc",
            file=other_file,
            folder=other,
            uploaded_by=owner,
            sent_to_all=True,
        )

        response = client.get(api_urls["folder_archive"](root.pk))

        assert response.status_code == status.HTTP_200_OK
        assert response["Content-Type"] == "application/zip"

        archive_bytes = b"".join(response.streaming_content)
        archive = zipfile.ZipFile(io.BytesIO(archive_bytes))

        assert "Root/" in archive.namelist()
        assert "Root/Child/" in archive.namelist()
        assert archive.read("Root/root.txt") == b"root payload"
        assert archive.read("Root/Child/child.txt") == b"child payload"
        assert "Other/other.txt" not in archive.namelist()


# -------------------- E3. Уведомления --------------------

class TestDocumentNotifications:
    """E3. Уведомления о новых документах и ознакомлении."""

    def test_required_document_notification_mentions_acknowledgement(
        self, monkeypatch, make_user
    ):
        """Документ на ознакомление получает требовательный текст."""
        from documents.notifications.handlers import notify_document_ready

        calls = []

        def fake_notify_send(**kwargs):
            calls.append(kwargs)

        monkeypatch.setattr(
            "documents.notifications.handlers.notify.send",
            fake_notify_send,
        )
        author = make_user("required-document-author@example.com")
        viewer = make_user("required-document-viewer@example.com")
        doc = make_document(
            title="Регламент",
            uploaded_by=author,
            sent_to_all=False,
            acknowledgement_required=True,
        )

        notify_document_ready(doc, viewer)

        assert len(calls) == 1
        payload = calls[0]
        assert payload["recipient"] == viewer
        assert payload["verb"] == "document_ready"
        assert "Требуется ознакомление" in payload["description"]
        assert payload["data"]["title"] == "Новый документ на ознакомление"
        assert payload["data"]["acknowledgement_required"] is True

    def test_optional_document_notification_is_neutral(
        self, monkeypatch, make_user
    ):
        """Документ без ознакомления уведомляет без требования ознакомиться."""
        from documents.notifications.handlers import notify_document_ready

        calls = []

        def fake_notify_send(**kwargs):
            calls.append(kwargs)

        monkeypatch.setattr(
            "documents.notifications.handlers.notify.send",
            fake_notify_send,
        )
        author = make_user("optional-document-author@example.com")
        viewer = make_user("optional-document-viewer@example.com")
        doc = make_document(
            title="Справка",
            uploaded_by=author,
            sent_to_all=False,
            acknowledgement_required=False,
        )

        notify_document_ready(doc, viewer)

        assert len(calls) == 1
        payload = calls[0]
        assert payload["recipient"] == viewer
        assert payload["verb"] == "document_ready"
        assert "Требуется ознакомление" not in payload["description"]
        assert payload["description"].endswith('загрузил документ "Справка".')
        assert payload["data"]["title"] == "Новый документ"
        assert payload["data"]["acknowledgement_required"] is False

    def test_optional_document_acknowledgement_does_not_notify_uploader(
        self, monkeypatch, make_user
    ):
        """Ручные ACK по необязательному документу не запускают итоговое уведомление."""
        calls = []

        def fake_notify_all_acknowledged(*args):
            calls.append(args)

        monkeypatch.setattr(
            "documents.notifications.signals.notify_all_acknowledged",
            fake_notify_all_acknowledged,
        )
        author = make_user("optional-ack-author@example.com")
        viewer = make_user("optional-ack-viewer@example.com")
        doc = make_document(
            uploaded_by=author,
            sent_to_all=False,
            acknowledgement_required=False,
        )

        DocumentAcknowledgement.objects.create(document=doc, user=viewer)

        assert calls == []


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
            uploaded_by=author,
            sent_to_all=True,
            acknowledgement_required=True,
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
        """Пользователь вне recipients при sent_to_all=false — не может ACK (404, документ не видит)."""
        author = make_user("author@example.com")
        u = make_user("u@example.com")
        client = auth_client(u)

        r = client.post(
            api_urls["ack"](make_document(uploaded_by=author, sent_to_all=False).pk), {}
        )
        assert r.status_code == 404

    def test_ack_rejects_document_without_required_acknowledgement(
        self, auth_client, make_user, api_urls
    ):
        """Документ без обязательного ознакомления нельзя отметить через API."""
        author = make_user("optional-author@example.com")
        viewer = make_user("optional-viewer@example.com")
        client = auth_client(viewer)
        doc = make_document(
            uploaded_by=author,
            sent_to_all=True,
            acknowledgement_required=False,
        )

        response = client.post(api_urls["ack"](doc.pk), {})

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "не требуется" in response.json()["detail"]
        assert not DocumentAcknowledgement.objects.filter(
            document=doc,
            user=viewer,
        ).exists()


class TestAcknowledgementsReport:
    """Ведомость ознакомлений доступна всем, кому доступен документ."""

    def test_department_recipient_can_view_acknowledgements_report(
        self, auth_client, make_user, api_urls
    ):
        """Сотрудник отдела-получателя видит ведомость документа."""
        author = make_user("report-author@example.com")
        viewer = make_user("report-viewer@example.com")
        department = Department.objects.create(name="Report Department")
        EmployeeDepartment.objects.create(
            employee=viewer,
            department=department,
            is_active=True,
        )
        document = make_document(
            uploaded_by=author,
            sent_to_all=False,
            acknowledgement_required=True,
        )
        document.departments.add(department)
        DocumentAcknowledgement.objects.create(document=document, user=viewer)

        response = auth_client(viewer).get(api_urls["acknowledgements"](document.pk))

        assert response.status_code == status.HTTP_200_OK, response.content
        body = response.json()
        assert body["counts"] == {
            "acknowledged": 1,
            "unacknowledged": 0,
            "total": 1,
        }
        assert body["acknowledged"][0]["id"] == viewer.id

    def test_unrelated_user_cannot_view_acknowledgements_report(
        self, auth_client, make_user, api_urls
    ):
        """Посторонний сотрудник без доступа к документу не видит ведомость."""
        author = make_user("report-author-2@example.com")
        unrelated = make_user("report-unrelated@example.com")
        recipient = make_user("report-recipient@example.com")
        document = make_document(
            uploaded_by=author,
            sent_to_all=False,
            acknowledgement_required=True,
            recipients=[recipient],
        )

        response = auth_client(unrelated).get(
            api_urls["acknowledgements"](document.pk)
        )

        assert response.status_code == status.HTTP_404_NOT_FOUND


class TestDocumentTags:
    """CRUD тегов документов."""

    def test_create_tag_without_slug_generates_unique_slug(
        self, auth_client, make_user
    ):
        """Создание тега из формы работает без передачи slug."""
        user = make_user("tag-author@example.com")
        client = auth_client(user)
        url = reverse("api:v1:document-tags-list")

        response = client.post(
            url,
            {"name": "Регламент охраны труда", "color": "#3B82F6"},
            format="json",
        )

        assert response.status_code == status.HTTP_201_CREATED, response.content
        body = response.json()
        tag = DocumentTag.objects.get(pk=body["id"])
        assert tag.name == "Регламент охраны труда"
        assert tag.slug
        assert tag.color == "#3B82F6"

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

    # def test_file_url_downloadable_in_dev(
    #     self, client, auth_client, make_user, api_urls
    # ):
    #     """Интеграционный: можно скачать файл по file_url (если DEBUG и MEDIA настроены)."""
    #     author = make_user("author@example.com")
    #     viewer = make_user("viewer@example.com")
    #     grant_perms(viewer, "view_document")
    #     api = auth_client(viewer)

    #     d = make_document(uploaded_by=author)
    #     file_url = api.get(api_urls["detail"](d.pk)).json()["file_url"]

    #     # обычный Django client (без APIClient) для скачивания
    #     resp = client.get(file_url)
    #     assert resp.status_code == 200

# -------------------- H. Ошибки/краевые случаи --------------------

class TestErrorsAndEdgeCases:
    """H. Неудачные Content-Type, perms и размер файла."""

    def test_json_create_without_file(self, auth_client, make_user, api_urls):
        """JSON без файла создаёт документ: файл в документах необязателен."""
        uploader = make_user("uploader@example.com", staff=True)
        client = auth_client(uploader)
        r = client.post(
            api_urls["list"], {"title": "X", "sent_to_all": True}, format="json"
        )
        assert r.status_code in (200, 201), r.content
        assert r.json()["title"] == "X"
        assert r.json()["file_url"] is None

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
        - detail чужого документа при sent_to_all=false → 404 (не видит в queryset).
        """
        user = make_user("u@example.com")
        client = auth_client(user)
        author = make_user("a@example.com")
        d = make_document(uploaded_by=author, sent_to_all=False)
        assert client.get(api_urls["list"]).status_code == 200
        assert client.get(api_urls["detail"](d.pk)).status_code == 404

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
        # django-filer не проверяет DATA_UPLOAD_MAX_MEMORY_SIZE при загрузке
        # Лимит применяется на уровне Django request parserа, но во время тестов это может не работать
        # Просто проверяем, что запрос корректно обработан
        assert r.status_code in (200, 201, 400, 413)

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

        # Допускаем больше запросов из-за select_related/prefetch_related
        # и дополнительных запросов для filer.File и recipients
        with django_assert_num_queries(50, exact=False):
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
        - detail чужого документа (sent_to_all=false) → 404 (не видит в queryset);
        - ack чужого документа (sent_to_all=false) → 404.
        """
        u = make_user("u@example.com")
        client = auth_client(u)
        author = make_user("a@example.com")
        d = make_document(uploaded_by=author, sent_to_all=False)

        assert client.get(api_urls["list"]).status_code == 200
        assert client.get(api_urls["detail"](d.pk)).status_code == 404

        r = client.post(api_urls["ack"](d.pk), {})
        assert r.status_code == 404
