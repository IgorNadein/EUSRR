"""EmployeeActionViewSet — кадровые события (приём, увольнение и т.д.)."""

from __future__ import annotations

import logging

from django.db import transaction
from django.utils import timezone
from employees.constants import ACTION_DISMISSED
from employees.models import Department, EmployeeAction, EmployeeDepartment
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated

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
        - sync_department_member_to_ldap: удаление из отделов в LDAP
        """
        emp = action_obj.employee

        if action_obj.action == ACTION_DISMISSED:
            # Снимаем с должности руководителя (до деактивации!)
            headed_depts = list(Department.objects.filter(head=emp))
            if headed_depts:
                for dept in headed_depts:
                    logger.info(
                        f"Clearing head of department '{dept.name}' "
                        f"(employee_id={emp.id}) due to dismissal"
                    )
                Department.objects.filter(head=emp).update(
                    head=None, head_appointed_at=None
                )
                # Очищаем managedBy в LDAP (best-effort)
                self._clear_ldap_managed_by(headed_depts)

            # Деактивируем сотрудника (сигнал синхронизирует в LDAP)
            if emp.is_active:
                emp.is_active = False
                emp._ldap_changes = {"is_active": False}
                emp.save(update_fields=["is_active"])

            # Деактивируем связи с отделами (сигналы синхронизируют в LDAP)
            # ВАЖНО: используем save() для каждой записи, чтобы сработали сигналы
            today = timezone.now().date()
            for emp_dept in EmployeeDepartment.objects.filter(
                    employee=emp, is_active=True):
                emp_dept.is_active = False
                emp_dept.date_to = today
                emp_dept.save(update_fields=["is_active", "date_to"])
        else:
            # Любое иное событие делает сотрудника активным (сигнал синхронизирует в
            # LDAP)
            if not emp.is_active:
                emp.is_active = True
                emp._ldap_changes = {"is_active": True}
                emp.save(update_fields=["is_active"])

        # Гарантируем, что DN в правильном OU (Users или Dismissed)
        # Покрывает: восстановление, увольнение без отделов, множественные отделы
        self._ensure_ldap_dn_location(emp)

    @staticmethod
    def _ensure_ldap_dn_location(emp):
        """Гарантирует, что LDAP DN сотрудника в правильном OU.

        is_active=False → OU=Dismissed
        is_active=True  → OU=Users
        """
        from django.conf import settings

        if not getattr(settings, "LDAP_ENABLED", False):
            return

        try:
            from employees.ldap.utils.ldap_utils import get_base_dn_for_employee
            from employees.models import LdapSyncState

            sync_state = LdapSyncState.objects.filter(
                model="employee", object_pk=str(emp.pk)
            ).first()
            if not sync_state or not sync_state.ldap_dn:
                return

            current_dn = sync_state.ldap_dn
            target_base = get_base_dn_for_employee(emp)

            # Проверяем, уже ли в правильном OU
            parts = current_dn.split(",", 1)
            if len(parts) == 2 and parts[1].lower() == target_base.lower():
                return

            from employees.ldap.infrastructure.connections import _ldap
            from employees.ldap.repositories.ldap_repository import (
                ensure_container_exists,
            )

            with _ldap() as conn:
                ensure_container_exists(conn, target_base)
                rdn = parts[0]
                ok = conn.modify_dn(current_dn, rdn, new_superior=target_base)
                if ok:
                    new_dn = f"{rdn},{target_base}"
                    sync_state.ldap_dn = new_dn
                    sync_state.save(update_fields=["ldap_dn"])
                    logger.info(
                        f"Moved employee {emp.id} DN: "
                        f"{current_dn} → {new_dn}"
                    )
                else:
                    logger.warning(
                        f"LDAP modify_dn failed for employee "
                        f"{emp.id}: {conn.result}"
                    )
        except Exception as e:
            logger.warning(
                f"Failed to ensure LDAP DN location for "
                f"employee {emp.id}: {e}"
            )

    @staticmethod
    def _clear_ldap_managed_by(departments):
        """Очищает LDAP managedBy для переданных отделов (best-effort)."""
        from django.conf import settings

        if not getattr(settings, "LDAP_ENABLED", False):
            return

        try:
            from employees.ldap.orm_models import LdapOrganizationalUnit
            from employees.models import LdapSyncState

            for dept in departments:
                sync = LdapSyncState.objects.filter(
                    model="department", object_pk=str(dept.pk)
                ).first()
                if not sync or not sync.ldap_dn:
                    continue
                try:
                    ou = LdapOrganizationalUnit.objects.get(dn=sync.ldap_dn)
                    if ou.managed_by:
                        ou.managed_by = ""
                        ou.save()
                        logger.info(
                            f"Cleared LDAP managedBy for OU={sync.ldap_dn}"
                        )
                except LdapOrganizationalUnit.DoesNotExist:
                    pass
                except Exception as e:
                    logger.warning(
                        f"Failed to clear LDAP managedBy for "
                        f"dept '{dept.name}': {e}"
                    )
        except Exception as e:
            logger.warning(f"Failed to clear LDAP managedBy: {e}")

    @transaction.atomic
    def perform_create(self, serializer):
        obj = serializer.save()
        self._apply_effects(obj)

    @transaction.atomic
    def perform_update(self, serializer):
        obj = serializer.save()
        self._apply_effects(obj)
