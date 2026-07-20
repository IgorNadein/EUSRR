import pytest
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import PermissionDenied
from django.test import RequestFactory
from django.urls import reverse

from finance.admin import (
    EmployeePayRateAdmin,
    PayrollAuditEventAdmin,
    PayrollPeriodAdmin,
    PayrollStatementAdmin,
)
from finance.models import (
    EmployeePayRate,
    PayrollAuditEvent,
    PayrollDailyWorkEntry,
    PayrollPeriod,
    PayrollRun,
    PayrollStatement,
    PayrollWorkRecord,
)

pytestmark = pytest.mark.django_db


@pytest.fixture(autouse=True)
def use_granular_policy_by_default(settings):
    """Keep legacy permission assertions explicit while the app defaults simple."""

    settings.FINANCE_PAYROLL = {"SIMPLE_ADMIN_ACCESS": False}


def grant(user, *codenames):
    permissions = Permission.objects.filter(
        content_type__app_label="finance",
        codename__in=codenames,
    )
    assert permissions.count() == len(codenames)
    user.user_permissions.add(*permissions)
    for cache_name in ("_perm_cache", "_user_perm_cache", "_group_perm_cache"):
        if hasattr(user, cache_name):
            delattr(user, cache_name)


def admin_request(user):
    request = RequestFactory().get("/admin/finance/")
    request.user = user
    return request


def test_superuser_has_unrestricted_finance_admin_permissions(user_factory):
    superuser = user_factory(
        email="payroll.superuser@example.test",
        staff=True,
        superuser=True,
    )
    manager = user_factory(email="payroll.manager@example.test", staff=True)
    grant(manager, "manage_payroll_inputs")
    superuser_request = admin_request(superuser)
    manager_request = admin_request(manager)
    period_admin = PayrollPeriodAdmin(PayrollPeriod, admin.site)

    assert period_admin.has_module_permission(superuser_request) is True
    assert period_admin.has_view_permission(superuser_request) is True
    assert period_admin.has_add_permission(superuser_request) is True
    assert period_admin.has_change_permission(superuser_request) is True
    assert period_admin.has_delete_permission(superuser_request) is True
    assert "delete_selected" in period_admin.get_actions(superuser_request)

    assert period_admin.has_delete_permission(manager_request) is False
    assert "delete_selected" not in period_admin.get_actions(manager_request)
    assert EmployeePayRateAdmin(
        EmployeePayRate,
        admin.site,
    ).has_delete_permission(superuser_request) is True
    assert PayrollStatementAdmin(
        PayrollStatement,
        admin.site,
    ).has_delete_permission(superuser_request) is True
    assert PayrollAuditEventAdmin(
        PayrollAuditEvent,
        admin.site,
    ).has_delete_permission(superuser_request) is True


def test_period_admin_confirms_and_cascades_related_payroll_objects(user_factory):
    superuser = user_factory(
        email="payroll.delete@example.test",
        staff=True,
        superuser=True,
    )
    employee = user_factory(email="payroll.delete.employee@example.test")
    period = PayrollPeriod.objects.create(
        code="2026-03",
        name="Март 2026",
        date_from="2026-03-01",
        date_to="2026-03-31",
        pay_date="2026-04-05",
        created_by=superuser,
    )
    daily_entry = PayrollDailyWorkEntry.objects.create(
        period=period,
        employee=employee,
        work_date="2026-03-02",
        target_points="5",
        actual_points="4",
    )
    work_record = PayrollWorkRecord.objects.create(
        period=period,
        employee=employee,
        target_points="105",
        actual_points="84",
        created_by=superuser,
    )
    replacement_work_record = PayrollWorkRecord.objects.create(
        period=period,
        employee=employee,
        target_points="105",
        actual_points="90",
        revision=2,
        replaces=work_record,
        reason="Уточнение выработки",
        created_by=superuser,
    )
    run = PayrollRun.objects.create(
        period=period,
        revision=1,
        ruleset_id="test",
        ruleset_version="1",
        ruleset_hash="rules",
        calculator_version="test",
        input_hash="input",
        result_hash="result",
        requested_by=superuser,
    )
    replacement_run = PayrollRun.objects.create(
        period=period,
        revision=2,
        supersedes=run,
        recalculation_reason="Уточнение исходных данных",
        ruleset_id="test",
        ruleset_version="1",
        ruleset_hash="rules",
        calculator_version="test",
        input_hash="input-2",
        result_hash="result-2",
        requested_by=superuser,
    )
    period.refresh_from_db()
    period.current_run = replacement_run
    period.save(update_fields=["current_run"])
    audit_event = PayrollAuditEvent.objects.create(
        actor=superuser,
        action="payroll.period_created",
        object_type="finance.payrollperiod",
        object_id=str(period.pk),
        period=period,
    )

    model_admin = PayrollPeriodAdmin(PayrollPeriod, admin.site)
    request = admin_request(superuser)
    deleted_objects, model_count, perms_needed, protected = (
        model_admin.get_deleted_objects([period], request)
    )

    assert deleted_objects
    assert model_count[PayrollDailyWorkEntry._meta.verbose_name_plural] == 1
    assert model_count[PayrollWorkRecord._meta.verbose_name_plural] == 2
    assert model_count[PayrollRun._meta.verbose_name_plural] == 2
    assert model_count[PayrollAuditEvent._meta.verbose_name_plural] == 1
    assert perms_needed == set()
    assert protected == []

    period.delete()

    assert not PayrollPeriod.objects.filter(pk=period.pk).exists()
    assert not PayrollDailyWorkEntry.objects.filter(pk=daily_entry.pk).exists()
    assert not PayrollWorkRecord.objects.filter(pk=work_record.pk).exists()
    assert not PayrollWorkRecord.objects.filter(
        pk=replacement_work_record.pk,
    ).exists()
    assert not PayrollRun.objects.filter(pk=run.pk).exists()
    assert not PayrollRun.objects.filter(pk=replacement_run.pk).exists()
    assert not PayrollAuditEvent.objects.filter(pk=audit_event.pk).exists()


