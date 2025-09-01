# backend/employees/views_front.py

from __future__ import annotations

import json
import base64
import mimetypes
from typing import Any

from api.client import get_api_client
from api.decorators import require_api_auth
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views.decorators.http import require_http_methods
from django.views.generic import CreateView, DeleteView, ListView, UpdateView
from django.views.decorators.http import require_POST
from django.http import JsonResponse

from .forms import (
    DepartmentEditForm,
    DepartmentForm,
    DepartmentMemberRoleForm,
    InviteToDepartmentForm,
    SkillForm,
)
from .forms_front import DepartmentEditForm, SetHeadForm, SetMemberRoleForm
from .models import Department, EmployeeDepartment, Skill


# =========================
#   Утилиты
# =========================


def _file_to_data_uri(uploaded) -> str:
    """
    Превращаем загруженный файл (InMemoryUploadedFile/TemporaryUploadedFile)
    в data URI (data:image/...;base64,xxxx).
    """
    if not uploaded:
        return ""
    content = uploaded.read()
    if hasattr(uploaded, "seek"):
        uploaded.seek(0)
    mime = (
        getattr(uploaded, "content_type", None)
        or mimetypes.guess_type(getattr(uploaded, "name", ""))[0]
        or "application/octet-stream"
    )
    b64 = base64.b64encode(content).decode("ascii")
    return f"data:{mime};base64,{b64}"


def _extract_items(payload: Any):
    """
    Универсальный парсер: пагинированный ответ DRF или «сырой» список.
    """
    if isinstance(payload, dict) and "results" in payload:
        return (
            payload["results"],
            payload.get("count", 0),
            payload.get("next"),
            payload.get("previous"),
        )
    if isinstance(payload, list):
        return payload, len(payload), None, None
    return [], 0, None, None


def _cleanup_payload(data: dict, keep_empty: set[str] = frozenset()) -> dict:
    """
    Убираем None и пустые строки, КРОМЕ ключей из keep_empty.
    """
    cleaned = {}
    for k, v in data.items():
        if v is None:
            continue
        if v == "" and k not in keep_empty:
            continue
        cleaned[k] = v
    return cleaned


def _extract_results(payload):
    if isinstance(payload, dict):
        return payload.get("results", payload.get("items", [])) or []
    return payload or []


def _fetch_employee_posts(api, employee_id: int):
    # сначала пробуем ?author=, если в API другое имя фильтра — fallback на ?employee=
    for url in (
        f"v1/posts/?author={employee_id}&ordering=-created_at",
        f"v1/posts/?employee={employee_id}&ordering=-created_at",
    ):
        r = api.get(url)
        if r.ok:
            data = r.json or []
            return _extract_results(data)


# =========================
#   Сотрудники
# =========================


# ---------- LIST ----------
@require_api_auth
def employee_list(request):
    """
    Список сотрудников.
    Ходит в /api/v1/employees/ c поддержкой поиска/сортировки/пагинации.
    """
    api = get_api_client(request)

    page = request.GET.get("page") or 1
    ordering = request.GET.get("o") or "last_name"
    q = (request.GET.get("q") or "").strip()
    department = request.GET.get(
        "department"
    )  # опциональный фильтр по отделу (из detail отдела)

    params = {"page": page, "ordering": ordering}
    if q:
        params["search"] = q
    if department:
        params["department"] = department

    resp = api.get("v1/employees/", params=params)
    if not resp.ok:
        messages.error(request, f"Ошибка API ({resp.status})")
        return render(
            request,
            "employees/employees_list.html",
            {"employees": [], "q": q, "o": ordering, "page": page},
        )

    payload = resp.json or {}
    items, count, next_url, prev_url = _extract_items(payload)
    context = {
        "employees": items,
        "count": count,
        "q": q,
        "o": ordering,
        "page": page,
        "next_url": next_url,
        "prev_url": prev_url,
    }
    return render(request, "employees/employees_list.html", context)


