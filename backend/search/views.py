# backend/search/views.py
from __future__ import annotations

from typing import Any, Dict, List, Literal, TypedDict, Optional, Tuple

from django.contrib.auth.decorators import login_required
from django.core.exceptions import FieldError
from django.db.models import Q, QuerySet
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render
from django.utils.html import escape

from feed.models import Post
from employees.models import Employee, Department
from requests_app.models import Request


class SearchItem(TypedDict):
    """Элемент единой выдачи поиска.

    Attributes:
        model_name (Literal["post","employee","department","request","chat","message","event"]):
            Тип найденной сущности.
        object (Any): Экземпляр модели, который будет отрисован в шаблоне.
    """

    model_name: Literal[
        "post", "employee", "department", "request", "chat", "message", "event"
    ]
    object: Any


# ------------------------ ВСПОМОГАТЕЛЬНЫЕ УТИЛИТЫ ------------------------


def _is_hr(user: Employee) -> bool:
    """Проверяет расширенные права на просмотр заявлений.

    Args:
        user (Employee): Текущий пользователь.

    Returns:
        bool: True, если пользователь может видеть все заявления.

    Notes:
        Используются пермишены из requests_app.
    """
    return user.has_perm("requests_app.can_view_all_requests") or user.has_perm(
        "requests_app.can_process_requests"
    )


def _try_extend_q(model_cls: type, base_q: Q, lookups: List[Tuple[str, Any]]) -> Q:
    """Пытается добавить условия в Q, аккуратно игнорируя несуществующие поля.

    Для каждого пути из lookups пытаемся выполнить пустой фильтр, чтобы проверить валидность.
    Неудачные пути (FieldError) игнорируем.

    Args:
        model_cls (type): Класс модели, к которой будет применён Q.
        base_q (Q): Исходное условие.
        lookups (List[Tuple[str, Any]]): Список пар (путь_к_полю, значение).

    Returns:
        Q: Итоговое условие с добавленными (валидными) частями.
    """
    q = Q(base_q)
    from django.db.models import QuerySet as _QS  # локальный импорт для mypy

    qs: _QS = model_cls.objects.all()
    for path, value in lookups:
        try:
            # проверяем валидность пути: попытаемся составить запрос
            _ = qs.filter(**{path: value}).values("pk")[:1]
            q |= Q(**{path: value})
        except FieldError:
            continue
    return q


def _order_by_first_valid(qs: QuerySet, fields: List[str]) -> QuerySet:
    """Сортирует QS по первому валидному полю, иначе возвращает как есть.

    Args:
        qs (QuerySet): Исходный QS.
        fields (List[str]): Список полей приоритета сортировки.

    Returns:
        QuerySet: Отсортированный QS или оригинал.
    """
    for f in fields:
        try:
            test = qs.order_by(f)
            # прогрев запроса для раннего исключения FieldError
            _ = test.values("pk")[:0]
            return test
        except FieldError:
            continue
    return qs


# ----------------------------- ОСНОВНЫЕ ПОИСКИ -----------------------------


def _search_posts(query: str) -> QuerySet[Post]:
    """Поиск по постам (title/body).

    Args:
        query (str): Строка запроса.

    Returns:
        QuerySet[Post]: Отсортированный QS.
    """
    if not query:
        return Post.objects.none()
    return (
        Post.objects.filter(Q(title__icontains=query) | Q(body__icontains=query))
        .only("id", "title", "body", "created_at")
        .order_by("-created_at")
    )


def _search_employees(query: str) -> QuerySet[Employee]:
    """Поиск по сотрудникам (ФИО/контакты + принадлежность к отделам + навыки).

    Ищем:
      - ФИО, email, телефон
      - Принадлежность к отделам (по названию отдела) через EmployeeDepartment
      - Навыки (по названию навыка)

    Args:
        query (str): Строка запроса.

    Returns:
        QuerySet[Employee]: Отсортированный QS без дублей.

    Raises:
        ValueError: Если query пустая строка после trim (обрабатывается возвратом .none()).
    """
    if not query:
        return Employee.objects.none()

    fio_contacts = (
        Q(last_name__icontains=query)
        | Q(first_name__icontains=query)
        | Q(patronymic__icontains=query)
        | Q(email__icontains=query)
        | Q(phone_number__icontains=query)
    )

    # 🔹 ВАЖНО: у вас связь через EmployeeDepartment → departments_links
    dept_lookups = [
        ("departments_links__department__name__icontains", query),
    ]
    # Навыки — прямая M2M
    skill_lookups = [
        ("skills__name__icontains", query),
    ]

    q = _try_extend_q(Employee, fio_contacts, dept_lookups)
    q = _try_extend_q(Employee, q, skill_lookups)

    return (
        Employee.objects.filter(q)
        .distinct()
        .select_related("position")
        .only(
            "id",
            "last_name",
            "first_name",
            "patronymic",
            "email",
            "phone_number",
            "position__name",
        )
        .order_by("last_name", "first_name")
    )


