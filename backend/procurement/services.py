"""
Сервисы для модуля закупок и инвентаря.
"""

from typing import Optional

from django.db import transaction
from django.utils import timezone

from procurement.constants import (
    ApprovalStatus,
    get_default_approval_step_name,
)


class InventoryNumberGenerator:
    """Генератор инвентарных номеров."""

    PREFIX = "INV"

    @classmethod
    def generate(cls, year: Optional[int] = None) -> str:
        """
        Генерирует уникальный инвентарный номер.

        Формат: INV-YYYY-NNNN
        Например: INV-2025-0001, INV-2025-0002
        """
        from .models import Equipment

        if year is None:
            year = timezone.now().year

        # Находим последний номер за этот год
        prefix = f"{cls.PREFIX}-{year}-"
        last_equipment = (
            Equipment.objects.filter(inventory_number__startswith=prefix)
            .order_by("-inventory_number")
            .first()
        )

        if last_equipment:
            # Извлекаем номер из последнего инвентарного номера
            try:
                last_num = int(last_equipment.inventory_number.split("-")[-1])
            except (ValueError, IndexError):
                last_num = 0
        else:
            last_num = 0

        new_num = last_num + 1
        return f"{cls.PREFIX}-{year}-{new_num:04d}"

    @classmethod
    def validate(cls, inventory_number: str) -> bool:
        """
        Проверяет формат инвентарного номера.

        Returns:
            True если формат верный, False иначе
        """
        parts = inventory_number.split("-")
        if len(parts) != 3:
            return False

        prefix, year_str, num_str = parts

        if prefix != cls.PREFIX:
            return False

        try:
            year = int(year_str)
            if year < 2000 or year > 2100:
                return False
        except ValueError:
            return False

        try:
            num = int(num_str)
            if num < 1:
                return False
        except ValueError:
            return False

        return True


class ProcurementApprovalResolver:
    """Определяет согласующих для заявки на закупку.

    Состав этапов и их порядок берутся из таблицы ApprovalRoute.
    Для этапа типа department_head согласующий определяется
    через Department.head.
    """

    @classmethod
    def resolve_approval_step(cls, procurement_request, route):
        from .models import ApprovalRoute

        if route is None:
            return None

        if not isinstance(route, ApprovalRoute):
            route = (
                ApprovalRoute.objects.select_related("employee")
                .filter(
                    priority=route,
                )
                .first()
            )
            if route is None:
                return None

        step_name = route.name or get_default_approval_step_name(
            route.priority,
            resolver_type=route.resolver_type,
        )

        if route.resolver_type == ApprovalRoute.ResolverType.DEPARTMENT_HEAD:
            head = procurement_request.department.head
            if head and head.is_active:
                return route.priority, head, step_name
            return None

        if route.employee and route.employee.is_active:
            return route.priority, route.employee, step_name
        return None

    @classmethod
    def resolve_approver(cls, procurement_request, priority: int):
        step = cls.resolve_approval_step(procurement_request, priority)
        if step is None:
            return None
        return step[1]

    @classmethod
    def resolve_required_approvers(cls, procurement_request):
        resolved, missing = [], []
        for route in procurement_request.get_required_approval_routes():
            step = cls.resolve_approval_step(procurement_request, route)
            if step:
                resolved.append(step)
            else:
                missing.append(route.priority)
        resolved.sort(key=lambda item: item[0])
        return resolved, missing

    @classmethod
    def resolve_required_approvers_detailed(cls, procurement_request):
        """Возвращает согласующих и подробности по пропущенным этапам."""
        from .models import ApprovalRoute

        resolved = []
        missing = []

        for route in procurement_request.get_required_approval_routes():
            step = cls.resolve_approval_step(procurement_request, route)
            if step:
                resolved.append(step)
                continue

            step_label = route.name or get_default_approval_step_name(
                route.priority,
                resolver_type=route.resolver_type,
            )
            reason = "unknown"
            if route.resolver_type == ApprovalRoute.ResolverType.DEPARTMENT_HEAD:
                reason = "department_head_missing"
            elif route.resolver_type == ApprovalRoute.ResolverType.FIXED_EMPLOYEE:
                reason = "approver_missing_or_inactive"

            missing.append(
                {
                    "priority": route.priority,
                    "step_name": step_label,
                    "resolver_type": route.resolver_type,
                    "reason": reason,
                }
            )

        resolved.sort(key=lambda item: item[0])
        return resolved, missing

    @classmethod
    def get_available_approval(cls, user, procurement_request):
        if not user or not user.is_authenticated:
            return None

        pending = procurement_request.approvals.filter(
            status=ApprovalStatus.PENDING,
        ).order_by("priority", "created_at", "id")
        first_pending = pending.first()
        if first_pending is None:
            return None

        return pending.filter(
            approver=user,
            priority__gte=first_pending.priority,
        ).first()

    @classmethod
    def user_can_approve(cls, user, procurement_request) -> bool:
        if not user or not user.is_authenticated:
            return False
        return cls.get_available_approval(user, procurement_request) is not None


