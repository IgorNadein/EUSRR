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
    """Страница списка документов.
    
    Все данные загружаются через JavaScript с использованием API.
    View только рендерит пустой шаблон с необходимыми URL'ами и правами пользователя.
    """

    template_name = "documents/document_list.html"

    def get_context_data(self, **kwargs: Any) -> Dict[str, Any]:
        """Формирует минимальный контекст для JavaScript-приложения.

        Returns:
            dict: Контекст с API URLs и правами пользователя.
        """
        ctx = super().get_context_data(**kwargs)
        user = self.request.user

        can_manage = _user_can_manage_documents(user)

        ctx.update(
            {
                "api_document_list_url": reverse("api:v1:documents-list"),
                "api_document_detail_base": reverse("api:v1:documents-list"),
                "acknowledge_url_template": reverse("documents:acknowledge", args=[0]).replace("/0/", "/{id}/"),
                "can_manage_documents": can_manage,
                "user_id": user.id,
                "perm_can_add": user.has_perm("documents.add_document") or user.is_staff,
                "perm_can_change": user.has_perm("documents.change_document") or user.is_staff,
                "perm_can_delete": user.has_perm("documents.delete_document") or user.is_staff,
            }
        )
        return ctx


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
