# employees/views_auth.py
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib.auth.views import (
    LoginView as DjangoLoginView,
    PasswordResetView as DjangoPasswordResetView,
    PasswordResetDoneView as DjangoPasswordResetDoneView,
    PasswordResetConfirmView as DjangoPasswordResetConfirmView,
    PasswordResetCompleteView as DjangoPasswordResetCompleteView,
)
from django.shortcuts import redirect, render
from django.views import View

from .forms_auth import EmailOrPhoneAuthenticationForm


class EmailOrPhoneLoginView(DjangoLoginView):
    """
    Страница входа: одно поле 'Email или телефон' + пароль.
    Использует наш кастомный AuthenticationForm.
    """

    template_name = "registration/login.html"
    authentication_form = EmailOrPhoneAuthenticationForm


class ConfirmLogoutView(LoginRequiredMixin, View):
    template_name = "registration/logout.html"  # или logout_confirm.html — под твой файл

    def get(self, request):
        next_url = request.GET.get("next") or request.META.get("HTTP_REFERER") or ""
        return render(request, self.template_name, {"next": next_url})

    def post(self, request):
        next_url = request.POST.get("next") or "login"
        logout(request)
        messages.success(request, "Вы вышли из аккаунта.")
        return redirect(next_url)

# ===== Поток сброса пароля =====


class PasswordResetView(DjangoPasswordResetView):
    """
    Шаг 1: форма запроса сброса пароля по email.
    """

    template_name = "registration/password_reset_form.html"
    email_template_name = "registration/password_reset_email.txt"
    subject_template_name = "registration/password_reset_subject.txt"
    success_url = "/auth/password-reset/done/"


class PasswordResetDoneView(DjangoPasswordResetDoneView):
    """
    Шаг 2: уведомление, что письмо отправлено.
    """

    template_name = "registration/password_reset_done.html"


class PasswordResetConfirmView(DjangoPasswordResetConfirmView):
    """
    Шаг 3: установка нового пароля по ссылке из письма.
    """

    template_name = "registration/password_reset_confirm.html"
    success_url = "/auth/reset/done/"


class PasswordResetCompleteView(DjangoPasswordResetCompleteView):
    """
    Шаг 4: пароль изменён.
    """

    template_name = "registration/password_reset_complete.html"
