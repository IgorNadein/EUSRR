import re
import pytest
from datetime import timedelta

from django.core import mail
from django.urls import reverse
from django.utils import timezone
from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.test import APIClient

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


def register_payload(**overrides):
    data = {
        "first_name": "Иван",
        "last_name": "Иванов",
        "phone_number": "+79990000001",
        "email": "ivan@example.com",
        "password": "Str0ngPass!",
        "birth_date": "1990-01-01",
        # достаточно любого из контактов:
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


def test_register_requires_at_least_one_contact(api):
    payload = register_payload(telegram="", whatsapp="", wechat="")
    resp = api.post(reverse("api:v1:register"), payload, format="json")
    assert resp.status_code == status.HTTP_400_BAD_REQUEST
    assert (
        "WhatsApp" in resp.json().get("detail", "")
        or "WeChat" in resp.json().get("detail", "")
        or "Telegram" in resp.json().get("detail", "")
    )


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
