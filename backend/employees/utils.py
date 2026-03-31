from __future__ import annotations

import phonenumbers
from django.conf import settings
from django.contrib.auth import get_user_model

from employees.models import (
    Department,
    DepartmentPermission,
    DeptPerm,
    EmployeeDepartment,
)
from phonenumbers import PhoneNumberFormat


Employee = get_user_model()


def _to_bool(val: str | None) -> bool | None:
    if val is None:
        return None
    s = str(val).strip().lower()
    if s in {"1", "true", "yes", "да"}:
        return True
    if s in {"0", "false", "no", "нет"}:
        return False
    return None


def _normalize_phone(raw: str | None) -> str | None:
    if not raw:
        return None
    if phonenumbers is None:
        return str(raw).strip()
    region = getattr(settings, "PHONE_DEFAULT_REGION", "RU")
    try:
        pn = phonenumbers.parse(str(raw), region)
        if not phonenumbers.is_valid_number(pn):
            return None
        return phonenumbers.format_number(pn, PhoneNumberFormat.E164)
    except Exception:
        return None


def _detect_phone_field() -> str | None:
    for n in ("phone", "phone_number", "mobile", "msisdn", "tel"):
        if any(f.name == n for f in Employee._meta.fields):
            return n
    return None


def _validate_head_active(
    dept: Department,
    employee_id: int,
    require_email_verified: bool = True,
) -> tuple[bool, dict | None]:
    """
    Проверить, можно ли назначить сотрудника руководителем отдела.

    Parameters
    ----------
    dept : Department
        Отдел, в который назначается руководитель.
    employee_id : int
        Кандидат на роль руководителя.
    require_email_verified : bool, optional
        Требовать ли подтверждение email. Для действий, совершаемых не-руководителем,
        оставляем True; для действий текущего руководителя можно ослабить до False.

    Returns
    -------
    (True, None) | (False, {"head_id": [..]})
        True — назначать можно; False — нельзя (причина в словаре).
    """
    employee_model = Department._meta.get_field("head").remote_field.model
    emp = employee_model.objects.filter(id=employee_id).first()
    if not emp:
        return False, {"head_id": ["Employee not found."]}

    # Должен быть включён аккаунт
    if getattr(emp, "is_active", True) is False:
        return False, {"head_id": ["Employee is inactive."]}

    # Требование верификации email — опционально
    if require_email_verified and getattr(emp, "email_verified", True) is False:
        return False, {"head_id": ["Employee is inactive."]}

    return True, None


def _ensure_department_permissions() -> list[dict]:
    """
    Гарантирует наличие записей DepartmentPermission на основе DeptPerm.CHOICES.
    Возвращает список словарей {id, code, name} в порядке CHOICES.
    """
    items: list[dict] = []
    # пробежимся по CHOICES, создадим/обновим имя, соберём выдачу
    for code, label in DeptPerm.CHOICES:
        obj, _ = DepartmentPermission.objects.get_or_create(
            code=code, defaults={"name": label}
        )
        # если имя в БД отстаёт от CHOICES — мягко синхронизируем
        if obj.name != label:
            obj.name = label
            obj.save(update_fields=["name"])
        items.append({"id": obj.id, "code": obj.code, "name": obj.name})
    return items


def _head_choices_for_dept(dept: Department, serializer) -> list[dict]:
    """
    Вернёт список кандидатов для назначения руководителя отдела.

    Формат элемента:
      {
        "id": int,            # ID сотрудника
        "name": str,          # display_name из EmployeeBriefSerializer
        "email": str          # email сотрудника (может быть пустой строкой)
      }
    """
    choices, seen = [], set()
    qs = (
        EmployeeDepartment.objects.filter(department_id=dept.id)
        .select_related("employee")
        .order_by(
            "employee__last_name",
            "employee__first_name",
            "employee__patronymic",
            "employee_id",
        )
    )
    for link in qs:
        data = serializer(link.employee).data
        if data["id"] not in seen:
            choices.append(
                {
                    "id": data["id"],
                    "name": data["display_name"],
                    "email": data.get("email", "") or "",
                }
            )
            seen.add(data["id"])

    if dept.head_id and dept.head_id not in seen:
        head_data = serializer(dept.head).data
        choices.insert(
            0,
            {
                "id": head_data["id"],
                "name": head_data["display_name"],
                "email": head_data.get("email", "") or "",
            },
        )

    return choices


