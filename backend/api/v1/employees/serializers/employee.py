"""Сериализаторы для сотрудников (Employee)."""

from collections import defaultdict
from typing import Any, Dict

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from django.contrib.auth import get_user_model
from django.contrib.contenttypes.models import ContentType
from django.utils import timezone
from employees.models import EmployeeDepartment, Position, Skill
from employees.services.personnel_state import resolve_employee_personnel_state
from eusrr_backend.auth_backends import PHONE_FIELD as DETECTED_PHONE_FIELD
from rest_framework import serializers

from api.v1.serializers import Base64ImageField

from .shared import (
    EmployeeActionSerializer,
    PositionBriefSerializer,
    SkillSerializer,
)

Employee = get_user_model()


def _linked_task_payloads_for_employee(obj, user) -> list[dict]:
    if not user or not getattr(user, "is_authenticated", False):
        return []

    try:
        from tasks.access import task_board_access_q
        from tasks.models import (
            TaskBoard,
            TaskLinkedObject,
            TaskLinkedObjectKind,
        )
    except Exception:
        return []

    content_type = ContentType.objects.get_for_model(Employee)
    accessible_boards = TaskBoard.objects.filter(
        is_archived=False,
    ).filter(task_board_access_q(user))

    links = (
        TaskLinkedObject.objects.filter(
            kind=TaskLinkedObjectKind.EMPLOYEE,
            content_type=content_type,
            object_id=obj.id,
            task__board__in=accessible_boards,
        )
        .select_related("task", "task__board", "task__column")
        .order_by("task__title", "task_id")
    )

    return [
        {
            "link_id": link.id,
            "id": link.task_id,
            "title": link.task.title,
            "board_id": link.task.board_id,
            "board_name": link.task.board.name,
            "column_id": link.task.column_id,
            "column_name": link.task.column.name,
            "column_color": link.task.column.color,
            "priority": link.task.priority,
            "priority_display": link.task.get_priority_display(),
        }
        for link in links
    ]


def _employee_personnel_state_payload(obj):
    prefetched = getattr(obj, "_prefetched_objects_cache", {})
    actions = prefetched.get("actions") if prefetched else None
    state = resolve_employee_personnel_state(
        obj,
        timezone.localdate(),
        actions=actions,
    )
    return {
        "status": state.status,
        "label": state.label or "Работает",
        "action_id": state.action_id,
        "date_from": state.date_from,
        "date_to": state.date_to,
        "expects_attendance": state.expects_attendance,
    }


def _normalize_attendance_time(value) -> str | None:
    if not value:
        return None
    text = str(value).strip()
    if not text:
        return None
    if "T" in text:
        text = text.split("T", 1)[1]
    if len(text) >= 5 and text[2] == ":":
        return text[:5]
    return text


def _employee_attendance_status_payload(obj):
    has_attendance_annotation = hasattr(obj, "latest_attendance_record_id")
    record_id = getattr(obj, "latest_attendance_record_id", None)
    record_date = getattr(obj, "latest_attendance_date", None)
    arrival_time = getattr(obj, "latest_attendance_arrival_time", None)
    departure_time = getattr(obj, "latest_attendance_departure_time", None)

    if (
        record_id is None
        and not has_attendance_annotation
        and hasattr(obj, "attendance_records")
    ):
        latest_record = obj.attendance_records.order_by("-date", "-id").first()
        if latest_record is not None:
            record_id = latest_record.id
            record_date = latest_record.date
            arrival_time = latest_record.arrival_time
            departure_time = latest_record.departure_time

    if record_id is None or record_date is None:
        return None

    event = "none"
    label = "Без отметок"
    time_value = None

    departure = _normalize_attendance_time(departure_time)
    arrival = _normalize_attendance_time(arrival_time)
    if departure:
        event = "departure"
        label = "Уход"
        time_value = departure
    elif arrival:
        event = "arrival"
        label = "Приход"
        time_value = arrival

    if hasattr(record_date, "strftime"):
        display_date = record_date.strftime("%d.%m.%Y")
    else:
        display_date = str(record_date)

    display = f"{label} · {display_date}"
    if time_value:
        display = f"{display}, {time_value}"

    return {
        "record_id": record_id,
        "date": record_date,
        "time": time_value,
        "event": event,
        "label": label,
        "display": display,
    }


class EmployeeDepartmentSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField(allow_null=True)
    role_id = serializers.IntegerField(allow_null=True)
    role_name = serializers.CharField(allow_null=True)
    is_head = serializers.BooleanField()
    via_assignment = serializers.BooleanField(required=False)


class EmployeeDepartmentRelationSerializer(serializers.Serializer):
    is_member = serializers.BooleanField()
    is_head = serializers.BooleanField()
    has_role_only = serializers.BooleanField()
    role_names = serializers.ListField(child=serializers.CharField())


class EmployeePersonnelStateSerializer(serializers.Serializer):
    status = serializers.CharField()
    label = serializers.CharField(allow_blank=True)
    action_id = serializers.IntegerField(allow_null=True)
    date_from = serializers.DateField(allow_null=True)
    date_to = serializers.DateField(allow_null=True)
    expects_attendance = serializers.BooleanField()


class EmployeeAttendanceStatusSerializer(serializers.Serializer):
    record_id = serializers.IntegerField()
    date = serializers.DateField()
    time = serializers.CharField(allow_null=True)
    event = serializers.CharField()
    label = serializers.CharField()
    display = serializers.CharField()


class EmployeeSerializer(serializers.ModelSerializer):
    """Полная версия сотрудника для /employees/."""

    avatar = Base64ImageField(required=False, allow_null=True)
    attendance_aliases = serializers.ListField(
        child=serializers.CharField(allow_blank=True),
        required=False,
        allow_empty=True,
    )
    actions = EmployeeActionSerializer(many=True, read_only=True)
    username = serializers.CharField(read_only=True, allow_blank=True)
    last_activity_at = serializers.SerializerMethodField()

    skills = SkillSerializer(many=True, read_only=True)
    skills_ids = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.all(), many=True, write_only=True, required=False
    )

    position = PositionBriefSerializer(read_only=True)
    position_id = serializers.PrimaryKeyRelatedField(
        source="position",
        queryset=Position.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )

    departments = serializers.SerializerMethodField()
    auth = serializers.SerializerMethodField(read_only=True)
    personnel_state = serializers.SerializerMethodField(read_only=True)
    attendance_status = serializers.SerializerMethodField(read_only=True)
    linked_tasks = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = (
            "avatar",
            "actions",
            "id",
            "username",
            "is_ldap_managed",
            "email",
            "last_name",
            "first_name",
            "patronymic",
            "departments",
            "gender",
            "phone_number",
            "birth_date",
            "position",
            "position_id",
            "telegram",
            "whatsapp",
            "wechat",
            "attendance_aliases",
            "skills",
            "skills_ids",
            "is_active",
            "email_verified",
            "created_at",
            "updated_at",
            "last_login",
            "last_activity_at",
            "date_joined",
            "auth",
            "personnel_state",
            "attendance_status",
            "linked_tasks",
        )
        read_only_fields = (
            "is_ldap_managed",
            "is_active",
            "email_verified",
            "created_at",
            "updated_at",
            "last_login",
            "last_activity_at",
            "date_joined",
            "auth",
            "personnel_state",
            "attendance_status",
            "linked_tasks",
        )
        extra_kwargs = {
            "password": {"write_only": True, "required": False},
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        return data

    def validate_avatar(self, value):
        if value == "":
            return None
        return value

    def validate_attendance_aliases(self, value):
        result = []
        for alias in value or []:
            alias_value = str(alias).strip()
            if alias_value and alias_value not in result:
                result.append(alias_value)
        return result

    def update(self, instance, validated_data):
        skills = validated_data.pop("skills_ids", None)

        if "avatar" in validated_data and validated_data["avatar"] is None:
            validated_data.pop("avatar")

        instance = super().update(instance, validated_data)
        if skills is not None:
            instance.skills.set(skills)
        return instance

    @extend_schema_field(EmployeeDepartmentSerializer(many=True))
    def get_departments(self, obj):
        from employees.models import RoleAssignment

        links = getattr(obj, "dept_links", None)
        if links is None:
            links = EmployeeDepartment.objects.select_related(
                "department", "role"
            ).filter(employee=obj, is_active=True)

        out = []
        member_dept_ids = set()

        for link in links:
            dept = link.department
            member_dept_ids.add(link.department_id)
            out.append(
                {
                    "id": link.department_id,
                    "name": dept.name if link.department_id else None,
                    "role_id": link.role_id,
                    "role_name": link.role.name if link.role_id else None,
                    "is_head": (dept.head_id == obj.id),
                    "via_assignment": False,
                }
            )

        role_assignments = RoleAssignment.objects.select_related(
            "role__department"
        ).filter(employee=obj, is_active=True)

        for ra in role_assignments:
            dept = ra.role.department
            if dept.id in member_dept_ids:
                continue

            existing = next(
                (
                    d
                    for d in out
                    if d["id"] == dept.id and d.get("via_assignment")
                ),
                None,
            )
            if existing:
                existing["role_name"] = (
                    f"{existing['role_name']}, {ra.role.name}"
                    if existing.get("role_name")
                    else ra.role.name
                )
            else:
                out.append(
                    {
                        "id": dept.id,
                        "name": dept.name,
                        "role_id": ra.role_id,
                        "role_name": ra.role.name,
                        "is_head": False,
                        "via_assignment": True,
                    }
                )

        return out

    def get_fields(self):
        fields = super().get_fields()

        if self.context.get("include_actions") is not True:
            view = self.context.get("view")
            action = getattr(view, "action", None) if view else None
            if action not in {"retrieve", "me"}:
                fields.pop("actions", None)

        include_auth = self.context.get("include_auth") is True
        view = self.context.get("view")
        action = getattr(view, "action", None) if view else None
        if not include_auth and action != "me":
            fields.pop("auth", None)
        if action != "me":
            fields.pop("username", None)

        return fields

    @extend_schema_field(OpenApiTypes.DATETIME)
    def get_last_activity_at(self, obj):
        return getattr(obj, "last_activity_at", None)

    @extend_schema_field(OpenApiTypes.OBJECT)
    def get_auth(self, obj):
        req = self.context.get("request")
        if not req or not getattr(req.user, "is_authenticated", False):
            return None

        include_auth = self.context.get("include_auth") is True
        if not include_auth and req.user.pk != getattr(obj, "pk", None):
            return None

        u = req.user
        perms = sorted(u.get_all_permissions())

        by_app = defaultdict(list)
        for p in perms:
            app, code = p.split(".", 1)
            by_app[app].append(code)
        perms_by_app = {app: sorted(codes) for app, codes in by_app.items()}

        return {
            "id": u.id,
            "email": u.email or "",
            "is_staff": u.is_staff,
            "is_superuser": u.is_superuser,
            "groups": list(u.groups.values_list("name", flat=True)),
            "permissions": perms,
            "permissions_by_app": perms_by_app,
        }

    @extend_schema_field(EmployeePersonnelStateSerializer())
    def get_personnel_state(self, obj):
        return _employee_personnel_state_payload(obj)

    @extend_schema_field(EmployeeAttendanceStatusSerializer(allow_null=True))
    def get_attendance_status(self, obj):
        return _employee_attendance_status_payload(obj)

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_linked_tasks(self, obj):
        prefetched = getattr(obj, "_linked_task_payloads", None)
        if prefetched is not None:
            return prefetched

        request = self.context.get("request")
        user = getattr(request, "user", None)
        return _linked_task_payloads_for_employee(obj, user)


class EmployeeBriefSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    avatar = serializers.ImageField(read_only=True)
    full_name = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = (
            "id",
            "first_name",
            "last_name",
            "patronymic",
            "email",
            "phone_number",
            "display_name",
            "full_name",
            "avatar",
        )

    @extend_schema_field(serializers.CharField())
    def get_display_name(self, obj) -> str:
        parts = [
            obj.last_name or "",
            obj.first_name or "",
            obj.patronymic or "",
        ]
        fio = " ".join(p.strip() for p in parts if p)
        if fio:
            return fio
        if getattr(obj, "email", None):
            return obj.email
        if getattr(obj, "phone_number", None):
            return obj.phone_number
        return f"Сотрудник #{obj.id}"

    @extend_schema_field(serializers.CharField())
    def get_full_name(self, obj: Employee) -> str:
        parts = [
            obj.last_name or "",
            obj.first_name or "",
            getattr(obj, "patronymic", "") or "",
        ]
        return " ".join(p.strip() for p in parts if p)


class EmployeeListSerializer(serializers.ModelSerializer):
    """Списочное представление сотрудника."""

    display_name = serializers.SerializerMethodField()
    email = serializers.EmailField(read_only=True)
    phone_number = serializers.CharField(read_only=True)
    avatar = serializers.ImageField(read_only=True)
    position = PositionBriefSerializer(read_only=True)
    departments = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    skills = SkillSerializer(many=True, read_only=True)
    department_relation = serializers.SerializerMethodField()
    personnel_state = serializers.SerializerMethodField(read_only=True)
    attendance_status = serializers.SerializerMethodField(read_only=True)
    linked_tasks = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = (
            "id",
            "email",
            "phone_number",
            "last_name",
            "first_name",
            "patronymic",
            "full_name",
            "avatar",
            "position",
            "departments",
            "skills",
            "created_at",
            "display_name",
            "department_relation",
            "personnel_state",
            "attendance_status",
            "linked_tasks",
        )

    @extend_schema_field(EmployeePersonnelStateSerializer())
    def get_personnel_state(self, obj):
        return _employee_personnel_state_payload(obj)

    @extend_schema_field(EmployeeAttendanceStatusSerializer(allow_null=True))
    def get_attendance_status(self, obj):
        return _employee_attendance_status_payload(obj)

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_linked_tasks(self, obj):
        prefetched = getattr(obj, "_linked_task_payloads", None)
        if prefetched is not None:
            return prefetched

        request = self.context.get("request")
        user = getattr(request, "user", None)
        return _linked_task_payloads_for_employee(obj, user)

    @extend_schema_field(EmployeeDepartmentRelationSerializer(allow_null=True))
    def get_department_relation(self, obj):
        is_member = getattr(obj, "_is_dept_member", None)
        is_head = getattr(obj, "_is_dept_head", None)
        has_role = getattr(obj, "_has_role_assignment", None)

        if is_member is None:
            return None

        role_names = []
        request = self.context.get("request")
        dept_id = (
            getattr(request, "_department_filter_id", None) if request else None
        )

        if dept_id and has_role:
            from employees.models import RoleAssignment

            assignments = RoleAssignment.objects.filter(
                employee=obj,
                role__department_id=dept_id,
                is_active=True,
            ).select_related("role")
            role_names = [a.role.name for a in assignments]

        return {
            "is_member": bool(is_member),
            "is_head": bool(is_head),
            "has_role_only": bool(has_role) and not bool(is_member),
            "role_names": role_names,
        }

    @extend_schema_field(EmployeeDepartmentSerializer(many=True))
    def get_departments(self, obj):
        links = getattr(obj, "dept_links", None)
        if links is None:
            links = EmployeeDepartment.objects.select_related(
                "department", "role"
            ).filter(employee=obj, is_active=True)
        out = []
        for link in links:
            dept = link.department
            out.append(
                {
                    "id": link.department_id,
                    "name": dept.name if link.department_id else None,
                    "role_id": link.role_id,
                    "role_name": link.role.name if link.role_id else None,
                    "is_head": (dept.head_id == obj.id),
                }
            )
        return out

    @extend_schema_field(serializers.CharField())
    def get_full_name(self, obj):
        fn = (obj.first_name or "").strip()
        ln = (obj.last_name or "").strip()
        pt = (obj.patronymic or "").strip()
        return f"{ln} {fn} {pt}".strip()

    @extend_schema_field(serializers.CharField())
    def get_display_name(self, obj: Employee) -> str:
        parts = [
            obj.last_name or "",
            obj.first_name or "",
            obj.patronymic or "",
        ]
        fio = " ".join(p.strip() for p in parts if p).strip()
        if fio:
            return fio
        if getattr(obj, "email", None):
            return obj.email
        if getattr(obj, "phone_number", None):
            return obj.phone_number
        return f"Сотрудник #{obj.id}"


class ProfilePatchSerializer(serializers.Serializer):
    """Сериализатор частичного обновления профиля."""

    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)

    _phone_field = DETECTED_PHONE_FIELD or "phone_number"
    locals()[_phone_field] = serializers.CharField(
        required=False, allow_blank=True
    )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if not attrs:
            raise serializers.ValidationError("No fields to update")
        return attrs
