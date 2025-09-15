from __future__ import annotations

import itertools
from typing import Callable, Final, Optional  # убрал Any, Dict
from django.core.exceptions import FieldDoesNotExist  # новое

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import models
from rest_framework.test import APIClient

from .contract import MODEL_VIEW_PERMISSION

_phone_counter: Final = itertools.count(100_000_000)  # 9 цифр для номера после +79
_email_counter: Final = itertools.count(1)  # для уникальных email по умолчанию


def _detect_phone_field(User: type[models.Model]) -> Optional[str]:
    """Возвращает имя телефонного поля модели пользователя, если оно есть.

    Проверяются популярные варианты: 'phone', 'phone_number', 'mobile', 'mobile_phone'.

    Args:
        User (type[models.Model]): Класс пользовательской модели.

    Returns:
        Optional[str]: Имя поля телефона или None, если поле не найдено.
    """
    candidates = ("phone", "phone_number", "mobile", "mobile_phone")
    for name in candidates:
        try:
            User._meta.get_field(name)  # type: ignore[attr-defined]
            return name
        except (AttributeError, FieldDoesNotExist):
            # нет _meta или такое поле отсутствует — пробуем следующий вариант
            continue
    return None


def _next_ru_phone() -> str:
    """Генерирует уникальный российский номер в формате E.164 (+79XXXXXXXXX).

    Returns:
        str: Телефон в формате +79XXXXXXXXX.
    """
    # примечание: переполнение счётчика в тестовой среде нереалистично
    return f"+79{next(_phone_counter):09d}"


@pytest.fixture
def api_client() -> APIClient:
    """Чистый DRF-клиент без авторизации.

    Returns:
        APIClient: Клиент без заголовков авторизации.
    """
    return APIClient()


@pytest.fixture
def make_user() -> Callable[..., models.Model]:
    """Фабрика пользователей, совместимая с кастомной моделью (телефон может быть обязателен).

    По умолчанию:
      - задаёт уникальный email;
      - автоматически проставляет телефон в найденное поле;
      - отключает отправку писем активации в менеджере (`send_activation_email=False`);
      - выставляет флаги is_staff/is_superuser при необходимости;
      - устанавливает пароль.
    """
    User = get_user_model()
    phone_field = _detect_phone_field(User)
    username_field = getattr(User, "USERNAME_FIELD", "email")

    def _make_user(
        email: Optional[str] = None,
        *,
        password: str = "pass12345",
        is_staff: bool = False,
        is_superuser: bool = False,
        phone: Optional[str] = None,
        **extra: object,
    ) -> models.Model:
        """Создаёт пользователя и возвращает его инстанс.

        Args:
            email (Optional[str]): Email пользователя. Если не указан — сгенерируется уникальный.
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
        if email is None:
            email = f"user{next(_email_counter)}@example.com"

        # Отключаем реальную отправку писем активации в тестах.
        extra = {**extra, "send_activation_email": False}

        kwargs: dict[str, object] = {username_field: email, "email": email, **extra}

        if phone_field:
            kwargs[phone_field] = phone or _next_ru_phone()
        elif phone is not None:
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
    """Обычный пользователь без спецправ."""
    return make_user(email="regular@example.com")


@pytest.fixture
def admin_user(make_user: Callable[..., models.Model]) -> models.Model:
    """Администратор (суперпользователь)."""
    return make_user(email="admin@example.com", is_staff=True, is_superuser=True)


@pytest.fixture
def auth_client() -> Callable[[models.Model], APIClient]:
    """Фабрика авторизованных DRF-клиентов с использованием force_authenticate.

    Это быстрый и надёжный способ авторизации в unit-тестах API без зависимости от JWT.
    """

    def _build(user: models.Model) -> APIClient:
        if not isinstance(user, models.Model):
            raise AssertionError("user должен быть Django-моделью.")
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    return _build


@pytest.fixture
def grant_model_perm() -> Callable[[models.Model, str], None]:
    """Выдаёт пользователю модельное право (по умолчанию из MODEL_VIEW_PERMISSION).

    Возвращает функцию grant(user, perm_label='app_label.codename').
    """

    def _grant(user: models.Model, perm_label: str = MODEL_VIEW_PERMISSION) -> None:
        """Назначает пользователю право `perm_label`.

        Args:
            user (models.Model): Экземпляр пользователя.
            perm_label (str): Право в формате 'app_label.codename' (по умолчанию MODEL_VIEW_PERMISSION).

        Raises:
            AssertionError: Если указанное право не найдено.
            ValueError: Если строка права не в формате 'app_label.codename'.
        """
        if "." not in perm_label:
            raise ValueError("perm_label должен быть в формате 'app_label.codename'")
        app_label, codename = perm_label.split(".", 1)
        perm = Permission.objects.filter(
            content_type__app_label=app_label,
            codename=codename,
        ).first()
        assert perm is not None, (
            f"Permission '{perm_label}' не найден. Убедись, что приложение в INSTALLED_APPS "
            "и применены миграции (manage.py migrate)."
        )
        user.user_permissions.add(perm)
        # save() не требуется: изменение M2M уже записано

    return _grant
