# backend/employees/views_front.py

from datetime import timedelta

from common.emails import send_templated_mail
from django.contrib.auth import login
from django.contrib import messages
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
from django.utils.crypto import get_random_string
from django.views import View
from django.views.generic import (
    CreateView,
    DeleteView,
    DetailView,
    ListView,
    UpdateView,
)
from feed.constants import TYPE_DEPARTMENT
from feed.models import Comment, Post, PostLike

from .forms import (
    AbsenceForm,
    DepartmentForm,
    DepartmentMemberRoleForm,
    EducationForm,
    InviteToDepartmentForm,
    ProfileUpdateForm,
    RegistrationForm,
    SkillForm,
)
from .models import (
    Absence,
    Department,
    Education,
    Employee,
    EmployeeAction,
    EmployeeDepartment,
    Skill,
)
from django.http import HttpResponseNotAllowed
from employees.api_client import api_post, APIError


# =========================
#   Регистрация
# =========================


class RegisterView(CreateView):
    model = Employee
    form_class = RegistrationForm
    template_name = "registration/register.html"

    def form_valid(self, form):
        cd = form.cleaned_data

        email = cd.get("email")
        password = cd.get("password1") or cd.get("password") or ""
        first_name = cd.get("first_name", "")
        last_name = cd.get("last_name", "")
        phone = cd.get("phone") or cd.get("phone_number") or ""

        # >>> добавь это приведение типов <<<
        try:
            # если установлен django-phonenumber-field
            from phonenumber_field.phonenumber import PhoneNumber
        except Exception:
            PhoneNumber = None

        if PhoneNumber and isinstance(phone, PhoneNumber):
            # canonical формат для API
            phone = phone.as_e164 or phone.raw_input or str(phone)
        elif phone is None:
            phone = ""
        else:
            phone = str(phone).strip()

        payload = {
            "email": email,
            "password": password,
            "first_name": first_name,
            "last_name": last_name,
        }
        if phone:
            payload["phone"] = phone

        try:
            status_code, data = api_post(self.request, "api_v1:register", payload)
        except APIError as e:
            form.add_error(None, f"Ошибка регистрации: {e}")
            return self.form_invalid(form)

        if status_code in (200, 201) and data.get("ok"):
            self.request.session["email"] = email
            if data.get("resent"):
                messages.info(self.request, "Пользователь уже был создан. Мы отправили код повторно.")
            else:
                messages.success(self.request, "Код подтверждения отправлен на вашу почту.")
            return redirect("employees:email_verify")

        err = (data or {}).get("error")
        if err == "email_taken":
            form.add_error("email", "Этот email уже используется.")
        else:
            form.add_error(None, "Не удалось зарегистрировать. Попробуйте позже.")
        return self.form_invalid(form)


class EmailVerifyView(View):
    template_name = "registration/email_verify.html"

    def get(self, request):
        return render(
            request, self.template_name, {"email": request.session.get("email")}
        )

    def post(self, request):
        email = request.session.get("email")
        if not email:
            messages.error(request, "Сессия истекла. Пройдите регистрацию заново.")
            return redirect("employees:register")

        code = (request.POST.get("code") or "").strip()
        if not code:
            messages.error(request, "Введите код подтверждения.")
            return render(request, self.template_name, {"email": email})

        # ✨ зовём API
        try:
            status_code, data = api_post(
                request, "api_v1:verify-email", {"email": email, "code": code}
            )
        except APIError as e:
            messages.error(request, f"Ошибка проверки кода: {e}")
            return render(request, self.template_name, {"email": email})

        if status_code == 200 and data.get("ok"):
            # Автовход
            user = None
            user_id = data.get("user_id")
            if user_id:
                user = Employee.objects.filter(id=user_id).first()
            if not user:
                user = Employee.objects.filter(email__iexact=email).first()

            if user:
                request.session.pop("email", None)
                login(
                    request, user, backend="django.contrib.auth.backends.ModelBackend"
                )
                messages.success(request, "Email подтверждён! Добро пожаловать.")
                return redirect("feed:feed_list")

            messages.warning(
                request,
                "Email подтверждён, но не удалось выполнить вход. Войдите вручную.",
            )
            return redirect("login")

        # Обработка ошибок API
        err = (data or {}).get("error")
        if err == "user_not_found":
            messages.error(request, "Пользователь не найден.")
            return redirect("employees:register")
        if err == "invalid_code":
            messages.error(request, "Код неверный.")
            return render(request, self.template_name, {"email": email})
        if err == "empty_code":
            messages.error(request, "Введите код подтверждения.")
            return render(request, self.template_name, {"email": email})

        messages.error(request, "Не удалось подтвердить email. Попробуйте позже.")
        return render(request, self.template_name, {"email": email})


