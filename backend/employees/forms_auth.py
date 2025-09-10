# backend/employees/forms_auth.py
from __future__ import annotations

import base64
from typing import Any, Dict, List, Optional

from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.files.uploadedfile import UploadedFile
from PIL import Image


class EmailOrPhoneAuthenticationForm(AuthenticationForm):
    username = forms.CharField(
        label="Email или телефон",
        widget=forms.TextInput(
            attrs={
                "autofocus": True,
                "placeholder": "user@example.com или +7 999 123-45-67",
            }
        ),
    )
    password = forms.CharField(
        label="Пароль",
        strip=False,
        widget=forms.PasswordInput(attrs={"autocomplete": "current-password"}),
    )


class RegistrationForm(forms.Form):
    """Форма регистрации для POST /api/v1/auth/register/.

    Валидирует обязательные поля, совпадение паролей и наличие хотя бы одного контактного способа.
    Метод :meth:`to_api_payload` готовит JSON-совместимый payload под ваш DRF-сериализатор,
    включая аватар, закодированный как data URI (base64).

    Notes:
        Вызывайте :meth:`to_api_payload` только после успешной валидации (`form.is_valid()`).

    Raises:
        ValidationError: Бросается не напрямую, а через `self.add_error(...)` — форма станет невалидной.
    """

    # Обязательные поля
    first_name = forms.CharField(max_length=150, label="Имя")
    last_name = forms.CharField(max_length=150, label="Фамилия")
    phone_number = forms.CharField(
        max_length=17,  # + и до 15 цифр (с запасом)
        label="Номер телефона",
        widget=forms.TextInput(attrs={
            "type": "tel",
            "inputmode": "numeric",
            "pattern": r"^\+?\d{10,15}$",
            "autocomplete": "tel",
            "data-phone-only": "1",
            "title": "Введите номер в формате +79991234567 (10–15 цифр)",
        })
    )
    email = forms.EmailField(label="Email")
    birth_date = forms.DateField(
        label="Дата рождения", widget=forms.DateInput(attrs={"type": "date"})
    )

    # Пароли как в шаблоне (password1/password2)
    password1 = forms.CharField(label="Пароль", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Повторите пароль", widget=forms.PasswordInput)

    # Контакты: нужен хотя бы один
    telegram = forms.CharField(required=False, label="Telegram")
    whatsapp = forms.CharField(required=False, label="WhatsApp")
    wechat = forms.CharField(required=False, label="WeChat")

    # Опциональные поля модели
    patronymic = forms.CharField(required=False, label="Отчество")
    gender = forms.IntegerField(required=False, label="Пол (0/1/2)")
    position = forms.IntegerField(required=False, label="ID должности")
    # skills — список ID через запятую
    skills = forms.CharField(required=False, label="Навыки (ID через запятую)")
    avatar = forms.ImageField(required=False, label="Аватар")

    def clean(self) -> Dict[str, Any]:
        """Глобальная валидация формы.

        Проверяет:
            - наличие хотя бы одного контактного поля (Telegram/WhatsApp/WeChat);
            - корректность паролей (оба заполнены и совпадают).

        Returns:
            dict: Очищенные данные формы.
        """
        data = super().clean()

        # хотя бы один контакт
        if not (
            (data.get("telegram") or "").strip()
            or (data.get("whatsapp") or "").strip()
            or (data.get("wechat") or "").strip()
        ):
            self.add_error(
                None,
                "Заполните хотя бы одно из полей: WhatsApp, WeChat или Telegram",
            )

        # пароли
        p1 = (data.get("password1") or "").strip()
        p2 = (data.get("password2") or "").strip()
        if not p1:
            self.add_error("password1", "Введите пароль.")
        if not p2:
            self.add_error("password2", "Подтвердите пароль.")
        if p1 and p2 and p1 != p2:
            self.add_error("password2", "Пароли не совпадают.")

        return data

    def skills_ids(self) -> List[int]:
        """Возвращает список ID навыков из текстового поля.

        Returns:
            list[int]: Список целых ID. Пустой, если поле пустое или состоит из мусора.
        """
        raw = (self.cleaned_data.get("skills") or "").strip()
        if not raw:
            return []
        out: List[int] = []
        for chunk in raw.split(","):
            s = chunk.strip()
            if not s:
                continue
            try:
                out.append(int(s))
            except ValueError:
                # игнорируем мусор
                continue
        return out

    # ---------- Вспомогательные методы для аватара ----------

    @staticmethod
    def _guess_mime(upload: UploadedFile, content: bytes) -> str:
        """Определяет MIME-тип изображения.

        Args:
            upload: Загруженный файл (может содержать content_type).
            content: Байты файла.

        Returns:
            str: MIME-тип, например 'image/jpeg'.
        """
        # 1) используем content_type, если его дал браузер/клиент
        ct = getattr(upload, "content_type", None)
        if ct and ct.startswith("image/"):
            return ct

        # 2) пробуем Pillow
        if Image is not None:
            try:
                im = Image.open(upload)  # type: ignore[arg-type]
                fmt = (im.format or "").upper()
                mime = Image.MIME.get(fmt)
                if mime:
                    # откатим указатель, чтобы не ломать повторные чтения
                    try:
                        upload.seek(0)
                    except Exception:
                        pass
                    return mime
            except Exception:
                try:
                    upload.seek(0)
                except Exception:
                    pass

        # 3) дефолт
        return "image/jpeg"

    @staticmethod
    def _file_to_data_uri(upload: UploadedFile) -> Optional[str]:
        """Кодирует изображение в data URI (base64).

        Args:
            upload: Загруженный файл.

        Returns:
            Optional[str]: Строка вида 'data:<mime>;base64,<payload>' или None, если нет данных.

        Raises:
            ValueError: Если файл нельзя прочитать.
        """
        if not upload:
            return None
        try:
            content: bytes = upload.read()
            try:
                upload.seek(0)
            except Exception:
                pass
        except Exception as exc:
            raise ValueError("Не удалось прочитать файл аватара.") from exc

        if not content:
            return None

        mime = RegistrationForm._guess_mime(upload, content)
        b64 = base64.b64encode(content).decode("ascii")
        return f"data:{mime};base64,{b64}"

    # ---------- Публичные методы ----------

    def to_api_payload(self) -> Dict[str, Any]:
        """Готовит JSON payload для POST `/api/v1/auth/register/`.

        Включает:
            - все обязательные поля;
            - контакты (как пустые строки, если не указаны);
            - дополнительные поля (если заданы);
            - `avatar` как data URI (base64), если файл загружен.

        Returns:
            dict[str, Any]: Готовый словарь.

        Raises:
            KeyError: Если метод вызван до `is_valid()` и ключей нет в `cleaned_data`.
            ValueError: При проблеме чтения файла аватара.
        """
        cd = self.cleaned_data  # предполагается, что форма валидна

        payload: Dict[str, Any] = {
            "first_name": cd["first_name"],
            "last_name": cd["last_name"],
            "phone_number": cd["phone_number"],
            "email": cd["email"],
            "birth_date": cd["birth_date"].isoformat(),
            "password": cd["password1"],
            "telegram": cd.get("telegram") or "",
            "whatsapp": cd.get("whatsapp") or "",
            "wechat": cd.get("wechat") or "",
        }

        # Доп. поля
        if cd.get("patronymic"):
            payload["patronymic"] = cd["patronymic"]
        if cd.get("gender") is not None:
            payload["gender"] = cd["gender"]
        if cd.get("position") is not None:
            payload["position"] = cd["position"]

        ids = self.skills_ids()
        if ids:
            payload["skills"] = ids

        # Аватар → base64 data URI (совместимо с Base64ImageField)
        avatar_file = cd.get("avatar")
        if avatar_file:
            data_uri = self._file_to_data_uri(avatar_file)
            if data_uri:
                payload["avatar"] = data_uri

        return payload


class VerifyEmailForm(forms.Form):
    email = forms.EmailField(label="Email")
    code = forms.CharField(max_length=32, label="Код из письма")