# ---------- DETAIL / ME ----------
@require_api_auth
def employee_profile(request, pk="me"):
    """
    /employees/me/  и  /employees/<int:pk>/
    Если pk == текущему пользователю — редиректим на /employees/me/
    """
    # --- редирект "свой id" -> /me ---
    try:
        int_pk = int(pk)
    except (TypeError, ValueError):
        int_pk = None

    if (
        int_pk is not None
        and request.user.is_authenticated
        and request.user.id == int_pk
    ):
        url = reverse("employees:profile")
        qs = request.META.get("QUERY_STRING")
        if qs:  # сохраняем ?tab=skills и т.п.
            url = f"{url}?{qs}"
        return redirect(url)  # 302 достаточно, чтобы не кэшировать навсегда

    # --- обычная логика detail/me ---
    api = get_api_client(request)
    is_me = str(pk) in {"me", "self"}

    endpoint = "v1/employees/me/" if is_me else f"v1/employees/{pk}/"
    resp = api.get(endpoint)
    if not resp.ok:
        messages.error(request, f"Сотрудник не найден ({resp.status})")
        return redirect("employees:employees_list")

    emp = resp.json or {}
    emp_id = emp.get("id") or (request.user.id if is_me else pk)
    posts = _fetch_employee_posts(api, emp_id)

    sresp = api.get("v1/skills/", params={"ordering": "name"})
    sdata = sresp.json if sresp.ok else []
    all_skills = sdata.get("results", sdata) if isinstance(sdata, dict) else sdata
    gresp = None
    for path in ("v1/auth/groups/", "v1/groups/"):
        r = api.get(path, params={"ordering": "name"})
        if r.ok:
            gresp = r
            break
    gdata = gresp.json if gresp and gresp.ok else []
    all_groups = gdata.get("results", gdata) if isinstance(gdata, dict) else gdata
    presp = api.get("v1/positions/", params={"ordering": "name"})
    pdata = presp.json if presp.ok else []
    all_positions = pdata.get("results", pdata) if isinstance(pdata, dict) else pdata

    can_edit = (
        True
        if is_me
        else bool(
            request.user and (request.user.is_staff or request.user.id == emp.get("id"))
        )
    )
    ctx = {
        "emp": emp,
        "can_edit": can_edit,
        "all_skills": all_skills,
        "all_positions": all_positions,
        "all_groups": all_groups,
        "posts": posts,
    }
    if is_me:
        ctx["is_me"] = True

    return render(request, "employees/employee_detail.html", ctx)


# ---------- EDIT (self or staff) ----------
@require_api_auth
@require_http_methods(["PATCH", "POST"])
def employee_edit(request, pk: int):
    """
    Редактирование пользователя по id.
    """
    api = get_api_client(request)
    try:
        payload = json.loads(request.body or b"{}")
    except Exception:
        payload = {}
    resp = api.patch(f"v1/employees/{pk}/", json=payload)
    try:
        data = resp.json
    except Exception:
        data = {"detail": resp.text}
    return JsonResponse(data or {}, status=resp.status)


# ---------- EDIT ME ----------
@require_api_auth
@require_http_methods(["PATCH", "POST"])
def employee_edit_me(request):
    """
    Редактирование собственного профиля через /api/v1/employees/me/
    """
    api = get_api_client(request)
    # принимаем JSON из браузера
    try:
        payload = json.loads(request.body or b"{}")
    except Exception:
        payload = {}
    # отправляем в DRF
    resp = api.patch("v1/employees/me/", json=payload)
    try:
        data = resp.json
    except Exception:
        data = {"detail": resp.text}
    return JsonResponse(data or {}, status=resp.status)


