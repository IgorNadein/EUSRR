# backend/employees/views_front.py

from __future__ import annotations

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
from django.utils.http import urlencode
from django.views.decorators.http import require_http_methods
from django.views.generic import CreateView, DeleteView, ListView, UpdateView

from .forms import (DepartmentEditForm, DepartmentForm,
                    DepartmentMemberRoleForm,
                    InviteToDepartmentForm, SkillForm)
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


# ---------- DETAIL ----------
@require_api_auth
def employee_detail(request, pk: int):
    api = get_api_client(request)
    resp = api.get(f"v1/employees/{pk}/")
    if not resp.ok:
        messages.error(request, f"Сотрудник не найден ({resp.status})")
        return redirect("employees:employees_list")

    emp = resp.json or {}
    can_edit = bool(
        request.user and (request.user.is_staff or request.user.id == emp.get("id"))
    )
    return render(
        request, "employees/employee_detail.html", {"emp": emp, "can_edit": can_edit}
    )


# ---------- ME ----------
@require_api_auth
def employee_me(request):
    api = get_api_client(request)
    resp = api.get("v1/employees/me/")
    if not resp.ok:
        messages.error(request, f"Ошибка API ({resp.status})")
        return redirect("employees:employees_list")
    emp = resp.json or {}
    return render(
        request, "employees/employee_detail.html", {"emp": emp, "can_edit": True}
    )


# ---------- EDIT (self or staff) ----------
@require_api_auth
@require_http_methods(["GET", "POST"])
def employee_edit(request, pk: int):
    """
    Редактирование пользователя по id.
    Разрешено staff/superuser или самому себе (проверку делает API).
    """
    api = get_api_client(request)

    if request.method == "GET":
        resp = api.get(f"v1/employees/{pk}/")
        if not resp.ok:
            messages.error(request, f"Сотрудник не найден ({resp.status})")
            return redirect("employees:employees_list")
        emp = resp.json or {}
        return render(request, "employees/employee_edit.html", {"emp": emp})

    # POST → PATCH
    data = {
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

    # skills (множественный select): skills=1&skills=2 …
    skills = request.POST.getlist("skills")
    if skills:
        data["skills"] = skills

    # avatar: либо новый файл, либо снять (clear_avatar=on)
    if request.FILES.get("avatar"):
        data["avatar"] = _file_to_data_uri(request.FILES["avatar"])
    elif request.POST.get("clear_avatar") == "on":
        data["avatar"] = ""  # Base64ImageField очистит

    # удаляем пустые строки, чтобы не перетирать nullables
    data = _cleanup_payload(data, keep_empty={"avatar"})

    resp = api.patch(f"v1/employees/{pk}/", json=data)
    if not resp.ok:
        messages.error(request, f"Не удалось сохранить: {resp.status} — {resp.text}")
        # Подставим обратно форму с введёнными данными
        current = api.get(f"v1/employees/{pk}/").json or {}
        current.update(
            {k: request.POST.get(k) for k in ["last_name", "first_name", "patronymic"]}
        )
        return render(request, "employees/employee_edit.html", {"emp": current})

    messages.success(request, "Профиль обновлён.")
    return redirect("employees:employee_detail", pk=pk)


# ---------- EDIT ME ----------
@require_api_auth
@require_http_methods(["GET", "POST"])
def employee_edit_me(request):
    """
    Редактирование собственного профиля через /api/v1/employees/me/
    """
    api = get_api_client(request)

    if request.method == "GET":
        resp = api.get("v1/employees/me/")
        if not resp.ok:
            messages.error(request, f"Ошибка API ({resp.status})")
            return redirect("employees:employees_list")
        emp = resp.json or {}
        return render(
            request, "employees/employee_edit.html", {"emp": emp, "is_me": True}
        )

    data = {
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
    skills = request.POST.getlist("skills")
    if skills:
        data["skills"] = skills

    if request.FILES.get("avatar"):
        data["avatar"] = _file_to_data_uri(request.FILES["avatar"])
    elif request.POST.get("clear_avatar") == "on":
        data["avatar"] = ""

    data = _cleanup_payload(data, keep_empty={"avatar"})

    resp = api.patch("v1/employees/me/", json=data)
    if not resp.ok:
        messages.error(request, f"Не удалось сохранить: {resp.status} — {resp.text}")
        current = api.get("v1/employees/me/").json or {}
        current.update(
            {k: request.POST.get(k) for k in ["last_name", "first_name", "patronymic"]}
        )
        return render(
            request, "employees/employee_edit.html", {"emp": current, "is_me": True}
        )

    messages.success(request, "Профиль обновлён.")
    return redirect("employees:employee_me")


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


# =========================
#   Приглашение в отдел
# =========================
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
#   Универсальный CRUD для Absence, Skill
# =========================
class BaseCRUDListView(LoginRequiredMixin, ListView):
    """Базовый ListView: если у модели есть FK employee — показываем только свои записи."""

    def get_queryset(self):
        qs = super().get_queryset()
        has_employee_fk = any(f.name == "employee" for f in self.model._meta.fields)
        if has_employee_fk:
            return qs.filter(employee=self.request.user)
        return qs


class BaseCRUDCreateView(LoginRequiredMixin, CreateView):
    def form_valid(self, form):
        has_employee_fk = any(f.name == "employee" for f in self.model._meta.fields)
        if has_employee_fk:
            form.instance.employee = self.request.user
        return super().form_valid(form)


class BaseCRUDUpdateView(LoginRequiredMixin, UpdateView):
    pass


class BaseCRUDDeleteView(LoginRequiredMixin, DeleteView):
    pass


# Skill CRUD (через базовые вьюхи, чтобы ограничить видимость своими записями)
class SkillListView(BaseCRUDListView):
    model = Skill
    template_name = "employees/skill_list.html"
    context_object_name = "skills"


class SkillCreateView(BaseCRUDCreateView):
    model = Skill
    form_class = SkillForm
    template_name = "employees/skill_form.html"
    success_url = reverse_lazy("employees:skill_list")


class SkillUpdateView(BaseCRUDUpdateView):
    model = Skill
    form_class = SkillForm
    template_name = "employees/skill_form.html"
    success_url = reverse_lazy("employees:skill_list")


class SkillDeleteView(BaseCRUDDeleteView):
    model = Skill
    template_name = "employees/skill_confirm_delete.html"
    success_url = reverse_lazy("employees:skill_list")
