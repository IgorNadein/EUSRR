import uuid
from decimal import Decimal

import pytest
from django.contrib.auth.models import Permission
from django.db import IntegrityError, transaction
from django.urls import reverse
from django.utils import timezone

from finance.models import (
    EmployeePayRate,
    PayrollAuditEvent,
    PayrollComponent,
    PayrollInputLine,
    PayrollPeriod,
    PayrollRun,
    PayrollWorkRecord,
)

pytestmark = pytest.mark.django_db


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


def api_url(name, **kwargs):
    return reverse(f"api:v1:finance-payroll:{name}", kwargs=kwargs or None)


def assert_no_store(response):
    assert "no-store" in response["Cache-Control"]


def make_period(*, creator, code="2026-06"):
    return PayrollPeriod.objects.create(
        code=code,
        name="Июнь 2026",
        date_from="2026-06-01",
        date_to="2026-06-30",
        pay_date="2026-07-05",
        currency="RUB",
        created_by=creator,
    )


def test_admin_workspace_rejects_anonymous_and_generic_model_permission(
    user_factory,
    auth_client_factory,
):
    url = api_url("admin-workspace")
    anonymous = auth_client_factory()
    anonymous_response = anonymous.get(url)
    assert anonymous_response.status_code in {401, 403}
    assert_no_store(anonymous_response)

    generic_viewer = user_factory(email="generic.payroll.viewer@example.test")
    generic_permission = Permission.objects.get(
        content_type__app_label="finance",
        codename="view_payrollperiod",
    )
    generic_viewer.user_permissions.add(generic_permission)
    response = auth_client_factory(generic_viewer).get(url)

    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"
    assert_no_store(response)

    override_only = user_factory(email="override.only@example.test")
    grant(override_only, "override_payroll_approval")
    override_response = auth_client_factory(override_only).get(url)
    assert override_response.status_code == 403
    assert override_response.json()["code"] == "PERMISSION_DENIED"


def test_workspace_contract_is_minimal_and_redacts_money_without_view_all(
    user_factory,
    auth_client_factory,
):
    manager = user_factory(
        email="workspace.manager@example.test",
        first_name="Мария",
        last_name="Расчётова",
    )
    grant(manager, "manage_payroll_inputs")
    response = auth_client_factory(manager).get(api_url("admin-workspace"))

    assert response.status_code == 200
    assert_no_store(response)
    body = response.json()
    assert set(body["permissions"]) == {
        "full_access",
        "manage_inputs",
        "approve_inputs",
        "calculate",
        "approve_run",
        "override_approval",
        "publish",
        "view_all",
        "audit",
    }
    assert body["permissions"]["manage_inputs"] is True
    assert body["permissions"]["full_access"] is False
    assert body["permissions"]["override_approval"] is False
    assert body["summary"] is None
    assert set(body["readiness"]) == {
        "rates",
        "work_records",
        "input_lines",
        "calculation",
    }
    employee = next(item for item in body["employees"] if item["id"] == manager.pk)
    assert employee == {
        "id": manager.pk,
        "display_name": "Мария Расчётова",
        "position": None,
        "department": None,
    }