# ---------- CREATE (staff) ----------
@require_api_auth
@require_http_methods(["GET", "POST"])
def employee_create(request):
    api = get_api_client(request)

    if request.method == "GET":
        return render(request, "employees/employee_create.html")

    data = {
        "email": request.POST.get("email", "").strip(),
        "phone_number": request.POST.get("phone_number", "").strip(),
        "last_name": request.POST.get("last_name", "").strip(),
        "first_name": request.POST.get("first_name", "").strip(),
        "patronymic": request.POST.get("patronymic", "").strip(),
        "gender": request.POST.get("gender") or None,
        "birth_date": request.POST.get("birth_date") or None,
        "position": request.POST.get("position") or None,
        "telegram": request.POST.get("telegram", "").strip(),
        "whatsapp": request.POST.get("whatsapp", "").strip(),
        "wechat": request.POST.get("wechat", "").strip(),
    }
    if request.FILES.get("avatar"):
        data["avatar"] = _file_to_data_uri(request.FILES["avatar"])
    skills = request.POST.getlist("skills")
    if skills:
        data["skills"] = skills
    password = request.POST.get("password", "").strip()
    if password:
        data["password"] = password  # API сгенерирует сам, если не передали

    resp = api.post("v1/employees/", json=data)
    if not resp.ok:
        messages.error(request, f"Не удалось создать: {resp.status} — {resp.text}")
        return render(request, "employees/employee_create.html", {"form": request.POST})

    new_emp = resp.json or {}
    messages.success(request, "Сотрудник создан.")
    return redirect("employees:employee_detail", pk=new_emp.get("id"))


# =========================
#   Отделы
# =========================


# ---------- LIST ----------
@require_api_auth
def department_list(request):
    """
    Список отделов.
    Ходит в /api/v1/departments/ c поддержкой поиска/сортировки/пагинации DRF.
    """
    api = get_api_client(request)

    page = request.GET.get("page") or 1
    ordering = request.GET.get("o") or "name"
    q = (request.GET.get("q") or "").strip()

    params = {"page": page, "ordering": ordering}
    if q:
        params["search"] = q  # DRF SearchFilter

    resp = api.get("v1/departments/", params=params)
    if not resp.ok:
        messages.error(request, f"Ошибка API ({resp.status})")
        return render(
            request,
            "employees/department_list.html",
            {
                "departments": [],
                "count": 0,
                "q": q,
                "o": ordering,
                "page": page,
                "next_url": None,
                "prev_url": None,
            },
        )

    payload = resp.json  # важно: без "or {}" — иначе потеряем список

    # ✅ поддерживаем оба формата DRF: dict с results или list без пагинации
    if isinstance(payload, dict) and "results" in payload:
        items = payload["results"]
        count = payload.get("count", len(items))
        next_url = payload.get("next")
        prev_url = payload.get("previous")
    elif isinstance(payload, list):
        items = payload
        count = len(items)
        next_url = prev_url = None
    else:
        items = []
        count = 0
        next_url = prev_url = None

    context = {
        "departments": items,
        "count": count,
        "q": q,
        "o": ordering,
        "page": page,
        "next_url": next_url,
        "prev_url": prev_url,
    }
    return render(request, "employees/department_list.html", context)


# ---------- DETAIL ----------
@require_api_auth
def department_detail(request, pk: int):
    """
    Детальная страница отдела.
    Тянет:
      - /api/v1/departments/{id}/
      - /api/v1/department-roles/?department={id}
      - /api/v1/employee-departments/?department={id}&is_active=true
    """
    api = get_api_client(request)

    dep = api.get(f"v1/departments/{pk}/")
    if not dep.ok:
        messages.error(
            request,
            "Отдел не найден" if dep.status == 404 else f"Ошибка API ({dep.status})",
        )
        return redirect("employees:dept_list")
    dept = dep.json

    roles_resp = api.get(
        "v1/department-roles/", params={"department": pk, "page_size": 1000}
    )
    roles = (
        roles_resp.json.get("results", [])
        if roles_resp.ok and isinstance(roles_resp.json, dict)
        else roles_resp.json or []
    )

    links_resp = api.get(
        "v1/employee-departments/",
        params={"department": pk, "is_active": True, "page_size": 1000},
    )
    links = (
        links_resp.json.get("results", [])
        if links_resp.ok and isinstance(links_resp.json, dict)
        else links_resp.json or []
    )

    context = {
        "dept": dept,
        "roles": roles,
        "links": links,  # элементы вида {"employee": <id>, "role": <id>|null, ...}
        "edit_form": DepartmentEditForm(
            initial={
                "name": dept.get("name", ""),
                "description": dept.get("description", ""),
            }
        ),
        "set_head_form": SetHeadForm(),
        "set_member_role_form": SetMemberRoleForm(),
    }
    page = request.GET.get("page") or 1
    r = api.get(
        "v1/feed/posts/",
        params={"department": pk, "page": page, "ordering": "-created_at"},
    )
    posts = []
    if r.ok:
        data = r.json
        posts = data.get("results", data) if isinstance(data, dict) else data

    context.update(
        {
            "posts": posts,
            "page": page,  # если пагинация нужна в шаблоне
        }
    )
    return render(request, "employees/department_detail.html", context)


