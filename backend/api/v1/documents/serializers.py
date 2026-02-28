from __future__ import annotations

import json
import logging
from typing import Any, Dict, Sequence, Iterable

from django.conf import settings
from django.http import QueryDict
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import UploadedFile
from django.template.defaultfilters import filesizeformat
from documents.models import Document, DocumentAcknowledgement
from rest_framework import serializers

from ..employees.serializers import EmployeeBriefSerializer
from .fields import FilerFileField as FilerFileSerializerField

logger = logging.getLogger(__name__)
User = get_user_model()


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

        При multipart (QueryDict) поддерживает repeat-params: recipient_ids=1&recipient_ids=2...
        """
        # 1) Спец. случай: multipart/QueryDict с repeat-params
        # DRF в обычное Field передаёт "последнее" значение, поэтому
        # забираем полный список через parent.initial_data.getlist(self.field_name)
        parent_data = getattr(self.parent, "initial_data", None)  # type: ignore[attr-defined]
        if isinstance(parent_data, QueryDict):
            values = parent_data.getlist(self.field_name)  # type: ignore[attr-defined]
            if len(values) > 1:
                data = values
            elif len(values) == 1 and not isinstance(data, (list, tuple)):
                # один элемент: оставим строкой — ниже распарсится как JSON/CSV/число
                data = values[0]

        # 2) Уже список/кортеж?
        if isinstance(data, (list, tuple)):
            # если это ['1','2','3'] — ок; если это ['[1,2]'] — распакуем как строку
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
                        raise serializers.ValidationError("Ожидается JSON-массив ID.")
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
    parent_id = serializers.IntegerField(source='parent.id', read_only=True, allow_null=True)
    path = serializers.SerializerMethodField()
    
    def get_path(self, obj) -> str:
        """Возвращает полный путь папки."""
        path_parts = []
        current = obj
        while current:
            path_parts.insert(0, current.name)
            current = current.parent
        return ' / '.join(path_parts)


class FolderBriefSerializer(serializers.Serializer):
    """Краткий сериализатор папки для вложенного отображения."""
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField(read_only=True)


class DocumentTypeSerializer(serializers.Serializer):
    """Сериализатор для типов документов."""
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()
    code = serializers.SlugField()
    description = serializers.CharField(required=False, allow_blank=True)
    icon = serializers.CharField(required=False)
    color = serializers.CharField(required=False)
    is_active = serializers.BooleanField(default=True)


class DocumentTagSerializer(serializers.Serializer):
    """Сериализатор для тегов документов."""
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()
    slug = serializers.SlugField(required=False)
    color = serializers.CharField(required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    document_count = serializers.SerializerMethodField()
    
    def get_document_count(self, obj) -> int:
        """Возвращает количество документов с этим тегом."""
        return obj.documents.count() if hasattr(obj, 'documents') else 0


class CabinetSerializer(serializers.Serializer):
    """Сериализатор для кабинетов (виртуальных коллекций)."""
    id = serializers.IntegerField(read_only=True)
    name = serializers.CharField()
    slug = serializers.SlugField(required=False)
    description = serializers.CharField(required=False, allow_blank=True)
    parent_id = serializers.IntegerField(source='parent.id', required=False, allow_null=True)
    icon = serializers.CharField(required=False)
    color = serializers.CharField(required=False)
    document_count = serializers.SerializerMethodField()
    created_by = EmployeeBriefSerializer(read_only=True)
    created_at = serializers.DateTimeField(read_only=True)
    
    def get_document_count(self, obj) -> int:
        """Возвращает количество документов в кабинете."""
        return obj.documents.count() if hasattr(obj, 'documents') else 0


class DocumentReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения документа.

    Включает список получателей и флаг, ознакомился ли текущий пользователь.
    """

    uploaded_by = EmployeeBriefSerializer(read_only=True)
    modified_by = EmployeeBriefSerializer(read_only=True)
    recipients = EmployeeBriefSerializer(many=True, read_only=True)
    departments = DepartmentBriefSerializer(many=True, read_only=True)
    folder = FolderBriefSerializer(read_only=True)
    folder_path = serializers.CharField(read_only=True)
    document_type = DocumentTypeSerializer(read_only=True)
    tags = DocumentTagSerializer(many=True, read_only=True)
    file_url = FilerFileSerializerField(source="file", read_only=True)
    file_name = serializers.CharField(source='file.name', read_only=True, allow_null=True)
    file_size = serializers.IntegerField(source='file.size', read_only=True, allow_null=True)
    is_acknowledged = serializers.SerializerMethodField()
    status = serializers.CharField(source='get_status_display', read_only=True)
    status_code = serializers.CharField(source='status', read_only=True)

    class Meta:
        model = Document
        fields = (
            "id",
            "title",
            "description",
            "extracted_text",  # Для полнотекстового поиска
            "folder",  # Папка документа
            "folder_path",  # Полный путь папки
            "document_type",  # Тип документа
            "tags",  # Теги
            "status",  # Человекочитаемый статус
            "status_code",  # Код статуса для программной обработки
            "uploaded_by",
            "uploaded_at",
            "modified_by",
            "modified_at",
            "sent_to_all",
            "acknowledgement_required",  # Требуется ли ознакомление
            "departments",
            "recipients",
            "file_url",
            "file_name",
            "file_size",
            "is_acknowledged",
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


class DocumentWriteSerializer(serializers.ModelSerializer):
    """Сериализатор для записи/обновления документа.

    Поддерживает:
        - загрузку файла (multipart) через django-filer
        - sent_to_all
        - department_ids (отделы-получатели)
        - recipient_ids (repeat/JSON/CSV) при sent_to_all=false
    """

    recipient_ids = RecipientIDsField(
        write_only=True,
        required=False,
        help_text="Список ID сотрудников (repeat/JSON/CSV) при sent_to_all=false.",
    )
    
    department_ids = RecipientIDsField(
        write_only=True,
        required=False,
        help_text="Список ID отделов-получателей.",
    )
    
    file = FilerFileSerializerField(
        required=False,
        allow_null=True,
        help_text="Файл для загрузки через django-filer"
    )

    class Meta:
        model = Document
        fields = (
            "id",
            "title",
            "description",
            "file",
            "extracted_text",
            "sent_to_all",
            "department_ids",
            "recipient_ids",
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
        if self.instance is None and not attrs.get("file"):
            raise serializers.ValidationError({"file": "Обязательное поле."})

        sent_to_all = attrs.get("sent_to_all", True)
        recipient_ids = attrs.get("recipient_ids", [])
        department_ids = attrs.get("department_ids", [])
        
        if sent_to_all is False and not recipient_ids and not department_ids:
            raise serializers.ValidationError(
                {
                    "recipient_ids": "Укажите получателей, отделы или установите sent_to_all=true."
                }
            )
        return attrs
    
    def _set_departments(self, doc: Document, department_ids: Sequence[int]) -> int:
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
        logger.info(
            f"[serializers] Set {count} departments for doc={doc.id}"
        )
        return count

    def _set_recipients(self, doc: Document, recipient_ids: Sequence[int]) -> int:
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
        logger.info(
            f"[serializers] Set {count} recipients for doc={doc.id}"
        )
        return count

    def create(self, validated_data: Dict[str, Any]) -> Document:
        """Создание документа с корректной установкой получателей и уведомлением.

        Args:
            validated_data (dict): Данные.

        Returns:
            Document: Созданный документ.
        """
        recipient_ids = validated_data.pop("recipient_ids", [])
        department_ids = validated_data.pop("department_ids", [])
        request = self.context.get("request")
        uploader = getattr(request, "user", None)
        sent_to_all = validated_data.get("sent_to_all", True)

        logger.info(
            f"[serializers] Creating document sent_to_all={sent_to_all} "
            f"department_ids={list(department_ids)} "
            f"recipient_ids={list(recipient_ids)}"
        )

        # Создаём документ - сигналы из notification_signals.py сработают автоматически
        doc = Document.objects.create(uploaded_by=uploader, **validated_data)  # type: ignore[arg-type]
        logger.info(
            f"[serializers] Document created id={doc.id} "
            f"sent_to_all={doc.sent_to_all}"
        )
        
        # Для индивидуальной рассылки устанавливаем получателей
        # Это вызовет m2m_changed сигнал
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

        logger.info(f"[serializers] Document creation complete id={doc.id}")
        return doc

    def update(self, instance: Document, validated_data: Dict[str, Any]) -> Document:
        """Частичное обновление документа.

        Args:
            instance (Document): Экземпляр.
            validated_data (dict): Данные.

        Returns:
            Document: Обновлённый документ.
        """
        recipient_ids = validated_data.pop("recipient_ids", None)
        department_ids = validated_data.pop("department_ids", None)
        
        for f in ("title", "description", "sent_to_all", "file"):
            if f in validated_data:
                setattr(instance, f, validated_data[f])
        instance.save()

        # очищаем получателей и отделы при sent_to_all=true
        if "sent_to_all" in validated_data and instance.sent_to_all:
            instance.recipients.clear()
            instance.departments.clear()
        else:
            if department_ids is not None:
                self._set_departments(instance, department_ids)
            if recipient_ids is not None:
                self._set_recipients(instance, recipient_ids)

        return instance
