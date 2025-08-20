# backend/employees/forms_auth.py
from django import forms
from django.contrib.auth.forms import AuthenticationForm


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
