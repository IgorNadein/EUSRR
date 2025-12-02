# backend/employees/views_front.py

from __future__ import annotations

import base64
import json
import mimetypes
from io import BytesIO
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
from django.http.multipartparser import MultiPartParser, MultiPartParserError


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


def _parse_multipart_request(
    request: HttpRequest, logger
) -> tuple[Dict[str, Any], Any]:
    """Возвращает (POST, FILES) даже для PATCH с multipart/form-data."""
    content_type = request.content_type or ""
    if request.method == "POST" or "multipart/form-data" not in content_type:
        return request.POST, request.FILES

    try:
        stream = BytesIO(request.body)
        parser = MultiPartParser(
            request.META,
            stream,
            request.upload_handlers,
            request.encoding,
        )
        post_data, files_data = parser.parse()
        logger.info(
            "[multipart_parser] Parsed PATCH payload: %s fields, %s files",
            len(post_data.keys()),
            len(files_data.keys()),
        )
        return post_data, files_data
    except MultiPartParserError as exc:
        logger.error(
            "[multipart_parser] Failed to parse multipart body: %s",
            exc,
        )
    except Exception:
        logger.exception(
            "[multipart_parser] Unexpected error while parsing multipart body"
        )
    return request.POST, request.FILES


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


def _convert_api_url_to_frontend(api_url: str | None, frontend_path: str) -> str | None:
    """
    Преобразует API URL пагинации в frontend URL.
    
    Пример:
        http://localhost:9000/api/v1/employees/?page=2&search=test
        -> /employees/list/?page=2&search=test
    """
    if not api_url:
        return None
    
    from urllib.parse import urlparse, parse_qs, urlencode
    
    parsed = urlparse(api_url)
    query_params = parse_qs(parsed.query)
    
    # Преобразуем query_params обратно в строку (parse_qs возвращает списки)
    clean_params = {k: v[0] if isinstance(v, list) and len(v) == 1 else v 
                    for k, v in query_params.items()}
    query_string = urlencode(clean_params, doseq=True)
    
    return f"{frontend_path}?{query_string}" if query_string else frontend_path
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
    position = request.GET.get("position")
    is_active = request.GET.get("is_active")

    params = {"page": page, "ordering": ordering}
    if q:
        params["search"] = q
    if department:
        params["department"] = department
    if position:
        params["position"] = position
    if is_active:
        params["is_active"] = is_active

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
    
    # Преобразуем API URLs в frontend URLs
    next_url = _convert_api_url_to_frontend(next_url, request.path)
    prev_url = _convert_api_url_to_frontend(prev_url, request.path)

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
    # Проверяем права на создание сотрудников
    create_url = None
    has_perm = (
        request.user.has_perm('employees.add_employee')
        or request.user.is_staff
        or request.user.is_superuser
    )
    if has_perm:
        from django.urls import reverse
        create_url = reverse('employees:employee_create')
    
    # Если фильтрация по отделу, меняем label
    count_label = "Всего:"
    if department:
        count_label = "В отделе:"
    
    # Получаем списки для фильтров
    departments_list = []
    positions_list = []
    try:
        # Получаем все отделы
        dept_resp = api.get("v1/departments/", params={"page_size": 1000})
        if dept_resp.ok:
            dept_data = dept_resp.json or {}
            departments_list = dept_data.get("results", [])
        
        # Получаем все должности
        pos_resp = api.get("v1/positions/", params={"page_size": 1000})
        if pos_resp.ok:
            pos_data = pos_resp.json or {}
            positions_list = pos_data.get("results", [])
    except Exception:
        pass
    
    context = {
        "employees": items,
        "count": count,
        "q": q,
        "o": ordering,
        "page": page,
        "next_url": next_url,
        "prev_url": prev_url,
        "create_url": create_url,
        "count_label": count_label,
        "departments_list": departments_list,
        "positions_list": positions_list,
    }
    return render(request, "employees/employees_list.html", context)


