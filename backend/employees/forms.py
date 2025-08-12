# backend/employees/forms.py
from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from django.core.exceptions import ValidationError
from phonenumber_field.formfields import PhoneNumberField

from .models import Absence, Department, Education, Employee, Skill


# =========================
#   Миксин для проверки аватара
# =========================
class AvatarValidationMixin:
    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar:
            if avatar.size > 2 * 1024 * 1024:
                raise forms.ValidationError("Размер файла не должен превышать 2MB")
            if not avatar.name.lower().endswith((".jpg", ".jpeg", ".png")):
                raise forms.ValidationError("Допустимые форматы: JPG, JPEG, PNG")
        return avatar


# =========================
#   Регистрация
# =========================
class RegistrationForm(AvatarValidationMixin, UserCreationForm):
    first_name = forms.CharField(label="Имя", required=True)
    last_name = forms.CharField(label="Фамилия", required=True)
    email = forms.EmailField(label="Email", required=True)
    avatar = forms.ImageField(label="Аватар", required=False)

    class Meta:
        model = Employee
        fields = [
            "phone_number",
            "last_name",
            "first_name",
            "patronymic",
            "birth_date",
            "whatsapp",
            "telegram",
            "wechat",
            "email",
            "avatar",
            "password1",
            "password2",
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["whatsapp"].required = False
        self.fields["telegram"].required = False
        self.fields["wechat"].required = False

    def clean(self):
        cleaned = super().clean()
        # Более дружественная ошибка, чем из model.clean
        if not (
            cleaned.get("whatsapp") or cleaned.get("telegram") or cleaned.get("wechat")
        ):
            raise ValidationError(
                "Укажите хотя бы один контакт: WhatsApp, Telegram или WeChat."
            )
        return cleaned


# =========================
#   Обновление профиля
# =========================
class ProfileUpdateForm(AvatarValidationMixin, UserChangeForm):
    avatar = forms.ImageField(
        label="Аватар", required=False, widget=forms.ClearableFileInput()
    )
    telegram = forms.CharField(label="Telegram", required=False)
    whatsapp = PhoneNumberField(label="WhatsApp", required=False)
    wechat = PhoneNumberField(label="WeChat", required=False)

    class Meta:
        model = Employee
        fields = (
            "last_name",
            "first_name",
            "patronymic",
            "birth_date",
            "gender",
            "email",
            "phone_number",
            "telegram",
            "whatsapp",
            "wechat",
            "avatar",
        )

    def clean(self):
        cleaned = super().clean()
        # Дублируем проверку для понятного сообщения
        if not (
            cleaned.get("whatsapp") or cleaned.get("telegram") or cleaned.get("wechat")
        ):
            raise ValidationError(
                "Укажите хотя бы один контакт: WhatsApp, Telegram или WeChat."
            )
        return cleaned


# =========================
#   SMS верификация
# =========================
class SMSCodeVerifyForm(forms.Form):
    code = forms.CharField(label="Код из SMS", max_length=6)


# =========================
#   Отделы
# =========================
class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ["name", "description", "head"]


class InviteToDepartmentForm(forms.Form):
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.none(),
        label="Сотрудник",
        widget=forms.Select(attrs={"class": "form-select"})
    )

    def __init__(self, department, *args, **kwargs):
        super().__init__(*args, **kwargs)

        qs = (Employee.objects
              .all()
              # НЕ показываем тех, кто уже активен в отделе
              .exclude(
                  departments_links__department=department,
                  departments_links__is_active=True,
              )
              # по желанию: не показывать руководителя, если он уже назначен
              .exclude(id=department.head_id if department.head_id else None)
              .order_by("last_name", "first_name"))

        self.fields["employee"].queryset = qs


# =========================
#   CRUD формы
# =========================
class AbsenceForm(forms.ModelForm):
    class Meta:
        model = Absence
        fields = ["type", "date_from", "date_to", "comment"]

    def clean(self):
        cleaned = super().clean()
        start = cleaned.get("date_from")
        end = cleaned.get("date_to")
        if start and end and start > end:
            raise ValidationError("Дата начала не может быть позже даты окончания.")
        return cleaned


class SkillForm(forms.ModelForm):
    class Meta:
        model = Skill
        fields = ["name"]


class EducationForm(forms.ModelForm):
    class Meta:
        model = Education
        fields = ["institution", "degree", "graduation_year"]

    def clean_graduation_year(self):
        year = self.cleaned_data.get("graduation_year")
        if year and (year < 1900 or year > 2100):
            raise ValidationError("Некорректный год окончания.")
        return year
