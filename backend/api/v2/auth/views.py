"""Authentication views for API v2."""
from api.v1.employees.views import (
    RegisterAPIView as V1RegisterAPIView,
    ResendEmailAPIView as V1ResendEmailAPIView,
    VerifyEmailAPIView as V1VerifyEmailAPIView,
)


class RegisterAPIView(V1RegisterAPIView):
    """API v2 для регистрации пользователей."""
    pass


class ResendEmailAPIView(V1ResendEmailAPIView):
    """API v2 для повторной отправки email подтверждения."""
    pass


class VerifyEmailAPIView(V1VerifyEmailAPIView):
    """API v2 для подтверждения email."""
    pass
