from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from rest_framework import serializers

from communications import comments_helpers
from api.v1.serializers import Base64ImageField
from api.v1.documents.serializers import DocumentReadSerializer, FolderBriefSerializer
from api.v1.employees.serializers import EmployeeBriefSerializer
from documents.models import Document
from guests.constants import GuestVisitStatus
from guests.models import Guest, GuestVisit, GuestVisitEvent
from guests.permissions import (
    can_decide_guest_visit,
    can_manage_guest_account,
    is_guest_admin,
)
from guests.services import (
    GUEST_VISIT_PERIOD_BLOCKING_STATUSES,
    GuestVisitWorkflow,
    has_unread_info_response_for_user,
    normalize_all_day_range,
    validate_guest_visit_period_available,
    validate_guest_visit_period_not_past,
)

User = get_user_model()


class GuestBriefSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    avatar = Base64ImageField(read_only=True)
    visits_count = serializers.SerializerMethodField()

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
            "avatar",
            "visits_count",
            "is_active",
            "is_blacklisted",
        )

    def get_visits_count(self, obj):
        annotated_count = getattr(obj, "visits_count", None)
        if annotated_count is not None:
            return annotated_count
        return obj.visits.count()


class GuestSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)
    created_by = EmployeeBriefSerializer(read_only=True)
    avatar = Base64ImageField(required=False, allow_null=True)
    document_folder = FolderBriefSerializer(read_only=True)
    documents = DocumentReadSerializer(many=True, read_only=True)
    comments_count = serializers.SerializerMethodField()
    visits_count = serializers.SerializerMethodField()

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
            "avatar",
            "organization",
            "position",
            "comments_count",
            "visits_count",
            "document_folder",
            "documents",
            "created_by",
            "is_active",
            "is_blacklisted",
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
            "comments_count",
            "visits_count",
            "document_folder",
            "documents",
            "created_by",
            "is_active",
            "is_blacklisted",
            "ldap_username",
            "ldap_upn",
            "ldap_last_synced_at",
            "ldap_last_error",
            "created_at",
            "updated_at",
        )

    def get_comments_count(self, obj):
        annotated_count = getattr(obj, "comments_count", None)
        if annotated_count is not None:
            return annotated_count
        return comments_helpers.get_comment_count(obj)

    def get_visits_count(self, obj):
        annotated_count = getattr(obj, "visits_count", None)
        if annotated_count is not None:
            return annotated_count
        return obj.visits.count()


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
    can_approve = serializers.SerializerMethodField()
    can_reject = serializers.SerializerMethodField()
    can_request_info = serializers.SerializerMethodField()
    can_cancel = serializers.SerializerMethodField()
    can_revoke = serializers.SerializerMethodField()
    can_return_to_work = serializers.SerializerMethodField()
    can_sync_ldap = serializers.SerializerMethodField()
    can_delete = serializers.SerializerMethodField()
    comments_count = serializers.IntegerField(read_only=True, default=0)
    has_unread_info_response = serializers.SerializerMethodField()

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
            "can_approve",
            "can_reject",
            "can_request_info",
            "can_cancel",
            "can_revoke",
            "can_return_to_work",
            "can_sync_ldap",
            "can_delete",
            "comments_count",
            "has_unread_info_response",
            "events",
        )

    def _user(self):
        request = self.context.get("request")
        return getattr(request, "user", None)

    @staticmethod
    def _inviter_is_active(obj):
        return bool(
            obj.inviter.is_active
            and getattr(obj.inviter, "is_actually_active", True)
        )

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

    def get_can_approve(self, obj):
        return bool(
            can_decide_guest_visit(self._user())
            and obj.status in {GuestVisitStatus.PENDING, GuestVisitStatus.REJECTED}
            and not obj.inviter_inactive
            and self._inviter_is_active(obj)
        )

    def get_can_reject(self, obj):
        return bool(
            can_decide_guest_visit(self._user())
            and obj.status
            in {
                GuestVisitStatus.PENDING,
                GuestVisitStatus.NEEDS_INFO,
                GuestVisitStatus.APPROVED,
            }
        )

    def get_can_request_info(self, obj):
        return bool(can_decide_guest_visit(self._user()) and obj.status == GuestVisitStatus.PENDING)

    def get_can_cancel(self, obj):
        user = self._user()
        return bool(
            user
            and (is_guest_admin(user) or obj.inviter_id == user.id)
            and obj.status
            in {
                GuestVisitStatus.DRAFT,
                GuestVisitStatus.PENDING,
                GuestVisitStatus.NEEDS_INFO,
                GuestVisitStatus.APPROVED,
            }
        )

    def get_can_revoke(self, obj):
        return bool(
            can_decide_guest_visit(self._user())
            and obj.status == GuestVisitStatus.APPROVED
        )

    def get_can_return_to_work(self, obj):
        user = self._user()
        return bool(
            user
            and (is_guest_admin(user) or obj.inviter_id == user.id)
            and obj.status
            in {
                GuestVisitStatus.CANCELLED,
                GuestVisitStatus.REVOKED,
                GuestVisitStatus.EXPIRED,
            }
            and not obj.inviter_inactive
            and self._inviter_is_active(obj)
        )

    def get_can_sync_ldap(self, obj):
        return can_manage_guest_account(self._user())

    def get_can_delete(self, obj):
        user = self._user()
        return bool(user and (is_guest_admin(user) or obj.inviter_id == user.id))

    def get_has_unread_info_response(self, obj):
        return has_unread_info_response_for_user(obj, self._user())


