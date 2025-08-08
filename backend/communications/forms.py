# backend/communications/forms.py

from django import forms

from .models import Message


class MessageForm(forms.ModelForm):
    class Meta:
        model = Message
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(
                attrs={
                    "rows": 2,
                    "placeholder": "Введите сообщение...",
                    "class": "form-control",
                }
            ),
        }
