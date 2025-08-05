from django.urls import path
from . import views_front

app_name = 'employees'

urlpatterns = [
    path('profile/', views_front.profile, name='profile'),
    path('profile/avatar_remove/', views_front.avatar_remove, name='avatar_remove'),
    path('employees/<int:pk>/', views_front.employee_detail, name='employee_detail'),
    path('departments/', views_front.department_list, name='department_list'),
    path('departments/<int:pk>/', views_front.department_detail,
         name='department_detail'),
    path('', views_front.employees_list, name='employees_list'),
]
