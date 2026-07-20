# Payroll Core

`payroll_core` is a deterministic, project-independent calculation package.
It contains no Django, database, network, Celery or EUSRR imports. A host
application resolves employees and approved inputs, calls the calculator, and
persists the returned immutable snapshot.

## Guarantees

- every monetary and quantity value is `Decimal`; floats are rejected;
- each displayed money line is rounded once before totals are summed;
- calculation uses a fixed local decimal context and does not depend on the
  host process context;
- rules are immutable, effective-dated and versioned;
- inputs, rules and calculation output have canonical SHA-256 fingerprints;
- reconciliation warnings have a separate fingerprint, so legacy checkpoints
  never alter calculation identity but cannot be changed unnoticed;
- explicit line kinds carry direction, so a negative correction cannot become
  a double negative;
- legacy spreadsheet totals are reconciliation checkpoints, never inputs;
- the result is independent of the order of input lines.

## Example matching the June 2026 spreadsheet

```python
from datetime import date
from decimal import Decimal

from payroll_core import (
    DeterministicPayrollCalculator,
    ExpectedTotals,
    InputLine,
    LineKind,
    PayrollPeriod,
    PayrollRequest,
    PayrollRules,
    PointPolicy,
)

period = PayrollPeriod(date(2026, 6, 1), date(2026, 6, 30))
request = PayrollRequest(
    employee_ref="employee:42",
    period=period,
    currency="RUB",
    base_accrual=Decimal("80000"),
    base_source_ref="rate:42:revision:1",
    point_base_accrual=Decimal("95000"),
    target_points=Decimal("110"),
    actual_points=Decimal("110"),
    point_rate=Decimal("100"),
    lines=(
        InputLine(
            line_id="bonus:1",
            code="BONUS",
            label="Bonus",
            kind=LineKind.EARNING,
            amount=Decimal("15000"),
            source_ref="excel:june:row-2:bonus",
        ),
        InputLine(
            line_id="correction:1",
            code="MANUAL_CORRECTION",
            label="Manual correction",
            kind=LineKind.ADJUSTMENT_CREDIT,
            amount=Decimal("20000"),
            reason="Approved accounting correction",
            source_ref="excel:june:row-2:correction",
        ),
    ),
    expected_totals=ExpectedTotals(
        point_amount=Decimal("0"),
        gross=Decimal("115000"),
        recalculated_gross=Decimal("115000"),
        payable=Decimal("115000"),
    ),
)
rules = PayrollRules(
    ruleset_id="company-standard",
    version="2026.07.1",
    effective_from=date(2026, 1, 1),
    point_policy=PointPolicy.EXCESS_ONLY,
)

result = DeterministicPayrollCalculator().calculate(request, rules)
assert result.totals.payable == Decimal("115000.00")
```

The initial `EXCESS_ONLY` point policy pays only points above the target:
`max(actual - target, 0) * point_rate`. It never creates an implicit penalty
for a shortfall. This policy must remain in shadow/reconciliation mode until
the company confirms how points work for other rows.

`PROPORTIONAL_WITH_EXCESS` produces a signed point adjustment. Below target it
uses the complete point basis supplied by the host:
`point_base_accrual * actual / target - point_base_accrual`. Above target it
uses `(actual - target) * point_rate`. Keeping the basis separate from the base
accrual preserves the original input lines while making the adjustment visible.

## Host boundary

The core knows an employee only as an opaque `employee_ref`. The host adapter
is responsible for authorization, rate resolution, maker-checker approval,
transactions, audit, publication, acknowledgements and notifications.
EUSRR maps the spreadsheet point basis to base accrual plus bonus inputs. It
keeps the configured excess point price nullable: when blank, the host supplies
the current in-norm display price and marks it as automatic. The core then uses
the unrounded `point_base_accrual / target_points` formula, without persisting
the derived value.
