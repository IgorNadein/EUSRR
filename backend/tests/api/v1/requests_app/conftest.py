from __future__ import annotations

import itertools
from typing import Callable, Final, Optional  # убрал Any, Dict
from django.core.exceptions import FieldDoesNotExist  # новое

import pytest
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import models
from rest_framework.test import APIClient
from requests_app.models import Request as Req

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
        is_active=True,
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
        if is_active:
            user.is_active = True
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
def grant_model_perm(db):
    def _grant(user, perm_str: str):
        app_label, codename = perm_str.split(".")
        perm = Permission.objects.get(
            content_type__app_label=app_label, codename=codename
        )
        user.user_permissions.add(perm)
        # сбиваем кэш прав на текущем экземпляре
        if hasattr(user, "_perm_cache"):
            delattr(user, "_perm_cache")
        # возвращаем свежий экземпляр из БД
        return get_user_model().objects.get(pk=user.pk)

    return _grant


@pytest.fixture
def make_request(db):
    """Фабрика: создаёт заявку с минимальными полями.

    Если передан финальный статус (APPROVED/REJECTED), гарантирует заполненный approver,
    чтобы пройти CHECK-констрейнт БД `request_approver_required_on_decision`.
    """

    def _make(
        *,
        employee: models.Model,
        type_: str = Req.TYPE_VACATION,
        status: str | None = None,
        comment: str = "",
        approver: models.Model | None = None,
    ) -> Req:
        """Создаёт `requests_app.Request`.

        Args:
            employee (models.Model): Владелец заявки.
            type_ (str): Тип заявки.
            status (str | None): Начальный статус (если None — возьмётся дефолт модели).
            comment (str): Комментарий.
            approver (models.Model | None): Согласующий; обязателен для финальных статусов.

        Returns:
            Req: Созданный объект.

        Raises:
            ValueError: Если для финального статуса не удалось определить approver.
        """
        obj = Req.objects.create(employee=employee, type=type_, comment=comment)

        if status:
            obj.status = status

            # Для «решённых» статусов БД требует approver.
            final_statuses = {
                getattr(Req, "STATUS_APPROVED", "approved"),
                getattr(Req, "STATUS_REJECTED", "rejected"),
            }
            if status in final_statuses:
                obj.approver = approver or employee  # в тестах допустимо
                # Опционально поставим время решения, если модель его использует
                if hasattr(obj, "decided_at") and not obj.decided_at:
                    from django.utils import timezone

                    obj.decided_at = timezone.now()

            obj.save()

        return obj

    return _make
