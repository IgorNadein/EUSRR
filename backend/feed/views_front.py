# backend/feed/views.py
from __future__ import annotations

from datetime import timedelta

from django import forms
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from api.client import ApiResponse, get_api_client
from .constants import TYPE_COMPANY, TYPE_DEPARTMENT, TYPE_EMPLOYEE
from .forms import CommentForm, PostForm

# ---------- Константы путей API ----------
API_POSTS = "v1/posts/"
API_COMMENTS = "v1/comments/"
API_DEPARTMENTS = "v1/departments/"
API_EMPLOYEES = "v1/employees/"


# ---------- Вспомогательное: доступ к ApiClient ----------
def _api(request):
    return get_api_client(request)


def _paged_or_list(resp: ApiResponse):
    data = resp.json or {}
    return data.get("results", data)


# ---------- Локальный multipart-враппер поверх ApiClient (без его модификации) ----------
def _api_request_multipart(
    client, method: str, path: str, *, data=None, files=None
) -> ApiResponse:
    """
    Отправляет multipart/form-data, используя ту же сессию и заголовки, что ApiClient.
    Делает ровно один refresh на 401.
    """
    url = client._make_url(
        path
    )  # noqa: SLF001 — осознанно пользуемся внутренними методами
    headers = dict(client.cfg.default_headers or {})
    headers.update(client._auth_headers())  # noqa: SLF001

    resp = client.session.request(
        method,
        url,
        data=data,
        files=files,
        headers=headers,
        timeout=client.cfg.timeout,
    )
    # 401 -> пробуем обновить access и повторить
    if resp.status_code == 401 and client.refresh and client.refresh_tokens():
        headers = dict(client.cfg.default_headers or {})
        headers.update(client._auth_headers())  # noqa: SLF001
        resp = client.session.request(
            method,
            url,
            data=data,
            files=files,
            headers=headers,
            timeout=client.cfg.timeout,
        )
    try:
        payload = resp.json()
    except Exception:
        payload = None
    return ApiResponse(
        ok=resp.ok, status=resp.status_code, json=payload, text=resp.text
    )


# ---------- Хелперы API для ленты ----------
def _api_list_posts(request, **params) -> list[dict]:
    resp = _api(request).get(API_POSTS, params=params)
    if not resp.ok:
        messages.error(request, f"Не удалось получить публикации: {resp.status}")
        return []
    return _paged_or_list(resp)


def _api_get_post(request, post_id: int) -> dict | None:
    resp = _api(request).get(f"{API_POSTS}{post_id}/")
    if not resp.ok:
        messages.error(request, f"Публикация недоступна: {resp.status}")
        return None
    return resp.json or None


def _api_get_comments_for_post(request, post_id: int) -> list[dict]:
    resp = _api(request).get(
        API_COMMENTS, params={"post": post_id, "ordering": "created_at"}
    )
    if not resp.ok:
        messages.error(request, f"Не удалось получить комментарии: {resp.status}")
        return []
    return _paged_or_list(resp)


def _api_get_department(request, dept_id: int) -> dict | None:
    resp = _api(request).get(f"{API_DEPARTMENTS}{dept_id}/")
    return resp.json if resp.ok else None


def _api_get_employee(request, employee_id: int) -> dict | None:
    resp = _api(request).get(f"{API_EMPLOYEES}{employee_id}/")
    return resp.json if resp.ok else None


def _api_list_department_members(request, dept_id: int) -> list[dict]:
    # Предпочтительно: /v1/employees/?department=<id>&is_active=true&ordering=last_name,first_name
    resp = _api(request).get(
        API_EMPLOYEES,
        params={
            "department": dept_id,
            "is_active": "true",
            "ordering": "last_name,first_name",
        },
    )
    return _paged_or_list(resp) if resp.ok else []


def _api_list_new_employees(request, limit: int = 10) -> list[dict]:
    since = (timezone.now() - timedelta(days=14)).isoformat()
    resp = _api(request).get(
        API_EMPLOYEES,
        params={
            "is_active": "true",
            "created_at__gte": since,  # или "created_at_after": since — см. ниже
            "ordering": "-created_at",
            "page_size": limit,
        },
    )
    return _paged_or_list(resp) if resp.ok else []


# ---------- Навигационные хелперы ----------
def _post_back_url(post: dict, user) -> str:
    t = post.get("type")
    if t == TYPE_COMPANY:
        return reverse("feed:feed_list")
    if t == TYPE_DEPARTMENT and post.get("department_id"):
        return reverse("employees:department_detail", args=[post["department_id"]])
    # страница пользователя — все его публикации
    author_id = post.get("author_id") or (
        user.pk if getattr(user, "is_authenticated", False) else None
    )
    return reverse("feed:employee_feed", args=[author_id or 0])


