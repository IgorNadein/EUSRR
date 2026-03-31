# backend/api/v1/schedule/serializers.py
"""
Serializers для django-scheduler.
Чистые, проверенные временем модели.
"""

from drf_spectacular.utils import extend_schema_field
from rest_framework import serializers
from schedule.models import (
    Calendar,
    Event,
    Rule,
    Occurrence,
    EventRelation,
    CalendarRelation,
)
from django.contrib.contenttypes.models import ContentType


class RelatedUserSummarySerializer(serializers.Serializer):
    id = serializers.IntegerField()
    username = serializers.CharField()
    first_name = serializers.CharField(required=False, allow_blank=True)
    last_name = serializers.CharField(required=False, allow_blank=True)
    full_name = serializers.CharField(required=False)
    role = serializers.CharField(required=False)


class EventRuleDataSerializer(serializers.Serializer):
    frequency = serializers.CharField()
    params = serializers.DictField()
    description = serializers.CharField(allow_blank=True, allow_null=True)


class CalendarRelationSerializer(serializers.ModelSerializer):
    """Сериализатор для CalendarRelation (участники календаря)."""

    user_id = serializers.IntegerField(write_only=True, required=False)
    user = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = CalendarRelation
        fields = [
            "id",
            "calendar",
            "user_id",
            "user",
            "distinction",
            "inheritable",
        ]
        read_only_fields = ["id"]

    @extend_schema_field(RelatedUserSummarySerializer(allow_null=True))
    def get_user(self, obj):
        """Информация о связанном пользователе."""
        if obj.content_object:
            return {
                "id": obj.content_object.id,
                "username": getattr(
                    obj.content_object, "username", str(obj.content_object)
                ),
                "first_name": getattr(obj.content_object, "first_name", ""),
                "last_name": getattr(obj.content_object, "last_name", ""),
            }
        return None

    def create(self, validated_data):
        """Создать связь календаря с пользователем."""
        from django.contrib.auth import get_user_model

        User = get_user_model()

        user_id = validated_data.pop("user_id")
        calendar = validated_data["calendar"]
        distinction = validated_data.get("distinction", "viewer")
        inheritable = validated_data.get("inheritable", True)

        user = User.objects.get(id=user_id)

        # Используем встроенный метод create_relation
        calendar.create_relation(
            user, distinction=distinction, inheritable=inheritable
        )

        # Возвращаем созданную relation
        ct = ContentType.objects.get_for_model(User)
        return CalendarRelation.objects.get(
            calendar=calendar,
            content_type=ct,
            object_id=user_id,
            distinction=distinction,
        )


class CalendarSerializer(serializers.ModelSerializer):
    """Сериализатор для Calendar (django-scheduler) с совместимостью EUSRR."""

    # Совместимость с EUSRR API - принимаем title, конвертируем в name
    title = serializers.CharField(source="name", required=False)
    events_count = serializers.SerializerMethodField()
    owner = serializers.SerializerMethodField()
    participants = serializers.SerializerMethodField()
    user_role = serializers.SerializerMethodField()

    class Meta:
        model = Calendar
        fields = [
            "id",
            "name",
            "title",
            "slug",
            "events_count",
            "owner",
            "participants",
            "user_role",
        ]
        read_only_fields = ["id", "owner", "participants", "user_role"]
        extra_kwargs = {
            # Сделаем auto-generated если не указан
            "slug": {"required": False},
        }

    @extend_schema_field(serializers.IntegerField())
    def get_events_count(self, obj):
        """Количество событий в календаре."""
        return obj.event_set.count()

    @extend_schema_field(RelatedUserSummarySerializer(allow_null=True))
    def get_owner(self, obj):
        """Получить владельца календаря."""
        try:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            ct = ContentType.objects.get_for_model(User)

            owner_relation = CalendarRelation.objects.filter(
                calendar=obj, content_type=ct, distinction="owner"
            ).first()

            if owner_relation and owner_relation.content_object:
                return {
                    "id": owner_relation.content_object.id,
                    "username": getattr(
                        owner_relation.content_object,
                        "username",
                        str(owner_relation.content_object),
                    ),
                    "full_name": str(owner_relation.content_object),
                }
        except Exception:
            pass
        return None

    @extend_schema_field(RelatedUserSummarySerializer(many=True))
    def get_participants(self, obj):
        """Список всех участников календаря."""
        from django.contrib.auth import get_user_model

        User = get_user_model()
        ct = ContentType.objects.get_for_model(User)

        relations = CalendarRelation.objects.filter(
            calendar=obj, content_type=ct
        ).select_related("content_type")

        participants = []
        for rel in relations:
            if rel.content_object:
                participants.append(
                    {
                        "id": rel.content_object.id,
                        "username": getattr(
                            rel.content_object,
                            "username",
                            str(rel.content_object),
                        ),
                        "full_name": str(rel.content_object),
                        "role": rel.distinction,
                    }
                )
        return participants

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_user_role(self, obj):
        """Роль текущего пользователя для этого календаря."""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return None

        from django.contrib.auth import get_user_model

        User = get_user_model()
        ct = ContentType.objects.get_for_model(User)

        relation = CalendarRelation.objects.filter(
            calendar=obj, content_type=ct, object_id=request.user.id
        ).first()

        return relation.distinction if relation else None

    def create(self, validated_data):
        """Создать календарь с автогенерацией slug из name/title."""
        from django.utils.text import slugify

        # Если slug не указан - генерируем из name
        if "slug" not in validated_data or not validated_data.get("slug"):
            name = validated_data.get("name", "calendar")
            base_slug = slugify(name)
            if not base_slug:
                base_slug = "calendar"

            # Проверяем уникальность slug
            slug = base_slug
            counter = 1
            while Calendar.objects.filter(slug=slug).exists():
                slug = f"{base_slug}-{counter}"
                counter += 1

            validated_data["slug"] = slug

        return super().create(validated_data)


