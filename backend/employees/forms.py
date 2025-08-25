# backend/employees/forms.py
import base64
from mimetypes import guess_type

from django import forms
from django.contrib.auth.forms import (AuthenticationForm, UserChangeForm,
                                       UserCreationForm)
from django.core.exceptions import ValidationError
from employees.models import Employee
from phonenumber_field.formfields import PhoneNumberField

from .models import Department, Employee, EmployeeDepartment, Skill


# =========================
#   Регистрация
# =========================
def _file_to_data_uri(f) -> str:
    """
    Конвертирует загруженный файл (InMemoryUploadedFile) в data URI: data:<mime>;base64,<...>
    Совместимо с твоим Base64ImageField на бэкенде.
    """
    try:
        content = f.read()
        if hasattr(f, "seek"):
            f.seek(0)
    except Exception:
        return ""
    mime = (
        getattr(f, "content_type", None)
        or guess_type(getattr(f, "name", ""))[0]
        or "image/jpeg"
    )
    b64 = base64.b64encode(content).decode("ascii")
    return f"data:{mime};base64,{b64}"


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

    # Пароли — как в шаблоне
    password1 = forms.CharField(label="Пароль", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Повторите пароль", widget=forms.PasswordInput)

    # Контакты: нужен хотя бы один
    telegram = forms.CharField(required=False, label="Telegram")
    whatsapp = forms.CharField(required=False, label="WhatsApp")
    wechat = forms.CharField(required=False, label="WeChat")

    # Аватар (опционально)
    avatar = forms.ImageField(required=False, label="Аватар")

    # Опциональные поля модели
    patronymic = forms.CharField(required=False, label="Отчество")
    gender = forms.IntegerField(required=False, label="Пол (0/1/2)")
    position = forms.IntegerField(required=False, label="ID должности")
    # skills — список ID через запятую (для простоты)
    skills = forms.CharField(required=False, label="Навыки (ID через запятую)")

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
                pass
        return out

    def to_api_payload(self) -> dict:
        """
        Payload для POST /api/v1/auth/register/.
        Включает avatar как data URI, если загружен.
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
        # avatar → base64 data URI
        if cd.get("avatar"):
            payload["avatar"] = _file_to_data_uri(cd["avatar"])
        return payload

    def save(self, commit=True):
        """
        Прямое создание пользователя (если не ходим в API).
        Создаём через менеджер, аватар передаём как файл.
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
            avatar=data.get("avatar") or None,
        )
        return user


class VerifyEmailForm(forms.Form):
    email = forms.EmailField(label="Email")
    code = forms.CharField(max_length=32, label="Код из письма")


# =========================
#   Отделы
# =========================
class DepartmentEditForm(forms.Form):
    name = forms.CharField(max_length=255, label="Название")
    description = forms.CharField(
        required=False, widget=forms.Textarea, label="Описание"
    )


class SetHeadForm(forms.Form):
    # просто номер id; мы не тянем ORM
    head_id = forms.IntegerField(
        required=False, label="ID руководителя (пусто — снять)"
    )


class SetMemberRoleForm(forms.Form):
    employee_id = forms.IntegerField(label="ID сотрудника")
    role_id = forms.IntegerField(required=False, label="ID роли (пусто — снять)")
    is_active = forms.BooleanField(required=False, label="Активен в отделе")


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "description", "head"]


class InviteToDepartmentForm(forms.Form):
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.none(),
        label="Сотрудник",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, department, *args, **kwargs):
        super().__init__(*args, **kwargs)

        qs = (
            Employee.objects.all()
            # НЕ показываем тех, кто уже активен в отделе
            .exclude(
                departments_links__department=department,
                departments_links__is_active=True,
            )
            # по желанию: не показывать руководителя, если он уже назначен
            .exclude(id=department.head_id if department.head_id else None).order_by(
                "last_name", "first_name"
            )
        )

        self.fields["employee"].queryset = qs


class DepartmentMemberRoleForm(forms.ModelForm):
    class Meta:
        model = EmployeeDepartment
        fields = ["role", "is_active"]
        labels = {
            "role": "Роль в отделе",
            "is_active": "Активен в отделе",
        }
        widgets = {
            "role": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Например: Аналитик, Тимлид, Наставник",
                    "autocomplete": "off",
                }
            ),
            "is_active": forms.CheckboxInput(attrs={"class": "form-check-input"}),
        }


# =========================
#   CRUD формы
# =========================


class SkillForm(forms.ModelForm):
    class Meta:
        model = Skill
        fields = ["name"]
