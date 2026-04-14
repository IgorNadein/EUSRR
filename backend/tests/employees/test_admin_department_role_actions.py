import hashlib
from unittest.mock import Mock, call, patch

import pytest
from django.contrib import messages
from django.contrib.admin.sites import AdminSite
from django.test import RequestFactory

from employees.admin import DepartmentRoleAdmin
from employees.models import Department, DepartmentRole, Employee


def make_user(email: str, *, staff: bool = True, superuser: bool = True):
    suffix = int(hashlib.sha256(email.encode("utf-8")).hexdigest(), 16) % 10**9
    return Employee.objects.create_user(
        email=email,
        password="pwd12345",
        phone_number=f"+79{suffix:09d}",
        is_staff=staff,
        is_superuser=superuser,
        send_activation_email=False,
    )


@pytest.mark.django_db
def test_department_role_admin_sync_to_ldap_calls_service_for_each_role():
    request = RequestFactory().post("/admin/employees/departmentrole/")
    request.user = make_user("admin-sync-roles@example.com")

    dept = Department.objects.create(name="Dept Admin Sync")
    role_a = DepartmentRole.objects.create(department=dept, name="Role A")
    role_b = DepartmentRole.objects.create(department=dept, name="Role B")

    model_admin = DepartmentRoleAdmin(DepartmentRole, AdminSite())
    model_admin.message_user = Mock()

    with patch(
        "employees.ldap.services.department_service.DepartmentService.sync_role_state"
    ) as sync_role_state:
        model_admin.sync_to_ldap(
            request,
            DepartmentRole.objects.filter(pk__in=[role_a.pk, role_b.pk]).order_by(
                "pk"
            ),
        )

    assert sync_role_state.call_args_list == [call(role_a), call(role_b)]
    model_admin.message_user.assert_called_once_with(
        request,
        "Успешно пересинхронизировано ролей: 2",
        level=messages.SUCCESS,
    )


@pytest.mark.django_db
def test_department_role_admin_sync_to_ldap_reports_errors():
    request = RequestFactory().post("/admin/employees/departmentrole/")
    request.user = make_user("admin-sync-role-errors@example.com")

    dept = Department.objects.create(name="Dept Admin Sync Errors")
    ok_role = DepartmentRole.objects.create(department=dept, name="Ok Role")
    bad_role = DepartmentRole.objects.create(
        department=dept,
        name="Bad Role",
    )

    model_admin = DepartmentRoleAdmin(DepartmentRole, AdminSite())
    model_admin.message_user = Mock()

    def side_effect(role):
        if role.pk == bad_role.pk:
            raise RuntimeError("LDAP unavailable")

    with patch(
        "employees.ldap.services.department_service.DepartmentService.sync_role_state",
        side_effect=side_effect,
    ) as sync_role_state:
        model_admin.sync_to_ldap(
            request,
            DepartmentRole.objects.filter(pk__in=[ok_role.pk, bad_role.pk]).order_by(
                "pk"
            ),
        )

    assert sync_role_state.call_args_list == [call(ok_role), call(bad_role)]
    assert model_admin.message_user.call_count == 3
    model_admin.message_user.assert_has_calls(
        [
            call(
                request,
                "Ошибка синхронизации роли "
                "«Bad Role» (Dept Admin Sync Errors): LDAP unavailable",
                level=messages.ERROR,
            ),
            call(
                request,
                "Успешно пересинхронизировано ролей: 1",
                level=messages.SUCCESS,
            ),
            call(
                request,
                "Ошибок синхронизации ролей: 1",
                level=messages.WARNING,
            ),
        ]
    )
