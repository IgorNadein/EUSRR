from __future__ import annotations

from typing import Any, Mapping, Optional

from django.contrib import messages
from django.http import (
    HttpRequest,
    HttpResponse,
    HttpResponseBadRequest,
    HttpResponseForbidden,
)
from django.shortcuts import redirect, render
from django.urls import reverse

from api.client import get_api_client  # ваш клиент
from api.decorators import require_api_auth  # проверка наличия токена в сессии


API_PATH = "v1/requests/"  # относительный путь внутри API (base_url настраивается в settings)


# ===================== Списки =====================

@require_api_auth
def my_requests(request: HttpRequest) -> HttpResponse:
    """Список «моих» заявок через GET /api/v1/requests/?view=mine.

    Returns:
        HttpResponse: HTML со списком заявок.

    Raises:
        RuntimeError: В случае неожиданных ошибок клиента API (маловероятно).
    """
    api = get_api_client(request)
    params = {"view": "mine", **request.GET.dict()}
    resp = api.get(API_PATH, params=params)

    if resp.status == 401:
        messages.info(request, "Войдите заново.")
        return redirect(reverse("auth_front:login"))

    if resp.ok:
        return render(request, "requests_app/my_requests.html", {"items": resp.json or []})

    if resp.status == 403:
        return HttpResponseForbidden("Нет прав на просмотр ваших заявок.")

    messages.error(request, f"Ошибка API: {resp.status}")
    return render(request, "requests_app/my_requests.html", {"items": [], "error": resp.text})


@require_api_auth
def all_requests(request: HttpRequest) -> HttpResponse:
    """Список всех заявок через GET /api/v1/requests/.

    Query-параметры проксируются как есть (?type=...&status=...).

    Returns:
        HttpResponse: HTML со списком заявок.

    Raises:
        RuntimeError: В случае неожиданных ошибок клиента API.
    """
    api = get_api_client(request)
    resp = api.get(API_PATH, params=request.GET.dict())

    if resp.status == 401:
        messages.info(request, "Войдите заново.")
        return redirect(reverse("auth_front:login"))

    if resp.ok:
        return render(request, "requests_app/all_requests.html", {"items": resp.json or []})

    if resp.status == 403:
        return HttpResponseForbidden("Недостаточно прав для просмотра заявок.")

    messages.error(request, f"Ошибка API: {resp.status}")
    return render(request, "requests_app/all_requests.html", {"items": [], "error": resp.text})


# ===================== Создание/детали =====================

@require_api_auth
def request_create(request: HttpRequest) -> HttpResponse:
    """Создание заявки через POST /api/v1/requests/.

    GET: вывести форму.
    POST: отправить поля формы в API. Для обычного пользователя API игнорирует `employee/status`
          и выставляет автора/статус автоматически.

    Returns:
        HttpResponse: Редирект на детальную страницу при успехе или HTML формы с ошибками.

    Raises:
        ValueError: Если передан неподдерживаемый метод.
    """
    if request.method == "GET":
        return render(request, "requests_app/request_form.html")

    if request.method != "POST":
        return HttpResponseBadRequest("Метод не поддерживается.")

    api = get_api_client(request)

    # Соберите безопасный набор полей (минимум, совпадающий с API write-сериализатором)
    payload: dict[str, Any] = {
        "type": request.POST.get("type"),
        "title": request.POST.get("title") or "",
        "date_from": request.POST.get("date_from") or None,
        "date_to": request.POST.get("date_to") or None,
        "comment": request.POST.get("comment") or "",
    }

    # Если есть файл — используем form-data, иначе JSON.
    if upload := request.FILES.get("attachment"):
        files = {"attachment": (upload.name, upload.file, upload.content_type)}
        resp = api.post(API_PATH, data=payload, files=files)
    else:
        resp = api.post(API_PATH, json=payload)

    if resp.status == 401:
        messages.info(request, "Войдите заново.")
        return redirect(reverse("auth_front:login"))

    if resp.status == 201 and isinstance(resp.json, dict):
        messages.success(request, "Заявка создана.")
        return redirect("requests_app:request_detail", pk=resp.json["id"])

    if resp.status in (400, 403):
        # Пытаемся показать ошибки валидатора
        form_errors: Mapping[str, Any] = resp.json if isinstance(resp.json, dict) else {"__all__": resp.text}
        return render(
            request,
            "requests_app/request_form.html",
            {"form_errors": form_errors, "form_data": payload},
        )

    messages.error(request, f"Ошибка API: {resp.status}")
    return render(
        request,
        "requests_app/request_form.html",
        {"form_errors": {"__all__": resp.text or "Неизвестная ошибка"}},
    )


@require_api_auth
def request_detail(request: HttpRequest, pk: int) -> HttpResponse:
    """Детальная страница заявки (GET /api/v1/requests/{pk}/) + попытка подтянуть комментарии.

    Args:
        pk (int): Идентификатор заявки.

    Returns:
        HttpResponse: HTML с деталями заявки.

    Raises:
        RuntimeError: В случае неожиданных ошибок клиента API.
    """
    api = get_api_client(request)

    # Основной объект заявки
    item_resp = api.get(f"{API_PATH}{pk}/")
    if item_resp.status == 401:
        messages.info(request, "Войдите заново.")
        return redirect(reverse("auth_front:login"))

    if item_resp.status == 404:
        return render(request, "requests_app/request_detail.html", {"item": None, "error": "Заявка не найдена."})
    if item_resp.status == 403:
        return HttpResponseForbidden("Недостаточно прав для просмотра заявки.")
    if not item_resp.ok:
        messages.error(request, f"Ошибка API: {item_resp.status}")
        return render(request, "requests_app/request_detail.html", {"item": None, "error": item_resp.text})

    # Комментарии (если доступ есть)
    comments: list[dict[str, Any]] = []
    comm_resp = api.get(f"{API_PATH}{pk}/comments/")
    if comm_resp.ok and isinstance(comm_resp.json, list):
        comments = comm_resp.json

    return render(
        request,
        "requests_app/request_detail.html",
        {"item": item_resp.json, "comments": comments},
    )


