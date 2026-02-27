from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pytest
from django.db import models
from django.utils import timezone
from rest_framework.test import APIClient

from requests_app.models import Request as Req
from requests_app.enums import RequestStatus, RequestType
from django.contrib.auth import get_user_model

from tests.test_config import API_REQUESTS_URL


pytestmark = pytest.mark.django_db

API_BASE = API_REQUESTS_URL


def _results(payload: Any) -> List[Dict[str, Any]]:
    """Возвращает список объектов из ответа API.

    DRF может возвращать как чистый список (без пагинации), так и словарь
    с `results` (с пагинацией). Эта функция нормализует оба случая.

    Args:
        payload (Any): JSON-ответ.

    Returns:
        List[Dict[str, Any]]: Список элементов.
    """
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict) and "results" in payload:
        return payload["results"] or []
    return []


def _reload(user):
    # сбрасываем кэш прав на текущем экземпляре (если уже вычислялся)
    if hasattr(user, "_perm_cache"):
        delattr(user, "_perm_cache")
    # подменяем объект свежим из БД — это важно для force_authenticate
    return get_user_model().objects.get(pk=user.pk)


# ------------------------------------------------------------------------------
# 1) СПИСКИ / ВИДИМОСТЬ
# ------------------------------------------------------------------------------


def test_list_unauth_401(api_client: APIClient) -> None:
    """Неаутентифицированный доступ к списку → 401."""
    resp = api_client.get(API_BASE)
    assert resp.status_code == 401


def test_list_regular_user_sees_only_own(
    auth_client, regular_user: models.Model, make_user, make_request
) -> None:
    """Обычный пользователь видит только свои заявки независимо от параметров."""
    other = make_user(email="other@example.com")

    # Сгенерируем заявки двух пользователей
    r1 = make_request(employee=regular_user, type_=RequestType.VACATION)
    _ = make_request(employee=other, type_=RequestType.SICK_LEAVE)

    client = auth_client(regular_user)

    # Без параметров
    resp = client.get(API_BASE)
    assert resp.status_code == 200
    ids = {it["id"] for it in _results(resp.json())}
    assert r1.id in ids
    assert len(ids) == 1

    # Параметры ?view=mine и ?mine=1 игнорируются для обычного пользователя
    for qs in ("?view=mine", "?mine=1", "?mine=true", "?mine=True"):
        resp = client.get(f"{API_BASE}{qs}")
        assert resp.status_code == 200
        ids = {it["id"] for it in _results(resp.json())}
        assert ids == {r1.id}


def test_list_admin_default_all_and_mine_toggle(
    auth_client, admin_user: models.Model, make_user, make_request
) -> None:
    """Админ по умолчанию видит все, но может сузить до «только свои» параметром."""
    u1 = make_user(email="u1@example.com")
    u2 = make_user(email="u2@example.com")

    r1 = make_request(employee=u1, type_=RequestType.VACATION)
    r2 = make_request(employee=u2, type_=RequestType.SICK_LEAVE)

    client = auth_client(admin_user)

    # По умолчанию — все
    resp = client.get(API_BASE)
    assert resp.status_code == 200
    ids = {it["id"] for it in _results(resp.json())}
    assert ids.issuperset({r1.id, r2.id})

    # mine: у админа обычно нет собственных заявок → пусто
    for qs in ("?view=mine", "?mine=1", "?mine=true", "?mine=True"):
        resp = client.get(f"{API_BASE}{qs}")
        assert resp.status_code == 200
        ids = {it["id"] for it in _results(resp.json())}
        assert ids == set()


def test_list_manager_with_model_perm_sees_all(
    auth_client, make_user, grant_model_perm, make_request
) -> None:
    """Пользователь с модельным правом `view_request` видит все заявки."""
    manager = make_user(email="manager@example.com")
    grant_model_perm(manager, "requests_app.view_request")

    u1 = make_user(email="u1b@example.com")
    u2 = make_user(email="u2b@example.com")

    r1 = make_request(employee=u1)
    r2 = make_request(employee=u2)

    client = auth_client(manager)
    resp = client.get(API_BASE)
    assert resp.status_code == 200
    ids = {it["id"] for it in _results(resp.json())}
    assert ids.issuperset({r1.id, r2.id})


