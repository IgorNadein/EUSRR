# api/auth/views.py
from drf_spectacular.utils import (
    OpenApiExample,
    OpenApiResponse,
    extend_schema,
)
from rest_framework_simplejwt.views import TokenObtainPairView
from rest_framework_simplejwt.views import TokenRefreshView

from .serializers import (
    PhoneOrEmailTokenObtainPairSerializer,
    TokenPairResponseSerializer,
    TokenRefreshRequestSerializer,
    TokenRefreshResponseSerializer,
)


@extend_schema(
    tags=["Auth"],
    summary="Получить JWT access и refresh токены",
    description=(
        "Принимает email или телефон вместе с паролем. "
        "Если передан телефон, backend найдёт пользователя "
        "и использует его email "
        "для стандартной JWT-аутентификации."
    ),
    request=PhoneOrEmailTokenObtainPairSerializer,
    responses={
        200: TokenPairResponseSerializer,
        401: OpenApiResponse(
            description=(
                "Неверные учетные данные или email пользователя "
                "не подтвержден."
            ),
        ),
    },
    examples=[
        OpenApiExample(
            "Вход по email",
            value={"email": "user@example.com", "password": "Str0ngPass!"},
            request_only=True,
        ),
        OpenApiExample(
            "Вход по телефону",
            value={"phone_number": "+79990000001", "password": "Str0ngPass!"},
            request_only=True,
        ),
    ],
)
class PhoneOrEmailTokenObtainPairView(TokenObtainPairView):
    serializer_class = PhoneOrEmailTokenObtainPairSerializer


@extend_schema(
    tags=["Auth"],
    summary="Обновить JWT access token",
    description="Принимает refresh token и возвращает новый access token.",
    request=TokenRefreshRequestSerializer,
    responses={
        200: TokenRefreshResponseSerializer,
        401: OpenApiResponse(
            description="Refresh token недействителен или истек."
        ),
    },
)
class JWTTokenRefreshView(TokenRefreshView):
    pass
