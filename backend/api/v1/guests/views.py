from __future__ import annotations

from django.contrib.contenttypes.models import ContentType
from django.db.models import Count, IntegerField, OuterRef, Q, Subquery, Value
from django.db.models.functions import Coalesce
from django.shortcuts import get_object_or_404
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied, ValidationError
from rest_framework.response import Response

from communications import comments_helpers
from communications.models import Message
from documents.models import Document
from guests.constants import GuestVisitEventType, GuestVisitStatus
from guests.models import Guest, GuestVisit
from guests.permissions import (
    can_decide_guest_visit,
    can_manage_guest_account,
    is_guest_admin,
)
from guests.services import (
    GuestLdapService,
    GuestVisitWorkflow,
    record_guest_event,
)

from .permissions import GuestAdminPermission, GuestVisitPermission
from .serializers import (
    GuestSerializer,
    GuestSearchSerializer,
    GuestVisitReadSerializer,
    GuestVisitWriteSerializer,
)
from ..employees.serializers import EmployeeBriefSerializer


class GuestVisitViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = (
        GuestVisit.objects.select_related(
            "guest",
            "inviter",
            "decided_by",
            "host_department",
        )
        .prefetch_related("documents", "events__actor")
        .order_by("-created_at")
    )
    permission_classes = [GuestVisitPermission]

    def get_serializer_class(self):
        if self.action in {"list", "retrieve"}:
            return GuestVisitReadSerializer
        return GuestVisitWriteSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        params = self.request.query_params

        request_ct = ContentType.objects.get_for_model(GuestVisit)
        comments_subquery = (
            Message.objects.filter(
                chat__type="comments",
                chat__context_content_type=request_ct,
                chat__context_object_id=OuterRef("pk"),
                is_deleted=False,
            )
            .values("chat")
            .annotate(count=Count("id"))
            .values("count")
        )
        qs = qs.annotate(
            comments_count=Coalesce(
                Subquery(comments_subquery, output_field=IntegerField()),
                Value(0),
            )
        )

        scope = params.get("scope")
        if not is_guest_admin(user):
            qs = qs.filter(inviter=user)
        elif scope == "mine":
            qs = qs.filter(inviter=user)
        elif scope == "pending_decision":
            qs = qs.filter(status=GuestVisitStatus.PENDING)
        elif scope == "active":
            qs = qs.filter(status=GuestVisitStatus.APPROVED)
        elif scope == "expired":
            qs = qs.filter(status=GuestVisitStatus.EXPIRED)
        elif scope == "risk":
            qs = qs.filter(inviter_inactive=True)

        if status_value := params.get("status"):
            qs = qs.filter(status=status_value)
        if guest_id := params.get("guest_id"):
            qs = qs.filter(guest_id=guest_id)
        if inviter_id := params.get("inviter_id"):
            qs = qs.filter(inviter_id=inviter_id)
        if created_from := params.get("created_from"):
            qs = qs.filter(created_at__date__gte=created_from)
        if created_to := params.get("created_to"):
            qs = qs.filter(created_at__date__lte=created_to)
        if access_from := params.get("access_from"):
            qs = qs.filter(
                Q(access_expires_at__isnull=True)
                | Q(access_expires_at__gte=access_from)
            )
        if access_to := params.get("access_to"):
            qs = qs.filter(
                Q(access_starts_at__isnull=True)
                | Q(access_starts_at__lte=access_to)
            )
        if params.get("unlimited") in {"true", "false"}:
            qs = qs.filter(unlimited=params.get("unlimited") == "true")
        if params.get("ldap_enabled") in {"true", "false"}:
            qs = qs.filter(guest__ldap_enabled=params.get("ldap_enabled") == "true")
        if q := (params.get("q") or "").strip():
            qs = qs.filter(
                Q(guest__last_name__icontains=q)
                | Q(guest__first_name__icontains=q)
                | Q(guest__organization__icontains=q)
                | Q(guest__email__icontains=q)
                | Q(guest__phone__icontains=q)
                | Q(purpose__icontains=q)
            )
        ordering = params.get("ordering")
        allowed_ordering = {
            "created_at",
            "-created_at",
            "access_starts_at",
            "-access_starts_at",
            "access_expires_at",
            "-access_expires_at",
        }
        if ordering in allowed_ordering:
            qs = qs.order_by(ordering)
        return qs.distinct()

    def _read_response(self, visit, response_status=status.HTTP_200_OK):
        visit.refresh_from_db()
        serializer = GuestVisitReadSerializer(
            visit,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data, status=response_status)

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        visit = serializer.save()
        return self._read_response(visit, status.HTTP_201_CREATED)

    def update(self, request, *args, **kwargs):
        partial = kwargs.pop("partial", False)
        instance = self.get_object()
        if not instance.can_edit_by(request.user):
            raise PermissionDenied("Недостаточно прав для изменения визита.")
        serializer = self.get_serializer(
            instance,
            data=request.data,
            partial=partial,
        )
        serializer.is_valid(raise_exception=True)
        visit = serializer.save()
        return self._read_response(visit)

    @action(detail=True, methods=["post"])
    def submit(self, request, pk=None):
        visit = self.get_object()
        try:
            GuestVisitWorkflow.submit(visit, actor=request.user)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return self._read_response(visit)

    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        if not can_decide_guest_visit(request.user):
            raise PermissionDenied("Недостаточно прав для решения.")
        visit = self.get_object()
        try:
            GuestVisitWorkflow.approve(
                visit,
                actor=request.user,
                comment=request.data.get("comment", ""),
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return self._read_response(visit)

    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        if not can_decide_guest_visit(request.user):
            raise PermissionDenied("Недостаточно прав для решения.")
        visit = self.get_object()
        try:
            GuestVisitWorkflow.reject(
                visit,
                actor=request.user,
                comment=request.data.get("comment", ""),
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return self._read_response(visit)

    @action(detail=True, methods=["post"], url_path="request-info")
    def request_info(self, request, pk=None):
        if not can_decide_guest_visit(request.user):
            raise PermissionDenied("Недостаточно прав для решения.")
        visit = self.get_object()
        try:
            GuestVisitWorkflow.request_info(
                visit,
                actor=request.user,
                comment=request.data.get("comment", ""),
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return self._read_response(visit)

    @action(detail=True, methods=["post"], url_path="provide-info")
    def provide_info(self, request, pk=None):
        visit = self.get_object()
        comment = (request.data.get("comment") or "").strip()
        if not comment:
            raise ValidationError("Комментарий обязателен.")
        comments_helpers.create_comment(visit, request.user, comment)
        try:
            GuestVisitWorkflow.submit(visit, actor=request.user)
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return self._read_response(visit)

    @action(detail=True, methods=["post"])
    def cancel(self, request, pk=None):
        visit = self.get_object()
        if visit.inviter_id != request.user.id and not is_guest_admin(request.user):
            raise PermissionDenied("Недостаточно прав для отмены.")
        try:
            GuestVisitWorkflow.cancel(
                visit,
                actor=request.user,
                comment=request.data.get("comment", ""),
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return self._read_response(visit)

    @action(detail=True, methods=["post"])
    def revoke(self, request, pk=None):
        if not can_decide_guest_visit(request.user):
            raise PermissionDenied("Недостаточно прав для отзыва.")
        visit = self.get_object()
        try:
            GuestVisitWorkflow.revoke(
                visit,
                actor=request.user,
                comment=request.data.get("comment", ""),
            )
        except ValueError as exc:
            raise ValidationError(str(exc)) from exc
        return self._read_response(visit)

    @action(detail=True, methods=["post"], url_path="sync-ldap")
    def sync_ldap(self, request, pk=None):
        if not can_manage_guest_account(request.user):
            raise PermissionDenied("Недостаточно прав для LDAP.")
        visit = self.get_object()
        GuestLdapService().sync_guest_for_visit(visit)
        return self._read_response(visit)

    @action(detail=True, methods=["get", "post"])
    def comments(self, request, pk=None):
        visit = self.get_object()
        if request.method == "GET":
            messages = comments_helpers.get_comments(visit)
            return Response(
                [
                    {
                        "id": msg.id,
                        "author": EmployeeBriefSerializer(msg.author).data,
                        "text": msg.content,
                        "created_at": msg.created_at,
                    }
                    for msg in messages
                ]
            )
        text = (request.data.get("text") or "").strip()
        if not text:
            raise ValidationError({"text": "Это поле не может быть пустым."})
        msg = comments_helpers.create_comment(visit, request.user, text)
        return Response(
            {
                "id": msg.id,
                "author": EmployeeBriefSerializer(msg.author).data,
                "text": msg.content,
                "created_at": msg.created_at,
            },
            status=status.HTTP_201_CREATED,
        )

    @action(
        detail=True,
        methods=["delete"],
        url_path="comments/(?P<comment_id>[^/.]+)",
    )
    def delete_comment(self, request, pk=None, comment_id=None):
        visit = self.get_object()
        chat = comments_helpers.get_or_create_comments_chat(visit)
        message = get_object_or_404(Message, id=comment_id, chat=chat)
        if message.author_id != request.user.id and not is_guest_admin(request.user):
            raise PermissionDenied("Недостаточно прав для удаления комментария.")
        comments_helpers.delete_comment(message, request.user, soft_delete=True)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=["post"], url_path="documents")
    def attach_document(self, request, pk=None):
        visit = self.get_object()
        document_id = request.data.get("document_id")
        document = get_object_or_404(Document, pk=document_id)
        visit.documents.add(document)
        record_guest_event(
            visit,
            GuestVisitEventType.DOCUMENT_ATTACHED,
            actor=request.user,
            metadata={"document_id": document.id},
        )
        return self._read_response(visit)

    @action(
        detail=True,
        methods=["delete"],
        url_path="documents/(?P<document_id>[^/.]+)",
    )
    def remove_document(self, request, pk=None, document_id=None):
        visit = self.get_object()
        document = get_object_or_404(Document, pk=document_id)
        visit.documents.remove(document)
        record_guest_event(
            visit,
            GuestVisitEventType.DOCUMENT_REMOVED,
            actor=request.user,
            metadata={"document_id": document.id},
        )
        return self._read_response(visit)


class GuestViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Guest.objects.all().order_by("last_name", "first_name", "id")
    serializer_class = GuestSerializer
    permission_classes = [GuestAdminPermission]

    def get_queryset(self):
        qs = super().get_queryset()
        q = (self.request.query_params.get("q") or "").strip()
        if q:
            text_q = (
                Q(last_name__icontains=q)
                | Q(first_name__icontains=q)
                | Q(patronymic__icontains=q)
                | Q(email__icontains=q)
                | Q(phone__icontains=q)
                | Q(organization__icontains=q)
            )
            if q.isdigit():
                text_q |= Q(id=int(q))
            qs = qs.filter(text_q)
        return qs

    @action(detail=False, methods=["get"])
    def search(self, request):
        serializer = GuestSearchSerializer(
            self.get_queryset()[:20],
            many=True,
            context=self.get_serializer_context(),
        )
        return Response(serializer.data)

    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        guest = self.get_object()
        guest.is_active = False
        guest.save(update_fields=["is_active", "updated_at"])
        GuestLdapService().disable_guest(guest)
        return Response(self.get_serializer(guest).data)

    @action(detail=True, methods=["post"], url_path="sync-ldap")
    def sync_ldap(self, request, pk=None):
        guest = self.get_object()
        GuestLdapService().sync_guest(guest)
        return Response(self.get_serializer(guest).data)