# ---------- EDIT BASIC FIELDS ----------
@require_api_auth
@require_http_methods(["POST"])
def department_edit(request, pk: int):
    """
    Редактирование name/description через PATCH /api/v1/departments/{id}/.
    Права проверяет API (manage_department).
    """
    api = get_api_client(request)
    form = DepartmentEditForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Проверьте форму")
        return redirect("employees:dept_detail", pk=pk)

    payload = {
        "name": form.cleaned_data["name"],
        "description": form.cleaned_data.get("description") or "",
    }
    resp = api.patch(f"v1/departments/{pk}/", json=payload)
    if not resp.ok:
        messages.error(
            request,
            f"Не удалось обновить отдел ({resp.status}) — {resp.json or resp.text}",
        )
    else:
        messages.success(request, "Отдел обновлён")
    return redirect("employees:dept_detail", pk=pk)


# ---------- SET HEAD ----------
@require_api_auth
@require_http_methods(["POST"])
def department_set_head(request, pk: int):
    """
    Назначение/снятие руководителя через POST /api/v1/departments/{id}/set_head/.
    Права проверяет API (change_department_head).
    """
    api = get_api_client(request)
    form = SetHeadForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Проверьте форму")
        return redirect("employees:dept_detail", pk=pk)

    head_id = form.cleaned_data.get("head_id", None)
    payload = {"head_id": head_id if head_id is not None else None}  # None → снять
    resp = api.post(f"v1/departments/{pk}/set_head/", json=payload)
    if not resp.ok:
        messages.error(
            request,
            f"Не удалось изменить руководителя ({resp.status}) — {resp.json or resp.text}",
        )
    else:
        messages.success(
            request, "Руководитель обновлён" if head_id else "Руководитель снят"
        )
    return redirect("employees:dept_detail", pk=pk)


# ---------- SET MEMBER ROLE ----------
@require_api_auth
@require_http_methods(["POST"])
def department_set_member_role(request, pk: int):
    """
    Назначение/снятие роли участнику отдела через POST /api/v1/departments/{id}/set_member_role/.
    Права проверяет API (assign_department_role).
    """
    api = get_api_client(request)
    form = SetMemberRoleForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Проверьте форму")
        return redirect("employees:dept_detail", pk=pk)

    payload = {
        "employee_id": form.cleaned_data["employee_id"],
        "role_id": form.cleaned_data.get("role_id", None),
        "is_active": form.cleaned_data.get("is_active", None),
    }
    resp = api.post(f"v1/departments/{pk}/set_member_role/", json=payload)
    if not resp.ok:
        messages.error(
            request,
            f"Не удалось обновить роль ({resp.status}) — {resp.json or resp.text}",
        )
    else:
        messages.success(request, "Роль участника обновлена")
    return redirect("employees:dept_detail", pk=pk)


class StaffOnlyMixin(UserPassesTestMixin):
    def test_func(self):
        return self.request.user.is_staff

    def handle_no_permission(self):
        messages.error(self.request, "Недостаточно прав.")
        return redirect("employees:department_list")


class DepartmentCreateView(LoginRequiredMixin, StaffOnlyMixin, CreateView):
    model = Department
    form_class = DepartmentForm
    template_name = "employees/department_form.html"
    success_url = reverse_lazy("employees:department_list")