def test_simple_mode_staff_can_open_and_edit_any_payroll_draft(
    settings,
    user_factory,
):
    settings.FINANCE_PAYROLL = {"SIMPLE_ADMIN_ACCESS": True}
    administrator = user_factory(email="simple.admin@example.test", staff=True)
    creator = user_factory(email="simple.creator@example.test")
    employee = user_factory(email="simple.employee@example.test")
    rate = EmployeePayRate.objects.create(
        employee=employee,
        amount="80000",
        effective_from="2026-01-01",
        created_by=creator,
    )
    model_admin = EmployeePayRateAdmin(EmployeePayRate, admin.site)
    request = admin_request(administrator)

    assert model_admin.has_module_permission(request) is True
    assert model_admin.has_add_permission(request) is True
    assert "amount" not in model_admin.get_readonly_fields(request, rate)


def test_standard_model_permission_does_not_expose_all_statements(user_factory):
    staff = user_factory(email="generic.admin@example.test", staff=True)
    grant(staff, "view_payrollstatement")
    model_admin = PayrollStatementAdmin(PayrollStatement, admin.site)
    request = admin_request(staff)

    assert model_admin.has_module_permission(request) is False
    assert model_admin.has_view_permission(request) is False

    grant(staff, "view_all_payroll")
    assert model_admin.has_module_permission(request) is True
    assert model_admin.has_view_permission(request) is True


def test_audit_requires_dedicated_audit_permission(user_factory):
    staff = user_factory(email="audit.admin@example.test", staff=True)
    grant(staff, "view_payrollauditevent", "view_all_payroll")
    model_admin = PayrollAuditEventAdmin(PayrollAuditEvent, admin.site)
    request = admin_request(staff)

    assert model_admin.has_view_permission(request) is False

    grant(staff, "audit_payroll")
    assert model_admin.has_view_permission(request) is True


def test_approver_can_review_but_not_edit_another_users_draft(
    user_factory,
):
    creator = user_factory(email="draft.creator@example.test", staff=True)
    approver = user_factory(email="draft.approver@example.test", staff=True)
    employee = user_factory(email="draft.employee@example.test")
    grant(creator, "manage_payroll_inputs")
    grant(approver, "approve_payroll_inputs")
    rate = EmployeePayRate.objects.create(
        employee=employee,
        amount="80000",
        effective_from="2026-01-01",
        created_by=creator,
    )
    model_admin = EmployeePayRateAdmin(EmployeePayRate, admin.site)

    creator_readonly = model_admin.get_readonly_fields(
        admin_request(creator),
        rate,
    )
    approver_readonly = model_admin.get_readonly_fields(
        admin_request(approver),
        rate,
    )
    concrete_fields = {field.name for field in rate._meta.concrete_fields}

    assert "amount" not in creator_readonly
    assert concrete_fields.issubset(set(approver_readonly))
    assert model_admin.has_delete_permission(admin_request(creator), rate) is False


def test_view_or_approval_role_cannot_edit_own_draft_without_manage_permission(
    user_factory,
):
    approver = user_factory(email="own.draft.approver@example.test", staff=True)
    employee = user_factory(email="own.draft.employee@example.test")
    grant(approver, "approve_payroll_inputs")
    rate = EmployeePayRate.objects.create(
        employee=employee,
        amount="80000",
        effective_from="2026-01-01",
        created_by=approver,
    )
    model_admin = EmployeePayRateAdmin(EmployeePayRate, admin.site)
    request = admin_request(approver)
    concrete_fields = {field.name for field in rate._meta.concrete_fields}

    assert concrete_fields.issubset(set(model_admin.get_readonly_fields(request, rate)))
    with pytest.raises(PermissionDenied):
        model_admin.save_model(request, rate, form=None, change=True)


