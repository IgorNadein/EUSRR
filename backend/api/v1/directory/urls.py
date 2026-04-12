from django.urls import path

from .views import DirectoryMeLoginAPIView, DirectoryMeLoginRefreshAPIView

app_name = "directory"

urlpatterns = [
    path("me/login/", DirectoryMeLoginAPIView.as_view(), name="me-login"),
    path(
        "me/login/refresh/",
        DirectoryMeLoginRefreshAPIView.as_view(),
        name="me-login-refresh",
    ),
]
