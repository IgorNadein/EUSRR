from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from employees.constants import (
    ACTION_DISMISSED,
    ACTION_WORKING,
    ACTION_LABELS,
    ACTIVATING_MARKER_ACTIONS,
    MARKER_ACTIONS,
    PERMANENT_ACTIONS,
    RETURN_MARKER_ACTIONS,
    TEMPORARY_ACTION_PRIORITIES,
    TEMPORARY_START_ACTIONS,
)
from employees.models import Employee, EmployeeAction

PERSONNEL_STATUS_NORMAL = "normal"


@dataclass(frozen=True)
class EmployeePersonnelState:
    status: str = PERSONNEL_STATUS_NORMAL
    label: str = ""
    action_id: int | None = None
    date_from: date | None = None
    date_to: date | None = None
    expects_attendance: bool = True

    @property
    def is_non_working(self) -> bool:
        return not self.expects_attendance


def resolve_employee_personnel_state(
    employee: Employee,
    target_date: date,
    *,
    actions: Iterable[EmployeeAction] | None = None,
) -> EmployeePersonnelState:
    employee_actions = _sorted_actions(
        actions
        if actions is not None
        else employee.actions.select_related("source_request").all()
    )
    relevant_actions = [
        action
        for action in employee_actions
        if action.date and action.date.date() <= target_date
    ]
    if not relevant_actions:
        return EmployeePersonnelState()

    permanent_action = _resolve_permanent_action(relevant_actions)
    if permanent_action and permanent_action.action == ACTION_DISMISSED:
        return EmployeePersonnelState(
            status=ACTION_DISMISSED,
            label=ACTION_LABELS[ACTION_DISMISSED],
            action_id=permanent_action.id,
            date_from=permanent_action.date.date(),
            expects_attendance=False,
        )

    active_temporary = _active_temporary_actions(employee_actions, target_date)
    if active_temporary:
        action, date_to = active_temporary[0]
        return EmployeePersonnelState(
            status=action.action,
            label=action.get_action_display(),
            action_id=action.id,
            date_from=action.date.date(),
            date_to=date_to,
            expects_attendance=False,
        )

    marker_action = _active_marker_action(relevant_actions, target_date)
    if marker_action:
        return EmployeePersonnelState(
            status=marker_action.action,
            label=marker_action.get_action_display(),
            action_id=marker_action.id,
            date_from=marker_action.date.date(),
            expects_attendance=True,
        )

    if permanent_action:
        return EmployeePersonnelState(
            status=permanent_action.action,
            label=permanent_action.get_action_display(),
            action_id=permanent_action.id,
            date_from=permanent_action.date.date(),
        )

    return EmployeePersonnelState(
        status=ACTION_WORKING,
        label=ACTION_LABELS[ACTION_WORKING],
    )


def _sorted_actions(actions: Iterable[EmployeeAction]) -> list[EmployeeAction]:
    return sorted(
        actions,
        key=lambda action: (
            action.date or datetime.min,
            action.id or 0,
        ),
    )


def _resolve_permanent_action(
    actions: Iterable[EmployeeAction],
) -> EmployeeAction | None:
    permanent_actions = [
        action for action in actions if action.action in PERMANENT_ACTIONS
    ]
    if not permanent_actions:
        return None

    last_permanent = permanent_actions[-1]
    if last_permanent.action != ACTION_DISMISSED:
        return last_permanent

    activation_after_dismissal = [
        action
        for action in actions
        if action.action in ACTIVATING_MARKER_ACTIONS
        and action.date
        and last_permanent.date
        and action.date >= last_permanent.date
    ]
    if not activation_after_dismissal:
        return last_permanent

    restored_state = [
        action
        for action in permanent_actions[:-1]
        if action.action != ACTION_DISMISSED
    ]
    return restored_state[-1] if restored_state else None


def _active_marker_action(
    actions: list[EmployeeAction],
    target_date: date,
) -> EmployeeAction | None:
    marker_actions = [
        action
        for action in actions
        if action.action in MARKER_ACTIONS
        and action.date
        and action.date.date() == target_date
    ]
    return marker_actions[-1] if marker_actions else None


def _active_temporary_actions(
    actions: list[EmployeeAction],
    target_date: date,
) -> list[tuple[EmployeeAction, date | None]]:
    active = []
    for action in actions:
        if action.action not in TEMPORARY_START_ACTIONS or not action.date:
            continue

        date_from = action.date.date()
        if date_from > target_date:
            continue

        date_to = _resolve_temporary_action_date_to(action)
        if date_to is not None and date_to < target_date:
            continue

        active.append((action, date_to))

    return sorted(
        active,
        key=lambda item: (
            TEMPORARY_ACTION_PRIORITIES.get(item[0].action, 99),
            -(item[0].date.timestamp() if item[0].date else 0),
            -(item[0].id or 0),
        ),
    )


def _resolve_temporary_action_date_to(action: EmployeeAction) -> date | None:
    if action.date_to:
        return action.date_to
    if action.date:
        return action.date.date()
    return None


def is_temporary_start_action(action: str) -> bool:
    return action in TEMPORARY_START_ACTIONS


def is_temporary_return_action(action: str) -> bool:
    return action in RETURN_MARKER_ACTIONS


def action_expects_attendance(action: str) -> bool:
    return action not in TEMPORARY_START_ACTIONS and action != ACTION_DISMISSED