def test_staff_admin_gets_full_pilot_access_and_can_manage_any_draft(
    user_factory,
    auth_client_factory,
):
    administrator = user_factory(
        email="simple.payroll.admin@example.test",
        staff=True,
    )
    creator = user_factory(email="simple.payroll.creator@example.test")
    first_employee = user_factory(email="simple.payroll.employee.one@example.test")
    second_employee = user_factory(email="simple.payroll.employee.two@example.test")
    client = auth_client_factory(administrator)

    workspace = client.get(api_url("admin-workspace"))

    assert workspace.status_code == 200
    assert workspace.json()["permissions"] == {
        "manage_inputs": True,
        "approve_inputs": True,
        "calculate": True,
        "approve_run": True,
        "override_approval": True,
        "publish": True,
        "view_all": True,
        "audit": True,
        "full_access": True,
    }

    foreign_rate = EmployeePayRate.objects.create(
        employee=first_employee,
        amount="80000",
        effective_from="2026-01-01",
        created_by=creator,
    )
    patched = client.patch(
        api_url("admin-pay-rate-detail", pk=foreign_rate.pk),
        {"amount": "81000.0000", "expected_lock_version": 0},
        format="json",
    )
    assert patched.status_code == 200
    assert patched.json()["amount"] == "81000.0000"

    own_rate = client.post(
        api_url("admin-pay-rate-list"),
        {
            "employee_id": second_employee.pk,
            "rate_code": "BASE",
            "amount": "90000.0000",
            "point_rate": "0.0000",
            "currency": "RUB",
            "effective_from": "2026-01-01",
            "reason": "",
        },
        format="json",
    )
    assert own_rate.status_code == 201
    approved = client.post(
        api_url("admin-pay-rate-approve", pk=own_rate.json()["id"]),
        {"expected_lock_version": own_rate.json()["lock_version"]},
        format="json",
    )
    assert approved.status_code == 200
    assert approved.json()["approved_by_id"] == administrator.pk
    assert "self_approval_overridden" not in approved.json()


def test_staff_without_finance_permissions_is_denied_when_simple_mode_is_disabled(
    settings,
    user_factory,
    auth_client_factory,
):
    settings.FINANCE_PAYROLL = {"SIMPLE_ADMIN_ACCESS": False}
    administrator = user_factory(
        email="granular.payroll.admin@example.test",
        staff=True,
    )

    response = auth_client_factory(administrator).get(api_url("admin-workspace"))

    assert response.status_code == 403
    assert response.json()["code"] == "PERMISSION_DENIED"
    assert_no_store(response)


def test_workspace_blocks_period_outside_ruleset_effective_dates(
    settings,
    user_factory,
    auth_client_factory,
):
    settings.FINANCE_PAYROLL = {"EFFECTIVE_FROM": "2026-07-01"}
    operator = user_factory(email="ruleset.operator@example.test")
    checker = user_factory(email="ruleset.checker@example.test")
    employee = user_factory(email="ruleset.employee@example.test")
    grant(operator, "calculate_payroll")
    period = make_period(creator=operator)
    approved_at = timezone.now()
    EmployeePayRate.objects.create(
        employee=employee,
        amount="80000",
        effective_from="2026-01-01",
        status="approved",
        created_by=operator,
        approved_by=checker,
        approved_at=approved_at,
    )
    PayrollWorkRecord.objects.create(
        period=period,
        employee=employee,
        target_points="100",
        actual_points="100",
        status="approved",
        created_by=operator,
        approved_by=checker,
        approved_at=approved_at,
    )
    client = auth_client_factory(operator)

    workspace = client.get(
        api_url("admin-workspace"),
        {"period_id": period.pk},
    )

    assert workspace.status_code == 200
    readiness = workspace.json()["readiness"]
    assert readiness["rates"]["ready"] is True
    assert readiness["work_records"]["ready"] is True
    assert readiness["calculation"]["ready"] is False
    ruleset_blocker = next(
        blocker
        for blocker in readiness["calculation"]["blockers"]
        if blocker["code"] == "RULESET_NOT_EFFECTIVE"
    )
    assert ruleset_blocker == {
        "code": "RULESET_NOT_EFFECTIVE",
        "message": (
            "Для выбранного периода нет действующих правил расчёта. "
            "Набор eusrr-standard, версия 2026.07.1, применяется с 01.07.2026. "
            "Измените период или подключите историческую версию правил."
        ),
        "details": {
            "period": {
                "date_from": "2026-06-01",
                "date_to": "2026-06-30",
            },
            "ruleset": {
                "id": "eusrr-standard",
                "version": "2026.07.1",
                "effective_from": "2026-07-01",
            },
        },
    }

    calculation = client.post(
        api_url("admin-period-calculate", pk=period.pk),
        {
            "expected_lock_version": period.lock_version,
            "idempotency_key": str(uuid.uuid4()),
            "recalculation_reason": "",
        },
        format="json",
    )
    assert calculation.status_code == 409
    assert calculation.json()["code"] == "RULESET_NOT_EFFECTIVE"
    assert calculation.json()["message"] == ruleset_blocker["message"]
    assert (
        calculation.json()["details"]["period"] == ruleset_blocker["details"]["period"]
    )
    assert (
        calculation.json()["details"]["ruleset"]
        == ruleset_blocker["details"]["ruleset"]
    )
    assert PayrollRun.objects.count() == 0


