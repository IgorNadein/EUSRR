from __future__ import annotations

import pytest
from django.conf import settings
from django.contrib.auth.models import Group
from rest_framework.test import APIClient

from employees.ldap import (
    DepartmentService,
    LdapGroup,
    LdapOrganizationalUnit,
    LdapOrganizationalUnitGroup,
    LdapUser,
)
from employees.models import Department, DepartmentRole, LdapSyncState, Position

"""
Живой LDAP integration-suite.

Запускать под обычными settings, а не settings_test:
    LDAP_ENABLED=true LDAP_WRITE_ENABLED=true \
    .venv/bin/python -m pytest \
    -q -o addopts='' --ds=eusrr_backend.settings \
    tests/manual/ldap_integration/test_entities_roundtrip.py
"""

pytestmark = [
    pytest.mark.manual,
    pytest.mark.integration,
    pytest.mark.django_db(transaction=True, databases=["default", "ldap"]),
]

TINY_PNG_BASE64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk"
    "+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
)


def _employee_dn(employee) -> str:
    return LdapSyncState.objects.get(
        model="employee", object_pk=str(employee.pk)
    ).ldap_dn


def _department_dn(department: Department) -> str:
    return LdapSyncState.objects.get(
        model="department", object_pk=str(department.pk)
    ).ldap_dn


def _norm_dn(value: str | None) -> str:
    return (value or "").lower()


def _bootstrap_department_for_role_tests(name: str) -> Department:
    return Department.objects.create(
        name=name,
        description="Bootstrapped for role tests",
    )


def test_employee_profile_patch_updates_live_ldap(
    ensure_live_ldap, create_ldap_user
):
    user = create_ldap_user(first_name="Manual", last_name="Employee")
    client = APIClient()
    client.force_authenticate(user=user)

    response = client.patch(
        "/api/v1/employees/me/",
        {
            "first_name": "Updated",
            "last_name": "Renamed",
            "email": f"updated-{user.pk}@example.com",
            "phone_number": "+79995554433",
            "avatar": f"data:image/png;base64,{TINY_PNG_BASE64}",
        },
        format="json",
    )

    assert response.status_code == 200, response.content

    ldap_user = LdapUser.objects.get(dn=_employee_dn(user))
    assert ldap_user.given_name == "Updated"
    assert ldap_user.sn == "Renamed"
    assert ldap_user.mail == f"updated-{user.pk}@example.com"
    assert ldap_user.telephone_number == "+79995554433"
    assert bool(ldap_user.thumbnail_photo) is True


