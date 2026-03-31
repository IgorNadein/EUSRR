from __future__ import annotations

from typing import Any, Mapping

from drf_spectacular.utils import extend_schema_field
from django.contrib.auth import get_user_model
from django.db import models
from employees.models import Department
from requests_app.enums import RequestStatus
from requests_app.models import Request
from rest_framework import serializers

from ..employees.serializers import EmployeeBriefSerializer
from .validators import (
    RequestApproverNotEmployeeValidator,
    RequestDatesByTypeValidator,
)

User = get_user_model()


class RecipientIDsField(serializers.ListField):
    """
    Принимает recipient_ids в форматах:
    - repeat params: ?recipient_ids=1&recipient_ids=2
    - JSON string: {"recipient_ids": "[1,2,3]"}
    - CSV: {"recipient_ids": "1,2,3"}
    - JSON list: {"recipient_ids": [1,2,3]}
    """

    child = serializers.IntegerField(min_value=1)

    def to_internal_value(self, data):
        """Нормализует различные форматы в list[int]."""
        if not data:
            return []

        # Если уже список
        if isinstance(data, (list, tuple)):
            return super().to_internal_value(data)

        # Если строка JSON
        if isinstance(data, str):
            data = data.strip()
            # JSON массив
            if data.startswith("[") and data.endswith("]"):
                import json

                try:
                    parsed = json.loads(data)
                    if isinstance(parsed, list):
                        return super().to_internal_value(parsed)
                except (json.JSONDecodeError, ValueError):
                    pass
            # CSV
            if "," in data:
                parts = [p.strip() for p in data.split(",") if p.strip()]
                return super().to_internal_value(parts)
            # Одно число
            try:
                return super().to_internal_value([int(data)])
            except (ValueError, TypeError):
                pass

        # QueryDict.getlist() возвращает list - отдаём как есть
        return super().to_internal_value(data)


class RequestReadSerializer(serializers.ModelSerializer):
    """Сериализатор чтения заявки с получателями.

    Включает краткую информацию о сотрудниках и вычисляемые поля.
    """

    employee = EmployeeBriefSerializer(read_only=True)
    approver = EmployeeBriefSerializer(read_only=True)
    display_title = serializers.CharField(read_only=True)
    is_final = serializers.BooleanField(read_only=True)

    # URL для вложенного файла (аналогично file_url в DocumentReadSerializer)
    attachment_url = serializers.FileField(source="attachment", read_only=True)

    # Новые поля для получателей
    departments = serializers.PrimaryKeyRelatedField(many=True, read_only=True)
    recipients = EmployeeBriefSerializer(many=True, read_only=True)
    cc_users = EmployeeBriefSerializer(many=True, read_only=True)

    # Вычисляемые поля
    recipient_count = serializers.SerializerMethodField()
    cc_count = serializers.SerializerMethodField()
    is_recipient = serializers.SerializerMethodField()
    # Используем аннотированное поле из queryset
    comments_count = serializers.IntegerField(read_only=True, allow_null=True)

    class Meta:
        model = Request
        fields = (
            "id",
            "employee",
            "approver",
            "department",  # Старое поле для обратной совместимости
            "departments",  # Новое поле
            "type",
            "title",
            "date_from",
            "date_to",
            "comment",
            "status",
            "attachment",
            "attachment_url",  # Полный URL к файлу
            "created_at",
            "updated_at",
            "decided_at",
            "display_title",
            "is_final",
            # Новые поля
            "recipients",
            "cc_users",
            "sent_to_all_department",
            "recipient_count",
            "cc_count",
            "is_recipient",
            "comments_count",
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
            "attachment_url",
            "recipients",
            "cc_users",
            "recipient_count",
            "cc_count",
            "is_recipient",
            "comments_count",
        )

    @extend_schema_field(serializers.IntegerField())
    def get_recipient_count(self, obj):
        """Количество получателей"""
        if obj.sent_to_all_department:
            # Считаем всех сотрудников выбранных отделов
            count = (
                obj.departments.aggregate(
                    total=models.Count(
                        "employeedepartment",
                        filter=models.Q(employeedepartment__is_active=True),
                        distinct=True,
                    )
                )["total"]
                or 0
            )
            return count
        return obj.recipients.count()

    @extend_schema_field(serializers.IntegerField())
    def get_cc_count(self, obj):
        """Количество пользователей в копии"""
        return obj.cc_users.count()

    @extend_schema_field(serializers.BooleanField())
    def get_is_recipient(self, obj):
        """Является ли текущий пользователь получателем"""
        request = self.context.get("request")
        if not request or not hasattr(request, "user"):
            return False
        user = request.user
        if not user or not user.is_authenticated:
            return False
        return obj.is_recipient(user)


