from __future__ import annotations

from django.contrib.auth import get_user_model
from rest_framework import serializers

from api.v1.documents.serializers import DocumentReadSerializer
from api.v1.employees.serializers import EmployeeBriefSerializer
from documents.models import Document
from guests.constants import GuestVisitStatus
from guests.models import Guest, GuestVisit, GuestVisitEvent
from guests.permissions import (
    can_decide_guest_visit,
    can_manage_guest_account,
    is_guest_admin,
)
from guests.services import GuestVisitWorkflow, normalize_all_day_range

User = get_user_model()


class GuestBriefSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = Guest
        fields = (
            "id",
            "full_name",
            "last_name",
            "first_name",
            "patronymic",
            "organization",
            "email",
            "phone",
            "ldap_enabled",
            "is_active",
        )


class GuestSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    created_by = EmployeeBriefSerializer(read_only=True)

    class Meta:
        model = Guest
        fields = (
            "id",
            "full_name",
            "last_name",
            "first_name",
            "patronymic",
            "birth_date",
            "phone",
            "email",
            "organization",
            "position",
            "comment",
            "created_by",
            "is_active",
            "ldap_enabled",
            "ldap_username",
            "ldap_upn",
            "ldap_last_synced_at",
            "ldap_last_error",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "full_name",
            "created_by",
            "ldap_enabled",
            "ldap_username",
            "ldap_upn",
            "ldap_last_synced_at",
            "ldap_last_error",
            "created_at",
            "updated_at",
        )


class GuestVisitEventSerializer(serializers.ModelSerializer):
    actor = EmployeeBriefSerializer(read_only=True)

    class Meta:
        model = GuestVisitEvent
        fields = (
            "id",
            "event_type",
            "actor",
            "from_status",
            "to_status",
            "comment",
            "metadata",
            "created_at",
        )


