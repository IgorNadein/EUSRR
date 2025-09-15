from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from requests_app.models import Request, RequestComment
from rest_framework import serializers

from ..employees.serializers import EmployeeBriefSerializer

User = get_user_model()


class RequestReadSerializer(serializers.ModelSerializer):
    """Сериализатор чтения заявки.

    Включает краткую информацию о сотрудниках и вычисляемые поля.
    """

    employee = EmployeeBriefSerializer(read_only=True)
    approver = EmployeeBriefSerializer(read_only=True)
    display_title = serializers.CharField(read_only=True)
    is_final = serializers.BooleanField(read_only=True)

    class Meta:
        model = Request
        fields = (
            "id",
            "employee",
            "approver",
            "department",
            "type",
            "title",
            "date_from",
            "date_to",
            "comment",
            "status",
            "attachment",
            "created_at",
            "updated_at",
            "decided_at",
            "display_title",
            "is_final",
        )
        read_only_fields = (
            "employee",
            "approver",
            "status",
            "created_at",
            "updated_at",
            "decided_at",
            "display_title",
            "is_final",
        )


class RequestWriteSerializer(serializers.ModelSerializer):
    """Сериализатор записи заявки (создание/обновление).

    Принцип: обычным пользователям нельзя указывать/менять `employee`, `approver`,
    `status`, `decided_at`, `created_at`, `updated_at`. Эти поля управляются
    системой или через отдельные экшены (approve/reject/cancel).

    Raises:
        serializers.ValidationError: При попытке изменить запрещённые поля
            или при неверных данных (валидация модели сработает в `.save()`).
    """

    class Meta:
        model = Request
        fields = (
            "id",
            "employee",     # будет проигнорирован для обычных пользователей
            "approver",     # только для админов/обладателей прав
            "department",
            "type",
            "title",
            "date_from",
            "date_to",
            "comment",
            "status",       # будет проигнорирован (меняется экшенами)
            "attachment",
        )
        read_only_fields = ("id",)

    def validate(self, attrs: dict[str, Any]) -> dict[str, Any]:
        """Фильтрует запрещённые к записи поля для обычных пользователей.

        Returns:
            dict[str, Any]: Очищенные данные.
        """
        user: User = self.context["request"].user
        is_power = (
            user.is_staff
            or user.has_perm("requests_app.change_request")
            or user.has_perm("requests_app.can_process_requests")
        )

        # Обычным пользователям запрещаем управлять этими полями напрямую
        blocked = {"employee", "approver", "status"}
        if not is_power:
            for k in list(attrs.keys()):
                if k in blocked:
                    attrs.pop(k, None)

        # Если хотите жестко запретить менять status даже админам через write-эндпойнты,
        # раскомментируйте следующую строку:
        # attrs.pop("status", None)

        return attrs

    def create(self, validated_data: dict[str, Any]) -> Request:
        """Создаёт заявку.

        Обычным пользователям принудительно проставляется `employee=self.request.user`
        и статус по умолчанию (`STATUS_PENDING` из модели).

        Returns:
            Request: Созданная заявка.
        """
        user: User = self.context["request"].user
        is_power = user.is_staff or user.has_perm("requests_app.add_request")

        if not is_power:
            validated_data["employee"] = user
            # статус возьмётся из default модели (STATUS_PENDING)

        return super().create(validated_data)

    def update(self, instance: Request, validated_data: dict[str, Any]) -> Request:
        """Обновляет заявку.

        Обычным пользователям нельзя менять владельца/согласующего/статус.
        Дополнительно не даём редактировать финальные заявки.

        Raises:
            serializers.ValidationError: Если заявка в финальном статусе.
        """
        user: User = self.context["request"].user
        if getattr(instance, "is_final", False) and not (
            user.is_staff or user.has_perm("requests_app.change_request")
        ):
            raise serializers.ValidationError("Финальная заявка недоступна для правок.")

        # Поля employee/approver/status уже вычищены в validate() при необходимости
        return super().update(instance, validated_data)


class RequestCommentSerializer(serializers.ModelSerializer):
    """Сериализатор комментариев к заявке."""

    author = EmployeeBriefSerializer(read_only=True)

    class Meta:
        model = RequestComment
        fields = ("id", "request", "author", "text", "created_at")
        read_only_fields = ("id", "author", "created_at", "request")
