# backend/employees/views_front.py
import os
import random

import requests
from communications.models import Chat
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import (CreateView, DeleteView, DetailView, ListView,
                                  UpdateView)
from dotenv import load_dotenv
from feed.models import Post
from phonenumber_field.phonenumber import to_python

from .forms import (AbsenceForm, DepartmentForm, EducationForm,
                    InviteToDepartmentForm, ProfileUpdateForm,
                    RegistrationForm, SkillForm, SMSCodeVerifyForm)
from .models import (Absence, Department, Education, Employee,
                     EmployeeDepartment, Skill)

load_dotenv()


# =========================
#   Утилиты
# =========================
def send_sms_alpha(phone: str, text: str, sender: str = "EUSRR"):
    api_key = os.getenv("SMS_API_TOKEN", "")
    api_url = os.getenv("SMS_API_URL", "https://new.smsgorod.ru/apiSms/create")
    payload = {
        "apiKey": api_key,
        "sms": [{"channel": "char", "sender": sender, "text": text, "phone": phone}],
    }
    try:
        resp = requests.post(
            api_url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=5,
        )
        return resp.json()
    except Exception as e:
        return {"error": str(e)}


# =========================
#   Регистрация
# =========================
class RegisterView(CreateView):
    model = Employee
    form_class = RegistrationForm
    template_name = "registration/register.html"
    success_url = reverse_lazy("sms_verify")

    def form_valid(self, form):
        user = form.save(commit=False)
        user.is_active = False
        code = f"{random.randint(0, 999999):06}"
        user.sms_activation_code = code
        user.save()

        send_sms_alpha(
            str(user.phone_number),
            f"Ваш код подтверждения: {code}",
            sender=os.getenv("SMS_API_SENDER", "EUSRR"),
        )

        self.request.session["phone_number"] = str(user.phone_number)
        messages.info(self.request, "Код подтверждения отправлен по SMS")
        return redirect("sms_verify")


class SMSVerifyView(View):
    template_name = "registration/sms_verify.html"

    def get(self, request):
        return render(
            request, self.template_name, {"phone": request.session.get("phone_number")}
        )

    def post(self, request):
        phone = request.session.get("phone_number")
        if not phone:
            messages.error(request, "Сессия истекла. Пройдите регистрацию заново.")
            return redirect("employees:register")

        user = Employee.objects.filter(phone_number=to_python(phone)).first()
        if not user:
            messages.error(request, "Пользователь не найден.")
            return redirect("employees:register")

        form = SMSCodeVerifyForm(request.POST)
        if form.is_valid():
            if str(user.sms_activation_code) == str(form.cleaned_data["code"]):
                user.is_active = True
                user.sms_activation_code = None
                user.save()
                messages.success(request, "Телефон подтверждён! Можете войти.")
                return redirect("login")
            messages.error(request, "Код неверный.")
        return render(request, self.template_name, {"form": form, "phone": phone})


def resend_sms(request):
    return HttpResponseNotAllowed(["GET", "POST"], "Not Implemented")


# =========================
#   Профиль
# =========================
@login_required
def profile(request):
    employee = request.user
    posts = (
        Post.objects.filter(author=employee)
        .select_related("author")
        .order_by("-created_at")[:10]
    )
    show_edit = False

    if request.method == "POST":
        form = ProfileUpdateForm(request.POST, request.FILES, instance=employee)
        if form.is_valid():
            form.save()
            messages.success(request, "Профиль успешно обновлён.")
            return redirect("employees:profile")
        show_edit = True
    else:
        form = ProfileUpdateForm(instance=employee)

    return render(
        request,
        "employees/profile.html",
        {
            "form": form,
            "employee": employee,
            "own": True,
            "posts": posts,
            "show_edit": show_edit,
        },
    )


