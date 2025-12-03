from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, QuerySet, Q
from documents.models import Document, DocumentAcknowledgement
from rest_framework import status
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from ..employees.serializers import EmployeeBriefSerializer
from ..permissions import AdminOrActionOrModelPerms
from .permissions import DocumentReadOrModelPerms
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
    permission_classes = [DocumentReadOrModelPerms]
    parser_classes = (MultiPartParser, FormParser, JSONParser)

    def get_serializer_class(self):
        """Возвращает сериализатор в зависимости от действия.

        Returns:
            type: Класс сериализатора для чтения/записи.
        """
        if self.action in ("create", "update", "partial_update"):
            return DocumentWriteSerializer
        return DocumentReadSerializer

    def get_queryset(self) -> QuerySet[Document]:
        """Базовый queryset + аннотация флага ознакомления текущего пользователя.

        Поддерживает параметр ?scope=mine для фильтрации документов,
        доступных текущему пользователю.

        Returns:
            QuerySet[Document]: оптимизированный для списка без N+1.
        """
        qs = super().get_queryset()
        request = getattr(self, "request", None)
        user = getattr(request, "user", None)

        # Параметр scope из запроса
        scope = ""
        if request:
            scope = request.query_params.get("scope", "").lower()

        # Если scope=mine - показываем только доступные пользователю
        if scope == "mine" and user and user.is_authenticated:
            # Документы для всех ИЛИ где пользователь получатель
            # ИЛИ в отделе ИЛИ автор
            qs = qs.filter(
                Q(sent_to_all=True) |
                Q(recipients=user) |
                Q(departments__employeedepartment__employee=user,
                  departments__employeedepartment__is_active=True) |
                Q(uploaded_by=user)
            ).distinct()
        # Если нет прав view_document - тоже ограничиваем
        elif (user and user.is_authenticated and
              not user.has_perm("documents.view_document") and
              not user.is_staff):
            qs = qs.filter(
                Q(sent_to_all=True) |
                Q(recipients=user) |
                Q(departments__employeedepartment__employee=user,
                  departments__employeedepartment__is_active=True) |
                Q(uploaded_by=user)
            ).distinct()

        # Для аутентифицированных аннотируем флаг "я ознакомился"
        if user and user.is_authenticated:
            subq = DocumentAcknowledgement.objects.filter(
                document=OuterRef("pk"), user=user
            )
            qs = qs.annotate(_is_acknowledged=Exists(subq))

        return qs.order_by("-uploaded_at")

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Создаёт документ и возвращает read-схему + recipient_count.

        recipient_count:
        - 0, если sent_to_all=True;
        - число активных пользователей из переданных recipient_ids (неактивные/несуществующие игнорируются).
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        # Сохраним нормализованные ID до save(), т.к. serializer.save() их вытаскивает.
        input_recipient_ids = list(serializer.validated_data.get("recipient_ids", []))

        doc = serializer.save()

        read = DocumentReadSerializer(doc, context={"request": request})
        data = dict(read.data)

        if doc.sent_to_all:
            data["recipient_count"] = 0
        else:
            active_count = User.objects.filter(
                is_active=True, id__in=input_recipient_ids
            ).aggregate(n=Count("id", distinct=True))["n"]
            data["recipient_count"] = active_count

        return Response(data, status=status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        """Полная замена документа.

        Returns:
            Response: Тело ответа в формате read-сериализатора (с file_url).
        """
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)
        doc = serializer.save()

        read = DocumentReadSerializer(doc, context={"request": request})
        return Response(read.data, status=status.HTTP_200_OK)

    def partial_update(self, request, *args, **kwargs):
        """Частичное обновление (PATCH) — аналогично update, но partial=True."""
        kwargs["partial"] = True
        return self.update(request, *args, **kwargs)

    @action(methods=["post"], detail=True)
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

    @action(
        detail=True, methods=["get"], permission_classes=[AdminOrActionOrModelPerms]
    )
    def acknowledgements(self, request, pk=None):
        """Ведомость ознакомлений: доступна только staff/модельные права.
        Поддерживает ?search= для фильтра и отдаёт непагинированно (или подключите пагинацию).
        """
        doc = self.get_object()
        q = (request.query_params.get("search") or "").strip()
        base = User.objects.filter(is_active=True)
        
        if not doc.sent_to_all:
            # Собираем ID получателей из recipients и departments
            recipient_ids = set(doc.recipients.values_list("pk", flat=True))
            
            # Добавляем активных сотрудников из отделов
            for department in doc.departments.all():
                recipient_ids.update(emp.id for emp in department.active_employees)
            
            base = base.filter(pk__in=recipient_ids)
        
        if q:
            base = base.filter(
                Q(email__icontains=q)
                | Q(first_name__icontains=q)
                | Q(last_name__icontains=q)
                | Q(patronymic__icontains=q)
            )
        acked_qs = base.filter(document_acknowledgements__document=doc)
        unacked_qs = base.exclude(pk__in=acked_qs.values("pk"))

        acked = EmployeeBriefSerializer(
            acked_qs, many=True, context={"request": request}
        ).data
        unacked = EmployeeBriefSerializer(
            unacked_qs, many=True, context={"request": request}
        ).data
        # при желании подключите PageNumberPagination и верните {"acknowledged": page1, "unacknowledged": page2}
        return Response(
            {
                "acknowledged": acked,
                "unacknowledged": unacked,
                "counts": {
                    "acknowledged": acked_qs.count(),
                    "unacknowledged": unacked_qs.count(),
                    "total": base.count(),
                },
            }
        )
