from __future__ import annotations

from typing import Any, Dict, List, Tuple

import pytest
from django.db import models
from django.utils import timezone
from rest_framework.test import APIClient

from requests_app.models import Request as Req


pytestmark = pytest.mark.django_db

API_BASE = "/api/v1/requests/"


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
            final_statuses = {getattr(Req, "STATUS_APPROVED", "approved"),
                              getattr(Req, "STATUS_REJECTED", "rejected")}
            if status in final_statuses:
                obj.approver = approver or employee  # в тестах допустимо
                # Опционально поставим время решения, если модель его использует
                if hasattr(obj, "decided_at") and not obj.decided_at:
                    from django.utils import timezone
                    obj.decided_at = timezone.now()

            obj.save()

        return obj

    return _make



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
    r1 = make_request(employee=regular_user, type_=Req.TYPE_VACATION)
    _ = make_request(employee=other, type_=Req.TYPE_SICK)

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

    r1 = make_request(employee=u1, type_=Req.TYPE_VACATION)
    r2 = make_request(employee=u2, type_=Req.TYPE_SICK)

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
    payload = {"type": Req.TYPE_VACATION, "comment": "Отпуск на недельку", "employee": 999, "status": Req.STATUS_APPROVED}
    resp = client.post(API_BASE, data=payload, format="json")
    assert resp.status_code == 201
    data = resp.json()
    # Поле employee — текущий пользователь
    assert str(data["employee"]["id"]) == str(regular_user.id) or data["employee"]["id"] == regular_user.id
    # Статус должен быть не финальный (дефолт модели — pending)
    assert data["status"] in (Req.STATUS_DRAFT, Req.STATUS_PENDING)


def test_create_admin_can_set_employee(
    auth_client, admin_user: models.Model, make_user
) -> None:
    """POST: админ может создавать заявку для другого пользователя."""
    other = make_user(email="y@example.com")
    client = auth_client(admin_user)
    payload = {"type": Req.TYPE_SICK, "employee": other.id, "comment": "Больничный"}
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
    pending = make_request(employee=regular_user, status=Req.STATUS_PENDING)
    final = make_request(employee=regular_user, status=Req.STATUS_APPROVED)

    client = auth_client(regular_user)
    ok = client.patch(f"{API_BASE}{pending.id}/", data={"comment": "обновлено"}, format="json")
    deny = client.patch(f"{API_BASE}{final.id}/", data={"comment": "нельзя"}, format="json")

    assert ok.status_code == 200
    assert deny.status_code in (400, 403)


def test_update_foreign_hidden(
    auth_client, regular_user: models.Model, make_user, make_request
) -> None:
    """PATCH: чужая заявка для обычного пользователя недоступна (ожидаем 404 по queryset)."""
    other = make_user(email="z@example.com")
    foreign = make_request(employee=other)
    client = auth_client(regular_user)
    resp = client.patch(f"{API_BASE}{foreign.id}/", data={"comment": "try"}, format="json")
    assert resp.status_code in (403, 404)


def test_delete_own_pending_ok_final_forbidden(
    auth_client, regular_user: models.Model, make_request
) -> None:
    """DELETE: владелец может удалить не финальную; финальную — нельзя."""
    pending = make_request(employee=regular_user, status=Req.STATUS_PENDING)
    final = make_request(employee=regular_user, status=Req.STATUS_REJECTED)

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

    req = make_request(employee=owner, status=Req.STATUS_PENDING)

    # Менеджер может approve
    mclient = auth_client(manager)
    resp = mclient.post(f"{API_BASE}{req.id}/approve/", data={}, format="json")
    assert resp.status_code == 200
    assert resp.json()["status"] == Req.STATUS_APPROVED

    # Повторный approve/reject на финальной — ожидаем 400/403
    again = mclient.post(f"{API_BASE}{req.id}/approve/", data={}, format="json")
    assert again.status_code in (400, 403)

    # Владелец отменяет НЕ финальную (создадим новую pending)
    req2 = make_request(employee=owner, status=Req.STATUS_PENDING)
    oclient = auth_client(owner)
    c_ok = oclient.post(f"{API_BASE}{req2.id}/cancel/", data={}, format="json")
    assert c_ok.status_code == 200
    assert c_ok.json()["status"] == Req.STATUS_CANCELLED

    # Отменить финальную владельцу нельзя
    c_deny = oclient.post(f"{API_BASE}{req.id}/cancel/", data={}, format="json")
    assert c_deny.status_code in (400, 403)

    # Админ может reject любую
    req3 = make_request(employee=owner, status=Req.STATUS_PENDING)
    aclient = auth_client(admin_user)
    r_admin = aclient.post(f"{API_BASE}{req3.id}/reject/", data={}, format="json")
    assert r_admin.status_code == 200
    assert r_admin.json()["status"] == Req.STATUS_REJECTED


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
    """Админ и пользователь с модельными правами могут видеть и оставлять комментарии.

    Проверяем оба актёра:
      - admin (is_staff=True)
      - manager с правом просмотра/изменения заявок.
    """
    owner = make_user(email="owner-comments@example.com")
    req = make_request(employee=owner)

    # Админ
    aclient = auth_client(admin_user)
    get_a = aclient.get(f"{API_BASE}{req.id}/comments/")
    assert get_a.status_code == 200, "Админ должен видеть список комментариев"

    post_a = aclient.post(
        f"{API_BASE}{req.id}/comments/",
        data={"text": "от админа"},
        format="json",
    )
    assert post_a.status_code == 201, "Админ должен уметь создавать комментарий"

    # Менеджер с модельными правами
    manager = make_user(email="manager-comments@example.com")
    grant_model_perm(manager, "requests_app.view_requestcomment")
    grant_model_perm(manager, "requests_app.add_requestcomment") 


    mclient = auth_client(manager)
    get_m = mclient.get(f"{API_BASE}{req.id}/comments/")

    assert get_m.status_code == 200, "Пользователь с правами должен видеть список"
    data = get_m.json()
    assert isinstance(data, list)

    post_m = mclient.post(
        f"{API_BASE}{req.id}/comments/",
        data={"text": "от менеджера"},
        format="json",
    )
    assert post_m.status_code == 201, "Пользователь с правами должен создавать комментарии"
    body = post_m.json()
    assert body.get("text") == "от менеджера"

# ------------------------------------------------------------------------------
# 8) ФИЛЬТРЫ
# ------------------------------------------------------------------------------

@pytest.mark.parametrize(
    "flt,expected_types",
    [
        ("?type=vacation", {Req.TYPE_VACATION}),
        ("?status=pending", {Req.STATUS_PENDING}),
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
    make_request(employee=u1, type_=Req.TYPE_VACATION, status=Req.STATUS_PENDING)
    make_request(employee=u2, type_=Req.TYPE_SICK, status=Req.STATUS_REJECTED)

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

def test_invalid_filter_does_not_crash(
    auth_client, admin_user: models.Model
) -> None:
    """Странные значения фильтров не приводят к 500."""
    client = auth_client(admin_user)
    resp = client.get(f"{API_BASE}?type=__sql__' OR 1=1 --&status=")
    assert resp.status_code == 200