# ---------- DETAIL / ME ----------
@require_api_auth
def employee_profile(request, pk: str | int = "me"):
    """Профиль сотрудника (/employees/me/ и /employees/<pk>/).

    Поведение:
      * Если pk совпадает с текущим пользователем — выполняется 302 редирект на /employees/me/?<query>.
      * Подтягивает данные сотрудника, посты, справочники (навыки/должности/группы).
      * Передаёт в шаблон персональные группы сотрудника для рендера «пилюль».
      * Передаёт `endpoint` для PATCH-редактирования профиля через фронтовую вьюху.

    Args:
        request (HttpRequest): HTTP-запрос.
        pk (str | int, optional): 'me'/'self' или числовой ID сотрудника. По умолчанию 'me'.

    Returns:
        HttpResponse: Отрисованный шаблон профиля либо редирект/сообщение об ошибке.

    Raises:
        None: Все ошибки бэкенд-API обрабатываются и отражаются через messages/redirect.
    """
    # --- редирект "свой id" -> /me ---
    try:
        int_pk = int(pk)  # type: ignore[arg-type]
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

    endpoint_api = "v1/employees/me/" if is_me else f"v1/employees/{pk}/"
    resp = api.get(endpoint_api)
    if not resp.ok:
        messages.error(request, f"Сотрудник не найден ({resp.status})")
        return redirect("employees:employees_list")

    emp = resp.json or {}
    emp_id = emp.get("id") or (request.user.id if is_me else pk)
    posts = _fetch_employee_posts(api, emp_id)

    # Справочники
    sresp = api.get("v1/skills/", params={"ordering": "name"})
    sdata = sresp.json if sresp.ok else []
    all_skills = sdata.get("results", sdata) if isinstance(sdata, dict) else sdata

    gresp_all = api.get("v1/groups/", params={"ordering": "name"})
    gdata_all = gresp_all.json if gresp_all.ok else []
    all_groups = (
        gdata_all.get("results", gdata_all) if isinstance(gdata_all, dict) else gdata_all
    ) or []

    # Персональные группы сотрудника (для «пилюль»)
    pg_resp = api.get("v1/groups/", params={"ordering": "name", "member": emp_id})
    pg_data = pg_resp.json if pg_resp.ok else []
    emp_personal_groups = (
        pg_data.get("results", pg_data) if isinstance(pg_data, dict) else pg_data
    ) or []

    presp = api.get("v1/positions/", params={"ordering": "name"})
    pdata = presp.json if presp.ok else []
    all_positions = pdata.get("results", pdata) if isinstance(pdata, dict) else pdata

    # Отделы/роли
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

    # Права на редактирование профиля
    can_edit = (
        True
        if is_me
        else bool(
            request.user and (request.user.is_staff or request.user.id == emp.get("id"))
        )
    )

    # ВАЖНО: endpoint фронтовой вьюхи для PATCH профиля (а не прямой DRF-URL)
    endpoint = (
        reverse("employees:employee_edit_me")
        if is_me
        else reverse("employees:employee_edit", args=[emp_id])
    )

    ctx = {
        "emp": emp,
        "emp_depts": emp_depts,
        "can_edit": can_edit,
        "all_skills": all_skills,
        "all_positions": all_positions,
        "all_groups": all_groups,
        "emp_personal_groups": emp_personal_groups,
        "posts": posts,
        "is_me": True if is_me else False,
        "endpoint": endpoint,  # для data-endpoint в _employee_edit.html
    }
    return render(request, "employees/employee_detail.html", ctx)


