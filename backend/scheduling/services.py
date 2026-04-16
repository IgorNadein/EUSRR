from __future__ import annotations

from collections import defaultdict
from typing import Iterable

from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.db import transaction

from employees.models import Department, EmployeeDepartment, RoleAssignment
from schedule.models import Calendar, CalendarRelation, Event

from .models import CalendarBinding

User = get_user_model()


def get_calendar_binding(calendar: Calendar | None) -> CalendarBinding | None:
    if calendar is None:
        return None
    binding = getattr(calendar, "binding", None)
    if binding is not None:
        return binding
    return (
        CalendarBinding.objects.select_related("context_content_type")
        .filter(calendar=calendar)
        .first()
    )


def is_department_calendar(calendar: Calendar | None) -> bool:
    binding = get_calendar_binding(calendar)
    return bool(
        binding and binding.type == CalendarBinding.BindingType.DEPARTMENT
    )


def get_department_calendar_binding(
    department: Department,
) -> CalendarBinding | None:
    dept_ct = ContentType.objects.get_for_model(Department)
    return (
        CalendarBinding.objects.select_related("calendar")
        .filter(
            type=CalendarBinding.BindingType.DEPARTMENT,
            context_content_type=dept_ct,
            context_object_id=department.id,
        )
        .first()
    )


def department_calendar_name(department: Department) -> str:
    return department.name


def department_calendar_slug(department: Department) -> str:
    return f"department-{department.id}"


def _unique_calendar_slug(base_slug: str) -> str:
    if not Calendar.objects.filter(slug=base_slug).exists():
        return base_slug

    counter = 1
    while Calendar.objects.filter(slug=f"{base_slug}-{counter}").exists():
        counter += 1
    return f"{base_slug}-{counter}"


def _find_existing_department_calendar(
    department: Department,
) -> Calendar | None:
    slug = department_calendar_slug(department)
    return (
        Calendar.objects.filter(slug=slug)
        .exclude(binding__isnull=False)
        .order_by("-id")
        .first()
    )


@transaction.atomic
def get_or_create_department_calendar(
    department: Department,
) -> tuple[Calendar, CalendarBinding]:
    binding = get_department_calendar_binding(department)
    if binding:
        sync_department_calendar_binding(department, binding=binding)
        return binding.calendar, binding

    calendar = _find_existing_department_calendar(department)
    if calendar is None:
        calendar = Calendar.objects.create(
            name=department_calendar_name(department),
            slug=_unique_calendar_slug(department_calendar_slug(department)),
        )

    dept_ct = ContentType.objects.get_for_model(Department)
    binding, _ = CalendarBinding.objects.get_or_create(
        calendar=calendar,
        defaults={
            "type": CalendarBinding.BindingType.DEPARTMENT,
            "context_content_type": dept_ct,
            "context_object_id": department.id,
        },
    )

    if (
        binding.type != CalendarBinding.BindingType.DEPARTMENT
        or binding.context_content_type_id != dept_ct.id
        or binding.context_object_id != department.id
    ):
        binding.type = CalendarBinding.BindingType.DEPARTMENT
        binding.context_content_type = dept_ct
        binding.context_object_id = department.id
        binding.save(
            update_fields=[
                "type",
                "context_content_type",
                "context_object_id",
                "updated_at",
            ]
        )

    sync_department_calendar_binding(department, binding=binding)
    return binding.calendar, binding


def _department_participant_ids(department: Department) -> set[int]:
    ids: set[int] = set(
        EmployeeDepartment.objects.filter(
            department=department,
            is_active=True,
            employee__is_active=True,
        ).values_list("employee_id", flat=True)
    )

    role_only_ids = RoleAssignment.objects.filter(
        role__department=department,
        is_active=True,
        employee__is_active=True,
    ).values_list("employee_id", flat=True)
    ids.update(role_only_ids)

    if department.head_id:
        ids.add(department.head_id)

    return ids


def _set_relation_role(
    calendar: Calendar, user_id: int, distinction: str
) -> None:
    user_ct = ContentType.objects.get_for_model(User)
    relations = list(
        CalendarRelation.objects.filter(
            calendar=calendar,
            content_type=user_ct,
            object_id=user_id,
        ).order_by("id")
    )
    if relations:
        primary = relations[0]
        changed = False
        if primary.distinction != distinction:
            primary.distinction = distinction
            changed = True
        if primary.inheritable is not True:
            primary.inheritable = True
            changed = True
        if changed:
            primary.save(update_fields=["distinction", "inheritable"])
        if len(relations) > 1:
            CalendarRelation.objects.filter(
                id__in=[relation.id for relation in relations[1:]]
            ).delete()
        return

    calendar.create_relation(
        User.objects.get(pk=user_id),
        distinction=distinction,
        inheritable=True,
    )