class GuestVisitWriteSerializer(serializers.Serializer):
    guest_id = serializers.IntegerField(required=False)
    guest = GuestSerializer(required=False)
    guest_comment = serializers.CharField(required=False, allow_blank=True)
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

        try:
            validate_guest_visit_period_not_past(
                expires_at=expires_at,
                unlimited=unlimited,
            )
        except ValueError as exc:
            raise serializers.ValidationError(
                {"access_expires_at": str(exc)}
            ) from exc

        if not instance and not attrs.get("guest_id") and not attrs.get("guest"):
            raise serializers.ValidationError({"guest": "Укажите гостя."})
        if not instance:
            if not (attrs.get("purpose") or "").strip():
                raise serializers.ValidationError({"purpose": "Укажите цель приглашения."})
            if not unlimited and not (starts_at and expires_at):
                raise serializers.ValidationError(
                    {"access_starts_at": "Укажите период доступа или бессрочный доступ."}
                )
            if getattr(settings, "GUESTS_REQUIRE_ID_DOCUMENT", False) and not attrs.get("document_ids"):
                raise serializers.ValidationError(
                    {"document_ids": "Прикрепите документ гостя."}
                )
        elif instance.status in GUEST_VISIT_PERIOD_BLOCKING_STATUSES:
            try:
                validate_guest_visit_period_available(
                    guest=instance.guest,
                    starts_at=starts_at,
                    expires_at=expires_at,
                    unlimited=unlimited,
                    exclude_pk=instance.pk,
                )
            except ValueError as exc:
                raise serializers.ValidationError(
                    {"access_starts_at": str(exc)}
                ) from exc

        return attrs

    def _get_or_create_guest(self, attrs):
        guest_id = attrs.pop("guest_id", None)
        guest_data = attrs.pop("guest", None)
        if guest_id:
            try:
                return Guest.objects.get(pk=guest_id)
            except Guest.DoesNotExist as exc:
                raise serializers.ValidationError(
                    {"guest_id": "Гость не найден."}
                ) from exc
        request = self.context["request"]
        serializer = GuestSerializer(data=guest_data)
        serializer.is_valid(raise_exception=True)
        return serializer.save(created_by=request.user)

    def create(self, validated_data):
        document_ids = validated_data.pop("document_ids", [])
        guest_comment = (validated_data.pop("guest_comment", "") or "").strip()
        guest = self._get_or_create_guest(validated_data)
        try:
            validate_guest_visit_period_available(
                guest=guest,
                starts_at=validated_data.get("access_starts_at"),
                expires_at=validated_data.get("access_expires_at"),
                unlimited=bool(validated_data.get("unlimited", False)),
            )
            visit = GuestVisitWorkflow.create_visit(
                actor=self.context["request"].user,
                guest=guest,
                **validated_data,
            )
        except ValueError as exc:
            raise serializers.ValidationError(
                {"access_starts_at": str(exc)}
            ) from exc
        if document_ids:
            documents = Document.objects.filter(id__in=document_ids)
            visit.documents.set(documents)
            guest.documents.add(*documents)
        if guest_comment:
            comments_helpers.create_comment(
                guest,
                self.context["request"].user,
                guest_comment,
            )
        return visit

    def update(self, instance, validated_data):
        document_ids = validated_data.pop("document_ids", None)
        validated_data.pop("guest_comment", None)
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
            documents = Document.objects.filter(id__in=document_ids)
            instance.documents.set(documents)
            instance.guest.documents.add(*documents)
        return instance


class GuestSearchSerializer(GuestBriefSerializer):
    pass
