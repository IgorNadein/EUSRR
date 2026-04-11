# eusrr_backend/channels_jwt.py
from __future__ import annotations

from typing import Optional
from urllib.parse import parse_qs

from channels.db import database_sync_to_async
from channels.middleware import BaseMiddleware
from django.contrib.auth.models import AnonymousUser


class JWTAuthMiddleware(BaseMiddleware):
    """Auth для Channels по JWT.

    Поддерживает query ?token=... и header Authorization: Bearer ...
    """

    def _get_raw_token(self, scope) -> Optional[str]:
        # 1) query string
        qs = parse_qs(scope.get("query_string", b"").decode())
        if "token" in qs and qs["token"]:
            return qs["token"][0]
        # 2) header
        for name, value in scope.get("headers", []):
            if name == b"authorization" and value.lower().startswith(
                b"bearer "
            ):
                return value.split()[1].decode()
        return None

    @database_sync_to_async
    def _authenticate_raw_token(self, raw_token: str):
        from api.auth.authentication import SessionAwareJWTAuthentication

        auth = SessionAwareJWTAuthentication()
        validated_token = auth.get_validated_token(raw_token)
        user = auth.get_user(validated_token)
        auth.validate_session(validated_token, user)
        return user, validated_token

    async def __call__(self, scope, receive, send):
        scope.setdefault("user", AnonymousUser())
        try:
            raw = self._get_raw_token(scope)
            if raw:
                user, token = await self._authenticate_raw_token(raw)
                scope["user"] = user
                scope["auth"] = token
        except Exception:
            # оставим scope["user"] анонимным — соединение сам consumer решит
            pass
        return await super().__call__(scope, receive, send)