def test_period_and_rate_drafts_use_exact_optimistic_versions_and_maker_checker(
    user_factory,
    auth_client_factory,
):
    maker = user_factory(email="rate.maker@example.test")
    other_maker = user_factory(email="other.rate.maker@example.test")
    approver = user_factory(email="rate.approver@example.test")
    employee = user_factory(
        email="paid.employee@example.test",
        first_name="Игорь",
        last_name="Надеин",
    )
    inactive_employee = user_factory(
        email="inactive.paid.employee@example.test",
        active=False,
    )
    grant(maker, "manage_payroll_inputs", "approve_payroll_inputs")
    grant(other_maker, "manage_payroll_inputs")
    grant(approver, "approve_payroll_inputs")
    maker_client = auth_client_factory(maker)

    period_response = maker_client.post(
        api_url("admin-period-list"),
        {
            "code": "2026-06",
            "name": "Июнь 2026",
            "date_from": "2026-06-01",
            "date_to": "2026-06-30",
            "pay_date": "2026-07-05",
            "currency": "RUB",
        },
        format="json",
    )
    assert period_response.status_code == 201
    assert period_response.json()["lock_version"] == 0
    assert_no_store(period_response)
    period_id = period_response.json()["id"]

    period_patch_url = api_url("admin-period-detail", pk=period_id)
    patched_period = maker_client.patch(
        period_patch_url,
        {"name": "Зарплата за июнь", "expected_lock_version": 0},
        format="json",
    )
    assert patched_period.status_code == 200
    assert patched_period.json()["lock_version"] == 1
    stale_period = maker_client.patch(
        period_patch_url,
        {"name": "Устаревшее название", "expected_lock_version": 0},
        format="json",
    )
    assert stale_period.status_code == 409
    assert stale_period.json()["code"] == "STALE_PERIOD"
    assert PayrollPeriod.objects.get(pk=period_id).name == "Зарплата за июнь"

    rate_list_url = api_url("admin-pay-rate-list")
    inactive_response = maker_client.post(
        rate_list_url,
        {
            "employee_id": inactive_employee.pk,
            "rate_code": "BASE",
            "amount": "80000.0000",
            "point_rate": "0.0000",
            "currency": "RUB",
            "effective_from": "2026-06-01",
            "reason": "",
        },
        format="json",
    )
    assert inactive_response.status_code == 400

    created = maker_client.post(
        rate_list_url,
        {
            "employee_id": employee.pk,
            "rate_code": "BASE",
            "amount": "80000.0000",
            "point_rate": "0.0000",
            "currency": "RUB",
            "effective_from": "2026-06-01",
            "reason": "",
        },
        format="json",
    )
    assert created.status_code == 201
    rate_id = created.json()["id"]
    assert created.json()["created_by"] == {
        "id": maker.pk,
        "display_name": maker.get_full_name(),
    }
    assert created.json()["employee"]["position"] is None
    assert "source_ref" not in created.json()
    assert "idempotency_key" not in created.json()

    detail_url = api_url("admin-pay-rate-detail", pk=rate_id)
    first_patch = maker_client.patch(
        detail_url,
        {"amount": "81000.0000", "expected_lock_version": 0},
        format="json",
    )
    assert first_patch.status_code == 200
    assert first_patch.json()["lock_version"] == 1

    stale_patch = maker_client.patch(
        detail_url,
        {"amount": "999999.0000", "expected_lock_version": 0},
        format="json",
    )
    assert stale_patch.status_code == 409
    assert stale_patch.json()["code"] == "STALE_DRAFT"
    assert_no_store(stale_patch)
    assert EmployeePayRate.objects.get(pk=rate_id).amount == Decimal("81000")

    hidden_from_other_maker = auth_client_factory(other_maker).patch(
        detail_url,
        {"amount": "82000.0000", "expected_lock_version": 1},
        format="json",
    )
    assert hidden_from_other_maker.status_code == 404

    stale_approval = auth_client_factory(approver).post(
        api_url("admin-pay-rate-approve", pk=rate_id),
        {"expected_lock_version": 0},
        format="json",
    )
    assert stale_approval.status_code == 409
    assert stale_approval.json()["code"] == "APPROVAL_VERSION_CONFLICT"
    assert EmployeePayRate.objects.get(pk=rate_id).status == "draft"

    self_approval = maker_client.post(
        api_url("admin-pay-rate-approve", pk=rate_id),
        {"expected_lock_version": 1},
        format="json",
    )
    assert self_approval.status_code == 409
    assert self_approval.json()["code"] == "SELF_APPROVAL_FORBIDDEN"

    approved = auth_client_factory(approver).post(
        api_url("admin-pay-rate-approve", pk=rate_id),
        {"expected_lock_version": 1},
        format="json",
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by"]["id"] == approver.pk

    immutable_patch = maker_client.patch(
        detail_url,
        {"amount": "83000.0000", "expected_lock_version": 1},
        format="json",
    )
    assert immutable_patch.status_code == 404
    assert EmployeePayRate.objects.get(pk=rate_id).amount == Decimal("81000")

    revision = maker_client.post(
        api_url("admin-pay-rate-revise", pk=rate_id),
        {"reason": "Новая согласованная ставка"},
        format="json",
    )
    assert revision.status_code == 201
    assert revision.json()["status"] == "draft"
    assert revision.json()["revision"] == 2
    assert revision.json()["replaces_id"] == rate_id


def test_native_api_runs_complete_service_workflow_and_redacts_aggregate_money(
    user_factory,
    auth_client_factory,
):
    maker = user_factory(email="workflow.maker@example.test")
    input_approver = user_factory(email="workflow.input.approver@example.test")
    operator = user_factory(email="workflow.operator@example.test")
    run_approver = user_factory(email="workflow.run.approver@example.test")
    publisher = user_factory(email="workflow.publisher@example.test")
    viewer = user_factory(email="workflow.viewer@example.test")
    employee = user_factory(email="workflow.employee@example.test")
    grant(maker, "manage_payroll_inputs")
    grant(input_approver, "approve_payroll_inputs")
    grant(operator, "calculate_payroll")
    grant(run_approver, "approve_payroll")
    grant(publisher, "publish_payroll")
    grant(viewer, "view_all_payroll")
    period = make_period(creator=maker)

    maker_client = auth_client_factory(maker)
    rate_response = maker_client.post(
        api_url("admin-pay-rate-list"),
        {
            "employee_id": employee.pk,
            "rate_code": "BASE",
            "amount": "80000.0000",
            "point_rate": "0.0000",
            "currency": "RUB",
            "effective_from": "2026-06-01",
            "reason": "",
        },
        format="json",
    )
    assert rate_response.status_code == 201
    work_response = maker_client.post(
        api_url("admin-work-record-list"),
        {
            "period_id": period.pk,
            "employee_id": employee.pk,
            "target_points": "110.0000",
            "actual_points": "110.0000",
            "reason": "",
        },
        format="json",
    )
    assert work_response.status_code == 201
    bonus = PayrollComponent.objects.get(code="BONUS")
    input_response = maker_client.post(
        api_url("admin-input-line-list"),
        {
            "period_id": period.pk,
            "employee_id": employee.pk,
            "component_id": bonus.pk,
            "amount": "100.00",
            "reason": "Премия за месяц",
        },
        format="json",
    )
    assert input_response.status_code == 201
    assert input_response.json()["component"]["code"] == "BONUS"

    checker_client = auth_client_factory(input_approver)
    for route_name, object_response in (
        ("admin-pay-rate-approve", rate_response),
        ("admin-work-record-approve", work_response),
        ("admin-input-line-approve", input_response),
    ):
        approval = checker_client.post(
            api_url(route_name, pk=object_response.json()["id"]),
            {"expected_lock_version": object_response.json()["lock_version"]},
            format="json",
        )
        assert approval.status_code == 200
        assert approval.json()["status"] == "approved"
        assert "self_approval_overridden" not in approval.json()

    operator_client = auth_client_factory(operator)
    workspace_before = operator_client.get(
        api_url("admin-workspace"),
        {"period_id": period.pk},
    )
    assert workspace_before.status_code == 200
    assert workspace_before.json()["readiness"]["calculation"]["ready"] is True
    assert workspace_before.json()["summary"] is None

    calculation = operator_client.post(
        api_url("admin-period-calculate", pk=period.pk),
        {
            "expected_lock_version": period.lock_version,
            "idempotency_key": str(uuid.uuid4()),
            "recalculation_reason": "",
        },
        format="json",
    )
    assert calculation.status_code == 201
    assert calculation.json()["status"] == "calculated"
    assert calculation.json()["gross_total"] is None
    assert calculation.json()["requested_by"]["id"] == operator.pk
    assert "input_hash" not in calculation.json()
    assert_no_store(calculation)
    run_id = calculation.json()["id"]

    blocked_draft = maker_client.post(
        api_url("admin-input-line-list"),
        {
            "period_id": period.pk,
            "employee_id": employee.pk,
            "component_id": bonus.pk,
            "amount": "50.00",
            "reason": "Поздняя премия",
        },
        format="json",
    )
    assert blocked_draft.status_code == 409
    assert blocked_draft.json()["code"] == "PERIOD_INPUTS_LOCKED"

    viewer_workspace = auth_client_factory(viewer).get(
        api_url("admin-workspace"),
        {"period_id": period.pk},
    )
    assert viewer_workspace.status_code == 200
    assert viewer_workspace.json()["summary"] == {
        "employee_count": 1,
        "gross_total": "80100.00",
        "deduction_total": "0.00",
        "payable_total": "80100.00",
    }

    submitted = operator_client.post(
        api_url("admin-run-submit-review", pk=run_id),
        {},
        format="json",
    )
    assert submitted.status_code == 200
    assert submitted.json()["status"] == "review"

    approved = auth_client_factory(run_approver).post(
        api_url("admin-run-approve", pk=run_id),
        {},
        format="json",
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by"]["id"] == run_approver.pk
    assert "self_approval_overridden" not in approved.json()

    published = auth_client_factory(publisher).post(
        api_url("admin-run-publish", pk=run_id),
        {},
        format="json",
    )
    assert published.status_code == 200
    assert published.json()["status"] == "published"
    assert published.json()["published_by"]["id"] == publisher.pk

    closed = auth_client_factory(publisher).post(
        api_url("admin-period-close", pk=period.pk),
        {},
        format="json",
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    blocked_closed_draft = maker_client.post(
        api_url("admin-input-line-list"),
        {
            "period_id": period.pk,
            "employee_id": employee.pk,
            "component_id": bonus.pk,
            "amount": "50.00",
            "reason": "После закрытия",
        },
        format="json",
    )
    assert blocked_closed_draft.status_code == 409
    assert blocked_closed_draft.json()["code"] == "PERIOD_INPUTS_LOCKED"
    assert PayrollRun.objects.get(pk=run_id).status == "published"
    assert (
        PayrollWorkRecord.objects.filter(period=period, status="approved").count() == 1
    )
    assert (
        PayrollInputLine.objects.filter(period=period, status="approved").count() == 1
    )


def test_override_holder_can_self_approve_every_serialized_payroll_object(
    user_factory,
    auth_client_factory,
):
    operator = user_factory(email="self.approver@example.test")
    employee = user_factory(email="self.approval.employee@example.test")
    grant(
        operator,
        "manage_payroll_inputs",
        "approve_payroll_inputs",
        "calculate_payroll",
        "approve_payroll",
        "override_payroll_approval",
    )
    client = auth_client_factory(operator)
    period = make_period(creator=operator, code="2026-07")

    workspace = client.get(
        api_url("admin-workspace"),
        {"period_id": period.pk},
    )
    assert workspace.status_code == 200
    assert workspace.json()["permissions"]["override_approval"] is True

    rate = client.post(
        api_url("admin-pay-rate-list"),
        {
            "employee_id": employee.pk,
            "rate_code": "BASE",
            "amount": "90000.0000",
            "point_rate": "0.0000",
            "currency": "RUB",
            "effective_from": "2026-06-01",
            "reason": "",
        },
        format="json",
    )
    work_record = client.post(
        api_url("admin-work-record-list"),
        {
            "period_id": period.pk,
            "employee_id": employee.pk,
            "target_points": "100.0000",
            "actual_points": "100.0000",
            "reason": "",
        },
        format="json",
    )
    bonus = PayrollComponent.objects.get(code="BONUS")
    input_line = client.post(
        api_url("admin-input-line-list"),
        {
            "period_id": period.pk,
            "employee_id": employee.pk,
            "component_id": bonus.pk,
            "amount": "1000.00",
            "reason": "Премия",
        },
        format="json",
    )
    assert {rate.status_code, work_record.status_code, input_line.status_code} == {201}

    approved_objects = []
    for route_name, response in (
        ("admin-pay-rate-approve", rate),
        ("admin-work-record-approve", work_record),
        ("admin-input-line-approve", input_line),
    ):
        approval = client.post(
            api_url(route_name, pk=response.json()["id"]),
            {"expected_lock_version": response.json()["lock_version"]},
            format="json",
        )
        assert approval.status_code == 200
        assert approval.json()["approved_by_id"] == operator.pk
        assert "self_approval_overridden" not in approval.json()
        approved_objects.append(approval.json())

    calculation = client.post(
        api_url("admin-period-calculate", pk=period.pk),
        {
            "expected_lock_version": period.lock_version,
            "idempotency_key": str(uuid.uuid4()),
            "recalculation_reason": "",
        },
        format="json",
    )
    assert calculation.status_code == 201
    run_id = calculation.json()["id"]
    submitted = client.post(api_url("admin-run-submit-review", pk=run_id), {})
    assert submitted.status_code == 200
    run_approval = client.post(api_url("admin-run-approve", pk=run_id), {})
    assert run_approval.status_code == 200
    assert run_approval.json()["approved_by_id"] == operator.pk
    assert "self_approval_overridden" not in run_approval.json()

    records = (
        (EmployeePayRate, approved_objects[0]["id"]),
        (PayrollWorkRecord, approved_objects[1]["id"]),
        (PayrollInputLine, approved_objects[2]["id"]),
        (PayrollRun, run_id),
    )
    for model, object_id in records:
        instance = model.objects.get(pk=object_id)
        assert instance.self_approval_overridden is True
        with pytest.raises(IntegrityError):
            with transaction.atomic():
                model.objects.filter(pk=object_id).update(
                    self_approval_overridden=False
                )

    events = PayrollAuditEvent.objects.filter(
        actor=operator,
        action__in={
            "payroll.rate_approved",
            "payroll.work_record_approved",
            "payroll.input_line_approved",
            "payroll.approved",
        },
    )
    assert events.count() == 4
    for event in events:
        assert event.metadata["self_approval_overridden"] is True
        assert event.metadata["approval_mode"] == "self_override"
        assert (
            event.metadata["override_permission"] == "finance.override_payroll_approval"
        )
