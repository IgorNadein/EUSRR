from __future__ import annotations

from typing import Any, Mapping

from django.contrib.auth import get_user_model
from requests_app.enums import RequestStatus, RequestType
from requests_app.models import Request, RequestComment
from rest_framework import serializers

from ..employees.serializers import EmployeeBriefSerializer
from .validators import (RequestApproverNotEmployeeValidator,
                         RequestDatesByTypeValidator)

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
    """Сериализатор записи заявки.

    Обычным пользователям запрещено передавать `employee`, `status`, `approver` —
    они будут проигнорированы. Админы/обладатели прав могут их указывать.

    Поле `employee` умышленно НЕ делаем read_only, чтобы админ мог его задать.
    Для обычных пользователей оно подставится автоматически в `create()`/`perform_create()`.

    Raises:
        serializers.ValidationError: При некорректных данных (кроме запрещённых полей у обычных пользователей — они вычищаются).
    """

    # Важно: снять обязательность, чтобы отсутствие полей не роняло валидацию
    employee = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )
    status = serializers.ChoiceField(
        choices=RequestStatus, required=False, allow_null=True
    )
    approver = serializers.PrimaryKeyRelatedField(
        queryset=User.objects.all(), required=False, allow_null=True
    )

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
        )
        read_only_fields = ("id",)
        validators = [
            RequestDatesByTypeValidator(),
            RequestApproverNotEmployeeValidator(),
        ]

    def _is_power(self) -> bool:
        """Определяет, имеет ли пользователь расширенные права на создание/изменение.

        Returns:
            bool: True для staff или имеющих модельные права; иначе False.
        """
        user = self.context["request"].user
        return bool(
            getattr(user, "is_staff", False)
            or user.has_perm("requests_app.add_request")
            or user.has_perm("requests_app.change_request")
            or user.has_perm("requests_app.can_process_requests")
        )

    def to_internal_value(self, data: Mapping[str, Any]) -> dict[str, Any]:
        """Предвалидационная очистка входа.

        Для обычного пользователя удаляет `employee`, `status`, `approver` до полевой валидации,
        чтобы не получить 400 из-за, например, несуществующего PK в `employee`.

        Args:
            data (Mapping[str, Any]): Входные данные запроса.

        Returns:
            dict[str, Any]: Преобразованные данные для дальнейшей валидации.
        """
        if not self._is_power():
            # data может быть QueryDict — сделаем копию как обычный dict
            data = dict(data)
            data.pop("employee", None)
            data.pop("status", None)
            data.pop("approver", None)
        return super().to_internal_value(data)

    def create(self, validated_data: dict[str, Any]) -> Request:
        """Создание заявки.

        Обычным пользователям проставляет текущего пользователя; статус берётся из default модели.

        Args:
            validated_data (dict[str, Any]): Провалидированные данные.

        Returns:
            Request: Созданная заявка.

        Raises:
            serializers.ValidationError: Если не удалось определить автора.
        """
        request = self.context.get("request")
        user = getattr(request, "user", None)

        if not user or getattr(user, "is_anonymous", False):
            raise serializers.ValidationError(
                {"detail": "Требуется аутентификация для создания заявки."}
            )

        if not self._is_power():
            # обычный пользователь: запрещённые поля убираем/переписываем
            validated_data.pop("status", None)
            validated_data.pop("approver", None)
            validated_data["employee"] = user
        else:
            # staff/менеджер: если employee не указан — ставим текущего
            validated_data.setdefault("employee", user)

        if not validated_data.get("employee"):
            raise serializers.ValidationError(
                {"employee": "Автор должен быть установлен сервером."}
            )

        return super().create(validated_data)


class RequestCommentSerializer(serializers.ModelSerializer):
    """Сериализатор комментариев к заявке."""

    author = EmployeeBriefSerializer(read_only=True)

    class Meta:
        model = RequestComment
        fields = ("id", "request", "author", "text", "created_at")
        read_only_fields = ("id", "author", "created_at", "request")
