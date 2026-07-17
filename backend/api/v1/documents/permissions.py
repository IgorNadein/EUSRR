# backend/api/v1/documents/permissions.py
from __future__ import annotations
from typing import Any
from copy import deepcopy
from rest_framework.permissions import SAFE_METHODS
from rest_framework.permissions import DjangoModelPermissions
from rest_framework.request import Request
from rest_framework.views import View
from ..permissions import AdminOrActionOrModelPerms


def _has_any_model_perm(
    user,
    app_label: str,
    model_name: str,
    actions=("view", "change", "add", "delete"),
) -> bool:
    """Проверяет наличие любого модельного права из набора."""
    for act in actions:
        code = f"{act}_{model_name}"
        if user.has_perm(f"{app_label}.{code}"):
            return True
    return False


def _user_has_document_access(user, obj) -> bool:
    """Проверяет пользовательский доступ к конкретному документу."""
    if getattr(obj, "sent_to_all", False) and getattr(user, "is_active", False):
        return True

    if getattr(obj, "uploaded_by_id", None) == getattr(user, "pk", None):
        return True

    if obj.recipients.filter(pk=user.pk, is_active=True).exists():
        return True

    return obj.departments.filter(
        employeedepartment__employee=user,
        employeedepartment__is_active=True,
    ).exists()


class DocumentReadOrModelPerms(AdminOrActionOrModelPerms):
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
        action = getattr(view, "action", None)

        # SAFE + acknowledge/download → достаточно быть аутентифицированным
        if request.method in SAFE_METHODS or action in (
            "acknowledge",
            "download",
            "archive",
            "comments",
            "document_comment",
        ):
            return bool(request.user and request.user.is_authenticated)

        # CREATE → разрешаем всем аутентифицированным (документы создаются
        # неопубликованными)
        if action == "create":
            return bool(request.user and request.user.is_authenticated)

        # update/destroy и related documents - проверяем на уровне объекта
        if action in (
            "update",
            "partial_update",
            "destroy",
            "add_related",
            "remove_related",
            "revert",
        ):
            return bool(request.user and request.user.is_authenticated)

        # небезопасные → staff ИЛИ стандартные модельные права
        # (add/change/delete)
        if request.user and request.user.is_staff:
            return True
        return super().has_permission(request, view)

    def has_object_permission(
        self, request: Request, view: View, obj: Any
    ) -> bool:
        user = request.user
        if not (user and user.is_authenticated):
            return False

        action = getattr(view, "action", None)

        # Полный доступ при наличии ЛЮБОГО модельного права или staff
        if user.is_staff or _has_any_model_perm(user, "documents", "document"):
            return True

        # revert - откатить версию может автор или менеджер
        if action == "revert":
            return user.has_perm("documents.change_document", obj)

        # add_related/remove_related → проверяем django-rules change_document
        if action in ("add_related", "remove_related"):
            return user.has_perm("documents.change_document", obj)

        if action in ("comments", "document_comment"):
            return _user_has_document_access(user, obj)

        # PUT/PATCH → проверяем django-rules change_document
        if request.method in ("PUT", "PATCH"):
            return user.has_perm("documents.change_document", obj)

        # DELETE → проверяем django-rules delete_document
        if request.method == "DELETE":
            return user.has_perm("documents.delete_document", obj)

        # SAFE/ack/download без модельных прав → только пользователи,
        # которым документ доступен.
        if request.method in SAFE_METHODS or action in (
            "acknowledge",
            "download",
            "archive",
            "comments",
            "document_comment",
        ):
            return _user_has_document_access(user, obj)

        # Небезопасные без прав — нельзя (POST custom actions)
        return False
