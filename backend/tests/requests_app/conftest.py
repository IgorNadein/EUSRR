import pytest
from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.conf import settings

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def _clear_cache():
    cache.clear()
    yield
    cache.clear()

# На всякий: bakery сможет печь PhoneNumberField, если вдруг где-то всплывёт Employee
@pytest.fixture(autouse=True)
def _bakery_phone_generator():
    try:
        from model_bakery import generators
        from phonenumber_field.modelfields import PhoneNumberField
        import itertools
        counter = itertools.count(10000)
        generators.add(
            PhoneNumberField,
            lambda: f"+7999{next(counter):07d}"
        )
    except Exception:
        pass
    yield

def _mk_user(phone: str, **extra):
    User = get_user_model()
    defaults = dict(
        phone_number=phone,
        password=extra.pop("password", "pass"),
        email=extra.pop("email", f"{phone}@example.com"),
        first_name=extra.pop("first_name", "Test"),
        last_name=extra.pop("last_name", "User"),
        telegram=extra.pop("telegram", "@test"),
        is_active=True,  # <<< ВАЖНО: активируем пользователя для тестов
        **extra,
    )
    return User.objects.create_user(**defaults)


@pytest.fixture
def user():
    return _mk_user("+79990000001")

@pytest.fixture
def hr_user():
    return _mk_user("+79990000002", is_staff=True)

@pytest.fixture
def other_user():
    return _mk_user("+79990000003")

@pytest.fixture
def login(client):
    def _do(u):
        client.force_login(u, backend=settings.AUTHENTICATION_BACKENDS[0])
        return client
    return _do

@pytest.fixture
def request_obj(user):
    from model_bakery import baker
    from requests_app.models import Request
    return baker.make(
        Request,
        employee=user,
        status=Request.STATUS_PENDING,
        type=Request.TYPE_OTHER,
    )
