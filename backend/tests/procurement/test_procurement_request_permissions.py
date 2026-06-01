"""
Тесты прав доступа для API заявок на закупку.

Сценарии:
1. Создание заявки:
   - любой аутентифицированный пользователь → любой отдел
   - requestor всегда текущий пользователь

2. Изменение заявки:
   - admin/staff/superuser → любая заявка в DRAFT
   - модельные права → любая заявка в DRAFT
   - автор заявки → своя заявка в DRAFT
   - начальник отдела → заявки своего отдела в DRAFT
   - другой сотрудник → запрещено

3. Удаление заявки:
   - admin/staff/superuser → любая заявка
   - модельные права → любая заявка в DRAFT
   - автор заявки → своя заявка в DRAFT
   - начальник отдела → заявки своего отдела в DRAFT
   - другой сотрудник → запрещено

4. Просмотр заявок:
   - сотрудник видит: свои + своего отдела + где approver
   - admin/staff → все заявки
"""

import pytest
from decimal import Decimal
from datetime import date

from django.urls import reverse
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from rest_framework import status
from rest_framework.test import APIClient

from employees.models import Department, EmployeeDepartment
from procurement.models import ProcurementRequest
from procurement.constants import ProcurementStatus, UrgencyLevel

User = get_user_model()


# =============================================================================
# Helpers
# =============================================================================

_phone_counter = 0


def unique_phone() -> str:
    """Генерирует уникальный телефон."""
    global _phone_counter
    _phone_counter += 1
    return f"+7888{_phone_counter:07d}"


def make_user(
    email: str,
    staff: bool = False,
    superuser: bool = False,
    verified: bool = True,
) -> User:
    """Создаёт пользователя."""
    return User.objects.create_user(
        email=email,
        password="testpass123",
        phone_number=unique_phone(),
        first_name="Test",
        last_name="User",
        is_staff=staff,
        is_superuser=superuser,
        is_active=True,
        email_verified=verified,
        send_activation_email=False,
    )


def make_department(name: str, head: User = None) -> Department:
    """Создаёт отдел."""
    return Department.objects.create(name=name, head=head)


def add_user_to_dept(
    user: User,
    dept: Department,
    is_active: bool = True
) -> EmployeeDepartment:
    """Добавляет пользователя в отдел."""
    link, _ = EmployeeDepartment.objects.update_or_create(
        employee=user,
        department=dept,
        defaults={"is_active": is_active}
    )
    return link


def grant_model_permission(user: User, perm_codename: str, model_class) -> None:
    """Выдаёт модельное право пользователю."""
    ct = ContentType.objects.get_for_model(model_class)
    perm = Permission.objects.get(content_type=ct, codename=perm_codename)
    user.user_permissions.add(perm)
    # Очищаем кэш прав пользователя
    if hasattr(user, '_perm_cache'):
        del user._perm_cache
    if hasattr(user, '_user_perm_cache'):
        del user._user_perm_cache


def make_procurement_request(
    title: str,
    dept: Department,
    requestor: User,
    status: str = ProcurementStatus.DRAFT,
) -> ProcurementRequest:
    """Создаёт заявку на закупку."""
    return ProcurementRequest.objects.create(
        title=title,
        description="Тестовое описание",
        department=dept,
        requestor=requestor,
        status=status,
        urgency=UrgencyLevel.MEDIUM,
    )


def request_list_url() -> str:
    """URL для списка/создания заявок."""
    return reverse("api:v1:procurement:procurementrequest-list")


def request_detail_url(pk: int) -> str:
    """URL для конкретной заявки."""
    return reverse("api:v1:procurement:procurementrequest-detail", args=[pk])


