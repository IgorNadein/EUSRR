# backend/requests_app/urls.py
from django.urls import path
from . import views

app_name = "requests_app"

urlpatterns = [
    # Коллекция
    path("my/", views.my_requests, name="my_requests"),
    path("all/", views.all_requests, name="all_requests"),
    path("new/", views.request_create, name="request_create"),
    # Элемент (по pk)
    path("<int:pk>/", views.request_detail, name="request_detail"),
    path("<int:pk>/process/", views.request_process, name="request_process"),
    path("<int:pk>/cancel/", views.request_cancel, name="request_cancel"),
    # Комментарии к заявке
    path(
        "<int:pk>/comments/add/", views.request_comment_add, name="request_comment_add"
    ),
    path(
        "<int:pk>/comments/<int:comment_id>/delete/",
        views.request_comment_delete,
        name="request_comment_delete",
    ),
]
