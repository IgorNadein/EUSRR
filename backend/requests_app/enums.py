from __future__ import annotations
from django.db.models import TextChoices


class RequestType(TextChoices):
    """Перечень типов заявлений (значение хранится в БД)."""

    VACATION = "vacation", "Отпуск"
    SICK_LEAVE = "sick_leave", "Больничный"
    DAY_OFF = "day_off", "Отгул"
    TRANSFER = "transfer", "Перевод"
    DISMISSAL = "dismissal", "Увольнение"
    OTHER = "other", "Другое"


class RequestStatus(TextChoices):
    """Статусы жизненного цикла заявления (значение хранится в БД)."""

    DRAFT = "draft", "Черновик"
    PENDING = "pending", "На рассмотрении"
    APPROVED = "approved", "Одобрено"
    REJECTED = "rejected", "Отклонено"
    CANCELLED = "cancelled", "Отменено"


FINAL_STATUS = {
    RequestStatus.APPROVED,
    RequestStatus.REJECTED,
    RequestStatus.CANCELLED,
}
