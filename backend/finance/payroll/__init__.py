"""EUSRR adapter for the project-independent :mod:`payroll_core` package."""

from .services import (
    acknowledge_statement,
    approve_input_line,
    approve_pay_rate,
    approve_run,
    approve_work_record,
    calculate_period,
    clear_component_input_lines,
    bulk_set_target_points,
    close_period,
    publish_run,
    return_run_for_correction,
    submit_run_for_review,
)

__all__ = [
    "acknowledge_statement",
    "approve_input_line",
    "approve_pay_rate",
    "approve_run",
    "approve_work_record",
    "calculate_period",
    "clear_component_input_lines",
    "bulk_set_target_points",
    "close_period",
    "publish_run",
    "return_run_for_correction",
    "submit_run_for_review",
]
