from __future__ import annotations

import json
from typing import Any, Dict, Sequence, Iterable

from django.conf import settings
from django.http import QueryDict
from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import UploadedFile
from django.template.defaultfilters import filesizeformat
from documents.models import Document, DocumentAcknowledgement
from rest_framework import serializers

from ..employees.serializers import EmployeeBriefSerializer

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


class DocumentReadSerializer(serializers.ModelSerializer):
    """Сериализатор для чтения документа.

    Включает список получателей и флаг, ознакомился ли текущий пользователь.
    """

    uploaded_by = EmployeeBriefSerializer(read_only=True)
    recipients = EmployeeBriefSerializer(many=True, read_only=True)
    file_url = serializers.FileField(source="file", read_only=True)
    is_acknowledged = serializers.SerializerMethodField()

    class Meta:
        model = Document
        fields = (
            "id",
            "title",
            "description",
            "uploaded_by",
            "uploaded_at",
            "sent_to_all",
            "recipients",
            "file_url",
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
        - загрузку файла (multipart)
        - sent_to_all
        - recipient_ids (repeat/JSON/CSV) при sent_to_all=false
    """

    recipient_ids = RecipientIDsField(
        write_only=True,
        required=False,
        help_text="Список ID сотрудников (repeat/JSON/CSV) при sent_to_all=false.",
    )

    class Meta:
        model = Document
        fields = (
            "id",
            "title",
            "description",
            "file",
            "sent_to_all",
            "recipient_ids",
        )
        extra_kwargs = {
            "file": {"required": False, "allow_null": True},
        }

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Согласованность полей.

        Args:
            attrs (dict): Данные после field-level валидаций.

        Returns:
            dict: Те же данные.

        Raises:
            serializers.ValidationError: Если sent_to_all=false и нет recipient_ids.
        """
        if self.instance is None and not attrs.get("file"):
            raise serializers.ValidationError({"file": "Обязательное поле."})

        sent_to_all = attrs.get("sent_to_all", True)
        recipient_ids = attrs.get("recipient_ids", [])
        if sent_to_all is False and not recipient_ids:
            raise serializers.ValidationError(
                {
                    "recipient_ids": "Укажите получателей или установите sent_to_all=true."
                }
            )
        return attrs

    def _set_recipients(self, doc: Document, recipient_ids: Sequence[int]) -> int:
        """Привязывает получателей по списку ID (только активные).

        Args:
            doc (Document): Документ.
            recipient_ids (Sequence[int]): Идентификаторы пользователей.

        Returns:
            int: Количество привязанных получателей.
        """
        if not recipient_ids:
            doc.recipients.clear()
            return 0
        users = User.objects.filter(is_active=True, id__in=set(recipient_ids))
        doc.recipients.set(users)
        return users.count()

    def create(self, validated_data: Dict[str, Any]) -> Document:
        """Создание документа с корректной установкой получателей и уведомлением.

        Args:
            validated_data (dict): Данные.

        Returns:
            Document: Созданный документ.
        """
        recipient_ids = validated_data.pop("recipient_ids", [])
        request = self.context.get("request")
        uploader = getattr(request, "user", None)

        # временно отключаем сигнал, чтобы M2M успели установиться
        from django.db.models.signals import post_save

        try:
            from documents.signals import on_document_saved  # type: ignore
        except Exception:
            on_document_saved = None

        if on_document_saved:
            post_save.disconnect(on_document_saved, sender=Document)

        try:
            doc = Document.objects.create(uploaded_by=uploader, **validated_data)  # type: ignore[arg-type]
            if validated_data.get("sent_to_all") is False:
                self._set_recipients(doc, recipient_ids)
        finally:
            if on_document_saved:
                post_save.connect(on_document_saved, sender=Document)

        # уведомление после полной подготовки
        try:
            from documents.notification import notify_users_about_document  # type: ignore

            notify_users_about_document(doc)
        except Exception:
            pass

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
        for f in ("title", "description", "sent_to_all", "file"):
            if f in validated_data:
                setattr(instance, f, validated_data[f])
        instance.save()

        # очищаем получателей при sent_to_all=true
        if "sent_to_all" in validated_data and instance.sent_to_all:
            instance.recipients.clear()
        elif recipient_ids is not None:
            self._set_recipients(instance, recipient_ids)

        return instance

    def validate_file(self, f: UploadedFile) -> UploadedFile:
        """Проверяет, что размер загружаемого файла не превышает системный лимит.

        Лимит берётся из settings.DATA_UPLOAD_MAX_MEMORY_SIZE. Если он задан (truthy),
        и размер файла больше лимита, возвращается 400 (ValidationError).

        Args:
            f (UploadedFile): Загружаемый файл.

        Returns:
            UploadedFile: Исходный файл при успешной проверке.

        Raises:
            serializers.ValidationError: Размер файла превышает допустимый лимит.
            TypeError: Если невозможно определить размер файла.
        """
        limit = getattr(settings, "DATA_UPLOAD_MAX_MEMORY_SIZE", None)
        if limit:
            size = getattr(f, "size", None)
            if size is None:
                raise TypeError("Невозможно определить размер файла")
            if int(size) > int(limit):
                human = filesizeformat(limit)
                raise serializers.ValidationError(f"Файл слишком большой: > {human}.")
        return f
