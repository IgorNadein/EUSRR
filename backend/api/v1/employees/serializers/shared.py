"""Общие (shared) сериализаторы: Skill, Position, EmployeeAction."""

from drf_spectacular.utils import extend_schema_field
from django.contrib.auth.models import Group
from employees.constants import ACTION_CHOICES
from employees.models import EmployeeAction, Position, Skill
from rest_framework import serializers


class GroupVerboseSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    name = serializers.CharField()


class EmployeeActionHistorySerializer(serializers.Serializer):
    history_id = serializers.IntegerField()
    history_type = serializers.CharField()
    history_type_display = serializers.CharField(allow_null=True)
    history_date = serializers.DateTimeField()
    history_date_display = serializers.CharField()
    history_user = serializers.CharField(allow_null=True)
    action = serializers.CharField(allow_null=True)
    action_display = serializers.CharField(allow_null=True)
    changes = serializers.DictField()


class SkillSerializer(serializers.ModelSerializer):
    class Meta:
        model = Skill
        fields = ["id", "name"]


class PositionBriefSerializer(serializers.ModelSerializer):
    class Meta:
        model = Position
        fields = ("id", "name")


class PositionSerializer(serializers.ModelSerializer):
    groups = serializers.PrimaryKeyRelatedField(
        queryset=Group.objects.all(), many=True, required=False
    )
    groups_verbose = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = Position
        fields = ["id", "name", "description", "groups", "groups_verbose"]

    @extend_schema_field(GroupVerboseSerializer(many=True))
    def get_groups_verbose(self, obj):
        return [{"id": g.id, "name": g.name} for g in obj.groups.all()]


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
            "history",
        ]

    @extend_schema_field(serializers.CharField())
    def get_action_display(self, obj):
        return obj.get_action_display()

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_date_display(self, obj):
        return obj.date.strftime("%d.%m.%Y %H:%M") if obj.date else None

    @extend_schema_field(EmployeeActionHistorySerializer(many=True))
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
                    "history_date_display": cur.history_date.strftime(
                        "%d.%m.%Y %H:%M"
                    ),
                    "history_user": getattr(cur.history_user, "email", None),
                    "action": getattr(cur, "action", None),
                    "action_display": action_labels.get(getattr(cur, "action", None)),
                    "changes": changes,
                }
            )
        return out
