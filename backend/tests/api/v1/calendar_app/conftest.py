# tests/conftest.py
from __future__ import annotations

import itertools
from collections.abc import Callable
from datetime import date, time
from typing import Callable, Generator, Optional, Tuple, Type

import pytest
from django.apps import apps as django_apps
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Permission
from django.db import IntegrityError, models
from django.db.models import Model as DjangoModel
from employees.constants import DeptPerm
from employees.models import (Department, DepartmentPermission, DepartmentRole,
                              Employee, EmployeeDepartment)
from rest_framework.test import APIClient

API_EVENTS = "/api/v1/calendar/events/"


_phone_counter = itertools.count(100_000_000)  # 9 цифр


def _detect_phone_field(User: type[models.Model]) -> str | None:
    """Возвращает имя телефонного поля модели пользователя, если оно есть.

    Проверяются популярные варианты: 'phone', 'phone_number', 'mobile', 'mobile_phone'.

    Args:
        User (type[models.Model]): Класс пользовательской модели.

    Returns:
        str | None: Имя поля телефона или None, если подходящее поле не найдено.
    """
    candidates = ("phone", "phone_number", "mobile", "mobile_phone")
    for name in candidates:
        try:
            User._meta.get_field(name)  # поле существует
            return name
        except Exception:
            continue
    return None


def _next_ru_phone() -> str:
    """Генерирует уникальный российский номер в формате E.164.

    Формат: +79XXXXXXXXX (после +7 идёт '9' и 9 цифр).

    Returns:
        str: Телефон в формате +79XXXXXXXXX.
    """
    return f"+79{next(_phone_counter):09d}"


@pytest.fixture
def api_url() -> str:
    """Базовый URL API календаря.

    Returns:
        str: Абсолютный путь к вьюсету событий.
    """
    return API_EVENTS


@pytest.fixture
def User() -> Type[models.Model]:
    """Модель пользователя проекта.

    Returns:
        Type[models.Model]: Модель пользователя (get_user_model()).
    """
    return get_user_model()


@pytest.fixture
def CalendarEvent() -> Type[models.Model]:
    """Модель событий календаря.

    Returns:
        Type[models.Model]: calendar_app.CalendarEvent.

    Raises:
        LookupError: Если приложение/модель не найдены.
    """
    return django_apps.get_model("calendar_app", "CalendarEvent")


@pytest.fixture
def Recurrence():
    """Enum повторяемости из приложения (это не модель)."""
    from calendar_app.models import Recurrence as _Recurrence

    return _Recurrence


@pytest.fixture
def Department() -> Optional[Type[models.Model]]:
    """Модель отдела.

    Returns:
        Optional[Type[models.Model]]: employees.Department или None, если нет.
    """
    try:
        return django_apps.get_model("employees", "Department")
    except LookupError:
        return None


@pytest.fixture
def make_user() -> callable:
    """Фабрика пользователей, совместимая с кастомной моделью, где телефон обязателен.

    По умолчанию:
      - задаёт уникальный email;
      - автоматически подставляет телефон в найденное поле;
      - при необходимости выставляет флаги is_staff/is_superuser.

    Returns:
        Callable[..., models.Model]: Функция создания пользователя.
    """
    User = get_user_model()
    phone_field = _detect_phone_field(User)

    def _make_user(
        email: str = "user@example.com",
        *,
        is_staff: bool = False,
        is_superuser: bool = False,
        password: str = "pass",
        phone: str | None = None,
        **extra: object,
    ) -> models.Model:
        """Создаёт пользователя.

        Args:
            email (str): Email пользователя.
            is_staff (bool): Признак персонала админки.
            is_superuser (bool): Признак суперпользователя.
            password (str): Пароль.
            phone (str | None): Номер телефона; если не задан — сгенерируется автоматически.
            **extra (object): Доп. поля, будут переданы в create_user.

        Raises:
            ValueError: Если у модели обязателен телефон, но поле не найдено.
        """
        kwargs: dict[str, object] = {"email": email, **extra}

        # Если у модели есть поле телефона — заполняем.
        if phone_field:
            kwargs[phone_field] = phone or _next_ru_phone()
        else:
            # Если менеджер требует телефон, но поля мы не нашли — подскажем явно.
            # (На практике сюда не дойдём, т.к. get_field выше обнаружит нужное поле)
            if phone is not None:
                kwargs["phone"] = (
                    phone  # на случай, если менеджер принимает phone через **extra
                )
            # Иначе оставим как есть — если менеджер всё равно потребует, тест покажет точное поле.

        # Создаём обычного пользователя и затем поднимем флаги (надёжнее, чем вызывать create_superuser)
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
def admin_user(make_user) -> models.Model:
    """Администратор (superuser)."""
    return make_user("admin@example.com", is_staff=True, is_superuser=True)


@pytest.fixture
def regular_user(make_user) -> models.Model:
    """Обычный пользователь без спецправ."""
    return make_user("regular@example.com")


