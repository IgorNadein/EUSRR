"""
Тесты для новых endpoints назначения ролей: assign, revoke, assignments.
"""
import pytest
from django.test import override_settings
from rest_framework import status
from rest_framework.test import APIClient
from unittest.mock import patch

from django.contrib.auth import get_user_model
from employees.models import (
    Department, DepartmentPermission, DepartmentRole,
    EmployeeDepartment, RoleAssignment,
)
from tests.conftest import _unique_phone

User = get_user_model()
# В этом проекте User == Employee (кастомная модель)
Employee = User

def make_user(email: str, is_staff: bool = False) -> User:
    return User.objects.create_user(
        email=email,
        password="pwd12345",
        phone_number=_unique_phone(),
        is_staff=is_staff,
        send_activation_email=False,
    )

def make_dept(name: str, head: User = None) -> Department:
    """Создаёт отдел."""
    return Department.objects.create(name=name, head=head)

def make_role(dept: Department, name: str, perm_codes: list[str]) -> DepartmentRole:
    """Создаёт роль с указанными правами."""
    role = DepartmentRole.objects.create(department=dept, name=name)
    for code in perm_codes:
        perm, _ = DepartmentPermission.objects.get_or_create(
            code=code, defaults={"name": code}
        )
        role.scoped_permissions.add(perm)
    return role

def grant_assign_perm(user: User, dept: Department) -> DepartmentRole:
    """Даёт пользователю право assign_department_role в отделе."""
    role = make_role(dept, "Assigner", ["assign_department_role"])
    EmployeeDepartment.objects.create(employee=user, department=dept, role=role)
    RoleAssignment.objects.create(employee=user, role=role, is_active=True)
    return role

@pytest.fixture
def api_client() -> APIClient:
    return APIClient()