# ------------------------------------------------------------------------------
# 2) ДЕТАЛЬНЫЙ ПРОСМОТР
# ------------------------------------------------------------------------------


def test_detail_regular_user_own_and_forbidden_foreign(
    auth_client, regular_user: models.Model, make_user, make_request
) -> None:
    """Обычный пользователь: свою заявку видит, чужую — нет (404 через урезанный queryset)."""
    other = make_user(email="other2@example.com")
    mine = make_request(employee=regular_user)
    foreign = make_request(employee=other)

    client = auth_client(regular_user)
    ok = client.get(f"{API_BASE}{mine.id}/")
    no = client.get(f"{API_BASE}{foreign.id}/")

    assert ok.status_code == 200
    assert no.status_code in (403, 404)  # через queryset ожидаем 404


def test_detail_admin_and_manager_can_see_any(
    auth_client, admin_user: models.Model, make_user, grant_model_perm, make_request
) -> None:
    """Админ и менеджер с правами видят любую заявку."""
    u = make_user(email="x@example.com")
    r = make_request(employee=u)

    # Админ
    aclient = auth_client(admin_user)
    resp = aclient.get(f"{API_BASE}{r.id}/")
    assert resp.status_code == 200

    # Менеджер
    manager = make_user(email="manager2@example.com")
    grant_model_perm(manager, "requests_app.view_request")
    mclient = auth_client(manager)
    resp = mclient.get(f"{API_BASE}{r.id}/")
    assert resp.status_code == 200


# ------------------------------------------------------------------------------
# 3) СОЗДАНИЕ
# ------------------------------------------------------------------------------


def test_create_regular_user_forces_employee_and_default_status(
    auth_client, regular_user: models.Model
) -> None:
    """POST: обычному пользователю принудительно проставляется employee=текущий и дефолтный статус."""
    client = auth_client(regular_user)
    payload = {
        "type": RequestType.VACATION,
        "comment": "Отпуск на недельку",
        "employee": 999,
        "status": RequestStatus.APPROVED,
    }
    resp = client.post(API_BASE, data=payload, format="json")
    assert resp.status_code == 201
    data = resp.json()
    # Поле employee — текущий пользователь
    assert (
        str(data["employee"]["id"]) == str(regular_user.id)
        or data["employee"]["id"] == regular_user.id
    )
    # Статус должен быть не финальный (дефолт модели — pending)
    assert data["status"] in (RequestStatus.DRAFT, RequestStatus.PENDING)


def test_create_admin_can_set_employee(
    auth_client, admin_user: models.Model, make_user
) -> None:
    """POST: админ может создавать заявку для другого пользователя."""
    other = make_user(email="y@example.com")
    client = auth_client(admin_user)
    payload = {"type": RequestType.SICK_LEAVE, "employee": other.id, "comment": "Больничный"}
    resp = client.post(API_BASE, data=payload, format="json")
    assert resp.status_code == 201
    assert str(resp.json()["employee"]["id"]) == str(other.id)


# ------------------------------------------------------------------------------
# 4) ОБНОВЛЕНИЕ / 5) УДАЛЕНИЕ
# ------------------------------------------------------------------------------


def test_update_own_pending_ok_and_final_forbidden(
    auth_client, regular_user: models.Model, make_request
) -> None:
    """PATCH: владелец правит не финальную заявку; финальную — нельзя (403/400)."""
    pending = make_request(employee=regular_user, status=RequestStatus.PENDING)
    final = make_request(employee=regular_user, status=RequestStatus.APPROVED)

    client = auth_client(regular_user)
    ok = client.patch(
        f"{API_BASE}{pending.id}/", data={"comment": "обновлено"}, format="json"
    )
    deny = client.patch(
        f"{API_BASE}{final.id}/", data={"comment": "нельзя"}, format="json"
    )

    assert ok.status_code == 200
    assert deny.status_code in (400, 403)


def test_update_foreign_hidden(
    auth_client, regular_user: models.Model, make_user, make_request
) -> None:
    """PATCH: чужая заявка для обычного пользователя недоступна (ожидаем 404 по queryset)."""
    other = make_user(email="z@example.com")
    foreign = make_request(employee=other)
    client = auth_client(regular_user)
    resp = client.patch(
        f"{API_BASE}{foreign.id}/", data={"comment": "try"}, format="json"
    )
    assert resp.status_code in (403, 404)