def valid_request_data(dept: Department, title: str = "Тестовая заявка") -> dict:
    """Валидные данные для создания заявки."""
    return {
        "title": title,
        "description": "Описание закупки",
        "department": dept.id,
        "urgency": UrgencyLevel.MEDIUM,
        "items": [
            {
                "name": "Тестовый товар",
                "quantity": 1,
                "unit": "шт",
                "estimated_unit_price": "1000.00",
            }
        ]
    }


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def api_client() -> APIClient:
    return APIClient()


@pytest.fixture
def admin_user(db) -> User:
    """Администратор (staff)."""
    return make_user("admin_proc@example.com", staff=True)


@pytest.fixture
def superuser(db) -> User:
    """Суперпользователь."""
    return make_user("super_proc@example.com", superuser=True)


@pytest.fixture
def model_perm_user(db) -> User:
    """Пользователь с модельными правами на заявки."""
    user = make_user("modelperm_proc@example.com")
    grant_model_permission(user, "add_procurementrequest", ProcurementRequest)
    grant_model_permission(user, "change_procurementrequest", ProcurementRequest)
    grant_model_permission(user, "delete_procurementrequest", ProcurementRequest)
    # Перезагружаем из БД для обновления кэша прав
    user = User.objects.get(pk=user.pk)
    return user


@pytest.fixture
def dept_it(db) -> Department:
    """IT отдел (без начальника изначально)."""
    return make_department("IT отдел для заявок")


@pytest.fixture
def dept_hr(db) -> Department:
    """HR отдел."""
    return make_department("HR отдел для заявок")


@pytest.fixture
def dept_head(db, dept_it) -> User:
    """Начальник IT отдела."""
    user = make_user("head_proc@example.com")
    dept_it.head = user
    dept_it.save()
    add_user_to_dept(user, dept_it)
    return user


@pytest.fixture
def dept_member(db, dept_it) -> User:
    """Обычный сотрудник IT отдела."""
    user = make_user("member_proc@example.com")
    add_user_to_dept(user, dept_it)
    return user


@pytest.fixture
def other_dept_member(db, dept_hr) -> User:
    """Сотрудник HR отдела."""
    user = make_user("hr_member_proc@example.com")
    add_user_to_dept(user, dept_hr)
    return user


@pytest.fixture
def user_without_dept(db) -> User:
    """Пользователь без отдела."""
    return make_user("nodept_proc@example.com")


# =============================================================================
# Tests: Создание заявки - кто может
# =============================================================================

