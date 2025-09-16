# backend/requests_app/views.py
import logging
import time
from datetime import datetime

from django.conf import settings
from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.core.paginator import EmptyPage, PageNotAnInteger, Paginator
from django.db import transaction
from django.db.models import Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_http_methods

from .constants import ALLOWED_SORTS_ALL, MAX_COMMENT_LEN, PAGINATE_ALL, PAGINATE_MY
from .forms import RequestForm, RequestStatusForm
from .models import Request, RequestComment

logger = logging.getLogger(__name__)

# ---- Опционально: django-ratelimit (лучше для прод-нагрузки)
try:
    from ratelimit.decorators import ratelimit  # type: ignore

    RATE_LIMIT_AVAILABLE = True
except Exception:
    RATE_LIMIT_AVAILABLE = False
    logger.warning(
        "django-ratelimit не установлен: включён упрощённый cache-rate-limit fallback. "
        "Поставьте django-ratelimit + Redis для защищённой работы под нагрузкой."
    )

    def ratelimit(*_, **__):  # no-op для отсутствующего пакета
        def _noop(view):
            return view

        return _noop


# ---------- Rate-limit cache fallback (fixed-window, атомарный incr, без локов) ----------
def _client_ident(request) -> str:
    """
    user:<id> для аутентифицированных; ip:<addr> для гостей.
    Если REMOTE_ADDR — доверенный прокси (settings.TRUSTED_PROXIES), берём первый IP из X-Forwarded-For.
    Иначе — REMOTE_ADDR. Для продакшена рекомендуем real-ip middleware/ingress.
    """
    user = getattr(request, "user", None)
    if user and user.is_authenticated:
        return f"user:{user.pk}"

    remote = request.META.get("REMOTE_ADDR", "anon")
    xff = request.META.get("HTTP_X_FORWARDED_FOR")
    trusted = set(getattr(settings, "TRUSTED_PROXIES", []))

    if xff and remote in trusted:
        # стандартный формат: "client, proxy1, proxy2, ..."
        ip = xff.split(",")[0].strip()
    else:
        ip = remote
    return f"ip:{ip}"


def cache_rate_limit_fixed_window(window_sec: int, max_hits: int, name: str):
    """
    Fixed-window счётчик, ключ привязан к «слоту» времени:
      slot = int(now / window)
      key = f"rl:{name}:{ident}:{slot}"
    - Первая запись — cache.add(key, 1, timeout=window)
    - Дальше — cache.incr(key, 1) (атомарно для locmem/memcached/redis)
    - При превышении — 429
    Без каких-либо ретраев/локов → не блокирует воркеры под нагрузкой.
    """

    def _decorator(view):
        def _wrapped(request, *args, **kwargs):
            ident = _client_ident(request)
            now = int(time.time())
            slot = now // window_sec
            key = f"rl:{name}:{ident}:{slot}"

            # инициализация ведра
            if cache.add(key, 1, timeout=window_sec):
                return view(request, *args, **kwargs)

            # атомарное инкрементирование (если backend поддерживает)
            try:
                count = cache.incr(key, 1)  # type: ignore[no-untyped-call]
            except Exception:
                # крайней случай: backend без incr → считаем, что лимит исчерпан
                logger.warning(
                    "Cache backend не поддерживает incr — fallback RL менее надёжен."
                )
                return HttpResponse(status=429)

            if count > max_hits:
                return HttpResponse(status=429)
            return view(request, *args, **kwargs)

        return _wrapped

    return _decorator


def maybe_cache_rl(window_sec: int, max_hits: int, name: str):
    """Включаем cache-fallback только если нет django-ratelimit."""

    def _decorator(view):
        if RATE_LIMIT_AVAILABLE:
            return view
        return cache_rate_limit_fixed_window(window_sec, max_hits, name)(view)

    return _decorator


# ---------- Константы / QuerySets ----------

VALID_STATUSES = {s for s, _ in Request.STATUS_CHOICES}
VALID_TYPES = {t for t, _ in Request.TYPE_CHOICES}

COMMENTS_PREFETCH = Prefetch(
    "comments",
    queryset=RequestComment.objects.select_related("author").order_by("created_at"),
)

BASE_REQUEST_QS = Request.objects.select_related("employee", "approver", "department")
DETAIL_REQUEST_QS = BASE_REQUEST_QS.prefetch_related(COMMENTS_PREFETCH)


# ---------- Права ----------
def is_hr(user) -> bool:
    return user.is_staff or user.groups.filter(name="HR").exists()


def is_department_head(user) -> bool:
    return user.headed_departments.exists()


def is_hr_or_head(user) -> bool:
    return is_hr(user) or is_department_head(user)


def get_allowed_request_qs(user):
    """HR — все; руководитель — заявки сотрудников своих отделов."""
    if is_hr(user):
        return BASE_REQUEST_QS
    return BASE_REQUEST_QS.filter(
        employee__departments_links__department__head=user
    ).distinct()