def resend_email(request):
    if request.method != "POST":
        return HttpResponseNotAllowed(["POST"])

    email = request.session.get("email")
    if not email:
        messages.error(request, "Сессия истекла.")
        return redirect("employees:register")

    # Простая защита от частых повторов: не чаще 1 раза в минуту
    # Локальная защита от частых повторов оставляем (по сессии)
    now_ts = int(timezone.now().timestamp())
    last_ts = request.session.get("email_code_last_sent_ts")
    if last_ts and (now_ts - int(last_ts) < 60):
        messages.error(request, "Слишком часто. Попробуйте через минуту.")
        return redirect("employees:email_verify")
    # Вызываем API
    try:
        status_code, data = api_post(
            request,
            "api_v1:resend-email",
            {"email": email},
        )
    except APIError as e:
        messages.error(request, f"Ошибка отправки кода: {e}")
        return redirect("employees:email_verify")

    if status_code == 200 and data.get("ok"):
        request.session["email_code_last_sent_ts"] = now_ts
        messages.success(request, "Код отправлен повторно.")
        return redirect("employees:email_verify")

    # Обработка ошибок API
    err = (data or {}).get("error")
    if err == "user_not_found":
        messages.error(request, "Пользователь не найден.")
        return redirect("employees:register")
    if err == "already_verified":
        messages.error(request, "Email уже подтверждён.")
        return redirect("login")
    messages.error(request, "Не удалось отправить код. Попробуйте позже.")
    return redirect("employees:email_verify")


# =========================
#   Утилиты
# =========================
def _annotated_feed(base_qs, user):
    """
    Добавляет к queryset постов:
      - is_liked: bool — лайкал ли текущий пользователь
      - comments_count: int — количество комментариев
      - comments_sorted: [Comment] — все комментарии поста, отсортированные по -created_at
    Плюс select_related(author, department) и сортировка как в ленте.

    В шаблоне используйте первый элемент:
        {{ post.comments_sorted|first }}
    """
    is_liked = (
        Exists(PostLike.objects.filter(post=OuterRef("pk"), user=user))
        if getattr(user, "is_authenticated", False)
        else Value(False, output_field=BooleanField())
    )
    last_comment_qs = Comment.objects.select_related("author").order_by("-created_at")
    return (
        base_qs.select_related("author", "department")
        .annotate(is_liked=is_liked, comments_count=Count("comments"))
        .prefetch_related(
            Prefetch(
                "comments",
                queryset=last_comment_qs,
                to_attr="comments_sorted",
            )
        )
        .order_by("-pinned", "-created_at")
    )


# =========================
#   Профиль
# =========================
@login_required
def profile(request):
    employee = request.user
    posts = _annotated_feed(Post.objects.filter(author=employee), request.user)[:10]
    show_edit = False

    # кадровые события — видит только тот, у кого есть право
    hr_actions = []
    if request.user.has_perm("employees.view_employeeaction"):
        hr_actions = EmployeeAction.objects.filter(employee=employee).order_by("-date")[
            :50
        ]
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
            "hr_actions": hr_actions,
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
    hr_actions = []
    if request.user.has_perm("employees.view_employeeaction"):
        hr_actions = EmployeeAction.objects.filter(employee=employee).order_by("-date")[
            :50
        ]
    emp_departments = employee.departments.order_by("name")
    return render(
        request,
        "employees/profile.html",
        {
            "employee": employee,
            "own": False,
            "posts": posts,
            "show_edit": False,
            "hr_actions": hr_actions,
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

        # Если отдел не найден, логично вернуть пустой список
        if not department:
            return qs.none()

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

        # --- Присоединились за 30 дней: максимум 10 (сравниваем DateField с датой)
        month_ago_date = (timezone.now() - timedelta(days=30)).date()
        recent_links = base_links.filter(date_from__gte=month_ago_date).order_by(
            "-date_from"
        )[:10]

        # --- Лента отдела с аннотациями (для сердца/счётчика/последнего коммента)
        is_liked_annot = (
            Exists(PostLike.objects.filter(post=OuterRef("pk"), user=self.request.user))
            if self.request.user.is_authenticated
            else Value(False, output_field=BooleanField())
        )
        last_comment_qs = Comment.objects.select_related("author").order_by(
            "-created_at"
        )
        posts = (
            Post.objects.filter(type=TYPE_DEPARTMENT, department=department)
            .select_related("author", "department")
            .annotate(is_liked=is_liked_annot, comments_count=Count("comments"))
            .prefetch_related(
                Prefetch(
                    "comments", queryset=last_comment_qs, to_attr="comments_sorted"
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
                employee=employee,
                department=department,
                defaults={"is_active": True, "date_from": timezone.now().date()},
            )
            if not created and not emp_dep.is_active:
                emp_dep.is_active = True
                emp_dep.date_from = timezone.now().date()
                emp_dep.date_to = None
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


# Skill CRUD (через базовые вьюхи, чтобы ограничить видимость своими записями)
class SkillListView(BaseCRUDListView):
    model = Skill
    template_name = "employees/skill_list.html"
    context_object_name = "skills"


class SkillCreateView(BaseCRUDCreateView):
    model = Skill
    form_class = SkillForm
    template_name = "employees/skill_form.html"
    success_url = reverse_lazy("employees:skill_list")


class SkillUpdateView(BaseCRUDUpdateView):
    model = Skill
    form_class = SkillForm
    template_name = "employees/skill_form.html"
    success_url = reverse_lazy("employees:skill_list")


class SkillDeleteView(BaseCRUDDeleteView):
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