class RuleSerializer(serializers.ModelSerializer):
    """
    Сериализатор для Rule (rrule RFC 5545).

    Преобразует параметры между форматами:
    - Frontend: dict {"byweekday": [0, 4], "interval": 1}
    - django-scheduler: string "byweekday:0,4;interval:1"
    """

    VALID_FREQUENCIES = [
        "YEARLY",
        "MONTHLY",
        "WEEKLY",
        "DAILY",
        "HOURLY",
        "MINUTELY",
        "SECONDLY",
    ]

    frequency_display = serializers.CharField(
        source="get_frequency_display", read_only=True
    )

    class Meta:
        model = Rule
        fields = [
            "id",
            "name",
            "description",
            "frequency",
            "frequency_display",
            "params",
        ]
        read_only_fields = ["id", "frequency_display"]

    def _dict_to_params_string(self, params_dict):
        """
        Преобразует dict в строковый формат django-scheduler.

        Args:
            params_dict: {"byweekday": [0, 3], "interval": 1}

        Returns:
            "byweekday:0,3;interval:1"
        """
        if not params_dict or not isinstance(params_dict, dict):
            return ""

        parts = []
        for key, value in params_dict.items():
            if isinstance(value, (list, tuple)):
                value_str = ",".join(str(v) for v in value)
            else:
                value_str = str(value)
            parts.append(f"{key}:{value_str}")

        return ";".join(parts)

    def _params_string_to_dict(self, params_str):
        """
        Преобразует строку django-scheduler в dict.

        Args:
            params_str: "byweekday:0,3;interval:1"

        Returns:
            {"byweekday": [0, 3], "interval": 1}
        """
        if not params_str:
            return {}

        result = {}
        for param_pair in params_str.split(";"):
            if ":" not in param_pair:
                continue

            key, value_str = param_pair.split(":", 1)
            key = key.strip()

            # Если значение содержит запятые - это список
            if "," in value_str:
                try:
                    result[key] = [int(v.strip()) for v in value_str.split(",")]
                except ValueError:
                    result[key] = [v.strip() for v in value_str.split(",")]
            else:
                # Пробуем преобразовать в число
                try:
                    result[key] = int(value_str.strip())
                except ValueError:
                    result[key] = value_str.strip()

        return result

    def _parse_params_input(self, params):
        """
        Парсит params из любого формата в dict.

        Поддерживает:
        - dict (прямо от JSON)
        - JSON-string (от некоторых клиентов)
        - django-scheduler string (для обратной совместимости)

        Args:
            params: dict, JSON-string или django-scheduler string

        Returns:
            dict с параметрами
        """
        import json

        # Уже dict - возвращаем как есть
        if isinstance(params, dict):
            return params

        # Пробуем распарсить как JSON-строку
        if isinstance(params, str):
            # Если начинается с { - это JSON
            if params.strip().startswith("{"):
                try:
                    return json.loads(params)
                except (json.JSONDecodeError, TypeError):
                    pass

            # Иначе пробуем как django-scheduler формат
            return self._params_string_to_dict(params)

        return {}

    def to_representation(self, instance):
        """Преобразует params из БД в dict для frontend.

        Исходный формат — django-scheduler format.
        """
        data = super().to_representation(instance)
        data["params"] = self._params_string_to_dict(data.get("params", ""))
        return data

    def to_internal_value(self, data):
        """Преобразует params от frontend в формат для БД.

        Поддерживаются dict/JSON, на выходе — django-scheduler format.
        """
        # Парсим params в dict из любого формата
        params_dict = self._parse_params_input(data.get("params"))

        # Вызываем родительский метод для валидации остальных полей
        validated_data = super().to_internal_value(data)

        # Конвертируем dict в формат django-scheduler для сохранения в БД
        validated_data["params"] = self._dict_to_params_string(params_dict)

        return validated_data

    def validate_frequency(self, value):
        """Валидация поля frequency."""
        if value not in self.VALID_FREQUENCIES:
            raise serializers.ValidationError(
                f"Invalid frequency. Must be one of: {
                    ', '.join(self.VALID_FREQUENCIES)
                }"
            )
        return value