@pytest.mark.django_db
class TestRoleAssignmentEndpoints:
    """Тесты для /department-roles/{id}/assign/, revoke, assignments."""
    
    def test_assign_role_to_any_employee(self, api_client: APIClient):
        """Роль можно назначить любому сотруднику, не только члену отдела."""
        # Создаём admin, отдел и роль
        admin = make_user("admin@test.com", is_staff=True)
        dept = make_dept("IT")
        role = make_role(dept, "Developer", ["view_request"])
        
        # Создаём сотрудника НЕ в отделе
        other_user = make_user("other@test.com")
        
        # Проверяем что сотрудник не член отдела
        assert not EmployeeDepartment.objects.filter(
            employee=other_user, department=dept
        ).exists()
        
        # Назначаем роль
        api_client.force_authenticate(admin)
        url = f"/api/v1/department-roles/{role.id}/assign/"
        resp = api_client.post(url, {"employee_id": other_user.id})
        
        assert resp.status_code == status.HTTP_201_CREATED
        assert resp.data["employee_id"] == other_user.id
        assert resp.data["role_id"] == role.id
        assert resp.data["is_active"] is True
        
        # Проверяем что RoleAssignment создан
        assert RoleAssignment.objects.filter(
            employee=other_user, role=role, is_active=True
        ).exists()
    
    def test_revoke_role(self, api_client: APIClient):
        """Отзыв роли деактивирует RoleAssignment."""
        admin = make_user("admin@test.com", is_staff=True)
        dept = make_dept("IT")
        role = make_role(dept, "Developer", [])
        
        user = make_user("worker@test.com")
        
        # Назначаем роль
        assignment = RoleAssignment.objects.create(
            employee=user, role=role, is_active=True
        )
        
        # Отзываем
        api_client.force_authenticate(admin)
        url = f"/api/v1/department-roles/{role.id}/revoke/"
        resp = api_client.post(url, {"employee_id": user.id})
        
        assert resp.status_code == status.HTTP_204_NO_CONTENT
        
        # Проверяем что деактивировано
        assignment.refresh_from_db()
        assert assignment.is_active is False
    
    def test_assignments_list(self, api_client: APIClient):
        """Список назначений роли."""
        admin = make_user("admin@test.com", is_staff=True)
        dept = make_dept("IT")
        role = make_role(dept, "Developer", [])
        
        # Создаём несколько назначений
        user1 = make_user("worker1@test.com")
        user2 = make_user("worker2@test.com")
        
        RoleAssignment.objects.create(employee=user1, role=role, is_active=True)
        RoleAssignment.objects.create(employee=user2, role=role, is_active=False)
        
        api_client.force_authenticate(admin)
        
        # По умолчанию только активные
        url = f"/api/v1/department-roles/{role.id}/assignments/"
        resp = api_client.get(url)
        
        assert resp.status_code == status.HTTP_200_OK
        assert resp.data["count"] == 1
        assert resp.data["results"][0]["employee_id"] == user1.id
        
        # Все назначения
        resp = api_client.get(url + "?active=all")
        assert resp.data["count"] == 2
    
    def test_assign_requires_permission(self, api_client: APIClient):
        """Назначение требует право assign_department_role."""
        dept = make_dept("IT")
        role = make_role(dept, "Developer", [])
        
        # Пользователь без прав
        user = make_user("nopriv@test.com")
        
        other_user = make_user("other@test.com")
        
        api_client.force_authenticate(user)
        url = f"/api/v1/department-roles/{role.id}/assign/"
        resp = api_client.post(url, {"employee_id": other_user.id})
        
        assert resp.status_code == status.HTTP_403_FORBIDDEN
    
    def test_assign_with_dept_permission(self, api_client: APIClient):
        """Пользователь с assign_department_role может назначать роли."""
        dept = make_dept("IT")
        role = make_role(dept, "Developer", [])
        
        # Пользователь с правом
        user = make_user("assigner@test.com")
        grant_assign_perm(user, dept)
        
        other_user = make_user("other2@test.com")
        
        api_client.force_authenticate(user)
        url = f"/api/v1/department-roles/{role.id}/assign/"
        resp = api_client.post(url, {"employee_id": other_user.id})

        assert resp.status_code == status.HTTP_201_CREATED

    @override_settings(LDAP_ENABLED=True)
    def test_assign_and_revoke_trigger_ldap_sync(self, api_client: APIClient):
        with override_settings(LDAP_ENABLED=False):
            admin = make_user("admin-ldap@test.com", is_staff=True)
            dept = make_dept("IT LDAP")
            role = make_role(dept, "Developer LDAP", [])
            user = make_user("worker-ldap@test.com")

        api_client.force_authenticate(admin)
        url_assign = f"/api/v1/department-roles/{role.id}/assign/"
        url_revoke = f"/api/v1/department-roles/{role.id}/revoke/"

        with patch(
            "employees.signals.ldap.role.DepartmentService.sync_role_assignment_state"
        ) as mock_sync:
            assign_resp = api_client.post(url_assign, {"employee_id": user.id})
            revoke_resp = api_client.post(url_revoke, {"employee_id": user.id})

        assert assign_resp.status_code == status.HTTP_201_CREATED
        assert revoke_resp.status_code == status.HTTP_204_NO_CONTENT
        assert mock_sync.call_count >= 2
        first_call = mock_sync.call_args_list[0]
        second_call = mock_sync.call_args_list[1]
        assert first_call.kwargs["is_active"] is True
        assert second_call.kwargs["is_active"] is False

    def test_department_members_include_role_only_employees(self, api_client: APIClient):
        """members endpoint показывает сотрудников с ролью в отделе даже без membership."""
        admin = make_user("admin-members@test.com", is_staff=True)
        dept = make_dept("IT")
        role = make_role(dept, "Developer", [])
        role_only_user = make_user("role-only@test.com")

        RoleAssignment.objects.create(
            employee=role_only_user,
            role=role,
            is_active=True,
        )

        api_client.force_authenticate(admin)
        resp = api_client.get(f"/api/v1/departments/{dept.id}/members/")

        assert resp.status_code == status.HTTP_200_OK
        role_only_link = next(
            item
            for item in resp.data["results"]
            if item["employee"]["id"] == role_only_user.id
        )
        assert role_only_link["via_assignment"] is True
        assert role_only_link["is_active"] is True
        assert role_only_link["role"]["name"] == "Developer"

@pytest.mark.django_db
class TestRoleAssignmentPermissions:
    """Тесты для проверки прав через RoleAssignment."""
    
    def test_permission_check_via_role_assignment(self, api_client: APIClient):
        """Права проверяются через RoleAssignment, не требуя членства в отделе."""
        from api.v1.permissions import has_dept_perm
        
        dept = make_dept("IT")
        role = make_role(dept, "Manager", ["manage_department", "view_request"])
        
        user = make_user("manager@test.com")
        
        # Пользователь НЕ член отдела
        assert not EmployeeDepartment.objects.filter(
            employee=user, department=dept
        ).exists()
        
        # Но у него есть RoleAssignment
        RoleAssignment.objects.create(employee=user, role=role, is_active=True)
        
        # Проверяем права
        assert has_dept_perm(user, dept.id, "manage_department")
        assert has_dept_perm(user, dept.id, "view_request")
        assert not has_dept_perm(user, dept.id, "change_department_head")
    
    def test_inactive_assignment_does_not_grant_permission(self, api_client: APIClient):
        """Неактивное назначение не даёт прав."""
        from api.v1.permissions import has_dept_perm
        
        dept = make_dept("IT")
        role = make_role(dept, "Manager", ["manage_department"])
        
        user = make_user("manager2@test.com")
        
        # Неактивное назначение
        RoleAssignment.objects.create(employee=user, role=role, is_active=False)
        
        assert not has_dept_perm(user, dept.id, "manage_department")
