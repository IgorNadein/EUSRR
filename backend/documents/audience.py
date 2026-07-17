"""Единые правила вычисления аудиторий документа."""

from django.contrib.auth import get_user_model
from django.db.models import Q, QuerySet

from .models import Document


Employee = get_user_model()


def document_access_audience(document: Document) -> QuerySet:
    """Активные сотрудники, которым документ адресован для просмотра."""
    employees = Employee.objects.filter(is_active=True)
    if document.sent_to_all:
        return employees

    return employees.filter(
        Q(pk__in=document.recipients.values("pk"))
        | Q(
            departments_links__department__in=document.departments.all(),
            departments_links__is_active=True,
        )
    ).distinct()


def document_acknowledgement_audience(document: Document) -> QuerySet:
    """Активные сотрудники, обязанные ознакомиться с документом."""
    access_audience = document_access_audience(document)
    if not document.acknowledgement_required:
        return access_audience.none()
    if document.acknowledgement_for_all:
        return access_audience

    selected = Employee.objects.filter(is_active=True).filter(
        Q(pk__in=document.acknowledgement_recipients.values("pk"))
        | Q(
            departments_links__department__in=(
                document.acknowledgement_departments.all()
            ),
            departments_links__is_active=True,
        )
    )
    return selected.filter(pk__in=access_audience.values("pk")).distinct()


def user_requires_document_acknowledgement(document: Document, user) -> bool:
    """Нужно ли конкретному сотруднику подтверждать ознакомление."""
    if not getattr(user, "is_authenticated", False):
        return False
    return document_acknowledgement_audience(document).filter(pk=user.pk).exists()
