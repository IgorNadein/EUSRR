from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model

from employees.ldap.repositories.employee_repository import bind_user_department
from employees.ldap.services.department_service import DepartmentService
from employees.models import (
    Department,
    DepartmentRole,
    EmployeeDepartment,
    LdapSyncState,
    RoleAssignment,
)

User = get_user_model()


@pytest.mark.django_db
def test_sync_role_state_nests_role_group_into_department_group():
    dept = Department.objects.create(name="LDAP Dept")
    role = DepartmentRole.objects.create(department=dept, name="Reviewer")
    dept_dn = "OU=LDAP Dept,OU=Departments,DC=example,DC=local"
    role_group_dn = "CN=ROLE_Reviewer,OU=LDAP Dept,OU=Departments,DC=example,DC=local"
    fake_group = SimpleNamespace(member=[], save=MagicMock())

    def ensure_role_group_side_effect(role_obj):
        DepartmentRole.objects.filter(pk=role_obj.pk).update(
            ldap_group_dn=role_group_dn
        )
        role_obj.ldap_group_dn = role_group_dn
        return role_group_dn

    with patch.object(
        DepartmentService,
        "_get_department_dn",
        return_value=dept_dn,
    ), patch.object(
        DepartmentService,
        "_ensure_role_group",
        side_effect=ensure_role_group_side_effect,
    ), patch.object(
        DepartmentService,
        "_ensure_department_group",
        return_value=f"CN=DEP_{dept.name},{dept_dn}",
    ), patch(
        "employees.ldap.services.department_service.LdapOrganizationalUnitGroup.objects.get",
        return_value=fake_group,
    ):
        DepartmentService().sync_role_state(role)

    assert fake_group.member == [role_group_dn]
    fake_group.save.assert_called_once()


@pytest.mark.django_db
def test_reconcile_department_group_keeps_members_and_multiple_role_groups():
    dept = Department.objects.create(name="LDAP Dept Aggregate")
    role1 = DepartmentRole.objects.create(
        department=dept,
        name="Reviewer",
        ldap_group_dn="CN=ROLE_Reviewer,OU=LDAP Dept Aggregate,OU=Departments,DC=example,DC=local",
    )
    role2 = DepartmentRole.objects.create(
        department=dept,
        name="Approver",
        ldap_group_dn="CN=ROLE_Approver,OU=LDAP Dept Aggregate,OU=Departments,DC=example,DC=local",
    )
    employee = User.objects.create(
        email="dept-role-aggregate@example.com",
        phone_number="+79990009999",
        first_name="Role",
        last_name="Aggregate",
        is_active=True,
        email_verified=True,
    )
    employee.set_password("pass")
    employee.save()
    EmployeeDepartment.objects.create(
        employee=employee,
        department=dept,
        is_active=True,
    )
    LdapSyncState.objects.create(
        model="employee",
        object_pk=str(employee.pk),
        ldap_dn="CN=Test User,OU=LDAP Dept Aggregate,OU=Departments,DC=example,DC=local",
    )
    fake_group = SimpleNamespace(member=[], save=MagicMock())

    with patch.object(
        DepartmentService,
        "_ensure_department_group",
        return_value="CN=DEP_LDAP Dept Aggregate,OU=LDAP Dept Aggregate,OU=Departments,DC=example,DC=local",
    ), patch(
        "employees.ldap.services.department_service.LdapOrganizationalUnitGroup.objects.get",
        return_value=fake_group,
    ):
        DepartmentService()._reconcile_department_group(
            dept,
            "OU=LDAP Dept Aggregate,OU=Departments,DC=example,DC=local",
        )

    assert fake_group.member[0] == (
        "CN=Test User,OU=LDAP Dept Aggregate,OU=Departments,DC=example,DC=local"
    )
    assert set(fake_group.member[1:]) == {role1.ldap_group_dn, role2.ldap_group_dn}
    fake_group.save.assert_called_once()


@pytest.mark.django_db
def test_reconcile_department_group_skips_inactive_employee_with_active_link():
    dept = Department.objects.create(name="LDAP Dept Inactive Guard")
    active_employee = User.objects.create(
        email="active-aggregate@example.com",
        phone_number="+79990001001",
        first_name="Active",
        last_name="Member",
        is_active=True,
        email_verified=True,
    )
    inactive_employee = User.objects.create(
        email="inactive-aggregate@example.com",
        phone_number="+79990001002",
        first_name="Inactive",
        last_name="Member",
        is_active=False,
        email_verified=True,
    )
    EmployeeDepartment.objects.create(
        employee=active_employee,
        department=dept,
        is_active=True,
    )
    EmployeeDepartment.objects.create(
        employee=inactive_employee,
        department=dept,
        is_active=True,
    )
    active_dn = "CN=Active,OU=LDAP Dept Inactive Guard,OU=Departments,DC=example,DC=local"
    inactive_dn = "CN=Inactive,OU=LDAP Dept Inactive Guard,OU=Departments,DC=example,DC=local"
    LdapSyncState.objects.create(
        model="employee",
        object_pk=str(active_employee.pk),
        ldap_dn=active_dn,
    )
    LdapSyncState.objects.create(
        model="employee",
        object_pk=str(inactive_employee.pk),
        ldap_dn=inactive_dn,
    )
    fake_group = SimpleNamespace(member=[], save=MagicMock())

    with patch.object(
        DepartmentService,
        "_ensure_department_group",
        return_value=(
            "CN=DEP_LDAP Dept Inactive Guard,"
            "OU=LDAP Dept Inactive Guard,OU=Departments,DC=example,DC=local"
        ),
    ), patch(
        "employees.ldap.services.department_service.LdapOrganizationalUnitGroup.objects.get",
        return_value=fake_group,
    ):
        DepartmentService()._reconcile_department_group(
            dept,
            "OU=LDAP Dept Inactive Guard,OU=Departments,DC=example,DC=local",
        )

    assert active_dn in fake_group.member
    assert inactive_dn not in fake_group.member
    fake_group.save.assert_called_once()


@pytest.mark.django_db
def test_resolve_member_roles_returns_no_roles_for_inactive_employee():
    dept = Department.objects.create(name="LDAP Role Inactive Guard")
    role = DepartmentRole.objects.create(department=dept, name="Reviewer")
    employee = User.objects.create(
        email="inactive-role-member@example.com",
        phone_number="+79990001003",
        first_name="Inactive",
        last_name="Role",
        is_active=False,
        email_verified=True,
    )
    EmployeeDepartment.objects.create(
        employee=employee,
        department=dept,
        role=role,
        is_active=True,
    )
    RoleAssignment.objects.create(
        employee=employee,
        role=role,
        is_active=True,
    )

    assert DepartmentService()._resolve_member_roles(employee, dept) == []


@pytest.mark.django_db
def test_bind_user_department_deactivates_links_for_inactive_employee():
    old_dept = Department.objects.create(name="Old LDAP Dept")
    inactive_employee = User.objects.create(
        email="inactive-import@example.com",
        phone_number="+79990001004",
        first_name="Inactive",
        last_name="Import",
        is_active=False,
        email_verified=True,
    )
    old_link = EmployeeDepartment.objects.create(
        employee=inactive_employee,
        department=old_dept,
        is_active=True,
    )

    bind_user_department(
        inactive_employee,
        "CN=Inactive Import,OU=New LDAP Dept,OU=Departments,DC=example,DC=local",
    )

    old_link.refresh_from_db()
    assert old_link.is_active is False
    assert not Department.objects.filter(name="New LDAP Dept").exists()