class GuestVisitReadSerializer(serializers.ModelSerializer):
    guest = GuestBriefSerializer(read_only=True)
    inviter = EmployeeBriefSerializer(read_only=True)
    decided_by = EmployeeBriefSerializer(read_only=True)
    documents = DocumentReadSerializer(many=True, read_only=True)
    events = GuestVisitEventSerializer(many=True, read_only=True)
    status_display = serializers.CharField(source="get_status_display", read_only=True)
    is_active_now = serializers.BooleanField(read_only=True)
    is_expired = serializers.BooleanField(read_only=True)
    can_edit = serializers.SerializerMethodField()
    can_submit = serializers.SerializerMethodField()
    can_decide = serializers.SerializerMethodField()
    can_request_info = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    can_revoke = serializers.SerializerMethodField()
    can_sync_ldap = serializers.SerializerMethodField()
    comments_count = serializers.IntegerField(read_only=True, default=0)

    class Meta:
        model = GuestVisit
        fields = (
            "id",
            "guest",
            "inviter",
            "inviter_snapshot_name",
            "inviter_snapshot_email",
            "host_department",
            "purpose",
            "visit_comment",
            "admin_comment",
            "status",
            "status_display",
            "access_starts_at",
            "access_expires_at",
            "all_day",
            "unlimited",
            "documents",
            "submitted_at",
            "decided_by",
            "decided_at",
            "decision_comment",
            "cancelled_at",
            "cancel_reason",
            "revoked_at",
            "revoke_reason",
            "expired_at",
            "inviter_inactive",
            "created_at",
            "updated_at",
            "is_active_now",
            "is_expired",
            "can_edit",
            "can_submit",
            "can_decide",
            "can_request_info",
            "can_cancel",
            "can_revoke",
            "can_sync_ldap",
            "comments_count",
            "events",
        )

    def _user(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    def get_can_edit(self, obj):
        return obj.can_edit_by(self._user())

    def get_can_submit(self, obj):
        user = self._user()
        return bool(
            user
            and obj.inviter_id == user.id
            and obj.status in {GuestVisitStatus.DRAFT, GuestVisitStatus.NEEDS_INFO}
        )

    def get_can_decide(self, obj):
        return can_decide_guest_visit(self._user())

    def get_can_request_info(self, obj):
        return can_decide_guest_visit(self._user())

    def get_can_cancel(self, obj):
        user = self._user()
        return bool(user and (is_guest_admin(user) or obj.inviter_id == user.id))

    def get_can_revoke(self, obj):
        return can_decide_guest_visit(self._user())

    def get_can_sync_ldap(self, obj):
        return can_manage_guest_account(self._user())


class GuestVisitWriteSerializer(serializers.Serializer):
    guest_id = serializers.IntegerField(required=False)
    guest = GuestSerializer(required=False)
    purpose = serializers.CharField(required=False, allow_blank=True)
    visit_comment = serializers.CharField(required=False, allow_blank=True)
    all_day = serializers.BooleanField(required=False, default=True)
    unlimited = serializers.BooleanField(required=False, default=False)
    access_starts_at = serializers.DateTimeField(required=False, allow_null=True)
    access_expires_at = serializers.DateTimeField(required=False, allow_null=True)
    date_from = serializers.DateField(required=False)
    date_to = serializers.DateField(required=False)
    document_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        required=False,
        allow_empty=True,
    )

    def validate(self, attrs):
        instance = getattr(self, "instance", None)
        unlimited = attrs.get("unlimited", getattr(instance, "unlimited", False))
        all_day = attrs.get("all_day", getattr(instance, "all_day", True))

        if all_day and "date_from" in attrs and "date_to" in attrs:
            starts_at, expires_at = normalize_all_day_range(
                attrs.pop("date_from"),
                attrs.pop("date_to"),
            )
            attrs["access_starts_at"] = starts_at
            attrs["access_expires_at"] = expires_at

        starts_at = attrs.get("access_starts_at", getattr(instance, "access_starts_at", None))
        expires_at = attrs.get("access_expires_at", getattr(instance, "access_expires_at", None))

        if not unlimited:
            if starts_at and expires_at and starts_at >= expires_at:
                raise serializers.ValidationError(
                    {"access_expires_at": "Окончание должно быть позже начала."}
                )
        else:
            attrs["access_expires_at"] = None

        if not instance and not attrs.get("guest_id") and not attrs.get("guest"):
            raise serializers.ValidationError({"guest": "Укажите гостя."})

        return attrs

    def _get_or_create_guest(self, attrs):
        request = self.context["request"]
        guest_id = attrs.pop("guest_id", None)
        guest_data = attrs.pop("guest", None)
        if guest_id:
            try:
                return Guest.objects.get(pk=guest_id)
            except Guest.DoesNotExist as exc:
                raise serializers.ValidationError(
                    {"guest_id": "Гость не найден."}
                ) from exc
        serializer = GuestSerializer(data=guest_data)
        serializer.is_valid(raise_exception=True)
        return serializer.save(created_by=request.user)

    def create(self, validated_data):
        document_ids = validated_data.pop("document_ids", [])
        guest = self._get_or_create_guest(validated_data)
        visit = GuestVisitWorkflow.create_visit(
            actor=self.context["request"].user,
            guest=guest,
            **validated_data,
        )
        if document_ids:
            visit.documents.set(Document.objects.filter(id__in=document_ids))
        return visit

    def update(self, instance, validated_data):
        document_ids = validated_data.pop("document_ids", None)
        validated_data.pop("guest", None)
        validated_data.pop("guest_id", None)
        for field in (
            "purpose",
            "visit_comment",
            "all_day",
            "unlimited",
            "access_starts_at",
            "access_expires_at",
        ):
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        instance.save()
        if document_ids is not None:
            instance.documents.set(Document.objects.filter(id__in=document_ids))
        return instance


class GuestSearchSerializer(GuestBriefSerializer):
    pass