@login_required
def employee_detail(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if employee == request.user:
        return redirect("employees:profile")
    posts = (
        Post.objects.filter(author=employee)
        .select_related("author")
        .order_by("-created_at")[:10]
    )
    return render(
        request,
        "employees/profile.html",
        {"employee": employee, "own": False, "posts": posts},
    )


@login_required
def avatar_remove(request):
    if request.method == "POST" and request.user.avatar:
        request.user.avatar.delete(save=True)
        messages.success(request, "Аватар успешно удалён.")
    return redirect("employees:profile")


# =========================
#   Сотрудники
# =========================
class EmployeeListView(LoginRequiredMixin, ListView):
    model = Employee
    template_name = "employees/employees_list.html"
    context_object_name = "employees"
    ordering = ["last_name", "first_name"]

    def get_queryset(self):
        qs = super().get_queryset().order_by("last_name", "first_name").select_related()
        dept_id = self.request.GET.get("department")
        if dept_id:
            # фильтруем по активным связям в отделе, без отдельного запроса на ids:
            qs = qs.filter(
                departments_links__department_id=dept_id,
                departments_links__is_active=True,
            ).distinct()
        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dept_id = self.request.GET.get("department")
        ctx["filter_department_id"] = dept_id
        ctx["current_department"] = (
            Department.objects.filter(pk=dept_id).first() if dept_id else None
        )
        return ctx


# =========================
#   Отделы
# =========================
class DepartmentListView(LoginRequiredMixin, ListView):
    model = Department
    template_name = "employees/department_list.html"
    context_object_name = "departments"
    ordering = ["name"]


class DepartmentDetailView(LoginRequiredMixin, DetailView):
    model = Department
    template_name = "employees/department_detail.html"
    context_object_name = "department"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        department = self.object
        # Список позиций (EmployeePosition) связан через related_name="employees"
        ctx["emp_links"] = (
            EmployeeDepartment.objects.filter(department=department, is_active=True)
            .select_related("employee")
            .order_by("employee__last_name", "employee__first_name")
        )
        ctx["employees"] = department.active_employees
        ctx["posts"] = Post.objects.filter(
            type="department", department=department
        ).order_by("-pinned", "-created_at")
        ctx["new_employees"] = department.new_employees
        # Флаг для кнопки "Пригласить"
        ctx["can_invite"] = self.request.user.is_staff or (
            department.head_id == self.request.user.id
        )
        return ctx


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
                employee=employee, department=department, defaults={"is_active": True}
            )
            if not created and not emp_dep.is_active:
                emp_dep.is_active = True
                emp_dep.save()

            # участников в чат можно не добавлять — get_participants собирает динамически
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
#   Универсальный CRUD для Absence, Skill, Education
# =========================
class BaseCRUDListView(LoginRequiredMixin, ListView):
    """Базовый ListView: если у модели есть FK employee — показываем только свои записи."""

    def get_queryset(self):
        qs = super().get_queryset()
        # Надёжная проверка наличия поля 'employee'
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


# Absence CRUD
class AbsenceListView(BaseCRUDListView):
    model = Absence
    template_name = "employees/absence_list.html"
    context_object_name = "absences"


class AbsenceCreateView(BaseCRUDCreateView):
    model = Absence
    form_class = AbsenceForm
    template_name = "employees/absence_form.html"
    success_url = reverse_lazy("employees:absence_list")


class AbsenceUpdateView(BaseCRUDUpdateView):
    model = Absence
    form_class = AbsenceForm
    template_name = "employees/absence_form.html"
    success_url = reverse_lazy("employees:absence_list")


class AbsenceDeleteView(BaseCRUDDeleteView):
    model = Absence
    template_name = "employees/absence_confirm_delete.html"
    success_url = reverse_lazy("employees:absence_list")


# Skill CRUD
class SkillListView(LoginRequiredMixin, ListView):
    model = Skill
    template_name = "employees/skill_list.html"
    context_object_name = "skills"


class SkillCreateView(LoginRequiredMixin, CreateView):
    model = Skill
    form_class = SkillForm
    template_name = "employees/skill_form.html"
    success_url = reverse_lazy("employees:skill_list")


class SkillUpdateView(LoginRequiredMixin, UpdateView):
    model = Skill
    form_class = SkillForm
    template_name = "employees/skill_form.html"
    success_url = reverse_lazy("employees:skill_list")


class SkillDeleteView(LoginRequiredMixin, DeleteView):
    model = Skill
    template_name = "employees/skill_confirm_delete.html"
    success_url = reverse_lazy("employees:skill_list")


# Education CRUD
class EducationListView(BaseCRUDListView):
    model = Education
    template_name = "employees/education_list.html"
    context_object_name = "educations"


class EducationCreateView(BaseCRUDCreateView):
    model = Education
    form_class = EducationForm
    template_name = "employees/education_form.html"
    success_url = reverse_lazy("employees:education_list")


class EducationUpdateView(BaseCRUDUpdateView):
    model = Education
    form_class = EducationForm
    template_name = "employees/education_form.html"
    success_url = reverse_lazy("employees:education_list")


class EducationDeleteView(BaseCRUDDeleteView):
    model = Education
    template_name = "employees/education_confirm_delete.html"
    success_url = reverse_lazy("employees:education_list")