# ---------- EDIT (self or staff) ----------
@require_api_auth
@require_http_methods(["PATCH", "POST"])
def employee_edit(request, pk: int):
    """
    Редактирование пользователя по id.
    Поддерживает как JSON, так и multipart/form-data (для загрузки файлов).
    """
    import logging
    logger = logging.getLogger(__name__)
    
    api = get_api_client(request)
    
    # Проверяем Content-Type
    content_type = request.content_type or ''
    logger.info(f"[employee_edit] pk={pk}, Content-Type: {content_type}")
    parsed_post, parsed_files = _parse_multipart_request(request, logger)
    logger.info(
        "[employee_edit] request.POST keys: %s",
        list(parsed_post.keys()),
    )
    logger.info(
        "[employee_edit] request.FILES keys: %s",
        list(parsed_files.keys()),
    )
    
    if 'multipart/form-data' in content_type:
        # Обрабатываем multipart/form-data (файлы)
        logger.info("[employee_edit] Processing multipart/form-data")
        payload = {}
        
        # Собираем обычные поля из POST
        for key, value in parsed_post.items():
            if key == 'csrfmiddlewaretoken':
                continue
            # Если это массив (например skills_ids)
            if key.endswith('_ids') or key == 'skills':
                payload[key] = parsed_post.getlist(key)
            else:
                payload[key] = value
        
        logger.info(
            "[employee_edit] Payload before avatar: %s",
            list(payload.keys()),
        )
        
        # Обрабатываем файлы (аватар)
        if 'avatar' in parsed_files:
            avatar_file = parsed_files['avatar']
            logger.info(
                "[employee_edit] Processing avatar: %s, size: %s",
                avatar_file.name,
                avatar_file.size,
            )
            # Конвертируем в data URI для Base64ImageField
            data_uri = _file_to_data_uri(avatar_file)
            payload['avatar'] = data_uri
            logger.info(f"[employee_edit] Avatar converted, data URI length: {len(data_uri)}")
        else:
            logger.warning("[employee_edit] No avatar in request.FILES")
        
        logger.info(f"[employee_edit] Final payload keys: {list(payload.keys())}")
        
        # Отправляем в DRF как JSON (с base64 аватаром)
        resp = api.patch(f"v1/employees/{pk}/", json=payload)
        logger.info(f"[employee_edit] API response status: {resp.status}")
    else:
        # Обрабатываем JSON (как раньше)
        logger.info("[employee_edit] Processing JSON")
        try:
            payload = json.loads(request.body or b"{}")
        except Exception as e:
            logger.error(f"[employee_edit] JSON parse error: {e}")
            payload = {}
        resp = api.patch(f"v1/employees/{pk}/", json=payload)
    
    try:
        data = resp.json
    except Exception:
        data = {"detail": resp.text}

    accepts = (request.headers.get("Accept") or "").lower()
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    wants_json = "application/json" in accepts or is_ajax

    if wants_json:
        return JsonResponse(data or {}, status=resp.status)

    if resp.ok:
        messages.success(request, "Профиль сотрудника обновлён")
        redirect_url = request.META.get("HTTP_REFERER") or reverse(
            "employees:employee_profile",
            args=(pk,),
        )
        return redirect(redirect_url)
    else:
        # При ошибке валидации показываем детали
        if resp.status == 400 and isinstance(data, dict):
            # Собираем все ошибки валидации
            error_messages = []
            for field, errors in data.items():
                if field == 'detail':
                    error_messages.append(str(errors))
                elif isinstance(errors, list):
                    field_name = field.replace('_', ' ').title()
                    for error in errors:
                        if isinstance(error, dict):
                            err_str = error.get('string', error)
                            error_messages.append(f"{field_name}: {err_str}")
                        else:
                            error_messages.append(f"{field_name}: {error}")
                else:
                    field_name = field.replace('_', ' ').title()
                    error_messages.append(f"{field_name}: {errors}")
            
            if error_messages:
                for msg in error_messages:
                    messages.error(request, msg)
            else:
                messages.error(request, "Ошибка валидации данных")
        else:
            detail = ""
            if isinstance(data, dict):
                detail = data.get("detail") or data.get("error") or ""
            error_msg = (
                detail
                or f"Не удалось обновить сотрудника (HTTP {resp.status})"
            )
            messages.error(request, error_msg)
        
        # Возвращаем на страницу редактирования, а не на профиль
        edit_url = reverse("employees:employee_edit", args=(pk,))
        return redirect(edit_url)


