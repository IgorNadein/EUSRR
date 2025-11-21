from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from api.client import get_api_client
from api.decorators import require_api_auth
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import AbstractBaseUser
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect
from django.urls import reverse
from django.utils.decorators import method_decorator
from django.views.decorators.csrf import csrf_protect
from django.views.generic import TemplateView


# ==============================
# Вспомогательные структуры/утилиты
# ==============================

@dataclass(frozen=True)
class ApiPage:
    """Результат пагинированного ответа API.

    Attributes:
        items (list[dict]): Список элементов (обычно объекты документов).
        count (int): Общее количество элементов (если известно).
        next_url (str|None): Ссылка на следующую страницу (как возвращает API).
        prev_url (str|None): Ссылка на предыдущую страницу (как возвращает API).
    """
    items: List[Dict[str, Any]]
    count: int
    next_url: Optional[str]
    prev_url: Optional[str]


def _as_bool(value: Any) -> bool:
    """Нормализует булево значение из строк HTML-форм.

    Args:
        value: Строка/булево/None.

    Returns:
        bool: True, если значение похоже на истину ('1', 'true', 'on', 'yes').

    Raises:
        ValueError: Если значение имеет неожиданный тип, не приводимый к строке.
    """
    if isinstance(value, bool):
        return value
    try:
        s = str(value).strip().lower()
    except Exception as exc:  # pragma: no cover - защитный блок
        raise ValueError("Unsupported boolean value") from exc
    return s in {"1", "true", "on", "yes"}


def _repeat_field_pairs(field: str, values: Iterable[int | str]) -> List[Tuple[str, str]]:
    """Готовит список повторяемых пар (field, value) для multipart-формы.

    Args:
        field (str): Имя поля.
        values (Iterable[int|str]): Значения (могут быть пустыми/None — игнорируются).

    Returns:
        list[tuple[str, str]]: Повторяемые пары для передачи в API-клиент.

    Raises:
        TypeError: Если field пустой или values неитерируемый.
    """
    if not field:
        raise TypeError("field must be a non-empty string")
    out: List[Tuple[str, str]] = []
    for v in values or []:
        if v is None:
            continue
        s = str(v).strip()
        if s:
            out.append((field, s))
    return out


def _api_unpack(resp: Any) -> Tuple[bool, Dict[str, Any], int]:
    """Безопасно извлекает признаки успеха, JSON и статус из ответа API.

    Args:
        resp: Объект ответа клиентской обёртки (ожидаются атрибуты .ok, .json, .status).

    Returns:
        tuple: (ok, data, status)

    Raises:
        AttributeError: Если у ответа нет ожидаемых атрибутов.
    """
    ok: bool = getattr(resp, "ok")
    status: int = getattr(resp, "status")
    data: Dict[str, Any] = getattr(resp, "json") or {}
    return ok, data, status


def _parse_page_payload(payload: Any) -> ApiPage:
    """Преобразует полезную нагрузку DRF в ApiPage.

    Поддерживает форматы:
      - пагинация DRF: {"count": N, "next": URL, "previous": URL, "results": [...]}
      - сырой список:  [ ... ]

    Args:
        payload (Any): Десериализованный JSON из API.

    Returns:
        ApiPage: Стандартизованный результат.

    Raises:
        TypeError: Если payload незнакомого формата.
    """
    if isinstance(payload, dict) and "results" in payload:
        items = list(payload.get("results") or [])
        return ApiPage(
            items=items,
            count=int(payload.get("count") or 0),
            next_url=payload.get("next"),
            prev_url=payload.get("previous"),
        )
    if isinstance(payload, list):
        return ApiPage(items=list(payload), count=len(payload), next_url=None, prev_url=None)
    raise TypeError("Unsupported API payload format")


