"""Application-level errors raised by the Django payroll adapter."""

from __future__ import annotations

from typing import Mapping


class PayrollOperationError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        details: Mapping[str, object] | None = None,
    ):
        self.code = code
        self.message = message
        self.details = dict(details or {})
        super().__init__(f"{code}: {message}")


class PayrollPermissionDenied(PayrollOperationError):
    def __init__(self, permission: str):
        super().__init__(
            "PERMISSION_DENIED",
            "Недостаточно прав для операции с зарплатой.",
            details={"permission": permission},
        )
