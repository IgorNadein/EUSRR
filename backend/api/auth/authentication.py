from __future__ import annotations

from rest_framework_simplejwt.authentication import JWTAuthentication

from .services import validate_access_session


class SessionAwareJWTAuthentication(JWTAuthentication):
    def validate_session(self, validated_token, user, *, request=None):
        return validate_access_session(
            validated_token,
            user=user,
            request=request,
        )

    def authenticate(self, request):
        result = super().authenticate(request)
        if result is None:
            return None

        user, validated_token = result
        self.validate_session(validated_token, user, request=request)
        return user, validated_token
