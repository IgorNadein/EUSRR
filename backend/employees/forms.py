from django import forms
from django.contrib.auth.forms import UserCreationForm, UserChangeForm
from phonenumber_field.formfields import PhoneNumberField
from .models import Employee


class AvatarValidationMixin:
    def clean_avatar(self):
        avatar = self.cleaned_data.get('avatar')
        if avatar:
            if avatar.size > 2 * 1024 * 1024:
                raise forms.ValidationError(
                    "Размер файла не должен превышать 2MB")
            if not avatar.name.lower().endswith(('.jpg', '.jpeg', '.png')):
                raise forms.ValidationError(
                    "Допустимые форматы: JPG, JPEG, PNG")
        return avatar


class RegistrationForm(AvatarValidationMixin, UserCreationForm):
    first_name = forms.CharField(
        label="Имя",
        required=True,
        widget=forms.TextInput(attrs={'required': 'required'})
    )
    last_name = forms.CharField(
        label="Фамилия",
        required=True,
        widget=forms.TextInput(attrs={'required': 'required'})
    )
    email = forms.EmailField(
        label="Email",
        required=True,
        widget=forms.EmailInput(attrs={'required': 'required'})
    )
    avatar = forms.ImageField(
        label="Аватар",
        required=True,
        widget=forms.FileInput(attrs={'required': 'required'})
    )

    class Meta:
        model = Employee
        fields = [
            'phone_number',  # USERNAME_FIELD
            'last_name',
            'first_name',
            'patronymic',
            'birth_date',
            'whatsapp',
            'telegram',
            'email',
            'avatar',
            'password1',
            'password2'
        ]

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['whatsapp'].required = False
        self.fields['telegram'].required = False


class ProfileUpdateForm(AvatarValidationMixin, UserChangeForm):
    avatar = forms.ImageField(label='Аватарка', required=False,
                              widget=forms.ClearableFileInput(attrs={'id': 'avatarInput'}))
    telegram = forms.CharField(label='Telegram', required=False)
    whatsapp = PhoneNumberField(label='WhatsApp', required=False)

    class Meta:
        model = Employee
        fields = (
            'last_name',
            'first_name',
            'patronymic',
            'birth_date',
            'gender',
            'email',
            'phone_number',
            'telegram',
            'whatsapp',
            'wechat',
            'avatar'
        )
