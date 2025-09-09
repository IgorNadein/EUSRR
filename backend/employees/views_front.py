# backend/employees/views_front.py

from __future__ import annotations

import base64
import json
import mimetypes
from typing import Any, Dict, Tuple

from api.client import get_api_client
from api.decorators import require_api_auth
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_http_methods, require_POST


from .forms_front import DepartmentEditForm, SetHeadForm


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


def _fetch_department_posts(api, department_id: int) -> list[dict]:
    """Возвращает публикации отдела (type=department), отсортированные по пину и дате.

    Args:
        api: Инициализированный API-клиент (get_api_client(request)).
        department_id (int): ID отдела.

    Returns:
        list[dict]: Список публикаций для шаблона.

    Raises:
        RuntimeError: Если ответ API не JSON (редко, мы перехватываем безопасно).
        ValueError: Если department_id некорректный (не int).
    """
    # Пробуем явный фильтр по типу и отделу; fallback — только department
    for url in (
        f"v1/posts/?type=department&department={int(department_id)}&ordering=-pinned,-created_at",
        f"v1/posts/?department={int(department_id)}&ordering=-pinned,-created_at",
    ):
        r = api.get(url)
        if r.ok:
            data = r.json or []
            return _extract_results(data)
    return []


def _json_body(request: HttpRequest) -> Dict[str, Any]:
    """Безопасно парсим JSON; если не JSON — возвращаем пустой dict."""
    try:
        if request.body:
            return json.loads(request.body.decode("utf-8"))
    except Exception:
        pass
    return {}


def _error(message: str, status: int = 400) -> JsonResponse:
    return JsonResponse({"detail": message}, status=status)


def _ok(data: Dict[str, Any], status: int = 200) -> JsonResponse:
    return JsonResponse(data, status=status)


def _api_ok_or_error(resp) -> Tuple[bool, Dict[str, Any], int]:
    """Унифицированная распаковка ответа API."""
    try:
        data = resp.json or {}
    except Exception:
        data = {}
    return resp.ok, data, getattr(resp, "status", 500)


# =========================
#   Сотрудники
# =========================


