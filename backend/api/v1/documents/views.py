from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import QuerySet
from documents.models import Document, DocumentAcknowledgement
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import (SAFE_METHODS, BasePermission,
                                        IsAuthenticated)
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from ..permissions import AdminOrActionOrModelPerms
from .serializers import DocumentReadSerializer, DocumentWriteSerializer

User = get_user_model()


class DocumentViewSet(ModelViewSet):
    """Полный CRUD по документам + экшен `acknowledge`.

    Создание/обновление поддерживает multipart (для файла) и назначение получателей.
    """

    queryset: QuerySet[Document] = (
        Document.objects.all()
        .select_related("uploaded_by")
        .prefetch_related("recipients")
    )
    permission_classes = [AdminOrActionOrModelPerms]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_serializer_class(self):
        """Выбор сериализатора: на чтение — Read, на запись — Write."""
        if self.action in ("list", "retrieve"):
            return DocumentReadSerializer
        return DocumentWriteSerializer

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Создаёт документ для рассылки.

        Returns:
            Response: 201 Created с данными документа (read-сериализатор).
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        doc = serializer.save()
        read = DocumentReadSerializer(doc, context={"request": request})
        return Response(read.data, status=status.HTTP_201_CREATED)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """Полное обновление документа."""
        return super().update(request, *args, **kwargs)

    @transaction.atomic
    def partial_update(self, request, *args, **kwargs):
        """Частичное обновление документа."""
        return super().partial_update(request, *args, **kwargs)

    @action(methods=["post"], detail=True, permission_classes=[IsAuthenticated])
    def acknowledge(self, request, pk=None):
        """Отметить ознакомление текущего пользователя с документом.

        Args:
            request: DRF Request
            pk: ID документа

        Returns:
            Response: {"ok": true, "already": bool}
        """
        doc = self.get_object()
        obj, created = DocumentAcknowledgement.objects.get_or_create(
            document=doc, user=request.user
        )
        return Response({"ok": True, "already": not created})
