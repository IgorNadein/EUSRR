from __future__ import annotations

from typing import Any

from django.contrib.auth import get_user_model
from django.db import transaction
from django.db.models import Count, Exists, OuterRef, QuerySet, Q
from django.http import FileResponse, Http404
from documents.models import (
    Document,
    DocumentAcknowledgement,
    DocumentTag,
    DocumentType,
    Cabinet,
    DocumentComment,
)
from easy_thumbnails.files import get_thumbnailer
from filer.models import Folder
import reversion
from reversion.models import Version
from rest_framework import status, serializers as rest_serializers
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS, BasePermission, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet

from ..employees.serializers import EmployeeBriefSerializer
from ..permissions import AdminOrActionOrModelPerms
from .permissions import DocumentReadOrModelPerms
from .serializers import (
    DocumentReadSerializer,
    DocumentWriteSerializer,
    FolderSerializer,
    VersionSerializer,
    ActivityItemSerializer,
    DocumentTagSerializer,
    DocumentTypeSerializer,
    CabinetSerializer,
    DocumentCommentSerializer,
)

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
        
        Поддерживает параметр ?folder_id для фильтрации по папке.

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
            
            # Фильтрация по папке
            folder_id = request.query_params.get("folder_id")
            if folder_id is not None:
                try:
                    qs = qs.filter(folder_id=int(folder_id))
                except (ValueError, TypeError):
                    pass  # Игнорируем некорректное значение

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
        detail=True, methods=["get"], permission_classes=[IsAuthenticated]
    )
    def acknowledgements(self, request, pk=None):
        """Ведомость ознакомлений: доступна всем авторизованным пользователям.
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

    # -------------------------------------------------------------------------
    # FSM WORKFLOW ACTIONS
    # -------------------------------------------------------------------------

    @action(detail=True, methods=['post'], url_path='submit-for-review')
    def submit_for_review(self, request, pk=None):
        """Отправить документ на рассмотрение (draft → in_review)."""
        document = self.get_object()
        try:
            document.submit_for_review()
            document.save()
            serializer = self.get_serializer(document)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def approve(self, request, pk=None):
        """Одобрить документ (in_review → approved)."""
        document = self.get_object()
        try:
            document.approve()
            document.save()
            serializer = self.get_serializer(document)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def reject(self, request, pk=None):
        """Отклонить документ (in_review → rejected)."""
        document = self.get_object()
        try:
            document.reject()
            document.save()
            serializer = self.get_serializer(document)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def publish(self, request, pk=None):
        """Опубликовать документ (approved → published)."""
        document = self.get_object()
        try:
            document.publish()
            document.save()
            serializer = self.get_serializer(document)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'], url_path='return-to-draft')
    def return_to_draft(self, request, pk=None):
        """Вернуть документ в черновики."""
        document = self.get_object()
        try:
            document.return_to_draft()
            document.save()
            serializer = self.get_serializer(document)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def archive(self, request, pk=None):
        """Архивировать документ (published → archived)."""
        document = self.get_object()
        try:
            document.archive()
            document.save()
            serializer = self.get_serializer(document)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['post'])
    def unarchive(self, request, pk=None):
        """Разархивировать документ (archived → published)."""
        document = self.get_object()
        try:
            document.unarchive()
            document.save()
            serializer = self.get_serializer(document)
            return Response(serializer.data)
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    # -------------------------------------------------------------------------
    # DJANGO-REVERSION ENDPOINTS
    # -------------------------------------------------------------------------

    @action(detail=True, methods=['get'])
    def versions(self, request, pk=None):
        """Получить историю версий документа.
        
        Returns:
            [
                {
                    "id": 1,
                    "revision_id": 123,
                    "date_created": "2026-02-28T10:00:00Z",
                    "user": {"id": 1, "full_name": "Иванов Иван"},
                    "comment": "Изменено описание",
                    "data": {"title": "...", "description": "..."}
                },
                ...
            ]
        """
        document = self.get_object()
        
        # Получаем все версии документа
        versions = Version.objects.get_for_object(document).select_related('revision', 'revision__user')
        
        serializer = VersionSerializer(versions, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['get'])
    def activity(self, request, pk=None):
        """Получить timeline активности документа (версии + аудит).
        
        Объединяет данные из:
        - reversion.Version (изменения документа)
        - DocumentAuditLog (аудит действий)
        - DocumentAcknowledgement (ознакомления)
        
        Returns:
            [
                {
                    "type": "version",
                    "timestamp": "2026-02-28T10:00:00Z",
                    "user": {"id": 1, "full_name": "Иванов Иван"},
                    "action": "Изменение документа",
                    "details": {"comment": "...", "fields": ["title", "description"]}
                },
                {
                    "type": "audit",
                    "timestamp": "2026-02-28T09:00:00Z",
                    "user": {...},
                    "action": "Просмотрен",
                    "details": {"ip_address": "192.168.1.1"}
                },
                ...
            ]
        """
        document = self.get_object()
        activity_items = []
        
        # 1. Добавляем версии
        versions = Version.objects.get_for_object(document).select_related('revision', 'revision__user')
        for version in versions:
            user_data = None
            if version.revision.user:
                user = version.revision.user
                user_data = {
                    'id': user.id,
                    'full_name': f'{user.last_name} {user.first_name}'.strip(),
                    'avatar_url': getattr(user, 'avatar_url', None),
                }
            
            activity_items.append({
                'type': 'version',
                'timestamp': version.revision.date_created,
                'user': user_data,
                'action': 'Изменение документа',
                'details': {
                    'comment': version.revision.comment or '',
                    'version_id': version.id,
                    'revision_id': version.revision.id,
                }
            })
        
        # 2. Добавляем аудит (если есть)
        if hasattr(document, 'audit_log'):
            audit_logs = document.audit_log.all().select_related('user')[:50]  # Ограничиваем 50 записями
            for log in audit_logs:
                user_data = None
                if log.user:
                    user_data = {
                        'id': log.user.id,
                        'full_name': f'{log.user.last_name} {log.user.first_name}'.strip(),
                        'avatar_url': getattr(log.user, 'avatar_url', None),
                    }
                
                activity_items.append({
                    'type': 'audit',
                    'timestamp': log.timestamp,
                    'user': user_data,
                    'action': log.get_action_display(),
                    'details': {
                        'ip_address': log.ip_address,
                        'metadata': log.metadata,
                    }
                })
        
        # 3. Добавляем ознакомления
        acknowledgements = DocumentAcknowledgement.objects.filter(document=document).select_related('user')[:50]
        for ack in acknowledgements:
            user_data = {
                'id': ack.user.id,
                'full_name': f'{ack.user.last_name} {ack.user.first_name}'.strip(),
                'avatar_url': getattr(ack.user, 'avatar_url', None),
            }
            
            activity_items.append({
                'type': 'acknowledgement',
                'timestamp': ack.acknowledged_at,
                'user': user_data,
                'action': 'Ознакомление',
                'details': None
            })
        
        # Сортируем по времени (новые сверху)
        activity_items.sort(key=lambda x: x['timestamp'], reverse=True)
        
        serializer = ActivityItemSerializer(activity_items, many=True)
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def revert(self, request, pk=None):
        """Откатить документ к указанной версии.
        
        Body:
            {
                "version_id": 123,  // ID версии из reversion.Version
                "comment": "Причина отката"  // опционально
            }
        
        Returns:
            Обновленный документ
            
        Note:
            Поле status не откатывается, так как оно управляется через FSM transitions.
            ManyToMany поля (departments, recipients, related_documents) откатываются отдельно.
        """
        document = self.get_object()
        version_id = request.data.get('version_id')
        comment = request.data.get('comment', '')
        
        if not version_id:
            return Response(
                {'error': 'version_id обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Получаем версию
            version = Version.objects.get(id=version_id, object_id=str(document.pk))
            version_data = version.field_dict
            
            # Исключаем защищенные FSM поля и служебные поля
            excluded_fields = ['status', 'id', 'uploaded_at', 'modified_at', 'uploaded_by']
            
            # ManyToMany поля нужно обрабатывать отдельно через .set()
            m2m_fields = ['departments', 'recipients', 'related_documents']
            
            # Откатываем с комментарием
            with reversion.create_revision():
                # Собираем обычные поля для восстановления
                updated_fields = []
                for field, value in version_data.items():
                    if (field not in excluded_fields and 
                        field not in m2m_fields and 
                        hasattr(document, field)):
                        setattr(document, field, value)
                        updated_fields.append(field)
                
                # Сохраняем с автором отката (чтобы ID был доступен для M2M)
                document.modified_by = request.user
                updated_fields.append('modified_by')
                
                # ВАЖНО: Указываем update_fields, чтобы избежать проверки FSM protected=True
                document.save(update_fields=updated_fields)
                
                # Восстанавливаем ManyToMany поля
                for m2m_field in m2m_fields:
                    if m2m_field in version_data:
                        m2m_manager = getattr(document, m2m_field)
                        m2m_value = version_data[m2m_field]
                        # version_data хранит список ID
                        if isinstance(m2m_value, list):
                            m2m_manager.set(m2m_value)
                
                reversion.set_user(request.user)
                reversion.set_comment(comment or f'Откат к версии {version_id}')
            
            # Обновляем объект из базы
            document.refresh_from_db()
            serializer = self.get_serializer(document)
            return Response(serializer.data)
            
        except Version.DoesNotExist:
            return Response(
                {'error': 'Версия не найдена'},
                status=status.HTTP_404_NOT_FOUND
            )
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )

    @action(detail=True, methods=['get'])
    def thumbnail(self, request, pk=None):
        """Получить thumbnail документа.
        
        Query параметры:
            size: admin_thumbnail | small | medium | large (default: medium)
        
        Returns:
            Изображение thumbnail или 404 если документ не является изображением/PDF
        """
        document = self.get_object()
        
        if not document.file:
            return Response(
                {'error': 'У документа нет файла'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        size = request.query_params.get('size', 'medium')
        allowed_sizes = ['admin_thumbnail', 'small', 'medium', 'large']
        
        if size not in allowed_sizes:
            return Response(
                {'error': f'Размер должен быть одним из: {", ".join(allowed_sizes)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            # Получаем thumbnailer для файла
            thumbnailer = get_thumbnailer(document.file.file)
            
            # Генерируем thumbnail используя alias из settings
            thumbnail = thumbnailer[size]
            
            # Возвращаем файл
            return FileResponse(
                open(thumbnail.path, 'rb'),
                content_type='image/jpeg'
            )
        except Exception as e:
            return Response(
                {'error': f'Не удалось создать thumbnail: {str(e)}'},
                status=status.HTTP_400_BAD_REQUEST
            )

    # -------------------------------------------------------------------------
    # RELATED DOCUMENTS ENDPOINTS
    # -------------------------------------------------------------------------

    @action(detail=True, methods=['get'])
    def related(self, request, pk=None):
        """Получить связанные документы.
        
        Returns:
            Список связанных документов
        """
        document = self.get_object()
        related = document.related_documents.all()
        serializer = DocumentReadSerializer(
            related,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)

    @action(detail=True, methods=['post'])
    def add_related(self, request, pk=None):
        """Добавить связанный документ.
        
        Body:
            {"document_id": 123}
        
        Returns:
            {"status": "added"}
        """
        document = self.get_object()
        related_id = request.data.get('document_id')
        
        if not related_id:
            return Response(
                {'error': 'document_id обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if related_id == document.pk:
            return Response(
                {'error': 'Нельзя связать документ с самим собой'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            related_doc = Document.objects.get(pk=related_id)
            document.related_documents.add(related_doc)
            return Response({'status': 'added'})
        except Document.DoesNotExist:
            return Response(
                {'error': 'Документ не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

    @action(detail=True, methods=['post'])
    def remove_related(self, request, pk=None):
        """Удалить связанный документ.
        
        Body:
            {"document_id": 123}
        
        Returns:
            {"status": "removed"}
        """
        document = self.get_object()
        related_id = request.data.get('document_id')
        
        if not related_id:
            return Response(
                {'error': 'document_id обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            related_doc = Document.objects.get(pk=related_id)
            document.related_documents.remove(related_doc)
            return Response({'status': 'removed'})
        except Document.DoesNotExist:
            return Response(
                {'error': 'Документ не найден'},
                status=status.HTTP_404_NOT_FOUND
            )


class DocumentCommentViewSet(ModelViewSet):
    """CRUD для комментариев к документам.
    
    Поддерживает вложенные ответы (threading) через поле parent.
    """
    serializer_class = DocumentCommentSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Возвращает комментарии, опционально фильтрованные по документу.
        
        Параметры:
            ?document_id=<id> - показать только комментарии к этому документу
            ?root=true - показать только корневые комментарии (без parent)
        """
        qs = DocumentComment.objects.all().select_related('author', 'document', 'parent')
        
        document_id = self.request.query_params.get('document_id')
        root = self.request.query_params.get('root', '').lower() == 'true'
        
        if document_id:
            qs = qs.filter(document_id=document_id)
        
        if root:
            qs = qs.filter(parent__isnull=True)
        
        return qs.order_by('created_at')
    
    @transaction.atomic
    def perform_create(self, serializer):
        """Автоматически устанавливаем author при создании."""
        # Получаем document_id и parent_id из request.data
        document_id = self.request.data.get('document_id')
        parent_id = self.request.data.get('parent_id')
        
        if not document_id:
            raise rest_serializers.ValidationError({'document_id': 'Это поле обязательно.'})
        
        try:
            document = Document.objects.get(pk=document_id)
        except Document.DoesNotExist:
            raise rest_serializers.ValidationError({'document_id': 'Документ не найден.'})
        
        parent = None
        if parent_id:
            try:
                parent = DocumentComment.objects.get(pk=parent_id, document=document)
            except DocumentComment.DoesNotExist:
                raise rest_serializers.ValidationError({'parent_id': 'Родительский комментарий не найден.'})
        
        serializer.save(
            author=self.request.user,
            document=document,
            parent=parent
        )
    
    @transaction.atomic
    def perform_update(self, serializer):
        """При обновлении помечаем комментарий как отредактированный."""
        serializer.save(is_edited=True)
    
    def destroy(self, request, *args, **kwargs):
        """Разрешаем удалять только свои комментарии (или staff)."""
        comment = self.get_object()
        
        if comment.author != request.user and not request.user.is_staff:
            return Response(
                {'error': 'Вы можете удалять только свои комментарии'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().destroy(request, *args, **kwargs)
    
    @action(detail=True, methods=['get'])
    def replies(self, request, pk=None):
        """Получить все ответы на комментарий."""
        comment = self.get_object()
        replies = comment.replies.all().select_related('author')
        serializer = self.get_serializer(replies, many=True)
        return Response(serializer.data)

class FolderViewSet(ModelViewSet):
    """CRUD для папок документов (filer.Folder).
    
    Поддерживает иерархическую структуру папок с parent/children связями.
    """
    
    queryset = Folder.objects.all()
    serializer_class = FolderSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Возвращает папки, опционально фильтрованные по parent_id.
        
        Параметры:
            ?parent_id=<id> - показать только дочерние папки указанного parent
            ?root=true - показать только корневые папки (parent=null)
        """
        from django.db.models import Count
        
        qs = super().get_queryset()
        request = getattr(self, "request", None)
        
        # Аннотируем количество документов в каждой папке
        qs = qs.annotate(document_count=Count('documents'))
        
        if not request:
            return qs
            
        parent_id = request.query_params.get('parent_id')
        root = request.query_params.get('root', '').lower() == 'true'
        
        if root:
            qs = qs.filter(parent__isnull=True)
        elif parent_id:
            qs = qs.filter(parent_id=parent_id)
            
        return qs.order_by('name')
    
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """Создать папку.
        
        Body:
            {
                "name": "Название папки",
                "parent": <id> | null  // опционально
            }
        """
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        # Создаем папку
        name = serializer.validated_data['name']
        parent_id = request.data.get('parent')
        
        parent = None
        if parent_id:
            try:
                parent = Folder.objects.get(pk=parent_id)
            except Folder.DoesNotExist:
                return Response(
                    {'error': 'Родительская папка не найдена'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        folder = Folder.objects.create(
            name=name,
            parent=parent,
            owner=request.user
        )
        
        result = FolderSerializer(folder).data
        return Response(result, status=status.HTTP_201_CREATED)
    
    @action(detail=True, methods=['get'])
    def children(self, request, pk=None):
        """Получить дочерние папки данной папки."""
        folder = self.get_object()
        children = folder.children.all().order_by('name')
        serializer = self.get_serializer(children, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def documents(self, request, pk=None):
        """Получить документы в данной папке."""
        folder = self.get_object()
        documents = Document.objects.filter(folder=folder)
        serializer = DocumentReadSerializer(
            documents,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)


class DocumentTagViewSet(ModelViewSet):
    """CRUD для тегов документов.
    
    Теги используются для категоризации документов.
    """
    queryset = DocumentTag.objects.all()
    serializer_class = DocumentTagSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Возвращает теги, опционально с аннотацией количества документов."""
        qs = super().get_queryset()
        
        # Аннотируем количество документов для каждого тега
        qs = qs.annotate(document_count=Count('documents'))
        
        # Поиск по названию
        search = self.request.query_params.get('search', '')
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        return qs.order_by('name')
    
    @action(detail=True, methods=['get'])
    def documents(self, request, pk=None):
        """Получить все документы с этим тегом."""
        tag = self.get_object()
        documents = tag.documents.all()
        serializer = DocumentReadSerializer(
            documents,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)


class DocumentTypeViewSet(ModelViewSet):
    """CRUD для типов документов.
    
    Типы определяют структуру метаданных и workflow для документов.
    """
    queryset = DocumentType.objects.filter(is_active=True)
    serializer_class = DocumentTypeSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Возвращает типы документов.
        
        Параметры:
            ?include_inactive=true - показать неактивные типы
        """
        qs = super().get_queryset()
        
        # Опционально показываем неактивные
        include_inactive = self.request.query_params.get('include_inactive', '').lower() == 'true'
        if include_inactive:
            qs = DocumentType.objects.all()
        
        # Поиск
        search = self.request.query_params.get('search', '')
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(code__icontains=search) |
                Q(description__icontains=search)
            )
        
        return qs.order_by('order', 'name')
    
    @action(detail=True, methods=['get'])
    def documents(self, request, pk=None):
        """Получить все документы этого типа."""
        doc_type = self.get_object()
        documents = Document.objects.filter(document_type=doc_type)
        serializer = DocumentReadSerializer(
            documents,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)


class CabinetViewSet(ModelViewSet):
    """CRUD для кабинетов (виртуальных коллекций документов).
    
    Кабинеты позволяют организовать документы в виртуальные коллекции
    независимо от физической структуры папок.
    """
    queryset = Cabinet.objects.all()
    serializer_class = CabinetSerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Возвращает кабинеты с поддержкой иерархии.
        
        Параметры:
            ?parent_id=<id> - показать только дочерние кабинеты
            ?root=true - показать только корневые кабинеты
        """
        qs = super().get_queryset()
        
        # Аннотируем количество документов
        qs = qs.annotate(document_count=Count('documents'))
        
        parent_id = self.request.query_params.get('parent_id')
        root = self.request.query_params.get('root', '').lower() == 'true'
        
        if root:
            qs = qs.filter(parent__isnull=True)
        elif parent_id:
            qs = qs.filter(parent_id=parent_id)
        
        # Поиск
        search = self.request.query_params.get('search', '')
        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(description__icontains=search)
            )
        
        return qs.order_by('order', 'name')
    
    @transaction.atomic
    def perform_create(self, serializer):
        """Автоматически устанавливаем created_by при создании."""
        serializer.save(created_by=self.request.user)
    
    @action(detail=True, methods=['get'])
    def children(self, request, pk=None):
        """Получить дочерние кабинеты."""
        cabinet = self.get_object()
        children = cabinet.children.all().order_by('order', 'name')
        serializer = self.get_serializer(children, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['get'])
    def documents(self, request, pk=None):
        """Получить документы в этом кабинете."""
        cabinet = self.get_object()
        documents = cabinet.documents.all()
        serializer = DocumentReadSerializer(
            documents,
            many=True,
            context={'request': request}
        )
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'])
    def add_document(self, request, pk=None):
        """Добавить документ в кабинет.
        
        Body:
            {"document_id": 123}
        """
        cabinet = self.get_object()
        document_id = request.data.get('document_id')
        
        if not document_id:
            return Response(
                {'error': 'document_id обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            document = Document.objects.get(pk=document_id)
            cabinet.documents.add(document)
            return Response({'status': 'added'})
        except Document.DoesNotExist:
            return Response(
                {'error': 'Документ не найден'},
                status=status.HTTP_404_NOT_FOUND
            )
    
    @action(detail=True, methods=['post'])
    def remove_document(self, request, pk=None):
        """Удалить документ из кабинета.
        
        Body:
            {"document_id": 123}
        """
        cabinet = self.get_object()
        document_id = request.data.get('document_id')
        
        if not document_id:
            return Response(
                {'error': 'document_id обязателен'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            document = Document.objects.get(pk=document_id)
            cabinet.documents.remove(document)
            return Response({'status': 'removed'})
        except Document.DoesNotExist:
            return Response(
                {'error': 'Документ не найден'},
                status=status.HTTP_404_NOT_FOUND
            )

