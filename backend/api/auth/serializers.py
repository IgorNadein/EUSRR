from __future__ import annotations

from api.v1.employees.views._helpers import PHONE_FIELD
from django.contrib.auth import get_user_model
from employees.models import Employee
from employees.utils import _normalize_phone
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import (
    TokenObtainPairSerializer,
    TokenRefreshSerializer,
)

from .models import UserAuthSession
from .services import (
    SESSION_ID_CLAIM,
    create_auth_session,
    hash_refresh_token,
    validate_refresh_session,
)

User = get_user_model()


class TokenPairResponseSerializer(serializers.Serializer):
    refresh = serializers.CharField(read_only=True)
    access = serializers.CharField(read_only=True)


class TokenRefreshRequestSerializer(serializers.Serializer):
    refresh = serializers.CharField(
        help_text="Refresh token, полученный при логине."
    )


class TokenRefreshResponseSerializer(serializers.Serializer):
    access = serializers.CharField(read_only=True)


class SessionSerializer(serializers.ModelSerializer):
    session_id = serializers.UUIDField(read_only=True)
    is_current = serializers.SerializerMethodField()

    class Meta:
        model = UserAuthSession
        fields = (
            "session_id",
            "is_current",
            "device_name",
            "ip_address",
            "created_at",
            "last_seen_at",
            "revoked_at",
        )

    def get_is_current(self, obj: UserAuthSession) -> bool:
        current_session_id = self.context.get("current_session_id")
        return str(obj.session_id) == str(current_session_id)


class SessionBulkActionResponseSerializer(serializers.Serializer):
    revoked = serializers.IntegerField(read_only=True)


class PhoneOrEmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Принимает email ИЛИ phone/phone_number + password.
    Если пришёл телефон — ищем пользователя и подставляем его email.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # <- КЛЮЧЕВОЕ: email (username_field) не обязателен
        self.fields[self.username_field].required = False
        self.fields[self.username_field].help_text = (
            "Email пользователя. Можно передать либо email, либо телефон."
        )
        # добавляем телефонные поля
        self.fields["phone"] = serializers.CharField(
            required=False,
            allow_blank=True,
            help_text="Номер телефона пользователя в произвольном формате.",
        )
        self.fields["phone_number"] = serializers.CharField(
            required=False,
            allow_blank=True,
            help_text="Альтернативное имя поля для номера телефона.",
        )

    def validate(self, attrs):
        raw_phone = (
            self.initial_data.get("phone")
            or self.initial_data.get("phone_number")
        )
        if raw_phone and not attrs.get(self.username_field):
            qfield = PHONE_FIELD or "phone_number"
            norm = _normalize_phone(raw_phone) or str(raw_phone).strip()
            try:
                user = Employee.objects.get(**{qfield: norm})
                # подставляем email в стандартный механизм SimpleJWT
                attrs[self.username_field] = user.email
            except Employee.DoesNotExist:
                pass  # базовая валидация ниже вернёт 401

        # Проверяем что есть email (после подстановки из телефона или напрямую)
        if not attrs.get(self.username_field):
            raise AuthenticationFailed(
                "Email or phone number required",
                code="no_credentials",
            )

        super().validate(attrs)

        # не выдаём токены, если email не подтверждён/аккаунт не активен
        if not self.user.email_verified or not self.user.is_active:
            raise AuthenticationFailed(
                "email_not_verified",
                code="email_not_verified",
            )

        request = self.context.get("request")
        if request is None:
            raise AuthenticationFailed("request_context_missing")

        session = create_auth_session(user=self.user, request=request)
        refresh = self.get_token(self.user)
        refresh[SESSION_ID_CLAIM] = str(session.session_id)
        access = refresh.access_token
        access[SESSION_ID_CLAIM] = str(session.session_id)

        session.refresh_token_hash = hash_refresh_token(str(refresh))
        session.save(update_fields=["refresh_token_hash"])

        return {
            "refresh": str(refresh),
            "access": str(access),
        }


class SessionTokenRefreshSerializer(TokenRefreshSerializer):
    def validate(self, attrs):
        raw_refresh = attrs["refresh"]
        refresh = self.token_class(raw_refresh)
        session = validate_refresh_session(
            refresh,
            raw_refresh=raw_refresh,
            request=self.context.get("request"),
        )

        access = refresh.access_token
        access[SESSION_ID_CLAIM] = str(session.session_id)

        return {"access": str(access)}
