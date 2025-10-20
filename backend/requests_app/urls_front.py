# urls.py
from django.urls import path
from .views_front import (
    RequestsView,
    request_comments,
    request_comment_add,
)

app_name = "requests"

urlpatterns = [
    path("", RequestsView.as_view(), name="request_list"),
    path("comments/<int:pk>/", request_comments, name="request_comments"),
    path(
        "comments/<int:pk>/add/",
        request_comment_add,
        name="request_comment_add",
    ),
]
