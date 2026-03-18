"""EmployeeActionViewSet — кадровые события (приём, увольнение и т.д.)."""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone
from employees.constants import ACTION_DISMISSED
from employees.models import EmployeeAction, EmployeeDepartment
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ...permissions import AdminOrActionOrModelPerms
from ..serializers import EmployeeActionSerializer
from ._helpers import HistoryActionMixin

logger = logging.getLogger(__name__)


class EmployeeActionViewSet(HistoryActionMixin, viewsets.ModelViewSet):
    """
    /api/v1/employee-actions/
      - GET list/retrieve  — IsAuthenticated
      - POST create        — staff/superuser ИЛИ perm employees.add_employeeaction
      - PATCH/PUT update   — staff/superuser ИЛИ perm employees.change_employeeaction
      - DELETE destroy     — staff/superuser ИЛИ perm employees.delete_employeeaction

    Фильтры: ?employee=<id> ?date_from=ISO ?date_to=ISO
    """

    serializer_class = EmployeeActionSerializer
    permission_classes = [IsAuthenticated]
    filter_backends = [filters.OrderingFilter]
    ordering_fields = ["date", "id"]
    ordering = ["-date"]
    pagination_class = None
    history_diff_fields = ["action", "date", "comment", "extra", "employee_id"]

    def get_queryset(self):
        qs = EmployeeAction.objects.select_related(
            "employee").order_by(*self.ordering)
        qp = self.request.query_params
        emp = qp.get("employee")
        if emp:
            try:
                emp_id = int(emp)
                qs = qs.filter(employee_id=emp_id)
            except (TypeError, ValueError):
                return EmployeeAction.objects.none()
        df = qp.get("date_from")
        dt = qp.get("date_to")
        if df:
            try:
                qs = qs.filter(date__gte=df)
            except Exception:
                pass
        if dt:
            try:
                qs = qs.filter(date__lte=dt)
            except Exception:
                pass
        return qs

    def get_permissions(self):
        if self.action == "create":
            self.required_perm_code = "employees.add_employeeaction"
            return [IsAuthenticated(), AdminOrActionOrModelPerms()]
        if self.action in ("update", "partial_update"):
            self.required_perm_code = "employees.change_employeeaction"
            return [IsAuthenticated(), AdminOrActionOrModelPerms()]
        if self.action == "destroy":
            self.required_perm_code = "employees.delete_employeeaction"
            return [IsAuthenticated(), AdminOrActionOrModelPerms()]
        self.required_perm_code = None
        return super().get_permissions()

    # --- бизнес-эффекты после записи события ---
    def _apply_effects(self, action_obj: EmployeeAction):
        """Применяет эффекты кадрового события.
        
        Работает только с БД. LDAP синхронизация через сигналы:
        - sync_employee_to_ldap_on_save: активация/деактивация в LDAP
        - sync_member (signals_department.py): удаление из отделов в LDAP
        """
        emp = action_obj.employee

        if action_obj.action == ACTION_DISMISSED:
            # Деактивируем сотрудника (сигнал синхронизирует в LDAP)
            if emp.is_active:
                emp.is_active = False
                emp._ldap_changes = {"is_active": False}
                emp.save(update_fields=["is_active"])

            # Деактивируем связи с отделами (сигналы синхронизируют в LDAP)
            EmployeeDepartment.objects.filter(employee=emp, is_active=True).update(
                is_active=False, date_to=timezone.now().date()
            )
        else:
            # Любое иное событие делает сотрудника активным (сигнал синхронизирует в LDAP)
            if not emp.is_active:
                emp.is_active = True
                emp._ldap_changes = {"is_active": True}
                emp.save(update_fields=["is_active"])

    @transaction.atomic
    def perform_create(self, serializer):
        obj = serializer.save()
        self._apply_effects(obj)

    @transaction.atomic
    def perform_update(self, serializer):
        obj = serializer.save()
        self._apply_effects(obj)
