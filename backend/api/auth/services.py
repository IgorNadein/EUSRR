from __future__ import annotations

import secrets
from datetime import timedelta
from typing import Any

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import transaction
from django.utils import timezone
from django.utils.crypto import salted_hmac
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.settings import api_settings as jwt_api_settings
from rest_framework_simplejwt.tokens import RefreshToken

from .models import QrLoginRequest, QrLoginToken, UserAuthSession

User = get_user_model()

SESSION_ID_CLAIM = "session_id"
LAST_SEEN_UPDATE_INTERVAL = timedelta(minutes=5)


def hash_refresh_token(raw_token: str) -> str:
    return salted_hmac("api.auth.refresh", raw_token).hexdigest()


def hash_qr_login_token(raw_token: str) -> str:
    return salted_hmac("api.auth.qr_login", raw_token).hexdigest()


def hash_qr_login_request_scan_token(raw_token: str) -> str:
    return salted_hmac("api.auth.qr_login_request.scan", raw_token).hexdigest()


def hash_qr_login_request_client_secret(raw_token: str) -> str:
    return salted_hmac("api.auth.qr_login_request.client", raw_token).hexdigest()


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
    return create_auth_session_from_client_info(
        user=user,
        ip_address=extract_client_ip(request) or None,
        user_agent=user_agent,
    )


def create_auth_session_from_client_info(
    *,
    user: User,
    ip_address: str | None,
    user_agent: str,
) -> UserAuthSession:
    return UserAuthSession.objects.create(
        user=user,
        ip_address=ip_address,
        user_agent=user_agent,
        device_name=build_device_name(user_agent),
    )


def create_token_pair_for_auth_session(
    *,
    user: User,
    session: UserAuthSession,
) -> tuple[str, str, UserAuthSession]:
    refresh = RefreshToken.for_user(user)
    refresh[SESSION_ID_CLAIM] = str(session.session_id)
    access = refresh.access_token
    access[SESSION_ID_CLAIM] = str(session.session_id)

    session.refresh_token_hash = hash_refresh_token(str(refresh))
    session.save(update_fields=["refresh_token_hash"])

    return str(refresh), str(access), session


def create_token_pair_for_session(
    *,
    user: User,
    request,
) -> tuple[str, str, UserAuthSession]:
    session = create_auth_session(user=user, request=request)
    return create_token_pair_for_auth_session(user=user, session=session)


def get_qr_login_ttl() -> timedelta:
    raw_seconds = getattr(settings, "QR_LOGIN_TOKEN_TTL_SECONDS", 120)
    try:
        seconds = int(raw_seconds)
    except (TypeError, ValueError):
        seconds = 120
    return timedelta(seconds=max(30, min(seconds, 600)))


def get_qr_login_request_ttl() -> timedelta:
    raw_seconds = getattr(settings, "QR_LOGIN_REQUEST_TTL_SECONDS", 120)
    try:
        seconds = int(raw_seconds)
    except (TypeError, ValueError):
        seconds = 120
    return timedelta(seconds=max(30, min(seconds, 600)))


def create_qr_login_token(
    *,
    user: User,
    request,
    current_session_id: str | None = None,
) -> tuple[str, QrLoginToken]:
    raw_token = secrets.token_urlsafe(32)
    current_session = None
    if current_session_id:
        current_session = UserAuthSession.objects.filter(
            user=user,
            session_id=current_session_id,
            revoked_at__isnull=True,
        ).first()

    token = QrLoginToken.objects.create(
        user=user,
        token_hash=hash_qr_login_token(raw_token),
        created_by_session=current_session,
        expires_at=timezone.now() + get_qr_login_ttl(),
        created_ip_address=extract_client_ip(request) or None,
        created_user_agent=extract_user_agent(request),
    )
    return raw_token, token


@transaction.atomic
def exchange_qr_login_token(*, raw_token: str, request) -> tuple[str, str]:
    token_hash = hash_qr_login_token(raw_token)
    qr_token = (
        QrLoginToken.objects.select_for_update()
        .select_related("user")
        .filter(token_hash=token_hash)
        .first()
    )

    if (
        qr_token is None
        or qr_token.is_used
        or qr_token.is_expired
        or not qr_token.user.is_active
        or not getattr(qr_token.user, "email_verified", False)
    ):
        raise InvalidToken("qr_login_token_invalid")

    refresh, access, session = create_token_pair_for_session(
        user=qr_token.user,
        request=request,
    )
    qr_token.used_at = timezone.now()
    qr_token.used_session = session
    qr_token.used_ip_address = extract_client_ip(request) or None
    qr_token.used_user_agent = extract_user_agent(request)
    qr_token.save(
        update_fields=[
            "used_at",
            "used_session",
            "used_ip_address",
            "used_user_agent",
        ]
    )

    return refresh, access


