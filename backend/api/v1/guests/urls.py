from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import GuestViewSet, GuestVisitViewSet

app_name = "guests"

router = DefaultRouter()
router.register(r"visits", GuestVisitViewSet, basename="guest-visits")
router.register(r"", GuestViewSet, basename="guests")

urlpatterns = [
    path("", include(router.urls)),
]