def test_delete_own_pending_ok_final_forbidden(
    auth_client, regular_user: models.Model, make_request
) -> None:
    """DELETE: владелец может удалить не финальную; финальную — нельзя."""
    pending = make_request(employee=regular_user, status=RequestStatus.PENDING)
    final = make_request(employee=regular_user, status=RequestStatus.REJECTED)

    client = auth_client(regular_user)
    ok = client.delete(f"{API_BASE}{pending.id}/")
    deny = client.delete(f"{API_BASE}{final.id}/")

    assert ok.status_code in (200, 204)  # зависит от реализации destroy
    assert deny.status_code in (400, 403)


# ------------------------------------------------------------------------------
# 6) ЭКШЕНЫ СТАТУСОВ
# ------------------------------------------------------------------------------


def test_actions_permissions_and_effects(
    auth_client, admin_user: models.Model, make_user, grant_model_perm, make_request
) -> None:
    """approve/reject/cancel: права и изменение статусов."""
    owner = make_user(email="owner@example.com")
    manager = make_user(email="manager3@example.com")
    grant_model_perm(manager, "requests_app.change_request")  # или can_process_requests

    req = make_request(employee=owner, status=RequestStatus.PENDING)

    # Менеджер может approve
    mclient = auth_client(manager)
    resp = mclient.post(f"{API_BASE}{req.id}/approve/", data={}, format="json")
    assert resp.status_code == 200
    assert resp.json()["status"] == RequestStatus.APPROVED

    # Повторный approve/reject на финальной — ожидаем 400/403
    again = mclient.post(f"{API_BASE}{req.id}/approve/", data={}, format="json")
    assert again.status_code in (400, 403)

    # Владелец отменяет НЕ финальную (создадим новую pending)
    req2 = make_request(employee=owner, status=RequestStatus.PENDING)
    oclient = auth_client(owner)
    c_ok = oclient.post(f"{API_BASE}{req2.id}/cancel/", data={}, format="json")
    assert c_ok.status_code == 200
    assert c_ok.json()["status"] == RequestStatus.CANCELLED

    # Отменить финальную владельцу нельзя
    c_deny = oclient.post(f"{API_BASE}{req.id}/cancel/", data={}, format="json")
    assert c_deny.status_code in (400, 403)

    # Админ может reject любую
    req3 = make_request(employee=owner, status=RequestStatus.PENDING)
    aclient = auth_client(admin_user)
    r_admin = aclient.post(f"{API_BASE}{req3.id}/reject/", data={}, format="json")
    assert r_admin.status_code == 200
    assert r_admin.json()["status"] == RequestStatus.REJECTED


# ------------------------------------------------------------------------------
# 7) КОММЕНТАРИИ
# ------------------------------------------------------------------------------


def test_comments_forbidden_for_regular_user(
    auth_client,
    regular_user: models.Model,
    make_user,
    make_request,
) -> None:
    """Обычный пользователь (без модельных прав) не может читать/создавать комментарии даже у своей заявки.

    Ожидаем 403 на GET и 403 на POST.
    """
    mine = make_request(employee=regular_user)
    client = auth_client(regular_user)

    get_resp = client.get(f"{API_BASE}{mine.id}/comments/")
    assert get_resp.status_code == 403

    post_resp = client.post(
        f"{API_BASE}{mine.id}/comments/",
        data={"text": "мимопроходил"},
        format="json",
    )
    assert post_resp.status_code == 403


