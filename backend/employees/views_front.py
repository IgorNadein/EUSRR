# backend/employees/views_front.py

import os
import random
from datetime import timedelta

import requests
from communications.models import Chat
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.db.models import (
    BooleanField,
    Case,
    CharField,
    Count,
    Exists,
    OuterRef,
    Prefetch,
    Q,
    Subquery,
    Value,
    When,
)
from django.http import HttpResponseNotAllowed
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import CreateView, DeleteView, DetailView, ListView, UpdateView
from dotenv import load_dotenv
from feed.constants import TYPE_DEPARTMENT, TYPE_EMPLOYEE
from feed.models import Comment, Post, PostLike
from phonenumber_field.phonenumber import to_python

from .forms import (
    AbsenceForm,
    DepartmentForm,
    DepartmentMemberRoleForm,
    EducationForm,
    InviteToDepartmentForm,
    ProfileUpdateForm,
    RegistrationForm,
    SkillForm,
    SMSCodeVerifyForm,
)
from .models import (
    Absence,
    Department,
    Education,
    Employee,
    EmployeeAction,          # ← добавлено
    EmployeeDepartment,
    Skill,
)

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


def _annotated_feed(base_qs, user):
    """
    Добавляет к queryset постов:
      - is_liked: bool — лайкал ли текущий пользователь
      - comments_count: int — количество комментариев
      - last_comment_list: [Comment] длиной 1 с автором (последний)
    Плюс select_related(author, department) и сортировка как в ленте.
    """
    is_liked = (
        Exists(PostLike.objects.filter(post=OuterRef("pk"), user=user))
        if user.is_authenticated
        else Value(False, output_field=BooleanField())
    )
    last_comment_qs = Comment.objects.select_related("author").order_by("-created_at")[
        :1
    ]
    return (
        base_qs.select_related("author", "department")
        .annotate(is_liked=is_liked, comments_count=Count("comments"))
        .prefetch_related(
            Prefetch("comments", queryset=last_comment_qs, to_attr="last_comment_list")
        )
        .order_by("-pinned", "-created_at")
    )


# =========================
#   Регистрация
# =========================
class RegisterView(CreateView):
    model = Employee
    form_class = RegistrationForm
    template_name = "registration/register.html"
    success_url = reverse_lazy("feed:feed_list")

    def form_valid(self, form):
        user = form.save(commit=False)
        user.is_active = True
        user.save()
        login(self.request, user, backend="django.contrib.auth.backends.ModelBackend")
        return redirect("feed:feed_list")


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
    posts = _annotated_feed(Post.objects.filter(author=employee), request.user)[:10]
    show_edit = False

    # кадровые события — видит только тот, у кого есть право
    hr_history = (
        EmployeeAction.history
        .filter(employee_id=employee.id)
        .select_related("history_user")
        .order_by("-history_date")
    )
    emp_departments = employee.departments.order_by("name")

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
            "hr_actions": hr_history,
            "emp_departments": emp_departments,
        },
    )


