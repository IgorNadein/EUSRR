"""
Тесты API для заявок на закупку (ProcurementRequest).
"""

from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

import pytest
from django.contrib.auth.models import Permission
from django.contrib.contenttypes.models import ContentType
from django.urls import reverse
from django.utils.dateparse import parse_datetime
from django.utils import timezone
from push_notifications.models import WebPushDevice
from rest_framework import status
from rest_framework.test import APIClient

from communications.comments_helpers import get_comments
from employees.constants import DeptPerm
from employees.models import (
    Department,
    DepartmentPermission,
    DepartmentRole,
    Employee,
    EmployeeDepartment,
    RoleAssignment,
)
from procurement.constants import (
    ApprovalStatus,
    ProcurementFulfillmentStatus,
    ProcurementItemExecutionStatus,
    ProcurementStatus,
    UrgencyLevel,
)
from procurement.models import (
    Approval,
    ApprovalRoute,
    Budget,
    ProcurementItem,
    ProcurementRequest,
    ProcurementSettings,
)
from procurement.notifications.handlers import notify_new_request
from tasks.models import (
    Task,
    TaskBoard,
    TaskColumn,
    TaskLinkedObject,
    TaskLinkedObjectKind,
)
from notifications.models import Notification, UserChannelPreferences


pytestmark = pytest.mark.django_db

HEAD_PRIORITY = 1
FINANCE_PRIORITY = 2
DIRECTOR_PRIORITY = 3


def prepare_for_recipient_department_submit(
    procurement_request,
    recipient_department,
):
    procurement_request.processing_department = recipient_department
    procurement_request.status = ProcurementStatus.WAITING
    procurement_request.save(
        update_fields=[
            "processing_department",
            "status",
            "updated_at",
        ]
    )
    return procurement_request


@pytest.fixture
def api_client():
    """API клиент."""
    return APIClient()


@pytest.fixture
def department(db):
    """Тестовый отдел."""
    return Department.objects.create(
        name="IT отдел",
        description="Отдел информационных технологий"
    )


@pytest.fixture
def recipient_department(db):
    """Отдел-получатель заявки на закупку."""
    return Department.objects.create(
        name="Снабжение",
        description="Отдел-получатель заявок на закупку",
    )


@pytest.fixture
def recipient_user(db, recipient_department):
    """Сотрудник отдела-получателя заявки."""
    employee = Employee.objects.create_user(
        email="recipient@example.com",
        password="testpass123",
        phone_number="+79990000001",
        first_name="Получатель",
        last_name="Заявки",
        is_active=True,
        email_verified=True,
        send_activation_email=False,
    )
    EmployeeDepartment.objects.create(
        employee=employee,
        department=recipient_department,
        is_active=True,
    )
    return employee


@pytest.fixture
def user(db, department):
    """Обычный пользователь."""
    user = Employee.objects.create_user(
        email="user@example.com",
        password="testpass123",
        phone_number="+79991111111",
        first_name="Иван",
        last_name="Иванов",
        is_active=True,
        email_verified=True,
        send_activation_email=False,
    )
    # Связываем с отделом
    EmployeeDepartment.objects.create(
        employee=user,
        department=department,
        is_active=True
    )
    return user


@pytest.fixture
def department_head(db, department):
    """Руководитель отдела."""
    head = Employee.objects.create_user(
        email="head@example.com",
        password="testpass123",
        phone_number="+79992222222",
        first_name="Петр",
        last_name="Петров",
        is_active=True,
        email_verified=True,
        send_activation_email=False,
    )
    # Назначаем руководителем отдела (автоматически создаст EmployeeDepartment)
    department.head = head
    department.save()
    return head


@pytest.fixture
def staff_user(db):
    """Staff пользователь."""
    return Employee.objects.create_user(
        email="staff@example.com",
        password="testpass123",
        phone_number="+79993333333",
        first_name="Админ",
        last_name="Админов",
        is_staff=True,
        is_active=True,
        email_verified=True,
        send_activation_email=False,
    )


@pytest.fixture
def superuser(db):
    """Суперпользователь без назначения в текущем approval stage."""
    return Employee.objects.create_user(
        email="superuser@example.com",
        password="testpass123",
        phone_number="+79996666666",
        first_name="Супер",
        last_name="Пользователь",
        is_staff=True,
        is_superuser=True,
        is_active=True,
        email_verified=True,
        send_activation_email=False,
    )


@pytest.fixture
def approver_with_permission(db, department):
    """Пользователь с модельным permission approve_procurementrequest."""
    employee = Employee.objects.create_user(
        email="approver@example.com",
        password="testpass123",
        phone_number="+79997777777",
        first_name="Разрешенный",
        last_name="Согласующий",
        is_active=True,
        email_verified=True,
        send_activation_email=False,
    )
    EmployeeDepartment.objects.create(
        employee=employee,
        department=department,
        is_active=True,
    )
    employee.user_permissions.add(
        Permission.objects.get(codename="approve_procurementrequest")
    )
    return employee


@pytest.fixture
def budget(db, department):
    """Бюджет отдела."""
    return Budget.objects.create(
        department=department,
        year=2026,
        quarter=1,
        allocated_amount=Decimal("500000.00"),
        spent_amount=Decimal("0.00"),
    )


@pytest.fixture
def procurement_request(db, department, user):
    """Тестовая заявка."""
    return ProcurementRequest.objects.create(
        title="Закупка ноутбуков",
        description="Нужны новые ноутбуки для разработчиков",
        department=department,
        requestor=user,
        status=ProcurementStatus.DRAFT,
        urgency=UrgencyLevel.MEDIUM,
    )


@pytest.fixture
def procurement_item(db, procurement_request):
    """Позиция в заявке."""
    return ProcurementItem.objects.create(
        request=procurement_request,
        name="Ноутбук Dell XPS 15",
        description="i7, 32GB RAM, 1TB SSD",
        quantity=3,
        unit="шт",
        estimated_unit_price=Decimal("120000.00"),
        supplier_info="https://example.com/dell-xps-15",
    )


# ==============================================================================
# ТЕСТЫ СПИСКА ЗАЯВОК
# ==============================================================================


class TestProcurementRequestList:
    """Тесты получения списка заявок."""

    def test_list_unauthorized(self, api_client):
        """Неавторизованный доступ запрещен."""
        url = reverse('api:v1:procurement:procurementrequest-list')
        response = api_client.get(url)
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_list_own_requests(
        self, api_client, user, procurement_request
    ):
        """Пользователь видит свои заявки."""
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:procurementrequest-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        results = response.data['results']
        assert len(results) == 1
        assert results[0]['id'] == procurement_request.id
        assert results[0]['title'] == "Закупка ноутбуков"

    def test_list_includes_visible_linked_tasks_only(
        self,
        api_client,
        user,
        procurement_request,
    ):
        """Список заявок отдаёт бейджи только доступных пользователю задач."""
        hidden_member = Employee.objects.create_user(
            email="hidden-board-member@example.com",
            password="testpass123",
            phone_number="+79998880003",
            first_name="Скрытый",
            last_name="Участник",
            is_active=True,
            email_verified=True,
            send_activation_email=False,
        )
        visible_board = TaskBoard.objects.create(
            name="Видимая доска закупок",
            created_by=user,
        )
        visible_column = TaskColumn.objects.create(
            board=visible_board,
            name="Новые",
            position=1000,
            color="#38bdf8",
        )
        visible_task = Task.objects.create(
            board=visible_board,
            column=visible_column,
            title="Видимая задача закупки",
            created_by=user,
            priority="high",
        )
        hidden_board = TaskBoard.objects.create(
            name="Скрытая доска закупок",
            created_by=hidden_member,
        )
        hidden_board.members.add(hidden_member)
        hidden_column = TaskColumn.objects.create(
            board=hidden_board,
            name="Новые",
            position=1000,
            color="#ef4444",
        )
        hidden_task = Task.objects.create(
            board=hidden_board,
            column=hidden_column,
            title="Скрытая задача закупки",
            created_by=hidden_member,
            priority="critical",
        )
        request_ct = ContentType.objects.get_for_model(ProcurementRequest)
        TaskLinkedObject.objects.create(
            task=visible_task,
            kind=TaskLinkedObjectKind.PROCUREMENT_REQUEST,
            content_type=request_ct,
            object_id=procurement_request.id,
            created_by=user,
        )
        TaskLinkedObject.objects.create(
            task=hidden_task,
            kind=TaskLinkedObjectKind.PROCUREMENT_REQUEST,
            content_type=request_ct,
            object_id=procurement_request.id,
            created_by=hidden_member,
        )

        api_client.force_authenticate(user=user)
        response = api_client.get(
            reverse('api:v1:procurement:procurementrequest-list')
        )

        assert response.status_code == status.HTTP_200_OK
        result = response.data['results'][0]
        assert result['id'] == procurement_request.id
        assert result['linked_tasks'] == [
            {
                'link_id': visible_task.linked_objects.get().id,
                'id': visible_task.id,
                'title': 'Видимая задача закупки',
                'board_id': visible_board.id,
                'board_name': 'Видимая доска закупок',
                'column_id': visible_column.id,
                'column_name': 'Новые',
                'column_color': '#38bdf8',
                'priority': 'high',
                'priority_display': 'Высокий',
            }
        ]

    def test_list_department_requests(
        self, api_client, department_head, procurement_request
    ):
        """Руководитель видит заявки своего отдела."""
        api_client.force_authenticate(user=department_head)
        url = reverse('api:v1:procurement:procurementrequest-list')
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        # Руководитель может видеть заявки отдела через scope=department
        
    def test_filter_by_status(
        self, api_client, user, department, procurement_request
    ):
        """Фильтрация по статусу."""
        # Создаем заявку с другим статусом
        ProcurementRequest.objects.create(
            title="Другая заявка",
            description="Описание",
            department=department,
            requestor=user,
            status=ProcurementStatus.PENDING,
        )
        
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:procurementrequest-list')
        
        # Фильтр DRAFT
        response = api_client.get(url, {'status': ProcurementStatus.DRAFT})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1
        assert response.data['results'][0]['status'] == ProcurementStatus.DRAFT

    def test_search_by_title(
        self, api_client, user, procurement_request
    ):
        """Поиск по названию."""
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:procurementrequest-list')
        
        response = api_client.get(url, {'search': 'ноутбук'})
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data['results']) == 1

    def test_filter_by_requestor_executor_and_processing_department(
        self, api_client, staff_user, user, department
    ):
        """Фильтрация по заказчику, исполнителю и отделу-исполнителю."""
        processing_department = Department.objects.create(name="Снабжение")
        other_requestor = Employee.objects.create_user(
            email="other-requestor@example.com",
            password="testpass123",
            phone_number="+79998880001",
            first_name="Другой",
            last_name="Заказчик",
            is_active=True,
            email_verified=True,
            send_activation_email=False,
        )
        executor = Employee.objects.create_user(
            email="executor-filter@example.com",
            password="testpass123",
            phone_number="+79998880002",
            first_name="Исполнитель",
            last_name="Фильтр",
            is_active=True,
            email_verified=True,
            send_activation_email=False,
        )
        matched = ProcurementRequest.objects.create(
            title="Нужная заявка",
            description="Описание",
            department=department,
            processing_department=processing_department,
            requestor=user,
            executor=executor,
            status=ProcurementStatus.IN_PROGRESS,
        )
        other = ProcurementRequest.objects.create(
            title="Другая заявка",
            description="Описание",
            department=department,
            requestor=other_requestor,
            status=ProcurementStatus.DRAFT,
        )

        api_client.force_authenticate(user=staff_user)
        url = reverse('api:v1:procurement:procurementrequest-list')

        for params in (
            {'requestor': user.id},
            {'executor': executor.id},
            {'processing_department': processing_department.id},
        ):
            response = api_client.get(url, params)
            assert response.status_code == status.HTTP_200_OK
            ids = {item['id'] for item in response.data['results']}
            assert matched.id in ids
            assert other.id not in ids

    def test_filter_by_created_date_range(
        self, api_client, staff_user, user, department
    ):
        """Фильтрация по диапазону дат создания."""
        now = timezone.now()
        old_request = ProcurementRequest.objects.create(
            title="Старая заявка",
            description="Описание",
            department=department,
            requestor=user,
            status=ProcurementStatus.DRAFT,
        )
        fresh_request = ProcurementRequest.objects.create(
            title="Новая заявка",
            description="Описание",
            department=department,
            requestor=user,
            status=ProcurementStatus.DRAFT,
        )
        ProcurementRequest.objects.filter(pk=old_request.pk).update(
            created_at=now - timedelta(days=10)
        )
        ProcurementRequest.objects.filter(pk=fresh_request.pk).update(
            created_at=now
        )

        api_client.force_authenticate(user=staff_user)
        url = reverse('api:v1:procurement:procurementrequest-list')

        response = api_client.get(
            url,
            {'date_from': (now - timedelta(days=1)).date().isoformat()},
        )
        assert response.status_code == status.HTTP_200_OK
        ids = {item['id'] for item in response.data['results']}
        assert fresh_request.id in ids
        assert old_request.id not in ids

        response = api_client.get(
            url,
            {'date_to': (now - timedelta(days=5)).date().isoformat()},
        )
        assert response.status_code == status.HTTP_200_OK
        ids = {item['id'] for item in response.data['results']}
        assert old_request.id in ids
        assert fresh_request.id not in ids

        response = api_client.get(url, {'date_from': 'not-a-date'})
        assert response.status_code == status.HTTP_200_OK


# ==============================================================================
# ТЕСТЫ СОЗДАНИЯ ЗАЯВОК
# ==============================================================================