class DepartmentUpdateView(LoginRequiredMixin, StaffOnlyMixin, UpdateView):
    model = Department
    form_class = DepartmentForm
    template_name = "employees/department_form.html"
    success_url = reverse_lazy("employees:department_list")


class DepartmentDeleteView(LoginRequiredMixin, StaffOnlyMixin, DeleteView):
    model = Department
    template_name = "employees/department_confirm_delete.html"
    success_url = reverse_lazy("employees:department_list")


@login_required
def edit_department_role(request, dept_id, employee_id):
    department = get_object_or_404(Department, pk=dept_id)

    # только staff или руководитель отдела
    if not (request.user.is_staff or department.head_id == request.user.id):
        messages.error(request, "Нет прав изменять роли в этом отделе.")
        return redirect("employees:employees_list")

    link = get_object_or_404(
        EmployeeDepartment,
        department=department,
        employee_id=employee_id,
    )

    if request.method == "POST":
        form = DepartmentMemberRoleForm(request.POST, instance=link)
        if form.is_valid():
            form.save()
            messages.success(request, "Роль в отделе обновлена.")
            next_url = request.POST.get("next") or (
                reverse("employees:employees_list") + f"?department={dept_id}"
            )
            return redirect(next_url)
    else:
        form = DepartmentMemberRoleForm(instance=link)

    employee = link.employee
    next_url = request.GET.get("next") or (
        reverse("employees:employees_list") + f"?department={dept_id}"
    )
    return render(
        request,
        "employees/department_role_form.html",
        {
            "department": department,
            "employee": employee,
            "form": form,
            "next_url": next_url,
        },
    )


# ---------- Приглашение в отдел ----------


@login_required
def invite_to_department(request, pk):
    department = get_object_or_404(Department, pk=pk)

    if not (request.user.is_staff or request.user == department.head):
        messages.error(request, "Нет прав приглашать сотрудников.")
        return redirect("employees:department_detail", pk=pk)

    if request.method == "POST":
        form = InviteToDepartmentForm(department, request.POST)
        if form.is_valid():
            employee = form.cleaned_data["employee"]

            emp_dep, created = EmployeeDepartment.objects.get_or_create(
                employee=employee,
                department=department,
                defaults={"is_active": True, "date_from": timezone.now().date()},
            )
            if not created and not emp_dep.is_active:
                emp_dep.is_active = True
                emp_dep.date_from = timezone.now().date()
                emp_dep.date_to = None
                emp_dep.save()

            messages.success(request, f"{employee.get_full_name()} приглашён в отдел!")
            return redirect("employees:department_detail", pk=pk)
    else:
        form = InviteToDepartmentForm(department)
        if not form.fields["employee"].queryset.exists():
            messages.info(
                request,
                "Нет сотрудников, которых можно пригласить — похоже, все уже в отделе.",
            )

    return render(
        request,
        "employees/invite_to_department.html",
        {"form": form, "department": department},
    )


# =========================
#   Навыки
# =========================


@login_required
@require_POST
@require_api_auth
def skill_add(request, pk: int):
    api = get_api_client(request)
    skill_id = request.POST.get("skill_id")
    skill_name = (request.POST.get("skill_name") or "").strip()
    payload = {
        k: v for k, v in (("skill_id", skill_id), ("skill_name", skill_name)) if v
    }
    resp = api.post(f"v1/employees/{pk}/add_skill/", data=payload)
    return JsonResponse(resp.json or {"detail": resp.text}, status=resp.status or 500)


@login_required
@require_POST
@require_api_auth
def skill_remove(request, pk: int):
    api = get_api_client(request)
    skill_id = request.POST.get("skill_id")
    skill_name = (request.POST.get("skill_name") or "").strip()
    payload = {
        k: v for k, v in (("skill_id", skill_id), ("skill_name", skill_name)) if v
    }
    # NB: у DRF-экшена underscore: remove_skill
    resp = api.post(f"v1/employees/{pk}/remove_skill/", data=payload)
    return JsonResponse(resp.json or {"detail": resp.text}, status=resp.status or 500)