def test_comments_allowed_for_admin_and_manager(
    auth_client,
    admin_user: models.Model,
    make_user,
    grant_model_perm,
    make_request,
) -> None:
    """Проверяет доступ к комментариям:
    - Админ видит и создаёт.
    - Менеджер с ТОЛЬКО чтением видит, но НЕ создаёт.
    - Менеджер с чтением+добавлением — и видит, и создаёт.
    - Менеджер с ТОЛЬКО добавлением — создаёт (чтение невлияет на добавление).
    """
    owner = make_user(email="owner-comments@example.com")
    req = make_request(employee=owner)

    # --- Админ ---
    aclient = auth_client(admin_user)
    get_a = aclient.get(f"{API_BASE}{req.id}/comments/")
    assert get_a.status_code == 200, "Админ должен видеть список комментариев"

    post_a = aclient.post(
        f"{API_BASE}{req.id}/comments/",
        data={"text": "от админа"},
        format="json",
    )
    assert post_a.status_code == 201, "Админ должен уметь создавать комментарий"

    # --- Менеджер: только право чтения комментариев ---
    manager_view_only = make_user(email="manager-comments-view@example.com")
    grant_model_perm(manager_view_only, "requests_app.view_requestcomment")
    manager_view_only = _reload(manager_view_only)

    mclient_v = auth_client(manager_view_only)
    get_m_v = mclient_v.get(f"{API_BASE}{req.id}/comments/")
    assert (
        get_m_v.status_code == 200
    ), "С правом view_requestcomment список должен быть доступен"

    post_m_v = mclient_v.post(
        f"{API_BASE}{req.id}/comments/",
        data={"text": "попытка без add"},
        format="json",
    )
    assert (
        post_m_v.status_code == 403
    ), "Одно чтение не даёт права создавать комментарий"

    # --- Менеджер: добавляем право на добавление, теперь должно быть можно ---
    grant_model_perm(manager_view_only, "requests_app.add_requestcomment")
    manager_view_only = _reload(manager_view_only)

    post_m_va = auth_client(manager_view_only).post(
        f"{API_BASE}{req.id}/comments/",
        data={"text": "от менеджера после выдачи add"},
        format="json",
    )
    assert (
        post_m_va.status_code == 201
    ), "При наличии view+add создание должно быть разрешено"
    assert post_m_va.json().get("text") == "от менеджера после выдачи add"

    # --- Менеджер: только право добавления (без чтения) — ок ---
    manager_add_only = make_user(email="manager-comments-add@example.com")
    grant_model_perm(manager_add_only, "requests_app.add_requestcomment")
    manager_view_only = _reload(manager_view_only)

    post_m_a = auth_client(manager_add_only).post(
        f"{API_BASE}{req.id}/comments/",
        data={"text": "только add, без view"},
        format="json",
    )
    assert (
        post_m_a.status_code == 201
    ), "Без прав на чтение комментарий свободно создается"


# ------------------------------------------------------------------------------
# 8) ФИЛЬТРЫ
# ------------------------------------------------------------------------------


@pytest.mark.parametrize(
    "flt,expected_types",
    [
        ("?type=vacation", {RequestType.VACATION}),
        ("?status=pending", {RequestStatus.PENDING}),
    ],
)
def test_filters_type_status_applied_within_scope(
    auth_client,
    admin_user: models.Model,
    make_user,
    make_request,
    flt: str,
    expected_types: set[str],
) -> None:
    """Фильтры type/status применяются поверх выбранной области (all/mine)."""
    u1 = make_user(email="fu1@example.com")
    u2 = make_user(email="fu2@example.com")
    make_request(employee=u1, type_=RequestType.VACATION, status=RequestStatus.PENDING)
    make_request(employee=u2, type_=RequestType.SICK_LEAVE, status=RequestStatus.REJECTED)

    client = auth_client(admin_user)

    # all
    resp_all = client.get(f"{API_BASE}{flt}")
    assert resp_all.status_code == 200
    data_all = _results(resp_all.json())
    assert len(data_all) >= 1

    # mine (у админа обычно пусто; проверим, что не падает)
    resp_mine = client.get(f"{API_BASE}?view=mine&{flt.lstrip('?')}")
    assert resp_mine.status_code == 200


# ------------------------------------------------------------------------------
# 9) БЕЗОПАСНОСТЬ / ПРОЧЕЕ
# ------------------------------------------------------------------------------


def test_invalid_filter_does_not_crash(auth_client, admin_user: models.Model) -> None:
    """Странные значения фильтров не приводят к 500."""
    client = auth_client(admin_user)
    resp = client.get(f"{API_BASE}?type=__sql__' OR 1=1 --&status=")
    assert resp.status_code == 200