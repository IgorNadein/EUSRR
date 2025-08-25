# backend/employees/urls_front.py
from django.urls import path
from . import views_front

app_name = "employees"

urlpatterns = [

    # --- Профиль и сотрудники ---
    path("list/", views_front.employee_list, name="employees_list"),
    path("me/", views_front.employee_me, name="profile"),
    path("me/edit/", views_front.employee_edit_me, name="employee_edit_profile"),
    path("<int:pk>/", views_front.employee_detail, name="employee_detail"),
    path("<int:pk>/edit/", views_front.employee_edit, name="employee_edit"),
    path("create/", views_front.employee_create, name="employee_create"),

    # --- Отделы ---
    path(
        "departments/add/",
        views_front.DepartmentCreateView.as_view(),
        name="department_add",
    ),
    # path("departments/<int:pk>/edit/", views_front.DepartmentUpdateView.as_view(), name="department_edit"),
    # path("departments/<int:pk>/delete/", views_front.DepartmentDeleteView.as_view(), name="department_delete"),
    # path("departments/<int:pk>/invite/", views_front.invite_to_department, name="invite_to_department"),
    path("departments/<int:dept_id>/members/<int:employee_id>/role/", views_front.edit_department_role, name="edit_department_role",),
    path("departments/", views_front.department_list, name="department_list"),
    path("departments/<int:pk>/", views_front.department_detail, name="department_detail"),
    path("departments/<int:pk>/edit/", views_front.department_edit, name="department_edit",),
    path("departments/<int:pk>/set-head/", views_front.department_set_head, name="department_set_head",),
    path("departments/<int:pk>/set-member-role/", views_front.department_set_member_role, name="department_set_member_role",),

    # --- Навыки ---
    path("skills/", views_front.SkillListView.as_view(), name="skill_list"),
    path("skills/add/", views_front.SkillCreateView.as_view(), name="skill_add"),
    path(
        "skills/<int:pk>/edit/",
        views_front.SkillUpdateView.as_view(),
        name="skill_edit",
    ),
    path(
        "skills/<int:pk>/delete/",
        views_front.SkillDeleteView.as_view(),
        name="skill_delete",
    ),

]
