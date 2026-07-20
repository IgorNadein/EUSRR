from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest
from django.contrib import admin
from django.contrib.auth.models import Permission
from django.contrib.messages.storage.fallback import FallbackStorage
from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.test import RequestFactory
from django.urls import reverse

from finance.enums import (
    ApprovalStatus,
    PayrollPeriodStatus,
    PayrollRunStatus,
)
from finance.admin import PayrollPeriodAdmin
from finance.models import (
    EmployeePayRate,
    PayrollAuditEvent,
    PayrollComponent,
    PayrollInputLine,
    PayrollPeriod,
    PayrollRun,
    PayrollStatement,
    PayrollStatementAcknowledgement,
    PayrollWorkRecord,
)
from finance.payroll.exceptions import PayrollOperationError, PayrollPermissionDenied
from finance.payroll.services import (
    acknowledge_statement,
    approve_input_line,
    approve_pay_rate,
    approve_run,
    approve_work_record,
    calculate_period,
    publish_run,
    return_run_for_correction,
    submit_run_for_review,
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


@pytest.fixture
def payroll_users(user_factory):
    operator = user_factory(email="payroll.operator@example.test")
    input_approver = user_factory(email="payroll.inputs@example.test")
    run_approver = user_factory(email="payroll.approver@example.test")
    publisher = user_factory(email="payroll.publisher@example.test")
    employee = user_factory(
        email="igor.nadein@example.test",
        first_name="Игорь",
        last_name="Надеин",
    )
    grant(operator, "calculate_payroll")
    grant(input_approver, "approve_payroll_inputs")
    grant(run_approver, "approve_payroll")
    grant(publisher, "publish_payroll")
    return {
        "operator": operator,
        "input_approver": input_approver,
        "run_approver": run_approver,
        "publisher": publisher,
        "employee": employee,
    }


@pytest.fixture
def june_period(payroll_users):
    return PayrollPeriod.objects.create(
        code="2026-06",
        name="Июнь 2026",
        date_from=date(2026, 6, 1),
        date_to=date(2026, 6, 30),
        pay_date=date(2026, 7, 5),
        currency="RUB",
        created_by=payroll_users["operator"],
    )


def create_approved_excel_inputs(period, users):
    operator = users["operator"]
    approver = users["input_approver"]
    employee = users["employee"]
    rate = EmployeePayRate.objects.create(
        employee=employee,
        amount=Decimal("80000"),
        point_rate=Decimal("100"),
        currency="RUB",
        effective_from=date(2026, 1, 1),
        created_by=operator,
        reason="Штатная ставка",
    )
    approve_pay_rate(
        rate.pk,
        actor=approver,
        expected_lock_version=rate.lock_version,
    )

    work_record = PayrollWorkRecord.objects.create(
        period=period,
        employee=employee,
        target_points=Decimal("110"),
        actual_points=Decimal("110"),
        expected_point_amount=Decimal("0"),
        expected_gross=Decimal("115000"),
        expected_recalculated_gross=Decimal("115000"),
        expected_payable=Decimal("115000"),
        source="excel",
        source_ref=f"excel:{period.code}:employee:{employee.pk}:work",
        created_by=operator,
    )
    approve_work_record(
        work_record.pk,
        actor=approver,
        expected_lock_version=work_record.lock_version,
    )

    bonus = PayrollInputLine.objects.create(
        period=period,
        employee=employee,
        component=PayrollComponent.objects.get(code="BONUS"),
        amount=Decimal("15000"),
        source="excel",
        source_ref=f"excel:{period.code}:employee:{employee.pk}:bonus",
        created_by=operator,
    )
    correction = PayrollInputLine.objects.create(
        period=period,
        employee=employee,
        component=PayrollComponent.objects.get(code="CORRECTION_CREDIT"),
        amount=Decimal("20000"),
        reason="Коррекция из исходной таблицы",
        source="excel",
        source_ref=f"excel:{period.code}:employee:{employee.pk}:correction",
        created_by=operator,
    )
    approve_input_line(
        bonus.pk,
        actor=approver,
        expected_lock_version=bonus.lock_version,
    )
    approve_input_line(
        correction.pk,
        actor=approver,
        expected_lock_version=correction.lock_version,
    )
    return rate, work_record, bonus, correction


def calculate_excel_period(period, users, *, idempotency_key=None):
    create_approved_excel_inputs(period, users)
    return calculate_period(
        period.pk,
        actor=users["operator"],
        idempotency_key=idempotency_key,
    )


def publish_calculation(run, users):
    submit_run_for_review(run.pk, actor=users["operator"])
    approve_run(run.pk, actor=users["run_approver"])
    return publish_run(run.pk, actor=users["publisher"])


def test_excel_row_is_persisted_as_a_deterministic_statement(
    june_period,
    payroll_users,
):
    run = calculate_excel_period(june_period, payroll_users)

    run.refresh_from_db()
    june_period.refresh_from_db()
    statement = run.statements.get(employee=payroll_users["employee"])
    assert run.revision == 1
    assert run.status == PayrollRunStatus.CALCULATED
    assert run.employee_count == 1
    assert run.gross_total == Decimal("115000.00")
    assert run.deduction_total == Decimal("0.00")
    assert run.payable_total == Decimal("115000.00")
    assert june_period.current_run_id == run.pk
    assert june_period.status == PayrollPeriodStatus.CALCULATED

    assert statement.gross_before_adjustments == Decimal("95000.00")
    assert statement.adjustment_total == Decimal("20000.00")
    assert statement.point_delta == Decimal("0.0000")
    assert statement.gross_total == Decimal("115000.00")
    assert statement.net_pay == Decimal("115000.00")
    assert statement.payable == Decimal("115000.00")
    assert statement.employee_snapshot["display_name"] == "Игорь Надеин"
    assert statement.input_snapshot["base_source_ref"].startswith("pay-rate:")
    assert statement.result_snapshot["warnings"] == []
    assert list(statement.lines.values_list("code", flat=True)) == [
        "BASE",
        "POINT_EXCESS",
        "BONUS",
        "CORRECTION_CREDIT",
    ]
    assert PayrollAuditEvent.objects.filter(
        action="payroll.calculated",
        object_id=str(run.pk),
    ).exists()


def test_full_workflow_requires_a_second_person_and_employee_can_acknowledge(
    june_period,
    payroll_users,
    user_factory,
):
    run = calculate_excel_period(june_period, payroll_users)
    submit_run_for_review(run.pk, actor=payroll_users["operator"])

    grant(payroll_users["operator"], "approve_payroll")
    with pytest.raises(PayrollOperationError) as error:
        approve_run(run.pk, actor=payroll_users["operator"])
    assert error.value.code == "SELF_APPROVAL_FORBIDDEN"

    approve_run(run.pk, actor=payroll_users["run_approver"])
    publish_run(run.pk, actor=payroll_users["publisher"])
    run.refresh_from_db()
    june_period.refresh_from_db()
    assert run.status == PayrollRunStatus.PUBLISHED
    assert june_period.status == PayrollPeriodStatus.PUBLISHED

    statement = run.statements.get()
    stranger = user_factory(email="not.the.employee@example.test")
    with pytest.raises(PayrollOperationError) as error:
        acknowledge_statement(statement.pk, actor=stranger)
    assert error.value.code == "STATEMENT_NOT_FOUND"

    key = uuid.uuid4()
    acknowledgement = acknowledge_statement(
        statement.pk,
        actor=payroll_users["employee"],
        idempotency_key=key,
    )
    duplicate = acknowledge_statement(
        statement.pk,
        actor=payroll_users["employee"],
        idempotency_key=key,
    )
    assert duplicate.pk == acknowledgement.pk
    assert acknowledgement.content_hash == statement.result_hash
    assert acknowledgement.acknowledged_at is not None
    assert PayrollStatementAcknowledgement.objects.count() == 1


def test_override_permission_never_replaces_operational_approval_permissions(
    user_factory,
):
    override_only = user_factory(email="override.without.approval@example.test")
    employee = user_factory(email="override.target@example.test")
    grant(override_only, "override_payroll_approval")
    rate = EmployeePayRate.objects.create(
        employee=employee,
        amount=Decimal("80000"),
        effective_from=date(2026, 1, 1),
        created_by=override_only,
    )

    with pytest.raises(PayrollPermissionDenied) as input_error:
        approve_pay_rate(
            rate.pk,
            actor=override_only,
            expected_lock_version=rate.lock_version,
        )
    assert input_error.value.details["permission"] == ("finance.approve_payroll_inputs")

    with pytest.raises(PayrollPermissionDenied) as run_error:
        approve_run(999_999, actor=override_only)
    assert run_error.value.details["permission"] == "finance.approve_payroll"


def test_database_rejects_override_flag_without_an_actual_self_approval(
    payroll_users,
):
    rate = EmployeePayRate.objects.create(
        employee=payroll_users["employee"],
        amount=Decimal("80000"),
        effective_from=date(2026, 1, 1),
        created_by=payroll_users["operator"],
    )

    with pytest.raises(IntegrityError):
        with transaction.atomic():
            EmployeePayRate.objects.filter(pk=rate.pk).update(
                self_approval_overridden=True
            )


def test_recalculation_creates_a_revision_without_mutating_published_result(
    june_period,
    payroll_users,
):
    first_run = calculate_excel_period(june_period, payroll_users)
    publish_calculation(first_run, payroll_users)
    first_statement = first_run.statements.get()
    first_hash = first_statement.result_hash

    debit = PayrollInputLine.objects.create(
        period=june_period,
        employee=payroll_users["employee"],
        component=PayrollComponent.objects.get(code="CORRECTION_DEBIT"),
        amount=Decimal("5000"),
        reason="Исправление после публикации",
        created_by=payroll_users["operator"],
    )
    approve_input_line(
        debit.pk,
        actor=payroll_users["input_approver"],
        expected_lock_version=debit.lock_version,
    )
    old_work_record = PayrollWorkRecord.objects.get(
        period=june_period,
        status=ApprovalStatus.APPROVED,
    )
    replacement_work_record = PayrollWorkRecord.objects.create(
        period=june_period,
        employee=payroll_users["employee"],
        target_points=old_work_record.target_points,
        actual_points=old_work_record.actual_points,
        expected_point_amount=Decimal("0"),
        expected_gross=Decimal("110000"),
        expected_recalculated_gross=Decimal("110000"),
        expected_payable=Decimal("110000"),
        revision=2,
        replaces=old_work_record,
        reason="Контрольные итоги после утверждённой корректировки",
        created_by=payroll_users["operator"],
    )
    approve_work_record(
        replacement_work_record.pk,
        actor=payroll_users["input_approver"],
        expected_lock_version=replacement_work_record.lock_version,
    )

    second_run = calculate_period(
        june_period.pk,
        actor=payroll_users["operator"],
        recalculation_reason="Исправление утверждённой корректировки",
    )
    second_statement = second_run.statements.get()
    first_run.refresh_from_db()
    first_statement.refresh_from_db()
    assert second_run.revision == 2
    assert second_run.supersedes_id == first_run.pk
    assert second_statement.supersedes_id == first_statement.pk
    assert second_statement.payable == Decimal("110000.00")
    assert first_run.status == PayrollRunStatus.PUBLISHED
    assert first_statement.result_hash == first_hash
    assert first_statement.payable == Decimal("115000.00")

    publish_calculation(second_run, payroll_users)
    first_run.refresh_from_db()
    second_run.refresh_from_db()
    assert first_run.status == PayrollRunStatus.SUPERSEDED
    assert second_run.status == PayrollRunStatus.PUBLISHED


def test_calculation_idempotency_key_returns_the_same_run(
    june_period,
    payroll_users,
):
    key = uuid.uuid4()
    first = calculate_excel_period(
        june_period,
        payroll_users,
        idempotency_key=key,
    )
    second = calculate_period(
        june_period.pk,
        actor=payroll_users["operator"],
        idempotency_key=key,
    )

    assert first.pk == second.pk
    assert PayrollRun.objects.count() == 1
    assert PayrollStatement.objects.count() == 1


def test_unapproved_work_record_is_not_used_and_run_is_not_partially_created(
    june_period,
    payroll_users,
):
    rate = EmployeePayRate.objects.create(
        employee=payroll_users["employee"],
        amount=Decimal("80000"),
        effective_from=date(2026, 1, 1),
        created_by=payroll_users["operator"],
    )
    approve_pay_rate(
        rate.pk,
        actor=payroll_users["input_approver"],
        expected_lock_version=rate.lock_version,
    )
    PayrollWorkRecord.objects.create(
        period=june_period,
        employee=payroll_users["employee"],
        target_points=Decimal("110"),
        actual_points=Decimal("110"),
        created_by=payroll_users["operator"],
    )

    with pytest.raises(PayrollOperationError) as error:
        calculate_period(june_period.pk, actor=payroll_users["operator"])

    assert error.value.code == "NO_APPROVED_WORK_RECORDS"
    assert PayrollRun.objects.count() == 0
    june_period.refresh_from_db()
    assert june_period.status == PayrollPeriodStatus.OPEN


def test_ruleset_not_effective_keeps_domain_code_and_localized_message(
    settings,
    june_period,
    payroll_users,
):
    create_approved_excel_inputs(june_period, payroll_users)
    settings.FINANCE_PAYROLL = {"EFFECTIVE_FROM": "2026-07-01"}

    with pytest.raises(PayrollOperationError) as error:
        calculate_period(june_period.pk, actor=payroll_users["operator"])

    assert error.value.code == "RULESET_NOT_EFFECTIVE"
    assert error.value.message == (
        "Для выбранного периода нет действующих правил расчёта. "
        "Набор eusrr-standard, версия 2026.07.2, применяется с 01.07.2026. "
        "Измените период или подключите историческую версию правил."
    )
    assert error.value.details["employee_id"] == payroll_users["employee"].pk
    assert error.value.details["period"] == {
        "date_from": "2026-06-01",
        "date_to": "2026-06-30",
    }
    assert error.value.details["ruleset"] == {
        "id": "eusrr-standard",
        "version": "2026.07.2",
        "effective_from": "2026-07-01",
    }
    assert {issue["code"] for issue in error.value.details["issues"]} == {
        "RULESET_NOT_EFFECTIVE"
    }
    assert PayrollRun.objects.count() == 0


def test_mid_period_rate_change_fails_closed_until_policy_is_defined(
    june_period,
    payroll_users,
):
    create_approved_excel_inputs(june_period, payroll_users)
    second_rate = EmployeePayRate.objects.create(
        employee=payroll_users["employee"],
        amount=Decimal("90000"),
        effective_from=date(2026, 6, 15),
        created_by=payroll_users["operator"],
    )
    approve_pay_rate(
        second_rate.pk,
        actor=payroll_users["input_approver"],
        expected_lock_version=second_rate.lock_version,
    )

    with pytest.raises(PayrollOperationError) as error:
        calculate_period(june_period.pk, actor=payroll_users["operator"])

    assert error.value.code == "MID_PERIOD_RATE_CHANGE_UNSUPPORTED"
    assert PayrollRun.objects.count() == 0


def test_staff_admin_can_calculate_without_dedicated_finance_permissions(
    june_period,
    payroll_users,
    user_factory,
):
    create_approved_excel_inputs(june_period, payroll_users)
    unrelated_staff = user_factory(
        email="staff.without.finance@example.test",
        staff=True,
    )

    run = calculate_period(june_period.pk, actor=unrelated_staff)

    assert run.requested_by == unrelated_staff
    assert run.status == PayrollRunStatus.CALCULATED
    assert PayrollRun.objects.count() == 1


def test_staff_admin_can_approve_own_run_without_override_role(
    june_period,
    payroll_users,
    user_factory,
):
    create_approved_excel_inputs(june_period, payroll_users)
    administrator = user_factory(
        email="staff.direct.approval@example.test",
        staff=True,
    )
    run = calculate_period(june_period.pk, actor=administrator)
    submit_run_for_review(run.pk, actor=administrator)

    approved = approve_run(run.pk, actor=administrator)

    assert approved.status == PayrollRunStatus.APPROVED
    assert approved.approved_by == administrator
    assert approved.self_approval_overridden is True
    event = PayrollAuditEvent.objects.get(
        action="payroll.approved",
        object_id=str(run.pk),
    )
    assert "self_approval_overridden" not in event.metadata
    assert "approval_mode" not in event.metadata


def test_every_new_revision_requires_a_reason(june_period, payroll_users):
    first_run = calculate_excel_period(june_period, payroll_users)

    with pytest.raises(PayrollOperationError) as error:
        calculate_period(june_period.pk, actor=payroll_users["operator"])

    assert error.value.code == "RECALCULATION_REASON_REQUIRED"
    assert PayrollRun.objects.get() == first_run


def test_reviewer_can_return_run_and_operator_creates_new_revision(
    june_period,
    payroll_users,
):
    first_run = calculate_excel_period(june_period, payroll_users)
    submit_run_for_review(first_run.pk, actor=payroll_users["operator"])

    returned = return_run_for_correction(
        first_run.pk,
        actor=payroll_users["run_approver"],
        reason="Неверно указана корректировка",
    )
    returned.refresh_from_db()
    june_period.refresh_from_db()
    assert returned.status == PayrollRunStatus.RETURNED
    assert june_period.status == PayrollPeriodStatus.CALCULATED

    second_run = calculate_period(
        june_period.pk,
        actor=payroll_users["operator"],
        recalculation_reason="Исправлена корректировка",
    )
    returned.refresh_from_db()
    assert second_run.revision == 2
    assert returned.status == PayrollRunStatus.SUPERSEDED


def test_excel_mismatch_blocks_review(june_period, payroll_users):
    create_approved_excel_inputs(june_period, payroll_users)
    PayrollWorkRecord.objects.filter(period=june_period).update(
        expected_gross=Decimal("1")
    )
    run = calculate_period(june_period.pk, actor=payroll_users["operator"])

    with pytest.raises(PayrollOperationError) as error:
        submit_run_for_review(run.pk, actor=payroll_users["operator"])

    assert error.value.code == "RECONCILIATION_MISMATCH"
    run.refresh_from_db()
    assert run.status == PayrollRunStatus.CALCULATED


def test_approved_input_outside_roster_blocks_calculation(
    june_period,
    payroll_users,
    user_factory,
):
    create_approved_excel_inputs(june_period, payroll_users)
    outsider = user_factory(email="outside.roster@example.test")
    outside_bonus = PayrollInputLine.objects.create(
        period=june_period,
        employee=outsider,
        component=PayrollComponent.objects.get(code="BONUS"),
        amount=Decimal("100"),
        created_by=payroll_users["operator"],
    )
    approve_input_line(
        outside_bonus.pk,
        actor=payroll_users["input_approver"],
        expected_lock_version=outside_bonus.lock_version,
    )

    with pytest.raises(PayrollOperationError) as error:
        calculate_period(june_period.pk, actor=payroll_users["operator"])

    assert error.value.code == "INPUT_EMPLOYEE_NOT_IN_ROSTER"
    assert PayrollRun.objects.count() == 0


def test_employee_api_only_returns_own_published_statement_and_no_stores_it(
    june_period,
    payroll_users,
    user_factory,
    auth_client_factory,
    extract_results,
):
    run = calculate_excel_period(june_period, payroll_users)
    publish_calculation(run, payroll_users)
    statement = run.statements.get()
    employee_client = auth_client_factory(payroll_users["employee"])
    stranger = user_factory(email="api.stranger@example.test")
    stranger_client = auth_client_factory(stranger)

    list_url = reverse("api:v1:finance-payroll:own-statement-list")
    response = employee_client.get(list_url)
    assert response.status_code == 200
    items = extract_results(response.json())
    assert len(items) == 1
    assert items[0]["public_id"] == str(statement.public_id)
    assert items[0]["payable"] == "115000.00"
    assert "lines" not in items[0]
    assert "gross_total" not in items[0]
    assert "employee" not in items[0]
    assert "input_snapshot" not in items[0]
    assert "no-store" in response["Cache-Control"]
    assert PayrollAuditEvent.objects.filter(
        action="payroll.statement_summary_viewed",
        actor=payroll_users["employee"],
    ).exists()

    detail_url = reverse(
        "api:v1:finance-payroll:own-statement-detail",
        kwargs={"public_id": statement.public_id},
    )
    assert stranger_client.get(detail_url).status_code == 404
    detail_response = employee_client.get(detail_url)
    assert detail_response.status_code == 200
    assert len(detail_response.json()["lines"]) == 4
    assert PayrollAuditEvent.objects.filter(
        action="payroll.statement_viewed",
        actor=payroll_users["employee"],
    ).exists()

    acknowledgement_url = reverse(
        "api:v1:finance-payroll:own-statement-acknowledge",
        kwargs={"public_id": statement.public_id},
    )
    ack_response = employee_client.post(acknowledgement_url, {}, format="json")
    assert ack_response.status_code == 200
    assert ack_response.json()["acknowledged_at"] is not None
    assert (
        stranger_client.post(
            acknowledgement_url,
            {},
            format="json",
        ).status_code
        == 404
    )


def test_new_approval_requires_return_and_recalculation(
    june_period,
    payroll_users,
):
    run = calculate_excel_period(june_period, payroll_users)
    extra_bonus = PayrollInputLine.objects.create(
        period=june_period,
        employee=payroll_users["employee"],
        component=PayrollComponent.objects.get(code="BONUS"),
        amount=Decimal("100"),
        source_ref="manual:late-bonus",
        created_by=payroll_users["operator"],
    )

    with pytest.raises(PayrollOperationError) as error:
        approve_input_line(
            extra_bonus.pk,
            actor=payroll_users["input_approver"],
            expected_lock_version=extra_bonus.lock_version,
        )
    assert error.value.code == "PERIOD_INPUTS_LOCKED"

    return_run_for_correction(
        run.pk,
        actor=payroll_users["operator"],
        reason="Поздно утверждённая премия",
    )
    approve_input_line(
        extra_bonus.pk,
        actor=payroll_users["input_approver"],
        expected_lock_version=extra_bonus.lock_version,
    )
    revised = calculate_period(
        june_period.pk,
        actor=payroll_users["operator"],
        recalculation_reason="Добавлена поздно утверждённая премия",
    )

    assert revised.revision == 2
    assert revised.payable_total == Decimal("115100.00")


def test_freshness_gate_detects_source_changes_before_review(
    june_period,
    payroll_users,
):
    run = calculate_excel_period(june_period, payroll_users)
    PayrollWorkRecord.objects.filter(
        period=june_period,
        employee=payroll_users["employee"],
        status=ApprovalStatus.APPROVED,
    ).update(actual_points=Decimal("111"))

    with pytest.raises(PayrollOperationError) as error:
        submit_run_for_review(run.pk, actor=payroll_users["operator"])

    assert error.value.code == "RUN_STALE_RECALCULATION_REQUIRED"


def test_rate_approval_is_blocked_while_employee_run_is_active(
    june_period,
    payroll_users,
):
    run = calculate_excel_period(june_period, payroll_users)
    original_rate = EmployeePayRate.objects.get(status=ApprovalStatus.APPROVED)
    replacement = EmployeePayRate.objects.create(
        employee=payroll_users["employee"],
        rate_code=original_rate.rate_code,
        amount=Decimal("81000"),
        point_rate=original_rate.point_rate,
        currency=original_rate.currency,
        effective_from=original_rate.effective_from,
        revision=2,
        replaces=original_rate,
        reason="Изменение ставки",
        created_by=payroll_users["operator"],
    )

    with pytest.raises(PayrollOperationError) as error:
        approve_pay_rate(
            replacement.pk,
            actor=payroll_users["input_approver"],
            expected_lock_version=replacement.lock_version,
        )

    assert run.status == PayrollRunStatus.CALCULATED
    assert error.value.code == "RATE_USED_BY_ACTIVE_RUN"


def test_employee_visible_period_fields_freeze_after_calculation(
    june_period,
    payroll_users,
):
    calculate_excel_period(june_period, payroll_users)
    june_period.pay_date = date(2026, 7, 6)

    with pytest.raises(ValidationError):
        june_period.save()


def test_stale_period_form_cannot_overwrite_calculation_state(
    june_period,
    payroll_users,
):
    stale_period = PayrollPeriod.objects.get(pk=june_period.pk)
    run = calculate_excel_period(june_period, payroll_users)

    stale_period.save()
    stale_period.refresh_from_db()

    assert stale_period.status == PayrollPeriodStatus.CALCULATED
    assert stale_period.current_run_id == run.pk
    assert stale_period.lock_version == 1


def test_checker_approves_only_the_version_they_reviewed(
    payroll_users,
):
    rate = EmployeePayRate.objects.create(
        employee=payroll_users["employee"],
        amount=Decimal("80000"),
        point_rate=Decimal("100"),
        currency="RUB",
        effective_from=date(2026, 1, 1),
        created_by=payroll_users["operator"],
    )
    reviewed_version = rate.lock_version
    rate.amount = Decimal("800000")
    rate.save()
    assert rate.lock_version == reviewed_version + 1

    with pytest.raises(PayrollOperationError) as error:
        approve_pay_rate(
            rate.pk,
            actor=payroll_users["input_approver"],
            expected_lock_version=reviewed_version,
        )

    assert error.value.code == "APPROVAL_VERSION_CONFLICT"
    rate.refresh_from_db()
    assert rate.status == ApprovalStatus.DRAFT


def test_stale_draft_save_is_rejected(payroll_users):
    rate = EmployeePayRate.objects.create(
        employee=payroll_users["employee"],
        amount=Decimal("80000"),
        effective_from=date(2026, 1, 1),
        created_by=payroll_users["operator"],
    )
    stale = EmployeePayRate.objects.get(pk=rate.pk)
    rate.amount = Decimal("81000")
    rate.save()
    stale.amount = Decimal("82000")

    with pytest.raises(ValidationError):
        stale.save()

    rate.refresh_from_db()
    assert rate.amount == Decimal("81000.0000")
    assert rate.lock_version == 1


def test_component_semantics_freeze_after_creation(payroll_users):
    component = PayrollComponent.objects.get(code="BONUS")
    component.kind = "deduction"

    with pytest.raises(ValidationError):
        component.save()

    component.refresh_from_db()
    component.is_active = False
    component.save()
    assert component.is_active is False


def test_inactive_component_cannot_be_approved(
    june_period,
    payroll_users,
):
    component = PayrollComponent.objects.get(code="BONUS")
    component.is_active = False
    component.save()
    line = PayrollInputLine.objects.create(
        period=june_period,
        employee=payroll_users["employee"],
        component=component,
        amount=Decimal("100"),
        created_by=payroll_users["operator"],
    )

    with pytest.raises(PayrollOperationError) as error:
        approve_input_line(
            line.pk,
            actor=payroll_users["input_approver"],
            expected_lock_version=line.lock_version,
        )

    assert error.value.code == "PAYROLL_COMPONENT_INACTIVE"


def test_admin_recalculation_collects_and_persists_reason(
    june_period,
    payroll_users,
):
    calculate_excel_period(june_period, payroll_users)
    model_admin = PayrollPeriodAdmin(PayrollPeriod, admin.site)
    queryset = PayrollPeriod.objects.filter(pk=june_period.pk)

    preview_request = RequestFactory().post(
        "/admin/finance/payrollperiod/",
        {
            "action": "calculate_selected",
            "_selected_action": [june_period.pk],
        },
    )
    preview_request.user = payroll_users["operator"]
    preview = model_admin.calculate_selected(preview_request, queryset)
    assert preview.context_data["reason_required"] is True

    reason = "Повторная сверка с исходной таблицей"
    confirm_request = RequestFactory().post(
        "/admin/finance/payrollperiod/",
        {
            "action": "calculate_selected",
            "_selected_action": [june_period.pk],
            "confirm_payroll_action": "1",
            "reason": reason,
        },
    )
    confirm_request.user = payroll_users["operator"]
    confirm_request.session = {}
    confirm_request._messages = FallbackStorage(confirm_request)

    model_admin.calculate_selected(confirm_request, queryset)

    revised = PayrollRun.objects.get(period=june_period, revision=2)
    assert revised.recalculation_reason == reason