# ===================== Обработка статусов =====================

@require_api_auth
def request_process(request: HttpRequest, pk: int) -> HttpResponse:
    """Обработка заявки через POST /api/v1/requests/{pk}/(approve|reject)/.

    Ожидает в POST параметр 'action' со значением 'approve' или 'reject'.

    Args:
        pk (int): Идентификатор заявки.

    Returns:
        HttpResponse: Редирект на детальную страницу.

    Raises:
        ValueError: Если action неизвестен.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("Только POST.")

    action = (request.POST.get("action") or "").strip().lower()
    if action not in {"approve", "reject"}:
        raise ValueError("action должен быть 'approve' или 'reject'.")

    api = get_api_client(request)
    resp = api.post(f"{API_PATH}{pk}/{action}/")

    if resp.status == 401:
        messages.info(request, "Войдите заново.")
        return redirect(reverse("auth_front:login"))

    if resp.ok:
        messages.success(request, f"Действие '{action}' выполнено.")
    elif resp.status in (400, 403):
        messages.error(request, f"Не удалось выполнить '{action}': {resp.json or resp.text}")
    else:
        messages.error(request, f"Ошибка API ({resp.status}) при '{action}'.")
    return redirect("requests_app:request_detail", pk=pk)


@require_api_auth
def request_cancel(request: HttpRequest, pk: int) -> HttpResponse:
    """Отмена заявки через POST /api/v1/requests/{pk}/cancel/.

    Args:
        pk (int): Идентификатор заявки.

    Returns:
        HttpResponse: Редирект на детальную страницу.

    Raises:
        RuntimeError: В случае неожиданных ошибок клиента API.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("Только POST.")

    api = get_api_client(request)
    resp = api.post(f"{API_PATH}{pk}/cancel/")

    if resp.status == 401:
        messages.info(request, "Войдите заново.")
        return redirect(reverse("auth_front:login"))

    if resp.ok:
        messages.success(request, "Заявка отменена.")
    elif resp.status in (400, 403):
        messages.error(request, f"Не удалось отменить: {resp.json or resp.text}")
    else:
        messages.error(request, f"Ошибка API ({resp.status}) при отмене.")
    return redirect("requests_app:request_detail", pk=pk)


# ===================== Комментарии =====================

@require_api_auth
def request_comment_add(request: HttpRequest, pk: int) -> HttpResponse:
    """Добавление комментария через POST /api/v1/requests/{pk}/comments/.

    Тело: {"text": "..."}.

    Args:
        pk (int): Идентификатор заявки.

    Returns:
        HttpResponse: Редирект на детальную страницу заявки.

    Raises:
        ValueError: Если метод не POST или текст пустой.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("Только POST.")

    text = (request.POST.get("text") or "").strip()
    if not text:
        messages.error(request, "Текст комментария не может быть пустым.")
        return redirect("requests_app:request_detail", pk=pk)

    api = get_api_client(request)
    resp = api.post(f"{API_PATH}{pk}/comments/", json={"text": text})

    if resp.status == 401:
        messages.info(request, "Войдите заново.")
        return redirect(reverse("auth_front:login"))

    if resp.status == 201:
        messages.success(request, "Комментарий добавлен.")
    elif resp.status == 403:
        messages.error(request, "Нет прав для добавления комментариев.")
    elif resp.status == 400:
        messages.error(request, f"Ошибка валидации: {resp.json or resp.text}")
    else:
        messages.error(request, f"Ошибка API ({resp.status}) при добавлении комментария.")
    return redirect("requests_app:request_detail", pk=pk)


@require_api_auth
def request_comment_delete(request: HttpRequest, pk: int, comment_id: int) -> HttpResponse:
    """Удаление комментария.

    Пытается вызвать DELETE в одном из известных эндпоинтов.
    Сначала: /api/v1/requests/{pk}/comments/{comment_id}/
    Затем:   /api/v1/comments/{comment_id}/ (если первый путь не поддерживается).

    Args:
        pk (int): Идентификатор заявки.
        comment_id (int): Идентификатор комментария.

    Returns:
        HttpResponse: Редирект на детальную страницу заявки.

    Raises:
        ValueError: Если метод не POST.
    """
    if request.method != "POST":
        return HttpResponseBadRequest("Только POST.")

    api = get_api_client(request)

    # Вариант 1: nested под заявкой
    resp = api.delete(f"{API_PATH}{pk}/comments/{comment_id}/")
    if resp.status == 401:
        messages.info(request, "Войдите заново.")
        return redirect(reverse("auth_front:login"))

    if resp.status in (200, 204):
        messages.success(request, "Комментарий удалён.")
        return redirect("requests_app:request_detail", pk=pk)

    # Вариант 2: общий ресурс комментариев
    if resp.status == 404:
        resp2 = api.delete(f"v1/comments/{comment_id}/")
        if resp2.status in (200, 204):
            messages.success(request, "Комментарий удалён.")
            return redirect("requests_app:request_detail", pk=pk)
        if resp2.status == 403:
            return HttpResponseForbidden("Нет прав на удаление комментария.")
        messages.error(request, f"Не удалось удалить комментарий: {resp2.status}")
        return redirect("requests_app:request_detail", pk=pk)

    if resp.status == 403:
        return HttpResponseForbidden("Нет прав на удаление комментария.")
    messages.error(request, f"Не удалось удалить комментарий: {resp.status}")
    return redirect("requests_app:request_detail", pk=pk)