def _search_departments(query: str) -> QuerySet[Department]:
    """Поиск по отделам (название/описание/руководитель + сотрудники отдела).

    Ищем:
      - name / description
      - head (ФИО)
      - сотрудники отдела (ФИО/e-mail/телефон) — через Department.employeedepartment → employee

    Args:
        query (str): Строка запроса.

    Returns:
        QuerySet[Department]: Отсортированный QS без дублей.
    """
    if not query:
        return Department.objects.none()

    base = Q(name__icontains=query) | Q(description__icontains=query)
    base |= (
        Q(head__last_name__icontains=query)
        | Q(head__first_name__icontains=query)
        | Q(head__patronymic__icontains=query)
    )

    # 🔹 ВАЖНО: правильный reverse related_name — "employeedepartment"
    member_fields = [
        "last_name__icontains",
        "first_name__icontains",
        "patronymic__icontains",
        "email__icontains",
        "phone_number__icontains",
    ]
    member_lookups = [
        (f"employeedepartment__employee__{f}", query) for f in member_fields
    ]

    q = _try_extend_q(Department, base, member_lookups)

    return (
        Department.objects.filter(q)
        .distinct()
        .select_related("head")
        .only("id", "name", "description", "head")
        .order_by("name")
    )


def _search_events(query: str) -> QuerySet[Any]:
    """Поиск по календарным событиям (ваша модель: calendar_app.CalendarEvent).

    Args:
        query (str): Строка запроса.

    Returns:
        QuerySet[Any]: QS CalendarEvent или пустой QS при отсутствии приложения.
    """
    try:
        from calendar_app.models import CalendarEvent as EventModel  # type: ignore
    except Exception:
        return Post.objects.none()

    if not query:
        return EventModel.objects.none()

    q = Q(title__icontains=query) | Q(description__icontains=query)
    q |= Q(department__name__icontains=query)
    # других связей (owner/participants) в вашей модели нет

    qs = EventModel.objects.filter(q).distinct()
    # Поля дат у вас: start_date/start_time (+ end_*). Сортируем по началу.
    qs = qs.order_by("-start_date", "-start_time", "-id")
    try:
        qs = qs.select_related("department")
    except Exception:
        pass
    return qs


def _search_requests(query: str, user: Employee, is_hr: bool) -> QuerySet[Request]:
    """Поиск по заявлениям с учётом прав.

    Args:
        query (str): Строка запроса.
        user (Employee): Текущий пользователь.
        is_hr (bool): Признак расширенных прав.

    Returns:
        QuerySet[Request]: Отсортированный QS.

    Raises:
        ValueError: Если user не передан.
    """
    if not user:
        raise ValueError("user is required")

    base = (
        Request.objects.filter(
            Q(title__icontains=query)
            | Q(employee__last_name__icontains=query)
            | Q(employee__first_name__icontains=query)
            | Q(employee__patronymic__icontains=query)
            | Q(department__name__icontains=query)
        )
        if query
        else Request.objects.none()
    )

    if not is_hr:
        base = base.filter(employee=user)

    # Если используем select_related по FK — перечисляем их в only(...)
    return (
        base.select_related("employee", "department", "approver")
        .only(
            "id",
            "title",
            "status",
            "employee",
            "department",
            "approver",
            "created_at",
        )
        .order_by("-created_at")
    )


def _search_chats(query: str) -> QuerySet[Any]:
    """Поиск по чатам (название/участники/отдел).

    Args:
        query (str): Строка запроса.

    Returns:
        QuerySet[Any]: QS Chat или пустой QS, если приложение чатов отсутствует.

    Notes:
        Безопасно обрабатывает разные схемы (name/department/participants).
    """
    try:
        from communications.models import Chat  # type: ignore
    except Exception:
        return Post.objects.none()  # тип «пустой» QS (любой модели)

    if not query:
        return Chat.objects.none()

    q = Q()
    # Попробуем разные пути без падения
    q = _try_extend_q(
        Chat,
        q,
        [
            ("name__icontains", query),
            ("title__icontains", query),
            ("department__name__icontains", query),
            ("participants__last_name__icontains", query),
            ("participants__first_name__icontains", query),
            ("participants__patronymic__icontains", query),
            ("participants__email__icontains", query),
        ],
    )

    qs = Chat.objects.filter(q).distinct()
    qs = _order_by_first_valid(qs, ["-updated_at", "-last_message_at", "-id"])
    # мягкая оптимизация
    try:
        qs = qs.select_related("department")
    except FieldError:
        pass
    try:
        qs = qs.prefetch_related("participants")
    except FieldError:
        pass
    return qs


