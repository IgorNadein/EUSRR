# backend\api\urls.py

from django.urls import include, path
from drf_spectacular.views import (
    SpectacularAPIView,
    SpectacularRedocView,
    SpectacularSwaggerView,
)
from rest_framework.permissions import AllowAny

from .auth.views import JWTTokenRefreshView, PhoneOrEmailTokenObtainPairView
from .docs_views import AsyncAPIDocsView, AsyncAPISchemaView
app_name = "api"

urlpatterns = [
    path(
        "schema/",
        SpectacularAPIView.as_view(
            permission_classes=[AllowAny],
            authentication_classes=[],
        ),
        name="schema",
    ),
    path(
        "docs/",
        SpectacularSwaggerView.as_view(
            url_name="api:schema",
            permission_classes=[AllowAny],
            authentication_classes=[],
        ),
        name="swagger-ui",
    ),
    path(
        "redoc/",
        SpectacularRedocView.as_view(
            url_name="api:schema",
            permission_classes=[AllowAny],
            authentication_classes=[],
        ),
        name="redoc",
    ),
    path("ws/schema/", AsyncAPISchemaView.as_view(), name="ws-schema"),
    path("ws/docs/", AsyncAPIDocsView.as_view(), name="ws-docs"),
    path("v1/", include(("api.v1.urls", "v1"), namespace="v1")),
    path(
        "auth/token/",
        PhoneOrEmailTokenObtainPairView.as_view(),
        name="token_obtain_pair",
    ),
    path(
        "auth/token/refresh/",
        JWTTokenRefreshView.as_view(),
        name="token_refresh",
    ),
]