async def _can_edit_post_locally(user, post: dict) -> bool:
    # Мягкая проверка на стороне UI; фактическая авторизация — на API.
    if not (user and user.is_authenticated):
        return False
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    t = post.get("type")
    if t == TYPE_COMPANY:
        return False
    if t == TYPE_DEPARTMENT:
        dept_id = post.get("department_id")
        if dept_id:
            # проверим, не является ли юзер руководителем отдела
            # (берём минимальные данные отдела)
            # Если API возвращает в деталях отдела head_id — используем его.
            # Если нет — UI просто доверит решать бэкенду (можно упростить до False).
            return post.get("author_id") == user.id or bool(
                await _is_dept_head(user, dept_id)
            )
        return post.get("author_id") == user.id
    return post.get("author_id") == user.id


async def _is_dept_head(user, dept_id: int) -> bool:
    # Пытаемся определить head_id отдела через API
    # Если эндпоинт не даёт head_id, возвращаем False — API всё равно провалидирует право.
    # Для синхронных вьюх просто используем синхронный вызов:
    # (оставлено async для потенциальной асинхронной интеграции)
    from asgiref.sync import sync_to_async

    def _sync(request, d_id):
        dept = _api(
            request=None
        )  # не нужен request, но get_api_client требует — обойдём ниже; см. комментарий
        return False

    return False  # безопасное значение: разрешение решит API


# ---------- Ленты ----------


def feed_list(request):
    """
    Лента компании из API (?type=company).
    Блок «новые сотрудники» — тоже из API.
    """
    posts = _api_list_posts(request, type=TYPE_COMPANY)
    new_employees = _api_list_new_employees(request, limit=10)
    return render(
        request, "feed/feed_list.html", {"posts": posts, "new_employees": new_employees}
    )


@login_required
def department_feed(request, pk):
    department = _api_get_department(request, pk)
    if not department:
        messages.error(request, "Отдел недоступен.")
        return redirect("feed:feed_list")
    posts = _api_list_posts(request, type=TYPE_DEPARTMENT, department=pk)
    emp_links = _api_list_department_members(request, pk)
    return render(
        request,
        "feed/feed_list.html",
        {
            "department": department,
            "posts": posts,
            "new_employees": [],
            "emp_links": emp_links,
        },
    )


@login_required
def employee_feed(request, pk):
    employee = _api_get_employee(request, pk)
    if not employee:
        messages.error(request, "Сотрудник недоступен.")
        return redirect("feed:feed_list")
    posts = _api_list_posts(request, author=pk)
    return render(
        request, "feed/feed_list.html", {"employee": employee, "posts": posts}
    )


# ---------- Детальная + комментарии ----------


@login_required
def post_detail(request, pk):
    post = _api_get_post(request, pk)
    if not post:
        return redirect("feed:feed_list")

    comments = _api_get_comments_for_post(request, pk)

    if request.method == "POST":
        form = CommentForm(request.POST, request.FILES)
        if form.is_valid():
            cleaned = form.cleaned_data
            data = {
                "post": str(pk),
                "text": cleaned.get("text") or "",
            }
            files = {}
            if cleaned.get("image"):
                files["image"] = (
                    cleaned["image"].name,
                    cleaned["image"],
                    getattr(cleaned["image"], "content_type", None),
                )
            if cleaned.get("attachment"):
                files["attachment"] = (
                    cleaned["attachment"].name,
                    cleaned["attachment"],
                    getattr(cleaned["attachment"], "content_type", None),
                )

            client = _api(request)
            resp = _api_request_multipart(
                client, "POST", API_COMMENTS, data=data, files=files or None
            )
            if resp.ok:
                messages.success(request, "Комментарий добавлен!")
                next_url = request.POST.get("next")
                return (
                    redirect(next_url)
                    if next_url
                    else redirect("feed:post_detail", pk=pk)
                )
            # покажем ошибки API
            if isinstance(resp.json, dict):
                for field, errs in resp.json.items():
                    messages.error(request, f"{field}: {errs}")
            else:
                messages.error(request, f"Ошибка API: {resp.status}")
        else:
            messages.error(request, "Исправьте ошибки формы комментария.")
    else:
        form = CommentForm(initial={"post": pk})

    return render(
        request,
        "feed/post_detail.html",
        {"post": post, "comments": comments, "comment_form": form},
    )


