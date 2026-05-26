# backend/procurement/constants.py
"""
Константы для модуля закупок и инвентаря.
"""

from django.db import models


class ProcurementStatus(models.TextChoices):
    """Статусы заявки на закупку."""
    DRAFT = 'draft', 'Черновик'
    WAITING = 'waiting', 'Ожидает'
    PENDING = 'pending', 'На согласовании'
    APPROVED = 'approved', 'Одобрено'
    REJECTED = 'rejected', 'Отклонено'
    IN_PROGRESS = 'in_progress', 'В работе'
    COMPLETED = 'completed', 'Завершено'
    CANCELLED = 'cancelled', 'Отменено'


class UrgencyLevel(models.TextChoices):
    """Уровень срочности заявки."""
    LOW = 'low', 'Низкая'
    MEDIUM = 'medium', 'Средняя'
    HIGH = 'high', 'Высокая'
    CRITICAL = 'critical', 'Критическая'


class ProcurementFulfillmentStatus(models.TextChoices):
    """Рабочий статус исполнения заявки по позициям."""
    PENDING = 'pending', 'Ожидает обработки'
    PARTIALLY_ORDERED = 'partially_ordered', 'Заказано частично'
    ORDERED = 'ordered', 'Заказано'
    PARTIALLY_RECEIVED = 'partially_received', 'Прибыл частично'
    COMPLETED = 'completed', 'Выполнено'
    ISSUES = 'issues', 'Выполнено с проблемами'


class ProcurementItemExecutionStatus(models.TextChoices):
    """Рабочий статус отдельной позиции заявки."""
    PENDING = 'pending', 'Не выполнено'
    ORDERED = 'ordered', 'Заказано'
    REJECTED = 'rejected', 'Отказано'
    RECEIVED = 'received', 'Получено'
    COMPLETED_WITH_ISSUE = 'completed_with_issue', 'Выполнено с замечанием'
    EDITED = 'edited', 'Отредактировано'
    DEFECTIVE = 'defective', 'Брак / перезаказ'


def get_default_approval_step_name(priority: int,
                                   resolver_type: str | None = None) -> str:
    if resolver_type == 'department_head':
        return 'Руководитель отдела'
    return f'Этап {priority}'


class ApprovalStatus(models.TextChoices):
    """Статус согласования."""
    PENDING = 'pending', 'Ожидает решения'
    APPROVED = 'approved', 'Одобрено'
    REJECTED = 'rejected', 'Отклонено'


class EquipmentStatus(models.TextChoices):
    """Статус оборудования."""
    AVAILABLE = 'available', 'Доступно'
    IN_USE = 'in_use', 'В использовании'
    MAINTENANCE = 'maintenance', 'На обслуживании'
    REPAIR = 'repair', 'В ремонте'
    RETIRED = 'retired', 'Списано'
    LOST = 'lost', 'Утеряно'


class MaintenanceType(models.TextChoices):
    """Тип технического обслуживания."""
    INSPECTION = 'inspection', 'Осмотр/проверка'
    MAINTENANCE = 'maintenance', 'Плановое ТО'
    REPAIR = 'repair', 'Ремонт'
    UPGRADE = 'upgrade', 'Модернизация'
    CLEANING = 'cleaning', 'Чистка'
