from __future__ import annotations

import itertools
from typing import Any, Callable, Dict, Final, Optional

import pytest
from django.contrib.auth import get_user_model
from django.db import models
from rest_framework.test import APIClient

# === при необходимости поменяй URL выдачи токена (SimpleJWT) ===
TOKEN_OBTAIN_URL: Final[str] = "/api/auth/token/"


# Путь коллекции и деталки (поменяйте при необходимости)
LIST_URL: Final[str] = "/api/v1/requests/"
DETAIL_URL_FMT: Final[str] = "/api/v1/requests/{id}/"

# Модельное право, дающее доступ видеть чужие заявки (укажите ваш codename)
# пример: "requests_app.view_request"
MODEL_VIEW_PERMISSION: Final[str] = "requests_app.view_request"

# Минимальный валидный payload для создания заявления
# ❗ Заполните под ваш сериализатор (обязательные поля!)
SAMPLE_CREATE_PAYLOAD: Dict[str, Any] = {
    # "title": "Командировка",
    # "body": "По проекту А",
}
# =============================================================

_phone_counter = itertools.count(100_000_000)  # 9 цифр для номера после +79


def _detect_phone_field(User: type[models.Model]) -> Optional[str]:
    """Возвращает имя телефонного поля модели пользователя, если оно есть.

    Проверяются популярные варианты: 'phone', 'phone_number', 'mobile', 'mobile_phone'.

    Args:
        User (type[models.Model]): Класс пользовательской модели.

    Returns:
        Optional[str]: Имя поля телефона или None, если поле не найдено.

    Raises:
        AttributeError: Если у модели отсутствует _meta (не должно случиться у Django-моделей).
    """
    candidates = ("phone", "phone_number", "mobile", "mobile_phone")
    for name in candidates:
        try:
            User._meta.get_field(name)  # type: ignore[attr-defined]
            return name
        except Exception:
            continue
    return None


def _next_ru_phone() -> str:
    """Генерирует уникальный российский номер в формате E.164 (+79XXXXXXXXX).

    Returns:
        str: Телефон в формате +79XXXXXXXXX.

    Raises:
        OverflowError: Если счётчик телефонов переполнится (практически нереально в тестах).
    """
    return f"+79{next(_phone_counter):09d}"


@pytest.fixture
def api_client() -> APIClient:
    """Чистый DRF-клиент без авторизации.

    Returns:
        APIClient: Клиент без заголовков авторизации.

    Raises:
        RuntimeError: Если DRF не установлен/не сконфигурирован.
    """
    return APIClient()


@pytest.fixture
def make_user() -> Callable[..., models.Model]:
    """Фабрика пользователей, совместимая с кастомной моделью (телефон может быть обязателен).

    По умолчанию:
      - задаёт уникальный email;
      - автоматически проставляет телефон в найденное поле;
      - при необходимости выставляет флаги is_staff/is_superuser;
      - устанавливает пароль.

    Returns:
        Callable[..., models.Model]: Функция создания пользователя.

    Raises:
        Exception: Любые ошибки создания пользователя прокидываются наверх.
    """
    User = get_user_model()
    phone_field = _detect_phone_field(User)

    def _make_user(
        email: str = "user@example.com",
        *,
        password: str = "pass12345",
        is_staff: bool = False,
        is_superuser: bool = False,
        phone: Optional[str] = None,
        **extra: object,
    ) -> models.Model:
        """Создаёт пользователя и возвращает его инстанс.

        Args:
            email (str): Email пользователя (должен быть уникален, если так настроена модель).
            password (str): Пароль (если пустой — пароль не устанавливается).
            is_staff (bool): Флаг персонала админки.
            is_superuser (bool): Флаг суперпользователя.
            phone (Optional[str]): Номер телефона; если не задан — сгенерируется автоматически, если поле найдено.
            **extra (object): Дополнительные поля, передаются в create_user.

        Returns:
            models.Model: Созданный пользователь.

        Raises:
            ValueError: Если менеджер модели требует телефон, а мы не смогли его задать.
        """
        kwargs: dict[str, object] = {"email": email, **extra}

        # Если модель содержит тел. поле — заполним его (некоторые менеджеры делают его обязательным).
        if phone_field:
            kwargs[phone_field] = phone or _next_ru_phone()
        elif phone is not None:
            # Если тест явно передал phone, а поле называется иначе — пусть упадёт в менеджере;
            # это подсветит реальное имя поля.
            kwargs["phone"] = phone  # type: ignore[assignment]

        user = User.objects.create_user(**kwargs)  # type: ignore[arg-type]
        if password:
            user.set_password(password)
        if is_staff:
            user.is_staff = True
        if is_superuser:
            user.is_superuser = True
        user.save()
        return user

    return _make_user


