from __future__ import annotations

from datetime import timedelta
from typing import Any

from django.contrib.auth import get_user_model
from django.utils import timezone
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.settings import api_settings as jwt_api_settings

from .models import UserAuthSession

User = get_user_model()

SESSION_ID_CLAIM = "session_id"
LAST_SEEN_UPDATE_INTERVAL = timedelta(minutes=5)


def hash_refresh_token(raw_token: str) -> str:
    return salted_hmac("api.auth.refresh", raw_token).hexdigest()


def extract_client_ip(request) -> str:
    forwarded_for = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded_for:
        return forwarded_for.split(",")[0].strip()
    return (request.META.get("REMOTE_ADDR") or "").strip()


def extract_user_agent(request) -> str:
    return (request.META.get("HTTP_USER_AGENT") or "").strip()[:1024]


def build_device_name(user_agent: str) -> str:
    if not user_agent:
        return "Неизвестное устройство"

    lowered = user_agent.lower()

    browser = "Браузер"
    if "yabrowser" in lowered:
        browser = "Yandex Browser"
    elif "edg/" in lowered:
        browser = "Microsoft Edge"
    elif "chrome/" in lowered and "chromium" not in lowered:
        browser = "Google Chrome"
    elif "firefox/" in lowered:
        browser = "Mozilla Firefox"
    elif "safari/" in lowered and "chrome/" not in lowered:
        browser = "Safari"

    platform = "Unknown OS"
    if "android" in lowered:
        platform = "Android"
    elif "iphone" in lowered or "ipad" in lowered or "ios" in lowered:
        platform = "iOS"
    elif "windows" in lowered:
        platform = "Windows"
    elif "mac os x" in lowered or "macintosh" in lowered:
        platform = "macOS"
    elif "linux" in lowered:
        platform = "Linux"

    return f"{browser} on {platform}"


def create_auth_session(*, user: User, request) -> UserAuthSession:
    user_agent = extract_user_agent(request)
    return UserAuthSession.objects.create(
        user=user,
        ip_address=extract_client_ip(request) or None,
        user_agent=user_agent,
        device_name=build_device_name(user_agent),
    )


def _load_session_from_token(token: Any, *, user: User | None = None) -> UserAuthSession:
    session_id = token.get(SESSION_ID_CLAIM)
    if not session_id:
        raise AuthenticationFailed("session_missing")

    user_id = token.get(jwt_api_settings.USER_ID_CLAIM)
    if user is not None:
        user_id = user.pk

    try:
        return UserAuthSession.objects.select_related("user").get(
            session_id=session_id,
            user_id=user_id,
        )
    except UserAuthSession.DoesNotExist as exc:
        raise AuthenticationFailed("session_not_found") from exc


def touch_session(
    session: UserAuthSession,
    *,
    request=None,
    force: bool = False,
) -> UserAuthSession:
    now = timezone.now()
    update_fields: list[str] = []

    if force or not session.last_seen_at or (
        now - session.last_seen_at >= LAST_SEEN_UPDATE_INTERVAL
    ):
        session.last_seen_at = now
        update_fields.append("last_seen_at")

    if request is not None:
        ip_address = extract_client_ip(request) or None
        user_agent = extract_user_agent(request)
        device_name = build_device_name(user_agent)

        if session.ip_address != ip_address:
            session.ip_address = ip_address
            update_fields.append("ip_address")
        if user_agent and session.user_agent != user_agent:
            session.user_agent = user_agent
            update_fields.append("user_agent")
        if device_name and session.device_name != device_name:
            session.device_name = device_name
            update_fields.append("device_name")

    if update_fields:
        session.save(update_fields=update_fields)
    return session


def validate_access_session(
    token: Any,
    *,
    user: User,
    request=None,
) -> UserAuthSession:
    session = _load_session_from_token(token, user=user)
    if session.is_revoked:
        raise AuthenticationFailed("session_revoked")
    return touch_session(session, request=request)


def validate_refresh_session(
    token: Any,
    *,
    raw_refresh: str,
    request=None,
) -> UserAuthSession:
    session = _load_session_from_token(token)
    if session.is_revoked:
        raise InvalidToken("session_revoked")

    expected_hash = hash_refresh_token(raw_refresh)
    if session.refresh_token_hash != expected_hash:
        raise InvalidToken("session_mismatch")

    return touch_session(session, request=request, force=True)
