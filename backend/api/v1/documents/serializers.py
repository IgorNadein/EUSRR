from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Sequence, Iterable

from drf_spectacular.utils import extend_schema_field
from django.http import QueryDict
from django.contrib.auth import get_user_model
from django.db.models import Q
from django.utils.text import slugify
from documents.models import Document, DocumentAcknowledgement
from rest_framework import serializers

from ..employees.serializers import EmployeeBriefSerializer
from .fields import FilerFileField as FilerFileSerializerField

logger = logging.getLogger(__name__)
User = get_user_model()


@extend_schema_field(serializers.ListField(child=serializers.IntegerField()))
class RecipientIDsField(serializers.Field):
    """Принимает recipient_ids в форматах: список, JSON-строка или CSV.

    Примеры:
        - [1, 2, 3]
        - "[1,2,3]"
        - "1,2,3"

    Возвращает:
        list[int]: Нормализованный список целых ID.

    Raises:
        serializers.ValidationError: Некорректный формат/значения.
    """

    def to_internal_value(self, data: Any) -> list[int]:
        """Парсит raw-значение из запроса в список int.

        При multipart (QueryDict) поддерживает repeat-params:
        recipient_ids=1&recipient_ids=2...
        """
        # 1) Спец. случай: multipart/QueryDict с repeat-params
        # DRF в обычное Field передаёт "последнее" значение, поэтому
        # забираем полный список через
        # parent.initial_data.getlist(self.field_name)
        parent_data = getattr(
            self.parent, "initial_data", None
        )  # type: ignore[attr-defined]
        if isinstance(parent_data, QueryDict):
            values = parent_data.getlist(
                self.field_name
            )  # type: ignore[attr-defined]
            if len(values) > 1:
                data = values
            elif len(values) == 1 and not isinstance(data, (list, tuple)):
                # один элемент: оставим строкой — ниже распарсится как
                # JSON/CSV/число
                data = values[0]

        # 2) Уже список/кортеж?
        if isinstance(data, (list, tuple)):
            # если это ['1','2','3'] — ок; если это ['[1,2]'] — распакуем как
            # строку
            if (
                len(data) == 1
                and isinstance(data[0], str)
                and (data[0].strip().startswith("[") or "," in data[0])
            ):
                data = data[0]
            else:
                vals = list(data)
        # 3) Строка: JSON-массив или CSV или одно число
        if isinstance(data, str):
            s = data.strip()
            try:
                if s.startswith("[") and s.endswith("]"):
                    parsed = json.loads(s)
                    if not isinstance(parsed, list):
                        raise serializers.ValidationError(
                            "Ожидается JSON-массив ID."
                        )
                    vals = parsed
                elif "," in s:
                    vals = [p.strip() for p in s.split(",") if p.strip()]
                else:
                    vals = [s]
            except serializers.ValidationError:
                raise
            except Exception as e:
                raise serializers.ValidationError(
                    f"Неверный формат recipient_ids: {e!s}"
                )
        elif data in (None, ""):
            vals = []
        elif not isinstance(data, (list, tuple)):
            raise serializers.ValidationError(
                "Ожидается список, JSON-строка или CSV-строка."
            )

        # Приведение к int
        try:
            return [int(x) for x in vals]
        except Exception:
            raise serializers.ValidationError(
                "ID получателей должны быть целыми числами."
            )

    def to_representation(self, value: Iterable[int]) -> list[int]:
        """Отдаёт список ID (на всякий случай; поле write_only)."""
        if value is None:
            return []
        return list(value)


class DepartmentBriefSerializer(serializers.Serializer):
    """Краткий сериализатор отдела."""

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)


class FolderSerializer(serializers.Serializer):
    """Сериализатор для папки filer.Folder."""

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()
    parent_id = serializers.IntegerField(
        source="parent.id", read_only=True, allow_null=True
    )
    path = serializers.SerializerMethodField()
    document_count = serializers.IntegerField(read_only=True, default=0)

    def get_path(self, obj) -> str:
        """Возвращает полный путь папки."""
        path_parts = []
        current = obj
        while current:
            path_parts.insert(0, current.name)
            current = current.parent
        return " / ".join(path_parts)


class FolderBriefSerializer(serializers.Serializer):
    """Краткий сериализатор папки для вложенного отображения."""

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)