@login_required
def comment_update(request, pk):
    r = _api(request).get(f"{API_COMMENTS}{pk}/")
    if not r.ok:
        messages.error(request, "Комментарий недоступен.")
        return redirect("feed:feed_list")
    comment = r.json or {}
    post_id = comment.get("post_id")

    if request.method == "POST":
        form = CommentForm(request.POST)  # шлём только text
        if form.is_valid():
            payload = {"text": form.cleaned_data.get("text") or ""}
            resp = _api(request).patch(f"{API_COMMENTS}{pk}/", json=payload)
            if resp.ok:
                messages.success(request, "Комментарий обновлён.")
                return redirect(f"{reverse('feed:post_detail', args=[post_id])}#c{pk}")
            messages.error(request, f"Ошибка API: {resp.status}")
        else:
            messages.error(request, "Исправьте ошибки формы.")
    else:
        form = CommentForm(initial={"text": comment.get("text", "")})

    # для шаблона нужен пост (dict)
    post = _api_get_post(request, post_id) if post_id else None
    return render(
        request,
        "feed/comment_form.html",
        {"form": form, "comment": comment, "post": post},
    )


@login_required
def comment_delete(request, pk):
    r = _api(request).get(f"{API_COMMENTS}{pk}/")
    if not r.ok:
        messages.error(request, "Комментарий недоступен.")
        return redirect("feed:feed_list")
    comment = r.json or {}
    post_id = comment.get("post_id")

    if request.method == "POST":
        resp = _api(request).delete(f"{API_COMMENTS}{pk}/")
        if resp.ok:
            messages.success(request, "Комментарий удалён.")
        else:
            messages.error(request, f"Ошибка удаления: {resp.status}")
        return redirect("feed:post_detail", pk=post_id)

    post = _api_get_post(request, post_id) if post_id else None
    return render(
        request, "feed/comment_confirm_delete.html", {"comment": comment, "post": post}
    )


# ---------- Создание/редактирование/удаление поста ----------


@login_required
def post_create(request):
    dept_id = request.GET.get("department")
    force_type = request.GET.get("type")

    # Определяем контекст (куда публикуем)
    if dept_id:
        context_type = TYPE_DEPARTMENT
    elif force_type in {TYPE_COMPANY, TYPE_EMPLOYEE}:
        context_type = force_type
    else:
        context_type = TYPE_COMPANY

    cancel_url = (
        request.GET.get("next")
        or (reverse("employees:department_detail", args=[dept_id]) if dept_id else None)
        or (
            reverse("feed:feed_list")
            if context_type == TYPE_COMPANY
            else reverse("feed:employee_feed", args=[request.user.pk])
        )
    )

    if request.method == "POST":
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            cleaned = form.cleaned_data
            data = {"title": cleaned.get("title"), "body": cleaned.get("body")}
            if context_type == TYPE_DEPARTMENT:
                data["type"] = TYPE_DEPARTMENT
                data["department"] = str(dept_id)
            elif context_type == TYPE_COMPANY:
                data["type"] = TYPE_COMPANY
            else:
                data["type"] = TYPE_EMPLOYEE  # API не допустит, это ок.

            files = {}
            if cleaned.get("image"):
                files["image"] = (
                    cleaned["image"].name,
                    cleaned["image"],
                    getattr(cleaned["image"], "content_type", None),
                )
            if cleaned.get("attachment"):
                files["attachment"] = (
                    cleaned["attachment"].name,
                    cleaned["attachment"],
                    getattr(cleaned["attachment"], "content_type", None),
                )

            client = _api(request)
            resp = _api_request_multipart(
                client, "POST", API_POSTS, data=data, files=files or None
            )
            if resp.ok:
                messages.success(request, "Публикация создана!")
                return redirect(_post_back_url(resp.json or {}, request.user))
            if isinstance(resp.json, dict):
                for field, errs in resp.json.items():
                    messages.error(request, f"{field}: {errs}")
            else:
                messages.error(request, f"Ошибка создания: {resp.status}")
        else:
            messages.error(request, "Исправьте ошибки формы.")
    else:
        initial = {}
        if context_type == TYPE_DEPARTMENT:
            initial.update({"type": TYPE_DEPARTMENT})
        elif context_type == TYPE_COMPANY:
            initial.update({"type": TYPE_COMPANY, "department": None})
        else:
            initial.update({"type": TYPE_EMPLOYEE})
        form = PostForm(initial=initial)
        # прячем лишние поля (визуально)
        if "type" in form.fields:
            form.fields["type"].initial = initial["type"]
            form.fields["type"].widget = forms.HiddenInput()
        if context_type == TYPE_DEPARTMENT and "department" in form.fields:
            form.fields["department"].initial = dept_id
            form.fields["department"].widget = forms.HiddenInput()
        else:
            form.fields.pop("department", None)

    return render(
        request,
        "feed/post_form.html",
        {
            "form": form,
            "context_type": context_type,
            "department": {"id": dept_id} if dept_id else None,
            "cancel_url": cancel_url,
        },
    )


