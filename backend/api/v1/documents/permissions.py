# backend/api/v1/documents/permissions.py
from __future__ import annotations
from typing import Any
from copy import deepcopy
from django.contrib.auth.models import AbstractBaseUser
from rest_framework.permissions import BasePermission, SAFE_METHODS
from rest_framework.permissions import DjangoModelPermissions
from rest_framework.request import Request
from rest_framework.views import View


def _has_any_model_perm(
    user, app_label: str, model_name: str, actions=("view", "change", "add", "delete")
) -> bool:
    """Проверяет наличие любого модельного права из набора."""
    for act in actions:
        code = f"{act}_{model_name}"
        if user.has_perm(f"{app_label}.{code}"):
            return True
    return False


class DocumentReadOrModelPerms(DjangoModelPermissions):
    """Чтение/скачивание/ознакомление: любой аутентифицированный,
    но доступ только к 'своим' документам (или если есть модельные права/админ).
    Создание/редактирование/удаление: только админы и обладатели модельных прав.

    Raises:
        PermissionDenied: если нет доступа к конкретному документу.
    """

    perms_map = deepcopy(DjangoModelPermissions.perms_map)
    perms_map["GET"] = []
    perms_map["HEAD"] = []
    perms_map["OPTIONS"] = []

    def has_permission(self, request: Request, view: View) -> bool:
        # SAFE + acknowledge/download → достаточно быть аутентифицированным
        if request.method in SAFE_METHODS or getattr(view, "action", None) in (
            "acknowledge",
            "download",
        ):
            return bool(request.user and request.user.is_authenticated)

        # небезопасные → staff ИЛИ стандартные модельные права (add/change/delete)
        if request.user and request.user.is_staff:
            return True
        return super().has_permission(request, view)

    def has_object_permission(self, request: Request, view: View, obj: Any) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False

        # Полный доступ при наличии ЛЮБОГО модельного права или staff
        if user.is_staff or _has_any_model_perm(user, "documents", "document"):
            return True

        # SAFE/ack/download без модельных прав → только получатели или sent_to_all
        if request.method in SAFE_METHODS or getattr(view, "action", None) in (
            "acknowledge",
            "download",
        ):
            if getattr(obj, "sent_to_all", False):
                return True
            return obj.recipients.filter(pk=user.pk, is_active=True).exists()

        # Небезопасные без прав — нельзя
        return False