class DocumentTagSerializer(serializers.Serializer):
    """Сериализатор для тегов документов."""

    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(max_length=100)
    slug = serializers.SlugField(required=False, allow_blank=True, max_length=100)
    color = serializers.CharField(required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    document_count = serializers.SerializerMethodField()

    def get_document_count(self, obj) -> int:
        """Возвращает количество документов с этим тегом."""
        return obj.documents.count() if hasattr(obj, "documents") else 0

    def validate_slug(self, value):
        """Проверяет уникальность slug."""
        from documents.models import DocumentTag

        if not value:
            return value

        # Проверяем дубликаты (исключая текущий объект при обновлении)
        qs = DocumentTag.objects.filter(slug=value)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "Tag with this slug already exists."
            )
        return value

    def validate_name(self, value):
        """Проверяет уникальность названия тега."""
        from documents.models import DocumentTag

        name = value.strip()
        qs = DocumentTag.objects.filter(name__iexact=name)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError(
                "Тег с таким названием уже существует."
            )
        return name

    def _get_unique_slug(self, name: str) -> str:
        """Генерирует уникальный slug из названия."""
        from documents.models import DocumentTag

        base_slug = slugify(name, allow_unicode=True) or "tag"
        base_slug = base_slug[:90].strip("-") or "tag"
        slug = base_slug
        index = 2

        while DocumentTag.objects.filter(slug=slug).exists():
            suffix = f"-{index}"
            slug = f"{base_slug[:100 - len(suffix)]}{suffix}"
            index += 1

        return slug

    def create(self, validated_data):
        """Создаёт новый тег документа."""
        from documents.models import DocumentTag

        if not validated_data.get("slug"):
            validated_data["slug"] = self._get_unique_slug(
                validated_data["name"]
            )
        return DocumentTag.objects.create(**validated_data)

    def update(self, instance, validated_data):
        """Обновляет тег документа."""
        for attr, value in validated_data.items():
            setattr(instance, attr, value)
        instance.save()
        return instance


class VersionSerializer(serializers.Serializer):
    """Сериализатор для версий документа (django-reversion)."""

    id = serializers.IntegerField(read_only=True)
    revision_id = serializers.IntegerField(source="revision.id", read_only=True)
    date_created = serializers.DateTimeField(
        source="revision.date_created", read_only=True
    )
    user = serializers.SerializerMethodField()
    comment = serializers.CharField(
        source="revision.comment", read_only=True, allow_blank=True
    )

    # Данные версии
    data = serializers.SerializerMethodField()

    def get_user(self, obj) -> dict | None:
        """Возвращает информацию о пользователе, создавшем версию."""
        if not obj.revision.user:
            return None
        user = obj.revision.user
        return {
            "id": user.id,
            "full_name": f"{user.last_name} {user.first_name}".strip(),
            "avatar_url": getattr(user, "avatar_url", None),
        }

    def get_data(self, obj) -> dict:
        """Возвращает данные версии документа."""
        return obj.field_dict


class ActivityItemSerializer(serializers.Serializer):
    """Сериализатор для элемента timeline активности."""

    type = serializers.CharField()  # 'version', 'audit', 'acknowledgement'
    timestamp = serializers.DateTimeField()
    user = serializers.DictField(allow_null=True)
    action = serializers.CharField()
    details = serializers.DictField(allow_null=True)


class DocumentReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения документа.

    Включает список получателей и флаг, ознакомился ли текущий пользователь.
    """

    created_by = EmployeeBriefSerializer(read_only=True)
    uploaded_by = EmployeeBriefSerializer(read_only=True)
    modified_by = EmployeeBriefSerializer(read_only=True)
    recipients = EmployeeBriefSerializer(many=True, read_only=True)
    departments = DepartmentBriefSerializer(many=True, read_only=True)
    acknowledgement_recipients = EmployeeBriefSerializer(
        many=True, read_only=True
    )
    acknowledgement_departments = DepartmentBriefSerializer(
        many=True, read_only=True
    )
    folder = FolderBriefSerializer(read_only=True)
    folder_path = serializers.CharField(read_only=True)
    tags = DocumentTagSerializer(many=True, read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    file_url = FilerFileSerializerField(source="file", read_only=True)
    file_name = serializers.CharField(
        source="file.name", read_only=True, allow_null=True
    )
    file_size = serializers.IntegerField(
        source="file.size", read_only=True, allow_null=True
    )
    is_acknowledged = serializers.SerializerMethodField()
    acknowledgement_required_for_user = serializers.SerializerMethodField()
    acknowledged_count = serializers.SerializerMethodField()
    acknowledgement_total = serializers.SerializerMethodField()
    comments_count = serializers.SerializerMethodField()
    linked_tasks = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = (
            "id",
            "title",
            "description",
            "extracted_text",  # Для полнотекстового поиска
            "folder",  # Папка документа
            "folder_path",  # Полный путь папки
            "tags",  # Теги
            "created_by",  # Создатель документа
            "created_at",  # Дата создания
            "uploaded_by",
            "uploaded_at",
            "modified_by",
            "modified_at",
            "sent_to_all",
            "is_regulation",
            "acknowledgement_required",  # Требуется ли ознакомление
            "acknowledgement_for_all",
            "acknowledgement_required_for_user",
            "acknowledged_count",
            "acknowledgement_total",
            "comments_count",
            "departments",
            "recipients",
            "acknowledgement_departments",
            "acknowledgement_recipients",
            "file_url",
            "file_name",
            "file_size",
            "is_acknowledged",
            "linked_tasks",
        )

    def get_is_acknowledged(self, obj: Document) -> bool:
        """Возвращает флаг ознакомления текущего пользователя.

        Args:
            obj (Document): Документ.

        Returns:
            bool: True, если текущий пользователь уже ознакомился.
        """
        annotated = getattr(obj, "_is_acknowledged", None)
        if annotated is not None:
            return bool(annotated)

        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False
        return DocumentAcknowledgement.objects.filter(
            document=obj, user=request.user
        ).exists()

    def get_acknowledgement_required_for_user(self, obj: Document) -> bool:
        """Нужно ли текущему сотруднику подтверждать ознакомление."""
        request = self.context.get("request")
        if not request or not request.user.is_authenticated:
            return False

        audience_ids = getattr(obj, "_acknowledgement_user_ids", None)
        if audience_ids is not None:
            return request.user.pk in audience_ids

        from documents.audience import user_requires_document_acknowledgement

        return user_requires_document_acknowledgement(obj, request.user)

    def get_acknowledged_count(self, obj: Document) -> int:
        """Количество сотрудников из аудитории, уже ознакомившихся."""
        attached = getattr(obj, "_acknowledged_count", None)
        if attached is not None:
            return int(attached)

        from documents.audience import document_acknowledgement_audience

        audience = document_acknowledgement_audience(obj)
        return obj.acknowledgements.filter(user__in=audience).count()

    def get_acknowledgement_total(self, obj: Document) -> int:
        """Размер аудитории обязательного ознакомления."""
        attached = getattr(obj, "_acknowledgement_total", None)
        if attached is not None:
            return int(attached)

        from documents.audience import document_acknowledgement_audience

        return document_acknowledgement_audience(obj).count()

    def get_comments_count(self, obj: Document) -> int:
        """Количество неудалённых комментариев документа."""
        attached = getattr(obj, "_comments_count", None)
        if attached is not None:
            return int(attached)

        from communications.comments_helpers import get_comment_count

        return get_comment_count(obj)

    @extend_schema_field(serializers.ListField(child=serializers.DictField()))
    def get_linked_tasks(self, obj: Document) -> list[dict]:
        prefetched = getattr(obj, "_linked_task_payloads", None)
        if prefetched is not None:
            return prefetched

        request = self.context.get("request")
        user = getattr(request, "user", None)
        if not user or not getattr(user, "is_authenticated", False):
            return []

        try:
            from django.contrib.contenttypes.models import ContentType
            from tasks.access import task_board_access_q
            from tasks.models import (
                TaskBoard,
                TaskLinkedObject,
                TaskLinkedObjectKind,
            )
        except Exception:
            return []

        content_type = ContentType.objects.get_for_model(Document)
        accessible_boards = TaskBoard.objects.filter(
            is_archived=False,
        ).filter(task_board_access_q(user))

        links = (
            TaskLinkedObject.objects.filter(
                kind=TaskLinkedObjectKind.DOCUMENT,
                content_type=content_type,
                object_id=obj.id,
                task__board__in=accessible_boards,
            )
            .select_related("task", "task__board", "task__column")
            .order_by("task__title", "task_id")
        )

        return [
            {
                "link_id": link.id,
                "id": link.task_id,
                "title": link.task.title,
                "board_id": link.task.board_id,
                "board_name": link.task.board.name,
                "column_id": link.task.column_id,
                "column_name": link.task.column.name,
                "column_color": link.task.column.color,
                "priority": link.task.priority,
                "priority_display": link.task.get_priority_display(),
            }
            for link in links
        ]


class DocumentWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для записи/обновления документа.

    Поддерживает:
        - загрузку файла (multipart) через django-filer
        - sent_to_all
        - department_ids (отделы-получатели)
        - recipient_ids (repeat/JSON/CSV) при sent_to_all=false
        - tag_ids (теги)
    """

    title = serializers.CharField(
        required=False,
        allow_blank=True,
        max_length=255,
        help_text="Название документа. Если пусто, будет взято из имени файла.",
    )
    extracted_text = serializers.CharField(required=False, allow_blank=True)

    recipient_ids = RecipientIDsField(
        write_only=True,
        required=False,
        help_text=(
            "Список ID сотрудников (repeat/JSON/CSV) "
            "при sent_to_all=false."
        ),
    )

    department_ids = RecipientIDsField(
        write_only=True,
        required=False,
        help_text="Список ID отделов-получателей.",
    )

    acknowledgement_recipient_ids = RecipientIDsField(
        write_only=True,
        required=False,
        help_text="Список ID сотрудников, обязанных ознакомиться.",
    )

    acknowledgement_department_ids = RecipientIDsField(
        write_only=True,
        required=False,
        help_text="Список ID отделов, обязанных ознакомиться.",
    )

    tag_ids = RecipientIDsField(
        write_only=True,
        required=False,
        help_text="Список ID тегов для привязки к документу.",
    )

    file = FilerFileSerializerField(
        required=False,
        allow_null=True,
        help_text="Файл для загрузки через django-filer",
    )

    class Meta:
        model = Document
        fields = (
            "id",
            "title",
            "description",
            "file",
            "folder",
            "extracted_text",
            "sent_to_all",
            "is_regulation",
            "acknowledgement_required",
            "acknowledgement_for_all",
            "department_ids",
            "recipient_ids",
            "acknowledgement_department_ids",
            "acknowledgement_recipient_ids",
            "tag_ids",
        )

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Согласованность полей.

        Args:
            attrs (dict): Данные после field-level валидаций.

        Returns:
            dict: Те же данные.

        Raises:
            serializers.ValidationError: Если sent_to_all=false
                и нет recipient_ids или department_ids.
        """
        file_obj = attrs.get("file")

        if not str(attrs.get("title") or "").strip():
            if file_obj:
                file_name = (
                    getattr(file_obj, "original_filename", "")
                    or getattr(file_obj, "name", "")
                )
                default_title = os.path.splitext(os.path.basename(file_name))[
                    0
                ].strip()
                attrs["title"] = default_title or file_name or "Документ"
            elif self.instance is None:
                attrs["title"] = "Документ"
            elif self.instance is not None:
                attrs.pop("title", None)

        instance = self.instance
        sent_to_all = attrs.get(
            "sent_to_all",
            instance.sent_to_all if instance is not None else True,
        )
        recipient_ids = set(
            attrs.get(
                "recipient_ids",
                instance.recipients.values_list("pk", flat=True)
                if instance is not None
                else [],
            )
        )
        department_ids = set(
            attrs.get(
                "department_ids",
                instance.departments.values_list("pk", flat=True)
                if instance is not None
                else [],
            )
        )

        if sent_to_all is False and not recipient_ids and not department_ids:
            raise serializers.ValidationError(
                {
                    "recipient_ids": (
                        "Укажите получателей, отделы или установите "
                        "sent_to_all=true."
                    )
                }
            )

        acknowledgement_required = attrs.get(
            "acknowledgement_required",
            instance.acknowledgement_required if instance is not None else True,
        )
        acknowledgement_for_all = attrs.get(
            "acknowledgement_for_all",
            instance.acknowledgement_for_all if instance is not None else True,
        )
        acknowledgement_recipient_ids = set(
            attrs.get(
                "acknowledgement_recipient_ids",
                instance.acknowledgement_recipients.values_list("pk", flat=True)
                if instance is not None
                else [],
            )
        )
        acknowledgement_department_ids = set(
            attrs.get(
                "acknowledgement_department_ids",
                instance.acknowledgement_departments.values_list("pk", flat=True)
                if instance is not None
                else [],
            )
        )

        if (
            acknowledgement_required
            and not acknowledgement_for_all
            and not acknowledgement_recipient_ids
            and not acknowledgement_department_ids
        ):
            raise serializers.ValidationError(
                {
                    "acknowledgement_recipient_ids": (
                        "Выберите сотрудников, отделы или включите "
                        "ознакомление для всех с доступом."
                    )
                }
            )

        if acknowledgement_required and not acknowledgement_for_all and not sent_to_all:
            invalid_departments = acknowledgement_department_ids - department_ids
            if invalid_departments:
                raise serializers.ValidationError(
                    {
                        "acknowledgement_department_ids": (
                            "Отдел для ознакомления должен иметь доступ к документу."
                        )
                    }
                )

            allowed_recipients = User.objects.filter(is_active=True).filter(
                Q(pk__in=recipient_ids)
                | Q(
                    departments_links__department_id__in=department_ids,
                    departments_links__is_active=True,
                )
            ).values_list("pk", flat=True)
            invalid_recipients = acknowledgement_recipient_ids - set(
                allowed_recipients
            )
            if invalid_recipients:
                raise serializers.ValidationError(
                    {
                        "acknowledgement_recipient_ids": (
                            "Сотрудник для ознакомления должен иметь доступ "
                            "к документу."
                        )
                    }
                )
        return attrs

    def _set_departments(
        self, doc: Document, department_ids: Sequence[int]
    ) -> int:
        """Привязывает отделы-получатели по списку ID.

        Args:
            doc (Document): Документ.
            department_ids (Sequence[int]): Идентификаторы отделов.

        Returns:
            int: Количество привязанных отделов.
        """
        from employees.models import Department

        logger.info(
            f"[serializers] _set_departments doc={doc.id} "
            f"department_ids={list(department_ids)}"
        )

        if not department_ids:
            doc.departments.clear()
            logger.info(f"[serializers] Cleared departments for doc={doc.id}")
            return 0

        departments = Department.objects.filter(id__in=set(department_ids))
        count = departments.count()
        logger.info(
            f"[serializers] Found {count} departments from "
            f"{len(department_ids)} requested IDs"
        )

        doc.departments.set(departments)
        logger.info(f"[serializers] Set {count} departments for doc={doc.id}")
        return count

    def _set_recipients(
        self, doc: Document, recipient_ids: Sequence[int]
    ) -> int:
        """Привязывает получателей по списку ID (только активные).

        Args:
            doc (Document): Документ.
            recipient_ids (Sequence[int]): Идентификаторы пользователей.

        Returns:
            int: Количество привязанных получателей.
        """
        logger.info(
            f"[serializers] _set_recipients doc={doc.id} "
            f"recipient_ids={list(recipient_ids)}"
        )

        if not recipient_ids:
            doc.recipients.clear()
            logger.info(f"[serializers] Cleared recipients for doc={doc.id}")
            return 0

        users = User.objects.filter(is_active=True, id__in=set(recipient_ids))
        count = users.count()
        logger.info(
            f"[serializers] Found {count} active users from "
            f"{len(recipient_ids)} requested IDs"
        )

        doc.recipients.set(users)
        logger.info(f"[serializers] Set {count} recipients for doc={doc.id}")
        return count

    def _set_acknowledgement_departments(
        self, doc: Document, department_ids: Sequence[int]
    ) -> int:
        from employees.models import Department

        departments = Department.objects.filter(id__in=set(department_ids))
        doc.acknowledgement_departments.set(departments)
        return departments.count()

    def _set_acknowledgement_recipients(
        self, doc: Document, recipient_ids: Sequence[int]
    ) -> int:
        users = User.objects.filter(is_active=True, id__in=set(recipient_ids))
        doc.acknowledgement_recipients.set(users)
        return users.count()

    def _set_tags(self, doc: Document, tag_ids: Sequence[int]) -> int:
        """Привязывает теги по списку ID.

        Args:
            doc (Document): Документ.
            tag_ids (Sequence[int]): Идентификаторы тегов.

        Returns:
            int: Количество привязанных тегов.
        """
        from documents.models import DocumentTag

        logger.info(
            f"[serializers] _set_tags doc={doc.id} tag_ids={list(tag_ids)}"
        )

        if not tag_ids:
            doc.tags.clear()
            logger.info(f"[serializers] Cleared tags for doc={doc.id}")
            return 0

        tags = DocumentTag.objects.filter(id__in=set(tag_ids))
        count = tags.count()
        logger.info(
            f"[serializers] Found {count} tags from {len(tag_ids)} "
            f"requested IDs"
        )

        doc.tags.set(tags)
        logger.info(f"[serializers] Set {count} tags for doc={doc.id}")
        return count

    def create(self, validated_data: Dict[str, Any]) -> Document:
        """Создание документа с корректной установкой
        получателей и уведомлением.

        Args:
            validated_data (dict): Данные.

        Returns:
            Document: Созданный документ.
        """
        recipient_ids = validated_data.pop("recipient_ids", [])
        department_ids = validated_data.pop("department_ids", [])
        acknowledgement_recipient_ids = validated_data.pop(
            "acknowledgement_recipient_ids", []
        )
        acknowledgement_department_ids = validated_data.pop(
            "acknowledgement_department_ids", []
        )
        tag_ids = validated_data.pop("tag_ids", [])
        request = self.context.get("request")
        uploader = getattr(request, "user", None)
        sent_to_all = validated_data.get("sent_to_all", True)

        logger.info(
            f"[serializers] Creating document sent_to_all={sent_to_all} "
            f"department_ids={list(department_ids)} "
            f"recipient_ids={list(recipient_ids)} "
            f"tag_ids={list(tag_ids)}"
        )

        # Создаём документ - сигналы из notification_signals.py сработают
        # автоматически
        doc = Document(  # type: ignore[arg-type]
            uploaded_by=uploader,
            **validated_data,
        )
        doc._suppress_document_notifications = True
        doc.save()
        logger.info(
            f"[serializers] Document created id={doc.id} "
            f"sent_to_all={doc.sent_to_all}"
        )

        if (
            doc.acknowledgement_required
            and not doc.acknowledgement_for_all
        ):
            self._set_acknowledgement_departments(
                doc, acknowledgement_department_ids
            )
            self._set_acknowledgement_recipients(
                doc, acknowledgement_recipient_ids
            )

        # Для индивидуальной доступности устанавливаем получателей.
        if validated_data.get("sent_to_all") is False:
            if department_ids:
                logger.info(
                    f"[serializers] Setting departments for doc={doc.id}"
                )
                self._set_departments(doc, department_ids)

            if recipient_ids:
                logger.info(
                    f"[serializers] Setting recipients for doc={doc.id}"
                )
                self._set_recipients(doc, recipient_ids)

        # Устанавливаем теги (независимо от sent_to_all)
        if tag_ids:
            logger.info(f"[serializers] Setting tags for doc={doc.id}")
            self._set_tags(doc, tag_ids)

        doc._suppress_document_notifications = False
        from documents.notifications.handlers import notify_document_audience

        notify_document_audience(doc)

        logger.info(f"[serializers] Document creation complete id={doc.id}")
        return doc

    def update(
        self, instance: Document, validated_data: Dict[str, Any]
    ) -> Document:
        """Частичное обновление документа.

        Args:
            instance (Document): Экземпляр.
            validated_data (dict): Данные.

        Returns:
            Document: Обновлённый документ.
        """
        recipient_ids = validated_data.pop("recipient_ids", None)
        department_ids = validated_data.pop("department_ids", None)
        acknowledgement_recipient_ids = validated_data.pop(
            "acknowledgement_recipient_ids", None
        )
        acknowledgement_department_ids = validated_data.pop(
            "acknowledgement_department_ids", None
        )
        tag_ids = validated_data.pop("tag_ids", None)

        for f in (
            "title",
            "description",
            "extracted_text",
            "sent_to_all",
            "is_regulation",
            "acknowledgement_required",
            "acknowledgement_for_all",
            "file",
            "folder",
        ):
            if f in validated_data:
                setattr(instance, f, validated_data[f])
        instance.save()

        if not instance.acknowledgement_required or instance.acknowledgement_for_all:
            instance.acknowledgement_recipients.clear()
            instance.acknowledgement_departments.clear()
        else:
            if acknowledgement_department_ids is not None:
                self._set_acknowledgement_departments(
                    instance, acknowledgement_department_ids
                )
            if acknowledgement_recipient_ids is not None:
                self._set_acknowledgement_recipients(
                    instance, acknowledgement_recipient_ids
                )

        # очищаем получателей и отделы при sent_to_all=true
        if "sent_to_all" in validated_data and instance.sent_to_all:
            instance.recipients.clear()
            instance.departments.clear()
        else:
            if department_ids is not None:
                self._set_departments(instance, department_ids)
            if recipient_ids is not None:
                self._set_recipients(instance, recipient_ids)

        # Обновляем теги (независимо от sent_to_all)
        if tag_ids is not None:
            self._set_tags(instance, tag_ids)

        return instance
