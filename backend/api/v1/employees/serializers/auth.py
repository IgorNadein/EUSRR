"""Сериализаторы для аутентификации и регистрации."""

import re
from typing import Any, Dict

from employees.models import Position
from employees.utils import _normalize_phone
from rest_framework import serializers

from api.v1.serializers import Base64ImageField


class EmailSerializer(serializers.Serializer):
    email = serializers.EmailField()


class EmailVerifySerializer(serializers.Serializer):
    email = serializers.EmailField()
    code = serializers.CharField(max_length=6)


class RegisterSerializer(serializers.Serializer):
    """Сериализатор регистрации.

    Проверяет контакты, нормализует телефон до E.164 и ограничивает допустимые
    значения некоторых полей.
    """

    first_name = serializers.CharField(max_length=150)
    last_name = serializers.CharField(max_length=150)
    phone_number = serializers.CharField(
        max_length=100, required=False, allow_blank=True
    )
    phone = serializers.CharField(
        max_length=100, required=False, allow_blank=True, write_only=True
    )

    email = serializers.EmailField()
    password = serializers.CharField(min_length=6)
    birth_date = serializers.DateField()

    telegram = serializers.CharField(required=False, allow_blank=True, default="")
    whatsapp = serializers.CharField(required=False, allow_blank=True, default="")
    wechat = serializers.CharField(required=False, allow_blank=True, default="")

    avatar = Base64ImageField(required=True)
    patronymic = serializers.CharField(required=False, allow_blank=True, default="")

    gender = serializers.IntegerField(
        required=True,
        min_value=1,
        max_value=2,
        error_messages={
            'required': 'Поле "Пол" обязательно для заполнения.',
            'invalid': 'Укажите пол: 1 - Мужской, 2 - Женский.',
            'min_value': 'Укажите пол: 1 - Мужской, 2 - Женский.',
            'max_value': 'Укажите пол: 1 - Мужской, 2 - Женский.',
        }
    )

    position = serializers.IntegerField(required=False, allow_null=True)
    skills = serializers.ListField(child=serializers.IntegerField(), required=False)

    def validate_first_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Имя обязательно для заполнения.")
        if re.search(r'\d', value):
            raise serializers.ValidationError("Имя не должно содержать цифры.")
        if not re.match(r'^[\w\s\-\']+$', value, re.UNICODE):
            raise serializers.ValidationError(
                "Имя может содержать только буквы, пробелы, дефисы и апострофы."
            )
        return value

    def validate_last_name(self, value: str) -> str:
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Фамилия обязательна для заполнения.")
        if re.search(r'\d', value):
            raise serializers.ValidationError("Фамилия не должна содержать цифры.")
        if not re.match(r'^[\w\s\-\']+$', value, re.UNICODE):
            raise serializers.ValidationError(
                "Фамилия может содержать только буквы, пробелы, дефисы и апострофы."
            )
        return value

    def validate_patronymic(self, value: str) -> str:
        value = value.strip()
        if not value:
            return value
        if re.search(r'\d', value):
            raise serializers.ValidationError("Отчество не должно содержать цифры.")
        if not re.match(r'^[\w\s\-\']+$', value, re.UNICODE):
            raise serializers.ValidationError(
                "Отчество может содержать только буквы, пробелы, дефисы и апострофы."
            )
        return value

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        if not attrs.get("phone_number") and attrs.get("phone"):
            attrs["phone_number"] = attrs["phone"]

        norm = _normalize_phone(attrs.get("phone_number"))
        if not norm:
            raise serializers.ValidationError(
                {"phone_number": "Неверный номер телефона (требуется формат E.164)."}
            )
        attrs["phone_number"] = norm

        pos_id = attrs.get("position")
        if pos_id is not None:
            if not Position.objects.filter(pk=pos_id).exists():
                raise serializers.ValidationError(
                    {"position": "Указанная должность не найдена."}
                )

        return attrs