def test_department_api_roundtrip_syncs_ou_head_and_membership(
    ensure_live_ldap,
    superuser_client,
    create_ldap_user,
    ldap_cleanup,
    unique_name,
):
    head = create_ldap_user(first_name="Head", last_name="Dept")
    member = create_ldap_user(first_name="Member", last_name="Dept")
    dept_name = unique_name("qa-dept")

    create_response = superuser_client.post(
        "/api/v1/departments/",
        {"name": dept_name, "description": "Initial department"},
        format="json",
    )
    assert create_response.status_code == 201, create_response.content

    department = Department.objects.get(pk=create_response.json()["id"])
    ldap_cleanup(_department_dn(department))

    ou = LdapOrganizationalUnit.objects.get(dn=_department_dn(department))
    assert ou.ou == dept_name
    assert ou.description == "Initial department"

    dept_group = LdapOrganizationalUnitGroup.objects.get(dn=department.ldap_group_dn)
    assert dept_group.cn == f"DEP_{dept_name}"

    set_head = superuser_client.post(
        f"/api/v1/departments/{department.pk}/set_head/",
        {"head_id": head.pk},
        format="json",
    )
    assert set_head.status_code == 200, set_head.content

    ou = LdapOrganizationalUnit.objects.get(dn=_department_dn(department))
    assert _norm_dn(ou.managed_by) == _norm_dn(_employee_dn(head))

    add_member = superuser_client.post(
        f"/api/v1/departments/{department.pk}/add_member/",
        {"employee_id": member.pk},
        format="json",
    )
    assert add_member.status_code == 200, add_member.content

    dept_group = LdapOrganizationalUnitGroup.objects.get(dn=department.ldap_group_dn)
    member_dns = {_norm_dn(dn) for dn in list(dept_group.member or [])}
    assert _norm_dn(_employee_dn(member)) in member_dns

    rename_response = superuser_client.patch(
        f"/api/v1/departments/{department.pk}/",
        {"name": f"{dept_name}-renamed", "description": "Renamed department"},
        format="json",
    )
    assert rename_response.status_code == 200, rename_response.content

    old_dept_dn = f"OU={dept_name},{settings.LDAP_DEPARTMENTS_BASE}"
    department.refresh_from_db()
    renamed_dn = _department_dn(department)
    ldap_cleanup(renamed_dn)
    renamed_ou = LdapOrganizationalUnit.objects.get(dn=renamed_dn)
    assert renamed_ou.ou == f"{dept_name}-renamed"
    assert renamed_ou.description == "Renamed department"
    assert department.ldap_group_dn == (
        f"CN=DEP_{dept_name}-renamed,{renamed_dn}"
    )
    assert not LdapOrganizationalUnitGroup.objects.filter(
        dn=f"CN=DEP_{dept_name},{old_dept_dn}"
    ).exists()
    renamed_group = LdapOrganizationalUnitGroup.objects.get(
        dn=department.ldap_group_dn
    )
    assert renamed_group.cn == f"DEP_{dept_name}-renamed"
    renamed_member_dns = {_norm_dn(dn) for dn in list(renamed_group.member or [])}
    assert _norm_dn(_employee_dn(member)) in renamed_member_dns

    remove_member = superuser_client.post(
        f"/api/v1/departments/{department.pk}/remove_member/",
        {"employee_id": member.pk},
        format="json",
    )
    assert remove_member.status_code == 200, remove_member.content

    renamed_group = LdapOrganizationalUnitGroup.objects.get(
        dn=department.ldap_group_dn
    )
    renamed_member_dns = {_norm_dn(dn) for dn in list(renamed_group.member or [])}
    assert _norm_dn(_employee_dn(member)) not in renamed_member_dns


def test_group_api_roundtrip_syncs_live_ldap(
    ensure_live_ldap,
    superuser_client,
    create_ldap_user,
    ldap_cleanup,
    unique_name,
):
    member = create_ldap_user(first_name="Member", last_name="Group")
    group_name = unique_name("qa-group")
    group_dn = f"CN={group_name},{settings.LDAP_GROUPS_BASE}"
    ldap_cleanup(group_dn)

    create_response = superuser_client.post(
        "/api/v1/groups/",
        {
            "name": group_name,
            "ldap_description": "Initial LDAP group",
        },
        format="json",
    )
    assert create_response.status_code == 201, create_response.content

    ldap_group = LdapGroup.objects.get(dn=group_dn)
    assert ldap_group.description == "Initial LDAP group"

    add_members = superuser_client.post(
        f"/api/v1/groups/{create_response.json()['id']}/add-members/",
        {"member_ids": [member.pk]},
        format="json",
    )
    assert add_members.status_code == 200, add_members.content

    ldap_group = LdapGroup.objects.get(dn=group_dn)
    member_dns = {_norm_dn(dn) for dn in list(ldap_group.member or [])}
    assert _norm_dn(_employee_dn(member)) in member_dns

    rename_response = superuser_client.post(
        f"/api/v1/groups/{create_response.json()['id']}/rename/",
        {"new_name": f"{group_name}-renamed"},
        format="json",
    )
    assert rename_response.status_code == 200, rename_response.content

    renamed_dn = f"CN={group_name}-renamed,{settings.LDAP_GROUPS_BASE}"
    ldap_cleanup(renamed_dn)
    renamed_group = LdapGroup.objects.get(dn=renamed_dn)
    assert renamed_group.cn == f"{group_name}-renamed"

    description_response = superuser_client.post(
        f"/api/v1/groups/{create_response.json()['id']}/set-description/",
        {"description": "Updated LDAP description"},
        format="json",
    )
    assert description_response.status_code == 200, description_response.content

    renamed_group = LdapGroup.objects.get(dn=renamed_dn)
    assert renamed_group.description == "Updated LDAP description"

    remove_members = superuser_client.post(
        f"/api/v1/groups/{create_response.json()['id']}/remove-members/",
        {"member_ids": [member.pk]},
        format="json",
    )
    assert remove_members.status_code == 200, remove_members.content

    renamed_group = LdapGroup.objects.get(dn=renamed_dn)
    renamed_member_dns = {_norm_dn(dn) for dn in list(renamed_group.member or [])}
    assert _norm_dn(_employee_dn(member)) not in renamed_member_dns


