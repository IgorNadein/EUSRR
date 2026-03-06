# api/auth/serializers.py
from api.v1.employees.views._helpers import PHONE_FIELD
from employees.utils import _normalize_phone
from django.contrib.auth import get_user_model
from employees.models import Employee
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

User = get_user_model()


class PhoneOrEmailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """
    Принимает email ИЛИ phone/phone_number + password.
    Если пришёл телефон — ищем пользователя и подставляем его email.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # <- КЛЮЧЕВОЕ: email (username_field) не обязателен
        self.fields[self.username_field].required = False
        # добавляем телефонные поля
        self.fields["phone"] = serializers.CharField(required=False, allow_blank=True)
        self.fields["phone_number"] = serializers.CharField(required=False, allow_blank=True)

    def validate(self, attrs):
        raw_phone = self.initial_data.get("phone") or self.initial_data.get("phone_number")
        if raw_phone and not attrs.get(self.username_field):
            qfield = PHONE_FIELD or "phone_number"
            norm = _normalize_phone(raw_phone) or str(raw_phone).strip()
            try:
                user = Employee.objects.get(**{qfield: norm})
                # подставляем email в стандартный механизм SimpleJWT
                attrs[self.username_field] = user.email
            except Employee.DoesNotExist:
                pass  # базовая валидация ниже вернёт 401

        data = super().validate(attrs)

        # не выдаём токены, если email не подтверждён/аккаунт не активен
        if not self.user.email_verified or not self.user.is_active:
            raise AuthenticationFailed("email_not_verified", code="email_not_verified")

        return data
