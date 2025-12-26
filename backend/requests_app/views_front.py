from __future__ import annotations
from typing import Any, Dict, List, Mapping, Optional, Tuple

from api.client import get_api_client
from api.decorators import require_api_auth
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.models import AbstractBaseUser
from django.http import HttpRequest, JsonResponse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.views.generic import TemplateView
from django.utils.dateparse import parse_datetime
from django.utils.timezone import localtime
from employees.models import Department, EmployeeDepartment  # добавлены импорты


def _api_unpack(resp: Any) -> Tuple[bool, Dict[str, Any], int]:
    """Извлекает ok/json/status из ответа API-обёртки.

    Args:
        resp (Any): Ответ клиентской обёртки (ожидаются .ok, .json/.json(), .status).

    Returns:
        tuple[bool, dict[str, Any], int]: ok, payload, status.

    Raises:
        AttributeError: Если в ответе нет ожидаемых атрибутов.
    """
    ok: bool = getattr(resp, "ok")
    status: int = getattr(resp, "status")
    data_attr = getattr(resp, "json", None)
    data: Dict[str, Any]
    if callable(data_attr):
        data = data_attr() or {}
    else:
        data = data_attr or {}
    return ok, data, status


def _err_msg(payload: Any, fallback: str = "") -> str:
    # dict: detail / non_field_errors / первое поле со строкой
    if isinstance(payload, dict):
        if isinstance(payload.get("detail"), (str, list)):
            d = payload["detail"]
            return d if isinstance(d, str) else "; ".join(map(str, d))
        if isinstance(payload.get("non_field_errors"), list):
            return "; ".join(map(str, payload["non_field_errors"]))
        # первая строка из значений полей
        for v in payload.values():
            if isinstance(v, list) and v and isinstance(v[0], str):
                return "; ".join(map(str, v))
            if isinstance(v, str):
                return v
    # list: склеить
    if isinstance(payload, list):
        return "; ".join(map(str, payload))
    # str или что-то иное
    return str(payload or fallback)


def _fmt_dt(val, fmt: str = "%d.%m.%Y %H:%M") -> str | None:
    """Превращает ISO-строку/дату в локализованную строку.
    Если не получилось — возвращает исходное значение."""
    if not val:
        return None
    # если уже datetime — ок, если строка — парсим
    dt = parse_datetime(val) if isinstance(val, str) else val
    if dt is None:
        return val  # на всякий случай оставим как есть
    try:
        return localtime(dt).strftime(fmt)  # уважим таймзону пользователя
    except Exception:
        return val


def _format_datetime_fields(
    items: List[Any],
    fields: tuple[str, ...] = ("created_at", "updated_at", "decided_at"),
) -> List[Any]:
    out: List[Any] = []
    for it in items:
        if isinstance(it, Mapping):
            d = dict(it)  # копия, не мутируем исходник
            for f in fields:
                if f in d:
                    d[f] = _fmt_dt(d.get(f))
            out.append(d)
        else:
            out.append(it)
    return out


def _parse_page_payload(
    payload: Any,
) -> Tuple[List[Dict[str, Any]], Optional[str], Optional[str], Optional[int]]:
    """Нормализует ответ API к (results, next, previous, count). Поддерживает:
       - DRF-страницу {"count","next","previous","results":[...]}
       - непагинированный список [...]."""
    # 1) Непагинированный список
    if isinstance(payload, list):
        results = _format_datetime_fields(payload)
        return results, None, None, len(results)

    # 2) Словарь (пагинированный или нет)
    if isinstance(payload, Mapping):
        if "results" in payload:
            raw = payload.get("results") or []
            results = _format_datetime_fields(list(raw))
            return results, payload.get("next"), payload.get("previous"), payload.get("count")
        # словарь, но не страница — пустой список
        return [], None, None, None

    # 3) Непонятный формат
    return [], None, None, None


def _user_can_process_requests(user: AbstractBaseUser) -> bool:
    """Определяет, показывать ли расширенный скоуп (вкладку «Все» и действия).

    True если:
      - staff / superuser;
      - есть модельное право `requests_app.can_process_requests`;
      - руководитель хотя бы одного отдела;
      - есть департаментное право `can_process_requests` или `view_request`.
    """
    if not user or getattr(user, "is_anonymous", False):
        return False
    if getattr(user, "is_staff", False) or getattr(user, "is_superuser", False):
        return True
    if user.has_perm("requests_app.can_process_requests"):
        return True
    if Department.objects.filter(head_id=user.id).exists():
        return True
    dept_perm_codes = {"can_process_requests", "view_request"}
    has_dept_perm = EmployeeDepartment.objects.filter(
        employee_id=user.id,
        is_active=True,
        role__scoped_permissions__code__in=dept_perm_codes,
    ).exists()
    return has_dept_perm


