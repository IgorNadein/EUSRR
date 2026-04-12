"""Обратно-совместимый реэкспорт auth views из canonical api.auth."""

from api.auth.views import (
    AnonymousAPIView,
    RegisterAPIView,
    ResendEmailAPIView,
    VerifyEmailAPIView,
)

__all__ = [
    "AnonymousAPIView",
    "RegisterAPIView",
    "ResendEmailAPIView",
    "VerifyEmailAPIView",
]
