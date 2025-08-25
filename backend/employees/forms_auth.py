# backend/employees/forms_auth.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm
from django.core.exceptions import ValidationError
from employees.models import Employee


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
    # Обязательные поля
    first_name = forms.CharField(max_length=150, label="Имя")
    last_name = forms.CharField(max_length=150, label="Фамилия")
    phone_number = forms.CharField(max_length=100, label="Номер телефона")
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
    # skills — список ID через запятую (для простоты)
    skills = forms.CharField(required=False, label="Навыки (ID через запятую)")
    avatar = forms.ImageField(required=False, label="Аватар")

    def clean(self):
        data = super().clean()

        # хотя бы один контакт
        if not (data.get("telegram") or data.get("whatsapp") or data.get("wechat")):
            raise ValidationError(
                "Заполните хотя бы одно из полей: WhatsApp, WeChat или Telegram"
            )

        # пароли совпадают
        p1 = data.get("password1")
        p2 = data.get("password2")
        if p1 or p2:
            if p1 != p2:
                raise ValidationError("Пароли не совпадают.")
        else:
            raise ValidationError("Введите пароль и его подтверждение.")

        return data

    def skills_ids(self) -> list[int]:
        raw = (self.cleaned_data.get("skills") or "").strip()
        if not raw:
            return []
        out: list[int] = []
        for chunk in raw.split(","):
            chunk = chunk.strip()
            if not chunk:
                continue
            try:
                out.append(int(chunk))
            except ValueError:
                # игнорируем мусор
                pass
        return out

    def to_api_payload(self) -> dict:
        """
        Преобразует данные формы в payload для POST /api/v1/auth/register/
        Ключи ориентированы на API-сериализатор (password — из password1).
        """
        cd = self.cleaned_data
        payload = {
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
        # доп. поля, если заданы
        if cd.get("patronymic"):
            payload["patronymic"] = cd["patronymic"]
        if cd.get("gender") is not None:
            payload["gender"] = cd["gender"]
        if cd.get("position") is not None:
            payload["position"] = cd["position"]
        ids = self.skills_ids()
        if ids:
            payload["skills"] = ids
        return payload

    def save(self, commit=True):
        """
        Прямое создание пользователя (если не используешь API-прокси).
        Для фронта обычно лучше отправлять payload в API,
        но метод оставлен на случай локальной регистрации.
        """
        data = self.cleaned_data
        user = Employee.objects.create_user(
            email=data["email"].strip().lower(),
            password=data["password1"],
            phone_number=data["phone_number"],
            first_name=data["first_name"],
            last_name=data["last_name"],
            birth_date=data.get("birth_date"),
            telegram=data.get("telegram", ""),
            whatsapp=data.get("whatsapp", ""),
            wechat=data.get("wechat", ""),
        )
        return user


class VerifyEmailForm(forms.Form):
    email = forms.EmailField(label="Email")
    code = forms.CharField(max_length=32, label="Код из письма")