@pytest.fixture
def dept_manager_user(make_user) -> models.Model:
    """Пользователь, которому потом выдадим право manage_department_events."""
    return make_user("manager@example.com")


@pytest.fixture
def give_manage_calendar_perm(db) -> Callable[[DjangoModel, DjangoModel], None]:
    """Возвращает функцию, которая назначает пользователю ролевое право управления календарём в указанном отделе.

    Args:
        db: Стандартная фикстура pytest-django для доступа к БД.

    Returns:
        Callable[[DjangoModel, DjangoModel], None]: Функция-замыкание, принимающая (user, department).

    Raises:
        TypeError: Если переданы объекты не являются Django-моделями.
        ValueError: Если user или department не сохранены в БД (нет pk).
        IntegrityError: При ошибке записи в БД.
    """

    def _grant(user: DjangoModel, department: DjangoModel) -> None:
        """Назначает пользователю роль с правом DeptPerm.MANAGE_CALENDAR в указанном отделе.

        Args:
            user (DjangoModel): Сотрудник, которому выдаётся право (ваша модель пользователя/Employee).
            department (DjangoModel): Отдел, в котором выдаётся право.

        Raises:
            TypeError: Если объекты не наследуются от django.db.models.Model.
            ValueError: Если объекты не имеют первичных ключей.
            IntegrityError: Если нарушены ограничения БД при сохранении.
        """
        if not isinstance(user, DjangoModel) or not isinstance(department, DjangoModel):
            raise TypeError("Ожидаются экземпляры моделей Django (user и department).")
        if not getattr(user, "pk", None) or not getattr(department, "pk", None):
            raise ValueError("user и department должны быть предварительно сохранены (иметь pk).")

        # 1) Скоуп-пермишен отдела
        perm, _ = DepartmentPermission.objects.get_or_create(
            code=DeptPerm.MANAGE_CALENDAR,
            defaults={"name": "Управлять календарём отдела"},
        )

        # 2) Роль внутри отдела
        role, _ = DepartmentRole.objects.get_or_create(
            department=department,
            name="Manager",
        )
        role.scoped_permissions.add(perm)

        # 3) Привязка сотрудника к отделу с этой ролью
        EmployeeDepartment.objects.update_or_create(
            employee=user,
            department=department,
            defaults={"role": role, "is_active": True},
        )

    return _grant


@pytest.fixture
def api_client() -> APIClient:
    """Чистый DRF-клиент без авторизации."""
    return APIClient()


@pytest.fixture
def auth_client() -> Callable[[models.Model], APIClient]:
    """Создаёт авторизованный DRF-клиент.

    Args:
        user (models.Model): Пользователь.

    Returns:
        APIClient: Клиент с force_authenticate(user).
    """

    def _build(user: models.Model) -> APIClient:
        client = APIClient()
        client.force_authenticate(user=user)
        return client

    return _build


@pytest.fixture
def make_department(Department) -> Callable[..., models.Model]:
    """Фабрика отделов.

    Returns:
        Callable[..., models.Model]: Создатель отделов.

    Raises:
        pytest.SkipTest: Если модель Department отсутствует в проекте.
    """
    if Department is None:
        pytest.skip(
            "employees.Department отсутствует в проекте, отделные тесты будут пропущены."
        )

    def _make_dept(name: str = "Отдел R&D") -> models.Model:
        return Department.objects.create(name=name)  # type: ignore[attr-defined]

    return _make_dept


@pytest.fixture
def make_event(CalendarEvent, Recurrence) -> Callable[..., models.Model]:
    """Фабрика событий календаря.

    Args:
        CalendarEvent: Модель события.
        Recurrence: Enum повторяемости.

    Returns:
        Callable[..., models.Model]: Создатель событий с разумными дефолтами.
    """

    def _make(
        *,
        title: str = "Событие",
        department: Optional[models.Model] = None,
        start_date: date = date(2025, 1, 10),
        end_date: Optional[date] = None,
        start_time: Optional[time] = None,
        end_time: Optional[time] = None,
        all_day: bool = True,
        recurrence: str = "one_time",
        recurrence_interval: int = 1,
        weekdays_mask: Optional[int] = None,
        recurrence_until: Optional[date] = None,
        recurrence_count: Optional[int] = None,
        color: str = "",
        location: str = "",
    ) -> models.Model:
        obj = CalendarEvent.objects.create(
            title=title,
            department=department,
            start_date=start_date,
            end_date=end_date,
            start_time=start_time,
            end_time=end_time,
            all_day=all_day,
            recurrence=recurrence or Recurrence.ONE_TIME,  # type: ignore[attr-defined]
            recurrence_interval=recurrence_interval,
            weekdays_mask=weekdays_mask,
            recurrence_until=recurrence_until,
            recurrence_count=recurrence_count,
            color=color,
            location=location,
        )
        return obj

    return _make
