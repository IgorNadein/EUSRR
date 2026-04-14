from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
from django.contrib.auth import get_user_model

from employees.ldap.services.department_service import DepartmentService
from employees.models import Department, DepartmentRole, EmployeeDepartment, LdapSyncState

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
