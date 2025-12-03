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


# ============================================================================
# Fixtures для тестирования новых фич (recipients/cc/departments)
# ============================================================================

@pytest.fixture
def test_employee(user_factory):
    """Первый тестовый сотрудник"""
    return user_factory(email='emp1@test.com')


@pytest.fixture
def test_employee_second(user_factory):
    """Второй тестовый сотрудник"""
    return user_factory(email='emp2@test.com')


@pytest.fixture
def test_employee_third(user_factory):
    """Третий тестовый сотрудник"""
    return user_factory(email='emp3@test.com')


@pytest.fixture
def test_department(department_factory):
    """Тестовый отдел"""
    return department_factory(name='IT Department')


@pytest.fixture
def test_department_second(department_factory):
    """Второй тестовый отдел"""
    return department_factory(name='HR Department')


@pytest.fixture
def test_staff_user(user_factory):
    """Staff пользователь"""
    return user_factory(email='staff@test.com', staff=True)


@pytest.fixture
def create_request_helper(db):
    """Хелпер для создания заявки с получателями"""
    from requests_app.models import Request
    from requests_app.enums import RequestStatus, RequestType
    
    def _create(employee, recipients=None, cc_users=None, departments=None,
                sent_to_all=False, **kwargs):
        defaults = {
            'type': RequestType.OTHER,
            'title': 'Test request',
            'status': RequestStatus.PENDING
        }
        defaults.update(kwargs)
        
        request = Request.objects.create(
            employee=employee,
            sent_to_all_department=sent_to_all,
            **defaults
        )
        
        if recipients:
            if not isinstance(recipients, list):
                recipients = [recipients]
            request.recipients.set(recipients)
        if cc_users:
            if not isinstance(cc_users, list):
                cc_users = [cc_users]
            request.cc_users.set(cc_users)
        if departments:
            if not isinstance(departments, list):
                departments = [departments]
            request.departments.set(departments)
        
        return request
    
    return _create


@pytest.fixture
def global_viewer(user_factory):
    """Пользователь с глобальным правом can_view_all_requests"""
    from django.contrib.auth.models import Permission
    from django.contrib.contenttypes.models import ContentType
    from requests_app.models import Request
    
    user = user_factory(email='global@test.com')
    
    # Получаем или создаем permission
    ct = ContentType.objects.get_for_model(Request)
    perm, _ = Permission.objects.get_or_create(
        content_type=ct,
        codename='can_view_all_requests',
        defaults={'name': 'Можно просмотреть все заявления'}
    )
    
    user.user_permissions.add(perm)
    return user

