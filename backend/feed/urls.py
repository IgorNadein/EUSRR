from django.urls import path
from . import views

app_name = 'feed'

urlpatterns = [
    path('', views.feed_list, name='feed_list'),
    path('departments/<int:pk>/', views.department_feed, name='department_feed'),
    path('employees/<int:pk>/', views.employee_feed, name='employee_feed'),
    path('post/<int:pk>/', views.post_detail, name='post_detail'),
    path('post/new/', views.post_create, name='post_create'),
    path('post/<int:pk>/pin/', views.pin_post, name='pin_post'),

]