@method_decorator([csrf_protect, require_api_auth], name="dispatch")
class RequestsView(LoginRequiredMixin, TemplateView):
    """Единая фронтовая вью, покрывающая весь API заявлений.

    GET:
        - Загружает список заявлений через API (`GET /api/v1/requests/`).
        - Понимает фильтры API: `view=mine` ИЛИ `mine=1|true|yes|on`, `type`, `status`.
        - Поддерживает просмотр комментариев к одному заявлению через `?comments_for=<id>`
          (делает `GET /api/v1/requests/{id}/comments/` и кладёт их в контекст).

    POST (по `_action`):
        - create  → `POST /api/v1/requests/` (multipart при наличии файла).
        - update  → `PATCH /api/v1/requests/{id}/` (multipart при наличии файла).
        - delete  → `DELETE /api/v1/requests/{id}/`.
        - approve → `POST /api/v1/requests/{id}/approve/`.
        - reject  → `POST /api/v1/requests/{id}/reject/`.
        - cancel  → `POST /api/v1/requests/{id}/cancel/`.
        - comment → `POST /api/v1/requests/{id}/comments/` (JSON).

    Контекст шаблона:
        requests, next_url, prev_url, count, scope, can_process,
        filters (dict с применёнными фильтрами),
        comments_for (int|None), comments (list[dict]) — при запросе комментариев.

    Raises:
        ValueError: При невалидных входных данных для конкретных экшенов.
    """

    template_name = "requests_app/request_list_full.html"

    # ---------- GET ----------

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Формирует контекст страницы списка, фильтров и комментариев.

        Returns:
            Dict[str, Any]: Контекст шаблона.
        """
        ctx = super().get_context_data(**kwargs)
        request = self.request
        api = get_api_client(request)

        # --- фильтры API ---
        params: Dict[str, Any] = {}
        scope = (request.GET.get("view") or "").lower().strip()
        mine_raw = (request.GET.get("mine") or "").strip().lower()
        
        if scope == "mine" or mine_raw in {"1", "true", "yes", "on"}:
            params["view"] = "mine"
            scope = "mine"
        elif scope == "addressed":
            params["addressed_to_me"] = "true"
            scope = "addressed"
        else:
            scope = ""

        type_ = (request.GET.get("type") or "").strip()
        status_ = (request.GET.get("status") or "").strip()
        if type_:
            params["type"] = type_
        if status_:
            params["status"] = status_

        # NB: в API сортировки нет — параметр `ordering` не прокидываем.

        # --- список заявлений ---
        ok, data, status = _api_unpack(api.get("v1/requests/", params=params))
        if not ok:
            messages.error(
                request,
                data.get("detail")
                or f"Не удалось загрузить список заявлений (HTTP {status}).",
            )
            ctx.update(
                {
                    "requests": [],
                    "next_url": None,
                    "prev_url": None,
                    "count": None,
                    "scope": scope,
                    "can_process": _user_can_process_requests(request.user),
                    "filters": {
                        "type": type_,
                        "status": status_,
                        "view": scope,
                    },
                }
            )
            return ctx

        results, next_url, prev_url, count = _parse_page_payload(data)

        ctx.update(
            {
                "requests": results,
                "next_url": next_url,
                "prev_url": prev_url,
                "count": count,
                "scope": scope,
                "can_process": _user_can_process_requests(request.user),
                "filters": {
                    "type": type_,
                    "status": status_,
                    "view": scope,
                },
            }
        )

        # --- прицельная подгрузка комментариев к одному заявлению ---
        comments_for = request.GET.get("comments_for")
        if comments_for and str(comments_for).isdigit():
            ok_c, data_c, st_c = _api_unpack(
                api.get(f"v1/requests/{comments_for}/comments/")
            )
            if ok_c:
                comments, _, _, _ = _parse_page_payload(data_c)
                ctx.update(
                    {
                        "comments_for": int(comments_for),
                        "comments": comments,
                    }
                )
            else:
                messages.error(
                    request,
                    data_c.get("detail")
                    or f"Не удалось загрузить комментарии (HTTP {st_c}).",
                )
                ctx.update({"comments_for": int(comments_for), "comments": []})

        return ctx


class RequestDetailView(LoginRequiredMixin, TemplateView):
    """
    Детальный просмотр заявления.
    
    Загружает одно заявление и его комментарии через API.
    Может быть использовано как для отдельной страницы, так и для модального окна.
    
    GET /requests/{pk}/:
        - Загружает заявление через GET /api/v1/requests/{pk}/
        - Загружает комментарии через GET /api/v1/requests/{pk}/comments/
        - Проверяет права доступа (делает ошибку если нет прав)
    
    Контекст:
        - request_obj: dict с данными заявления
        - comments: list[dict] с комментариями
        - can_process: bool - может ли пользователь обрабатывать заявку
        - error: str - описание ошибки (если она была)
        - error_code: int - HTTP код ошибки
    """
    
    template_name = "requests_app/request_detail.html"
    
    def get_context_data(self, pk: int, **kwargs: Any) -> Dict[str, Any]:
        """
        Загружает данные заявления и комментарии.
        
        Args:
            pk: ID заявления
            
        Returns:
            Dict с контекстом для шаблона
        """
        ctx = super().get_context_data(**kwargs)
        request = self.request
        api = get_api_client(request)
        
        # Загружаем основные данные заявления
        ok, data, status = _api_unpack(api.get(f"v1/requests/{pk}/"))
        
        if not ok:
            # Обработка ошибок (404, 403 и т.д.)
            error_msg = data.get("detail", f"HTTP {status}")
            if isinstance(error_msg, list):
                error_msg = "; ".join(str(e) for e in error_msg)
            
            ctx.update({
                "request_obj": None,
                "comments": [],
                "can_process": _user_can_process_requests(request.user),
                "error": error_msg,
                "error_code": status,
            })
            return ctx
        
        request_data = data
        
        # Загружаем комментарии
        comments = []
        ok_c, data_c, st_c = _api_unpack(api.get(f"v1/requests/{pk}/comments/"))
        if ok_c:
            results_c, _, _, _ = _parse_page_payload(data_c)
            comments = _format_datetime_fields(
                results_c,
                fields=("created_at", "updated_at")
            )
        
        ctx.update({
            "request_obj": _format_datetime_fields([request_data], fields=("created_at", "updated_at", "decided_at"))[0],
            "comments": comments,
            "can_process": _user_can_process_requests(request.user),
        })
        
        return ctx


def request_comments(request: HttpRequest, pk: int) -> JsonResponse:
    """Прокси: список комментариев (JSON) для заявки.
    Требует авторизации (используем ту же обёртку клиента, что и основная вью).
    """
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication required"}, status=401)

    api = get_api_client(request)
    ok, data, st = _api_unpack(api.get(f"v1/requests/{pk}/comments/"))
    if not ok:
        return JsonResponse(data or {"detail": f"HTTP {st}"}, status=st)

    results, *_ = _parse_page_payload(data)
    return JsonResponse(results, safe=False)


def request_comment_add(request: HttpRequest, pk: int) -> JsonResponse:
    """Прокси: добавление комментария.
    POST: принимает form/multipart или JSON с полем text.
    """
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication required"}, status=401)

    text: str = ""
    ct = (request.content_type or "").split(";")[0].strip().lower()
    if ct == "application/json":
        try:
            import json as _json
            payload = _json.loads(request.body or b"{}")
            text = (payload.get("text") or "").strip()
        except Exception:
            text = ""
    else:
        text = (request.POST.get("text") or "").strip()

    if not text:
        return JsonResponse({"detail": "Empty comment"}, status=400)

    api = get_api_client(request)
    ok, data, st = _api_unpack(
        api.post(f"v1/requests/{pk}/comments/", json={"text": text})
    )
    if not ok and st != 201:
        return JsonResponse(data or {"detail": f"HTTP {st}"}, status=st)
    return JsonResponse(data, status=201)

def request_comment_delete(request: HttpRequest, pk: int, comment_id: int) -> JsonResponse:
    """Прокси: удаление комментария.
    
    DELETE /api/v1/requests/{pk}/comments/{comment_id}/
    
    Требует авторизации и проверяет права (только автор может удалить свой комментарий).
    """
    if request.method != "POST":
        return JsonResponse({"detail": "Method not allowed"}, status=405)
    if not request.user.is_authenticated:
        return JsonResponse({"detail": "Authentication required"}, status=401)

    api = get_api_client(request)
    ok, data, st = _api_unpack(
        api.delete(f"v1/requests/{pk}/comments/{comment_id}/")
    )
    
    if not ok:
        return JsonResponse(data or {"detail": f"HTTP {st}"}, status=st)
    
    return JsonResponse({"detail": "Comment deleted"}, status=204)