@login_required
def post_update(request, pk):
    post = _api_get_post(request, pk)
    if not post:
        return redirect("feed:feed_list")

    # UI-проверка — бэкенд всё равно решит правами
    # (синхронно считаем, см. примечание к _can_edit_post_locally)
    # Можно просто пропустить этот шаг, положившись на 403 от API.
    # if not sync_can_edit: messages.error(...)

    cancel_url = request.GET.get("next") or _post_back_url(post, request.user)

    if request.method == "POST":
        form = PostForm(request.POST, request.FILES)
        if form.is_valid():
            cleaned = form.cleaned_data
            data = {"title": cleaned.get("title"), "body": cleaned.get("body")}
            files = {}
            if cleaned.get("image"):
                files["image"] = (
                    cleaned["image"].name,
                    cleaned["image"],
                    getattr(cleaned["image"], "content_type", None),
                )
            if cleaned.get("attachment"):
                files["attachment"] = (
                    cleaned["attachment"].name,
                    cleaned["attachment"],
                    getattr(cleaned["attachment"], "content_type", None),
                )
            client = _api(request)
            resp = _api_request_multipart(
                client, "PATCH", f"{API_POSTS}{pk}/", data=data, files=files or None
            )
            if resp.ok:
                messages.success(request, "Публикация обновлена!")
                return redirect(_post_back_url(post, request.user))
            if isinstance(resp.json, dict):
                for field, errs in resp.json.items():
                    messages.error(request, f"{field}: {errs}")
            else:
                messages.error(request, f"Ошибка обновления: {resp.status}")
        else:
            messages.error(request, "Исправьте ошибки формы.")
    else:
        form = PostForm(
            initial={
                "type": post.get("type"),
                "title": post.get("title"),
                "body": post.get("body"),
                "department": post.get("department_id"),
            }
        )
        if "type" in form.fields:
            form.fields["type"].widget = forms.HiddenInput()
        if "department" in form.fields:
            form.fields["department"].widget = forms.HiddenInput()

    context_type = post.get("type")
    department = (
        {"id": post.get("department_id")}
        if (context_type == TYPE_DEPARTMENT and post.get("department_id"))
        else None
    )
    return render(
        request,
        "feed/post_form.html",
        {
            "form": form,
            "context_type": context_type,
            "department": department,
            "cancel_url": cancel_url,
        },
    )


@login_required
def post_delete(request, pk):
    post = _api_get_post(request, pk)
    if not post:
        return redirect("feed:feed_list")

    cancel_url = request.GET.get("next") or _post_back_url(post, request.user)

    if request.method == "POST":
        resp = _api(request).delete(f"{API_POSTS}{pk}/")
        if resp.ok:
            messages.success(request, "Публикация удалена.")
            return redirect(_post_back_url(post, request.user))
        messages.error(request, f"Ошибка удаления: {resp.status}")

    return render(
        request,
        "feed/post_confirm_delete.html",
        {"post": post, "cancel_url": cancel_url},
    )


@login_required
def pin_post(request, pk):
    post = _api_get_post(request, pk)
    if not post:
        return redirect("feed:feed_list")
    action = "unpin" if post.get("pinned") else "pin"
    resp = _api(request).post(f"{API_POSTS}{pk}/{action}/")
    if resp.ok:
        messages.success(
            request, "Новость закреплена!" if action == "pin" else "Новость откреплена!"
        )
    else:
        messages.error(request, f"Операция недоступна: {resp.status}")
    return redirect(_post_back_url(post, request.user))


# ---------- Лайки ----------


@login_required
def toggle_like(request, pk):
    if request.method != "POST":
        return redirect("feed:post_detail", pk=pk)

    op = (request.POST.get("op") or "like").lower()
    if op not in {"like", "unlike"}:
        op = "like"

    endpoint = "like" if op == "like" else "unlike"
    resp = _api(request).post(f"{API_POSTS}{pk}/{endpoint}/")

    if not resp.ok:
        messages.error(request, f"Не удалось {op} публикацию: {resp.status}")

    wants_json = (
        "application/json" in request.headers.get("Accept", "")
        or request.headers.get("X-Requested-With") == "XMLHttpRequest"
    )
    if wants_json:
        data = resp.json or {}
        return JsonResponse(
            {
                "ok": bool(resp.ok),
                "post_id": pk,
                "liked": data.get("liked"),
                "likes": data.get("likes_count"),
            }
        )

    next_url = (
        request.POST.get("next")
        or request.META.get("HTTP_REFERER")
        or reverse("feed:post_detail", args=[pk])
    )
    return HttpResponseRedirect(next_url)