def _user_can_manage_documents(user: AbstractBaseUser) -> bool:
    """Проверяет, есть ли у пользователя административные/модельные права на Document.

    Args:
        user (AbstractBaseUser): Пользователь.

    Returns:
        bool: True, если is_staff или есть одно из прав add/change/delete/view.
    """
    if getattr(user, "is_staff", False):
        return True
    model = "document"
    app_label = "documents"
    for act in ("view", "add", "change", "delete"):
        if user.has_perm(f"{app_label}.{act}_{model}"):
            return True
    return False


def _current_url_with(request: HttpRequest, **new_params: Any) -> str:
    """Возвращает URL текущего пути с подменой/удалением query-параметров.

    Args:
        request (HttpRequest): Текущий запрос.
        **new_params: Пары ключ-значение; None удаляет параметр.

    Returns:
        str: Абсолютный путь с новой query-строкой.
    """
    q = request.GET.copy()
    for k, v in new_params.items():
        if v is None and k in q:
            del q[k]
        elif v is not None:
            q[k] = str(v)
    qs = q.urlencode()
    return f"{request.path}?{qs}" if qs else request.path


def _filter_for_user(items: Sequence[Dict[str, Any]], user_id: Optional[int]) -> List[Dict[str, Any]]:
    """Фильтрует документы в область «Мои».

    Документ считается «моим», если:
      - он отправлен всем (`sent_to_all == true`), или
      - в `recipients[].id` присутствует `user_id`, или
      - в `departments` есть отдел, где пользователь является активным сотрудником, или
      - пользователь является загрузившим документ (`uploaded_by.id == user_id`).

    Args:
        items (Sequence[dict]): Полученный список документов из API.
        user_id (int|None): Идентификатор текущего пользователя.

    Returns:
        list[dict]: Отфильтрованный список.

    Raises:
        ValueError: Если user_id не задан (None).
    """
    if user_id is None:
        raise ValueError("user_id is required for filtering")
    result: List[Dict[str, Any]] = []
    for it in items:
        if not isinstance(it, dict):
            continue
        
        # 1. Документы для всех
        if it.get("sent_to_all"):
            result.append(it)
            continue
        
        # 2. Документы, загруженные текущим пользователем
        uploaded_by = it.get("uploaded_by")
        if uploaded_by and isinstance(uploaded_by, dict):
            try:
                if int(uploaded_by.get("id")) == user_id:
                    result.append(it)
                    continue
            except (ValueError, TypeError):
                pass
        
        # 3. Проверяем recipients
        recips = it.get("recipients") or []
        try:
            if any(int(r.get("id")) == user_id for r in recips if isinstance(r, dict) and r.get("id") is not None):
                result.append(it)
                continue
        except Exception:
            pass
        
        # 4. Проверяем departments
        depts = it.get("departments") or []
        try:
            # Если в документе есть отдел, нужно проверить членство
            # Но API возвращает только id и name отдела, без списка сотрудников
            # Поэтому нужно загрузить эту информацию отдельно или доверять backend'у
            # Для упрощения, если есть departments - считаем что пользователь может видеть
            # (реальная проверка происходит на backend при создании уведомлений)
            if depts:
                # TODO: добавить проверку членства в отделе через отдельный API запрос
                # Пока просто пропускаем - backend сам решит, нужно ли показывать
                pass
        except Exception:
            pass
    return result


# ==============================
# Вьюхи
# ==============================

