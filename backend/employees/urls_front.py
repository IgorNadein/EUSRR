# backend/employees/urls_front.py
from django.urls import path
from . import views_front

app_name = "employees"

urlpatterns = [
    # --- Профиль и сотрудники ---
    path("list/", views_front.employee_list, name="employees_list"),
    path("me/", views_front.employee_profile, name="profile"),
    path("me/edit/", views_front.employee_edit_me, name="employee_edit_me"),
    path("<int:pk>/", views_front.employee_profile, name="employee_detail"),
    path("<int:pk>/edit/", views_front.employee_edit, name="employee_edit"),
    path("create/", views_front.employee_create, name="employee_create"),
    # --- Отделы ---
    path(
        "departments/add/",
        views_front.DepartmentCreateView.as_view(),
        name="department_add",
    ),
    path(
        "departments/<int:dept_id>/members/<int:employee_id>/role/",
        views_front.edit_department_role,
        name="edit_department_role",
    ),
    path("departments/", views_front.department_list, name="department_list"),
    path(
        "departments/<int:pk>/", views_front.department_detail, name="department_detail"
    ),
    path(
        "departments/<int:pk>/edit/",
        views_front.department_edit,
        name="department_edit",
    ),
    path(
        "departments/<int:pk>/set-head/",
        views_front.department_set_head,
        name="department_set_head",
    ),
    path(
        "<int:emp_id>/departments/<int:dept_id>/set-role/",
        views_front.set_member_role,
        name="set_member_role",
    ),
    # --- Навыки ---
    path("<int:pk>/skill/add/", views_front.skill_add, name="skill_add"),
    path("<int:pk>/skill/remove/", views_front.skill_remove, name="skill_remove"),

    # --- Должности ---
    path("positions/create/", views_front.position_create_front, name="position_create"),
    path("positions/<int:pos_id>/update/", views_front.position_update_front, name="position_update"),
    path("<int:emp_id>/set-position/", views_front.employee_set_position_front, name="employee_set_position"),
    path("me/set-position/", views_front.employee_set_position_me_front, name="employee_set_position_me"),
]