def create_qr_login_request(*, request) -> tuple[str, str, QrLoginRequest]:
    scan_token = secrets.token_urlsafe(32)
    client_secret = secrets.token_urlsafe(32)
    user_agent = extract_user_agent(request)
    qr_request = QrLoginRequest.objects.create(
        scan_token_hash=hash_qr_login_request_scan_token(scan_token),
        client_secret_hash=hash_qr_login_request_client_secret(client_secret),
        requester_ip_address=extract_client_ip(request) or None,
        requester_user_agent=user_agent,
        requester_device_name=build_device_name(user_agent),
        expires_at=timezone.now() + get_qr_login_request_ttl(),
    )
    return scan_token, client_secret, qr_request


def _load_qr_login_request_by_scan_token(
    raw_scan_token: str,
) -> QrLoginRequest:
    qr_request = QrLoginRequest.objects.filter(
        scan_token_hash=hash_qr_login_request_scan_token(raw_scan_token),
    ).first()
    if qr_request is None:
        raise InvalidToken("qr_login_request_not_found")
    return qr_request


def _load_qr_login_request_by_client_secret(
    raw_client_secret: str,
) -> QrLoginRequest:
    qr_request = QrLoginRequest.objects.filter(
        client_secret_hash=hash_qr_login_request_client_secret(raw_client_secret),
    ).first()
    if qr_request is None:
        raise InvalidToken("qr_login_request_not_found")
    return qr_request


def get_qr_login_request_for_approval(raw_scan_token: str) -> QrLoginRequest:
    return _load_qr_login_request_by_scan_token(raw_scan_token)


@transaction.atomic
def approve_qr_login_request(
    *,
    raw_scan_token: str,
    user: User,
    current_session_id: str | None,
) -> QrLoginRequest:
    qr_request = (
        QrLoginRequest.objects.select_for_update()
        .filter(scan_token_hash=hash_qr_login_request_scan_token(raw_scan_token))
        .first()
    )
    if qr_request is None or qr_request.status != "pending":
        raise InvalidToken("qr_login_request_not_pending")

    current_session = None
    if current_session_id:
        current_session = UserAuthSession.objects.filter(
            user=user,
            session_id=current_session_id,
            revoked_at__isnull=True,
        ).first()

    qr_request.approved_by = user
    qr_request.approved_by_session = current_session
    qr_request.approved_at = timezone.now()
    qr_request.save(
        update_fields=["approved_by", "approved_by_session", "approved_at"]
    )
    return qr_request


@transaction.atomic
def deny_qr_login_request(
    *,
    raw_scan_token: str,
    user: User,
) -> QrLoginRequest:
    qr_request = (
        QrLoginRequest.objects.select_for_update()
        .filter(scan_token_hash=hash_qr_login_request_scan_token(raw_scan_token))
        .first()
    )
    if qr_request is None or qr_request.status not in ("pending", "approved"):
        raise InvalidToken("qr_login_request_closed")

    qr_request.denied_by = user
    qr_request.denied_at = timezone.now()
    qr_request.save(update_fields=["denied_by", "denied_at"])
    return qr_request


@transaction.atomic
def cancel_qr_login_request(*, raw_client_secret: str) -> QrLoginRequest:
    qr_request = (
        QrLoginRequest.objects.select_for_update()
        .filter(
            client_secret_hash=hash_qr_login_request_client_secret(raw_client_secret),
        )
        .first()
    )
    if qr_request is None:
        raise InvalidToken("qr_login_request_not_found")
    if qr_request.status == "pending":
        qr_request.denied_at = timezone.now()
        qr_request.save(update_fields=["denied_at"])
    return qr_request


@transaction.atomic
def poll_qr_login_request(
    *,
    raw_client_secret: str,
    request,
) -> dict[str, str | None]:
    qr_request = (
        QrLoginRequest.objects.select_for_update()
        .select_related("approved_by")
        .filter(
            client_secret_hash=hash_qr_login_request_client_secret(raw_client_secret),
        )
        .first()
    )
    if qr_request is None:
        raise InvalidToken("qr_login_request_not_found")

    current_status = qr_request.status
    if current_status != "approved":
        return {"status": current_status}

    user = qr_request.approved_by
    if user is None or not user.is_active or not getattr(user, "email_verified", False):
        qr_request.denied_at = timezone.now()
        qr_request.save(update_fields=["denied_at"])
        return {"status": "denied"}

    user_agent = extract_user_agent(request) or qr_request.requester_user_agent
    session = create_auth_session_from_client_info(
        user=user,
        ip_address=extract_client_ip(request) or qr_request.requester_ip_address,
        user_agent=user_agent,
    )
    refresh, access, session = create_token_pair_for_auth_session(
        user=user,
        session=session,
    )
    qr_request.claimed_at = timezone.now()
    qr_request.used_session = session
    qr_request.save(update_fields=["claimed_at", "used_session"])

    return {"status": "approved", "refresh": refresh, "access": access}


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