@login_required
def employee_detail(request, pk):
    employee = get_object_or_404(Employee, pk=pk)
    if employee == request.user:
        return redirect("employees:profile")

    posts = _annotated_feed(Post.objects.filter(author=employee), request.user)[:10]

    # кадровые события целевого сотрудника — только при наличии права
    hr_history = (
        EmployeeAction.history
        .filter(employee_id=employee.id)
        .select_related("history_user")
        .order_by("-history_date")
    )
    emp_departments = employee.departments.order_by("name")
    return render(
        request,
        "employees/profile.html",
        {
            "employee": employee,
            "own": False,
            "posts": posts,
            "show_edit": False,
            "hr_actions": hr_history,  # ← добавлено
            "emp_departments": emp_departments,
        },
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
        qs = super().get_queryset().order_by("last_name", "first_name")

        dept_id = self.request.GET.get("department")
        if not dept_id:
            return qs

        # Текущий отдел (для head_id)
        department = Department.objects.filter(pk=dept_id).only("id", "head_id").first()

        # Активная связь сотрудника с отделом (для аннотаций)
        link_qs = EmployeeDepartment.objects.filter(
            department_id=dept_id,
            employee_id=OuterRef("pk"),
            is_active=True,
        )

        # Фильтруем: сотрудники с активной связью ИЛИ руководитель отдела
        head_id = getattr(department, "head_id", None)
        qs = qs.filter(
            Q(
                departments_links__department_id=dept_id,
                departments_links__is_active=True,
            )
            | Q(pk=head_id)
        ).distinct()

        # Аннотации: роль в отделе, признак члена отдела и признак руководителя
        qs = qs.annotate(
            dep_role=Subquery(link_qs.values("role")[:1], output_field=CharField()),
            is_dept_member=Exists(link_qs),
            is_dept_head=Case(
                When(pk=head_id, then=Value(True)),
                default=Value(False),
                output_field=BooleanField(),
            ),
        )

        return qs

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        dept_id = self.request.GET.get("department")
        current_department = (
            Department.objects.filter(pk=dept_id).first() if dept_id else None
        )

        ctx["filter_department_id"] = dept_id
        ctx["current_department"] = current_department
        ctx["is_filtered_by_department"] = bool(current_department)
        ctx["can_manage_roles"] = bool(
            current_department
            and (
                self.request.user.is_staff
                or current_department.head_id == self.request.user.id
            )
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

        # --- Команда отдела: только с ролью, максимум 10
        base_links = EmployeeDepartment.objects.filter(
            department=department, is_active=True
        ).select_related("employee")
        team_links = (
            base_links.exclude(role__isnull=True)
            .exclude(role="")
            .order_by("employee__last_name", "employee__first_name")[:10]
        )

        # --- Присоединились за 14 дней: максимум 10
        two_weeks_ago = timezone.now() - timedelta(days=14)
        has_link_created = any(
            f.name == "created_at" for f in EmployeeDepartment._meta.fields
        )
        if has_link_created:
            recent_links = base_links.filter(created_at__gte=two_weeks_ago).order_by(
                "-created_at"
            )[:10]
        else:
            recent_links = base_links.filter(
                employee__created_at__gte=two_weeks_ago
            ).order_by("-employee__created_at")[:10]

        # --- Лента отдела с аннотациями (для сердца/счётчика/последнего коммента)
        is_liked_annot = (
            Exists(PostLike.objects.filter(post=OuterRef("pk"), user=self.request.user))
            if self.request.user.is_authenticated
            else Value(False)
        )
        last_comment_qs = Comment.objects.select_related("author").order_by(
            "-created_at"
        )[:1]
        posts = (
            Post.objects.filter(type="department", department=department)
            .select_related("author", "department")
            .annotate(is_liked=is_liked_annot, comments_count=Count("comments"))
            .prefetch_related(
                Prefetch(
                    "comments", queryset=last_comment_qs, to_attr="last_comment_list"
                )
            )
            .order_by("-pinned", "-created_at")
        )

        ctx.update(
            {
                "team_links": team_links,
                "recent_links": recent_links,
                "posts": posts,
                "new_employees": getattr(department, "new_employees", []),
                "can_invite": self.request.user.is_staff
                or (department.head_id == self.request.user.id),
            }
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


@login_required
def edit_department_role(request, dept_id, employee_id):
    department = get_object_or_404(Department, pk=dept_id)

    # только staff или руководитель отдела
    if not (request.user.is_staff or department.head_id == request.user.id):
        messages.error(request, "Нет прав изменять роли в этом отделе.")
        return redirect("employees:employees_list")

    link = get_object_or_404(
        EmployeeDepartment,
        department=department,
        employee_id=employee_id,
    )

    if request.method == "POST":
        form = DepartmentMemberRoleForm(request.POST, instance=link)
        if form.is_valid():
            form.save()
            messages.success(request, "Роль в отделе обновлена.")
            next_url = request.POST.get("next") or (
                reverse("employees:employees_list") + f"?department={dept_id}"
            )
            return redirect(next_url)
    else:
        form = DepartmentMemberRoleForm(instance=link)

    employee = link.employee
    next_url = request.GET.get("next") or (
        reverse("employees:employees_list") + f"?department={dept_id}"
    )
    return render(
        request,
        "employees/department_role_form.html",
        {
            "department": department,
            "employee": employee,
            "form": form,
            "next_url": next_url,
        },
    )


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
