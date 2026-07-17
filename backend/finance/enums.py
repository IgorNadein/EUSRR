"""Stable database values used by the finance payroll adapter."""

from django.db import models


class ApprovalStatus(models.TextChoices):
    DRAFT = "draft", "Черновик"
    APPROVED = "approved", "Утверждено"
    VOIDED = "voided", "Аннулировано"


class InputSource(models.TextChoices):
    MANUAL = "manual", "Вручную"
    EXCEL = "excel", "Excel"
    API = "api", "API"
    ATTENDANCE = "attendance", "Посещаемость"


class PayrollComponentKind(models.TextChoices):
    EARNING = "earning", "Начисление"
    ADJUSTMENT_CREDIT = "adjustment_credit", "Коррекция +"
    ADJUSTMENT_DEBIT = "adjustment_debit", "Коррекция −"
    DEDUCTION = "deduction", "Удержание"
    PAYMENT = "payment", "Выплата"


class PayrollPeriodStatus(models.TextChoices):
    OPEN = "open", "Открыт"
    CALCULATED = "calculated", "Рассчитан"
    REVIEW = "review", "На проверке"
    APPROVED = "approved", "Утверждён"
    PUBLISHED = "published", "Опубликован"
    CLOSED = "closed", "Закрыт"


class PayrollRunStatus(models.TextChoices):
    CALCULATED = "calculated", "Рассчитан"
    REVIEW = "review", "На проверке"
    APPROVED = "approved", "Утверждён"
    PUBLISHED = "published", "Опубликован"
    RETURNED = "returned", "Возвращён на исправление"
    SUPERSEDED = "superseded", "Заменён новой ревизией"