# ---------- LIST ----------
@require_api_auth
def employee_list(request):
    """
    Список сотрудников.
    Если ?format=json — вернуть JSON (для автокомплита):
      /employees/list/?format=json&q=...&exclude=1,2,3&limit=12
    """
    api = get_api_client(request)

    page = request.GET.get("page") or 1
    ordering = request.GET.get("o") or "last_name"
    q = (request.GET.get("q") or "").strip()
    department = request.GET.get("department")

    params = {"page": page, "ordering": ordering}
    if q:
        params["search"] = q
    if department:
        params["department"] = department

    resp = api.get("v1/employees/", params=params)
    if not resp.ok:
        if request.GET.get("format") == "json":
            return JsonResponse({"results": [], "count": 0}, status=resp.status or 500)
        messages.error(request, f"Ошибка API ({resp.status})")
        return render(
            request,
            "employees/employees_list.html",
            {"employees": [], "q": q, "o": ordering, "page": page},
        )

    payload = resp.json or {}
    items, count, next_url, prev_url = _extract_items(payload)

    # JSON-ветка для автокомплита
    if request.GET.get("format") == "json":
        # exclude: "1,2,3"
        raw_ex = (request.GET.get("exclude") or "").strip()
        try:
            ex_ids = {int(x) for x in raw_ex.split(",") if x.strip().isdigit()}
        except Exception:
            ex_ids = set()

        try:
            limit = int(request.GET.get("limit") or 12)
        except Exception:
            limit = 12

        # отфильтруем и обрежем на стороне фронт-прокси
        def _id(e):
            try:
                return int(e.get("id"))
            except Exception:
                return -1

        items = [e for e in items if _id(e) not in ex_ids][:limit]
        return JsonResponse({"results": items, "count": len(items)})

    # HTML-ветка (как было)
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
    for path in ("v1/groups/",):
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
    emp_depts = []
    for d in emp.get("departments") or []:
        did = d.get("id")
        if not did:
            emp_depts.append(d)
            continue

        # узнаём head отдела
        dresp = api.get(f"v1/departments/{did}/")
        head_id = None
        if dresp.ok:
            dj = dresp.json or {}
            head = dj.get("head") or {}
            head_id = head.get("id") or dj.get("head_id")

        # подгружаем роли отдела
        rresp = api.get(
            "v1/department-roles/", params={"department": did, "ordering": "name"}
        )
        roles = []
        if rresp.ok:
            rj = rresp.json
            roles = (rj.get("results", rj) if isinstance(rj, dict) else rj) or []

        can_edit_role = (
            bool(head_id)
            and str(head_id) == str(getattr(request.user, "id", None))
            and not d.get("is_head")  # нельзя править главу
            and str(emp_id) != str(getattr(request.user, "id", None))  # не себе
        )

        d2 = dict(d)
        d2.update(
            {
                "roles_choices": roles,  # [{id, name, ...}]
                "can_edit_role": can_edit_role,  # bool
            }
        )
        emp_depts.append(d2)

    can_edit = (
        True
        if is_me
        else bool(
            request.user and (request.user.is_staff or request.user.id == emp.get("id"))
        )
    )

    ctx = {
        "emp": emp,
        "emp_depts": emp_depts,
        "can_edit": can_edit,
        "all_skills": all_skills,
        "all_positions": all_positions,
        "all_groups": all_groups,
        "posts": posts,
        "is_me": True if is_me else False,
    }
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
    Страница отдела.

    Тонкая фронт-вьюха: забирает агрегированный контекст у API
    /api/v1/departments/{id}/ui-context/, дополняет его минимальными
    метаданными для шаблона и рендерит страницу.

    В контекст добавляются:
      - members_exclude_ids: список id сотрудников, которых нельзя
        предлагать в "Добавить участника" (те, кто уже в отделе + руководитель)
      - can_manage / can_change_head / can_assign_roles: плоские флаги,
        чтобы шаблонам не ходить в вложенный user_perms.
    """
    api = get_api_client(request)
    r = api.get(f"v1/departments/{pk}/ui-context/")
    if not r.ok:
        messages.error(
            request,
            "Отдел не найден" if r.status == 404 else f"Ошибка API ({r.status})",
        )
        return redirect("employees:department_list")

    # r.json в нашем api-клиенте может быть полем или методом — поддержим оба варианта
    try:
        ctx = (
            r.json
            if isinstance(r.json, dict)
            else (r.json() if callable(r.json) else {})
        )
    except Exception:
        ctx = {}

    if not isinstance(ctx, dict):
        ctx = {}

    perms = (
        (ctx.get("user_perms") or {}) if isinstance(ctx.get("user_perms"), dict) else {}
    )

    # ——— метаданные для автодополнения «Добавить участника» ———
    links = ctx.get("links") or []
    exclude_ids: list[int] = []
    for li in links:
        emp = li.get("employee") if isinstance(li, dict) else None
        if emp is None:
            continue
        # в агрегате employee может быть int (id) или объект
        eid = emp.get("id") if isinstance(emp, dict) else emp
        if eid:
            try:
                exclude_ids.append(int(eid))
            except (TypeError, ValueError):
                pass

    # head тоже исключаем
    dept = ctx.get("dept") or {}
    head_id = dept.get("head_id") or (
        (dept.get("head") or {}).get("id")
        if isinstance(dept.get("head"), dict)
        else None
    )
    if head_id:
        try:
            exclude_ids.append(int(head_id))
        except (TypeError, ValueError):
            pass

    # уберём дубликаты, сохраняя порядок
    seen = set()
    exclude_ids = [x for x in exclude_ids if not (x in seen or seen.add(x))]

    ctx.update(
        {
            "members_exclude_ids": exclude_ids,
            "can_manage": bool(perms.get("can_manage")),
            "can_change_head": bool(perms.get("can_change_head")),
            "can_assign_roles": bool(perms.get("can_assign_roles")),
            "posts": _fetch_department_posts(api, pk)
        }
    )
    return render(request, "employees/department_detail.html", ctx)


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
        return redirect("employees:department_detail", pk=pk)

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
    return redirect("employees:department_detail", pk=pk)


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
        return redirect("employees:department_detail", pk=pk)

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
    return redirect("employees:department_detail", pk=pk)


# ---------- SET MEMBER ROLE ----------
@require_api_auth
@require_http_methods(["POST"])
def set_member_role(request, dept_id: int, emp_id: int):
    """
    Серверный proxy: меняем роль сотрудника в отделе.
    Тело: role_id (пусто => снять роль), next (опционально для редиректа).
    """
    api = get_api_client(request)

    role_id_raw = request.POST.get("role_id", "")
    role_id = None
    if str(role_id_raw).strip() not in {"", "None", "null"}:
        try:
            role_id = int(role_id_raw)
        except (TypeError, ValueError):
            role_id = None

    # заодно не даём менять самому себе (UI тоже скрывает)
    if (str(emp_id) == str(getattr(request.user, "id", None))) and not (
        request.user.is_staff or request.user.is_superuser
    ):
        messages.error(request, "Нельзя изменять собственную роль в отделе.")
        return redirect(
            request.POST.get("next") or reverse("employees:profile", args=("me",))
        )

    # пробрасываем в API — он сам проверит, что вы глава отдела
    resp = api.post(
        f"v1/departments/{dept_id}/set_member_role/",
        json={
            "employee_id": emp_id,
            "role_id": role_id,
        },
    )

    if resp.ok:
        messages.success(request, "Роль обновлена.")
    else:
        try:
            data = resp.json
        except Exception:
            data = {}
        err = data.get("detail") or data.get("error") or f"HTTP {resp.status}"
        messages.error(request, f"Не удалось обновить роль: {err}")

    return redirect(
        request.POST.get("next")
        or reverse("employees:employee_profile", args=(emp_id,))
    )


@require_api_auth
@require_http_methods(["POST"])
def department_add_member(request, pk: int):
    """
    Прокси-вьюха: добавляет (активирует) сотрудника в отделе через API.

    Ожидает:
        POST form-data: employee_id

    Поведение:
        - Делает POST в /api/v1/departments/{id}/add_member/ c {"employee_id": <int>}.
        - Сообщения об успехе/ошибке через django.contrib.messages.
        - Редирект обратно на страницу отдела.
    """
    api = get_api_client(request)

    raw = (request.POST.get("employee_id") or "").strip()
    try:
        employee_id = int(raw)
    except (TypeError, ValueError):
        messages.error(request, "Не выбран сотрудник.")
        return redirect("employees:department_detail", pk=pk)

    resp = api.post(
        f"v1/departments/{pk}/add_member/", json={"employee_id": employee_id}
    )
    if resp.ok:
        messages.success(request, "Сотрудник добавлен в отдел.")
    else:
        # аккуратно вытащим текст ошибки
        detail = ""
        try:
            data = resp.json or {}
            detail = data.get("detail") or data.get("error") or ""
        except Exception:
            detail = resp.text or ""
        messages.error(request, f"Не удалось добавить: {resp.status} {detail}".strip())

    return redirect("employees:department_detail", pk=pk)


@require_api_auth
@require_http_methods(["POST"])
def department_remove_member(request, pk: int):
    """
    Прокси-вьюха: деактивирует (удаляет) сотрудника из отдела через API.

    Ожидает:
        POST form-data: employee_id

    Поведение:
        - Делает POST в /api/v1/departments/{id}/remove_member/ c {"employee_id": <int>}.
        - Не изменяет роль (эта логика на API и отделена).
        - Сообщения об успехе/ошибке через django.contrib.messages.
        - Редирект обратно на страницу отдела.
    """
    api = get_api_client(request)

    raw = (request.POST.get("employee_id") or "").strip()
    try:
        employee_id = int(raw)
    except (TypeError, ValueError):
        messages.error(request, "Не выбран сотрудник.")
        return redirect("employees:department_detail", pk=pk)

    resp = api.post(
        f"v1/departments/{pk}/remove_member/", json={"employee_id": employee_id}
    )
    if resp.ok:
        messages.success(request, "Сотрудник удалён из отдела.")
    else:
        try:
            data = resp.json or {}
            detail = data.get("detail") or data.get("error") or ""
        except Exception:
            detail = resp.text or ""
        messages.error(request, f"Не удалось удалить: {resp.status} {detail}".strip())

    return redirect("employees:department_detail", pk=pk)


@require_api_auth
@require_POST
def edit_department_role(request, pk: int):
    """
    Универсальный обработчик ролей отдела:
    - op=create  : POST v1/department-roles/ {department: pk, name} + сразу POST set_perms/
    - op=update  : PATCH v1/department-roles/<role_id>/ {name} + POST set_perms/
    - op=delete  : DELETE v1/department-roles/<role_id>/
    """
    api = get_api_client(request)
    op = (request.POST.get("op") or "").lower().strip()

    # Быстрая проверка прав (как и в шаблоне)
    dept_resp = api.get(f"v1/departments/{pk}/")
    if not dept_resp.ok:
        messages.error(request, "Отдел не найден.")
        return redirect("employees:department_detail", pk=pk)
    dept = dept_resp.json
    allowed = request.user.is_staff or (
        dept.get("head") and dept["head"].get("id") == request.user.id
    )
    if not allowed:
        messages.error(request, "Недостаточно прав для управления ролями отдела.")
        return redirect("employees:department_detail", pk=pk)

    try:
        if op == "create":
            name = (request.POST.get("name") or "").strip()
            if not name:
                messages.error(request, "Название роли не может быть пустым.")
                return redirect("employees:department_detail", pk=pk)

            # 1) создаём роль
            resp = api.post(
                "v1/department-roles/", json={"department": pk, "name": name}
            )
            if resp.ok:
                # 2) сразу выставляем права, если они пришли из формы
                role_id = (resp.json or {}).get("id")
                perm_ids = [
                    int(x)
                    for x in request.POST.getlist("permission_ids")
                    if str(x).isdigit()
                ]
                if role_id is not None:
                    # ВАЖНО: у set_perms — хвостовой слэш!
                    api.post(
                        f"v1/department-roles/{role_id}/set_perms/",
                        json={"permission_ids": perm_ids},
                    )

                messages.success(request, f"Роль «{name}» создана.")
            else:
                messages.error(
                    request,
                    f"Ошибка создания роли: {getattr(resp, 'status', '')} {resp.text or ''}",
                )

        elif op == "update":
            role_id = request.POST.get("role_id")
            name = (request.POST.get("name") or "").strip()

            # 1) имя
            if name:
                api.patch(f"v1/department-roles/{role_id}/", json={"name": name})

            # 2) права (с хвостовым слэшем!)
            perm_ids = [
                int(x)
                for x in request.POST.getlist("permission_ids")
                if str(x).isdigit()
            ]
            resp = api.post(
                f"v1/department-roles/{role_id}/set_perms/",
                json={"permission_ids": perm_ids},
            )

            if resp.ok:
                messages.success(request, f"Роль обновлена: «{name}».")
            else:
                messages.error(
                    request,
                    f"Ошибка обновления роли: {getattr(resp, 'status', '')} {resp.text or ''}",
                )

        elif op == "delete":
            role_id = request.POST.get("role_id")
            if not role_id:
                messages.error(request, "Не указан идентификатор роли для удаления.")
                return redirect("employees:department_detail", pk=pk)

            resp = api.delete(f"v1/department-roles/{role_id}/")
            if resp.ok or getattr(resp, "status", None) == 204:
                messages.success(request, "Роль удалена.")
            else:
                messages.error(
                    request,
                    f"Ошибка удаления роли: {getattr(resp, 'status', '')} {resp.text or ''}",
                )

        else:
            messages.error(request, "Неизвестная операция.")
    except Exception as exc:
        messages.error(request, f"Ошибка: {exc}")

    return redirect("employees:department_detail", pk=pk)


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


# =========================
#   Должности
# =========================


# ---------- CREATE POSITION ----------
@csrf_protect
@login_required
@require_POST
def position_create_front(request: HttpRequest) -> JsonResponse:
    """
    Создать должность (прокси к POST /api/v1/positions/).
    Ожидает JSON или form-data с полями: name, description?, groups? (list[int]).
    """
    payload = _json_body(request) or request.POST.dict()
    name = (payload.get("name") or "").strip()
    description = (payload.get("description") or "").strip()

    # groups может прийти как список, как csv или отсутствовать
    groups = payload.get("groups")
    if isinstance(groups, str):
        groups = [int(x) for x in groups.split(",") if x.strip().isdigit()]
    elif isinstance(groups, list):
        groups = [int(x) for x in groups if str(x).isdigit()]
    else:
        groups = []

    if not name:
        return _error("Укажите название должности", 400)

    api = get_api_client(request)
    api_payload = {"name": name}
    if description:
        api_payload["description"] = description
    if groups:
        api_payload["groups"] = groups

    resp = api.post("v1/positions/", json=api_payload)
    ok, data, status = _api_ok_or_error(resp)
    if not ok:
        return JsonResponse(
            data or {"detail": "Не удалось создать должность"}, status=status
        )
    return _ok(data, status=201)


# ---------- UPDATE POSITION ----------
@csrf_protect
@login_required
@require_http_methods(["PATCH", "POST"])
def position_update_front(request: HttpRequest, pos_id: int) -> JsonResponse:
    """
    Обновить должность (прокси к PATCH /api/v1/positions/{id}/).
    Приходит JSON с любыми изменяемыми полями (name, description, groups).
    Разрешаем метод PATCH и POST (для совместимости) — на POST тоже шлём PATCH в API.
    """
    payload = _json_body(request) or request.POST.dict()

    # Если groups пришли строкой — распарсим
    groups = payload.get("groups", None)
    if isinstance(groups, str):
        payload["groups"] = [int(x) for x in groups.split(",") if x.strip().isdigit()]

    api = get_api_client(request)
    resp = api.patch(f"v1/positions/{pos_id}/", json=payload)
    ok, data, status = _api_ok_or_error(resp)
    if not ok:
        return JsonResponse(
            data or {"detail": "Не удалось обновить должность"}, status=status
        )
    return _ok(data)


# ---------- ASSIGN POSITION TO EMPLOYEE ----------
@csrf_protect
@login_required
@require_POST
def employee_set_position_front(request: HttpRequest, emp_id: int) -> JsonResponse:
    """
    Назначить сотруднику position_id (прокси к PATCH /api/v1/employees/{id}/).
    Ожидает JSON/form-data: position_id (int или пусто для снятия).
    """
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Bad JSON"}, status=400)

    raw = payload.get("position_id", None)

    try:
        position_id = int(str(raw).strip()) if raw is not None else None
    except (ValueError, TypeError):
        return JsonResponse({"detail": "position_id must be an integer"}, status=400)

    if not position_id:
        return JsonResponse({"detail": "position_id is required"}, status=400)

    api = get_api_client(request)
    resp = api.patch(f"v1/employees/{emp_id}/", json={"position_id": position_id})
    ok, data, status = _api_ok_or_error(resp)
    if not ok:
        return JsonResponse(
            data or {"detail": "Не удалось назначить должность"}, status=status
        )
    return _ok(data)


# Удобная обёртка под «/me/»
@csrf_protect
@login_required
@require_POST
def employee_set_position_me_front(request: HttpRequest) -> JsonResponse:
    """
    Назначить должность текущему пользователю (прокси к PATCH /api/v1/employees/me/).
    """
    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse({"detail": "Bad JSON"}, status=400)

    raw = payload.get("position_id", None)

    try:
        position_id = int(str(raw).strip()) if raw is not None else None
    except (ValueError, TypeError):
        return JsonResponse({"detail": "position_id must be an integer"}, status=400)

    if not position_id:
        return JsonResponse({"detail": "position_id is required"}, status=400)

    api = get_api_client(request)
    resp = api.patch("v1/employees/me/", json={"position_id": position_id})
    ok, data, status = _api_ok_or_error(resp)
    if not ok:
        return JsonResponse(
            data or {"detail": "Не удалось назначить должность"}, status=status
        )
    return _ok(data)
