"""
Pytest fixtures для тестирования requests_app API
"""
import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission

from employees.models import Department, EmployeeDepartment, DepartmentRole
from requests_app.models import Request
from requests_app.enums import RequestStatus, RequestType

User = get_user_model()


# ============================================================================
# User Fixtures with различными правами
# ============================================================================

@pytest.fixture
def dept_processor(db, test_department):
    """Пользователь с правом can_process_requests в отделе"""
    user = User.objects.create_user(
        username='dept_processor',
        email='processor@test.com',
        password='testpass123',
        first_name='Согласующий',
        last_name='Отдела'
    )
    
    # Создаем роль с правом can_process_requests
    role = DepartmentRole.objects.create(name='Processor Role')
    
    # Добавляем permission can_process_requests к роли
    perm_code = 'can_process_requests'
    if hasattr(role, 'permissions_codes'):
        role.permissions_codes.append(perm_code)
        role.save()
    
    # Добавляем в отдел с ролью
    EmployeeDepartment.objects.create(
        employee=user,
        department=test_department,
        role=role,
        is_active=True
    )
    return user


@pytest.fixture
def global_viewer(db):
    """Пользователь с глобальным правом can_view_all_requests"""
    user = User.objects.create_user(
        username='global_viewer',
        email='global@test.com',
        password='testpass123',
        first_name='Глобальный',
        last_name='Просмотрщик'
    )
    
    # Пытаемся получить permission, если не найдено - создаем
    try:
        perm = Permission.objects.get(
            content_type__app_label='requests_app',
            codename='can_view_all_requests'
        )
    except Permission.DoesNotExist:
        ct = ContentType.objects.get_for_model(Request)
        perm = Permission.objects.create(
            content_type=ct,
            codename='can_view_all_requests',
            name='Можно просмотреть все заявления'
        )
    
    user.user_permissions.add(perm)
    return user


# ============================================================================
# Request Fixtures с различными конфигурациями получателей
# ============================================================================

@pytest.fixture
def request_with_recipients(db, test_employee, test_employee_second):
    """Заявка с получателями"""
    request = Request.objects.create(
        employee=test_employee,
        type=RequestType.OTHER,
        title='Заявка с получателями',
        status=RequestStatus.PENDING
    )
    request.recipients.add(test_employee_second)
    return request


@pytest.fixture
def request_with_cc(db, test_employee, test_employee_second):
    """Заявка с CC"""
    request = Request.objects.create(
        employee=test_employee,
        type=RequestType.OTHER,
        title='Заявка с CC',
        status=RequestStatus.PENDING
    )
    request.cc_users.add(test_employee_second)
    return request


@pytest.fixture
def request_to_department(db, test_employee, test_department):
    """Заявка, адресованная отделу"""
    request = Request.objects.create(
        employee=test_employee,
        type=RequestType.OTHER,
        title='Заявка для отдела',
        status=RequestStatus.PENDING
    )
    request.departments.add(test_department)
    return request


@pytest.fixture
def request_all_department(db, test_employee, test_department):
    """Заявка 'Всем в отделе'"""
    request = Request.objects.create(
        employee=test_employee,
        type=RequestType.OTHER,
        title='Всем в отделе',
        status=RequestStatus.PENDING,
        sent_to_all_department=True
    )
    request.departments.add(test_department)
    return request


@pytest.fixture
def request_complex(db, test_employee, test_employee_second, test_employee_third, test_department):
    """Сложная заявка: recipients + cc + departments"""
    request = Request.objects.create(
        employee=test_employee,
        type=RequestType.OTHER,
        title='Комплексная заявка',
        status=RequestStatus.PENDING
    )
    request.recipients.add(test_employee_second)
    request.cc_users.add(test_employee_third)
    request.departments.add(test_department)
    return request


@pytest.fixture
def approved_request(db, test_employee, test_staff_user):
    """Одобренная заявка"""
    request = Request.objects.create(
        employee=test_employee,
        type=RequestType.VACATION,
        title='Одобренный отпуск',
        status=RequestStatus.APPROVED,
        approver=test_staff_user
    )
    return request


# ============================================================================
# Helper Functions
# ============================================================================

@pytest.fixture
def create_request_helper(db):
    """Хелпер для создания заявки с получателями"""
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
            request.recipients.set(recipients if isinstance(recipients, list) else [recipients])
        if cc_users:
            request.cc_users.set(cc_users if isinstance(cc_users, list) else [cc_users])
        if departments:
            request.departments.set(departments if isinstance(departments, list) else [departments])
        
        return request
    
    return _create


@pytest.fixture
def check_user_can_see_request():
    """Хелпер для проверки видимости заявки для пользователя"""
    def _check(user, request_obj):
        from django.db.models import Q
        from employees.models import EmployeeDepartment, Department
        
        # Строим queryset как в реальном API
        my_dept_ids = list(
            EmployeeDepartment.objects.filter(
                employee=user,
                is_active=True
            ).values_list('department_id', flat=True)
        )
        
        # Проверка: может ли видеть ВСЁ
        can_view_all = (
            user.is_staff
            or user.has_perm("requests_app.can_view_all_requests")
            or user.has_perm("requests_app.view_request")
        )
        
        if can_view_all:
            return True
        
        # Обычный пользователь - строим scope
        scope = Q(employee_id=user.id)  # Свои заявки
        scope |= Q(recipients=user) | Q(cc_users=user)  # Адресованные
        
        # Заявки отделов с sent_to_all_department
        if my_dept_ids:
            scope |= Q(
                sent_to_all_department=True,
                departments__in=my_dept_ids
            )
        
        # Департаментные права
        view_dept_ids = list(
            EmployeeDepartment.objects.filter(
                employee_id=user.id,
                is_active=True,
                role__scoped_permissions__code="view_request",
            )
            .values_list("department_id", flat=True)
            .distinct()
        )
        proc_dept_ids = list(
            EmployeeDepartment.objects.filter(
                employee_id=user.id,
                is_active=True,
                role__scoped_permissions__code="can_process_requests",
            )
            .values_list("department_id", flat=True)
            .distinct()
        )
        head_dept_ids = list(
            Department.objects.filter(head_id=user.id).values_list("id", flat=True)
        )
        
        combined_ids = set(view_dept_ids) | set(proc_dept_ids) | set(head_dept_ids)
        
        if combined_ids:
            scope |= Q(departments__in=combined_ids)
            dept_emp_ids = list(
                EmployeeDepartment.objects.filter(
                    department_id__in=list(combined_ids),
                    is_active=True,
                )
                .values_list("employee_id", flat=True)
                .distinct()
            )
            if dept_emp_ids:
                scope |= Q(employee_id__in=dept_emp_ids)
        
        return Request.objects.filter(scope).filter(id=request_obj.id).exists()
    
    return _check


@pytest.fixture
def assert_notification_sent(db):
    """Хелпер для проверки отправки уведомлений"""
    def _assert(recipient, notification_type=None, request_obj=None):
        from notifications.models import Notification
        from django.contrib.contenttypes.models import ContentType
        
        qs = Notification.objects.filter(recipient=recipient)
        
        if notification_type:
            qs = qs.filter(notification_type__code=notification_type)
        
        if request_obj:
            ct = ContentType.objects.get_for_model(Request)
            qs = qs.filter(
                content_type=ct,
                object_id=request_obj.id
            )
        
        assert qs.exists(), (
            f"Уведомление не найдено для {recipient.username}"
        )
        
        return qs.first()
    
    return _assert