class EventSerializer(serializers.ModelSerializer):
    """Сериализатор для Event (django-scheduler)."""

    calendar_name = serializers.CharField(
        source="calendar.name", read_only=True
    )
    rule_description = serializers.CharField(
        source="rule.description", read_only=True, allow_null=True
    )
    rule_data = serializers.SerializerMethodField()

    class Meta:
        model = Event
        fields = [
            "id",
            "title",
            "description",
            "start",
            "end",
            "calendar",
            "calendar_name",
            "rule",
            "rule_description",
            "rule_data",
            "end_recurring_period",
            "color_event",
            "creator",
            "created_on",
            "updated_on",
        ]
        read_only_fields = ["id", "created_on", "updated_on"]

    @extend_schema_field(EventRuleDataSerializer(allow_null=True))
    def get_rule_data(self, obj):
        """Возвращает детальную информацию о правиле повторения."""
        if not obj.rule:
            return None

        rule = obj.rule
        params = rule.get_params()

        return {
            "frequency": rule.frequency,
            "params": params,
            "description": rule.description,
        }

    def validate(self, attrs):
        """Валидация start/end."""
        start = attrs.get("start")
        end = attrs.get("end")

        if end and start and end < start:
            raise serializers.ValidationError(
                {"end": "Дата окончания не может быть раньше даты начала."}
            )

        return attrs


class EventListSerializer(EventSerializer):
    """Упрощённый сериализатор для списка событий."""

    class Meta(EventSerializer.Meta):
        fields = [
            "id",
            "title",
            "description",
            "start",
            "end",
            "calendar",
            "calendar_name",
            "color_event",
            "rule",
            "end_recurring_period",
        ]


class OccurrenceSerializer(serializers.ModelSerializer):
    """Сериализатор для Occurrence (материализованные вхождения)."""

    event_title = serializers.CharField(source="event.title", read_only=True)
    event_id = serializers.IntegerField(source="event.id", read_only=True)

    class Meta:
        model = Occurrence
        fields = [
            "id",
            "event",
            "event_id",
            "event_title",
            "title",
            "description",
            "start",
            "end",
            "cancelled",
            "original_start",
            "original_end",
            "created_on",
            "updated_on",
        ]
        read_only_fields = ["id", "created_on", "updated_on"]


class EventRelationSerializer(serializers.ModelSerializer):
    """Сериализатор для EventRelation (участники встреч)."""

    event_title = serializers.CharField(source="event.title", read_only=True)
    user_name = serializers.SerializerMethodField()
    content_type = serializers.PrimaryKeyRelatedField(
        queryset=ContentType.objects.all(),
        required=False,  # Делаем необязательным
    )

    class Meta:
        model = EventRelation
        fields = [
            "id",
            "event",
            "event_title",
            "content_type",
            "object_id",
            "distinction",
            "user_name",
        ]
        read_only_fields = ["id"]

    @extend_schema_field(serializers.CharField(allow_null=True))
    def get_user_name(self, obj):
        """Имя связанного объекта."""
        if obj.content_object:
            return str(obj.content_object)
        return None

    def create(self, validated_data):
        """Автоматически устанавливает content_type для User."""
        if "content_type" not in validated_data:
            from django.contrib.auth import get_user_model

            User = get_user_model()
            validated_data["content_type"] = ContentType.objects.get_for_model(
                User
            )
        return super().create(validated_data)
