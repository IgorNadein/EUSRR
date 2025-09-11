from __future__ import annotations

from typing import Any, Dict, Sequence

from django.contrib.auth import get_user_model
from documents.models import Document, DocumentAcknowledgement
from rest_framework import serializers

from ..employees.serializers import EmployeeBriefSerializer

User = get_user_model()


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
        """Проверяет, отмечал ли текущий пользователь ознакомление.

        Args:
            obj (Document): Документ.

        Returns:
            bool: True, если текущий пользователь уже ознакомился.
        """
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
        - `sent_to_all`
        - `recipient_ids` (список ID пользователей), если `sent_to_all == False`
    """

    # Принимаем список ID вместо M2M-структуры
    recipient_ids = serializers.ListField(
        child=serializers.IntegerField(min_value=1),
        write_only=True,
        required=False,
        allow_empty=True,
        help_text="Список ID сотрудников (используется, когда sent_to_all=false).",
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

    def validate(self, attrs: Dict[str, Any]) -> Dict[str, Any]:
        """Общая валидация полей.

        Args:
            attrs (dict): Данные.

        Returns:
            dict: Провалидированные данные.

        Raises:
            serializers.ValidationError: При логических несоответствиях.
        """
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
        """Привязывает получателей по списку ID.

        Args:
            doc (Document): Документ.
            recipient_ids (Sequence[int]): Идентификаторы пользователей.

        Returns:
            int: Количество привязанных получателей.
        """
        if not recipient_ids:
            doc.recipients.clear()
            return 0
        users = User.objects.filter(is_active=True, id__in=list(set(recipient_ids)))
        doc.recipients.set(users)
        return users.count()

    def create(self, validated_data: Dict[str, Any]) -> Document:
        """Создание документа.

        ВАЖНО: чтобы уведомления (signals) не улетели до установки M2M,
        мы временно отключим `post_save` сигнал и вызовем уведомление вручную уже после назначения получателей.

        Args:
            validated_data (dict): Данные.

        Returns:
            Document: Созданный документ.

        Raises:
            serializers.ValidationError: Если входные данные недопустимы.
        """
        recipient_ids = validated_data.pop("recipient_ids", [])
        request = self.context.get("request")
        uploader = getattr(request, "user", None)

        # Подключим/отключим сигнал аккуратно
        from django.db.models.signals import post_save

        try:
            from documents.signals import on_document_saved  # type: ignore
        except Exception:
            on_document_saved = None

        if on_document_saved:
            post_save.disconnect(on_document_saved, sender=Document)

        try:
            doc = Document.objects.create(
                uploaded_by=uploader,  # type: ignore[arg-type]
                **validated_data,
            )
            if validated_data.get("sent_to_all") is False:
                self._set_recipients(doc, recipient_ids)
        finally:
            if on_document_saved:
                post_save.connect(on_document_saved, sender=Document)

        # Ручное уведомление после полной подготовки (если доступно)
        try:
            from documents.notification import \
                notify_users_about_document  # type: ignore

            notify_users_about_document(doc)
        except Exception:
            # если уведомлялка неактивна — просто молча пропустим
            pass

        return doc

    def update(self, instance: Document, validated_data: Dict[str, Any]) -> Document:
        """Обновление документа.

        Сценарии:
            - можно заменить файл/описание/заголовок
            - переключить `sent_to_all`
            - обновить получателей через `recipient_ids`

        Args:
            instance (Document): Документ для обновления.
            validated_data (dict): Новые данные.

        Returns:
            Document: Обновлённый документ.
        """
        recipient_ids = validated_data.pop("recipient_ids", None)

        for field in ("title", "description", "sent_to_all", "file"):
            if field in validated_data:
                setattr(instance, field, validated_data[field])
        instance.save()

        if recipient_ids is not None:
            # Если теперь "всем" — очистим M2M
            if validated_data.get("sent_to_all", instance.sent_to_all):
                instance.recipients.clear()
            else:
                self._set_recipients(instance, recipient_ids)

        # уведомления по обновлению — по желанию; оставим тихо
        return instance
