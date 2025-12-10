"""
URL конфигурация для HTML страниц модуля закупок (Frontend).
"""

from django.urls import path

from . import views_frontend as views

app_name = 'procurement_frontend'

urlpatterns = [
    # Дашборд
    path('', views.dashboard, name='dashboard'),

    # Заявки на закупку
    path('requests/', views.request_list, name='request_list'),
    path('requests/my/', views.my_requests, name='my_requests'),
    path(
        'requests/pending/',
        views.pending_approvals,
        name='pending_approvals'
    ),
    path('requests/create/', views.request_create, name='request_create'),
    path('requests/<int:pk>/', views.request_detail, name='request_detail'),

    # Оборудование
    path('equipment/', views.equipment_list, name='equipment_list'),
    path(
        'equipment/<int:pk>/',
        views.equipment_detail,
        name='equipment_detail'
    ),

    # Бюджеты
    path('budgets/', views.budget_list, name='budget_list'),
    path('budgets/create/', views.budget_create, name='budget_create'),
    path('budgets/<int:pk>/edit/', views.budget_edit, name='budget_edit'),
]