# ---------- EDIT ME ----------
@require_api_auth
@require_http_methods(["PATCH", "POST"])
def employee_edit_me(request):
    """
    Редактирование собственного профиля через /api/v1/employees/me/
    Поддерживает как JSON, так и multipart/form-data (для загрузки файлов).
    """
    import logging
    logger = logging.getLogger(__name__)
    
    logger.info("=" * 80)
    logger.info("[employee_edit_me] ===== FUNCTION CALLED =====")
    logger.info(f"[employee_edit_me] Method: {request.method}")
    
    api = get_api_client(request)
    
    # Проверяем Content-Type
    content_type = request.content_type or ''
    logger.info(f"[employee_edit_me] Content-Type: {content_type}")
    parsed_post, parsed_files = _parse_multipart_request(request, logger)
    logger.info(
        "[employee_edit_me] request.POST keys: %s",
        list(parsed_post.keys()),
    )
    logger.info(
        "[employee_edit_me] request.FILES keys: %s",
        list(parsed_files.keys()),
    )
    
    if 'multipart/form-data' in content_type:
        # Обрабатываем multipart/form-data (файлы)
        logger.info("[employee_edit_me] Processing multipart/form-data")
        payload = {}
        
        # Собираем обычные поля из POST
        for key, value in parsed_post.items():
            if key == 'csrfmiddlewaretoken':
                continue
            # Если это массив (например skills_ids)
            if key.endswith('_ids') or key == 'skills':
                payload[key] = parsed_post.getlist(key)
            else:
                payload[key] = value
        
        logger.info(
            "[employee_edit_me] Payload before avatar: %s",
            list(payload.keys()),
        )
        
        # Обрабатываем файлы (аватар)
        if 'avatar' in parsed_files:
            avatar_file = parsed_files['avatar']
            logger.info(
                "[employee_edit_me] Processing avatar: %s, size: %s, content_type: %s",
                avatar_file.name,
                avatar_file.size,
                avatar_file.content_type,
            )
            # Конвертируем в data URI для Base64ImageField
            data_uri = _file_to_data_uri(avatar_file)
            payload['avatar'] = data_uri
            logger.info(
                "[employee_edit_me] Avatar converted to data URI, length: %s",
                len(data_uri),
            )
        else:
            logger.warning("[employee_edit_me] No avatar in request.FILES")
        
        logger.info(
            "[employee_edit_me] Final payload keys: %s",
            list(payload.keys()),
        )
        
        # Отправляем в DRF как JSON (с base64 аватаром)
        resp = api.patch("v1/employees/me/", json=payload)
        logger.info(f"[employee_edit_me] API response status: {resp.status}")
    else:
        # Обрабатываем JSON (как раньше)
        logger.info("[employee_edit_me] Processing JSON")
        try:
            payload = json.loads(request.body or b"{}")
        except Exception as e:
            logger.error(f"[employee_edit_me] JSON parse error: {e}")
            payload = {}
        resp = api.patch("v1/employees/me/", json=payload)
    
    try:
        data = resp.json
    except Exception:
        data = {"detail": resp.text}

    accepts = (request.headers.get("Accept") or "").lower()
    is_ajax = request.headers.get("X-Requested-With") == "XMLHttpRequest"
    wants_json = "application/json" in accepts or is_ajax

    if wants_json:
        return JsonResponse(data or {}, status=resp.status)

    if resp.ok:
        messages.success(request, "Профиль обновлён")
        redirect_url = (
            request.META.get("HTTP_REFERER")
            or reverse("employees:profile")
        )
        return redirect(redirect_url)
    else:
        # При ошибке валидации показываем детали
        if resp.status == 400 and isinstance(data, dict):
            # Собираем все ошибки валидации
            error_messages = []
            for field, errors in data.items():
                if field == 'detail':
                    error_messages.append(str(errors))
                elif isinstance(errors, list):
                    field_name = field.replace('_', ' ').title()
                    for error in errors:
                        if isinstance(error, dict):
                            err_str = error.get('string', error)
                            error_messages.append(f"{field_name}: {err_str}")
                        else:
                            error_messages.append(f"{field_name}: {error}")
                else:
                    field_name = field.replace('_', ' ').title()
                    error_messages.append(f"{field_name}: {errors}")
            
            if error_messages:
                for msg in error_messages:
                    messages.error(request, msg)
            else:
                messages.error(request, "Ошибка валидации данных")
        else:
            detail = ""
            if isinstance(data, dict):
                detail = data.get("detail") or data.get("error") or ""
            error_msg = (
                detail or f"Не удалось обновить профиль (HTTP {resp.status})"
            )
            messages.error(request, error_msg)
        
        # Возвращаем на страницу редактирования
        edit_url = reverse("employees:employee_edit_me")
        return redirect(edit_url)