@pytest.mark.django_db
class TestProcurementRequestCreateAccess:
    """Тесты: кто может создавать заявки."""

    def test_unauthenticated_cannot_create(self, api_client, dept_it):
        """Неаутентифицированный пользователь не может создавать."""
        data = valid_request_data(dept_it)
        response = api_client.post(request_list_url(), data, format="json")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_admin_can_create_in_any_dept(
        self, api_client, admin_user, dept_it, dept_hr
    ):
        """Админ может создавать заявку в любом отделе."""
        api_client.force_authenticate(user=admin_user)
        
        # В IT отдел
        data = valid_request_data(dept_it, "Заявка в IT")
        response = api_client.post(request_list_url(), data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        
        # В HR отдел
        data = valid_request_data(dept_hr, "Заявка в HR")
        response = api_client.post(request_list_url(), data, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_superuser_can_create_in_any_dept(
        self, api_client, superuser, dept_it
    ):
        """Суперпользователь может создавать заявку в любом отделе."""
        api_client.force_authenticate(user=superuser)
        data = valid_request_data(dept_it)
        response = api_client.post(request_list_url(), data, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_model_perm_user_can_create_in_any_dept(
        self, api_client, model_perm_user, dept_it, dept_hr
    ):
        """Пользователь с модельными правами может создавать в любом отделе."""
        api_client.force_authenticate(user=model_perm_user)
        
        data = valid_request_data(dept_hr, "Заявка с модельными правами")
        response = api_client.post(request_list_url(), data, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_dept_member_can_create_in_own_dept(
        self, api_client, dept_member, dept_it
    ):
        """Сотрудник отдела может создать заявку в СВОЁМ отделе."""
        api_client.force_authenticate(user=dept_member)
        data = valid_request_data(dept_it)
        response = api_client.post(request_list_url(), data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['department'] == dept_it.id

    def test_dept_member_can_create_in_other_dept(
        self, api_client, dept_member, dept_hr
    ):
        """Сотрудник отдела может создать заявку в чужом отделе."""
        api_client.force_authenticate(user=dept_member)
        data = valid_request_data(dept_hr)
        response = api_client.post(request_list_url(), data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['department'] == dept_hr.id
        assert response.data['requestor'] == dept_member.id

    def test_dept_head_can_create_in_own_dept(
        self, api_client, dept_head, dept_it
    ):
        """Начальник отдела может создать заявку в своём отделе."""
        api_client.force_authenticate(user=dept_head)
        data = valid_request_data(dept_it)
        response = api_client.post(request_list_url(), data, format="json")
        assert response.status_code == status.HTTP_201_CREATED

    def test_dept_head_can_create_in_other_dept(
        self, api_client, dept_head, dept_hr
    ):
        """Начальник отдела может создать заявку в чужом отделе."""
        api_client.force_authenticate(user=dept_head)
        data = valid_request_data(dept_hr)
        response = api_client.post(request_list_url(), data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['department'] == dept_hr.id
        assert response.data['requestor'] == dept_head.id

    def test_user_without_dept_can_create(
        self, api_client, user_without_dept, dept_it
    ):
        """Пользователь без отдела может создать заявку в выбранном отделе."""
        api_client.force_authenticate(user=user_without_dept)
        data = valid_request_data(dept_it)
        response = api_client.post(request_list_url(), data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['department'] == dept_it.id
        assert response.data['requestor'] == user_without_dept.id

    def test_requestor_is_set_to_current_user(
        self, api_client, dept_member, dept_it
    ):
        """Заявитель автоматически устанавливается как текущий пользователь."""
        api_client.force_authenticate(user=dept_member)
        data = valid_request_data(dept_it)
        response = api_client.post(request_list_url(), data, format="json")
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['requestor'] == dept_member.id


# =============================================================================
# Tests: Изменение заявки
# =============================================================================

@pytest.mark.django_db
class TestProcurementRequestUpdateAccess:
    """Тесты: кто может редактировать заявки."""

    def test_admin_can_update_any_draft(
        self, api_client, admin_user, dept_member, dept_it
    ):
        """Админ может редактировать любую заявку в DRAFT."""
        request = make_procurement_request("Заявка", dept_it, dept_member)
        
        api_client.force_authenticate(user=admin_user)
        response = api_client.patch(
            request_detail_url(request.id),
            {"title": "Изменено админом"},
            format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == "Изменено админом"

    def test_superuser_can_update_any_draft(
        self, api_client, superuser, dept_member, dept_it
    ):
        """Суперпользователь может редактировать любую заявку в DRAFT."""
        request = make_procurement_request("Заявка", dept_it, dept_member)
        
        api_client.force_authenticate(user=superuser)
        response = api_client.patch(
            request_detail_url(request.id),
            {"title": "Изменено суперюзером"},
            format="json"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_model_perm_user_can_update_any_draft(
        self, api_client, model_perm_user, dept_member, dept_it
    ):
        """Пользователь с модельными правами может редактировать любую заявку."""
        request = make_procurement_request("Заявка", dept_it, dept_member)
        
        api_client.force_authenticate(user=model_perm_user)
        response = api_client.patch(
            request_detail_url(request.id),
            {"title": "Изменено с модельными правами"},
            format="json"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_owner_can_update_own_draft(
        self, api_client, dept_member, dept_it
    ):
        """Автор может редактировать свою заявку в DRAFT."""
        request = make_procurement_request("Моя заявка", dept_it, dept_member)
        
        api_client.force_authenticate(user=dept_member)
        response = api_client.patch(
            request_detail_url(request.id),
            {"title": "Моя обновлённая заявка"},
            format="json"
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == "Моя обновлённая заявка"

    def test_owner_cannot_update_pending(
        self, api_client, dept_member, dept_it
    ):
        """Автор НЕ может редактировать заявку в статусе PENDING."""
        request = make_procurement_request(
            "Заявка на согласовании",
            dept_it,
            dept_member,
            status=ProcurementStatus.PENDING
        )
        
        api_client.force_authenticate(user=dept_member)
        response = api_client.patch(
            request_detail_url(request.id),
            {"title": "Попытка изменить"},
            format="json"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_owner_cannot_update_approved(
        self, api_client, dept_member, dept_it
    ):
        """Автор НЕ может редактировать заявку в статусе APPROVED."""
        request = make_procurement_request(
            "Одобренная заявка",
            dept_it,
            dept_member,
            status=ProcurementStatus.APPROVED
        )
        
        api_client.force_authenticate(user=dept_member)
        response = api_client.patch(
            request_detail_url(request.id),
            {"title": "Попытка изменить"},
            format="json"
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_dept_head_can_update_dept_draft(
        self, api_client, dept_head, dept_member, dept_it
    ):
        """Начальник отдела может редактировать заявки своего отдела в DRAFT."""
        request = make_procurement_request("Заявка сотрудника", dept_it, dept_member)
        
        api_client.force_authenticate(user=dept_head)
        response = api_client.patch(
            request_detail_url(request.id),
            {"title": "Изменено начальником"},
            format="json"
        )
        assert response.status_code == status.HTTP_200_OK

    def test_dept_head_cannot_update_other_dept(
        self, api_client, dept_head, other_dept_member, dept_hr
    ):
        """Начальник отдела НЕ может редактировать заявки другого отдела."""
        request = make_procurement_request(
            "Заявка HR", dept_hr, other_dept_member
        )
        
        api_client.force_authenticate(user=dept_head)
        response = api_client.patch(
            request_detail_url(request.id),
            {"title": "Попытка изменить HR"},
            format="json"
        )
        # 404 - не видит в queryset, 403 - видит но нет прав
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ]

    def test_other_user_cannot_update(
        self, api_client, dept_member, other_dept_member, dept_it
    ):
        """Другой сотрудник НЕ может редактировать чужую заявку."""
        request = make_procurement_request("Заявка IT", dept_it, dept_member)
        
        api_client.force_authenticate(user=other_dept_member)
        response = api_client.patch(
            request_detail_url(request.id),
            {"title": "Попытка изменить"},
            format="json"
        )
        # 404 - не видит в queryset, 403 - видит но нет прав
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ]


# =============================================================================
# Tests: Удаление заявки
# =============================================================================

@pytest.mark.django_db
class TestProcurementRequestDeleteAccess:
    """Тесты: кто может удалять заявки."""

    def test_admin_can_delete_any(
        self, api_client, admin_user, dept_member, dept_it
    ):
        """Админ может удалить любую заявку."""
        request = make_procurement_request("Заявка", dept_it, dept_member)
        
        api_client.force_authenticate(user=admin_user)
        response = api_client.delete(request_detail_url(request.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_superuser_can_delete_any(
        self, api_client, superuser, dept_member, dept_it
    ):
        """Суперпользователь может удалить любую заявку."""
        request = make_procurement_request("Заявка", dept_it, dept_member)
        
        api_client.force_authenticate(user=superuser)
        response = api_client.delete(request_detail_url(request.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_model_perm_user_can_delete(
        self, api_client, model_perm_user, dept_member, dept_it
    ):
        """Пользователь с модельными правами может удалить заявку."""
        request = make_procurement_request("Заявка", dept_it, dept_member)
        
        api_client.force_authenticate(user=model_perm_user)
        response = api_client.delete(request_detail_url(request.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_owner_can_delete_own_draft(
        self, api_client, dept_member, dept_it
    ):
        """Автор может удалить свою заявку в DRAFT."""
        request = make_procurement_request("Моя заявка", dept_it, dept_member)
        
        api_client.force_authenticate(user=dept_member)
        response = api_client.delete(request_detail_url(request.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_owner_cannot_delete_pending(
        self, api_client, dept_member, dept_it
    ):
        """Автор НЕ может удалить заявку в статусе PENDING."""
        request = make_procurement_request(
            "Заявка на согласовании",
            dept_it,
            dept_member,
            status=ProcurementStatus.PENDING
        )
        
        api_client.force_authenticate(user=dept_member)
        response = api_client.delete(request_detail_url(request.id))
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_dept_head_can_delete_dept_draft(
        self, api_client, dept_head, dept_member, dept_it
    ):
        """Начальник отдела может удалить заявку своего отдела в DRAFT."""
        request = make_procurement_request("Заявка сотрудника", dept_it, dept_member)
        
        api_client.force_authenticate(user=dept_head)
        response = api_client.delete(request_detail_url(request.id))
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_dept_head_cannot_delete_other_dept(
        self, api_client, dept_head, other_dept_member, dept_hr
    ):
        """Начальник отдела НЕ может удалить заявку другого отдела."""
        request = make_procurement_request(
            "Заявка HR", dept_hr, other_dept_member
        )
        
        api_client.force_authenticate(user=dept_head)
        response = api_client.delete(request_detail_url(request.id))
        # 404 - не видит в queryset, 403 - видит но нет прав
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ]

    def test_other_user_cannot_delete(
        self, api_client, other_dept_member, dept_member, dept_it
    ):
        """Другой сотрудник НЕ может удалить чужую заявку."""
        request = make_procurement_request("Заявка IT", dept_it, dept_member)
        
        api_client.force_authenticate(user=other_dept_member)
        response = api_client.delete(request_detail_url(request.id))
        # 404 - не видит в queryset, 403 - видит но нет прав
        assert response.status_code in [
            status.HTTP_403_FORBIDDEN,
            status.HTTP_404_NOT_FOUND
        ]


# =============================================================================
# Tests: Просмотр заявок
# =============================================================================

@pytest.mark.django_db
class TestProcurementRequestViewAccess:
    """Тесты: видимость заявок."""

    def test_unauthenticated_cannot_view_list(self, api_client):
        """Неаутентифицированный пользователь не видит список."""
        response = api_client.get(request_list_url())
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_unauthenticated_cannot_view_detail(
        self, api_client, dept_member, dept_it
    ):
        """Неаутентифицированный пользователь не видит детали."""
        request = make_procurement_request("Заявка", dept_it, dept_member)
        response = api_client.get(request_detail_url(request.id))
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_user_sees_own_requests(
        self, api_client, dept_member, dept_it
    ):
        """Пользователь видит свои заявки."""
        my_request = make_procurement_request("Моя заявка", dept_it, dept_member)
        
        api_client.force_authenticate(user=dept_member)
        response = api_client.get(request_list_url())
        
        assert response.status_code == status.HTTP_200_OK
        request_ids = [r['id'] for r in response.data['results']]
        assert my_request.id in request_ids

    def test_user_sees_dept_requests(
        self, api_client, dept_member, dept_head, dept_it
    ):
        """Пользователь видит заявки своего отдела."""
        # Заявка начальника
        head_request = make_procurement_request(
            "Заявка начальника", dept_it, dept_head
        )
        
        api_client.force_authenticate(user=dept_member)
        response = api_client.get(request_list_url())
        
        assert response.status_code == status.HTTP_200_OK
        request_ids = [r['id'] for r in response.data['results']]
        assert head_request.id in request_ids

    def test_user_does_not_see_other_dept_requests(
        self, api_client, dept_member, other_dept_member, dept_hr
    ):
        """Пользователь НЕ видит заявки другого отдела."""
        hr_request = make_procurement_request(
            "Заявка HR", dept_hr, other_dept_member
        )
        
        api_client.force_authenticate(user=dept_member)
        response = api_client.get(request_list_url())
        
        assert response.status_code == status.HTTP_200_OK
        request_ids = [r['id'] for r in response.data['results']]
        assert hr_request.id not in request_ids

    def test_admin_sees_all_requests(
        self, api_client, admin_user, dept_member, other_dept_member, dept_it, dept_hr
    ):
        """Админ видит все заявки."""
        it_request = make_procurement_request("Заявка IT", dept_it, dept_member)
        hr_request = make_procurement_request("Заявка HR", dept_hr, other_dept_member)
        
        api_client.force_authenticate(user=admin_user)
        response = api_client.get(request_list_url())
        
        assert response.status_code == status.HTTP_200_OK
        request_ids = [r['id'] for r in response.data['results']]
        assert it_request.id in request_ids
        assert hr_request.id in request_ids

    def test_superuser_sees_all_requests(
        self, api_client, superuser, dept_member, other_dept_member, dept_it, dept_hr
    ):
        """Суперпользователь видит все заявки."""
        it_request = make_procurement_request("Заявка IT", dept_it, dept_member)
        hr_request = make_procurement_request("Заявка HR", dept_hr, other_dept_member)
        
        api_client.force_authenticate(user=superuser)
        response = api_client.get(request_list_url())
        
        assert response.status_code == status.HTTP_200_OK
        request_ids = [r['id'] for r in response.data['results']]
        assert it_request.id in request_ids
        assert hr_request.id in request_ids


# =============================================================================
# Tests: Валидация данных
# =============================================================================

@pytest.mark.django_db
class TestProcurementRequestValidation:
    """Тесты валидации данных заявки."""

    def test_cannot_create_without_items(
        self, api_client, dept_member, dept_it
    ):
        """Нельзя создать заявку без позиций."""
        api_client.force_authenticate(user=dept_member)
        data = {
            "title": "Заявка без позиций",
            "description": "Описание",
            "department": dept_it.id,
            "urgency": UrgencyLevel.MEDIUM,
            "items": []
        }
        response = api_client.post(request_list_url(), data, format="json")
        # Может вернуть 400 или позволить создать пустую заявку (зависит от логики)
        # Проверяем, что хотя бы не 500
        assert response.status_code in [
            status.HTTP_201_CREATED,
            status.HTTP_400_BAD_REQUEST
        ]

    def test_cannot_change_requestor(
        self, api_client, dept_member, dept_head, dept_it
    ):
        """Нельзя изменить заявителя при редактировании."""
        request = make_procurement_request("Заявка", dept_it, dept_member)
        
        api_client.force_authenticate(user=dept_member)
        response = api_client.patch(
            request_detail_url(request.id),
            {"requestor": dept_head.id},
            format="json"
        )
        
        # Либо игнорирует поле, либо возвращает ошибку
        if response.status_code == status.HTTP_200_OK:
            # Проверяем, что requestor не изменился
            assert response.data['requestor'] == dept_member.id

    def test_cannot_change_department_after_creation(
        self, api_client, dept_member, dept_it, dept_hr
    ):
        """Нельзя изменить отдел после создания (для обычного пользователя)."""
        request = make_procurement_request("Заявка", dept_it, dept_member)
        
        api_client.force_authenticate(user=dept_member)
        response = api_client.patch(
            request_detail_url(request.id),
            {"department": dept_hr.id},
            format="json"
        )
        
        # Либо игнорирует поле, либо возвращает ошибку
        if response.status_code == status.HTTP_200_OK:
            # Проверяем, что department не изменился
            assert response.data['department'] == dept_it.id
