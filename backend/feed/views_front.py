# backend/feed/views.py
from __future__ import annotations

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponseRedirect, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils import timezone

from api.client import ApiResponse, get_api_client
from .constants import TYPE_COMPANY, TYPE_DEPARTMENT
from .forms import CommentForm

# ---------- Константы путей API ----------
API_POSTS = "v1/posts/"
API_COMMENTS = "v1/comments/"
API_DEPARTMENTS = "v1/departments/"
API_EMPLOYEES = "v1/employees/"


# ---------- Вспомогательное: доступ к ApiClient ----------
def _api(request):
    return get_api_client(request)


def _paged_or_list(resp: ApiResponse):
    """Извлекает results из пагинированного ответа или возвращает сырой список."""
    data = resp.json or {}
    return data.get("results", data)


def _extract_page_data(resp: ApiResponse):
    """Извлекает данные пагинации из ответа API.
    
    Returns:
        tuple: (items, count, next_url, prev_url)
    """
    data = resp.json or {}
    if isinstance(data, dict) and "results" in data:
        return (
            data["results"],
            data.get("count", 0),
            data.get("next"),
            data.get("previous"),
        )
    return data if isinstance(data, list) else [], 0, None, None


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
    """Получить новых сотрудников через API"""
    since = (timezone.now() - timedelta(days=14)).isoformat()
    resp = _api(request).get(
        API_EMPLOYEES,
        params={
            "active": "true",
            "created_at__gte": since,
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


# ---------- Ленты ----------


def feed_list(request):
    """
    Лента компании - посты загружаются через API на клиенте.
    Блок «новые сотрудники» загружается с сервера.
    """
    # Загружаем только новых сотрудников с сервера
    new_employees = _api_list_new_employees(request, limit=10)
    
    return render(
        request,
        "feed/feed_list.html",
        {
            "new_employees": new_employees,
        },
    )


@login_required
def department_feed(request, pk):
    """Лента отдела"""
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
    """Лента сотрудника"""
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
    """Рендерит детальную страницу поста с комментариями. CRUD через API в JavaScript."""
    post = _api_get_post(request, pk)
    if not post:
        return redirect("feed:feed_list")

    comments = _api_get_comments_for_post(request, pk)
    form = CommentForm(initial={"post": pk})

    return render(
        request,
        "feed/post_detail.html",
        {"post": post, "comments": comments, "comment_form": form},
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
