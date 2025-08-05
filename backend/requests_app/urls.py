from django.urls import path
from . import views

app_name = 'requests_app'

urlpatterns = [
    path('my/', views.my_requests, name='my_requests'),
    path('new/', views.request_create, name='request_create'),
    path('my/<int:pk>/', views.request_detail, name='request_detail'),
    path('all/', views.all_requests, name='all_requests'),
    path('process/<int:pk>/', views.request_process, name='request_process'),
    path('delete/<int:pk>/', views.request_delete, name='request_delete'),

]
