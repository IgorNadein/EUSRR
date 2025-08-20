from employees.models import (Absence, Department, Education, Employee,
                              EmployeeAction, EmployeePosition, Skill)
from rest_framework import permissions, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response

from ..permissions import IsDepartmentHeadOrAdmin, IsHR, IsSelfOrAdmin
from .serializers import (AbsenceSerializer, DepartmentSerializer,
                          EducationSerializer, EmployeeActionSerializer,
                          EmployeePositionSerializer, EmployeeSerializer,
                          SkillSerializer)


class EmployeeViewSet(viewsets.ModelViewSet):
    queryset = Employee.objects.all().prefetch_related("skills", "positions", "actions")
    serializer_class = EmployeeSerializer

    def get_permissions(self):
        if self.action in [
            "update",
            "partial_update",
            "destroy",
            "set_avatar",
            "add_skill",
        ]:
            return [IsSelfOrAdmin()]
        return [permissions.IsAuthenticated()]

    @action(detail=True, methods=["post"], permission_classes=[IsSelfOrAdmin])
    def set_avatar(self, request, pk=None):
        employee = self.get_object()
        avatar = request.FILES.get("avatar")
        if avatar:
            employee.avatar = avatar
            employee.save()
            return Response({"status": "avatar set"})
        return Response({"error": "No file"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], permission_classes=[IsSelfOrAdmin])
    def add_skill(self, request, pk=None):
        employee = self.get_object()
        skill_name = request.data.get("skill")
        if skill_name:
            skill, _ = Skill.objects.get_or_create(name=skill_name)
            employee.skills.add(skill)
            return Response({"status": "skill added"})
        return Response({"error": "No skill"}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=["post"], permission_classes=[IsSelfOrAdmin])
    def request_absence(self, request, pk=None):
        return Response(
            {"status": "Not implemented"}, status=status.HTTP_501_NOT_IMPLEMENTED
        )

    @action(detail=True, methods=["post"], permission_classes=[IsSelfOrAdmin])
    def request_transfer(self, request, pk=None):
        return Response(
            {"status": "Not implemented"}, status=status.HTTP_501_NOT_IMPLEMENTED
        )


class DepartmentViewSet(viewsets.ModelViewSet):
    queryset = Department.objects.all()
    serializer_class = DepartmentSerializer
    permission_classes = [IsDepartmentHeadOrAdmin]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Department.objects.all()
        return Department.objects.filter(head=user)


class EmployeeActionViewSet(viewsets.ModelViewSet):
    queryset = EmployeeAction.objects.all()
    serializer_class = EmployeeActionSerializer
    permission_classes = [IsHR | IsDepartmentHeadOrAdmin]


class EmployeePositionViewSet(viewsets.ModelViewSet):
    queryset = EmployeePosition.objects.all()
    serializer_class = EmployeePositionSerializer
    permission_classes = [IsHR | IsDepartmentHeadOrAdmin]


class AbsenceViewSet(viewsets.ModelViewSet):
    serializer_class = AbsenceSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff or user.is_superuser:
            return Absence.objects.all()
        return Absence.objects.filter(employee=user)

    def perform_create(self, serializer):
        serializer.save(employee=self.request.user)

    def perform_update(self, serializer):
        if (
            serializer.instance.employee != self.request.user
            and not self.request.user.is_staff
        ):
            raise PermissionDenied("Вы не можете редактировать чужие заявления.")
        serializer.save()

    def perform_destroy(self, instance):
        if instance.employee != self.request.user and not self.request.user.is_staff:
            raise PermissionDenied("Вы не можете удалить чужое заявление.")
        instance.delete()


class SkillViewSet(viewsets.ModelViewSet):
    queryset = Skill.objects.all()
    serializer_class = SkillSerializer
    permission_classes = [permissions.IsAuthenticated]


class EducationViewSet(viewsets.ModelViewSet):
    serializer_class = EducationSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        user = self.request.user
        if user.is_staff:
            return Education.objects.all()
        return Education.objects.filter(employee=user)
