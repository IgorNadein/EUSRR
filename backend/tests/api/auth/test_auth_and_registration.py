import re
import pytest
from datetime import timedelta
from urllib.parse import parse_qs, urlparse
from unittest.mock import Mock

from django.core import mail
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from api.auth.models import UserAuthSession
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

pytestmark = pytest.mark.django_db
User = get_user_model()


# ======== фикстуры ========


@pytest.fixture
def api():
    return APIClient()


@pytest.fixture(autouse=True)
def _locmem_email_backend(settings):
    # Все письма складываются в mail.outbox
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    settings.LDAP_ENABLED = False
    settings.LDAP_WRITE_ENABLED = False


# ======== утилиты ========


def extract_code_from_last_email() -> str | None:
    """
    В менеджере пользователей письмо выглядит как:
    "Ваш код подтверждения: 123456"
    Вытаскиваем 6 цифр из последнего письма.
    """
    assert mail.outbox, "Почтовый ящик пуст — письмо не отправлялось"
    body = mail.outbox[-1].body
    m = re.search(r"(\d{6})", body)
    return m.group(1) if m else None


def extract_reset_link_from_last_email() -> str:
    assert mail.outbox, "Почтовый ящик пуст — письмо не отправлялось"
    body = mail.outbox[-1].body
    match = re.search(r"(https?://\S+)", body)
    assert match, "В письме нет ссылки восстановления"
    return match.group(1)


def extract_reset_params_from_last_email() -> tuple[str, str]:
    parsed = urlparse(extract_reset_link_from_last_email())
    query = parse_qs(parsed.query)
    uid = query.get("uid", [None])[0]
    token = query.get("token", [None])[0] or query.get("amp;token", [None])[0]
    assert uid and token, "В ссылке восстановления нет uid/token"
    return uid, token


def register_payload(**overrides):
    # Минимальный валидный PNG 1x1 пиксель (прозрачный) в base64
    tiny_png_base64 = (
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    )
    data = {
        "first_name": "Иван",
        "last_name": "Иванов",
        "phone_number": "+79990000001",
        "email": "ivan@example.com",
        "password": "Str0ngPass!",
        "birth_date": "1990-01-01",
        "gender": 1,  # 1 - Мужской, 2 - Женский
        "avatar": f"data:image/png;base64,{tiny_png_base64}",
        # Контактные поля опциональны, но можно указать одно:
        "telegram": "@ivan",
        # опционально можно добавить другие поля модели
    }
    data.update(overrides)
    return data


def register(api: APIClient, **overrides):
    url = reverse("api:v1:register")
    return api.post(url, register_payload(**overrides), format="json")


def verify(api: APIClient, *, email: str, code: str | None):
    url = reverse("api:v1:verify-email")
    # интерфейс верификации: email + code
    return api.post(url, {"email": email, "code": code}, format="json")


def resend(api: APIClient, *, email: str):
    url = reverse("api:v1:resend-email")
    return api.post(url, {"email": email}, format="json")


def jwt_obtain(
    api: APIClient,
    *,
    email: str | None = None,
    phone: str | None = None,
    password: str = "Str0ngPass!"
):
    """
    Ожидаем, что аутентификация поддерживает вход по email ИЛИ по телефону.
    - По email: передаём {"email": ..., "password": ...}
    - По телефону: передаём {"phone_number": ..., "password": ...}
    """
    url = reverse("api:token_obtain_pair")
    if email:
        payload = {"email": email, "password": password}
    else:
        payload = {"phone_number": phone, "password": password}
    return api.post(url, payload, format="json")


def auth_headers(access: str) -> dict[str, str]:
    return {"HTTP_AUTHORIZATION": f"Bearer {access}"}


def request_password_reset(api: APIClient, *, login: str):
    return api.post(
        reverse("api:password-reset"),
        {"login": login},
        format="json",
    )


def confirm_password_reset(
    api: APIClient,
    *,
    uid: str,
    token: str,
    new_password: str,
    route_name: str = "api:password-reset-confirm",
):
    return api.post(
        reverse(route_name),
        {
            "uid": uid,
            "token": token,
            "new_password": new_password,
            "new_password_confirm": new_password,
        },
        format="json",
    )


# ======== регистрация: happy-path ========


