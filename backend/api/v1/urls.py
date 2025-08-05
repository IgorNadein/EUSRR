from django.urls import path, include
from rest_framework.routers import DefaultRouter
from .views import (
    EmployeeViewSet, DepartmentViewSet, EmployeeActionViewSet,
    EmployeePositionViewSet, AbsenceViewSet, SkillViewSet, EducationViewSet
)

router = DefaultRouter()
router.register(r'employees', EmployeeViewSet, basename='employee')
router.register(r'departments', DepartmentViewSet, basename='department')
router.register(r'actions', EmployeeActionViewSet, basename='action')
router.register(r'positions', EmployeePositionViewSet, basename='position')
router.register(r'absences', AbsenceViewSet, basename='absence')
router.register(r'skills', SkillViewSet, basename='skill')
router.register(r'educations', EducationViewSet, basename='education')

urlpatterns = [
    path('', include(router.urls)),
]
