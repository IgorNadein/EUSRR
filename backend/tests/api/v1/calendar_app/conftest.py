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
def Calendar() -> Optional[Type[models.Model]]:
    """Модель календаря.

    Returns:
        Optional[Type[models.Model]]: calendar_app.Calendar или None, если нет.
    """
    try:
        return django_apps.get_model("calendar_app", "Calendar")
    except LookupError:
        return None


@pytest.fixture
def CalendarSubscription() -> Optional[Type[models.Model]]:
    """Модель подписки на календарь.

    Returns:
        Optional[Type[models.Model]]: calendar_app.CalendarSubscription или None.
    """
    try:
        return django_apps.get_model("calendar_app", "CalendarSubscription")
    except LookupError:
        return None


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
def give_manage_calendar_perm():
    """Выдаёт сотруднику право управления календарём отдела."""
    from employees.models import (DepartmentPermission, DepartmentRole,
                                  EmployeeDepartment)
    from employees.constants import DeptPerm

    def _grant(user: models.Model, department: models.Model) -> None:
        # Скоуп-пермишен отдела
        perm, _ = DepartmentPermission.objects.get_or_create(
            code=DeptPerm.MANAGE_CALENDAR,
            defaults={"name": "Управлять календарём отдела"},
        )

        # Роль внутри отдела
        role, _ = DepartmentRole.objects.get_or_create(
            department=department,
            name="Manager",
        )
        role.scoped_permissions.add(perm)

        # Привязка сотрудника к отделу с этой ролью
        EmployeeDepartment.objects.update_or_create(
            employee=user,
            department=department,
            defaults={"role": role, "is_active": True},
        )

    return _grant


@pytest.fixture
def make_calendar(Calendar, User) -> Callable[..., models.Model]:
    """Фабрика календарей.

    Returns:
        Callable[..., models.Model]: Создатель календарей.
    """
    if Calendar is None:
        pytest.skip("calendar_app.Calendar отсутствует в проекте")

    def _make(
        *,
        title: str = "Test Calendar",
        description: str = "",
        color: str = "#0d6efd",
        icon: str = "",
        owner_user: Optional[models.Model] = None,
        owner_department: Optional[models.Model] = None,
        visibility: str = "public",
        default_can_edit: bool = False,
        auto_subscribe_new_users: bool = False,
        auto_subscribe_department_members: bool = False,
        is_active: bool = True,
        created_by: Optional[models.Model] = None,
    ) -> models.Model:
        return Calendar.objects.create(
            title=title,
            description=description,
            color=color,
            icon=icon,
            owner_user=owner_user,
            owner_department=owner_department,
            visibility=visibility,
            default_can_edit=default_can_edit,
            auto_subscribe_new_users=auto_subscribe_new_users,
            auto_subscribe_department_members=auto_subscribe_department_members,
            is_active=is_active,
            created_by=created_by,
        )

    return _make


@pytest.fixture
def make_subscription(CalendarSubscription) -> Callable[..., models.Model]:
    """Фабрика подписок на календари.

    Returns:
        Callable[..., models.Model]: Создатель подписок.
    """
    if CalendarSubscription is None:
        pytest.skip("calendar_app.CalendarSubscription отсутствует в проекте")

    def _make(
        *,
        calendar: models.Model,
        user: models.Model,
        can_edit: bool = False,
        can_manage: bool = False,
        is_visible: bool = True,
        color_override: Optional[str] = None,
    ) -> models.Model:
        return CalendarSubscription.objects.create(
            calendar=calendar,
            user=user,
            can_edit=can_edit,
            can_manage=can_manage,
            is_visible=is_visible,
            color_override=color_override,
        )

    return _make


@pytest.fixture
def make_user(User) -> Callable[..., models.Model]:
    """Фабрика пользователей.

    Returns:
        Callable[..., models.Model]: Создатель пользователей.
    """

    def _make(
        *,
        username: str,
        email: Optional[str] = None,
        password: str = "testpass123",
        is_staff: bool = False,
        is_superuser: bool = False,
    ) -> models.Model:
        phone_field = _detect_phone_field(User)
        phone = _next_ru_phone() if phone_field else None
        
        user_data = {
            "username": username,
            "email": email or f"{username}@test.com",
            "is_staff": is_staff,
            "is_superuser": is_superuser,
        }
        
        if phone_field and phone:
            user_data[phone_field] = phone
        
        user = User.objects.create_user(**user_data)
        user.set_password(password)
        user.save()
        return user

    return _make


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
def regular_user(make_user) -> models.Model:
    """Обычный пользователь без спецправ."""
    return make_user(username="regular", email="regular@example.com")


@pytest.fixture
def admin_user(make_user) -> models.Model:
    """Пользователь с правами администратора."""
    return make_user(
        username="admin",
        email="admin@example.com",
        is_staff=True,
        is_superuser=True
    )


@pytest.fixture
def dept_manager_user(make_user) -> models.Model:
    """Пользователь - менеджер отдела."""
    return make_user(username="dept_manager", email="dept_manager@example.com")
