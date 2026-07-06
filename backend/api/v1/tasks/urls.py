from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import (
    TaskBoardViewSet,
    TaskColumnViewSet,
    TaskLabelViewSet,
    TaskViewSet,
)

app_name = "tasks"

router = DefaultRouter()
router.register(r"boards", TaskBoardViewSet, basename="task-board")
router.register(r"columns", TaskColumnViewSet, basename="task-column")
router.register(r"labels", TaskLabelViewSet, basename="task-label")
router.register(r"", TaskViewSet, basename="task")

urlpatterns = [
    path("", include(router.urls)),
]
