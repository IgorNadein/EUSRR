# backend/employees/urls_front.py
from django.urls import path
from . import views_front as views

app_name = "employees"

urlpatterns = [
    # --- Регистрация и активация ---
    path("register/", views.RegisterView.as_view(), name="register"),
    # path("sms-verify/", views.SMSVerifyView.as_view(), name="sms_verify"),
    path("email-verify/", views.EmailVerifyView.as_view(), name="email_verify"),
    # path("resend-sms/", views.resend_sms, name="resend_sms"),
    path("resend-email/", views.resend_email, name="resend_email"),

    # --- Профиль и сотрудники ---
    path("profile/", views.profile, name="profile"),
    path("employee/<int:pk>/", views.employee_detail, name="employee_detail"),
    path("avatar/remove/", views.avatar_remove, name="avatar_remove"),
    path("list/", views.EmployeeListView.as_view(), name="employees_list"),

    # --- Отделы ---
    path("departments/", views.DepartmentListView.as_view(), name="department_list"),
    path("departments/<int:pk>/", views.DepartmentDetailView.as_view(), name="department_detail"),
    path("departments/add/", views.DepartmentCreateView.as_view(), name="department_add"),
    path("departments/<int:pk>/edit/", views.DepartmentUpdateView.as_view(), name="department_edit"),
    path("departments/<int:pk>/delete/", views.DepartmentDeleteView.as_view(), name="department_delete"),
    path("departments/<int:pk>/invite/", views.invite_to_department, name="invite_to_department"),
    path("departments/<int:dept_id>/members/<int:employee_id>/role/", views.edit_department_role, name="edit_department_role",),

    # --- Отсутствия ---
    path("absences/", views.AbsenceListView.as_view(), name="absence_list"),
    path("absences/add/", views.AbsenceCreateView.as_view(), name="absence_add"),
    path("absences/<int:pk>/edit/", views.AbsenceUpdateView.as_view(), name="absence_edit"),
    path("absences/<int:pk>/delete/", views.AbsenceDeleteView.as_view(), name="absence_delete"),

    # --- Навыки ---
    path("skills/", views.SkillListView.as_view(), name="skill_list"),
    path("skills/add/", views.SkillCreateView.as_view(), name="skill_add"),
    path("skills/<int:pk>/edit/", views.SkillUpdateView.as_view(), name="skill_edit"),
    path("skills/<int:pk>/delete/", views.SkillDeleteView.as_view(), name="skill_delete"),

    # --- Образование ---
    path("education/", views.EducationListView.as_view(), name="education_list"),
    path("education/add/", views.EducationCreateView.as_view(), name="education_add"),
    path("education/<int:pk>/edit/", views.EducationUpdateView.as_view(), name="education_edit"),
    path("education/<int:pk>/delete/", views.EducationDeleteView.as_view(), name="education_delete"),
]
