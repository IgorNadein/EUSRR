# tests/conftest.py
import itertools
import mimetypes
import os
from datetime import datetime, date
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.core.files.base import ContentFile
from employees.models import Department, DepartmentRole, EmployeeDepartment
from rest_framework.test import APIClient

pytestmark = pytest.mark.django_db

User = get_user_model()

# -------------------------
#      Speed & isolation
# -------------------------


@pytest.fixture(autouse=True)
def _fast_hashers_and_email(settings, tmp_path):
    # быстрые хеши паролей и локальная почта
    settings.PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    # изоляция медиа
    media_root = tmp_path / "test_media"
    media_root.mkdir(exist_ok=True)
    settings.MEDIA_ROOT = media_root
    yield


# -------------------------
#       API clients
# -------------------------


@pytest.fixture
def api_client() -> APIClient:
    """DRF APIClient (имеет force_authenticate)."""
    return APIClient()


@pytest.fixture
def auth_client_factory():
    """Фабрика аутентифицированных клиентов: client = auth_client_factory(user)."""

    def _make(user=None):
        client = APIClient()
        if user:
            client.force_authenticate(user=user)
        return client

    return _make


# -------------------------
#         Factories
# -------------------------

_phone_seq = itertools.count(1000)


def _unique_phone() -> str:
    # валидный E.164 и уникальный в рамках сессии
    return f"+7999000{next(_phone_seq):03d}"


@pytest.fixture
def user_factory():
    """
    user = user_factory(email="x@example.com", staff=False, superuser=False,
                        verified=True, active=True, **extra)
    Создаёт пользователя напрямую (без менеджера create_user, чтобы не слать письма).
    """

    def _make(
        email: str,
        *,
        staff: bool = False,
        superuser: bool = False,
        verified: bool = True,
        active: bool = True,
        password: str = "pass",
        **extra,
    ):
        u = User.objects.create(
            email=email,
            phone_number=extra.pop("phone_number", _unique_phone()),
            first_name=extra.pop("first_name", "FN"),
            last_name=extra.pop("last_name", "LN"),
            is_staff=staff,
            is_superuser=superuser,
            is_active=active,
            email_verified=verified,
            **extra,
        )
        u.set_password(password)
        u.save()
        return u

    return _make


@pytest.fixture
def department_factory():
    def _make(**kwargs) -> Department:
        return Department.objects.create(**kwargs)

    return _make


@pytest.fixture
def perm_for_department():
    """
    p = perm_for_department("manage_department")
    Гарантированно возвращает Permission для модели Department с нужным codename.
    """

    def _make(codename: str) -> Permission:
        ct = ContentType.objects.get_for_model(Department)
        p, _ = Permission.objects.get_or_create(
            content_type=ct,
            codename=codename,
            defaults={"name": codename},
        )
        return p

    return _make


@pytest.fixture
def role_factory(perm_for_department):
    """
    role = role_factory(dept, name="mgr", codes=["manage_department", ...])
    """

    def _make(dept: Department, name: str = "role", codes=None) -> DepartmentRole:
        r = DepartmentRole.objects.create(department=dept, name=name)
        if codes:
            perms = [perm_for_department(code) for code in codes]
            r.permissions.add(*perms)
        return r

    return _make


@pytest.fixture
def link_factory():
    """
    link = link_factory(employee, department, is_active=True, role=None, **dates)
    """

    def _make(
        employee, department, is_active=True, role=None, **dates
    ) -> EmployeeDepartment:
        return EmployeeDepartment.objects.create(
            employee=employee,
            department=department,
            is_active=is_active,
            role=role,
            **dates,
        )

    return _make


# -------------------------
#       Test helpers
# -------------------------


@pytest.fixture
def extract_results():
    """
    items = extract_results(resp.json()) — поддерживает DRF пагинацию и «плоский» список.
    """

    def _do(payload):
        if isinstance(payload, dict) and "results" in payload:
            return payload["results"]
        return payload

    return _do


# -------------------------
#   Small misc utilities
# -------------------------


@pytest.fixture
def data_uri_image(tmp_path):
    """
    Возвращает data URI маленькой PNG-картинки (1x1), удобно для аватаров.
    """
    # минимальный валидный PNG 1x1 (чёрный пиксель)
    import base64

    png_b64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR4nGMA"
        "AQAABQABDQottAAAAABJRU5ErkJggg=="
    )
    return f"data:image/png;base64,{png_b64}"


@pytest.fixture
def content_file_from_b64():
    """
    ContentFile <- base64 строки (без data: префикса).
    """
    import base64

    def _make(b64: str, name: str = "upload.bin") -> ContentFile:
        return ContentFile(base64.b64decode(b64), name=name)

    return _make
