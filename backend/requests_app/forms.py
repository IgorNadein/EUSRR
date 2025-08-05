from django import forms
from .models import Request


class RequestForm(forms.ModelForm):
    class Meta:
        model = Request
        fields = ['type', 'date_from', 'date_to', 'comment']
        widgets = {
            'type': forms.Select(attrs={'class': 'form-select'}),
            'date_from': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'date_to': forms.DateInput(attrs={'type': 'date', 'class': 'form-control'}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'type': 'Тип заявления',
            'date_from': 'Дата начала',
            'date_to': 'Дата окончания',
            'comment': 'Комментарий',
        }
        help_texts = {
            'type': 'Выберите тип заявления',
            'date_from': 'Если не требуется — оставьте пустым',
            'date_to': 'Если не требуется — оставьте пустым',
        }


class RequestStatusForm(forms.ModelForm):
    class Meta:
        model = Request
        fields = ['status', 'comment']
        widgets = {
            'status': forms.Select(attrs={'class': 'form-select'}),
            'comment': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }
        labels = {
            'status': 'Статус заявления',
            'comment': 'Комментарий (для сотрудника)',
        }
        help_texts = {
            'status': 'Измените статус, чтобы согласовать или отклонить заявление.',
        }
