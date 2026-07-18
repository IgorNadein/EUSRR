"""Public error types returned by the payroll core."""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from typing import Mapping


@dataclass(frozen=True, slots=True)
class PayrollIssue:
    """A machine-readable validation or calculation issue."""

    code: str
    message: str
    field: str | None = None
    context: Mapping[str, str] = dataclass_field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        return {
            "code": self.code,
            "message": self.message,
            "field": self.field,
            "context": dict(self.context),
        }


class PayrollValidationError(ValueError):
    """Raised when calculation input cannot be processed safely."""

    def __init__(self, issues: tuple[PayrollIssue, ...] | list[PayrollIssue]):
        self.issues = tuple(issues)
        message = "; ".join(f"{issue.code}: {issue.message}" for issue in self.issues)
        super().__init__(message or "Payroll validation failed")
