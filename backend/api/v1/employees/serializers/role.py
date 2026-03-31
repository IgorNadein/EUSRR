"""Сериализаторы для ролей и групп."""

from drf_spectacular.utils import extend_schema_field
from django.contrib.auth.models import Group, Permission
from employees.models import DepartmentPermission, DepartmentRole
from rest_framework import serializers


class DepartmentPermissionVerboseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    code = serializers.CharField()
    name = serializers.CharField()


class GroupPermissionVerboseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    codename = serializers.CharField()
    name = serializers.CharField()
    app = serializers.CharField()
    model = serializers.CharField()


class DepartmentRoleSerializer(serializers.ModelSerializer):
    scoped_permissions = serializers.PrimaryKeyRelatedField(
        queryset=DepartmentPermission.objects.all(), many=True, required=False
    )
    scoped_permission_codes = serializers.ListField(
        child=serializers.CharField(), required=False, write_only=True
    )

    permissions = serializers.SerializerMethodField(read_only=True)
    permissions_verbose = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = DepartmentRole
        fields = (
            "id",
            "department",
            "name",
            "scoped_permissions",
            "scoped_permission_codes",
            "permissions",
            "permissions_verbose",
        )
        read_only_fields = ("id",)

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

    @extend_schema_field(serializers.ListField(child=serializers.IntegerField()))
    def get_permissions(self, obj: DepartmentRole):
        return list(obj.scoped_permissions.values_list("id", flat=True))

    @extend_schema_field(DepartmentPermissionVerboseSerializer(many=True))
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

    @extend_schema_field(GroupPermissionVerboseSerializer(many=True))
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
