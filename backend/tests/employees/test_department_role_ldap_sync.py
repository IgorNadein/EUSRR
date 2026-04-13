from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from employees.ldap.services.department_service import DepartmentService
from employees.models import Department, DepartmentRole


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