def _perm_choices_synced() -> list[dict]:
    """
    Возвращает справочник прав для ролей отдела, синхронизируя записи с DeptPerm.CHOICES.
    """
    items = []
    for code, label in DeptPerm.CHOICES:
        obj, _ = DepartmentPermission.objects.get_or_create(
            code=code, defaults={"name": label}
        )
        if obj.name != label:
            obj.name = label
            obj.save(update_fields=["name"])
        items.append({"id": obj.id, "code": obj.code, "name": obj.name})
    return items


def _build_links_for_dept(dept: Department, serializer) -> list[dict]:
    """
    Возвращает список линков отдела:
    [{ "employee": <EmployeeBriefSerializer.data>, "role": {"id","name"}|None, "is_active": bool }, ...]
    """
    links: list[dict] = []
    qs = (
        EmployeeDepartment.objects.filter(department_id=dept.id)
        .select_related("employee", "role")
        .order_by(
            "employee__last_name",
            "employee__first_name",
            "employee__patronymic",
            "employee_id",
        )
    )
    for link in qs:
        emp_data = serializer(link.employee).data  # содержит display_name
        role = {"id": link.role_id, "name": link.role.name} if link.role_id else None
        links.append(
            {"employee": emp_data, "role": role, "is_active": bool(link.is_active)}
        )

    # гарантируем присутствие head
    if dept.head_id and all(item["employee"]["id"] != dept.head_id for item in links):
        head_data = serializer(dept.head).data
        links.insert(0, {"employee": head_data, "role": None, "is_active": True})

    return links


# ===== Communications callbacks (EUSRR-specific) =====

def resolve_chat_participants_for_department(context_object, **kwargs):
    """
    EUSRR callback для разрешения участников чата отдела.

    Args:
        context_object: Department instance
        **kwargs: Дополнительные параметры (chat, type и т.д.)

    Returns:
        QuerySet Employee objects - участники чата
    """
    from django.db.models import Q

    # Проверяем что это Department
    if not isinstance(context_object, Department):
        return Employee.objects.none()

    department = context_object

    # Получаем активных сотрудников отдела
    employee_ids = EmployeeDepartment.objects.filter(
        department_id=department.id,
        is_active=True
    ).values_list("employee_id", flat=True)

    # Включаем руководителя отдела
    return Employee.objects.filter(
        Q(id__in=employee_ids) | Q(id=department.head_id)
    ).distinct()


def resolve_chat_participants(chat):
    """
    Главная функция для разрешения участников чата в EUSRR.

    Вызывается из Chat.get_participants() через настройки.

    Args:
        chat: Chat instance

    Returns:
        QuerySet Employee objects или None (если не обработали)
    """
    from django.db.models import Q

    # 1. Приватные чаты - используем M2M participants
    if chat.type == "private":
        return chat.participants.all()

    # 2. Глобальные чаты - все активные пользователи
    if chat.type == "global":
        return Employee.objects.filter(is_active=True)

    # 3. Announcement / Channel с include_all_users
    if chat.type in ["announcement", "channel"] and chat.include_all_users:
        return Employee.objects.filter(is_active=True)

    # 4. Context-based чаты
    if chat.context_object:
        # Department context
        if isinstance(chat.context_object, Department):
            return resolve_chat_participants_for_department(
                chat.context_object,
                chat=chat,
                type=chat.type
            )

        # Можно добавить другие типы контекстов:
        # - Project
        # - Team
        # - Event
        # и т.д.

    # 5. Legacy: department field (DEPRECATED, для обратной совместимости)
    if chat.type == "department" and hasattr(chat, 'department') and chat.department_id:
        employee_ids = EmployeeDepartment.objects.filter(
            department_id=chat.department_id,
            is_active=True
        ).values_list("employee_id", flat=True)

        return Employee.objects.filter(
            Q(id__in=employee_ids) | Q(id=chat.department.head_id)
        ).distinct()

    # 6. Fallback: ChatMembership или participants
    from communications.models import ChatMembership

    membership_ids = ChatMembership.objects.filter(
        chat=chat
    ).values_list("user_id", flat=True)

    participant_ids = chat.participants.values_list('id', flat=True)

    return Employee.objects.filter(
        Q(id__in=participant_ids) | Q(id__in=membership_ids)
    ).distinct()
