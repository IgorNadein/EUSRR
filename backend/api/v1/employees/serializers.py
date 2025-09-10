from collections import defaultdict
from typing import Any, Dict, Optional

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from employees.constants import ACTION_CHOICES
from employees.models import (
    Department,
    DepartmentPermission,
    DepartmentRole,
    EmployeeAction,
    EmployeeDepartment,
    Position,
    Skill,
)
from rest_framework import serializers

from ..serializers import Base64ImageField
from .utils import _normalize_phone

Employee = get_user_model()


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class EmailVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)


class RegisterSerializer(serializers.Serializer):
    """Сериализатор регистрации.

    Проверяет контакты, нормализует телефон до E.164 и ограничивает допустимые
    значения некоторых полей.

    Raises:
        serializers.ValidationError: При нарушении правил валидации.
    """

    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone_number = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    # alias, если прислали "phone": положим в phone_number
    phone = serializers.CharField(
        max_length=100, required=False, allow_blank=True, write_only=True
    )

    email = serializers.EmailField()
    password = serializers.CharField(min_length=6)
    birth_date = serializers.DateField()

    telegram = serializers.CharField(required=False, allow_blank=True, default="")
    whatsapp = serializers.CharField(required=False, allow_blank=True, default="")
    wechat = serializers.CharField(required=False, allow_blank=True, default="")

    avatar = Base64ImageField(required=False, allow_null=True)
    patronymic = serializers.CharField(required=False, allow_blank=True, default="")

    gender = serializers.ChoiceField(
        required=False,
        allow_null=True,
        choices=((0, "Не указан"), (1, "Мужской"), (2, "Женский")),
    )

    position = serializers.IntegerField(required=False, allow_null=True)
    skills = serializers.ListField(child=serializers.IntegerField(), required=False)

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Глобальная валидация: контакты + телефон (alias) + нормализация E.164.

        Args:
            attrs: Входные атрибуты.

        Returns:
            Отвалидированные атрибуты.

        Raises:
            serializers.ValidationError: Если нет контактов или телефон невалиден.
        """
        # контакты: нужен хотя бы один
        if not (
            (attrs.get("telegram") or "").strip()
            or (attrs.get("whatsapp") or "").strip()
            or (attrs.get("wechat") or "").strip()
        ):
            raise serializers.ValidationError(
                {
                    "non_field_errors": [
                        "Заполните хотя бы одно из полей: WhatsApp, WeChat или Telegram"
                    ]
                }
            )

        # alias "phone" → phone_number (если не задан)
        if not attrs.get("phone_number") and attrs.get("phone"):
            attrs["phone_number"] = attrs["phone"]

        # нормализация телефона
        norm = _normalize_phone(attrs.get("phone_number"))
        if not norm:
            raise serializers.ValidationError(
                {"phone_number": "Неверный номер телефона (требуется формат E.164)."}
            )
        attrs["phone_number"] = norm

        # (опционально) проверим, что position существует — чтобы не молча проигнорировать
        pos_id = attrs.get("position")
        if pos_id is not None:
            exists = Position.objects.filter(pk=pos_id).exists()
            if not exists:
                raise serializers.ValidationError(
                    {"position": "Указанная должность не найдена."}
                )

        return attrs


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ["id", "name"]


class PositionBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ("id", "name")


class EmployeeActionSerializer(serializers.ModelSerializer):
    action_display = serializers.SerializerMethodField()
    date_display = serializers.SerializerMethodField()
    history = serializers.SerializerMethodField()

    class Meta:
        model = EmployeeAction
        fields = [
            "id",
            "employee",
            "action",
            "action_display",
            "date",
            "date_display",
            "comment",
            "extra",
            "history",  # ← добавили
        ]

    def get_action_display(self, obj):
        return obj.get_action_display()

    def get_date_display(self, obj):
        return obj.date.strftime("%d.%m.%Y %H:%M") if obj.date else None

    def get_history(self, obj):
        if not self.context.get("include_action_history", False):
            return []

        items = list(
            obj.history.select_related("history_user").order_by(
                "-history_date", "-history_id"
            )
        )

        action_labels = dict(ACTION_CHOICES)
        history_type_labels = {"+": "Создано", "~": "Изменено", "-": "Удалено"}
        diff_fields = ["action", "comment", "extra"]

        out = []
        for i, cur in enumerate(items):
            prev = items[i + 1] if i + 1 < len(items) else None
            changes = {}

            for name in diff_fields:
                new = getattr(cur, name, None)
                old = getattr(prev, name, None) if prev else None

                if name == "date":
                    new_fmt = new.isoformat() if new else None
                    old_fmt = old.isoformat() if old else None
                    if new_fmt != old_fmt:
                        changes[name] = {"old": old_fmt, "new": new_fmt}
                elif name == "action":
                    if old != new:
                        changes[name] = {
                            "old": old,
                            "old_display": action_labels.get(old),
                            "new": new,
                            "new_display": action_labels.get(new),
                        }
                else:
                    if old != new:
                        changes[name] = {"old": old, "new": new}

            out.append(
                {
                    "history_id": cur.history_id,
                    "history_type": cur.history_type,
                    "history_type_display": history_type_labels.get(cur.history_type),
                    "history_date": cur.history_date.isoformat(),
                    "history_date_display": cur.history_date.strftime("%d.%m.%Y %H:%M"),
                    "history_user": getattr(cur.history_user, "email", None),
                    # текущее значение действия в этом снимке + «человеческий» перевод
                    "action": getattr(cur, "action", None),
                    "action_display": action_labels.get(getattr(cur, "action", None)),
                    "changes": changes,
                }
            )
        return out


class EmployeeSerializer(serializers.ModelSerializer):
    """Полная версия сотрудника для собственных эндпоинтов /employees/."""

    avatar = Base64ImageField(required=False, allow_null=True)
    actions = EmployeeActionSerializer(many=True, read_only=True)

    # навыки: читаем красиво, пишем ids
    skills = SkillSerializer(many=True, read_only=True)
    skills_ids = serializers.PrimaryKeyRelatedField(
        queryset=Skill.objects.all(), many=True, write_only=True, required=False
    )

    # должность: читаем объектом, пишем через position_id
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
            # чтобы точно не принимали/не отдавали пароль и коды
            "password": {"write_only": True, "required": False},
        }

    def to_representation(self, instance):
        data = super().to_representation(instance)
        return data

    def update(self, instance, validated_data):
        skills = validated_data.pop("skills_ids", None)
        instance = super().update(instance, validated_data)
        if skills is not None:
            instance.skills.set(skills)
        return instance

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

    def get_fields(self):
        fields = super().get_fields()

        # actions — как и было
        if self.context.get("include_actions") is not True:
            view = self.context.get("view")
            action = getattr(view, "action", None) if view else None
            if action not in {"retrieve", "me"}:
                fields.pop("actions", None)

        # ⬇️ Новое: auth показываем только в /me или при include_auth=True
        include_auth = self.context.get("include_auth") is True
        view = self.context.get("view")
        action = getattr(view, "action", None) if view else None
        if not include_auth and action != "me":
            fields.pop("auth", None)

        return fields

    def get_auth(self, obj):
        """
        Возвращает только ГЛОБАЛЬНЫЕ права текущего (request.user),
        уже с учётом должности (PositionRoleBackend).
        """
        req = self.context.get("request")
        if not req or not getattr(req.user, "is_authenticated", False):
            return None

        # Не светим auth другого сотрудника (кроме явного include_auth=True)
        include_auth = self.context.get("include_auth") is True
        if not include_auth and req.user.pk != getattr(obj, "pk", None):
            return None

        u = req.user
        perms = sorted(u.get_all_permissions())  # уже включает Position-права

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
    avatar = Base64ImageField(read_only=True)

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
            "avatar",
        )

    def get_display_name(self, obj) -> str:
        """
        Читабельное имя сотрудника: full name -> email -> phone -> 'Сотрудник #id'
        """
        parts = [obj.last_name or "", obj.first_name or "", obj.patronymic or ""]
        fio = " ".join(p.strip() for p in parts if p)
        if fio:
            return fio
        if getattr(obj, "email", None):
            return obj.email
        if getattr(obj, "phone_number", None):
            return obj.phone_number
        return f"Сотрудник #{obj.id}"


class DepartmentSerializer(serializers.ModelSerializer):
    head = EmployeeBriefSerializer(read_only=True)
    head_id = serializers.PrimaryKeyRelatedField(
        source="head",
        queryset=Employee.objects.all(),
        write_only=True,
        required=False,
        allow_null=True,
    )
    employees_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Department
        fields = (
            "id",
            "name",
            "description",
            "head",
            "head_id",
            "employees_count",
        )


class EmployeeListSerializer(serializers.ModelSerializer):
    """
    Списочное представление сотрудника в /employees/ (листинги, выборы и т.п.).
    Добавляет поле display_name по тем же правилам, что и в кратком сериализаторе.
    """

    display_name = serializers.SerializerMethodField()
    email = serializers.EmailField(read_only=True)
    phone_number = serializers.CharField(read_only=True)
    avatar = Base64ImageField(read_only=True)
    position = PositionBriefSerializer(read_only=True)
    departments = serializers.SerializerMethodField()
    full_name = serializers.SerializerMethodField()
    skills = SkillSerializer(many=True, read_only=True)

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
        )

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
                    "is_head": (dept.head_id == obj.id),  # ✅ правильная проверка
                }
            )
        return out

    def get_full_name(self, obj):
        fn = (obj.first_name or "").strip()
        ln = (obj.last_name or "").strip()
        pt = (obj.patronymic or "").strip()
        nm = f"{ln} {fn} {pt}".strip()
        return nm

    def get_display_name(self, obj: Employee) -> str:
        """См. логику в EmployeeBriefSerializer.get_display_name()."""
        parts = [obj.last_name or "", obj.first_name or "", obj.patronymic or ""]
        fio = " ".join(p.strip() for p in parts if p).strip()
        if fio:
            return fio
        if getattr(obj, "email", None):
            return obj.email
        if getattr(obj, "phone_number", None):
            return obj.phone_number
        return f"Сотрудник #{obj.id}"


class PositionSerializer(serializers.ModelSerializer):
    # для записи — массив id групп, для чтения — подробная инфа
    groups = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(), many=True, required=False
    )
    groups_verbose = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Position
        fields = ["id", "name", "description", "groups", "groups_verbose"]

    def get_groups_verbose(self, obj):
        return [{"id": g.id, "name": g.name} for g in obj.groups.all()]


class DepartmentRoleSerializer(serializers.ModelSerializer):
    # Новая схема: скоуп-права внутри отдела
    scoped_permissions = serializers.PrimaryKeyRelatedField(
        queryset=DepartmentPermission.objects.all(), many=True, required=False
    )
    scoped_permission_codes = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True
    )

    # Backward-compat поля (read-only), чтобы фронт/старые тесты не ломались
    permissions = serializers.SerializerMethodField(read_only=True)
    permissions_verbose = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DepartmentRole
        fields = (
            "id",
            "department",
            "name",
            # новые write-поля
            "scoped_permissions",
            "scoped_permission_codes",
            # совместимость (read-only зеркала)
            "permissions",
            "permissions_verbose",
        )
        read_only_fields = ("id",)

    # Поддержка записи codes вместо ids
    def _apply_codes_if_present(self, instance: DepartmentRole, validated_data: dict):
        codes = validated_data.pop("scoped_permission_codes", None)
        if codes is not None:
            qs = DepartmentPermission.objects.filter(code__in=codes)
            if qs.count() != len(set(codes)):
                raise serializers.ValidationError(
                    {"scoped_permission_codes": "Некоторые коды не существуют"}
                )
            instance.scoped_permissions.set(list(qs))

    def create(self, validated_data):
        # вытаскиваем write-only/внешние поля до super().create()
        codes = validated_data.pop("scoped_permission_codes", None)
        perms = validated_data.pop("scoped_permissions", None)

        role = super().create(validated_data)

        if perms is not None:
            role.scoped_permissions.set(perms)

        if codes is not None:
            qs = DepartmentPermission.objects.filter(code__in=codes)
            if qs.count() != len(set(codes)):
                raise serializers.ValidationError(
                    {"scoped_permission_codes": "Некоторые коды не существуют"}
                )
            role.scoped_permissions.set(list(qs))

        return role

    def update(self, instance, validated_data):
        # аналогично: вынимаем до super().update()
        codes = validated_data.pop("scoped_permission_codes", None)
        perms = validated_data.pop("scoped_permissions", None)

        role = super().update(instance, validated_data)

        if perms is not None:
            role.scoped_permissions.set(perms)

        if codes is not None:
            qs = DepartmentPermission.objects.filter(code__in=codes)
            if qs.count() != len(set(codes)):
                raise serializers.ValidationError(
                    {"scoped_permission_codes": "Некоторые коды не существуют"}
                )
            role.scoped_permissions.set(list(qs))

        return role

    # Backward-compat read
    def get_permissions(self, obj: DepartmentRole):
        return list(obj.scoped_permissions.values_list("id", flat=True))

    def get_permissions_verbose(self, obj: DepartmentRole):
        return [
            {"id": p.id, "code": p.code, "name": p.name}
            for p in obj.scoped_permissions.order_by("code").all()
        ]


class GroupSerializer(serializers.ModelSerializer):
    permissions = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.all(), many=True, required=False
    )
    permissions_verbose = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Group
        fields = ["id", "name", "permissions", "permissions_verbose"]

    def get_permissions_verbose(self, obj):
        qs = obj.permissions.select_related("content_type").all()
        return [
            {
                "id": p.id,
                "codename": f"{p.content_type.app_label}.{p.codename}",
                "name": p.name,
                "app": p.content_type.app_label,
                "model": p.content_type.model,
            }
            for p in qs
        ]


# --- payload-сериалайзеры для кастомных действий ---


class SetHeadInput(serializers.Serializer):
    head_id = serializers.IntegerField(
        allow_null=True, required=False
    )  # None -> снять руководителя


class SetMemberRoleInput(serializers.Serializer):
    # поддерживаем алиасы: employee / role
    employee_id = serializers.IntegerField(required=False)
    role_id = serializers.IntegerField(allow_null=True, required=False)
    employee = serializers.IntegerField(required=False)
    role = serializers.IntegerField(allow_null=True, required=False)
    is_active = serializers.BooleanField(required=False)  # 👈 новый флаг (опционально)

    def validate(self, attrs):
        emp = attrs.get("employee_id") or attrs.get("employee")
        role = attrs.get("role_id") if "role_id" in attrs else attrs.get("role")
        if emp is None:
            raise serializers.ValidationError(
                {"employee_id": "This field is required."}
            )
        attrs["employee_id"] = emp
        attrs["role_id"] = role  # может быть None (снять роль)
        # по умолчанию считаем активным, если поле не передали
        if "is_active" not in attrs:
            attrs["is_active"] = True
        return attrs


class AddMemberInput(serializers.Serializer):
    """
    Входные данные для добавления сотрудника в отдел.
    Роль НЕ назначается здесь (для этого есть set_member_role).
    """

    employee_id = serializers.IntegerField(required=False)
    employee = serializers.IntegerField(required=False)

    def validate(self, attrs):
        emp = (
            attrs.get("employee_id")
            if "employee_id" in attrs
            else attrs.get("employee")
        )
        if emp is None:
            raise serializers.ValidationError(
                {"employee_id": "This field is required."}
            )
        attrs["employee_id"] = emp
        return attrs


class RemoveMemberInput(serializers.Serializer):
    """
    Входные данные для удаления (деактивации) сотрудника из отдела.
    """

    employee_id = serializers.IntegerField(required=False)
    employee = serializers.IntegerField(required=False)

    def validate(self, attrs):
        emp = attrs.get("employee_id", attrs.get("employee"))
        if emp is None:
            raise serializers.ValidationError(
                {"employee_id": "This field is required."}
            )
        attrs["employee_id"] = emp
        return attrs


class DepartmentBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ("id", "name")
