"""Project-independent deterministic payroll calculation core.

The public API intentionally contains no Django or EUSRR imports. Host
applications are expected to resolve employees, rates and persistence before
calling the calculator.
"""

from .calculator import DeterministicPayrollCalculator, PayrollCalculator
from .domain import (
    CalculationWarning,
    ExpectedTotals,
    InputLine,
    LineKind,
    PayrollLine,
    PayrollPeriod,
    PayrollRequest,
    PayrollResult,
    PayrollRules,
    PayrollTotals,
    PointPolicy,
    RoundingPolicy,
)
from .exceptions import PayrollIssue, PayrollValidationError

__all__ = [
    "CalculationWarning",
    "DeterministicPayrollCalculator",
    "ExpectedTotals",
    "InputLine",
    "LineKind",
    "PayrollCalculator",
    "PayrollIssue",
    "PayrollLine",
    "PayrollPeriod",
    "PayrollRequest",
    "PayrollResult",
    "PayrollRules",
    "PayrollTotals",
    "PayrollValidationError",
    "PointPolicy",
    "RoundingPolicy",
]

__version__ = "0.1.0"
