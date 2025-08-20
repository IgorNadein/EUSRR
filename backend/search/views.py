from typing import Dict, Any, List
from django.contrib.auth.decorators import login_required
from django.db.models import Q, QuerySet
from django.shortcuts import render
from django.utils.html import escape

# Модели
from feed.models import Post  # подставьте актуальный путь
from employees.models import Employee
from requests_app.models import Request

# ====== ВСПОМОГАТЕЛЬНО: доступ к заявлениям ======


def _is_hr(user) -> bool:
    # считаем HR по группе/правам как вы уже настроили
    return user.is_active and (
        user.groups.filter(name="HR").exists()
        or user.has_perm("requests_app.can_view_all_requests")
        or user.has_perm("requests_app.can_process_requests")
    )


def _is_head(user) -> bool:
    # есть related_name=headed_departments в Employee
    return user.headed_departments.exists()


def _allowed_requests_qs(user) -> QuerySet[Request]:
    base = Request.objects.select_related("employee", "department", "approver")
    if _is_hr(user):
        return base
    if _is_head(user):
        return base.filter(
            employee__departments_links__department__head=user,
            employee__departments_links__is_active=True,
        ).distinct()
    return base.filter(employee=user)


# ====== ПОИСК ======


@login_required
def search_view(request):
    q = (request.GET.get("q") or "").strip()
    query = q[:100]  # ограничим длину для безопасности

    results: Dict[str, List[Any]] = {"posts": [], "employees": [], "requests": []}
    counts: Dict[str, int] = {"posts": 0, "employees": 0, "requests": 0}

    if query:
        # --- Посты (новости)
        posts_qs = Post.objects.all()
        posts_qs = (
            posts_qs.filter(Q(title__icontains=query) | Q(body__icontains=query))
            .only("id", "title")
            .order_by("-id")
        )
        counts["posts"] = posts_qs.count()
        results["posts"] = list(posts_qs[:10])

        # --- Сотрудники
        emp_qs = Employee.objects.all()
        emp_qs = (
            emp_qs.filter(
                Q(first_name__icontains=query)
                | Q(last_name__icontains=query)
                | Q(patronymic__icontains=query)
                | Q(email__icontains=query)
                | Q(phone_number__icontains=query)
            )
            .only("id", "first_name", "last_name", "patronymic", "email")
            .order_by("last_name", "first_name")
        )
        counts["employees"] = emp_qs.count()
        results["employees"] = list(emp_qs[:10])

        # --- Заявления (с учётом прав)
        req_qs = _allowed_requests_qs(request.user)
        req_qs = (
            req_qs.filter(
                Q(title__icontains=query)
                | Q(comment__icontains=query)
                | Q(employee__first_name__icontains=query)
                | Q(employee__last_name__icontains=query)
            )
            .only("id", "title", "status", "employee", "department", "created_at")
            .order_by("-created_at")
        )
        counts["requests"] = req_qs.count()
        results["requests"] = list(req_qs[:10])

    # Пустой запрос — просто страница с формой/подсказкой
    ctx = {
        "query": query,
        "results": results,
        "counts": counts,
    }
    return render(request, "search/results.html", ctx)