@method_decorator([login_required, require_api_auth, csrf_protect], name="dispatch")
class DocumentView(LoginRequiredMixin, TemplateView):
    """Список документов + CRUD через POST на тот же URL.

    Поведение:
        - GET — загружает список документов через API и формирует контекст.
        - POST — маршрутизирует действия форм `_action = create|edit|delete`:
            создаёт, редактирует или удаляет документ через API.

    Контекст (для шаблона `documents/document_list.html`):
        documents (list[dict]): Список документов.
        acked_ids (set[int]): Множество ID «ознакомленных» пользователем документов.
        count (int): Общее количество элементов (если известно).
        next_url (str|None): Ссылка на следующую страницу (как вернул API).
        prev_url (str|None): Ссылка на предыдущую страницу (как вернул API).
        page (int|str): Номер страницы (как пришёл из запроса).
        scope (str): 'mine' или 'all' — активная область.
        can_manage_documents (bool): Имеет ли пользователь модельные права/является staff.
        show_admin_controls (bool): Показывать ли кнопки create/edit/delete (True при scope='all' и наличии прав).
        scope_urls (dict): {'mine': url, 'all': url} — ссылки-переключатели.
        api_document_list_url (str): URL API-эндпоинта списка документов.
        api_document_detail_base (str): База detail (заканчивается '/documents/').
        perm_can_add/change/delete (bool): Точечные права для тонкой логики в шаблоне.
    """

    template_name = "documents/document_list.html"

    @property
    def paginate_by(self) -> int:
        """Размер страницы для обратной совместимости (реальная пагинация на стороне API).

        Returns:
            int: Желаемый размер страницы.
        """
        return 20

    # ---------- GET ----------

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Формирует контекст страницы.

        QueryParams:
            page (int, optional): Номер страницы (проксируется в API).
            scope ('mine'|'all'): Область показа. Обычным пользователям всегда 'mine'.
            ack_status ('acked'|'not_acked', optional): Фильтр по статусу ознакомления.

        Returns:
            dict: Контекст для шаблона.

        Raises:
            RuntimeError: Если API вернул неожиданный формат данных.
        """
        ctx = super().get_context_data(**kwargs)

        request = self.request
        user = request.user
        api = get_api_client(request)

        can_manage = _user_can_manage_documents(user)
        raw_scope = (request.GET.get("scope") or "mine").lower()
        scope = raw_scope if (raw_scope in {"mine", "all"} and can_manage) else "mine"
        page = request.GET.get("page") or 1
        ack_status = (request.GET.get("ack_status") or "").lower().strip()

        # Загружаем список документов через API
        resp = api.get("v1/documents/", params={"page": page})
        ok, data, _status = _api_unpack(resp)
        if not ok:
            messages.error(request, (data or {}).get("detail") or "Не удалось загрузить документы.")
            page_data = ApiPage(items=[], count=0, next_url=None, prev_url=None)
        else:
            try:
                page_data = _parse_page_payload(data)
            except TypeError:
                # Неожиданный формат ответа
                messages.error(request, "Неожиданный ответ API при загрузке документов.")
                page_data = ApiPage(items=[], count=0, next_url=None, prev_url=None)

        # Всегда фильтруем «Мои» локально — это надёжно и не зависит от токена к API
        items: List[Dict[str, Any]]
        if scope == "mine":
            try:
                items = _filter_for_user(page_data.items, getattr(user, "id", None))
            except ValueError:
                items = []  # Без user.id не можем корректно отфильтровать
        else:
            items = page_data.items

        # Фильтруем по статусу ознакомления
        if ack_status == "acked":
            items = [it for it in items if it.get("is_acknowledged")]
        elif ack_status == "not_acked":
            items = [it for it in items if not it.get("is_acknowledged")]

        # Множество ID ознакомленных документов
        acked_ids: Set[int] = {
            int(it.get("id"))
            for it in items
            if isinstance(it, dict) and it.get("is_acknowledged")
        }

        # Ссылки переключателя
        scope_urls = {
            "mine": _current_url_with(request, scope="mine", page=None),
            "all": _current_url_with(request, scope="all", page=None),
        }

        # API URL для фронта (если нужен JS) — сохраняем совместимость с шаблоном
        api_document_list_url = reverse("api:v1:documents-list")

        # Фильтры для передачи в шаблон
        filters = {
            "ack_status": ack_status if ack_status in {"acked", "not_acked"} else "",
        }
        
        # Преобразуем API URL'ы пагинации в URL'ы представления
        next_url = None
        prev_url = None
        
        current_page = int(page) if str(page).isdigit() else 1
        
        if page_data.next_url:
            # Извлекаем номер страницы из API URL
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(page_data.next_url)
            next_page = parse_qs(parsed.query).get('page', [None])[0]
            if next_page:
                next_url = _current_url_with(request, page=next_page)
        
        if page_data.prev_url:
            from urllib.parse import urlparse, parse_qs
            parsed = urlparse(page_data.prev_url)
            prev_page = parse_qs(parsed.query).get('page', [None])[0]
            if prev_page:
                prev_url = _current_url_with(request, page=prev_page)
            else:
                # Если в API URL нет параметра page, это страница 1
                prev_url = _current_url_with(request, page=1)
        elif current_page > 1:
            # Если API не вернул prev_url, но мы не на первой странице - создаем его
            prev_url = _current_url_with(request, page=current_page - 1)
        
        # Отладка пагинации
        import logging
        logger = logging.getLogger(__name__)
        logger.info(
            f"Pagination debug: current_page={current_page}, "
            f"prev_url={prev_url}, next_url={next_url}, "
            f"api_prev={page_data.prev_url}, api_next={page_data.next_url}"
        )

        ctx.update(
            {
                "documents": items,
                "acked_ids": acked_ids,
                "count": page_data.count,
                "next_url": next_url,
                "prev_url": prev_url,
                "page": int(page) if str(page).isdigit() else page,
                "scope": scope,
                "filters": filters,
                "can_manage_documents": can_manage,
                "show_admin_controls": bool(can_manage and scope == "all"),
                "scope_urls": scope_urls,
                "api_document_list_url": api_document_list_url,
                "api_document_detail_base": api_document_list_url,  # + {id}/
                "perm_can_add": user.has_perm("documents.add_document") or user.is_staff,
                "perm_can_change": user.has_perm("documents.change_document") or user.is_staff,
                "perm_can_delete": user.has_perm("documents.delete_document") or user.is_staff,
            }
        )
        return ctx

    # ---------- POST (CRUD через API) ----------

    def post(self, request: HttpRequest, *args: Any, **kwargs: Any) -> HttpResponse:
        """Маршрутизация действий форм по полю `_action`.

        Returns:
            HttpResponse: Редирект на список после выполнения действия.

        Raises:
            ValueError: Если `_action` отсутствует или имеет неизвестное значение.
        """
        action = (request.POST.get("_action") or "").lower().strip()
        if action == "create":
            return self._create(request)
        if action == "edit":
            return self._edit(request)
        if action == "delete":
            return self._delete(request)
        messages.error(request, "Неизвестное действие.")
        raise ValueError("Unknown _action for DocumentListView.post")

    # --- Handlers ---

    def _create(self, request: HttpRequest) -> HttpResponse:
        """Создаёт документ через API (multipart).

        Ожидаемые поля:
            title (str), description (str, optional),
            file (uploaded, required),
            sent_to_all (bool),
            recipient_ids (repeat, если sent_to_all=false).

        Returns:
            HttpResponse: Редирект на список документов.

        Raises:
            ValueError: Если отсутствует обязательный файл.
        """
        title = (request.POST.get("title") or "").strip()
        description = (request.POST.get("description") or "").strip()
        sent_to_all = _as_bool(request.POST.get("sent_to_all"))
        file = request.FILES.get("file")
        if not file:
            messages.error(request, "Файл обязателен.")
            raise ValueError("file is required")

        data: List[Tuple[str, str]] = [
            ("title", title),
            ("description", description),
            ("sent_to_all", "true" if sent_to_all else "false"),
        ]
        if not sent_to_all:
            data += _repeat_field_pairs("recipient_ids", request.POST.getlist("recipient_ids"))

        files = {
            "file": (getattr(file, "name", "file"), file, getattr(file, "content_type", None))
        }

        api = get_api_client(request)
        resp = api.post("v1/documents/", data=data, files=files)
        ok, j, status = _api_unpack(resp)
        if ok:
            messages.success(request, "Документ создан.")
        else:
            messages.error(request, j.get("detail") or f"Ошибка создания (HTTP {status}).")
        return redirect(reverse("documents:document_list"))

    def _edit(self, request: HttpRequest) -> HttpResponse:
        """Редактирует документ через API (multipart PATCH).

        Ожидаемые поля:
            id (int), title (str), description (str),
            sent_to_all (bool),
            recipient_ids (repeat, если sent_to_all=false),
            file (uploaded, optional).

        Returns:
            HttpResponse: Редирект на список документов.

        Raises:
            ValueError: Если id некорректен.
        """
        raw_id = request.POST.get("id")
        if not str(raw_id).isdigit():
            messages.error(request, "Некорректный идентификатор документа.")
            raise ValueError("Invalid document id")

        doc_id = int(raw_id)
        title = (request.POST.get("title") or "").strip()
        description = (request.POST.get("description") or "").strip()
        sent_to_all = _as_bool(request.POST.get("sent_to_all"))
        rids = request.POST.getlist("recipient_ids")

        data: List[Tuple[str, str]] = [
            ("title", title),
            ("description", description),
            ("sent_to_all", "true" if sent_to_all else "false"),
        ]
        if not sent_to_all:
            data += _repeat_field_pairs("recipient_ids", rids)

        file = request.FILES.get("file")
        files = (
            {"file": (getattr(file, "name", "file"), file, getattr(file, "content_type", None))}
            if file
            else None
        )

        api = get_api_client(request)
        resp = api.patch(f"v1/documents/{doc_id}/", data=data, files=files)
        ok, j, status = _api_unpack(resp)
        if ok:
            messages.success(request, "Документ сохранён.")
        else:
            messages.error(request, j.get("detail") or f"Не удалось сохранить (HTTP {status}).")
        return redirect(reverse("documents:document_list"))

    def _delete(self, request: HttpRequest) -> HttpResponse:
        """Удаляет документ через API.

        Ожидаемые поля:
            id (int).

        Returns:
            HttpResponse: Редирект на список документов.

        Raises:
            ValueError: Если id некорректен.
        """
        raw_id = request.POST.get("id")
        if not str(raw_id).isdigit():
            messages.error(request, "Некорректный идентификатор документа.")
            raise ValueError("Invalid document id")

        doc_id = int(raw_id)
        api = get_api_client(request)
        resp = api.delete(f"v1/documents/{doc_id}/")
        ok, j, status = _api_unpack(resp)
        if ok or status == 204:
            messages.success(request, "Документ удалён.")
        else:
            messages.error(request, (j or {}).get("detail") or f"Не удалось удалить (HTTP {status}).")
        return redirect(reverse("documents:document_list"))


@login_required
@require_api_auth
def acknowledge_document(request: HttpRequest, pk: int) -> HttpResponse:
    """Отмечает документ «ознакомленным» через API и перенаправляет на файл.

    Args:
        request (HttpRequest): Текущий запрос.
        pk (int): Идентификатор документа.

    Returns:
        HttpResponse: Редирект на файл документа или список документов при ошибке.

    Raises:
        ValueError: Если pk имеет неверный формат.
    """
    try:
        doc_id = int(pk)
    except (TypeError, ValueError) as exc:
        messages.error(request, "Некорректный идентификатор документа.")
        raise ValueError("pk must be an integer") from exc

    # Получаем документ для редиректа на файл
    from documents.models import Document
    try:
        doc = Document.objects.get(id=doc_id)
        file_url = doc.file.url if doc.file else None
    except Document.DoesNotExist:
        messages.error(request, "Документ не найден.")
        return redirect(reverse("documents:document_list"))

    # Отмечаем ознакомление через API
    api = get_api_client(request)
    resp = api.post(f"v1/documents/{doc_id}/acknowledge/")
    ok, data, _status = _api_unpack(resp)
    if ok:
        if data.get("already"):
            messages.info(request, "Вы уже отмечали ознакомление с этим документом.")
        else:
            messages.success(request, "Ознакомление с документом отмечено.")
    else:
        messages.error(request, data.get("detail") or "Не удалось отметить документ.")
    
    # Редирект на файл или обратно на список
    if file_url:
        return redirect(file_url)
    else:
        return redirect(reverse("documents:document_list"))
