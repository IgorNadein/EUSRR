# Finance / Payroll

The Finance app is the EUSRR adapter around the project-independent
`payroll_core` package. The dependency points in one direction:

```text
Django models, permissions, workflow and API
                    |
                    v
         immutable payroll_core DTOs
                    |
                    v
         deterministic calculation result
```

The core does not know about Django, users, databases, Excel or EUSRR. The
adapter resolves approved inputs, persists snapshots and implements the
company workflow.

## Implemented slice

- effective-dated, revisioned employee rates;
- period roster, point facts and legacy Excel control totals;
- typed bonuses, corrections, one-time accruals, deductions and advances;
- maker-checker approval for rates and input records;
- deterministic period calculation with input, ruleset and result hashes;
- immutable run revisions and employee statements;
- review, approval, publication, correction return and republication;
- native payroll workspace API for periods, rates, work records, input lines
  and run workflow actions;
- employee-only statement API and idempotent receipt acknowledgement;
- payroll audit events and dedicated Django permissions.

The June 2026 example is covered by an integration test:

```text
base 80,000 + bonus 15,000 + correction 20,000 = payable 115,000 RUB
target points 110, actual points 110, point amount 0
```

This proves the photographed row only. It does not prove the formula for
employees above or below the point target.

| Spreadsheet column | Finance source |
| --- | --- |
| Оклад | approved `EmployeePayRate` |
| Норма баллов / баллы | approved `PayrollWorkRecord` |
| Отпускные / премия / коррекция / разовая | typed `PayrollInputLine` |
| Аванс | payment input line, reducing payable |
| Итого / выработка / перерасчёт / к выплате | reconciliation checkpoints |

Checkpoint columns can block review on mismatch but never feed money back
into the calculation.

## Workflow

During the pilot, `PAYROLL_SIMPLE_ADMIN_ACCESS=true` is the default. Active
`staff` and `superuser` accounts receive every payroll operation without extra
Finance roles, may edit any draft, and may approve records and runs they
created. The legacy `self_approval_overridden` value remains internal to
satisfy existing database constraints; it is not exposed by the payroll API or
shown in the normal payroll workspace and Django model forms. With the pilot
mode disabled, privileged auditors can still inspect the preserved approval
metadata in the immutable audit log.

Set `PAYROLL_SIMPLE_ADMIN_ACCESS=false` to restore the preserved granular
policy: input records and rates are created as drafts and normally approved by
another actor; an approver cannot approve their own record or edit another
user's draft without the dedicated override policy.

> TODO(payroll-access-hardening): disable the temporary full-access mode only
> after the Finance role matrix and maker-checker workflow have passed a full
> pilot with representative payroll periods. In the same deployment, remove
> the temporary `staff` shortcut from the frontend navigation so it follows
> the granular Finance permissions again.

The approval screen captures the exact draft version the checker reviewed; any
concurrent maker edit increments that version and makes the approval fail
closed until the checker reviews it again.

```text
inputs: draft -> approved

run: calculated -> review -> approved -> published
                       |          |
                       +-> returned <-+
                              |
                    calculate new revision
```

Every revision after the first requires a reason. Publishing a new revision
supersedes the previous published run without changing its snapshots. A
legacy Excel mismatch blocks submission for review.

## Permissions

In the current pilot, active `staff` and `superuser` accounts receive all of
the following permissions automatically. When simple access is disabled, use
the custom Finance permissions rather than ordinary Django model access:

- `finance.manage_payroll_inputs` — create and maintain own drafts;
- `finance.approve_payroll_inputs` — approve another actor's inputs;
- `finance.calculate_payroll` — calculate, submit or withdraw a calculated run;
- `finance.approve_payroll` — return, review and approve runs;
- `finance.override_payroll_approval` — additionally allow an input or run
  approver to approve an object they created themselves; this permission grants
  no workspace access and never replaces either ordinary approval permission;
- `finance.publish_payroll` — publish employee statements;
- `finance.view_all_payroll` — see payroll data for all employees;
- `finance.audit_payroll` — inspect the audit journal.

Ordinary employees need none of these. The self-service API always filters by
the authenticated employee and by the currently published run:

```text
GET  /api/v1/finance/payroll/me/statements/
GET  /api/v1/finance/payroll/me/statements/<public_id>/
POST /api/v1/finance/payroll/me/statements/<public_id>/acknowledge/
```

Payroll operators use the permission-gated native workspace under
`/api/v1/finance/payroll/admin/`. It exposes explicit commands rather than
generic model CRUD: draft edits require the version that the operator opened,
the granular fallback can require a different actor, and run transitions call
the payroll services. The portal entry point is
`/finances/payroll/manage`; Django Admin is not required for the normal payroll
workflow.

Responses contain no internal source references and are marked
`Cache-Control: private, no-store`.

## Configuration

Rules live in `FINANCE_PAYROLL` and can be supplied through the
`PAYROLL_*` environment variables documented in `.env.example`. Increment
`PAYROLL_RULESET_VERSION` whenever calculation semantics change.

The point policy is `disabled` by default. `excess_only` is available for a
controlled shadow run and computes `max(actual - target, 0) * point_rate`, but
must not be enabled for publication until the company confirms it on a
representative workbook.

The adapter intentionally accepts only a `0.01` money quantum and nonnegative
payable amounts because the persisted schema stores two decimal places.

## Attendance work import

The EUSRR host adapter can prepare `PayrollWorkRecord` drafts from stored
attendance through the period-scoped preview/apply command.  This integration
does not live in `payroll_core`: it translates verified portal attendance into
the versioned payroll input contract.

Policy `attendance_to_daily_points_v2` keeps attendance hours and payroll points
in separate units.  Every verified workday contributes the configured daily
point target; actual points for that day are `daily target × worked hours ÷
expected hours`.  A complete shift therefore earns the daily target, a partial
shift earns its fraction, and overtime may exceed it.  Missing days, technical
issues, open shifts, unverified remote work and work outside the effective
schedule block the affected employee.  The apply command never auto-approves:
it creates a draft, updates an administrator-accessible draft, or creates a
draft revision that leaves the approved record intact until the record is
explicitly approved.

## Operational boundaries

- PostgreSQL is required in production. SQLite is suitable only for
  single-process development/tests because it does not provide the row locks
  used by the payroll workflow.
- An acknowledgement means the employee confirmed receipt of the statement;
  it is not evidence that a bank transfer completed.
- Model/admin protections are defense in depth for normal application paths.
  Database administrators and direct `QuerySet.update()` calls can bypass
  model validation, so production DB access must remain restricted.
- Successful workflow changes and detailed employee views are audited. Failed
  command attempts are not yet written to a separate append-only command log;
  add that external audit sink before treating this module as the sole
  compliance record.
- Overlapping periods are rejected by application validation. A PostgreSQL
  exclusion constraint should be added before periods can be written by more
  than one integration.
- Linked reversal records are intentionally disabled in this slice. Use an
  explicit debit/credit correction with a reason until reversal semantics are
  approved and implemented atomically.
- Taxes, statutory deductions, bank files, 1C export/import and disputes are
  deliberately outside this first slice.

## Rollout

1. Import rates and several representative spreadsheet periods as drafts.
2. Reconcile every employee in shadow mode; do not publish mismatched runs.
3. Confirm point, correction, deduction and rounding rules with accounting.
4. Freeze and version the approved ruleset.
5. Grant separated operator, checker, publisher and auditor roles.
6. Run one parallel payroll cycle before making the portal authoritative.
