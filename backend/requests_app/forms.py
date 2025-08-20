# backend/requests_app/forms.py
import logging

from django import forms
from django.core.exceptions import ValidationError

from .constants import (
    _ALLOWED_EXTS_DOTTED,
    MAX_ATTACHMENT_SIZE,
    SAFE_EXTENSIONS,
    SAFE_MIME_TYPES,
)
from .models import Request

logger = logging.getLogger(__name__)


def _sniff_mime(uploaded_file) -> str | None:
    """
    Осторожно определяем MIME по началу файла (python-magic).
    Бросаем ValidationError, если не удаётся безопасно прочитать/вернуть позицию.
    Возвращаем None, если magic недоступен.
    """
    if not uploaded_file:
        return None

    try:
        import magic  # type: ignore
    except Exception:
        logger.warning(
            "python-magic не установлен; строгая MIME-проверка отключена. "
            "Будет использовано content_type/расширение."
        )
        return None

    # Сохраняем позицию курсора
    try:
        pos = uploaded_file.file.tell()
    except Exception:
        logger.warning("Файл не поддерживает .tell(); проверка MIME невозможна.")
        raise ValidationError("Не удалось проверить тип файла. Попробуйте другой файл.")

    try:
        head = uploaded_file.file.read(2048) or b""
        if not head:
            logger.warning("Не удалось прочитать начало файла для MIME-проверки.")
            raise ValidationError(
                "Не удалось проверить тип файла. Попробуйте другой файл."
            )
        mime = magic.Magic(mime=True).from_buffer(head)
        return mime.split(";", 1)[0].strip() if mime else None
    except ValidationError:
        raise
    except Exception as e:
        logger.warning("Ошибка при MIME-проверке через python-magic: %s", e)
        raise ValidationError("Не удалось проверить тип файла. Попробуйте другой файл.")
    finally:
        try:
            uploaded_file.file.seek(pos)
        except Exception:
            logger.warning("Не удалось восстановить позицию файла после чтения.")
            # Фейлим явно — чтобы не сохранить повреждённый поток
            raise ValidationError(
                "Не удалось проверить тип файла. Попробуйте другой файл."
            )


class RequestForm(forms.ModelForm):
    """
    Создание заявки пользователем.
    UX-валидируем только *порядок дат* (без дублирования бизнес-логики модели).
    """

    date_from = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        label="Дата начала",
        help_text="Если не требуется — оставьте пустым.",
        error_messages={"invalid": "Некорректная дата."},
    )
    date_to = forms.DateField(
        required=False,
        widget=forms.DateInput(attrs={"type": "date", "class": "form-control"}),
        label="Дата окончания",
        help_text="Если не требуется — оставьте пустым.",
        error_messages={"invalid": "Некорректная дата."},
    )
    comment = forms.CharField(
        required=False,
        widget=forms.Textarea(attrs={"class": "form-control", "rows": 3}),
        label="Комментарий",
    )
    attachment = forms.FileField(
        required=False,
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".pdf,.jpg,.jpeg,.png"}
        ),
        label="Вложение",
        help_text="Допустимые форматы: PDF/JPG/PNG. До 10 МБ.",
        error_messages={"invalid": "Недопустимое вложение."},
    )

    class Meta:
        model = Request
        fields = ["type", "date_from", "date_to", "comment", "attachment"]
        widgets = {
            "type": forms.Select(attrs={"class": "form-select"}),
        }
        labels = {"type": "Тип заявления"}
        help_texts = {"type": "Выберите тип заявления."}
        error_messages = {"type": {"required": "Пожалуйста, выберите тип заявления."}}

    # UX: только порядок дат (модель проверит остальное)
    def clean(self):
        cleaned = super().clean()
        start, end = cleaned.get("date_from"), cleaned.get("date_to")
        if start and end and start > end:
            self.add_error(
                "date_to", "Дата окончания не может быть раньше даты начала."
            )
        return cleaned

    def _validate_attachment_common(self, f):
        if not f:
            return

        size = getattr(f, "size", 0)
        if size == 0:
            raise ValidationError("Пустой файл не допускается.")
        if size and size > MAX_ATTACHMENT_SIZE:
            raise ValidationError("Размер файла не должен превышать 10 МБ.")

        name = getattr(f, "name", "") or ""
        ext = name.rsplit(".", 1)[-1].lower() if "." in name else ""
        ext_dot = f".{ext}" if ext else ""

        # Пытаемся определить MIME строго
        try:
            mime = _sniff_mime(f)
        except ValidationError as e:
            raise e

        # Если magic недоступен (mime=None) — усиливаем проверку:
        # требуется *и* корректный content_type, *и* корректное расширение.
        content_type = (getattr(f, "content_type", None) or "").split(";", 1)[
            0
        ].strip() or None
        if mime is None:
            if not (
                content_type in SAFE_MIME_TYPES and ext_dot in _ALLOWED_EXTS_DOTTED
            ):
                raise ValidationError(
                    "Недопустимый тип файла. Разрешены: PDF, JPG, PNG."
                )
            return

        # Если MIME определён — он должен быть из белого списка
        if mime not in SAFE_MIME_TYPES:
            raise ValidationError("Недопустимый тип файла. Разрешены: PDF, JPG, PNG.")
        # Дополнительная мягкая проверка на расширение
        if ext_dot not in SAFE_EXTENSIONS:
            raise ValidationError(
                "Недопустимый тип файла (расширение). Разрешены: PDF, JPG, PNG."
            )

    def clean_attachment(self):
        f = self.cleaned_data.get("attachment")
        self._validate_attachment_common(f)
        return f


class RequestStatusForm(forms.ModelForm):
    """
    Обработка заявки HR/руководителем.
    Обязательно передавайте user=..., чтобы ограничить допустимые статусы.
    По умолчанию: approved/rejected; для staff/HR добавляется cancelled.
    """

    BASE_ALLOWED = {
        Request.STATUS_PENDING,
        Request.STATUS_APPROVED,
        Request.STATUS_REJECTED,
    }

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        if user is None:
            raise ValueError("RequestStatusForm требует параметр user.")

        allowed = set(self.BASE_ALLOWED)

        self._allowed_statuses = allowed
        self.fields["status"].choices = [
            (value, label)
            for value, label in Request.STATUS_CHOICES
            if value in allowed
        ]

    class Meta:
        model = Request
        fields = ["status",]
        widgets = {
            "status": forms.Select(attrs={"class": "form-select"}),
        }
        labels = {
            "status": "Статус заявления",
        }
        help_texts = {"status": "Выберите итог по заявлению."}
        error_messages = {"status": {"required": "Укажите новый статус заявления."}}

    def clean_status(self):
        value = self.cleaned_data.get("status")
        if value not in self._allowed_statuses:
            raise ValidationError("Недопустимый статус для вашей роли.")
        inst = self.instance
        if getattr(inst, "is_final", False) and value != inst.status:
            raise ValidationError(
                "Финальный статус уже установлен и не может быть изменён."
            )
        return value

    def clean_attachment(self):
        f = self.cleaned_data.get("attachment")
        RequestForm._validate_attachment_common(self, f)
        return f