# ---------- Утилиты ----------
def _parse_date(value: str | None):
    if not value:
        return None
    try:
        return datetime.strptime(value, "%Y-%m-%d").date()
    except ValueError:
        return None


def _apply_filters(qs, request, *, for_all: bool):
    errors: list[str] = []

    status = request.GET.get("status")
    if status and status in VALID_STATUSES:
        qs = qs.filter(status=status)

    rtype = request.GET.get("type")
    if rtype and rtype in VALID_TYPES:
        qs = qs.filter(type=rtype)

    raw_from = request.GET.get("from", "")
    raw_to = request.GET.get("to", "")
    d_from = _parse_date(raw_from) if raw_from else None
    d_to = _parse_date(raw_to) if raw_to else None

    if raw_from and not d_from:
        errors.append("Неверный формат даты 'from' (YYYY-MM-DD).")
    if raw_to and not d_to:
        errors.append("Неверный формат даты 'to' (YYYY-MM-DD).")

    if d_from:
        qs = qs.filter(created_at__date__gte=d_from)
    if d_to:
        qs = qs.filter(created_at__date__lte=d_to)

    sort = request.GET.get("sort") if for_all else None
    if for_all:
        qs = (
            qs.order_by(sort)
            if sort in ALLOWED_SORTS_ALL
            else qs.order_by("-created_at")
        )

    filters_ctx = {
        "status": status or "",
        "type": rtype or "",
        "from": raw_from,
        "to": raw_to,
        "sort": sort or "",
    }
    return qs, filters_ctx, errors


def _safe_back_url(request, default_url: str) -> str:
    next_url = request.GET.get("next")
    if next_url and url_has_allowed_host_and_scheme(
        next_url, allowed_hosts={request.get_host()}, require_https=request.is_secure()
    ):
        return next_url
    return default_url


def _paginate(qs, per_page: int, page_param):
    paginator = Paginator(qs, per_page)
    page_param = page_param or 1
    try:
        return paginator.page(page_param)
    except (PageNotAnInteger, EmptyPage):
        return paginator.page(1)


def _detail_or_process_name(user):
    return (
        "requests_app:request_process"
        if is_hr_or_head(user)
        else "requests_app:request_detail"
    )


def _get_request_for_comment_access(user, pk: int) -> Request:
    if is_hr_or_head(user):
        return get_object_or_404(get_allowed_request_qs(user), pk=pk)
    return get_object_or_404(Request, pk=pk, employee=user)


# ---------- Пользователь ----------
@login_required
def my_requests(request):
    qs = BASE_REQUEST_QS.filter(employee=request.user)
    qs, filters_ctx, errors = _apply_filters(qs, request, for_all=False)
    if errors:
        messages.error(request, " ".join(errors))
    page = _paginate(qs, PAGINATE_MY, request.GET.get("page"))
    return render(
        request, "requests_app/my_requests.html", {"page": page, "filters": filters_ctx}
    )


@login_required
def request_detail(request, pk):
    req = get_object_or_404(DETAIL_REQUEST_QS, pk=pk, employee=request.user)
    return render(request, "requests_app/request_detail.html", {"request_obj": req})


@login_required
@require_http_methods(["GET", "POST"])
@ratelimit(key="user_or_ip", rate="15/m", block=True)
@maybe_cache_rl(60, 15, name="req_create")
def request_create(request):
    if request.method == "POST":
        form = RequestForm(request.POST, request.FILES)
        if form.is_valid():
            obj = form.save(commit=False)
            obj.employee = request.user
            obj.save()
            messages.success(request, "Заявление отправлено!")
            return redirect("requests_app:my_requests")
        messages.error(request, "Исправьте ошибки в форме.")
    else:
        form = RequestForm()
    return render(request, "requests_app/request_form.html", {"form": form})


@login_required
@require_http_methods(["GET", "POST"])
def request_cancel(request, pk):
    req = get_object_or_404(Request, pk=pk, employee=request.user)

    if req.status == Request.STATUS_CANCELLED:
        messages.info(request, "Заявление уже отменено.")
        return redirect("requests_app:my_requests")

    if req.is_final and req.status != Request.STATUS_CANCELLED:
        messages.error(
            request, "Нельзя отозвать заявление, по которому уже принято решение."
        )
        return redirect("requests_app:my_requests")

    if request.method == "POST":
        req.cancel()
        messages.success(request, "Заявление отменено.")
        return redirect("requests_app:my_requests")

    return render(
        request, "requests_app/request_confirm_cancel.html", {"request_obj": req}
    )


# ---------- HR / Heads ----------
@user_passes_test(is_hr_or_head)
def all_requests(request):
    qs = get_allowed_request_qs(request.user)
    qs, filters_ctx, errors = _apply_filters(qs, request, for_all=True)
    if errors:
        messages.error(request, " ".join(errors))
    page = _paginate(qs, PAGINATE_ALL, request.GET.get("page"))
    return render(
        request,
        "requests_app/all_requests.html",
        {"page": page, "filters": filters_ctx},
    )