class TestProcurementRequestCreate:
    """Тесты создания заявок."""

    def test_create_options_use_configured_processing_departments(
        self, api_client, user
    ):
        """Опции формы берутся из настроек закупок."""
        supply_department = Department.objects.create(name="Снабжение")
        warehouse_department = Department.objects.create(name="Склад")
        hidden_department = Department.objects.create(name="Бухгалтерия")
        settings = ProcurementSettings.get_solo()
        settings.default_processing_department = supply_department
        settings.save()
        settings.available_processing_departments.set(
            [supply_department, warehouse_department]
        )

        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-create-options'
        )

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['default_processing_department'] == (
            supply_department.id
        )
        department_ids = {
            department['id']
            for department in response.data['processing_departments']
        }
        assert department_ids == {
            supply_department.id,
            warehouse_department.id,
        }
        assert hidden_department.id not in department_ids

    def test_create_request_with_items(
        self, api_client, user, department
    ):
        """Создание заявки с позициями."""
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:procurementrequest-list')
        
        data = {
            'title': 'Закупка мониторов',
            'description': 'Нужны мониторы для офиса',
            'department': department.id,
            'urgency': UrgencyLevel.LOW,
            'items': [
                {
                    'name': 'Монитор 27"',
                    'quantity': 5,
                    'unit': 'шт',
                    'estimated_unit_price': '25000.00',
                    'description': '4K, IPS',
                    'expected_delivery_dates': ['2026-06-10', '2026-06-12'],
                },
                {
                    'name': 'Монитор 24"',
                    'quantity': 10,
                    'unit': 'шт',
                    'estimated_unit_price': '18000.00',
                },
            ]
        }
        
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['title'] == 'Закупка мониторов'
        assert response.data['requestor'] == user.id
        assert response.data['status'] == ProcurementStatus.DRAFT
        
        # Проверяем что позиции созданы
        request_id = response.data['id']
        request = ProcurementRequest.objects.get(id=request_id)
        assert request.items.count() == 2
        assert request.total_cost == Decimal('305000.00')  # 5*25k + 10*18k
        assert request.items.get(name='Монитор 27"').expected_delivery_dates == [
            '2026-06-10',
            '2026-06-12',
        ]

    def test_create_request_for_other_department(
        self, api_client, user, db
    ):
        """Можно создать заявку для любого отдела."""
        other_dept = Department.objects.create(
            name="HR отдел", description="Другой отдел"
        )
        
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:procurementrequest-list')
        
        data = {
            'title': 'Заявка',
            'description': 'Описание',
            'department': other_dept.id,
            'urgency': UrgencyLevel.MEDIUM,
            'items': []
        }
        
        response = api_client.post(url, data, format='json')
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['department'] == other_dept.id
        assert response.data['requestor'] == user.id

    def test_create_processing_department_request_skips_approvals(
        self, api_client, user, department, db
    ):
        """Заявка в отдел-исполнитель сразу попадает в очередь."""
        supply_department = Department.objects.create(
            name="Снабжение",
            description="Отдел снабжения",
        )

        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:procurementrequest-list')

        response = api_client.post(
            url,
            {
                'title': 'Расходники для производства',
                'department': department.id,
                'processing_department': supply_department.id,
                'urgency': UrgencyLevel.MEDIUM,
                'items': [
                    {
                        'name': 'Перчатки',
                        'quantity': 10,
                        'unit': 'упак',
                        'estimated_unit_price': '500.00',
                        'links': ['https://example.com/gloves'],
                    },
                ],
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['status'] == ProcurementStatus.WAITING
        request_id = response.data['id']
        procurement_request = ProcurementRequest.objects.get(id=request_id)
        assert procurement_request.description == ""
        assert procurement_request.processing_department == supply_department
        assert procurement_request.approvals.count() == 0

    def test_create_rejects_processing_department_outside_settings(
        self, api_client, user, department
    ):
        """Нельзя выбрать отдел-исполнитель вне настроек закупок."""
        allowed_department = Department.objects.create(name="Снабжение")
        blocked_department = Department.objects.create(name="Маркетинг")
        settings = ProcurementSettings.get_solo()
        settings.default_processing_department = allowed_department
        settings.save()
        settings.available_processing_departments.set([allowed_department])

        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:procurementrequest-list')

        response = api_client.post(
            url,
            {
                'title': 'Расходники для офиса',
                'department': department.id,
                'processing_department': blocked_department.id,
                'urgency': UrgencyLevel.MEDIUM,
                'items': [
                    {
                        'name': 'Бумага',
                        'quantity': 10,
                        'unit': 'пачка',
                        'estimated_unit_price': '450.00',
                    },
                ],
            },
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'processing_department' in response.data


# ==============================================================================
# ТЕСТЫ ДЕТАЛЬНОЙ ИНФОРМАЦИИ
# ==============================================================================


class TestProcurementRequestDetail:
    """Тесты получения детальной информации."""

    def test_retrieve_own_request(
        self, api_client, user, procurement_request, procurement_item
    ):
        """Получение своей заявки."""
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': procurement_request.id}
        )
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['id'] == procurement_request.id
        assert response.data['title'] == "Закупка ноутбуков"
        assert 'items' in response.data
        assert len(response.data['items']) == 1
        assert 'total_cost' in response.data
        assert 'is_editable' in response.data
        assert response.data['is_editable'] is True

    def test_retrieve_other_request_forbidden(
        self, api_client, db, procurement_request
    ):
        """Нельзя просмотреть чужую заявку (обычному пользователю)."""
        other_user = Employee.objects.create_user(
            email="other@example.com",
            password="testpass123",
            phone_number="+79994444444",
            first_name="Другой",
            last_name="Пользователь",
            send_activation_email=False,
        )
        
        api_client.force_authenticate(user=other_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': procurement_request.id}
        )
        response = api_client.get(url)
        
        assert response.status_code == status.HTTP_404_NOT_FOUND

    def test_retrieve_includes_comments_count(
        self, api_client, user, procurement_request, procurement_item
    ):
        """В detail отдается comments_count."""
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': procurement_request.id}
        )

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data['comments_count'] == 0


class TestProcurementRequestComments:
    """Комментарии к заявке на закупку."""

    def test_comment_lifecycle_updates_comments_count(
        self, api_client, user, procurement_request
    ):
        api_client.force_authenticate(user=user)

        list_url = reverse('api:v1:procurement:procurementrequest-list')
        comments_url = reverse(
            'api:v1:procurement:procurementrequest-comments',
            kwargs={'pk': procurement_request.id}
        )

        before = api_client.get(list_url)
        assert before.status_code == status.HTTP_200_OK
        before_item = next(item for item in before.data['results'] if item['id'] == procurement_request.id)
        assert before_item['comments_count'] == 0

        create_response = api_client.post(
            comments_url,
            {'text': 'Проверочный комментарий'},
            format='json',
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        assert create_response.data['request'] == procurement_request.id
        comment_id = create_response.data['id']

        comments_response = api_client.get(comments_url)
        assert comments_response.status_code == status.HTTP_200_OK
        assert len(comments_response.data) == 1
        assert comments_response.data[0]['text'] == 'Проверочный комментарий'

        middle = api_client.get(list_url)
        middle_item = next(item for item in middle.data['results'] if item['id'] == procurement_request.id)
        assert middle_item['comments_count'] == 1

        delete_url = reverse(
            'api:v1:procurement:procurementrequest-delete-comment',
            kwargs={'pk': procurement_request.id, 'comment_id': comment_id}
        )
        delete_response = api_client.delete(delete_url)
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

        after_comments = api_client.get(comments_url)
        assert after_comments.status_code == status.HTTP_200_OK
        assert after_comments.data == []

        after = api_client.get(list_url)
        after_item = next(item for item in after.data['results'] if item['id'] == procurement_request.id)
        assert after_item['comments_count'] == 0


class TestProcurementItemComments:
    """Комментарии к позиции заявки на закупку."""

    def test_item_comment_lifecycle_updates_comments_count(
        self, api_client, user, procurement_item
    ):
        api_client.force_authenticate(user=user)

        list_url = reverse('api:v1:procurement:procurementitem-list')
        comments_url = reverse(
            'api:v1:procurement:procurementitem-comments',
            kwargs={'pk': procurement_item.id}
        )

        before = api_client.get(list_url, {'request': procurement_item.request_id})
        assert before.status_code == status.HTTP_200_OK
        before_item = next(
            item for item in before.data['results']
            if item['id'] == procurement_item.id
        )
        assert before_item['comments_count'] == 0

        create_response = api_client.post(
            comments_url,
            {'text': 'Комментарий по конкретной позиции'},
            format='json',
        )
        assert create_response.status_code == status.HTTP_201_CREATED
        assert create_response.data['item'] == procurement_item.id
        assert create_response.data['request'] == procurement_item.request_id
        comment_id = create_response.data['id']

        comments_response = api_client.get(comments_url)
        assert comments_response.status_code == status.HTTP_200_OK
        assert len(comments_response.data) == 1
        assert (
            comments_response.data[0]['text']
            == 'Комментарий по конкретной позиции'
        )

        middle = api_client.get(list_url, {'request': procurement_item.request_id})
        middle_item = next(
            item for item in middle.data['results']
            if item['id'] == procurement_item.id
        )
        assert middle_item['comments_count'] == 1

        request_detail_url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': procurement_item.request_id}
        )
        request_detail = api_client.get(request_detail_url)
        assert request_detail.status_code == status.HTTP_200_OK
        detail_item = next(
            item for item in request_detail.data['items']
            if item['id'] == procurement_item.id
        )
        assert detail_item['comments_count'] == 1

        delete_url = reverse(
            'api:v1:procurement:procurementitem-delete-comment',
            kwargs={'pk': procurement_item.id, 'comment_id': comment_id}
        )
        delete_response = api_client.delete(delete_url)
        assert delete_response.status_code == status.HTTP_204_NO_CONTENT

        after_comments = api_client.get(comments_url)
        assert after_comments.status_code == status.HTTP_200_OK
        assert after_comments.data == []

        after = api_client.get(list_url, {'request': procurement_item.request_id})
        after_item = next(
            item for item in after.data['results']
            if item['id'] == procurement_item.id
        )
        assert after_item['comments_count'] == 0

    def test_outsider_cannot_comment_item(
        self, api_client, procurement_item
    ):
        outsider = Employee.objects.create_user(
            email="item-outsider@example.com",
            password="testpass123",
            phone_number="+79997777771",
            first_name="Чужой",
            last_name="Сотрудник",
            is_active=True,
            email_verified=True,
            send_activation_email=False,
        )
        api_client.force_authenticate(user=outsider)

        comments_url = reverse(
            'api:v1:procurement:procurementitem-comments',
            kwargs={'pk': procurement_item.id}
        )

        get_response = api_client.get(comments_url)
        assert get_response.status_code == status.HTTP_403_FORBIDDEN

        post_response = api_client.post(
            comments_url,
            {'text': 'Не должен пройти'},
            format='json',
        )
        assert post_response.status_code == status.HTTP_403_FORBIDDEN

    def test_processing_department_member_can_comment_item(
        self, api_client, user, department, procurement_item_factory
    ):
        supply_department = Department.objects.create(
            name="Снабжение для комментариев",
            description="Отдел снабжения",
        )
        supply_user = Employee.objects.create_user(
            email="item-supply@example.com",
            password="testpass123",
            phone_number="+79997777772",
            first_name="Снабжение",
            last_name="Комментарий",
            is_active=True,
            email_verified=True,
            send_activation_email=False,
        )
        EmployeeDepartment.objects.create(
            employee=supply_user,
            department=supply_department,
            is_active=True,
        )
        procurement_request = ProcurementRequest.objects.create(
            title="Адресная заявка для комментариев",
            description="Нужны расходники",
            department=department,
            processing_department=supply_department,
            requestor=user,
            status=ProcurementStatus.WAITING,
            urgency=UrgencyLevel.MEDIUM,
        )
        item = procurement_item_factory(request=procurement_request)

        api_client.force_authenticate(user=supply_user)
        comments_url = reverse(
            'api:v1:procurement:procurementitem-comments',
            kwargs={'pk': item.id}
        )

        response = api_client.post(
            comments_url,
            {'text': 'Уточнение от снабжения'},
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data['item'] == item.id


# ==============================================================================
# ТЕСТЫ ОБНОВЛЕНИЯ ЗАЯВОК
# ==============================================================================


class TestProcurementRequestUpdate:
    """Тесты обновления заявок."""

    def test_update_draft_request(
        self, api_client, user, procurement_request
    ):
        """Обновление заявки в статусе DRAFT."""
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': procurement_request.id}
        )
        
        data = {
            'title': 'Обновленное название',
            'urgency': UrgencyLevel.HIGH,
        }
        response = api_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['title'] == 'Обновленное название'
        assert response.data['urgency'] == UrgencyLevel.HIGH

    def test_cannot_update_submitted_request(
        self, api_client, user, procurement_request
    ):
        """Нельзя обновить отправленную заявку."""
        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()
        
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': procurement_request.id}
        )
        
        data = {'title': 'Новое название'}
        response = api_client.patch(url, data, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN


# ==============================================================================
# ТЕСТЫ АДРЕСНЫХ ЗАЯВОК В ОТДЕЛ-ИСПОЛНИТЕЛЬ
# ==============================================================================


class TestProcessingDepartmentWorkflow:
    """Workflow для заявок, направленных в отдел-исполнитель."""

    @pytest.fixture
    def supply_department(self, db):
        return Department.objects.create(
            name="Снабжение",
            description="Отдел снабжения",
        )

    @pytest.fixture
    def supply_user(self, db, supply_department):
        employee = Employee.objects.create_user(
            email="supply@example.com",
            password="testpass123",
            phone_number="+79998888888",
            first_name="Снабжение",
            last_name="Исполнитель",
            is_active=True,
            email_verified=True,
            send_activation_email=False,
        )
        EmployeeDepartment.objects.create(
            employee=employee,
            department=supply_department,
            is_active=True,
        )
        return employee

    @pytest.fixture
    def supply_role_user(self, db, supply_department):
        employee = Employee.objects.create_user(
            email="supply-role@example.com",
            password="testpass123",
            phone_number="+79998888892",
            first_name="Ролевой",
            last_name="Исполнитель",
            is_active=True,
            email_verified=True,
            send_activation_email=False,
        )
        role = DepartmentRole.objects.create(
            department=supply_department,
            name="Закупщик",
        )
        RoleAssignment.objects.create(
            employee=employee,
            role=role,
            is_active=True,
        )
        return employee

    @pytest.fixture
    def supply_replacement_user(self, db, supply_department):
        employee = Employee.objects.create_user(
            email="supply-replacement@example.com",
            password="testpass123",
            phone_number="+79998888893",
            first_name="Новый",
            last_name="Исполнитель",
            is_active=True,
            email_verified=True,
            send_activation_email=False,
        )
        EmployeeDepartment.objects.create(
            employee=employee,
            department=supply_department,
            is_active=True,
        )
        return employee

    @pytest.fixture
    def procurement_execute_user(self, db):
        employee = Employee.objects.create_user(
            email="procurement-execute@example.com",
            password="testpass123",
            phone_number="+79998888894",
            first_name="Права",
            last_name="Закупок",
            is_active=True,
            email_verified=True,
            send_activation_email=False,
        )
        employee.user_permissions.add(
            Permission.objects.get(codename="execute_procurement")
        )
        return employee

    @pytest.fixture
    def outsider(self, db):
        return Employee.objects.create_user(
            email="outsider@example.com",
            password="testpass123",
            phone_number="+79998888889",
            first_name="Чужой",
            last_name="Сотрудник",
            is_active=True,
            email_verified=True,
            send_activation_email=False,
        )

    @pytest.fixture
    def processing_request(
        self, department, user, supply_department
    ):
        return ProcurementRequest.objects.create(
            title="Заявка на расходники",
            description="Нужны расходные материалы",
            department=department,
            processing_department=supply_department,
            requestor=user,
            status=ProcurementStatus.WAITING,
            urgency=UrgencyLevel.MEDIUM,
        )

    def test_create_draft_request_does_not_notify(
        self, api_client, user, department, monkeypatch
    ):
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )

        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:procurementrequest-list')

        response = api_client.post(
            url,
            {
                "title": "Черновик закупки",
                "description": "Без отдела-исполнителя",
                "department": department.id,
                "urgency": UrgencyLevel.MEDIUM,
                "items": [
                    {
                        "name": "Перчатки",
                        "quantity": 1,
                        "unit": "шт",
                        "estimated_unit_price": "100.00",
                    }
                ],
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == ProcurementStatus.DRAFT
        assert sent == []

    def test_create_request_allows_item_without_price_and_links_with_comment(
        self, api_client, user, department
    ):
        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:procurementrequest-list')

        response = api_client.post(
            url,
            {
                "title": "Нужен расходник",
                "description": "Не знаю где купить",
                "department": department.id,
                "urgency": UrgencyLevel.MEDIUM,
                "items": [
                    {
                        "name": "Паяльник",
                        "quantity": 1,
                        "unit": "шт",
                        "initial_comment": "Нужен для ремонта, ссылок нет",
                    }
                ],
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        procurement_request = ProcurementRequest.objects.get(
            id=response.data["id"]
        )
        item = procurement_request.items.get()
        assert item.estimated_unit_price is None
        assert item.links == []
        assert procurement_request.total_cost == Decimal("0.00")
        comments = list(get_comments(item))
        assert len(comments) == 1
        assert comments[0].content == "Нужен для ремонта, ссылок нет"

    def test_create_processing_department_request_notifies_department_members(
        self, api_client, user, department, supply_department, supply_user,
        monkeypatch
    ):
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )

        supply_head = Employee.objects.create_user(
            email="supply-head@example.com",
            password="testpass123",
            phone_number="+79998888890",
            first_name="Начальник",
            last_name="Снабжения",
            is_active=True,
            email_verified=True,
            send_activation_email=False,
        )
        supply_department.head = supply_head
        supply_department.save()

        role_user = Employee.objects.create_user(
            email="role-supply@example.com",
            password="testpass123",
            phone_number="+79998888891",
            first_name="Ролевой",
            last_name="Снабженец",
            is_active=True,
            email_verified=True,
            send_activation_email=False,
        )
        role = DepartmentRole.objects.create(
            department=supply_department,
            name="Закупки",
        )
        RoleAssignment.objects.create(employee=role_user, role=role)

        api_client.force_authenticate(user=user)
        url = reverse('api:v1:procurement:procurementrequest-list')

        response = api_client.post(
            url,
            {
                "title": "Расходники",
                "description": "Нужно для производства",
                "department": department.id,
                "processing_department": supply_department.id,
                "urgency": UrgencyLevel.MEDIUM,
                "items": [
                    {
                        "name": "Лампы",
                        "quantity": 2,
                        "unit": "шт",
                        "estimated_unit_price": "300.00",
                    }
                ],
            },
            format='json',
        )

        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["status"] == ProcurementStatus.WAITING
        department_notifications = [
            item
            for item in sent
            if item["verb"] == "procurement_department_request"
        ]
        recipients = sorted(
            item["recipient"].email for item in department_notifications
        )
        assert recipients == [
            "role-supply@example.com",
            "supply-head@example.com",
            "supply@example.com",
        ]
        assert user.email not in recipients
        author_name = user.get_full_name() or user.username
        assert all(
            item["sender"] == user for item in department_notifications
        )
        assert all(
            item["data"]["title"] == "Новая заявка на закупку"
            for item in department_notifications
        )
        assert all(
            f'{author_name} направил заявку "Расходники"'
            in item["description"]
            for item in department_notifications
        )

    def test_legacy_new_request_notification_uses_requestor_as_sender(
        self, user, department, department_head, monkeypatch
    ):
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )
        procurement_request = ProcurementRequest.objects.create(
            title="Расходники",
            description="Нужно для производства",
            department=department,
            requestor=user,
            status=ProcurementStatus.DRAFT,
            urgency=UrgencyLevel.MEDIUM,
        )

        notify_new_request(procurement_request)

        assert len(sent) == 1
        author_name = user.get_full_name() or user.username
        notification = sent[0]
        assert notification["sender"] == user
        assert notification["recipient"] == department_head
        assert notification["verb"] == "procurement_new_request"
        assert notification["data"]["title"] == "Новая заявка на закупку"
        assert (
            f'{author_name} создал заявку "Расходники"'
            in notification["description"]
        )

    def test_available_shows_processing_department_requests(
        self, api_client, supply_user, processing_request, procurement_item_factory
    ):
        procurement_item_factory(request=processing_request)
        api_client.force_authenticate(user=supply_user)
        url = reverse('api:v1:procurement:procurementrequest-available')

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        ids = [item['id'] for item in response.data['results']]
        assert processing_request.id in ids

    def test_role_assignment_user_sees_processing_department_request(
        self, api_client, supply_role_user, processing_request,
        procurement_item_factory
    ):
        procurement_item_factory(request=processing_request)
        api_client.force_authenticate(user=supply_role_user)

        available_url = reverse(
            'api:v1:procurement:procurementrequest-available'
        )
        available_response = api_client.get(available_url)
        assert available_response.status_code == status.HTTP_200_OK
        available_ids = [
            item['id'] for item in available_response.data['results']
        ]
        assert processing_request.id in available_ids

        list_url = reverse('api:v1:procurement:procurementrequest-list')
        list_response = api_client.get(list_url)
        assert list_response.status_code == status.HTTP_200_OK
        list_ids = [item['id'] for item in list_response.data['results']]
        assert processing_request.id in list_ids

    def test_processing_department_scope_uses_executor_department_participants(
        self, api_client, supply_role_user, user, processing_request,
        procurement_item_factory
    ):
        procurement_item_factory(request=processing_request)
        list_url = reverse('api:v1:procurement:procurementrequest-list')

        api_client.force_authenticate(user=supply_role_user)
        processing_response = api_client.get(
            f"{list_url}?scope=processing_department"
        )
        assert processing_response.status_code == status.HTTP_200_OK
        processing_ids = [
            item['id'] for item in processing_response.data['results']
        ]
        assert processing_request.id in processing_ids

        api_client.force_authenticate(user=user)
        department_response = api_client.get(f"{list_url}?scope=department")
        assert department_response.status_code == status.HTTP_200_OK
        department_ids = [
            item['id'] for item in department_response.data['results']
        ]
        assert processing_request.id in department_ids

    def test_processing_permission_flags_follow_executor_department(
        self, api_client, user, supply_user, supply_role_user,
        processing_request, procurement_item_factory
    ):
        procurement_item_factory(request=processing_request)
        detail_url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': processing_request.id},
        )

        api_client.force_authenticate(user=user)
        author_response = api_client.get(detail_url)
        assert author_response.status_code == status.HTTP_200_OK
        assert author_response.data["can_current_user_start_work"] is False
        assert author_response.data["can_current_user_process_items"] is False

        api_client.force_authenticate(user=supply_user)
        supply_response = api_client.get(detail_url)
        assert supply_response.status_code == status.HTTP_200_OK
        assert supply_response.data["can_current_user_start_work"] is True
        assert supply_response.data["can_current_user_process_items"] is True

        api_client.force_authenticate(user=supply_role_user)
        role_response = api_client.get(detail_url)
        assert role_response.status_code == status.HTTP_200_OK
        assert role_response.data["can_current_user_start_work"] is True
        assert role_response.data["can_current_user_process_items"] is True

        processing_request.status = ProcurementStatus.COMPLETED
        processing_request.completed_at = timezone.now()
        processing_request.save(
            update_fields=["status", "completed_at", "updated_at"],
        )

        completed_role_response = api_client.get(detail_url)
        assert completed_role_response.status_code == status.HTTP_200_OK
        assert (
            completed_role_response.data["can_current_user_process_items"]
            is True
        )

    def test_processing_permission_flags_allow_reassignment_for_other_member(
        self, api_client, user, supply_user, supply_replacement_user,
        processing_request, procurement_item_factory
    ):
        procurement_item_factory(request=processing_request)
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.executor = supply_user
        processing_request.started_at = timezone.now()
        processing_request.save(
            update_fields=[
                "status",
                "executor",
                "started_at",
                "updated_at",
            ],
        )
        detail_url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': processing_request.id},
        )

        api_client.force_authenticate(user=supply_user)
        executor_response = api_client.get(detail_url)
        assert executor_response.status_code == status.HTTP_200_OK
        assert executor_response.data["can_current_user_start_work"] is False

        api_client.force_authenticate(user=supply_replacement_user)
        replacement_response = api_client.get(detail_url)
        assert replacement_response.status_code == status.HTTP_200_OK
        assert replacement_response.data["can_current_user_start_work"] is True

        api_client.force_authenticate(user=user)
        author_response = api_client.get(detail_url)
        assert author_response.status_code == status.HTTP_200_OK
        assert author_response.data["can_current_user_start_work"] is False

    def test_outsider_cannot_start_processing_department_request(
        self, api_client, outsider, processing_request, procurement_item_factory
    ):
        procurement_item_factory(request=processing_request)
        api_client.force_authenticate(user=outsider)
        url = reverse(
            'api:v1:procurement:procurementrequest-start-work',
            kwargs={'pk': processing_request.id},
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        processing_request.refresh_from_db()
        assert processing_request.executor is None
        assert processing_request.status == ProcurementStatus.WAITING

    def test_processing_department_user_can_start_work_and_blocks_author_edit(
        self, api_client, user, supply_user, processing_request,
        procurement_item_factory
    ):
        procurement_item_factory(request=processing_request)
        start_url = reverse(
            'api:v1:procurement:procurementrequest-start-work',
            kwargs={'pk': processing_request.id},
        )
        detail_url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': processing_request.id},
        )

        api_client.force_authenticate(user=supply_user)
        start_response = api_client.post(start_url)
        assert start_response.status_code == status.HTTP_200_OK

        processing_request.refresh_from_db()
        assert processing_request.executor == supply_user
        assert processing_request.status == ProcurementStatus.IN_PROGRESS

        api_client.force_authenticate(user=user)
        edit_response = api_client.patch(
            detail_url,
            {'title': 'Нельзя менять'},
            format='json',
        )
        assert edit_response.status_code == status.HTTP_403_FORBIDDEN

    def test_processing_department_role_user_can_start_work(
        self, api_client, supply_role_user, processing_request,
        procurement_item_factory
    ):
        procurement_item_factory(request=processing_request)
        api_client.force_authenticate(user=supply_role_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-start-work',
            kwargs={'pk': processing_request.id},
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        processing_request.refresh_from_db()
        assert processing_request.executor == supply_role_user
        assert processing_request.status == ProcurementStatus.IN_PROGRESS

    def test_processing_department_user_can_reassign_in_progress_request(
        self, api_client, supply_user, supply_replacement_user,
        processing_request, procurement_item_factory
    ):
        procurement_item_factory(request=processing_request)
        previous_started_at = timezone.now()
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.executor = supply_user
        processing_request.started_at = previous_started_at
        processing_request.save(
            update_fields=[
                "status",
                "executor",
                "started_at",
                "updated_at",
            ],
        )
        api_client.force_authenticate(user=supply_replacement_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-start-work',
            kwargs={'pk': processing_request.id},
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        processing_request.refresh_from_db()
        assert processing_request.executor == supply_replacement_user
        assert processing_request.status == ProcurementStatus.IN_PROGRESS
        assert processing_request.started_at > previous_started_at
        assert response.data["executor"] == supply_replacement_user.id
        assert response.data["executor_name"] == (
            supply_replacement_user.get_full_name()
        )

    def test_available_scope_includes_reassignable_processing_request(
        self, api_client, supply_user, supply_replacement_user,
        processing_request, procurement_item_factory
    ):
        procurement_item_factory(request=processing_request)
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.executor = supply_user
        processing_request.started_at = timezone.now()
        processing_request.save(
            update_fields=[
                "status",
                "executor",
                "started_at",
                "updated_at",
            ],
        )
        api_client.force_authenticate(user=supply_replacement_user)
        url = reverse('api:v1:procurement:procurementrequest-list')

        response = api_client.get(f"{url}?scope=available")

        assert response.status_code == status.HTTP_200_OK
        ids = [item['id'] for item in response.data['results']]
        assert processing_request.id in ids

    def test_procurement_execute_permission_can_reassign_addressed_request(
        self, api_client, supply_user, procurement_execute_user,
        processing_request, procurement_item_factory
    ):
        procurement_item_factory(request=processing_request)
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.executor = supply_user
        processing_request.started_at = timezone.now()
        processing_request.save(
            update_fields=[
                "status",
                "executor",
                "started_at",
                "updated_at",
            ],
        )
        api_client.force_authenticate(user=procurement_execute_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-start-work',
            kwargs={'pk': processing_request.id},
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        processing_request.refresh_from_db()
        assert processing_request.executor == procurement_execute_user

    def test_processing_department_role_user_can_reassign_in_progress_request(
        self, api_client, supply_user, supply_role_user,
        processing_request, procurement_item_factory
    ):
        procurement_item_factory(request=processing_request)
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.executor = supply_user
        processing_request.started_at = timezone.now()
        processing_request.save(
            update_fields=[
                "status",
                "executor",
                "started_at",
                "updated_at",
            ],
        )
        api_client.force_authenticate(user=supply_role_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-start-work',
            kwargs={'pk': processing_request.id},
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        processing_request.refresh_from_db()
        assert processing_request.executor == supply_role_user
        assert processing_request.status == ProcurementStatus.IN_PROGRESS

    def test_reassign_in_progress_request_notifies_previous_executor_only(
        self, api_client, user, supply_user, supply_replacement_user,
        processing_request, procurement_item_factory, monkeypatch
    ):
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )

        procurement_item_factory(request=processing_request)
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.executor = supply_user
        processing_request.started_at = timezone.now()
        processing_request.save(
            update_fields=[
                "status",
                "executor",
                "started_at",
                "updated_at",
            ],
        )
        sent.clear()
        api_client.force_authenticate(user=supply_replacement_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-start-work',
            kwargs={'pk': processing_request.id},
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        reassignment_notifications = [
            item for item in sent
            if item["verb"] == "procurement_executor_reassigned"
        ]
        assert len(reassignment_notifications) == 1
        notification = reassignment_notifications[0]
        assert notification["recipient"] == supply_user
        assert notification["sender"] == supply_replacement_user
        assert notification["data"]["title"] == (
            "Заявку забрал другой сотрудник"
        )
        assert notification["description"] == (
            f'{supply_replacement_user.get_full_name()} взял в работу заявку '
            f'"{processing_request.title}".'
        )
        assert user not in [
            item["recipient"] for item in reassignment_notifications
        ]
        assert "procurement_in_progress" not in [
            item["verb"] for item in sent
        ]

    def test_current_executor_cannot_reassign_same_request(
        self, api_client, supply_user, processing_request,
        procurement_item_factory
    ):
        procurement_item_factory(request=processing_request)
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.executor = supply_user
        processing_request.started_at = timezone.now()
        processing_request.save(
            update_fields=[
                "status",
                "executor",
                "started_at",
                "updated_at",
            ],
        )
        api_client.force_authenticate(user=supply_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-start-work',
            kwargs={'pk': processing_request.id},
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        processing_request.refresh_from_db()
        assert processing_request.executor == supply_user

    def test_outsider_cannot_reassign_in_progress_request(
        self, api_client, outsider, supply_user, processing_request,
        procurement_item_factory
    ):
        procurement_item_factory(request=processing_request)
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.executor = supply_user
        processing_request.started_at = timezone.now()
        processing_request.save(
            update_fields=[
                "status",
                "executor",
                "started_at",
                "updated_at",
            ],
        )
        api_client.force_authenticate(user=outsider)
        url = reverse(
            'api:v1:procurement:procurementrequest-start-work',
            kwargs={'pk': processing_request.id},
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_404_NOT_FOUND
        processing_request.refresh_from_db()
        assert processing_request.executor == supply_user

    def test_non_processing_in_progress_request_cannot_be_reassigned(
        self, api_client, user, staff_user, procurement_request,
        procurement_item
    ):
        procurement_request.status = ProcurementStatus.IN_PROGRESS
        procurement_request.executor = staff_user
        procurement_request.started_at = timezone.now()
        procurement_request.save(
            update_fields=[
                "status",
                "executor",
                "started_at",
                "updated_at",
            ],
        )
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-start-work',
            kwargs={'pk': procurement_request.id},
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        procurement_request.refresh_from_db()
        assert procurement_request.executor == staff_user

    def test_processing_department_role_user_can_manage_items(
        self, api_client, supply_role_user, processing_request,
        procurement_item_factory
    ):
        item = procurement_item_factory(
            request=processing_request,
            quantity=2,
        )
        api_client.force_authenticate(user=supply_role_user)
        item_url = reverse(
            'api:v1:procurement:procurementitem-detail',
            kwargs={'pk': item.id},
        )

        update_response = api_client.patch(
            item_url,
            {
                'execution_status': ProcurementItemExecutionStatus.ORDERED,
                'ordered_quantity': 1,
            },
            format='json',
        )

        assert update_response.status_code == status.HTTP_200_OK
        item.refresh_from_db()
        assert item.execution_status == ProcurementItemExecutionStatus.ORDERED
        assert item.ordered_quantity == 1

        mark_all_url = reverse(
            'api:v1:procurement:procurementrequest-mark-all-received',
            kwargs={'pk': processing_request.id},
        )
        mark_all_response = api_client.post(mark_all_url)

        assert mark_all_response.status_code == status.HTTP_200_OK
        item.refresh_from_db()
        assert item.execution_status == ProcurementItemExecutionStatus.RECEIVED
        assert item.received_quantity == item.quantity

    def test_author_can_edit_waiting_request_with_items_before_work(
        self, api_client, user, department, supply_department,
        processing_request, procurement_item_factory
    ):
        kept_item = procurement_item_factory(
            request=processing_request,
            name="Старое название",
            quantity=2,
            unit="шт",
            estimated_unit_price=Decimal("10.00"),
        )
        removed_item = procurement_item_factory(
            request=processing_request,
            name="Удалить",
            quantity=1,
        )
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': processing_request.id},
        )

        response = api_client.patch(
            url,
            {
                "title": "Обновленная закупка",
                "description": "Уточненное описание",
                "department": department.id,
                "processing_department": supply_department.id,
                "urgency": UrgencyLevel.HIGH,
                "items": [
                    {
                        "id": kept_item.id,
                        "name": "Обновленная позиция",
                        "description": "Новые детали",
                        "quantity": 5,
                        "unit": "упак",
                        "estimated_unit_price": "12.50",
                        "supplier_info": "Поставщик",
                        "links": ["https://example.com/updated"],
                    },
                    {
                        "name": "Новая позиция",
                        "description": "",
                        "quantity": 1,
                        "unit": "шт",
                        "estimated_unit_price": None,
                        "supplier_info": "",
                        "links": [],
                        "initial_comment": "Первичный комментарий",
                    },
                ],
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        processing_request.refresh_from_db()
        kept_item.refresh_from_db()
        assert processing_request.title == "Обновленная закупка"
        assert processing_request.description == "Уточненное описание"
        assert processing_request.urgency == UrgencyLevel.HIGH
        assert kept_item.name == "Обновленная позиция"
        assert kept_item.description == "Новые детали"
        assert kept_item.quantity == 5
        assert kept_item.unit == "упак"
        assert kept_item.estimated_unit_price == Decimal("12.50")
        assert kept_item.supplier_info == "Поставщик"
        assert kept_item.links == ["https://example.com/updated"]
        assert not ProcurementItem.objects.filter(id=removed_item.id).exists()

        new_item = processing_request.items.get(name="Новая позиция")
        comments = get_comments(new_item)
        assert len(comments) == 1
        assert comments[0].content == "Первичный комментарий"

    @pytest.fixture
    def department_head_approval_route(self, department_head):
        return ApprovalRoute.objects.create(
            priority=HEAD_PRIORITY,
            resolver_type=ApprovalRoute.ResolverType.DEPARTMENT_HEAD,
        )

    def test_processing_department_user_can_submit_waiting_request_for_approval(
        self, api_client, supply_user, processing_request,
        procurement_item_factory, department_head_approval_route
    ):
        procurement_item_factory(request=processing_request)
        api_client.force_authenticate(user=supply_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': processing_request.id},
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        processing_request.refresh_from_db()
        assert processing_request.status == ProcurementStatus.PENDING
        assert processing_request.processing_department_id is not None
        assert processing_request.approvals.count() == 1
        assert response.data["can_current_user_submit_for_approval"] is False

    def test_processing_department_role_user_can_submit_for_approval(
        self, api_client, supply_role_user, processing_request,
        procurement_item_factory, department_head_approval_route
    ):
        procurement_item_factory(request=processing_request)
        api_client.force_authenticate(user=supply_role_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': processing_request.id},
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        processing_request.refresh_from_db()
        assert processing_request.status == ProcurementStatus.PENDING
        assert processing_request.approvals.count() == 1

    def test_processing_department_requestor_cannot_submit_for_approval(
        self, api_client, user, processing_request,
        procurement_item_factory, department_head_approval_route
    ):
        procurement_item_factory(request=processing_request)
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': processing_request.id},
        )
        options_url = reverse(
            'api:v1:procurement:procurementrequest-approval-options',
            kwargs={'pk': processing_request.id},
        )
        detail_url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': processing_request.id},
        )

        response = api_client.post(url)
        options_response = api_client.get(options_url)
        detail_response = api_client.get(detail_url)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert options_response.status_code == status.HTTP_403_FORBIDDEN
        assert detail_response.status_code == status.HTTP_200_OK
        assert detail_response.data["can_current_user_submit_for_approval"] is False
        processing_request.refresh_from_db()
        assert processing_request.status == ProcurementStatus.WAITING
        assert processing_request.approvals.count() == 0

    def test_customer_department_user_cannot_submit_for_approval(
        self, api_client, department, processing_request,
        procurement_item_factory, department_head_approval_route
    ):
        customer_user = Employee.objects.create_user(
            email="customer-colleague@example.com",
            password="testpass123",
            phone_number="+79998888895",
            first_name="Коллега",
            last_name="Заказчика",
            is_active=True,
            email_verified=True,
            send_activation_email=False,
        )
        EmployeeDepartment.objects.create(
            employee=customer_user,
            department=department,
            is_active=True,
        )
        procurement_item_factory(request=processing_request)
        api_client.force_authenticate(user=customer_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': processing_request.id},
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        processing_request.refresh_from_db()
        assert processing_request.status == ProcurementStatus.WAITING
        assert processing_request.approvals.count() == 0

        detail_url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': processing_request.id},
        )
        detail_response = api_client.get(detail_url)
        assert detail_response.status_code == status.HTTP_200_OK
        assert detail_response.data["can_current_user_submit_for_approval"] is False

    def test_customer_department_user_can_submit_when_processing_department_same(
        self, api_client, supply_department, supply_user,
        procurement_item_factory, department_head_approval_route
    ):
        supply_head = Employee.objects.create_user(
            email="supply-head@example.com",
            password="testpass123",
            phone_number="+79998888896",
            first_name="Руководитель",
            last_name="Снабжения",
            is_active=True,
            email_verified=True,
            send_activation_email=False,
        )
        supply_department.head = supply_head
        supply_department.save(update_fields=["head"])

        requestor = Employee.objects.create_user(
            email="same-department-requestor@example.com",
            password="testpass123",
            phone_number="+79998888897",
            first_name="Автор",
            last_name="Снабжения",
            is_active=True,
            email_verified=True,
            send_activation_email=False,
        )
        EmployeeDepartment.objects.create(
            employee=requestor,
            department=supply_department,
            is_active=True,
        )
        procurement_request = ProcurementRequest.objects.create(
            title="Внутренняя заявка снабжения",
            description="Заказчик и исполнитель совпадают",
            department=supply_department,
            processing_department=supply_department,
            requestor=requestor,
            status=ProcurementStatus.WAITING,
            urgency=UrgencyLevel.MEDIUM,
        )
        procurement_item_factory(request=procurement_request)
        detail_url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': procurement_request.id},
        )
        options_url = reverse(
            'api:v1:procurement:procurementrequest-approval-options',
            kwargs={'pk': procurement_request.id},
        )
        submit_url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': procurement_request.id},
        )

        api_client.force_authenticate(user=requestor)
        requestor_detail = api_client.get(detail_url)
        requestor_submit = api_client.post(submit_url)
        assert requestor_detail.status_code == status.HTTP_200_OK
        assert requestor_detail.data["can_current_user_submit_for_approval"] is False
        assert requestor_submit.status_code == status.HTTP_403_FORBIDDEN

        api_client.force_authenticate(user=supply_user)
        submitter_detail = api_client.get(detail_url)
        options_response = api_client.get(options_url)
        submit_response = api_client.post(submit_url)

        assert submitter_detail.status_code == status.HTTP_200_OK
        assert submitter_detail.data["can_current_user_submit_for_approval"] is True
        assert options_response.status_code == status.HTTP_200_OK
        assert submit_response.status_code == status.HTTP_200_OK
        procurement_request.refresh_from_db()
        assert procurement_request.status == ProcurementStatus.PENDING
        assert procurement_request.approvals.count() == 1

    def test_requestor_in_processing_department_cannot_submit_for_approval(
        self, api_client, user, supply_department, processing_request,
        procurement_item_factory, department_head_approval_route
    ):
        EmployeeDepartment.objects.create(
            employee=user,
            department=supply_department,
            is_active=True,
        )
        procurement_item_factory(request=processing_request)
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': processing_request.id},
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        processing_request.refresh_from_db()
        assert processing_request.status == ProcurementStatus.WAITING
        assert processing_request.approvals.count() == 0

    def test_execute_permission_user_outside_processing_department_cannot_submit(
        self, api_client, procurement_execute_user, processing_request,
        procurement_item_factory, department_head_approval_route
    ):
        procurement_item_factory(request=processing_request)
        api_client.force_authenticate(user=procurement_execute_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': processing_request.id},
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        processing_request.refresh_from_db()
        assert processing_request.status == ProcurementStatus.WAITING
        assert processing_request.approvals.count() == 0

    def test_request_without_processing_department_cannot_be_submitted(
        self, api_client, user, procurement_request, procurement_item,
        department_head_approval_route
    ):
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': procurement_request.id},
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        procurement_request.refresh_from_db()
        assert procurement_request.status == ProcurementStatus.DRAFT
        assert procurement_request.approvals.count() == 0

    def test_processing_department_request_cannot_be_submitted_twice_while_pending(
        self, api_client, supply_user, processing_request,
        procurement_item_factory, department_head_approval_route
    ):
        procurement_item_factory(request=processing_request)
        processing_request.status = ProcurementStatus.PENDING
        processing_request.save(update_fields=["status", "updated_at"])
        Approval.objects.create(
            request=processing_request,
            approver=processing_request.department.head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.PENDING,
        )

        api_client.force_authenticate(user=supply_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': processing_request.id},
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_approved_processing_request_cannot_be_submitted_again(
        self, api_client, supply_user, processing_request,
        procurement_item_factory, department_head_approval_route
    ):
        """После пройденного согласования кнопку submit больше не показываем."""
        procurement_item_factory(request=processing_request)
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.save(update_fields=["executor", "status", "updated_at"])
        Approval.objects.create(
            request=processing_request,
            approver=processing_request.department.head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.APPROVED,
        )

        api_client.force_authenticate(user=supply_user)
        detail_url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': processing_request.id},
        )
        submit_url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': processing_request.id},
        )

        detail_response = api_client.get(detail_url)
        assert detail_response.status_code == status.HTTP_200_OK
        assert detail_response.data["can_current_user_submit_for_approval"] is False

        submit_response = api_client.post(submit_url)
        assert submit_response.status_code == status.HTTP_403_FORBIDDEN

    def test_final_approve_returns_processing_request_to_waiting_without_executor(
        self, api_client, supply_user, department_head, processing_request,
        procurement_item_factory, department_head_approval_route
    ):
        procurement_item_factory(request=processing_request)
        submit_url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': processing_request.id},
        )
        approve_url = reverse(
            'api:v1:procurement:procurementrequest-approve',
            kwargs={'pk': processing_request.id},
        )

        api_client.force_authenticate(user=supply_user)
        submit_response = api_client.post(submit_url)
        assert submit_response.status_code == status.HTTP_200_OK

        api_client.force_authenticate(user=department_head)
        approve_response = api_client.post(approve_url, {'comment': 'Можно'})

        assert approve_response.status_code == status.HTTP_200_OK
        processing_request.refresh_from_db()
        assert processing_request.status == ProcurementStatus.WAITING
        assert processing_request.executor is None
        assert processing_request.processing_department is not None

    def test_final_approve_returns_processing_request_to_executor_work(
        self, api_client, supply_user, department_head, processing_request,
        procurement_item_factory, department_head_approval_route
    ):
        procurement_item_factory(request=processing_request)
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.started_at = timezone.now()
        processing_request.save(
            update_fields=[
                "executor",
                "status",
                "started_at",
                "updated_at",
            ]
        )
        submit_url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': processing_request.id},
        )
        approve_url = reverse(
            'api:v1:procurement:procurementrequest-approve',
            kwargs={'pk': processing_request.id},
        )

        api_client.force_authenticate(user=supply_user)
        submit_response = api_client.post(submit_url)
        assert submit_response.status_code == status.HTTP_200_OK

        api_client.force_authenticate(user=department_head)
        approve_response = api_client.post(approve_url, {'comment': 'Можно'})

        assert approve_response.status_code == status.HTTP_200_OK
        processing_request.refresh_from_db()
        assert processing_request.status == ProcurementStatus.IN_PROGRESS
        assert processing_request.executor == supply_user
        assert processing_request.processing_department is not None

    def test_reject_processing_request_stops_purchase(
        self, api_client, supply_user, department_head, processing_request,
        procurement_item_factory, department_head_approval_route
    ):
        procurement_item_factory(request=processing_request)
        submit_url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': processing_request.id},
        )
        reject_url = reverse(
            'api:v1:procurement:procurementrequest-reject',
            kwargs={'pk': processing_request.id},
        )

        api_client.force_authenticate(user=supply_user)
        submit_response = api_client.post(submit_url)
        assert submit_response.status_code == status.HTTP_200_OK

        api_client.force_authenticate(user=department_head)
        reject_response = api_client.post(reject_url, {'comment': 'Нельзя'})

        assert reject_response.status_code == status.HTTP_200_OK
        processing_request.refresh_from_db()
        assert processing_request.status == ProcurementStatus.REJECTED

    def test_pending_processing_request_blocks_execution_actions(
        self, api_client, supply_user, processing_request,
        procurement_item_factory, department_head_approval_route
    ):
        item = procurement_item_factory(request=processing_request)
        processing_request.status = ProcurementStatus.PENDING
        processing_request.save(update_fields=["status", "updated_at"])
        Approval.objects.create(
            request=processing_request,
            approver=processing_request.department.head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.PENDING,
        )
        api_client.force_authenticate(user=supply_user)

        item_url = reverse(
            'api:v1:procurement:procurementitem-detail',
            kwargs={'pk': item.id},
        )
        report_issue_url = reverse(
            'api:v1:procurement:procurementitem-report-issue',
            kwargs={'pk': item.id},
        )
        confirm_received_url = reverse(
            'api:v1:procurement:procurementitem-confirm-received',
            kwargs={'pk': item.id},
        )
        cancel_received_url = reverse(
            'api:v1:procurement:procurementitem-cancel-received',
            kwargs={'pk': item.id},
        )
        mark_all_url = reverse(
            'api:v1:procurement:procurementrequest-mark-all-received',
            kwargs={'pk': processing_request.id},
        )
        complete_url = reverse(
            'api:v1:procurement:procurementrequest-complete',
            kwargs={'pk': processing_request.id},
        )
        start_url = reverse(
            'api:v1:procurement:procurementrequest-start-work',
            kwargs={'pk': processing_request.id},
        )

        item_response = api_client.patch(
            item_url,
            {'execution_status': ProcurementItemExecutionStatus.RECEIVED},
            format='json',
        )
        issue_response = api_client.post(
            report_issue_url,
            {'text': 'Брак'},
            format='json',
        )
        confirm_received_response = api_client.post(confirm_received_url)
        cancel_received_response = api_client.post(cancel_received_url)
        mark_all_response = api_client.post(mark_all_url)
        complete_response = api_client.post(complete_url)
        start_response = api_client.post(start_url)

        assert item_response.status_code == status.HTTP_403_FORBIDDEN
        assert issue_response.status_code == status.HTTP_400_BAD_REQUEST
        assert confirm_received_response.status_code == status.HTTP_400_BAD_REQUEST
        assert cancel_received_response.status_code == status.HTTP_400_BAD_REQUEST
        assert mark_all_response.status_code == status.HTTP_400_BAD_REQUEST
        assert complete_response.status_code == status.HTTP_403_FORBIDDEN
        assert start_response.status_code == status.HTTP_400_BAD_REQUEST

    def test_item_status_recalculates_request_fulfillment_status(
        self, api_client, supply_user, processing_request,
        procurement_item_factory
    ):
        item = procurement_item_factory(request=processing_request)
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.save()

        api_client.force_authenticate(user=supply_user)
        item_url = reverse(
            'api:v1:procurement:procurementitem-detail',
            kwargs={'pk': item.id},
        )

        response = api_client.patch(
            item_url,
            {'execution_status': ProcurementItemExecutionStatus.RECEIVED},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        processing_request.refresh_from_db()
        assert (
            processing_request.fulfillment_status
            == ProcurementFulfillmentStatus.COMPLETED
        )
        assert processing_request.status == ProcurementStatus.COMPLETED
        assert processing_request.completed_at is not None
        item.refresh_from_db()
        assert item.ordered_quantity == item.quantity
        assert item.received_quantity == item.quantity

    def test_item_auto_completion_notification_uses_executor_actor(
        self, api_client, supply_user, processing_request,
        procurement_item_factory, monkeypatch
    ):
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )

        item = procurement_item_factory(request=processing_request)
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.save()
        sent.clear()

        api_client.force_authenticate(user=supply_user)
        item_url = reverse(
            'api:v1:procurement:procurementitem-detail',
            kwargs={'pk': item.id},
        )

        response = api_client.patch(
            item_url,
            {'received_quantity': item.quantity},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        completed_notifications = [
            item for item in sent
            if item["verb"] == "procurement_completed"
        ]
        assert len(completed_notifications) == 1
        assert completed_notifications[0]["sender"] == supply_user
        assert completed_notifications[0]["data"]["actor_id"] == supply_user.id

    def test_item_update_does_not_notify_requestor(
        self, api_client, supply_user, processing_request,
        procurement_item_factory, monkeypatch
    ):
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )

        item = procurement_item_factory(request=processing_request)
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.save()
        sent.clear()

        api_client.force_authenticate(user=supply_user)
        item_url = reverse(
            'api:v1:procurement:procurementitem-detail',
            kwargs={'pk': item.id},
        )

        response = api_client.patch(
            item_url,
            {
                'execution_status': ProcurementItemExecutionStatus.ORDERED,
                'actual_unit_price': '120.00',
                'expected_delivery_dates': ['2026-05-25', '2026-05-29'],
                'links': ['https://example.com/item'],
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["expected_delivery_dates"] == ["2026-05-25", "2026-05-29"]
        assert "expected_delivery_date" not in response.data
        item_notifications = [
            item for item in sent
            if item["verb"] == "procurement_item_updated"
        ]
        assert item_notifications == []

    @pytest.mark.django_db(transaction=True)
    def test_item_order_update_does_not_route_push_to_requestor(
        self, api_client, supply_user, processing_request,
        procurement_item_factory
    ):
        item = procurement_item_factory(
            request=processing_request,
            quantity=3,
        )
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.save()
        UserChannelPreferences.objects.update_or_create(
            user=processing_request.requestor,
            defaults={
                "web_enabled": False,
                "email_enabled": False,
                "push_enabled": True,
                "disabled_verbs": [],
            },
        )
        WebPushDevice.objects.create(
            user=processing_request.requestor,
            registration_id="https://push.example.test/procurement-item",
            p256dh="test-p256dh",
            auth="test-auth",
            browser="Chrome",
            active=True,
        )

        api_client.force_authenticate(user=supply_user)
        item_url = reverse(
            'api:v1:procurement:procurementitem-detail',
            kwargs={'pk': item.id},
        )

        with patch(
            "notifications.tasks.send_push_notification.delay"
        ) as send_push:
            response = api_client.patch(
                item_url,
                {"ordered_quantity": 2},
                format="json",
            )

        assert response.status_code == status.HTTP_200_OK
        assert not Notification.objects.filter(
            recipient=processing_request.requestor,
            verb="procurement_item_updated",
            data__item_id=item.id,
        ).exists()
        send_push.assert_not_called()

    def test_item_expected_delivery_dates_must_be_valid_dates(
        self, api_client, supply_user, processing_request,
        procurement_item_factory
    ):
        item = procurement_item_factory(request=processing_request)
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.save()

        api_client.force_authenticate(user=supply_user)
        item_url = reverse(
            'api:v1:procurement:procurementitem-detail',
            kwargs={'pk': item.id},
        )

        response = api_client.patch(
            item_url,
            {'expected_delivery_dates': ['2026-02-31']},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_item_expected_delivery_dates_accepts_empty_list(
        self, api_client, supply_user, processing_request,
        procurement_item_factory
    ):
        item = procurement_item_factory(
            request=processing_request,
            expected_delivery_dates=["2026-05-25"],
        )
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.save()

        api_client.force_authenticate(user=supply_user)
        item_url = reverse(
            'api:v1:procurement:procurementitem-detail',
            kwargs={'pk': item.id},
        )

        response = api_client.patch(
            item_url,
            {'expected_delivery_dates': []},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert response.data["expected_delivery_dates"] == []
        item.refresh_from_db()
        assert item.expected_delivery_dates == []

    def test_item_quantities_cannot_exceed_requested_quantity(
        self, api_client, supply_user, processing_request,
        procurement_item_factory
    ):
        item = procurement_item_factory(
            request=processing_request,
            quantity=3,
        )
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.save()

        api_client.force_authenticate(user=supply_user)
        item_url = reverse(
            'api:v1:procurement:procurementitem-detail',
            kwargs={'pk': item.id},
        )

        response = api_client.patch(
            item_url,
            {'ordered_quantity': 4},
            format='json',
        )

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "ordered_quantity" in response.data

    def test_ordered_quantity_moves_pending_item_to_ordered(
        self, api_client, supply_user, processing_request,
        procurement_item_factory
    ):
        item = procurement_item_factory(
            request=processing_request,
            quantity=3,
            execution_status=ProcurementItemExecutionStatus.PENDING,
        )
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.save()

        api_client.force_authenticate(user=supply_user)
        item_url = reverse(
            'api:v1:procurement:procurementitem-detail',
            kwargs={'pk': item.id},
        )

        response = api_client.patch(
            item_url,
            {'ordered_quantity': 2},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        item.refresh_from_db()
        assert item.ordered_quantity == 2
        assert item.execution_status == ProcurementItemExecutionStatus.ORDERED

    def test_partial_quantities_drive_item_display_and_request_fulfillment(
        self, api_client, supply_user, processing_request,
        procurement_item_factory
    ):
        item = procurement_item_factory(
            request=processing_request,
            quantity=4,
            execution_status=ProcurementItemExecutionStatus.PENDING,
        )
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.save()

        api_client.force_authenticate(user=supply_user)
        item_url = reverse(
            'api:v1:procurement:procurementitem-detail',
            kwargs={'pk': item.id},
        )

        partial_ordered_response = api_client.patch(
            item_url,
            {'ordered_quantity': 1},
            format='json',
        )

        assert partial_ordered_response.status_code == status.HTTP_200_OK
        assert (
            partial_ordered_response.data["execution_status_display"]
            == "Заказано частично"
        )
        processing_request.refresh_from_db()
        assert (
            processing_request.fulfillment_status
            == ProcurementFulfillmentStatus.PARTIALLY_ORDERED
        )
        assert processing_request.status == ProcurementStatus.IN_PROGRESS

        ordered_response = api_client.patch(
            item_url,
            {'ordered_quantity': 4},
            format='json',
        )

        assert ordered_response.status_code == status.HTTP_200_OK
        assert ordered_response.data["execution_status_display"] == "Заказано"
        processing_request.refresh_from_db()
        assert (
            processing_request.fulfillment_status
            == ProcurementFulfillmentStatus.ORDERED
        )
        assert processing_request.status == ProcurementStatus.IN_PROGRESS

        partial_received_response = api_client.patch(
            item_url,
            {'received_quantity': 2},
            format='json',
        )

        assert partial_received_response.status_code == status.HTTP_200_OK
        assert (
            partial_received_response.data["execution_status_display"]
            == "Получено частично"
        )
        processing_request.refresh_from_db()
        assert (
            processing_request.fulfillment_status
            == ProcurementFulfillmentStatus.PARTIALLY_RECEIVED
        )
        assert processing_request.status == ProcurementStatus.IN_PROGRESS

        received_response = api_client.patch(
            item_url,
            {'received_quantity': 4},
            format='json',
        )

        assert received_response.status_code == status.HTTP_200_OK
        assert received_response.data["execution_status_display"] == "Получено"
        processing_request.refresh_from_db()
        assert (
            processing_request.fulfillment_status
            == ProcurementFulfillmentStatus.COMPLETED
        )
        assert processing_request.status == ProcurementStatus.COMPLETED
        assert processing_request.completed_at is not None

    def test_received_quantity_sets_ordered_or_received_status(
        self, api_client, supply_user, processing_request,
        procurement_item_factory
    ):
        item = procurement_item_factory(
            request=processing_request,
            quantity=3,
            execution_status=ProcurementItemExecutionStatus.PENDING,
        )
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.save()

        api_client.force_authenticate(user=supply_user)
        item_url = reverse(
            'api:v1:procurement:procurementitem-detail',
            kwargs={'pk': item.id},
        )

        partial_response = api_client.patch(
            item_url,
            {'received_quantity': 2},
            format='json',
        )

        assert partial_response.status_code == status.HTTP_200_OK
        item.refresh_from_db()
        assert item.ordered_quantity == 2
        assert item.received_quantity == 2
        assert item.execution_status == ProcurementItemExecutionStatus.ORDERED

        full_response = api_client.patch(
            item_url,
            {'received_quantity': 3},
            format='json',
        )

        assert full_response.status_code == status.HTTP_200_OK
        item.refresh_from_db()
        assert item.ordered_quantity == 3
        assert item.received_quantity == 3
        assert item.execution_status == ProcurementItemExecutionStatus.RECEIVED

    def test_zero_received_quantity_returns_received_item_to_workflow(
        self, api_client, supply_user, processing_request,
        procurement_item_factory
    ):
        item = procurement_item_factory(
            request=processing_request,
            quantity=3,
            ordered_quantity=2,
            received_quantity=3,
            execution_status=ProcurementItemExecutionStatus.RECEIVED,
        )
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.save()

        api_client.force_authenticate(user=supply_user)
        item_url = reverse(
            'api:v1:procurement:procurementitem-detail',
            kwargs={'pk': item.id},
        )

        ordered_response = api_client.patch(
            item_url,
            {'received_quantity': 0},
            format='json',
        )

        assert ordered_response.status_code == status.HTTP_200_OK
        item.refresh_from_db()
        assert item.received_quantity == 0
        assert item.execution_status == ProcurementItemExecutionStatus.ORDERED

        pending_response = api_client.patch(
            item_url,
            {'ordered_quantity': 0},
            format='json',
        )

        assert pending_response.status_code == status.HTTP_200_OK
        item.refresh_from_db()
        assert item.ordered_quantity == 0
        assert item.execution_status == ProcurementItemExecutionStatus.PENDING

    def test_report_issue_marks_item_defective_and_reopens_completed_request(
        self, api_client, user, supply_user, processing_request,
        procurement_item_factory, monkeypatch
    ):
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )

        item = procurement_item_factory(
            request=processing_request,
            execution_status=ProcurementItemExecutionStatus.RECEIVED,
            received_quantity=1,
        )
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.COMPLETED
        processing_request.completed_at = timezone.now()
        processing_request.save()
        sent.clear()

        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementitem-report-issue',
            kwargs={'pk': item.id},
        )

        response = api_client.post(
            url,
            {'text': 'Обнаружен брак'},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        item.refresh_from_db()
        processing_request.refresh_from_db()
        assert item.execution_status == ProcurementItemExecutionStatus.DEFECTIVE
        assert (
            processing_request.fulfillment_status
            == ProcurementFulfillmentStatus.ISSUES
        )
        assert processing_request.status == ProcurementStatus.IN_PROGRESS
        assert processing_request.completed_at is None
        assert [comment.content for comment in get_comments(item)] == [
            "Обнаружен брак"
        ]

        api_client.force_authenticate(user=supply_user)
        my_work_url = reverse(
            'api:v1:procurement:procurementrequest-list'
        )
        my_work_response = api_client.get(
            my_work_url,
            {'scope': 'my_work'},
        )
        assert my_work_response.status_code == status.HTTP_200_OK
        my_work_item = next(
            item for item in my_work_response.data["results"]
            if item["id"] == processing_request.id
        )
        assert my_work_item["status"] == ProcurementStatus.IN_PROGRESS

        issue_recipients = [
            notification["recipient"].email
            for notification in sent
            if notification["verb"] == "procurement_item_updated"
        ]
        assert supply_user.email in issue_recipients

    def test_executor_issue_reopens_request_for_requestor_without_status_spam(
        self, api_client, user, supply_user, processing_request,
        procurement_item_factory, monkeypatch
    ):
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )

        item = procurement_item_factory(
            request=processing_request,
            execution_status=ProcurementItemExecutionStatus.RECEIVED,
            ordered_quantity=1,
            received_quantity=1,
        )
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.COMPLETED
        processing_request.completed_at = timezone.now()
        processing_request.fulfillment_status = (
            ProcurementFulfillmentStatus.COMPLETED
        )
        processing_request.save()
        sent.clear()

        api_client.force_authenticate(user=supply_user)
        url = reverse(
            'api:v1:procurement:procurementitem-report-issue',
            kwargs={'pk': item.id},
        )

        response = api_client.post(url, {'text': 'Брак'}, format='json')

        assert response.status_code == status.HTTP_200_OK
        item.refresh_from_db()
        processing_request.refresh_from_db()
        assert item.execution_status == ProcurementItemExecutionStatus.DEFECTIVE
        assert processing_request.status == ProcurementStatus.IN_PROGRESS
        assert processing_request.completed_at is None

        api_client.force_authenticate(user=user)
        mine_url = reverse('api:v1:procurement:procurementrequest-list')
        mine_response = api_client.get(mine_url, {'scope': 'mine'})
        assert mine_response.status_code == status.HTTP_200_OK
        mine_item = next(
            item for item in mine_response.data["results"]
            if item["id"] == processing_request.id
        )
        assert mine_item["status"] == ProcurementStatus.IN_PROGRESS

        item_updated_recipients = [
            notification["recipient"].email
            for notification in sent
            if notification["verb"] == "procurement_item_updated"
        ]
        in_progress_recipients = [
            notification["recipient"].email
            for notification in sent
            if notification["verb"] == "procurement_in_progress"
        ]
        assert user.email not in item_updated_recipients
        assert user.email not in in_progress_recipients

    def test_requestor_can_confirm_item_received(
        self, api_client, user, supply_user, processing_request,
        procurement_item_factory
    ):
        item = procurement_item_factory(
            request=processing_request,
            quantity=2,
            ordered_quantity=1,
            received_quantity=0,
            execution_status=ProcurementItemExecutionStatus.ORDERED,
        )
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.save()

        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementitem-confirm-received',
            kwargs={'pk': item.id},
        )

        response = api_client.post(url, {}, format='json')

        assert response.status_code == status.HTTP_200_OK
        item.refresh_from_db()
        processing_request.refresh_from_db()
        assert item.execution_status == ProcurementItemExecutionStatus.RECEIVED
        assert item.ordered_quantity == item.quantity
        assert item.received_quantity == item.quantity
        assert (
            processing_request.fulfillment_status
            == ProcurementFulfillmentStatus.COMPLETED
        )
        assert processing_request.status == ProcurementStatus.COMPLETED
        assert processing_request.completed_at is not None

    def test_requestor_can_confirm_partial_item_received(
        self, api_client, user, supply_user, processing_request,
        procurement_item_factory
    ):
        item = procurement_item_factory(
            request=processing_request,
            quantity=3,
            ordered_quantity=3,
            received_quantity=0,
            execution_status=ProcurementItemExecutionStatus.ORDERED,
        )
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.save()

        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementitem-confirm-received',
            kwargs={'pk': item.id},
        )

        response = api_client.post(
            url,
            {'received_quantity': 2},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        item.refresh_from_db()
        processing_request.refresh_from_db()
        assert item.execution_status == ProcurementItemExecutionStatus.ORDERED
        assert item.ordered_quantity == 3
        assert item.received_quantity == 2
        assert (
            processing_request.fulfillment_status
            == ProcurementFulfillmentStatus.PARTIALLY_RECEIVED
        )
        assert processing_request.status == ProcurementStatus.IN_PROGRESS
        assert processing_request.completed_at is None

    def test_confirm_item_received_rejects_invalid_quantity(
        self, api_client, user, supply_user, processing_request,
        procurement_item_factory
    ):
        item = procurement_item_factory(
            request=processing_request,
            quantity=2,
            ordered_quantity=2,
            received_quantity=1,
            execution_status=ProcurementItemExecutionStatus.ORDERED,
        )
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.save()

        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementitem-confirm-received',
            kwargs={'pk': item.id},
        )

        too_low_response = api_client.post(
            url,
            {'received_quantity': 1},
            format='json',
        )
        too_high_response = api_client.post(
            url,
            {'received_quantity': 3},
            format='json',
        )

        assert too_low_response.status_code == status.HTTP_400_BAD_REQUEST
        assert too_high_response.status_code == status.HTTP_400_BAD_REQUEST
        item.refresh_from_db()
        assert item.received_quantity == 1

    def test_requestor_can_cancel_item_issue(
        self, api_client, user, supply_user, processing_request,
        procurement_item_factory
    ):
        item = procurement_item_factory(
            request=processing_request,
            quantity=1,
            ordered_quantity=1,
            received_quantity=1,
            execution_status=ProcurementItemExecutionStatus.DEFECTIVE,
        )
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.fulfillment_status = ProcurementFulfillmentStatus.ISSUES
        processing_request.save()

        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementitem-cancel-issue',
            kwargs={'pk': item.id},
        )

        response = api_client.post(url, {}, format='json')

        assert response.status_code == status.HTTP_200_OK
        item.refresh_from_db()
        processing_request.refresh_from_db()
        assert item.execution_status == ProcurementItemExecutionStatus.RECEIVED
        assert (
            processing_request.fulfillment_status
            == ProcurementFulfillmentStatus.COMPLETED
        )
        assert processing_request.status == ProcurementStatus.COMPLETED

    def test_requestor_can_cancel_item_received_and_reopens_completed_request(
        self, api_client, user, supply_user, processing_request,
        procurement_item_factory
    ):
        item = procurement_item_factory(
            request=processing_request,
            quantity=2,
            ordered_quantity=2,
            received_quantity=2,
            execution_status=ProcurementItemExecutionStatus.RECEIVED,
        )
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.COMPLETED
        processing_request.completed_at = timezone.now()
        processing_request.fulfillment_status = ProcurementFulfillmentStatus.COMPLETED
        processing_request.save()

        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementitem-cancel-received',
            kwargs={'pk': item.id},
        )

        response = api_client.post(url, {}, format='json')

        assert response.status_code == status.HTTP_200_OK
        item.refresh_from_db()
        processing_request.refresh_from_db()
        assert item.execution_status == ProcurementItemExecutionStatus.ORDERED
        assert item.ordered_quantity == item.quantity
        assert item.received_quantity == 0
        assert (
            processing_request.fulfillment_status
            == ProcurementFulfillmentStatus.ORDERED
        )
        assert processing_request.status == ProcurementStatus.IN_PROGRESS
        assert processing_request.completed_at is None

    def test_requestor_can_cancel_partial_item_received(
        self, api_client, user, supply_user, processing_request,
        procurement_item_factory
    ):
        item = procurement_item_factory(
            request=processing_request,
            quantity=4,
            ordered_quantity=4,
            received_quantity=3,
            execution_status=ProcurementItemExecutionStatus.ORDERED,
        )
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.save()

        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementitem-cancel-received',
            kwargs={'pk': item.id},
        )

        response = api_client.post(
            url,
            {'cancel_quantity': 1},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        item.refresh_from_db()
        processing_request.refresh_from_db()
        assert item.execution_status == ProcurementItemExecutionStatus.ORDERED
        assert item.ordered_quantity == 4
        assert item.received_quantity == 2
        assert (
            processing_request.fulfillment_status
            == ProcurementFulfillmentStatus.PARTIALLY_RECEIVED
        )
        assert processing_request.status == ProcurementStatus.IN_PROGRESS

    def test_cancel_item_received_rejects_invalid_quantity(
        self, api_client, user, supply_user, processing_request,
        procurement_item_factory
    ):
        item = procurement_item_factory(
            request=processing_request,
            quantity=2,
            ordered_quantity=2,
            received_quantity=1,
            execution_status=ProcurementItemExecutionStatus.ORDERED,
        )
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.save()

        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementitem-cancel-received',
            kwargs={'pk': item.id},
        )

        too_low_response = api_client.post(
            url,
            {'cancel_quantity': 0},
            format='json',
        )
        too_high_response = api_client.post(
            url,
            {'cancel_quantity': 2},
            format='json',
        )

        assert too_low_response.status_code == status.HTTP_400_BAD_REQUEST
        assert too_high_response.status_code == status.HTTP_400_BAD_REQUEST
        item.refresh_from_db()
        assert item.received_quantity == 1

    def test_cancel_received_uses_received_status_as_effective_quantity(
        self, api_client, user, supply_user, processing_request,
        procurement_item_factory
    ):
        item = procurement_item_factory(
            request=processing_request,
            quantity=2,
            ordered_quantity=2,
            received_quantity=2,
            execution_status=ProcurementItemExecutionStatus.RECEIVED,
        )
        ProcurementItem.objects.filter(pk=item.pk).update(
            ordered_quantity=None,
            received_quantity=None,
            execution_status=ProcurementItemExecutionStatus.RECEIVED,
        )
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.COMPLETED
        processing_request.completed_at = timezone.now()
        processing_request.fulfillment_status = (
            ProcurementFulfillmentStatus.COMPLETED
        )
        processing_request.save()

        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementitem-cancel-received',
            kwargs={'pk': item.id},
        )

        response = api_client.post(url, {}, format='json')

        assert response.status_code == status.HTTP_200_OK
        item.refresh_from_db()
        processing_request.refresh_from_db()
        assert item.execution_status == ProcurementItemExecutionStatus.ORDERED
        assert item.ordered_quantity == item.quantity
        assert item.received_quantity == 0
        assert processing_request.status == ProcurementStatus.IN_PROGRESS
        assert processing_request.completed_at is None

    def test_outsider_cannot_confirm_item_received(
        self, api_client, outsider, processing_request,
        procurement_item_factory
    ):
        item = procurement_item_factory(
            request=processing_request,
            execution_status=ProcurementItemExecutionStatus.ORDERED,
            ordered_quantity=1,
        )

        api_client.force_authenticate(user=outsider)
        url = reverse(
            'api:v1:procurement:procurementitem-confirm-received',
            kwargs={'pk': item.id},
        )

        response = api_client.post(url, {}, format='json')

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_list_exposes_procurement_progress_summary(
        self, api_client, supply_user, processing_request,
        procurement_item_factory
    ):
        procurement_item_factory(
            request=processing_request,
            quantity=5,
            execution_status=ProcurementItemExecutionStatus.RECEIVED,
            ordered_quantity=5,
            received_quantity=3,
            expected_delivery_dates=["2026-05-28"],
        )
        procurement_item_factory(
            request=processing_request,
            name="Проблемная позиция",
            quantity=2,
            execution_status=ProcurementItemExecutionStatus.DEFECTIVE,
            ordered_quantity=1,
            expected_delivery_dates=["2026-05-31", "2026-05-27"],
        )
        procurement_item_factory(
            request=processing_request,
            name="Не обработано",
            quantity=4,
            execution_status=ProcurementItemExecutionStatus.PENDING,
        )

        api_client.force_authenticate(user=supply_user)
        url = reverse('api:v1:procurement:procurementrequest-list')

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        result = next(
            item for item in response.data["results"]
            if item["id"] == processing_request.id
        )
        assert result["next_expected_delivery_date"] == "2026-05-27"
        assert result["items_total_count"] == 3
        assert result["items_received_count"] == 0
        assert result["items_problem_count"] == 1
        assert result["items_pending_count"] == 1
        assert result["total_requested_quantity"] == 11
        assert result["total_ordered_quantity"] == 6
        assert result["total_received_quantity"] == 3

    def test_list_expected_date_falls_back_to_latest_when_all_received(
        self, api_client, supply_user, processing_request,
        procurement_item_factory
    ):
        procurement_item_factory(
            request=processing_request,
            quantity=1,
            execution_status=ProcurementItemExecutionStatus.RECEIVED,
            ordered_quantity=1,
            received_quantity=1,
            expected_delivery_dates=["2026-05-28"],
        )
        procurement_item_factory(
            request=processing_request,
            name="Вторая полученная позиция",
            quantity=1,
            execution_status=ProcurementItemExecutionStatus.RECEIVED,
            ordered_quantity=1,
            received_quantity=1,
            expected_delivery_dates=["2026-05-30", "2026-06-01"],
        )
        api_client.force_authenticate(user=supply_user)
        url = reverse('api:v1:procurement:procurementrequest-list')

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        result = next(
            item for item in response.data["results"]
            if item["id"] == processing_request.id
        )
        assert result["next_expected_delivery_date"] == "2026-06-01"

    def test_list_expected_date_is_null_when_pending_items_have_no_dates(
        self, api_client, supply_user, processing_request,
        procurement_item_factory
    ):
        procurement_item_factory(
            request=processing_request,
            quantity=1,
            execution_status=ProcurementItemExecutionStatus.RECEIVED,
            ordered_quantity=1,
            received_quantity=1,
            expected_delivery_dates=["2026-05-28"],
        )
        procurement_item_factory(
            request=processing_request,
            name="Без ожидаемой даты",
            quantity=1,
            execution_status=ProcurementItemExecutionStatus.PENDING,
        )
        api_client.force_authenticate(user=supply_user)
        url = reverse('api:v1:procurement:procurementrequest-list')

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        result = next(
            item for item in response.data["results"]
            if item["id"] == processing_request.id
        )
        assert result["next_expected_delivery_date"] is None

    def test_requestor_item_update_does_not_notify_self(
        self, api_client, user, processing_request,
        procurement_item_factory, monkeypatch
    ):
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )

        item = procurement_item_factory(request=processing_request)

        api_client.force_authenticate(user=user)
        item_url = reverse(
            'api:v1:procurement:procurementitem-detail',
            kwargs={'pk': item.id},
        )

        response = api_client.patch(
            item_url,
            {'name': 'Перчатки нитриловые'},
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        assert [
            item for item in sent
            if item["verb"] == "procurement_item_updated"
        ] == []

    def test_request_comment_notifies_requestor(
        self, api_client, supply_user, processing_request, monkeypatch
    ):
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )

        api_client.force_authenticate(user=supply_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-comments',
            kwargs={'pk': processing_request.id},
        )

        response = api_client.post(url, {'text': 'Взяли в анализ'})

        assert response.status_code == status.HTTP_201_CREATED
        comment_notifications = [
            item for item in sent
            if item["verb"] == "procurement_request_commented"
        ]
        assert len(comment_notifications) == 1
        assert comment_notifications[0]["recipient"] == processing_request.requestor
        assert comment_notifications[0]["data"]["comment_id"] == response.data["id"]

    def test_item_comment_notifies_requestor(
        self, api_client, supply_user, processing_request,
        procurement_item_factory, monkeypatch
    ):
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )

        item = procurement_item_factory(request=processing_request)
        api_client.force_authenticate(user=supply_user)
        url = reverse(
            'api:v1:procurement:procurementitem-comments',
            kwargs={'pk': item.id},
        )

        response = api_client.post(url, {'text': 'Заказали аналог'})

        assert response.status_code == status.HTTP_201_CREATED
        comment_notifications = [
            item for item in sent
            if item["verb"] == "procurement_item_commented"
        ]
        assert len(comment_notifications) == 1
        assert comment_notifications[0]["recipient"] == processing_request.requestor
        assert comment_notifications[0]["data"]["item_id"] == item.id
        assert comment_notifications[0]["data"]["comment_id"] == response.data["id"]

    def test_requestor_comments_do_not_notify_self(
        self, api_client, user, processing_request,
        procurement_item_factory, monkeypatch
    ):
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )

        item = procurement_item_factory(request=processing_request)

        api_client.force_authenticate(user=user)
        request_comment_url = reverse(
            'api:v1:procurement:procurementrequest-comments',
            kwargs={'pk': processing_request.id},
        )
        item_comment_url = reverse(
            'api:v1:procurement:procurementitem-comments',
            kwargs={'pk': item.id},
        )

        request_response = api_client.post(
            request_comment_url,
            {'text': 'Мой комментарий'},
        )
        item_response = api_client.post(
            item_comment_url,
            {'text': 'Мой комментарий к позиции'},
        )

        assert request_response.status_code == status.HTTP_201_CREATED
        assert item_response.status_code == status.HTTP_201_CREATED
        assert [
            item for item in sent
            if item["verb"] in {
                "procurement_request_commented",
                "procurement_item_commented",
            }
        ] == []

    def test_mark_all_received_updates_items_and_closes_request(
        self, api_client, supply_user, processing_request,
        procurement_item_factory, monkeypatch
    ):
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )

        item_1 = procurement_item_factory(
            request=processing_request,
            quantity=2,
            execution_status=ProcurementItemExecutionStatus.ORDERED,
            ordered_quantity=1,
        )
        item_2 = procurement_item_factory(
            request=processing_request,
            name="Лампы",
        )
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.save()
        sent.clear()

        api_client.force_authenticate(user=supply_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-mark-all-received',
            kwargs={'pk': processing_request.id},
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        processing_request.refresh_from_db()
        item_1.refresh_from_db()
        item_2.refresh_from_db()
        assert item_1.execution_status == ProcurementItemExecutionStatus.RECEIVED
        assert item_2.execution_status == ProcurementItemExecutionStatus.RECEIVED
        assert item_1.ordered_quantity == item_1.quantity
        assert item_1.received_quantity == item_1.quantity
        assert item_2.ordered_quantity == item_2.quantity
        assert item_2.received_quantity == item_2.quantity
        assert (
            processing_request.fulfillment_status
            == ProcurementFulfillmentStatus.COMPLETED
        )
        assert processing_request.status == ProcurementStatus.COMPLETED
        assert processing_request.completed_at is not None
        item_update_recipients = [
            item["recipient"].email
            for item in sent
            if item["verb"] == "procurement_item_updated"
        ]
        assert item_update_recipients == []
        completed_recipients = [
            item["recipient"].email
            for item in sent
            if item["verb"] == "procurement_completed"
        ]
        assert completed_recipients == [processing_request.requestor.email]

    def test_processing_user_can_notify_requestor_about_arrival_multiple_times(
        self, api_client, user, supply_user, processing_request, monkeypatch
    ):
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )

        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.save()
        sent.clear()

        api_client.force_authenticate(user=supply_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-notify-arrival',
            kwargs={'pk': processing_request.id},
        )

        first_response = api_client.post(url)
        second_response = api_client.post(url)

        assert first_response.status_code == status.HTTP_200_OK
        assert second_response.status_code == status.HTTP_200_OK
        arrival_notifications = [
            item for item in sent
            if item["verb"] == "procurement_arrival_notice"
        ]
        assert len(arrival_notifications) == 2
        assert [
            item["recipient"].email for item in arrival_notifications
        ] == [user.email, user.email]
        assert all(item["sender"] == supply_user for item in arrival_notifications)
        assert all(
            item["data"]["request_id"] == processing_request.id
            for item in arrival_notifications
        )

    def test_notify_arrival_exposes_last_notice_timestamp(
        self, api_client, user, supply_user, processing_request
    ):
        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.IN_PROGRESS
        processing_request.save()

        api_client.force_authenticate(user=supply_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-notify-arrival',
            kwargs={'pk': processing_request.id},
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        notice = Notification.objects.get(
            recipient=user,
            verb="procurement_arrival_notice",
            target_object_id=str(processing_request.id),
        )
        assert (
            parse_datetime(response.data["last_arrival_notice_at"])
            == notice.timestamp
        )

        list_response = api_client.get(
            reverse('api:v1:procurement:procurementrequest-list'),
        )
        assert list_response.status_code == status.HTTP_200_OK
        list_payload = list_response.json()
        list_items = list_payload.get("results", list_payload)
        list_item = next(
            item for item in list_items
            if item["id"] == processing_request.id
        )
        assert (
            parse_datetime(list_item["last_arrival_notice_at"])
            == notice.timestamp
        )

        detail_response = api_client.get(
            reverse(
                'api:v1:procurement:procurementrequest-detail',
                kwargs={'pk': processing_request.id},
            ),
        )
        assert detail_response.status_code == status.HTTP_200_OK
        assert (
            parse_datetime(detail_response.data["last_arrival_notice_at"])
            == notice.timestamp
        )

    def test_notify_arrival_is_not_available_after_request_completed(
        self, api_client, supply_user, processing_request, monkeypatch
    ):
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )

        processing_request.executor = supply_user
        processing_request.status = ProcurementStatus.COMPLETED
        processing_request.completed_at = timezone.now()
        processing_request.save()
        sent.clear()

        api_client.force_authenticate(user=supply_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-notify-arrival',
            kwargs={'pk': processing_request.id},
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert [
            item for item in sent
            if item["verb"] == "procurement_arrival_notice"
        ] == []

    def test_requestor_cannot_notify_self_about_arrival(
        self, api_client, user, processing_request, monkeypatch
    ):
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )

        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-notify-arrival',
            kwargs={'pk': processing_request.id},
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert [
            item for item in sent
            if item["verb"] == "procurement_arrival_notice"
        ] == []


