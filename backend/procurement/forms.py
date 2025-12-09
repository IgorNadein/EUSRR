"""
Django Forms для модуля закупок.
"""

from django import forms

from .models import ProcurementRequest, ProcurementItem


class ProcurementRequestForm(forms.ModelForm):
    """Форма создания/редактирования заявки на закупку."""

    class Meta:
        model = ProcurementRequest
        fields = ['title', 'description', 'department', 'urgency']
        widgets = {
            'title': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Название заявки',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 4,
                'placeholder': 'Описание и обоснование закупки',
            }),
            'department': forms.Select(attrs={
                'class': 'form-select',
            }),
            'urgency': forms.Select(attrs={
                'class': 'form-select',
            }),
        }

    def __init__(self, *args, user=None, **kwargs):
        """Инициализация формы с фильтрацией отделов пользователя."""
        super().__init__(*args, **kwargs)
        if user:
            # Ограничиваем выбор отделов теми, в которых состоит юзер
            user_departments = user.departments.filter(
                employeedepartment__is_active=True
            )
            self.fields['department'].queryset = user_departments

            # Если у пользователя один отдел - выбираем его по умолчанию
            if user_departments.count() == 1:
                self.fields['department'].initial = user_departments.first()


class ProcurementItemForm(forms.ModelForm):
    """Форма добавления позиции в заявку."""

    class Meta:
        model = ProcurementItem
        fields = [
            'name', 'description', 'quantity', 'unit',
            'estimated_unit_price', 'supplier_info'
        ]
        widgets = {
            'name': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'Наименование',
            }),
            'description': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Описание позиции',
            }),
            'quantity': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 1,
            }),
            'unit': forms.TextInput(attrs={
                'class': 'form-control',
                'placeholder': 'шт.',
            }),
            'estimated_unit_price': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0.01,
                'step': '0.01',
            }),
            'supplier_info': forms.Textarea(attrs={
                'class': 'form-control',
                'rows': 2,
                'placeholder': 'Ссылки на товар, контакты поставщика',
            }),
        }
