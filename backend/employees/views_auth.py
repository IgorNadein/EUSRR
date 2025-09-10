from __future__ import annotations

from api.client import ApiClient, get_api_client
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import LoginView as DjangoLoginView
from django.contrib.auth.views import \
    PasswordResetCompleteView as DjangoPasswordResetCompleteView
from django.contrib.auth.views import \
    PasswordResetConfirmView as DjangoPasswordResetConfirmView
from django.contrib.auth.views import \
    PasswordResetDoneView as DjangoPasswordResetDoneView
from django.contrib.auth.views import \
    PasswordResetView as DjangoPasswordResetView
from django.shortcuts import redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.views import View
from django.views.decorators.http import require_http_methods

from .forms_auth import (EmailOrPhoneAuthenticationForm, RegistrationForm,
                         VerifyEmailForm)


def _apply_api_errors_to_form(form, data: dict):
    """Развешиваем ошибки из API по полям/неполям."""
    if not isinstance(data, dict):
        form.add_error(None, "Неизвестная ошибка сервера.")
        return

    if "ok" in data and not data.get("ok"):
        form.add_error(
            None, data.get("error") or data.get("detail") or "Ошибка запроса."
        )

    detail = data.get("detail")
    if isinstance(detail, str):
        form.add_error(None, detail)
    elif isinstance(detail, (list, tuple)):
        for msg in detail:
            form.add_error(None, msg)

    for field, errs in data.items():
        if field in {"ok", "error", "detail"}:
            continue
        target = "phone_number" if field == "phone" else field
        if target in form.fields:
            if isinstance(errs, (list, tuple)):
                for e in errs:
                    form.add_error(target, e)
            else:
                form.add_error(target, str(errs))
        else:
            if isinstance(errs, (list, tuple)):
                for e in errs:
                    form.add_error(None, f"{field}: {e}")
            else:
                form.add_error(None, f"{field}: {errs}")


@require_http_methods(["GET", "POST"])
def register_view(request):
    """
    Страница регистрации: показываем Django-форму и шлём валидные данные в /api/v1/auth/register/
    (аватар пока локально, в API не отправляем — загрузим после верификации).
    """
    api = get_api_client(request)

    if request.method == "GET":
        form = RegistrationForm()
        return render(request, "auth/register.html", {"form": form})

    # ВАЖНО: учитывать файлы (чтобы form.avatar был BoundField)
    form = RegistrationForm(request.POST, request.FILES)
    if not form.is_valid():
        return render(request, "auth/register.html", {"form": form}, status=400)

    payload = form.to_api_payload()  # формирует json для API, включая password
    resp = api.post("v1/auth/register/", json=payload)

    if resp.status == 201:
        messages.success(
            request,
            "Мы отправили код подтверждения на вашу почту. Введите его на следующем шаге.",
        )
        q = urlencode({"email": payload["email"]})
        return redirect(f'{reverse("auth_front:verify_email")}?{q}')

    data = resp.json or {}
    if resp.status == 200 and data.get("ok") and data.get("pending_verification"):
        messages.info(request, "Аккаунт уже создан, подтвердите email кодом из письма.")
        q = urlencode({"email": payload["email"]})
        return redirect(f'{reverse("auth_front:verify_email")}?{q}')

    # Остальные ошибки — показать в форме
    _apply_api_errors_to_form(form, data)
    return render(request, "auth/register.html", {"form": form}, status=400)


@require_http_methods(["GET", "POST"])
def verify_email_view(request):
    """Ввод кода подтверждения. Использует /api/v1/auth/verify-email/."""
    api = get_api_client(request)

    if request.method == "GET":
        form = VerifyEmailForm(initial={"email": request.GET.get("email", "")})
        return render(request, "auth/verify_email.html", {"form": form})

    form = VerifyEmailForm(request.POST)
    if not form.is_valid():
        return render(request, "auth/verify_email.html", {"form": form}, status=400)

    payload = {"email": form.cleaned_data["email"], "code": form.cleaned_data["code"]}
    r = api.post("v1/auth/verify-email/", json=payload)

    if r.ok and (r.json or {}).get("ok"):
        messages.success(request, "Email подтверждён! Теперь вы можете войти.")
        return redirect("auth_front:login")

    data = r.json or {}
    err = data.get("error") or data.get("detail") or "Не удалось подтвердить email."
    if err == "invalid_code":
        err = "Неверный код подтверждения."
    elif err == "user_not_found":
        err = "Пользователь с таким email не найден."
    form.add_error(None, err)
    return render(request, "auth/verify_email.html", {"form": form}, status=400)


@require_http_methods(["POST"])
def resend_email_view(request):
    """Кнопка «Отправить код ещё раз» — /api/v1/auth/resend-email/."""
    api = get_api_client(request)
    email = (request.POST.get("email") or "").strip()
    r = api.post("v1/auth/resend-email/", json={"email": email})

    if r.ok and (r.json or {}).get("ok"):
        messages.success(request, "Код подтверждения повторно отправлен на вашу почту.")
    else:
        data = r.json or {}
        err = (
            data.get("error")
            or data.get("detail")
            or "Не удалось отправить код повторно."
        )
        if err == "already_verified":
            err = "Email уже подтверждён."
        elif err == "user_not_found":
            err = "Пользователь с таким email не найден."
        messages.error(request, err)

    q = urlencode({"email": email}) if email else ""
    return redirect(f'{reverse("auth_front:verify_email")}{("?" + q) if q else ""}')


class EmailOrPhoneLoginView(DjangoLoginView):
    """
    Страница входа: одно поле 'Email или телефон' + пароль.
    После успешной Django-аутентификации — берём JWT у DRF и кладём в сессию.
    """

    template_name = "auth/login.html"
    authentication_form = EmailOrPhoneAuthenticationForm

    def form_valid(self, form):
        # 1) Django-логин
        response = super().form_valid(form)
        # 2) Получаем JWT от API и кладём его в сессию
        user = self.request.user
        password = form.cleaned_data.get("password")
        client = ApiClient(self.request)
        ok = client.login(user.email, password)  # USERNAME_FIELD=email
        if not ok:
            messages.error(
                self.request, "Не удалось получить токен API. Повторите вход позже."
            )
        return response


class ConfirmLogoutView(LoginRequiredMixin, View):
    template_name = "auth/logout.html"

    def get(self, request):
        next_url = request.GET.get("next") or request.META.get("HTTP_REFERER") or ""
        return render(request, self.template_name, {"next": next_url})

    def post(self, request):
        next_url = request.POST.get("next") or reverse("auth_front:login")
        logout(request)
        messages.success(request, "Вы вышли из аккаунта.")
        return redirect(next_url)


# ===== Сброс пароля =====


class PasswordResetView(DjangoPasswordResetView):
    template_name = "auth/password_reset.html"
    email_template_name = "auth/password_reset_email.txt"
    subject_template_name = "auth/password_reset_subject.txt"
    success_url = "/auth/password-reset/done/"


class PasswordResetDoneView(DjangoPasswordResetDoneView):
    template_name = "auth/password_reset_done.html"


class PasswordResetConfirmView(DjangoPasswordResetConfirmView):
    template_name = "auth/password_reset_confirm.html"
    success_url = "/auth/reset/done/"


class PasswordResetCompleteView(DjangoPasswordResetCompleteView):
    template_name = "auth/password_reset_complete.html"