# ==============================================================================
# ТЕСТЫ WORKFLOW ДЕЙСТВИЙ
# ==============================================================================


class TestProcurementRequestWorkflow:
    """Тесты workflow действий с заявками."""

    @pytest.fixture(autouse=True)
    def approval_authorities(self, department_head, user):
        director = Employee.objects.create_user(
            email='director@example.com',
            password='testpass123',
            phone_number='+79995555555',
            first_name='Сергей',
            last_name='Сергеев',
            is_staff=True,
            is_superuser=True,
            is_active=True,
            email_verified=True,
            send_activation_email=False,
        )
        ApprovalRoute.objects.create(
            priority=HEAD_PRIORITY,
            resolver_type=ApprovalRoute.ResolverType.DEPARTMENT_HEAD,
        )
        ApprovalRoute.objects.create(
            priority=FINANCE_PRIORITY,
            min_amount=Decimal('10000.00'),
            name='Финансовый контроль',
            resolver_type=ApprovalRoute.ResolverType.FIXED_EMPLOYEE,
            employee=user,
        )
        ApprovalRoute.objects.create(
            priority=DIRECTOR_PRIORITY,
            min_amount=Decimal('50000.00'),
            name='Финальное одобрение',
            resolver_type=ApprovalRoute.ResolverType.FIXED_EMPLOYEE,
            employee=director,
        )

    def _create_department_approval_role_user(
        self,
        department,
        *,
        email="department-approval-role@example.com",
        phone_number="+79995555556",
    ):
        permission, _ = DepartmentPermission.objects.get_or_create(
            code=DeptPerm.APPROVE_PROCUREMENT,
            defaults={"name": "Согласование закупок отдела"},
        )
        role = DepartmentRole.objects.create(
            department=department,
            name=f"Согласующие закупки {email}",
        )
        role.scoped_permissions.add(permission)
        employee = Employee.objects.create_user(
            email=email,
            password='testpass123',
            phone_number=phone_number,
            first_name='Ролевой',
            last_name='Согласующий',
            is_active=True,
            email_verified=True,
            send_activation_email=False,
        )
        RoleAssignment.objects.create(
            employee=employee,
            role=role,
            is_active=True,
        )
        return employee

    def test_submit_notifies_only_current_stage_approver(
        self, api_client, recipient_user, recipient_department,
        procurement_request, procurement_item, budget, monkeypatch
    ):
        """При submit уведомление должно уйти только текущему этапу."""
        prepare_for_recipient_department_submit(
            procurement_request,
            recipient_department,
        )
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )

        api_client.force_authenticate(user=recipient_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': procurement_request.id}
        )

        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK

        pending_recipients = [
            item["recipient"].email
            for item in sent
            if item["verb"] == "procurement_pending_approval"
        ]
        assert pending_recipients == ["head@example.com"]

    def test_submit_notifies_department_head_and_role_approvers(
        self, api_client, recipient_user, recipient_department, department,
        procurement_request, procurement_item, monkeypatch
    ):
        prepare_for_recipient_department_submit(
            procurement_request,
            recipient_department,
        )
        role_approver = self._create_department_approval_role_user(
            department,
        )
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )

        api_client.force_authenticate(user=recipient_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': procurement_request.id}
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        pending_recipients = sorted(
            item["recipient"].email
            for item in sent
            if item["verb"] == "procurement_pending_approval"
        )
        assert pending_recipients == sorted([
            "head@example.com",
            role_approver.email,
        ])

    def test_department_role_user_can_approve_head_stage(
        self, api_client, user, department, department_head,
        procurement_request, procurement_item
    ):
        role_approver = self._create_department_approval_role_user(
            department,
            email="department-stage-approver@example.com",
            phone_number="+79995555557",
        )
        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()
        approval = Approval.objects.create(
            request=procurement_request,
            approver=department_head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.PENDING,
            step_name="Руководитель отдела",
        )

        api_client.force_authenticate(user=role_approver)
        pending_url = reverse(
            'api:v1:procurement:procurementrequest-pending-approvals'
        )
        pending_response = api_client.get(pending_url)
        assert pending_response.status_code == status.HTTP_200_OK
        assert [
            item['id'] for item in pending_response.data['results']
        ] == [procurement_request.id]
        assert pending_response.data['results'][0]['can_current_user_approve'] is True

        url = reverse(
            'api:v1:procurement:procurementrequest-approve',
            kwargs={'pk': procurement_request.id}
        )

        response = api_client.post(url, {'comment': 'Согласовано ролью'})

        assert response.status_code == status.HTTP_200_OK
        approval.refresh_from_db()
        procurement_request.refresh_from_db()
        assert approval.approver_id == role_approver.id
        assert approval.status == ApprovalStatus.APPROVED
        assert procurement_request.status == ProcurementStatus.APPROVED

    def test_department_role_approver_allows_submit_without_head(
        self, api_client, user, recipient_user, recipient_department,
        department
    ):
        department.head = None
        department.save(update_fields=["head"])
        role_approver = self._create_department_approval_role_user(
            department,
            email="department-no-head-approver@example.com",
            phone_number="+79995555558",
        )
        procurement_request = ProcurementRequest.objects.create(
            title="Заявка без начальника, но с ролью",
            description="Проверка согласующей роли",
            department=department,
            processing_department=recipient_department,
            requestor=user,
            status=ProcurementStatus.WAITING,
            urgency=UrgencyLevel.MEDIUM,
        )
        ProcurementItem.objects.create(
            request=procurement_request,
            name="Тестовая позиция",
            quantity=1,
            unit="шт",
            estimated_unit_price=Decimal("12.00"),
        )

        api_client.force_authenticate(user=recipient_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': procurement_request.id}
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        approval = procurement_request.approvals.get(priority=HEAD_PRIORITY)
        assert approval.approver_id == role_approver.id

    def test_approval_options_include_manual_routes_outside_amount(
        self, api_client, recipient_user, recipient_department,
        procurement_request
    ):
        """Предпросмотр показывает автоэтапы и ручные этапы вне суммы."""
        prepare_for_recipient_department_submit(
            procurement_request,
            recipient_department,
        )
        ProcurementItem.objects.create(
            request=procurement_request,
            name="Недорогая позиция",
            quantity=1,
            unit="шт",
            estimated_unit_price=Decimal("100.00"),
        )
        api_client.force_authenticate(user=recipient_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-approval-options',
            kwargs={'pk': procurement_request.id},
        )

        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert [
            item["priority"] for item in response.data["auto_steps"]
        ] == [HEAD_PRIORITY]
        available_by_priority = {
            item["priority"]: item
            for item in response.data["available_steps"]
        }
        assert available_by_priority[HEAD_PRIORITY]["is_amount_applicable"] is True
        assert available_by_priority[FINANCE_PRIORITY]["is_amount_applicable"] is False
        assert available_by_priority[DIRECTOR_PRIORITY]["is_amount_applicable"] is False
        assert available_by_priority[DIRECTOR_PRIORITY]["is_available"] is True

    def test_submit_with_manual_approver_bypasses_amount_auto_routes(
        self, api_client, recipient_user, recipient_department,
        procurement_request
    ):
        """Ручной список используется вместо автоподбора по сумме."""
        prepare_for_recipient_department_submit(
            procurement_request,
            recipient_department,
        )
        ProcurementItem.objects.create(
            request=procurement_request,
            name="Недорогая позиция",
            quantity=1,
            unit="шт",
            estimated_unit_price=Decimal("100.00"),
        )
        director = Employee.objects.get(email="director@example.com")
        api_client.force_authenticate(user=recipient_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': procurement_request.id},
        )

        response = api_client.post(
            url,
            {
                "approval_steps": [
                    {
                        "priority": DIRECTOR_PRIORITY,
                        "approver": director.id,
                    }
                ]
            },
            format='json',
        )

        assert response.status_code == status.HTTP_200_OK
        procurement_request.refresh_from_db()
        assert procurement_request.status == ProcurementStatus.PENDING
        approvals = list(procurement_request.approvals.order_by("priority"))
        assert len(approvals) == 1
        assert approvals[0].priority == DIRECTOR_PRIORITY
        assert approvals[0].approver_id == director.id

    def test_approve_notifies_only_next_stage_approver(
        self, api_client, department_head, procurement_request, procurement_item, monkeypatch
    ):
        """После approve уведомление переходит только следующему этапу."""
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )

        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()

        Approval.objects.create(
            request=procurement_request,
            approver=department_head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.PENDING,
            step_name="Руководитель отдела",
        )
        Approval.objects.create(
            request=procurement_request,
            approver=Employee.objects.get(email="user@example.com"),
            priority=FINANCE_PRIORITY,
            status=ApprovalStatus.PENDING,
            step_name="Финансовый контроль",
        )
        Approval.objects.create(
            request=procurement_request,
            approver=Employee.objects.get(email="director@example.com"),
            priority=DIRECTOR_PRIORITY,
            status=ApprovalStatus.PENDING,
            step_name="Финальное одобрение",
        )
        sent.clear()

        api_client.force_authenticate(user=department_head)
        url = reverse(
            'api:v1:procurement:procurementrequest-approve',
            kwargs={'pk': procurement_request.id}
        )

        response = api_client.post(url, {'comment': 'Одобрено'})
        assert response.status_code == status.HTTP_200_OK

        pending_recipients = [
            item["recipient"].email
            for item in sent
            if item["verb"] == "procurement_pending_approval"
        ]
        assert pending_recipients == ["user@example.com"]
        stage_notifications = [
            item for item in sent
            if item["verb"] == "procurement_stage_approved"
        ]
        assert stage_notifications == []

    def test_final_approve_does_not_notify_future_approvers(
        self, api_client, approver_with_permission, procurement_request, procurement_item, monkeypatch
    ):
        """На финальном approve не должно быть нового pending-уведомления."""
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )

        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()

        Approval.objects.create(
            request=procurement_request,
            approver=approver_with_permission,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.PENDING,
            step_name="Финальный этап",
        )
        sent.clear()

        api_client.force_authenticate(user=approver_with_permission)
        url = reverse(
            'api:v1:procurement:procurementrequest-approve',
            kwargs={'pk': procurement_request.id}
        )

        response = api_client.post(url, {'comment': 'Финально одобрено'})
        assert response.status_code == status.HTTP_200_OK

        pending_notifications = [
            item for item in sent
            if item["verb"] == "procurement_pending_approval"
        ]
        assert pending_notifications == []
        approved_recipients = [
            item["recipient"].email
            for item in sent
            if item["verb"] == "procurement_approved"
        ]
        assert approved_recipients == [procurement_request.requestor.email]

    def test_reject_notifies_requestor_without_next_stage_notification(
        self, api_client, department_head, procurement_request, procurement_item, monkeypatch
    ):
        """Reject не должен уведомлять следующий этап, только создателя."""
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )

        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()

        Approval.objects.create(
            request=procurement_request,
            approver=department_head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.PENDING,
            step_name="Руководитель отдела",
        )
        Approval.objects.create(
            request=procurement_request,
            approver=Employee.objects.get(email="user@example.com"),
            priority=FINANCE_PRIORITY,
            status=ApprovalStatus.PENDING,
            step_name="Финансовый контроль",
        )
        sent.clear()

        api_client.force_authenticate(user=department_head)
        url = reverse(
            'api:v1:procurement:procurementrequest-reject',
            kwargs={'pk': procurement_request.id}
        )

        response = api_client.post(url, {'comment': 'Отклонено'})
        assert response.status_code == status.HTTP_200_OK

        verbs = [item["verb"] for item in sent]
        recipients = [item["recipient"].email for item in sent]
        assert verbs.count("procurement_rejected") == 1
        assert recipients.count(procurement_request.requestor.email) == 1
        assert "procurement_pending_approval" not in verbs

    def test_cancel_notifies_all_related_approvers(
        self, api_client, user, department_head, procurement_request, procurement_item, monkeypatch
    ):
        """Cancel уведомляет всех причастных согласующих."""
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )

        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()

        Approval.objects.create(
            request=procurement_request,
            approver=department_head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.APPROVED,
            step_name="Руководитель отдела",
        )
        Approval.objects.create(
            request=procurement_request,
            approver=user,
            priority=FINANCE_PRIORITY,
            status=ApprovalStatus.PENDING,
            step_name="Финансовый контроль",
        )
        sent.clear()

        api_client.force_authenticate(user=procurement_request.requestor)
        url = reverse(
            'api:v1:procurement:procurementrequest-cancel',
            kwargs={'pk': procurement_request.id}
        )

        response = api_client.post(url, {'reason': 'Передумали'})
        assert response.status_code == status.HTTP_200_OK

        cancelled_recipients = [
            item["recipient"].email
            for item in sent
            if item["verb"] == "procurement_cancelled"
        ]
        assert cancelled_recipients == ["head@example.com"]

    def test_start_work_does_not_notify_requestor(
        self, api_client, user, staff_user, department_head, procurement_request, procurement_item, monkeypatch
    ):
        """При взятии в работу автор заявки не получает шумное уведомление."""
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )

        procurement_request.status = ProcurementStatus.APPROVED
        procurement_request.executor = None
        procurement_request.save()

        Approval.objects.create(
            request=procurement_request,
            approver=department_head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.APPROVED,
            step_name="Руководитель отдела",
        )
        Approval.objects.create(
            request=procurement_request,
            approver=user,
            priority=FINANCE_PRIORITY,
            status=ApprovalStatus.APPROVED,
            step_name="Финансовый контроль",
        )
        sent.clear()

        api_client.force_authenticate(user=staff_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-start-work',
            kwargs={'pk': procurement_request.id}
        )

        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK

        in_progress_recipients = [
            item["recipient"].email
            for item in sent
            if item["verb"] == "procurement_in_progress"
        ]
        assert procurement_request.requestor.email not in in_progress_recipients

    def test_complete_notifies_requestor(
        self, api_client, user, staff_user, department_head, procurement_request, procurement_item, monkeypatch
    ):
        """При завершении уведомляется автор заявки."""
        sent = []

        def fake_notify_send(**kwargs):
            sent.append(kwargs)

        monkeypatch.setattr(
            "procurement.notifications.handlers.notify.send",
            fake_notify_send,
        )

        procurement_request.status = ProcurementStatus.IN_PROGRESS
        procurement_request.executor = staff_user
        procurement_request.save()

        Approval.objects.create(
            request=procurement_request,
            approver=department_head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.APPROVED,
            step_name="Руководитель отдела",
        )
        Approval.objects.create(
            request=procurement_request,
            approver=user,
            priority=FINANCE_PRIORITY,
            status=ApprovalStatus.APPROVED,
            step_name="Финансовый контроль",
        )
        sent.clear()

        api_client.force_authenticate(user=staff_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-complete',
            kwargs={'pk': procurement_request.id}
        )

        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        procurement_item.refresh_from_db()
        assert procurement_item.execution_status == ProcurementItemExecutionStatus.PENDING

        completed_recipients = [
            item["recipient"].email
            for item in sent
            if item["verb"] == "procurement_completed"
        ]
        assert completed_recipients == [
            procurement_request.requestor.email,
        ]

    def test_submit_request(
        self, api_client, recipient_user, recipient_department,
        procurement_request, procurement_item, budget
    ):
        """Отправка заявки на согласование."""
        prepare_for_recipient_department_submit(
            procurement_request,
            recipient_department,
        )
        api_client.force_authenticate(user=recipient_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': procurement_request.id}
        )
        
        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        
        # Проверяем статус изменен
        procurement_request.refresh_from_db()
        assert procurement_request.status == ProcurementStatus.PENDING
        assert procurement_request.submitted_at is not None
        assert list(
            procurement_request.approvals.order_by('priority').values_list('priority', flat=True)
        ) == [1, 2, 3]
        assert list(
            procurement_request.approvals.order_by('priority').values_list('step_name', flat=True)
        ) == [
            'Руководитель отдела',
            'Финансовый контроль',
            'Финальное одобрение',
        ]

    @pytest.mark.parametrize(
        ("unit_price", "expected_priorities"),
        [
            (Decimal("12.00"), [HEAD_PRIORITY]),
            (Decimal("12000.00"), [HEAD_PRIORITY, FINANCE_PRIORITY]),
            (Decimal("120000.00"), [HEAD_PRIORITY, FINANCE_PRIORITY, DIRECTOR_PRIORITY]),
        ],
    )
    def test_submit_request_applies_amount_thresholds(
        self, api_client, user, recipient_user, recipient_department,
        department, unit_price, expected_priorities
    ):
        """Маршруты согласования включаются по порогам суммы заявки."""
        procurement_request = ProcurementRequest.objects.create(
            title="Пороговая заявка",
            description="Проверка маршрутов",
            department=department,
            processing_department=recipient_department,
            requestor=user,
            status=ProcurementStatus.WAITING,
            urgency=UrgencyLevel.MEDIUM,
        )
        ProcurementItem.objects.create(
            request=procurement_request,
            name="Тестовая позиция",
            quantity=1,
            unit="шт",
            estimated_unit_price=unit_price,
        )

        api_client.force_authenticate(user=recipient_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': procurement_request.id}
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        procurement_request.refresh_from_db()
        assert list(
            procurement_request.approvals.order_by('priority').values_list('priority', flat=True)
        ) == expected_priorities

    def test_submit_request_applies_amount_thresholds_by_actual_price(
        self, api_client, user, recipient_user, recipient_department,
        department
    ):
        """Если закупщик указал фактическую цену, пороги берутся по ней."""
        procurement_request = ProcurementRequest.objects.create(
            title="Уточненная пороговая заявка",
            description="Проверка маршрутов",
            department=department,
            processing_department=recipient_department,
            requestor=user,
            status=ProcurementStatus.WAITING,
            urgency=UrgencyLevel.MEDIUM,
        )
        ProcurementItem.objects.create(
            request=procurement_request,
            name="Позиция с уточненной ценой",
            quantity=1,
            unit="шт",
            estimated_unit_price=Decimal("100.00"),
            actual_unit_price=Decimal("120000.00"),
        )

        api_client.force_authenticate(user=recipient_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': procurement_request.id}
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        procurement_request.refresh_from_db()
        assert procurement_request.total_cost == Decimal("120000.00")
        assert list(
            procurement_request.approvals.order_by('priority').values_list('priority', flat=True)
        ) == [HEAD_PRIORITY, FINANCE_PRIORITY, DIRECTOR_PRIORITY]

    def test_submit_request_without_department_head_returns_explicit_error(
        self, api_client, user, recipient_user, recipient_department,
        department
    ):
        """Если обязательный этап = руководитель отдела, ошибка должна быть явной."""
        department.head = None
        department.save(update_fields=["head"])

        procurement_request = ProcurementRequest.objects.create(
            title="Заявка без начальника отдела",
            description="Проверка понятной ошибки",
            department=department,
            processing_department=recipient_department,
            requestor=user,
            status=ProcurementStatus.WAITING,
            urgency=UrgencyLevel.MEDIUM,
        )
        ProcurementItem.objects.create(
            request=procurement_request,
            name="Тестовая позиция",
            quantity=1,
            unit="шт",
            estimated_unit_price=Decimal("12.00"),
        )

        api_client.force_authenticate(user=recipient_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': procurement_request.id}
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["code"] == "department_head_missing"
        assert "не назначен руководитель" in response.data["error"].lower()
        assert response.data["missing_priorities"] == [HEAD_PRIORITY]
        assert response.data["missing_routes"][0]["reason"] == "department_head_missing"

    def test_submit_returns_manual_step_name(
        self, api_client, recipient_user, recipient_department,
        procurement_request, procurement_item, budget
    ):
        """Ручное название этапа сохраняется в согласовании и отдаётся в API."""
        prepare_for_recipient_department_submit(
            procurement_request,
            recipient_department,
        )
        api_client.force_authenticate(user=recipient_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': procurement_request.id}
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        approvals = sorted(response.data['approvals'], key=lambda item: item['priority'])
        assert isinstance(approvals[0]["approver"], dict)
        assert "avatar" in approvals[0]["approver"]
        assert approvals[1]['step_name'] == 'Финансовый контроль'
        assert approvals[1]['step_label'] == 'Финансовый контроль'

    def test_submit_without_items_fails(
        self, api_client, recipient_user, recipient_department,
        procurement_request
    ):
        """Нельзя отправить заявку без позиций."""
        prepare_for_recipient_department_submit(
            procurement_request,
            recipient_department,
        )
        api_client.force_authenticate(user=recipient_user)
        url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': procurement_request.id}
        )
        
        response = api_client.post(url)
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert 'позицию' in response.data['error'].lower()

    def test_approve_request_by_head(
        self, api_client, department_head, procurement_request,
        procurement_item, budget
    ):
        """Согласование заявки руководителем."""
        # Отправляем заявку
        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()
        
        # Создаем запись согласования
        Approval.objects.create(
            request=procurement_request,
            approver=department_head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.PENDING,
        )
        
        api_client.force_authenticate(user=department_head)
        url = reverse(
            'api:v1:procurement:procurementrequest-approve',
            kwargs={'pk': procurement_request.id}
        )
        
        response = api_client.post(url, {'comment': 'Одобрено'})
        assert response.status_code == status.HTTP_200_OK

    def test_higher_approver_can_approve_before_head(
        self, api_client, user, department_head, procurement_request,
        procurement_item, budget
    ):
        """Вышестоящий согласующий может закрыть предыдущий этап."""
        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()

        head_approval = Approval.objects.create(
            request=procurement_request,
            approver=department_head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.PENDING,
        )
        finance_approval = Approval.objects.create(
            request=procurement_request,
            approver=user,
            priority=FINANCE_PRIORITY,
            status=ApprovalStatus.PENDING,
        )

        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-approve',
            kwargs={'pk': procurement_request.id}
        )

        response = api_client.post(url, {'comment': 'Согласовано сверху'})
        assert response.status_code == status.HTTP_200_OK

        head_approval.refresh_from_db()
        finance_approval.refresh_from_db()
        procurement_request.refresh_from_db()

        assert head_approval.status == ApprovalStatus.APPROVED
        assert "вышестоящим" in head_approval.comment
        assert finance_approval.status == ApprovalStatus.APPROVED
        assert finance_approval.comment == "Согласовано сверху"
        assert procurement_request.status == ProcurementStatus.APPROVED

    def test_top_approver_can_close_all_previous_stages(
        self, api_client, user, department_head, procurement_request,
        procurement_item, budget
    ):
        """Последний согласующий может одобрить заявку сразу за всю цепочку."""
        director = Employee.objects.create_user(
            email="director-bypass@example.com",
            password="testpass123",
            phone_number="+79998889999",
            first_name="АЮ",
            last_name="Директор",
            is_active=True,
            email_verified=True,
            send_activation_email=False,
        )
        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()

        head_approval = Approval.objects.create(
            request=procurement_request,
            approver=department_head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.PENDING,
        )
        finance_approval = Approval.objects.create(
            request=procurement_request,
            approver=user,
            priority=FINANCE_PRIORITY,
            status=ApprovalStatus.PENDING,
        )
        director_approval = Approval.objects.create(
            request=procurement_request,
            approver=director,
            priority=DIRECTOR_PRIORITY,
            status=ApprovalStatus.PENDING,
        )

        api_client.force_authenticate(user=director)
        url = reverse(
            'api:v1:procurement:procurementrequest-approve',
            kwargs={'pk': procurement_request.id}
        )

        response = api_client.post(url, {'comment': 'Финальное согласование'})
        assert response.status_code == status.HTTP_200_OK

        head_approval.refresh_from_db()
        finance_approval.refresh_from_db()
        director_approval.refresh_from_db()
        procurement_request.refresh_from_db()

        assert head_approval.status == ApprovalStatus.APPROVED
        assert finance_approval.status == ApprovalStatus.APPROVED
        assert director_approval.status == ApprovalStatus.APPROVED
        assert director_approval.comment == "Финальное согласование"
        assert procurement_request.status == ProcurementStatus.APPROVED

    def test_higher_approver_reject_closes_previous_stages(
        self, api_client, user, department_head, procurement_request,
        procurement_item, budget
    ):
        """Вышестоящее отклонение закрывает предыдущие pending-этапы."""
        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()

        head_approval = Approval.objects.create(
            request=procurement_request,
            approver=department_head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.PENDING,
        )
        finance_approval = Approval.objects.create(
            request=procurement_request,
            approver=user,
            priority=FINANCE_PRIORITY,
            status=ApprovalStatus.PENDING,
        )

        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-reject',
            kwargs={'pk': procurement_request.id}
        )

        response = api_client.post(url, {'comment': 'Отклонено сверху'})
        assert response.status_code == status.HTTP_200_OK

        head_approval.refresh_from_db()
        finance_approval.refresh_from_db()
        procurement_request.refresh_from_db()

        assert head_approval.status == ApprovalStatus.REJECTED
        assert "вышестоящим" in head_approval.comment
        assert finance_approval.status == ApprovalStatus.REJECTED
        assert finance_approval.comment == "Отклонено сверху"
        assert procurement_request.status == ProcurementStatus.REJECTED

    def test_pending_approval_does_not_allow_approve_when_request_not_pending(
        self, api_client, department_head, procurement_request, procurement_item
    ):
        """Pending-запись не дает approve, если сама заявка уже не pending."""
        procurement_request.status = ProcurementStatus.APPROVED
        procurement_request.save()

        Approval.objects.create(
            request=procurement_request,
            approver=department_head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.PENDING,
        )

        list_url = reverse('api:v1:procurement:procurementrequest-list')
        detail_url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': procurement_request.id}
        )
        approve_url = reverse(
            'api:v1:procurement:procurementrequest-approve',
            kwargs={'pk': procurement_request.id}
        )

        api_client.force_authenticate(user=department_head)

        list_response = api_client.get(list_url)
        assert list_response.status_code == status.HTTP_200_OK
        assert list_response.data['results'][0]['can_current_user_approve'] is False

        detail_response = api_client.get(detail_url)
        assert detail_response.status_code == status.HTTP_200_OK
        assert detail_response.data['can_current_user_approve'] is False

        approve_response = api_client.post(approve_url, {'comment': 'Поздно'})
        assert approve_response.status_code == status.HTTP_403_FORBIDDEN

    def test_staff_without_pending_stage_cannot_approve(
        self, api_client, staff_user, department_head, procurement_request, procurement_item
    ):
        """Staff без текущего этапа не должен видеть или выполнять approve."""
        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()

        Approval.objects.create(
            request=procurement_request,
            approver=department_head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.PENDING,
        )

        list_url = reverse('api:v1:procurement:procurementrequest-list')
        detail_url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': procurement_request.id}
        )
        approve_url = reverse(
            'api:v1:procurement:procurementrequest-approve',
            kwargs={'pk': procurement_request.id}
        )

        api_client.force_authenticate(user=staff_user)

        list_response = api_client.get(list_url)
        assert list_response.status_code == status.HTTP_200_OK
        assert list_response.data['results'][0]['can_current_user_approve'] is False

        detail_response = api_client.get(detail_url)
        assert detail_response.status_code == status.HTTP_200_OK
        assert detail_response.data['can_current_user_approve'] is False

        approve_response = api_client.post(approve_url, {'comment': 'Нельзя'})
        assert approve_response.status_code == status.HTTP_403_FORBIDDEN

    def test_superuser_without_pending_stage_cannot_approve(
        self, api_client, superuser, department_head, procurement_request, procurement_item
    ):
        """Суперпользователь не должен получать approve без назначения на этап."""
        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()

        Approval.objects.create(
            request=procurement_request,
            approver=department_head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.PENDING,
        )

        list_url = reverse('api:v1:procurement:procurementrequest-list')
        detail_url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': procurement_request.id}
        )
        approve_url = reverse(
            'api:v1:procurement:procurementrequest-approve',
            kwargs={'pk': procurement_request.id}
        )

        api_client.force_authenticate(user=superuser)

        list_response = api_client.get(list_url)
        assert list_response.status_code == status.HTTP_200_OK
        assert list_response.data['results'][0]['can_current_user_approve'] is False

        detail_response = api_client.get(detail_url)
        assert detail_response.status_code == status.HTTP_200_OK
        assert detail_response.data['can_current_user_approve'] is False

        approve_response = api_client.post(approve_url, {'comment': 'Нельзя'})
        assert approve_response.status_code == status.HTTP_403_FORBIDDEN

    def test_permission_without_pending_stage_cannot_approve(
        self, api_client, approver_with_permission, department_head, procurement_request, procurement_item
    ):
        """Одного model-permission недостаточно без назначения на текущий этап."""
        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()

        Approval.objects.create(
            request=procurement_request,
            approver=department_head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.PENDING,
        )

        list_url = reverse('api:v1:procurement:procurementrequest-list')
        detail_url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': procurement_request.id}
        )
        approve_url = reverse(
            'api:v1:procurement:procurementrequest-approve',
            kwargs={'pk': procurement_request.id}
        )

        api_client.force_authenticate(user=approver_with_permission)

        list_response = api_client.get(list_url)
        assert list_response.status_code == status.HTTP_200_OK
        assert list_response.data['results'][0]['can_current_user_approve'] is False

        detail_response = api_client.get(detail_url)
        assert detail_response.status_code == status.HTTP_200_OK
        assert detail_response.data['can_current_user_approve'] is False

        approve_response = api_client.post(approve_url, {'comment': 'Нельзя'})
        assert approve_response.status_code == status.HTTP_403_FORBIDDEN

    def test_permissioned_current_approver_can_approve(
        self, api_client, approver_with_permission, procurement_request, procurement_item
    ):
        """Если пользователь и назначен, и имеет permission, approve доступен."""
        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()

        Approval.objects.create(
            request=procurement_request,
            approver=approver_with_permission,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.PENDING,
        )

        list_url = reverse('api:v1:procurement:procurementrequest-list')
        detail_url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': procurement_request.id}
        )
        approve_url = reverse(
            'api:v1:procurement:procurementrequest-approve',
            kwargs={'pk': procurement_request.id}
        )

        api_client.force_authenticate(user=approver_with_permission)

        list_response = api_client.get(list_url)
        assert list_response.status_code == status.HTTP_200_OK
        assert list_response.data['results'][0]['can_current_user_approve'] is True

        detail_response = api_client.get(detail_url)
        assert detail_response.status_code == status.HTTP_200_OK
        assert detail_response.data['can_current_user_approve'] is True

        approve_response = api_client.post(approve_url, {'comment': 'Можно'})
        assert approve_response.status_code == status.HTTP_200_OK

    def test_requestor_can_approve_when_requestor_is_current_approver(
        self, api_client, user, procurement_request, procurement_item
    ):
        """Если заявитель назначен текущим согласующим, approve для него доступен."""
        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()

        Approval.objects.create(
            request=procurement_request,
            approver=user,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.PENDING,
        )

        list_url = reverse('api:v1:procurement:procurementrequest-list')
        detail_url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': procurement_request.id}
        )
        approve_url = reverse(
            'api:v1:procurement:procurementrequest-approve',
            kwargs={'pk': procurement_request.id}
        )

        api_client.force_authenticate(user=user)

        list_response = api_client.get(list_url)
        assert list_response.status_code == status.HTTP_200_OK
        assert list_response.data['results'][0]['can_current_user_approve'] is True

        detail_response = api_client.get(detail_url)
        assert detail_response.status_code == status.HTTP_200_OK
        assert detail_response.data['can_current_user_approve'] is True

        approve_response = api_client.post(approve_url, {'comment': 'Сам себе согласовал'})
        assert approve_response.status_code == status.HTTP_200_OK

        procurement_request.refresh_from_db()
        assert procurement_request.status == ProcurementStatus.APPROVED

    def test_list_marks_current_and_higher_approver_as_can_approve(
        self, api_client, user, department_head, procurement_request, procurement_item
    ):
        """Список показывает approve/reject текущему и вышестоящему согласующим."""
        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()

        Approval.objects.create(
            request=procurement_request,
            approver=department_head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.PENDING,
        )
        Approval.objects.create(
            request=procurement_request,
            approver=user,
            priority=FINANCE_PRIORITY,
            status=ApprovalStatus.PENDING,
        )

        url = reverse('api:v1:procurement:procurementrequest-list')

        api_client.force_authenticate(user=department_head)
        head_response = api_client.get(url)
        assert head_response.status_code == status.HTTP_200_OK
        assert head_response.data['results'][0]['can_current_user_approve'] is True

        api_client.force_authenticate(user=user)
        finance_response = api_client.get(url)
        assert finance_response.status_code == status.HTTP_200_OK
        assert finance_response.data['results'][0]['can_current_user_approve'] is True

    def test_pending_approvals_includes_higher_approver(
        self, api_client, user, department_head, procurement_request, procurement_item
    ):
        """Вкладка согласования должна показывать заявку вышестоящему этапу."""
        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()

        Approval.objects.create(
            request=procurement_request,
            approver=department_head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.PENDING,
        )
        Approval.objects.create(
            request=procurement_request,
            approver=user,
            priority=FINANCE_PRIORITY,
            status=ApprovalStatus.PENDING,
        )

        url = reverse('api:v1:procurement:procurementrequest-pending-approvals')

        api_client.force_authenticate(user=user)
        response = api_client.get(url)

        assert response.status_code == status.HTTP_200_OK
        assert [item['id'] for item in response.data['results']] == [procurement_request.id]
        assert response.data['results'][0]['can_current_user_approve'] is True

    def test_higher_route_can_approve_even_if_not_required_by_amount(
        self, api_client, user, recipient_user, recipient_department,
        department
    ):
        """Вышестоящий маршрут может согласовать заявку ниже своего порога."""
        procurement_request = ProcurementRequest.objects.create(
            title="Низкая сумма для обхода сверху",
            description="Проверка согласования верхним маршрутом",
            department=department,
            processing_department=recipient_department,
            requestor=user,
            status=ProcurementStatus.WAITING,
            urgency=UrgencyLevel.MEDIUM,
        )
        ProcurementItem.objects.create(
            request=procurement_request,
            name="Дешевая позиция",
            quantity=1,
            unit="шт",
            estimated_unit_price=Decimal("12.00"),
        )

        api_client.force_authenticate(user=recipient_user)
        submit_url = reverse(
            'api:v1:procurement:procurementrequest-submit',
            kwargs={'pk': procurement_request.id}
        )
        submit_response = api_client.post(submit_url)
        assert submit_response.status_code == status.HTTP_200_OK

        procurement_request.refresh_from_db()
        assert list(
            procurement_request.approvals.order_by('priority').values_list('priority', flat=True)
        ) == [HEAD_PRIORITY]

        api_client.force_authenticate(user=user)
        pending_url = reverse('api:v1:procurement:procurementrequest-pending-approvals')
        pending_response = api_client.get(pending_url)
        assert pending_response.status_code == status.HTTP_200_OK
        assert [item['id'] for item in pending_response.data['results']] == [procurement_request.id]
        assert pending_response.data['results'][0]['can_current_user_approve'] is True

        approve_url = reverse(
            'api:v1:procurement:procurementrequest-approve',
            kwargs={'pk': procurement_request.id}
        )
        approve_response = api_client.post(approve_url, {'comment': 'Согласовано выше порога'})
        assert approve_response.status_code == status.HTTP_200_OK

        procurement_request.refresh_from_db()
        approvals = procurement_request.approvals.order_by('priority')
        assert list(approvals.values_list('priority', flat=True)) == [
            HEAD_PRIORITY,
            FINANCE_PRIORITY,
        ]
        assert list(approvals.values_list('status', flat=True)) == [
            ApprovalStatus.APPROVED,
            ApprovalStatus.APPROVED,
        ]
        assert procurement_request.status == ProcurementStatus.WAITING

    def test_detail_marks_next_stage_approver_after_previous_stage_complete(
        self, api_client, user, department_head, procurement_request, procurement_item
    ):
        """Detail должен отдавать backend-истину после смены текущего этапа."""
        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()

        Approval.objects.create(
            request=procurement_request,
            approver=department_head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.APPROVED,
        )
        Approval.objects.create(
            request=procurement_request,
            approver=user,
            priority=FINANCE_PRIORITY,
            status=ApprovalStatus.PENDING,
        )

        url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': procurement_request.id}
        )

        api_client.force_authenticate(user=department_head)
        head_response = api_client.get(url)
        assert head_response.status_code == status.HTTP_200_OK
        assert head_response.data['can_current_user_approve'] is False

        api_client.force_authenticate(user=user)
        finance_response = api_client.get(url)
        assert finance_response.status_code == status.HTTP_200_OK
        assert finance_response.data['can_current_user_approve'] is True

    def test_reject_request(
        self, api_client, department_head, procurement_request,
        procurement_item
    ):
        """Отклонение заявки."""
        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()
        
        Approval.objects.create(
            request=procurement_request,
            approver=department_head,
            priority=HEAD_PRIORITY,
            status=ApprovalStatus.PENDING,
        )
        
        api_client.force_authenticate(user=department_head)
        url = reverse(
            'api:v1:procurement:procurementrequest-reject',
            kwargs={'pk': procurement_request.id}
        )
        
        data = {'comment': 'Недостаточно обоснования'}
        response = api_client.post(url, data)
        assert response.status_code == status.HTTP_200_OK
        
        procurement_request.refresh_from_db()
        assert procurement_request.status == ProcurementStatus.REJECTED

    def test_cancel_own_request(
        self, api_client, user, procurement_request
    ):
        """Отмена своей заявки."""
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-cancel',
            kwargs={'pk': procurement_request.id}
        )
        
        response = api_client.post(url)
        assert response.status_code == status.HTTP_200_OK
        
        procurement_request.refresh_from_db()
        assert procurement_request.status == ProcurementStatus.CANCELLED