def test_stale_maker_form_cannot_reopen_an_approved_rate(user_factory):
    creator = user_factory(email="race.creator@example.test", staff=True)
    approver = user_factory(email="race.approver@example.test", staff=True)
    employee = user_factory(email="race.employee@example.test")
    grant(creator, "manage_payroll_inputs")
    grant(approver, "approve_payroll_inputs")
    rate = EmployeePayRate.objects.create(
        employee=employee,
        amount="80000",
        effective_from="2026-01-01",
        created_by=creator,
    )
    stale_form_instance = EmployeePayRate.objects.get(pk=rate.pk)
    from finance.payroll.services import approve_pay_rate

    approve_pay_rate(
        rate.pk,
        actor=approver,
        expected_lock_version=rate.lock_version,
    )
    stale_form_instance.amount = "800000"
    model_admin = EmployeePayRateAdmin(EmployeePayRate, admin.site)

    with pytest.raises(PermissionDenied):
        model_admin.save_model(
            admin_request(creator),
            stale_form_instance,
            form=None,
            change=True,
        )

    rate.refresh_from_db()
    assert rate.status == "approved"
    assert str(rate.amount) == "80000.0000"


def test_approval_action_shows_and_posts_the_reviewed_draft_version(user_factory):
    creator = user_factory(email="confirm.creator@example.test", staff=True)
    approver = user_factory(email="confirm.approver@example.test", staff=True)
    employee = user_factory(email="confirm.employee@example.test")
    grant(approver, "approve_payroll_inputs")
    rate = EmployeePayRate.objects.create(
        employee=employee,
        amount="80000",
        effective_from="2026-01-01",
        created_by=creator,
    )
    request = RequestFactory().post(
        "/admin/finance/employeepayrate/",
        {
            "action": "approve_selected",
            "_selected_action": [rate.pk],
        },
    )
    request.user = approver
    model_admin = EmployeePayRateAdmin(EmployeePayRate, admin.site)

    response = model_admin.approve_selected(
        request,
        EmployeePayRate.objects.filter(pk=rate.pk),
    )
    rendered = response.rendered_content

    assert "Утвердить показанные версии" in rendered
    assert f'name="lock_version_{rate.pk}"' in rendered
    assert f'value="{rate.lock_version}"' in rendered

    confirm = RequestFactory().post(
        "/admin/finance/employeepayrate/",
        {
            "action": "approve_selected",
            "_selected_action": [rate.pk],
            "confirm_payroll_approval": "1",
            f"lock_version_{rate.pk}": str(rate.lock_version),
        },
    )
    confirm.user = approver
    confirm.session = {}
    confirm._messages = FallbackStorage(confirm)
    model_admin.approve_selected(
        confirm,
        EmployeePayRate.objects.filter(pk=rate.pk),
    )

    rate.refresh_from_db()
    assert rate.status == "approved"


def test_two_admin_tabs_cannot_silently_overwrite_a_newer_draft(
    client,
    user_factory,
):
    creator = user_factory(email="tabs.creator@example.test", staff=True)
    employee = user_factory(email="tabs.employee@example.test")
    grant(creator, "manage_payroll_inputs")
    rate = EmployeePayRate.objects.create(
        employee=employee,
        amount="80000",
        point_rate="100",
        currency="RUB",
        effective_from="2026-01-01",
        created_by=creator,
    )
    client.force_login(creator)
    url = reverse("admin:finance_employeepayrate_change", args=[rate.pk])
    first_tab = client.get(url)
    second_tab = client.get(url)
    assert first_tab.status_code == 200
    assert second_tab.status_code == 200
    first_version = first_tab.context["adminform"].form.initial["expected_lock_version"]
    second_version = second_tab.context["adminform"].form.initial[
        "expected_lock_version"
    ]
    assert first_version == second_version == 0

    def form_data(amount, expected_version):
        return {
            "employee": str(employee.pk),
            "rate_code": "BASE",
            "amount": amount,
            "point_rate": "100",
            "currency": "RUB",
            "effective_from": "2026-01-01",
            "revision": "1",
            "replaces": "",
            "reason": "",
            "source": "manual",
            "source_ref": "",
            "expected_lock_version": str(expected_version),
            "_save": "Сохранить",
        }

    first_save = client.post(url, form_data("81000", first_version))
    assert first_save.status_code == 302
    rate.refresh_from_db()
    assert rate.amount == 81000
    assert rate.lock_version == 1

    stale_save = client.post(url, form_data("82000", second_version))
    assert stale_save.status_code == 403
    rate.refresh_from_db()
    assert rate.amount == 81000
    assert rate.lock_version == 1