def test_register_success_sends_email_and_user_inactive(api):
    resp = register(api)
    assert resp.status_code == status.HTTP_201_CREATED

    # письмо с кодом отправлено
    assert len(mail.outbox) == 1
    code = extract_code_from_last_email()
    assert code and len(code) == 6

    # пользователь создан и пока неактивен/неподтверждён
    u = User.objects.get(email="ivan@example.com")
    assert u.email_verified is False
    assert u.is_active is False
    assert u.email_activation_code == code


# ======== регистрация: обязательные поля ========


@pytest.mark.parametrize(
    "missing_field",
    ["first_name", "last_name", "phone_number", "email", "password", "birth_date"],
)
def test_register_missing_required_field(api, missing_field):
    payload = register_payload()
    payload.pop(missing_field)
    resp = api.post(reverse("api:v1:register"), payload, format="json")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_register_birth_date_must_be_valid_date(api):
    resp = register(api, birth_date="not-a-date")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST


def test_register_duplicate_email_phone(api):
    # 1) Регистрируем первого пользователя (пока не подтверждён)
    payload = register_payload()
    assert register(api, **payload).status_code == status.HTTP_201_CREATED

    # 2) Пытаемся ещё раз с тем же email (но другим телефоном) пока email НЕ подтверждён
    #    Ожидаем мягкий ответ для редиректа на ввод кода: 200 + pending_verification
    r = register(api, email=payload["email"], phone_number="+79990000002")
    assert r.status_code == status.HTTP_200_OK
    body = r.json()
    assert body.get("ok") is True
    assert body.get("pending_verification") is True

    # 3) Теперь подтверждаем email первого пользователя
    code = extract_code_from_last_email()
    assert verify(api, email=payload["email"], code=code).status_code in (200, 204)

    # 4) Пытаемся зарегистрироваться снова с тем же уже ПОДТВЕРЖДЁННЫМ email
    #    Ожидаем жёсткую ошибку «email уже занят»
    r = register(api, email=payload["email"], phone_number="+79990000003")
    assert r.status_code == status.HTTP_400_BAD_REQUEST
    err = r.json()
    assert err.get("error") == "email_taken" or "email" in err

    # 5) Дубликат телефона (тот же номер, другой email) всегда 400
    r = register(api, email="ivan2@example.com", phone_number=payload["phone_number"])
    assert r.status_code == status.HTTP_400_BAD_REQUEST


def test_register_accepts_optional_fields(api):
    resp = register(
        api,
        patronymic="Петрович",
        gender=1,
        whatsapp="+79995550011",  # можно указать другой контакт
        telegram="",  # телеграм можно не указывать, т.к. whatsapp есть
    )
    assert resp.status_code == status.HTTP_201_CREATED


# ======== подтверждение email ========


def test_verify_email_success_activates_user(api):
    assert register(api).status_code == status.HTTP_201_CREATED
    code = extract_code_from_last_email()
    r = verify(api, email="ivan@example.com", code=code)
    assert r.status_code in (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT)

    u = User.objects.get(email="ivan@example.com")
    assert u.email_verified is True
    assert u.is_active is True
    assert u.email_activation_code in (None, "")


def test_verify_email_wrong_code(api):
    assert register(api).status_code == status.HTTP_201_CREATED
    r = verify(api, email="ivan@example.com", code="000000")
    assert r.status_code == status.HTTP_400_BAD_REQUEST

    u = User.objects.get(email="ivan@example.com")
    assert not u.email_verified
    assert not u.is_active


def test_resend_email_sends_new_code_and_old_becomes_invalid(api):
    assert register(api).status_code == status.HTTP_201_CREATED
    old = extract_code_from_last_email()

    # отправляем новый код
    rr = resend(api, email="ivan@example.com")
    assert rr.status_code in (status.HTTP_200_OK, status.HTTP_204_NO_CONTENT)
    assert len(mail.outbox) >= 2
    new = extract_code_from_last_email()
    assert new != old

    # старый — не подходит
    assert (
        verify(api, email="ivan@example.com", code=old).status_code
        == status.HTTP_400_BAD_REQUEST
    )
    # новый — активирует
    assert verify(api, email="ivan@example.com", code=new).status_code in (
        status.HTTP_200_OK,
        status.HTTP_204_NO_CONTENT,
    )

    u = User.objects.get(email="ivan@example.com")
    assert u.is_active and u.email_verified