# ---------- CREATE (staff) ----------
@require_api_auth
@require_http_methods(["GET", "POST"])
def employee_create(request):
    """Страница создания сотрудника (старый вариант)"""
    api = get_api_client(request)

    if request.method == "GET":
        return render(request, "employees/employee_create.html")

    data = {
        "email": request.POST.get("email", "").strip(),
        "phone_number": request.POST.get("phone_number", "").strip(),
        "last_name": request.POST.get("last_name", "").strip(),
        "first_name": request.POST.get("first_name", "").strip(),
        "patronymic": request.POST.get("patronymic", "").strip(),
        "telegram": request.POST.get("telegram", "").strip(),
        "whatsapp": request.POST.get("whatsapp", "").strip(),
        "wechat": request.POST.get("wechat", "").strip(),
    }
    
    # Обработка gender (должно быть числом)
    gender = request.POST.get("gender", "").strip()
    if gender:
        try:
            data["gender"] = int(gender)
        except (ValueError, TypeError):
            pass
    
    # Обработка birth_date
    birth_date = request.POST.get("birth_date", "").strip()
    if birth_date:
        data["birth_date"] = birth_date
    
    # Обработка position
    position = request.POST.get("position", "").strip()
    if position:
        try:
            data["position"] = int(position)
        except (ValueError, TypeError):
            pass
    
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
        messages.error(
            request, f"Не удалось создать: {resp.status} — {resp.text}"
        )
        return render(
            request, "employees/employee_create.html", {"form": request.POST}
        )

    new_emp = resp.json or {}
    messages.success(request, "Сотрудник создан.")
    return redirect("employees:employee_detail", pk=new_emp.get("id"))


@login_required
@require_http_methods(["POST"])
def employee_create_modal(request):
    """
    Обработчик создания сотрудника через модальное окно.
    Принимает AJAX запрос, обращается к API через фронтовую логику.
    Возвращает JSON с результатом.
    """
    api = get_api_client(request)
    
    # Собираем данные из формы
    data = {
        "email": request.POST.get("email", "").strip(),
        "phone_number": request.POST.get("phone_number", "").strip(),
        "last_name": request.POST.get("last_name", "").strip(),
        "first_name": request.POST.get("first_name", "").strip(),
        "patronymic": request.POST.get("patronymic", "").strip(),
        "telegram": request.POST.get("telegram", "").strip(),
        "whatsapp": request.POST.get("whatsapp", "").strip(),
        "wechat": request.POST.get("wechat", "").strip(),
    }
    
    # Обработка gender (должно быть числом: 0, 1, 2)
    gender = request.POST.get("gender", "").strip()
    if gender:
        try:
            data["gender"] = int(gender)
        except (ValueError, TypeError):
            data["gender"] = None
    
    # Обработка остальных полей
    birth_date = request.POST.get("birth_date", "").strip()
    if birth_date:
        data["birth_date"] = birth_date
    
    position = request.POST.get("position", "").strip()
    if position:
        try:
            data["position"] = int(position)
        except (ValueError, TypeError):
            pass
    
    # Обработка аватара
    if request.FILES.get("avatar"):
        data["avatar"] = _file_to_data_uri(request.FILES["avatar"])
    
    # Обработка навыков (если будут добавлены в форму)
    skills = request.POST.getlist("skills")
    if skills:
        data["skills"] = skills
    
    # Обработка пароля
    password = request.POST.get("password", "").strip()
    if password:
        data["password"] = password
    
    # Отправляем запрос к API
    resp = api.post("v1/employees/", json=data)
    
    if not resp.ok:
        # Парсим ошибки от API
        error_msg = "Не удалось создать сотрудника"
        field_errors = {}
        
        try:
            error_data = resp.json
            if isinstance(error_data, dict):
                # Логируем для отладки
                import logging
                logger = logging.getLogger(__name__)
                logger.error(
                    f"API validation errors: {error_data}, "
                    f"sent data: {data}"
                )
                
                # Проверяем, есть ли детальные ошибки по полям
                for field, messages_list in error_data.items():
                    if isinstance(messages_list, list):
                        field_errors[field] = messages_list
                    else:
                        field_errors[field] = [str(messages_list)]
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Error parsing API response: {e}, resp.text: {resp.text}")
            error_msg = f"Ошибка {resp.status}: {resp.text}"
        
        # Если есть детальные ошибки, возвращаем их
        if field_errors:
            return JsonResponse({
                "success": False,
                "error": "Проверьте правильность заполнения полей",
                "errors": field_errors
            }, status=400)
        else:
            return JsonResponse({
                "success": False,
                "error": error_msg
            }, status=400)
    
    # Успешное создание
    new_emp = resp.json or {}
    emp_id = new_emp.get("id")
    
    redirect_url = None
    if emp_id:
        redirect_url = reverse(
            "employees:employee_detail", kwargs={"pk": emp_id}
        )
    
    return JsonResponse({
        "success": True,
        "message": "Сотрудник успешно создан",
        "employee_id": emp_id,
        "redirect_url": redirect_url
    })