def test_position_api_roundtrip_syncs_pos_group_and_nesting(
    ensure_live_ldap,
    superuser_client,
    ldap_cleanup,
    unique_name,
):
    target_group_name = unique_name("qa-target")
    target_group_dn = f"CN={target_group_name},{settings.LDAP_GROUPS_BASE}"
    ldap_cleanup(target_group_dn)

    group_response = superuser_client.post(
        "/api/v1/groups/",
        {
            "name": target_group_name,
            "ldap_description": "Target container group",
        },
        format="json",
    )
    assert group_response.status_code == 201, group_response.content
    target_group = Group.objects.get(pk=group_response.json()["id"])

    position_name = unique_name("qa-position")
    create_position = superuser_client.post(
        "/api/v1/positions/",
        {"name": position_name, "description": "Position description"},
        format="json",
    )
    assert create_position.status_code == 201, create_position.content

    position = Position.objects.get(pk=create_position.json()["id"])
    ldap_cleanup(position.ldap_group_dn)
    pos_group = LdapGroup.objects.get(dn=position.ldap_group_dn)
    assert pos_group.cn == f"POS_{position_name}"

    set_groups = superuser_client.post(
        f"/api/v1/positions/{position.pk}/set_groups/",
        {"groups": [target_group.pk]},
        format="json",
    )
    assert set_groups.status_code == 200, set_groups.content

    target_ldap_group = LdapGroup.objects.get(dn=target_group_dn)
    target_member_dns = {_norm_dn(dn) for dn in list(target_ldap_group.member or [])}
    assert _norm_dn(position.ldap_group_dn) in target_member_dns

    rename_position = superuser_client.patch(
        f"/api/v1/positions/{position.pk}/",
        {"name": f"{position_name}-renamed"},
        format="json",
    )
    assert rename_position.status_code == 200, rename_position.content

    position.refresh_from_db()
    ldap_cleanup(position.ldap_group_dn)
    renamed_pos_group = LdapGroup.objects.get(dn=position.ldap_group_dn)
    assert renamed_pos_group.cn == f"POS_{position_name}-renamed"


def test_department_role_service_roundtrip_syncs_live_ldap(
    ensure_live_ldap,
    create_ldap_user,
    ldap_cleanup,
    unique_name,
):
    service = DepartmentService()
    employee = create_ldap_user(first_name="Role", last_name="Member")
    department = _bootstrap_department_for_role_tests(unique_name("qa-role-dept"))
    ldap_cleanup(_department_dn(department))

    role = service.create_role(
        department=department,
        name="Operator",
        description="Operators",
    )
    ldap_cleanup(role.ldap_group_dn)
    role_group = LdapOrganizationalUnitGroup.objects.get(dn=role.ldap_group_dn)
    assert role_group.cn == "ROLE_Operator"

    assignment = service.assign_role(employee, role, assigned_by=None)
    assert assignment.is_active is True
    role_group = LdapOrganizationalUnitGroup.objects.get(dn=role.ldap_group_dn)
    role_member_dns = {_norm_dn(dn) for dn in list(role_group.member or [])}
    assert _norm_dn(_employee_dn(employee)) in role_member_dns

    updated_role = service.update_role(role, {"name": "Lead Operator"})
    ldap_cleanup(updated_role.ldap_group_dn)
    renamed_group = LdapOrganizationalUnitGroup.objects.get(dn=updated_role.ldap_group_dn)
    assert renamed_group.cn == "ROLE_Lead_Operator"

    service.revoke_role(employee, updated_role)
    assignment.refresh_from_db()
    assert assignment.is_active is False
    renamed_group = LdapOrganizationalUnitGroup.objects.get(dn=updated_role.ldap_group_dn)
    renamed_role_member_dns = {_norm_dn(dn) for dn in list(renamed_group.member or [])}
    assert _norm_dn(_employee_dn(employee)) not in renamed_role_member_dns

    service.delete_role(updated_role)
    assert not DepartmentRole.objects.filter(pk=updated_role.pk).exists()
    assert not LdapOrganizationalUnitGroup.objects.filter(dn=updated_role.ldap_group_dn).exists()