class RequestWriteSerializer(serializers.ModelSerializer):
    """Сериализатор записи заявки.

    Обычным пользователям запрещено передавать
    `employee`, `status`, `approver` —
    они будут проигнорированы. Админы/обладатели прав могут их указывать.

    Поле `employee` умышленно НЕ делаем read_only, чтобы админ мог его задать.
    Для обычных пользователей оно подставится автоматически в
    `create()`/`perform_create()`.

    Raises:
        serializers.ValidationError: При некорректных данных.
        Запрещённые поля у обычных пользователей просто вычищаются.
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

    # Новые поля для получателей
    department_ids = serializers.PrimaryKeyRelatedField(
        many=True,
        queryset=Department.objects.all(),
        source="departments",
        required=False,
        allow_empty=True,
    )
    recipient_ids = RecipientIDsField(required=False, allow_empty=True)
    cc_user_ids = RecipientIDsField(required=False, allow_empty=True)
    sent_to_all_department = serializers.BooleanField(
        required=False, default=False
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Импортируем здесь, чтобы избежать circular import
        from employees.models import Department

        self.fields["department_ids"].queryset = Department.objects.all()

    class Meta:
        model = Request
        fields = (
            "id",
            "employee",
            "approver",
            "department",  # Старое поле для обратной совместимости
            "department_ids",  # Новое поле
            "type",
            "title",
            "date_from",
            "date_to",
            "comment",
            "status",
            "attachment",
            # Новые поля
            "recipient_ids",
            "cc_user_ids",
            "sent_to_all_department",
        )
        read_only_fields = ("id",)
        validators = [
            RequestDatesByTypeValidator(),
            RequestApproverNotEmployeeValidator(),
        ]

    def _is_power(self) -> bool:
        """Определяет, имеет ли пользователь расширенные права.

        На создание и изменение.

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

        Для обычного пользователя удаляет `employee`, `status`, `approver`
        до полевой валидации, чтобы не получить 400 из-за, например,
        несуществующего PK в `employee`.

        Args:
            data (Mapping[str, Any]): Входные данные запроса.

        Returns:
            dict[str, Any]: Преобразованные данные для дальнейшей валидации.
        """
        if not self._is_power():
            # ВАЖНО: data может быть QueryDict из DRF
            # dict(QueryDict) превращает все значения в списки!
            # Используем _mutable для безопасного удаления полей
            if hasattr(data, "_mutable"):
                # Это QueryDict, делаем его mutable
                data._mutable = True
                data.pop("employee", None)
                data.pop("status", None)
                data.pop("approver", None)
                data._mutable = False
            else:
                # Обычный dict
                data = dict(data)
                data.pop("employee", None)
                data.pop("status", None)
                data.pop("approver", None)

        return super().to_internal_value(data)

    def validate(self, attrs):
        """Валидация получателей и отделов"""
        sent_to_all = attrs.get(
            "sent_to_all_department",
            getattr(self.instance, "sent_to_all_department", False),
        )

        recipient_ids = attrs.get("recipient_ids")
        if recipient_ids is None:
            if self.instance is not None:
                recipient_ids = list(
                    self.instance.recipients.values_list("id", flat=True)
                )
            else:
                recipient_ids = []

        departments = attrs.get("departments")
        if departments is None:
            if self.instance is not None:
                departments = list(self.instance.departments.all())
            else:
                departments = []

        # Если sent_to_all_department=True, должны быть указаны отделы
        if sent_to_all and not departments:
            raise serializers.ValidationError(
                {"department_ids": ("Укажите отделы для массовой рассылки")}
            )

        # Если sent_to_all_department=False и нет отделов,
        # должны быть получатели
        if not sent_to_all and not departments and not recipient_ids:
            raise serializers.ValidationError(
                {
                    "recipient_ids": "Укажите получателей или отделы"
                }
            )

        # Автор не может быть в получателях
        request = self.context.get("request")
        if request and hasattr(request, "user") and request.user:
            employee_id = attrs.get("employee", request.user).id
            if employee_id in recipient_ids:
                raise serializers.ValidationError(
                    {"recipient_ids": "Автор не может быть получателем"}
                )

        return attrs

    def _set_recipients(self, request_obj, recipient_ids, is_cc=False):
        """Устанавливает получателей (фильтрует только активных)"""
        if not recipient_ids:
            if is_cc:
                request_obj.cc_users.clear()
            else:
                request_obj.recipients.clear()
            return

        users = User.objects.filter(id__in=recipient_ids, is_active=True)

        if is_cc:
            request_obj.cc_users.set(users)
        else:
            request_obj.recipients.set(users)

    def create(self, validated_data: dict[str, Any]) -> Request:
        """Создание заявки.

        Обычным пользователям проставляет текущего пользователя;
        статус берётся из default модели.

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

        # Извлекаем данные получателей до создания
        recipient_ids = validated_data.pop("recipient_ids", [])
        cc_user_ids = validated_data.pop("cc_user_ids", [])
        departments = validated_data.pop("departments", [])

        # Отладка: проверяем что передается
        print(
            "📝 [SERIALIZER] create: "
            f"recipient_ids={recipient_ids}, "
            f"cc_user_ids={cc_user_ids}"
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

        # Создаем заявку
        request_obj = super().create(validated_data)
        print(
            f"✅ [SERIALIZER] Заявление #{request_obj.id} создано, "
            "устанавливаем recipients..."
        )

        # Устанавливаем связи ManyToMany
        if departments:
            request_obj.departments.set(departments)

        self._set_recipients(request_obj, recipient_ids, is_cc=False)
        self._set_recipients(request_obj, cc_user_ids, is_cc=True)

        # Проверяем что сохранилось
        recipients_count = request_obj.recipients.count()
        cc_count = request_obj.cc_users.count()
        print(
            "✅ [SERIALIZER] Recipients установлены: "
            f"{recipients_count} основных, {cc_count} в копии"
        )

        return request_obj

    def update(self, instance, validated_data: dict[str, Any]) -> Request:
        """Обновление заявки с получателями"""
        # Извлекаем данные получателей
        recipient_ids = validated_data.pop("recipient_ids", None)
        cc_user_ids = validated_data.pop("cc_user_ids", None)
        departments = validated_data.pop("departments", None)

        # Обновляем основные поля
        instance = super().update(instance, validated_data)

        # Обновляем связи только если переданы
        if departments is not None:
            instance.departments.set(departments)

        if recipient_ids is not None:
            self._set_recipients(instance, recipient_ids, is_cc=False)

        if cc_user_ids is not None:
            self._set_recipients(instance, cc_user_ids, is_cc=True)

        return instance