def test_verify_expired_more_than_5_minutes_deletes_account(api, settings):
    # Регистрируем
    assert register(api).status_code == status.HTTP_201_CREATED
    code = extract_code_from_last_email()
    u = User.objects.get(email="ivan@example.com")

    # Старим запись > 5 минут
    ts = timezone.now() - timedelta(minutes=6)
    # у модели есть и created_at, и date_joined — переставим оба, чтобы покрыть любую реализацию проверки
    User.objects.filter(pk=u.pk).update(created_at=ts, date_joined=ts)

    # Пытаемся подтвердить — ожидаем, что аккаунт удалён/подтверждение отвергнуто
    r = verify(api, email="ivan@example.com", code=code)
    assert r.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_404_NOT_FOUND)
    assert not User.objects.filter(email="ivan@example.com").exists()


# ======== авторизация (JWT): по email и по телефону ========


def test_login_by_email_denied_before_verify(api):
    assert register(api).status_code == status.HTTP_201_CREATED
    # до верификации — 401
    r = jwt_obtain(api, email="ivan@example.com", password="Str0ngPass!")
    assert r.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED)


def test_login_by_email_allowed_after_verify(api):
    assert register(api).status_code == status.HTTP_201_CREATED
    code = extract_code_from_last_email()
    assert verify(api, email="ivan@example.com", code=code).status_code in (200, 204)

    r = jwt_obtain(api, email="ivan@example.com", password="Str0ngPass!")
    assert r.status_code == status.HTTP_200_OK
    body = r.json()
    assert "access" in body and "refresh" in body


def test_login_by_phone_allowed_after_verify(api):
    # Регистрируем с телефоном и подтверждаем
    payload = register_payload()
    assert register(api, **payload).status_code == status.HTTP_201_CREATED
    code = extract_code_from_last_email()
    assert verify(api, email=payload["email"], code=code).status_code in (200, 204)

    r = jwt_obtain(api, phone=payload["phone_number"], password=payload["password"])
    # Если у вас кастомный сериализатор SimpleJWT, этот тест должен проходить.
    # Если пока не реализовано — он падёт, что будет сигналом допилить вход по телефону.
    assert r.status_code == status.HTTP_200_OK
    assert {"access", "refresh"} <= set(r.json().keys())


def test_login_wrong_password(api):
    assert register(api).status_code == status.HTTP_201_CREATED
    code = extract_code_from_last_email()
    verify(api, email="ivan@example.com", code=code)

    r = jwt_obtain(api, email="ivan@example.com", password="BAD")
    assert r.status_code in (status.HTTP_400_BAD_REQUEST, status.HTTP_401_UNAUTHORIZED)


@pytest.mark.parametrize(
    ("route_name", "path"),
    [
        ("api:register", "/api/auth/register/"),
        ("api:v1:register", "/api/v1/auth/register/"),
        ("api:resend-email", "/api/auth/resend-email/"),
        ("api:v1:resend-email", "/api/v1/auth/resend-email/"),
        ("api:verify-email", "/api/auth/verify-email/"),
        ("api:v1:verify-email", "/api/v1/auth/verify-email/"),
        ("api:token_obtain_pair", "/api/auth/token/"),
        ("api:v1:token_obtain_pair", "/api/v1/auth/token/"),
        ("api:token_refresh", "/api/auth/token/refresh/"),
        ("api:v1:token_refresh", "/api/v1/auth/token/refresh/"),
        ("api:password-reset", "/api/auth/password-reset/"),
        ("api:v1:password-reset", "/api/v1/auth/password-reset/"),
        ("api:password-reset-confirm", "/api/auth/password-reset/confirm/"),
        ("api:v1:password-reset-confirm", "/api/v1/auth/password-reset/confirm/"),
        ("api:change-password", "/api/auth/change-password/"),
        ("api:v1:change-password", "/api/v1/auth/change-password/"),
        ("api:sessions", "/api/auth/sessions/"),
        ("api:v1:sessions", "/api/v1/auth/sessions/"),
        ("api:logout-others", "/api/auth/sessions/logout-others/"),
        ("api:v1:logout-others", "/api/v1/auth/sessions/logout-others/"),
    ],
)
def test_auth_routes_are_mirrored(route_name, path):
    assert reverse(route_name) == path


def test_login_creates_auth_session_and_embeds_session_id(api):
    assert register(api).status_code == status.HTTP_201_CREATED
    code = extract_code_from_last_email()
    assert verify(api, email="ivan@example.com", code=code).status_code in (200, 204)

    response = jwt_obtain(api, email="ivan@example.com")
    assert response.status_code == status.HTTP_200_OK

    payload = response.json()
    access = AccessToken(payload["access"])
    refresh = RefreshToken(payload["refresh"])

    assert access["session_id"] == refresh["session_id"]

    session = UserAuthSession.objects.get(session_id=access["session_id"])
    assert session.user.email == "ivan@example.com"
    assert session.refresh_token_hash