class EquipmentService:
    """Сервис для операций с оборудованием."""

    @classmethod
    @transaction.atomic
    def create_equipment(
        cls,
        name: str,
        category,
        department,
        purchase_date,
        purchase_cost,
        **kwargs,
    ):
        """
        Создаёт новое оборудование с авто-генерацией инвентарного номера.
        """
        from .models import Equipment

        # Генерируем инвентарный номер если не указан
        if "inventory_number" not in kwargs or not kwargs["inventory_number"]:
            kwargs["inventory_number"] = InventoryNumberGenerator.generate()

        equipment = Equipment.objects.create(
            name=name,
            category=category,
            department=department,
            purchase_date=purchase_date,
            purchase_cost=purchase_cost,
            **kwargs,
        )

        return equipment

    @classmethod
    @transaction.atomic
    def assign_to_person(
        cls, equipment, person, location: Optional[str] = None
    ):
        """
        Назначает оборудование ответственному лицу.
        """
        from .constants import EquipmentStatus
        from .models import EquipmentTransferLog

        old_person = equipment.responsible_person
        old_location = equipment.location

        equipment.responsible_person = person
        equipment.status = EquipmentStatus.IN_USE
        if location:
            equipment.location = location
        equipment.save()

        # Логируем передачу
        EquipmentTransferLog.objects.create(
            equipment=equipment,
            from_person=old_person,
            to_person=person,
            from_location=old_location,
            to_location=location or equipment.location,
            transfer_type="assignment",
        )

        return equipment

    @classmethod
    @transaction.atomic
    def transfer(
        cls,
        equipment,
        to_department,
        to_person=None,
        to_location: Optional[str] = None,
        reason: str = "",
    ):
        """
        Перемещает оборудование в другой отдел.
        """
        from .models import EquipmentTransferLog

        old_department = equipment.department
        old_person = equipment.responsible_person
        old_location = equipment.location

        equipment.department = to_department
        equipment.responsible_person = to_person
        if to_location:
            equipment.location = to_location
        equipment.save()

        # Логируем передачу
        EquipmentTransferLog.objects.create(
            equipment=equipment,
            from_department=old_department,
            to_department=to_department,
            from_person=old_person,
            to_person=to_person,
            from_location=old_location,
            to_location=to_location or "",
            transfer_type="transfer",
            reason=reason,
        )

        return equipment

    @classmethod
    @transaction.atomic
    def write_off(cls, equipment, reason: str):
        """
        Списывает оборудование.
        """
        from .constants import EquipmentStatus

        equipment.status = EquipmentStatus.WRITTEN_OFF
        equipment.notes = (
            f"{equipment.notes}\n\n"
            f"[{timezone.now().strftime('%Y-%m-%d')}] Списано: {reason}"
        ).strip()
        equipment.save()

        return equipment

    @classmethod
    @transaction.atomic
    def add_maintenance_record(
        cls,
        equipment,
        maintenance_type: str,
        description: str,
        performed_by,
        cost=None,
        date=None,
    ):
        """
        Добавляет запись о техническом обслуживании.
        """
        from decimal import Decimal
        from .models import MaintenanceRecord
        from .constants import EquipmentStatus

        if date is None:
            date = timezone.now().date()

        if cost is None:
            cost = Decimal("0.00")

        record = MaintenanceRecord.objects.create(
            equipment=equipment,
            date=date,
            type=maintenance_type,
            description=description,
            cost=cost,
            performed_by=performed_by,
        )

        # Если на ремонте - обновляем статус
        if maintenance_type == "repair":
            equipment.status = EquipmentStatus.IN_REPAIR
            equipment.save()

        return record
