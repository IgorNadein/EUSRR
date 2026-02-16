"""EmployeeActionViewSet — кадровые события (приём, увольнение и т.д.)."""

from __future__ import annotations

import logging

from django.conf import settings
from django.db import transaction
from django.utils import timezone
from employees.constants import ACTION_DISMISSED
from employees.ldap.directory_service import DirectoryService
from employees.ldap.errors import (
    DirectoryDbError,
    DirectoryLdapError,
    DirectoryServiceError,
)
from employees.models import (
    EmployeeAction,
    EmployeeDepartment,
    LdapSyncState,
)
from rest_framework import filters, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from ..permissions import AdminOrActionOrModelPerms
from ..serializers import EmployeeActionSerializer
from ._helpers import HistoryActionMixin, _is_ldap_enabled

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
        qs = EmployeeAction.objects.select_related("employee").order_by(*self.ordering)
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
        emp = action_obj.employee
        ldap_enabled = _is_ldap_enabled()

        if action_obj.action == ACTION_DISMISSED:
            # Сначала деактивируем сотрудника
            if emp.is_active:
                emp.is_active = False
                emp.save(update_fields=["is_active"])

            # Деактивируем связи с отделами в БД
            EmployeeDepartment.objects.filter(employee=emp, is_active=True).update(
                is_active=False, date_to=timezone.now().date()
            )

            # Синхронизируем с LDAP
            if ldap_enabled:
                try:
                    svc = DirectoryService()
                    has_ldap_dn = LdapSyncState.objects.filter(
                        model="employee", object_pk=str(emp.pk), ldap_dn__isnull=False
                    ).exists()

                    if has_ldap_dn:
                        svc.update_user(emp, changes={"is_active": False})

                        active_departments = EmployeeDepartment.objects.filter(
                            employee=emp
                        ).select_related("department")

                        departments_processed = False
                        for emp_dept in active_departments:
                            try:
                                svc.remove_member(emp_dept.department, emp)
                                departments_processed = True
                            except (
                                DirectoryLdapError,
                                DirectoryDbError,
                                DirectoryServiceError,
                            ) as e:
                                logger.error(
                                    f"Failed to remove dismissed employee from department: "
                                    f"employee_id={emp.id}, department_id={emp_dept.department.id}, error={e}"
                                )

                        if not departments_processed:
                            try:
                                from employees.ldap.infrastructure.connections import (
                                    _ldap,
                                )
                                from employees.ldap.repositories.ldap_repository import (
                                    ensure_container_exists,
                                )
                                from employees.ldap.utils.ldap_utils import (
                                    get_base_dn_for_employee,
                                )

                                sync_state = LdapSyncState.objects.filter(
                                    model="employee", object_pk=str(emp.pk)
                                ).first()

                                if sync_state and sync_state.ldap_dn:
                                    target_base = get_base_dn_for_employee(emp)
                                    current_dn = sync_state.ldap_dn

                                    if not current_dn.lower().endswith(
                                        target_base.lower()
                                    ):
                                        with _ldap() as conn:
                                            ensure_container_exists(conn, target_base)
                                            new_dn = (
                                                svc._user_service._move_user_to_base(
                                                    conn, current_dn, target_base
                                                )
                                            )
                                            sync_state.touch(
                                                ldap_dn=new_dn, sync_dir="ldap"
                                            )
                                            logger.info(
                                                f"Dismissed employee without department moved to OU=Dismissed: "
                                                f"employee_id={emp.id}, new_dn={new_dn}"
                                            )
                            except Exception as e:
                                logger.error(
                                    f"Failed to move dismissed employee without department to OU=Dismissed: "
                                    f"employee_id={emp.id}, error={e}"
                                )
                except (
                    DirectoryLdapError,
                    DirectoryDbError,
                    DirectoryServiceError,
                ) as e:
                    logger.error(
                        f"Failed to disable user in LDAP during dismissal: "
                        f"employee_id={emp.id}, error={e}"
                    )
        else:
            # Любое иное событие делает сотрудника активным
            was_inactive = not emp.is_active
            if was_inactive:
                emp.is_active = True
                emp.save(update_fields=["is_active"])

            if ldap_enabled:
                try:
                    svc = DirectoryService()
                    has_ldap_dn = LdapSyncState.objects.filter(
                        model="employee", object_pk=str(emp.pk), ldap_dn__isnull=False
                    ).exists()

                    if has_ldap_dn:
                        svc.update_user(emp, changes={"is_active": True})

                        if was_inactive:
                            try:
                                sync_state = LdapSyncState.objects.get(
                                    model="employee", object_pk=str(emp.pk)
                                )
                                current_dn = sync_state.ldap_dn
                                dismissed_base = getattr(
                                    settings, "LDAP_DISMISSED_BASE", ""
                                )

                                if dismissed_base and current_dn.lower().endswith(
                                    dismissed_base.lower()
                                ):
                                    users_base = getattr(
                                        settings, "LDAP_USERS_BASE", None
                                    ) or getattr(settings, "LDAP_USER_BASE", None)
                                    if users_base:
                                        from employees.ldap.infrastructure.connections import (
                                            _ldap,
                                        )
                                        from employees.ldap.repositories.ldap_repository import (
                                            ensure_container_exists,
                                        )

                                        with _ldap() as conn:
                                            ensure_container_exists(conn, users_base)
                                            new_dn = (
                                                svc._user_service._move_user_to_base(
                                                    conn, current_dn, users_base
                                                )
                                            )
                                            sync_state.touch(
                                                ldap_dn=new_dn, sync_dir="ldap"
                                            )
                                            logger.info(
                                                f"Restored employee moved from Dismissed to Users: "
                                                f"employee_id={emp.id}, new_dn={new_dn}"
                                            )
                            except Exception as e:
                                logger.error(
                                    f"Failed to move restored employee from Dismissed to Users: "
                                    f"employee_id={emp.id}, error={e}"
                                )
                except (
                    DirectoryLdapError,
                    DirectoryDbError,
                    DirectoryServiceError,
                ) as e:
                    logger.error(
                        f"Failed to enable user in LDAP during action: "
                        f"employee_id={emp.id}, action={action_obj.action}, error={e}"
                    )

    @transaction.atomic
    def perform_create(self, serializer):
        obj = serializer.save()
        self._apply_effects(obj)

    @transaction.atomic
    def perform_update(self, serializer):
        obj = serializer.save()
        self._apply_effects(obj)
