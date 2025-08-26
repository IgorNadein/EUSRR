import base64
import binascii
from io import BytesIO

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group, Permission
from django.core.files.base import ContentFile
from django.utils import timezone
from PIL import Image
from rest_framework import serializers

from employees.models import (
    Department,
    DepartmentRole,
    EmployeeAction,
    EmployeeDepartment,
    Position,
    Skill,
)

Employee = get_user_model()


class Base64ImageField(serializers.ImageField):
    """
    Двухстороннее поле:
    - input: принимает строку base64 или data URI (data:image/...;base64,xxxx)
    - output: возвращает data URI (data:image/...;base64,xxxx)
    Совместимо с Python 3.13 (без imghdr).
    """

    default_ext = "jpg"

    def _detect_ext_mime(self, content: bytes) -> tuple[str, str]:
        """Определяем расширение и MIME через Pillow."""
        try:
            im = Image.open(BytesIO(content))
            fmt = (im.format or "").upper()
            ext_map = {
                "JPEG": "jpg",
                "JPG": "jpg",
                "PNG": "png",
                "WEBP": "webp",
                "GIF": "gif",
                "BMP": "bmp",
                "TIFF": "tiff",
                "ICO": "ico",
            }
            ext = ext_map.get(fmt, self.default_ext)
            mime = Image.MIME.get(fmt, "image/jpeg")
            return ext, mime
        except Exception:
            return self.default_ext, "image/jpeg"

    def to_internal_value(self, data):
        # Принимаем None/пустое
        if data in (None, "", b""):
            return super().to_internal_value(data)

        if isinstance(data, str):
            # Срезаем префикс data:image/...;base64, если есть
            if data.startswith("data:image"):
                try:
                    _, data = data.split(";base64,", 1)
                except ValueError:
                    raise serializers.ValidationError("Некорректный формат data URI.")
            try:
                decoded = base64.b64decode(data)
            except (TypeError, ValueError, binascii.Error):
                raise serializers.ValidationError("Невалидный base64.")

            ext, _ = self._detect_ext_mime(decoded)
            file = ContentFile(decoded, name=f"upload.{ext}")
            return super().to_internal_value(file)

        return super().to_internal_value(data)

    def to_representation(self, value):
        if not value:
            return ""
        # Получаем байты
        try:
            file_obj = getattr(value, "file", None) or value
            content = file_obj.read()
            if hasattr(file_obj, "seek"):
                file_obj.seek(0)
        except Exception:
            try:
                with open(value.path, "rb") as f:
                    content = f.read()
            except Exception:
                return ""

        b64 = base64.b64encode(content).decode("ascii")
        _, mime = self._detect_ext_mime(content)
        return f"data:{mime};base64,{b64}"


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class EmailVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=32)


class RegisterSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone_number = serializers.CharField(max_length=100)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=6)
    birth_date = serializers.DateField()

    telegram = serializers.CharField(required=False, allow_blank=True, default="")
    whatsapp = serializers.CharField(required=False, allow_blank=True, default="")
    wechat = serializers.CharField(required=False, allow_blank=True, default="")

    # Доп. поля модели можно тоже принять, но они опциональны:
    avatar = Base64ImageField(required=False, allow_null=True)
    patronymic = serializers.CharField(required=False, allow_blank=True, default="")
    gender = serializers.IntegerField(required=False, allow_null=True)
    position = serializers.IntegerField(required=False, allow_null=True)
    skills = serializers.ListField(child=serializers.IntegerField(), required=False)


class EmployeeSerializer(serializers.ModelSerializer):
    """Полная версия сотрудника для собственных эндпоинтов /employees/."""

    avatar = Base64ImageField(required=False, allow_null=True)

    class Meta:
        model = Employee
        # Явно укажем поля, чтобы не протекали чувствительные служебные
        fields = (
            "id",
            "email",
            "last_name",
            "first_name",
            "patronymic",
            "gender",
            "avatar",
            "phone_number",
            "birth_date",
            "position",
            "telegram",
            "whatsapp",
            "wechat",
            "skills",
            # служебные только read-only:
            "is_active",
            "email_verified",
            "created_at",
            "updated_at",
            "last_login",
            "date_joined",
        )
        read_only_fields = (
            "is_active",
            "email_verified",
            "created_at",
            "updated_at",
            "last_login",
            "date_joined",
        )
        extra_kwargs = {
            # чтобы точно не принимали/не отдавали пароль и коды
            "password": {"write_only": True, "required": False},
        }

    # На всякий случай выкинем поля, которых нет в fields, но если вдруг DRF попытается их притащить (обычно не будет).
    def to_representation(self, instance):
        data = super().to_representation(instance)
        # Ничего лишнего тут нет, просто оставил хук, если захочешь добавить правку URL для avatar до абсолютного и т.п.
        return data


class DepartmentSerializer(serializers.ModelSerializer):
    head = EmployeeSerializer(read_only=True)
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
            "head_appointed_at",
            "created_at",
            "employees_count",
        )
        read_only_fields = ("head_appointed_at", "created_at")

    def validate_head_id(self, value: Employee | None):
        if value and not value.is_actually_active:
            raise serializers.ValidationError(
                "Назначать можно только реально активного сотрудника"
            )
        return value


class PositionBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ("id", "name")


class EmployeeListSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(read_only=True)
    phone_number = serializers.CharField(read_only=True)
    avatar = Base64ImageField(read_only=True)
    position = PositionBriefSerializer(read_only=True)
    departments = serializers.SerializerMethodField()

    class Meta:
        model = Employee
        fields = (
            "id",
            "email",
            "phone_number",
            "last_name",
            "first_name",
            "patronymic",
            "avatar",
            "position",
            "departments",
        )

    def get_departments(self, obj):
        links = getattr(obj, "dept_links", None)
        if links is None:
            links = EmployeeDepartment.objects.select_related(
                "department", "role"
            ).filter(employee=obj, is_active=True)
        out = []
        for link in links:
            out.append(
                {
                    "id": link.department_id,
                    "name": link.department.name if link.department_id else None,
                    "role_id": link.role_id,
                    "role_name": link.role.name if link.role_id else None,
                }
            )
        return out


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
    permissions = serializers.PrimaryKeyRelatedField(
        queryset=Permission.objects.all(), many=True, required=False
    )
    permissions_verbose = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DepartmentRole
        fields = ["id", "department", "name", "permissions", "permissions_verbose"]

    def get_permissions(self, obj):
        return list(obj.permissions.values_list("id", flat=True))

    def get_permissions_verbose(self, obj):
        return [
            {
                "id": p.id,
                "codename": f"{p.content_type.app_label}.{p.codename}",
                "name": p.name,
            }
            for p in obj.permissions.select_related("content_type").all()
        ]


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ["id", "name"]


class EmployeeActionSerializer(serializers.ModelSerializer):
    # по умолчанию ставим текущее время, если не передали
    date = serializers.DateTimeField(required=False)

    class Meta:
        model = EmployeeAction
        fields = ["id", "employee", "action", "date", "comment", "extra"]

    def validate(self, attrs):
        if "date" not in attrs:
            attrs["date"] = timezone.now()
        return attrs