@pytest.fixture
def regular_user(make_user: Callable[..., models.Model]) -> models.Model:
    """Обычный пользователь без спецправ.

    Args:
        make_user (Callable[..., models.Model]): Фабрика пользователей.

    Returns:
        models.Model: Пользователь.
    """
    return make_user(email="regular@example.com")


@pytest.fixture
def admin_user(make_user: Callable[..., models.Model]) -> models.Model:
    """Администратор (суперпользователь).

    Args:
        make_user (Callable[..., models.Model]): Фабрика пользователей.

    Returns:
        models.Model: Суперпользователь.
    """
    return make_user(email="admin@example.com", is_staff=True, is_superuser=True)


@pytest.fixture
def auth_client() -> Callable[[models.Model], APIClient]:
    """Фабрика авторизованных DRF-клиентов с использованием force_authenticate.

    Это быстрый и надёжный способ авторизации в unit-тестах API без зависимости от JWT.

    Returns:
        Callable[[models.Model], APIClient]: Функция, принимающая пользователя и возвращающая авторизованный клиент.

    Raises:
        AssertionError: Если передан объект, не являющийся Django-моделью.
    """

    def _build(user: models.Model) -> APIClient:
        if not isinstance(user, models.Model):
            raise AssertionError("user должен быть Django-моделью.")
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    return _build


def _obtain_access_token(api_client: APIClient, username: str, password: str) -> str:
    """Получает access-токен через эндпоинт SimpleJWT.

    Args:
        api_client (APIClient): Клиент без авторизации.
        username (str): Имя пользователя.
        password (str): Пароль пользователя.

    Returns:
        str: Строка access-токена.

    Raises:
        AssertionError: Если эндпоинт вернул не 200/201 или тело ответа без токена.
        KeyError: Если формат тела ответа неожиданный.
    """
    resp = api_client.post(TOKEN_OBTAIN_URL, {"username": username, "password": password}, format="json")
    assert resp.status_code in (200, 201), f"Token obtain failed: {resp.status_code} {resp.content!r}"
    access = resp.data.get("access") or resp.data.get("token")
    assert access, f"No access token in response: {resp.data}"
    return str(access)


@pytest.fixture
def jwt_auth_client(api_client: APIClient, regular_user: models.Model) -> APIClient:
    """DRF-клиент, авторизованный через Bearer-токен (SimpleJWT).

    Полезно для интеграционных тестов, где важно пройти реальный путь аутентификации.

    Args:
        api_client (APIClient): Неаутентифицированный клиент.
        regular_user (models.Model): Пользователь.

    Returns:
        APIClient: Клиент с заголовком Authorization.

    Raises:
        AssertionError: Если не удалось получить токен или эндпоинт недоступен.
    """
    # В менеджере пользователя может быть username/email — берём .get_username() для совместимости
    username = getattr(regular_user, "get_username", lambda: getattr(regular_user, "username", "regular"))()
    token = _obtain_access_token(api_client, username, "pass12345")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client


@pytest.fixture
def jwt_admin_auth_client(api_client: APIClient, admin_user: models.Model) -> APIClient:
    """DRF-клиент с Bearer-токеном суперпользователя (SimpleJWT).

    Args:
        api_client (APIClient): Неаутентифицированный клиент.
        admin_user (models.Model): Суперпользователь.

    Returns:
        APIClient: Клиент с заголовком Authorization.

    Raises:
        AssertionError: Если не удалось получить токен.
    """
    username = getattr(admin_user, "get_username", lambda: getattr(admin_user, "username", "admin"))()
    token = _obtain_access_token(api_client, username, "pass12345")
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
    return api_client
