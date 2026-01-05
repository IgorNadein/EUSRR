# backend\api\urls.py

from django.urls import include, path
from rest_framework_simplejwt.views import TokenRefreshView

from .auth.views import PhoneOrEmailTokenObtainPairView
app_name = "api"

urlpatterns = [
    path("v1/", include(("api.v1.urls", "v1"), namespace="v1")),
    path(
        "auth/token/",
        PhoneOrEmailTokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("v1/", include("notifications.api_urls")),
]
