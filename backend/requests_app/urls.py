# urls.py
from django.urls import path

from .views import (
    RequestDetailView,
    RequestsView,
    request_comment_add,
    request_comment_delete,
    request_comments,
)

app_name = "requests"

urlpatterns = [
    path("", RequestsView.as_view(), name="request_list"),
    path("<int:pk>/", RequestDetailView.as_view(), name="request_detail"),
    path("comments/<int:pk>/", request_comments, name="request_comments"),
    path(
        "comments/<int:pk>/add/",
        request_comment_add,
        name="request_comment_add",
    ),
    path(
        "comments/<int:pk>/delete/<int:comment_id>/",
        request_comment_delete,
        name="request_comment_delete",
    ),
]