# ==============================================================================
# ТЕСТЫ УМНОГО ПРОЧТЕНИЯ УВЕДОМЛЕНИЙ
# ==============================================================================


class TestProcurementRequestNotificationRead:
    """Тесты прочтения уведомлений, связанных с конкретной закупкой."""

    def test_marks_only_current_request_procurement_notifications_read(
        self, api_client, user, department, procurement_request
    ):
        request_content_type = ContentType.objects.get_for_model(
            ProcurementRequest,
        )
        other_request = ProcurementRequest.objects.create(
            title="Другая закупка",
            description="Другая заявка",
            department=department,
            requestor=user,
            status=ProcurementStatus.DRAFT,
        )

        matching_by_data = Notification.objects.create(
            recipient=user,
            verb="procurement_department_request",
            data={"request_id": procurement_request.id},
        )
        matching_by_target = Notification.objects.create(
            recipient=user,
            verb="procurement_request_commented",
            target_content_type=request_content_type,
            target_object_id=str(procurement_request.id),
            data={},
        )
        other_request_notification = Notification.objects.create(
            recipient=user,
            verb="procurement_department_request",
            data={"request_id": other_request.id},
        )
        non_procurement_notification = Notification.objects.create(
            recipient=user,
            verb="new_message",
            data={"request_id": procurement_request.id},
        )
        already_read_notification = Notification.objects.create(
            recipient=user,
            verb="procurement_approved",
            unread=False,
            timestamp_read=timezone.now(),
            data={"request_id": procurement_request.id},
        )

        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-mark-notifications-read',
            kwargs={'pk': procurement_request.id},
        )

        response = api_client.post(url)

        assert response.status_code == status.HTTP_200_OK
        assert response.data["status"] == "success"
        assert response.data["count"] == 2
        assert sorted(response.data["notification_ids"]) == sorted([
            matching_by_data.id,
            matching_by_target.id,
        ])

        matching_by_data.refresh_from_db()
        matching_by_target.refresh_from_db()
        other_request_notification.refresh_from_db()
        non_procurement_notification.refresh_from_db()
        already_read_notification.refresh_from_db()

        assert matching_by_data.unread is False
        assert matching_by_target.unread is False
        assert other_request_notification.unread is True
        assert non_procurement_notification.unread is True
        assert already_read_notification.unread is False


# ==============================================================================
# ТЕСТЫ УДАЛЕНИЯ
# ==============================================================================


class TestProcurementRequestDelete:
    """Тесты удаления заявок."""

    def test_delete_draft_request(
        self, api_client, user, procurement_request
    ):
        """Удаление черновика."""
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': procurement_request.id}
        )
        
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_204_NO_CONTENT
        
        assert not ProcurementRequest.objects.filter(
            id=procurement_request.id
        ).exists()

    def test_cannot_delete_submitted_request(
        self, api_client, user, procurement_request
    ):
        """Нельзя удалить отправленную заявку."""
        procurement_request.status = ProcurementStatus.PENDING
        procurement_request.save()
        
        api_client.force_authenticate(user=user)
        url = reverse(
            'api:v1:procurement:procurementrequest-detail',
            kwargs={'pk': procurement_request.id}
        )
        
        response = api_client.delete(url)
        assert response.status_code == status.HTTP_403_FORBIDDEN