# =========================
# Группы
# =========================


@require_api_auth
@require_http_methods(["POST"])
def employee_groups_bulk(request, pk: int):
    """
    Назначить/снять персональные группы сотруднику.
    Body: { "action": "add"|"remove", "group_ids": [1,2,3] }
    """
    api = get_api_client(request)
    try:
        payload = json.loads(request.body or b"{}")
    except Exception:
        payload = {}
    action = (payload.get("action") or "").strip().lower()
    group_ids = payload.get("group_ids") or []
    if action not in {"add", "remove"}:
        return JsonResponse({"detail": "action must be 'add' or 'remove'"}, status=400)
    try:
        gids = [int(x) for x in group_ids]
    except Exception:
        return JsonResponse({"detail": "group_ids must be a list of integers"}, status=400)
    if not gids:
        return JsonResponse({"detail": "group_ids is empty"}, status=400)

    ok, errors = 0, {}
    endpoint = "add-members" if action == "add" else "remove-members"
    for gid in gids:
        r = api.post(f"v1/groups/{gid}/{endpoint}/", json={"member_ids": [pk]})
        if r.ok:
            ok += 1
        else:
            try:
                j = r.json or {}
                msg = j.get("detail") or r.text or f"HTTP {r.status}"
            except Exception:
                msg = r.text or f"HTTP {r.status}"
            errors[str(gid)] = msg
    status_code = 200 if not errors else 207  # Multi-Status семантически уместен
    return JsonResponse({"ok": True, "processed": ok, "failed": errors}, status=status_code)


@require_api_auth
@require_http_methods(["POST"])
def group_create(request):
    """
    Создать группу (LDAP+БД) через DRF.
    Body: { "name": "CN-Name" }
    """
    api = get_api_client(request)
    try:
        payload = json.loads(request.body or b"{}")
    except Exception:
        payload = {}
    name = (payload.get("name") or "").strip()
    if not name:
        return JsonResponse({"detail": "name is required"}, status=400)

    resp = api.post("v1/groups/", json={"name": name})
    try:
        data = resp.json
    except Exception:
        data = {"detail": resp.text}
    return JsonResponse(data or {}, status=resp.status)