def sync_department_calendar_owner(
    department: Department, *, binding: CalendarBinding | None = None
) -> Calendar | None:
    binding = binding or get_department_calendar_binding(department)
    if not binding:
        return None

    calendar = binding.calendar
    desired_owner_id = department.head_id
    user_ct = ContentType.objects.get_for_model(User)

    owner_relations = CalendarRelation.objects.filter(
        calendar=calendar,
        content_type=user_ct,
        distinction="owner",
    ).order_by("id")

    if desired_owner_id is None:
        owner_relations.delete()
        return calendar

    _set_relation_role(calendar, desired_owner_id, "owner")

    owner_relations.exclude(object_id=desired_owner_id).delete()
    return calendar


def sync_department_calendar_members(
    department: Department, *, binding: CalendarBinding | None = None
) -> Calendar | None:
    binding = binding or get_department_calendar_binding(department)
    if not binding:
        return None

    calendar = binding.calendar
    desired_ids = _department_participant_ids(department)
    owner_id = department.head_id
    user_ct = ContentType.objects.get_for_model(User)

    existing_relations = list(
        CalendarRelation.objects.filter(
            calendar=calendar,
            content_type=user_ct,
        ).order_by("id")
    )
    existing_ids = {relation.object_id for relation in existing_relations}

    if owner_id:
        _set_relation_role(calendar, owner_id, "owner")

    for user_id in sorted(desired_ids):
        if user_id == owner_id:
            continue
        _set_relation_role(calendar, user_id, "editor")

    stale_relation_ids = [
        relation.id
        for relation in existing_relations
        if relation.object_id not in desired_ids
    ]
    if stale_relation_ids:
        CalendarRelation.objects.filter(id__in=stale_relation_ids).delete()

    return calendar


def sync_department_calendar_binding(
    department: Department, *, binding: CalendarBinding | None = None
) -> Calendar | None:
    binding = binding or get_department_calendar_binding(department)
    if not binding:
        return None

    calendar = binding.calendar
    desired_name = department_calendar_name(department)
    if calendar.name != desired_name:
        calendar.name = desired_name
        calendar.save(update_fields=["name"])

    sync_department_calendar_owner(department, binding=binding)
    sync_department_calendar_members(department, binding=binding)
    return calendar


def sync_department_calendar_if_bound(department: Department) -> None:
    binding = get_department_calendar_binding(department)
    if not binding:
        return
    sync_department_calendar_binding(department, binding=binding)


def sync_department_calendar_binding_by_department_id(department_id: int) -> None:
    try:
        department = Department.objects.get(pk=department_id)
    except Department.DoesNotExist:
        return
    sync_department_calendar_if_bound(department)


def delete_department_calendar(department_id: int) -> None:
    try:
        department = Department.objects.get(pk=department_id)
    except Department.DoesNotExist:
        department = None

    if department:
        binding = get_department_calendar_binding(department)
    else:
        dept_ct = ContentType.objects.get_for_model(Department)
        binding = CalendarBinding.objects.filter(
            type=CalendarBinding.BindingType.DEPARTMENT,
            context_content_type=dept_ct,
            context_object_id=department_id,
        ).select_related("calendar").first()

    if binding:
        binding.calendar.delete()


def user_relation_distinction(
    calendar: Calendar, user
) -> str | None:
    if not getattr(user, "is_authenticated", False):
        return None
    if user.is_staff or user.is_superuser:
        return "owner"

    user_ct = ContentType.objects.get_for_model(User)
    relation = CalendarRelation.objects.filter(
        calendar=calendar,
        content_type=user_ct,
        object_id=user.id,
    ).order_by("id").first()
    return relation.distinction if relation else None


def user_can_view_calendar(user, calendar: Calendar) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff or user.is_superuser:
        return True
    if is_department_calendar(calendar):
        return True
    return user_relation_distinction(calendar, user) is not None


def user_can_create_event(user, calendar: Calendar) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff or user.is_superuser:
        return True
    if is_department_calendar(calendar):
        return True
    return user_relation_distinction(calendar, user) in {"owner", "editor"}


def user_can_edit_calendar(user, calendar: Calendar) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff or user.is_superuser:
        return True
    return user_relation_distinction(calendar, user) == "owner"


def user_can_manage_participants(user, calendar: Calendar) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff or user.is_superuser:
        return True
    if is_department_calendar(calendar):
        return False
    return user_relation_distinction(calendar, user) == "owner"


def user_can_edit_event(user, event: Event) -> bool:
    if not getattr(user, "is_authenticated", False):
        return False
    if user.is_staff or user.is_superuser:
        return True

    calendar = event.calendar
    if is_department_calendar(calendar):
        relation = user_relation_distinction(calendar, user)
        if relation in {"owner", "editor"}:
            return True
        return event.creator_id == user.id

    return user_relation_distinction(calendar, user) in {"owner", "editor"}


def user_can_delete_event(user, event: Event) -> bool:
    return user_can_edit_event(user, event)