def _search_messages(query: str) -> QuerySet[Any]:
    """Поиск по сообщениям чатов (контент/автор/чат).

    Args:
        query (str): Строка запроса.

    Returns:
        QuerySet[Any]: QS Message или пустой QS, если приложение чатов отсутствует.
    """
    try:
        from communications.models import Message  # type: ignore
    except Exception:
        return Post.objects.none()

    if not query:
        return Message.objects.none()

    q = Q(content__icontains=query)
    q = _try_extend_q(
        Message,
        q,
        [
            ("author__last_name__icontains", query),
            ("author__first_name__icontains", query),
            ("author__patronymic__icontains", query),
            ("chat__name__icontains", query),
            ("chat__title__icontains", query),
            ("chat__department__name__icontains", query),
        ],
    )

    qs = Message.objects.filter(q).distinct()
    qs = _order_by_first_valid(qs, ["-created_at", "-id"])
    try:
        qs = qs.select_related("author", "chat")
    except FieldError:
        pass
    return qs


# -------------------------------- ВЬЮХА --------------------------------


@login_required
def search_view(request: HttpRequest) -> HttpResponse:
    """Единый поиск по системе (посты, сотрудники, отделы, заявления, чаты, сообщения, события).

    Args:
        request (HttpRequest): Запрос (`GET["q"]`).

    Returns:
        HttpResponse: Рендер `templates/search/results.html` с плоским списком.

    Контекст шаблона:
        - query: str — исходная строка запроса
        - results: List[SearchItem] — плоский список элементов
        - counts: Dict[str, int] — счётчики по типам:
            keys: post, employee, department, request, chat, message, event
        - total: int — сумма всех счётчиков
    """
    raw_q = request.GET.get("q", "") or ""
    query = escape(raw_q.strip())

    items: List[SearchItem] = []
    counts: Dict[str, int] = {
        "post": 0,
        "employee": 0,
        "department": 0,
        "request": 0,
        "chat": 0,
        "message": 0,
        "event": 0,
    }

    if query:
        # --- Посты
        post_qs = _search_posts(query)
        counts["post"] = post_qs.count()
        items.extend({"model_name": "post", "object": p} for p in post_qs[:10])

        # --- Сотрудники (ФИО/контакты + отделы + навыки)
        emp_qs = _search_employees(query)
        counts["employee"] = emp_qs.count()
        items.extend({"model_name": "employee", "object": e} for e in emp_qs[:10])

        # --- Отделы (в т.ч. по сотрудникам)
        dept_qs = _search_departments(query)
        counts["department"] = dept_qs.count()
        items.extend({"model_name": "department", "object": d} for d in dept_qs[:10])

        # --- Заявления (учёт прав)
        is_hr = _is_hr(request.user)  # type: ignore[arg-type]
        req_qs = _search_requests(query, request.user, is_hr)  # type: ignore[arg-type]
        counts["request"] = req_qs.count()
        items.extend({"model_name": "request", "object": r} for r in req_qs[:10])

        # --- Чаты
        chat_qs = _search_chats(query)
        # Если приложение отсутствует — chat_qs будет пустым QS другой модели, count()=0
        try:
            counts["chat"] = chat_qs.count()
        except Exception:
            counts["chat"] = 0
        items.extend({"model_name": "chat", "object": c} for c in chat_qs[:10])

        # --- Сообщения
        msg_qs = _search_messages(query)
        try:
            counts["message"] = msg_qs.count()
        except Exception:
            counts["message"] = 0
        items.extend({"model_name": "message", "object": m} for m in msg_qs[:10])

        # --- Календарные события
        evt_qs = _search_events(query)
        try:
            counts["event"] = evt_qs.count()
        except Exception:
            counts["event"] = 0
        items.extend({"model_name": "event", "object": ev} for ev in evt_qs[:10])

    ctx = {
        "query": query,
        "results": items,
        "counts": counts,
        "total": sum(counts.values()),
    }
    return render(request, "search/results.html", ctx)