@require_api_auth
@require_http_methods(["POST"])
def group_delete(request):
    """
    Удалить группу (LDAP+БД) через DRF.
    Body: { "group_id": 123 }
    """
    api = get_api_client(request)
    try:
        payload = json.loads(request.body or b"{}")
    except Exception:
        payload = {}
    gid = payload.get("group_id")
    try:
        gid = int(gid)
    except Exception:
        return JsonResponse({"detail": "group_id must be int"}, status=400)

    resp = api.delete(f"v1/groups/{gid}/")
    if not resp.ok:
        return JsonResponse({"detail": resp.text}, status=resp.status)
    return JsonResponse({"ok": True, "id": gid}, status=200)


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

    # Преобразуем API URLs в frontend URLs
    next_url = _convert_api_url_to_frontend(next_url, request.path)
    prev_url = _convert_api_url_to_frontend(prev_url, request.path)

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
            "posts": _fetch_department_posts(api, pk),
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


# ---------- CREATE (staff) ----------
@login_required
@require_api_auth
@require_http_methods(["GET", "POST"])
def department_create(request):
    """
    Страница создания отдела.
    Работает ТОЛЬКО через API: POST v1/departments/
    Доступ: суперпользователь/страфф или обладатели perms.employees.add_department.
    """
    # Мягкая проверка прав на фронте (API всё равно откажет 403 при отсутствии прав)
    if not (
        request.user.is_superuser
        or request.user.is_staff
        or request.user.has_perm("employees.add_department")
    ):
        return redirect("employees:department_list")

    if request.method == "GET":
        form = DepartmentEditForm()
        return render(
            request,
            "employees/department_create.html",
            {
                "form": form,
                "page_title": "Создать отдел",
                "submit_label": "Создать",
                "object": None,
            },
        )

    # POST
    form = DepartmentEditForm(request.POST)
    if not form.is_valid():
        return render(
            request,
            "employees/department_create.html",
            {
                "form": form,
                "page_title": "Создать отдел",
                "submit_label": "Создать",
                "object": None,
            },
            status=400,
        )

    api = get_api_client(request)
    payload = {
        "name": form.cleaned_data["name"],
        "description": form.cleaned_data.get("description") or "",
    }

    # Отправляем в API
    r = api.post("v1/departments/", json=payload)
    if r.ok and isinstance(r.json, dict):
        dept_id = r.json.get("id")
        messages.success(request, "Отдел успешно создан.")
        if dept_id:
            return redirect("employees:department_detail", pk=dept_id)
        # если по какой-то причине id не вернули — уходим в список
        return redirect("employees:department_list")

    # Обработка ошибок API: 400 — ошибки сериализатора, 403 — запрет
    try:
        err = r.json()
    except Exception:
        err = None

    if getattr(r, "status", None) == 400 and isinstance(err, dict):
        # Пытаемся сопоставить ошибки полям формы
        attached = False
        for field in ("name", "description", "non_field_errors"):
            if field in err:
                msgs = err[field]
                if isinstance(msgs, (list, tuple)) and msgs:
                    if field in form.fields:
                        form.add_error(field, msgs[0])
                    else:
                        form.add_error(None, msgs[0])
                    attached = True
        if not attached:
            form.add_error(
                None, "Не удалось создать отдел. Проверьте введённые данные."
            )
        status_code = 400
    elif getattr(r, "status", None) == 403:
        form.add_error(None, "Недостаточно прав для создания отдела.")
        status_code = 403
    else:
        form.add_error(None, f"Ошибка API ({getattr(r, "status", None)}). Повторите попытку позже.")
        status_code = 502

    return render(
        request,
        "employees/department_create.html",
        {
            "form": form,
            "page_title": "Создать отдел",
            "submit_label": "Создать",
            "object": None,
        },
        status=status_code,
    )


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

@require_api_auth
@require_http_methods(["GET"])
def position_detail_front(request: HttpRequest, pos_id: int) -> JsonResponse:
    """
    Прокси к GET /api/v1/positions/{id}/ — возвращает JSON должности.
    """
    api = get_api_client(request)
    resp = api.get(f"v1/positions/{pos_id}/")
    ok, data, status = _api_ok_or_error(resp)
    if not ok:
        return JsonResponse(data or {"detail": "Не удалось получить должность"}, status=status)
    return JsonResponse(data or {}, status=200)


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
