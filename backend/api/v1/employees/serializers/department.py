"""Сериализаторы для отделов (Department)."""

from django.contrib.auth import get_user_model
from employees.models import Department
from rest_framework import serializers

from .employee import EmployeeBriefSerializer

Employee = get_user_model()


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


class DepartmentBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Department
        fields = ("id", "name")


class SetHeadInput(serializers.Serializer):
    head_id = serializers.IntegerField(allow_null=True, required=False)


class SetMemberRoleInput(serializers.Serializer):
    employee_id = serializers.IntegerField(required=False)
    role_id = serializers.IntegerField(allow_null=True, required=False)
    employee = serializers.IntegerField(required=False)
    role = serializers.IntegerField(allow_null=True, required=False)
    is_active = serializers.BooleanField(required=False)

    def validate(self, attrs):
        emp = attrs.get("employee_id") or attrs.get("employee")
        role = attrs.get("role_id") if "role_id" in attrs else attrs.get("role")
        if emp is None:
            raise serializers.ValidationError(
                {"employee_id": "This field is required."}
            )
        attrs["employee_id"] = emp
        attrs["role_id"] = role
        if "is_active" not in attrs:
            attrs["is_active"] = True
        return attrs


class AddMemberInput(serializers.Serializer):
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