def test_sessions_list_and_logout_others_revoke_other_session(api):
    assert register(api).status_code == status.HTTP_201_CREATED
    code = extract_code_from_last_email()
    assert verify(api, email="ivan@example.com", code=code).status_code in (200, 204)

    first = jwt_obtain(api, email="ivan@example.com")
    second = jwt_obtain(api, email="ivan@example.com")
    assert first.status_code == second.status_code == status.HTTP_200_OK

    access1 = first.json()["access"]
    access2 = second.json()["access"]
    refresh2 = second.json()["refresh"]
    session_id_2 = str(AccessToken(access2)["session_id"])

    listed = api.get(reverse("api:sessions"), **auth_headers(access1))
    assert listed.status_code == status.HTTP_200_OK
    assert len(listed.json()) == 2

    logout_others = api.post(reverse("api:logout-others"), **auth_headers(access1))
    assert logout_others.status_code == status.HTTP_200_OK
    assert logout_others.json()["revoked"] == 1

    listed_after = api.get(reverse("api:v1:sessions"), **auth_headers(access1))
    assert listed_after.status_code == status.HTTP_200_OK
    assert len(listed_after.json()) == 1
    assert listed_after.json()[0]["is_current"] is True

    profile = api.get(reverse("api:v1:employees-me"), **auth_headers(access2))
    assert profile.status_code == status.HTTP_401_UNAUTHORIZED

    refresh_resp = api.post(
        reverse("api:v1:token_refresh"),
        {"refresh": refresh2},
        format="json",
    )
    assert refresh_resp.status_code == status.HTTP_401_UNAUTHORIZED

    session = UserAuthSession.objects.get(session_id=session_id_2)
    assert session.revoked_at is not None


def test_delete_current_session_revokes_access_immediately(api):
    assert register(api).status_code == status.HTTP_201_CREATED
    code = extract_code_from_last_email()
    assert verify(api, email="ivan@example.com", code=code).status_code in (200, 204)

    login = jwt_obtain(api, email="ivan@example.com")
    assert login.status_code == status.HTTP_200_OK

    access = login.json()["access"]
    session_id = AccessToken(access)["session_id"]

    before = api.get(reverse("api:v1:employees-me"), **auth_headers(access))
    assert before.status_code == status.HTTP_200_OK

    deleted = api.delete(
        reverse("api:session-detail", kwargs={"session_id": session_id}),
        **auth_headers(access),
    )
    assert deleted.status_code == status.HTTP_204_NO_CONTENT

    after = api.get(reverse("api:v1:employees-me"), **auth_headers(access))
    assert after.status_code == status.HTTP_401_UNAUTHORIZED


def test_change_password_updates_local_password(api):
    assert register(api).status_code == status.HTTP_201_CREATED
    code = extract_code_from_last_email()
    assert verify(api, email="ivan@example.com", code=code).status_code in (200, 204)

    login = jwt_obtain(api, email="ivan@example.com", password="Str0ngPass!")
    assert login.status_code == status.HTTP_200_OK
    access = login.json()["access"]

    response = api.post(
        reverse("api:change-password"),
        {
            "current_password": "Str0ngPass!",
            "new_password": "NewStrongPass123!",
            "new_password_confirm": "NewStrongPass123!",
        },
        format="json",
        **auth_headers(access),
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"ok": True}

    old_login = jwt_obtain(api, email="ivan@example.com", password="Str0ngPass!")
    assert old_login.status_code in (
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
    )

    new_login = jwt_obtain(
        api,
        email="ivan@example.com",
        password="NewStrongPass123!",
    )
    assert new_login.status_code == status.HTTP_200_OK


