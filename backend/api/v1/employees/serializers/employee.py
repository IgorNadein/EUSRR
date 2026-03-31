"""Сериализаторы для сотрудников (Employee)."""

from collections import defaultdict
from typing import Any, Dict

from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import extend_schema_field
from django.contrib.auth import get_user_model
from employees.models import EmployeeDepartment, Position, Skill
from eusrr_backend.auth_backends import PHONE_FIELD as DETECTED_PHONE_FIELD
from rest_framework import serializers

from api.v1.serializers import Base64ImageField

from .shared import (
    EmployeeActionSerializer,
    PositionBriefSerializer,
    SkillSerializer,
)

Employee = get_user_model()


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


class EmployeeSerializer(serializers.ModelSerializer):
    """Полная версия сотрудника для /employees/."""

    avatar = Base64ImageField(required=False, allow_null=True)
    actions = EmployeeActionSerializer(many=True, read_only=True)

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

    class Meta:
        model = Employee
        fields = (
            "avatar",
            "actions",
            "id",
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
            "skills",
            "skills_ids",
            "is_active",
            "email_verified",
            "created_at",
            "updated_at",
            "last_login",
            "date_joined",
            "auth",
        )
        read_only_fields = (
            "is_active",
            "email_verified",
            "created_at",
            "updated_at",
            "last_login",
            "date_joined",
            "auth",
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

        return fields

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
        )

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