@user_passes_test(is_hr_or_head)
@require_http_methods(["GET", "POST"])
def request_process(request, pk):
    allowed_qs = get_allowed_request_qs(request.user)

    if request.method == "POST":
        with transaction.atomic():
            req = get_object_or_404(allowed_qs.select_for_update(), pk=pk)
            req.refresh_from_db()

            post = request.POST.copy()
            # Фоллбек: если status отсутствует (или кнопка без JS), используем имя кнопки
            if not post.get("status"):
                do = post.get("do")
                if do in {
                    Request.STATUS_APPROVED,
                    Request.STATUS_REJECTED,
                    Request.STATUS_CANCELLED,
                }:
                    post["status"] = do

            form = RequestStatusForm(
                post, request.FILES, instance=req, user=request.user
            )
            if not form.is_valid():
                messages.error(request, "Исправьте ошибки в форме.")
                return render(
                    request,
                    "requests_app/request_process.html",
                    {
                        "request_obj": req,
                        "form": form,
                        "can_cancel": is_hr(
                            request.user
                        ),  # чтобы шаблон не показывал «Отменить» начальникам
                    },
                )

            new_status = form.cleaned_data["status"]
            old_status = req.status
            status_changed = new_status != old_status
            need_side_effects = (
                new_status == Request.STATUS_APPROVED
                and (not req.approver_id or not getattr(req, "decided_at", None))
            ) or (
                new_status in {Request.STATUS_REJECTED, Request.STATUS_CANCELLED}
                and not getattr(req, "decided_at", None)
            )
            if status_changed or need_side_effects:
                if new_status == Request.STATUS_APPROVED:
                    req.approve(by_user=request.user)
                elif new_status == Request.STATUS_REJECTED:
                    req.reject(by_user=request.user)
                elif new_status == Request.STATUS_CANCELLED:
                    req.cancel()
                req.save()  # <-- сохраняем гарантированно
                messages.success(request, "Решение сохранено.")

            # «мягкие» поля
            soft_updates = []
            if "comment" in form.changed_data:
                req.comment = form.cleaned_data["comment"]
                soft_updates.append("comment")
            if "attachment" in form.changed_data:
                req.attachment = form.cleaned_data["attachment"]
                soft_updates.append("attachment")
            if soft_updates:
                req.save(update_fields=soft_updates + ["updated_at"])
                if not status_changed:
                    messages.success(request, "Изменения сохранены.")

            if not status_changed and not soft_updates:
                messages.info(request, "Изменений не обнаружено.")

            return redirect("requests_app:all_requests")

    # GET
    req = get_object_or_404(allowed_qs.prefetch_related(COMMENTS_PREFETCH), pk=pk)
    form = RequestStatusForm(instance=req, user=request.user)
    return render(
        request,
        "requests_app/request_process.html",
        {"request_obj": req, "form": form, "can_cancel": is_hr(request.user)},
    )


# ---------- Комментарии ----------
@login_required
@require_http_methods(["POST"])
@ratelimit(key="user_or_ip", rate="60/m", block=True)
@maybe_cache_rl(60, 60, name="req_comment_add")
def request_comment_add(request, pk):
    req = _get_request_for_comment_access(request.user, pk)

    text = request.POST.get("text", "").strip()
    if not text:
        messages.error(request, "Комментарий не может быть пустым.")
        default_url = reverse(_detail_or_process_name(request.user), args=[pk])
        return redirect(_safe_back_url(request, default_url))

    if len(text) > MAX_COMMENT_LEN:
        messages.error(
            request, f"Комментарий слишком длинный (>{MAX_COMMENT_LEN} символов)."
        )
        default_url = reverse(_detail_or_process_name(request.user), args=[pk])
        return redirect(_safe_back_url(request, default_url))

    RequestComment.objects.create(request=req, author=request.user, text=text)
    messages.success(request, "Комментарий добавлен.")

    default_url = reverse(_detail_or_process_name(request.user), args=[pk])
    return redirect(_safe_back_url(request, default_url))


@login_required
@require_http_methods(["POST"])
def request_comment_delete(request, pk, comment_id):
    """
    HR/Head: удаляет комментарии в доступных им заявках.
    Пользователь: только свои комментарии в своих заявках.
    """
    base = RequestComment.objects.select_related("author", "request")
    if is_hr_or_head(request.user):
        base = base.filter(request__in=get_allowed_request_qs(request.user))
    else:
        base = base.filter(author=request.user, request__employee=request.user)

    comment = get_object_or_404(base, pk=comment_id, request_id=pk)

    if comment.author_id != request.user.id and not is_hr_or_head(request.user):
        raise PermissionDenied("Недостаточно прав для удаления комментария.")

    comment.delete()
    messages.success(request, f"Комментарий №{comment_id} удалён.")

    default_url = reverse(_detail_or_process_name(request.user), args=[pk])
    return redirect(_safe_back_url(request, default_url))