def test_change_password_requires_valid_current_password(api):
    assert register(api).status_code == status.HTTP_201_CREATED
    code = extract_code_from_last_email()
    assert verify(api, email="ivan@example.com", code=code).status_code in (200, 204)

    login = jwt_obtain(api, email="ivan@example.com")
    access = login.json()["access"]

    response = api.post(
        reverse("api:v1:change-password"),
        {
            "current_password": "BAD",
            "new_password": "NewStrongPass123!",
            "new_password_confirm": "NewStrongPass123!",
        },
        format="json",
        **auth_headers(access),
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "current_password" in response.json()


def test_change_password_uses_ldap_update_for_ldap_managed_user(api, monkeypatch):
    assert register(api).status_code == status.HTTP_201_CREATED
    code = extract_code_from_last_email()
    assert verify(api, email="ivan@example.com", code=code).status_code in (200, 204)

    login = jwt_obtain(api, email="ivan@example.com", password="Str0ngPass!")
    assert login.status_code == status.HTTP_200_OK
    access = login.json()["access"]

    user = User.objects.get(email="ivan@example.com")
    user.is_ldap_managed = True
    user.set_unusable_password()
    user.save(update_fields=["is_ldap_managed", "password"])

    auth_mock = Mock(return_value=user)
    update_mock = Mock(return_value=user)
    monkeypatch.setattr("api.auth.views.authenticate", auth_mock)
    monkeypatch.setattr("employees.ldap.UserService.update_user", update_mock)

    response = api.post(
        reverse("api:change-password"),
        {
            "current_password": "Str0ngPass!",
            "new_password": "NewStrongPass123!",
            "new_password_confirm": "NewStrongPass123!",
        },
        format="json",
        **auth_headers(access),
    )
    assert response.status_code == status.HTTP_200_OK
    auth_mock.assert_called_once()
    update_mock.assert_called_once_with(
        emp=user,
        changes={"password": "NewStrongPass123!"},
        group_cns=None,
        move_to_department_dn=None,
    )


def test_password_reset_request_sends_email_by_email_or_phone(api):
    assert register(api).status_code == status.HTTP_201_CREATED
    user = User.objects.get(email="ivan@example.com")

    by_email = request_password_reset(api, login="ivan@example.com")
    assert by_email.status_code == status.HTTP_200_OK
    assert by_email.json() == {"ok": True}
    assert len(mail.outbox) == 2  # registration + reset

    by_phone = request_password_reset(api, login=str(user.phone_number))
    assert by_phone.status_code == status.HTTP_200_OK
    assert by_phone.json() == {"ok": True}
    assert len(mail.outbox) == 3


def test_password_reset_request_does_not_leak_nonexistent_user(api):
    response = request_password_reset(api, login="nobody@example.com")
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"ok": True}
    assert len(mail.outbox) == 0


def test_password_reset_confirm_updates_local_password(api):
    assert register(api).status_code == status.HTTP_201_CREATED
    code = extract_code_from_last_email()
    assert verify(api, email="ivan@example.com", code=code).status_code in (200, 204)
    assert request_password_reset(api, login="ivan@example.com").status_code == 200
    uid, token = extract_reset_params_from_last_email()

    response = confirm_password_reset(
        api,
        uid=uid,
        token=token,
        new_password="RecoveredPass123!",
    )
    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"ok": True}

    old_login = jwt_obtain(api, email="ivan@example.com", password="Str0ngPass!")
    assert old_login.status_code in (
        status.HTTP_400_BAD_REQUEST,
        status.HTTP_401_UNAUTHORIZED,
    )

    new_login = jwt_obtain(api, email="ivan@example.com", password="RecoveredPass123!")
    assert new_login.status_code == status.HTTP_200_OK


def test_password_reset_confirm_rejects_invalid_token(api):
    assert register(api).status_code == status.HTTP_201_CREATED
    response = confirm_password_reset(
        api,
        uid="bad",
        token="broken",
        new_password="RecoveredPass123!",
    )
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "token" in response.json()


def test_password_reset_confirm_uses_ldap_update_for_ldap_managed_user(api, monkeypatch):
    assert register(api).status_code == status.HTTP_201_CREATED
    user = User.objects.get(email="ivan@example.com")
    user.is_ldap_managed = True
    user.set_unusable_password()
    user.save(update_fields=["is_ldap_managed", "password"])

    assert request_password_reset(api, login="ivan@example.com").status_code == 200
    uid, token = extract_reset_params_from_last_email()

    update_mock = Mock(return_value=user)
    monkeypatch.setattr("employees.ldap.UserService.update_user", update_mock)

    response = confirm_password_reset(
        api,
        uid=uid,
        token=token,
        new_password="RecoveredPass123!",
        route_name="api:v1:password-reset-confirm",
    )
    assert response.status_code == status.HTTP_200_OK
    update_mock.assert_called_once_with(
        emp=user,
        changes={"password": "RecoveredPass123!"},
        group_cns=None,
        move_to_department_dn=None,
    )
