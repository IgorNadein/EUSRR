"""
Django Forms для модуля закупок.
"""
from datetime import date

from django import forms

from .models import ProcurementRequest, ProcurementItem, Budget


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


class BudgetForm(forms.ModelForm):
    """Форма создания/редактирования бюджета отдела."""

    QUARTER_CHOICES = [
        (1, '1 квартал'),
        (2, '2 квартал'),
        (3, '3 квартал'),
        (4, '4 квартал'),
    ]

    class Meta:
        model = Budget
        fields = ['department', 'year', 'quarter', 'allocated_amount']
        widgets = {
            'department': forms.Select(attrs={
                'class': 'form-select',
            }),
            'year': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 2020,
                'max': 2100,
            }),
            'quarter': forms.Select(attrs={
                'class': 'form-select',
            }),
            'allocated_amount': forms.NumberInput(attrs={
                'class': 'form-control',
                'min': 0,
                'step': '0.01',
                'placeholder': '0.00',
            }),
        }
        labels = {
            'department': 'Отдел',
            'year': 'Год',
            'quarter': 'Квартал',
            'allocated_amount': 'Выделенная сумма (₽)',
        }

    def __init__(self, *args, **kwargs):
        """Инициализация формы с текущим годом/кварталом."""
        super().__init__(*args, **kwargs)
        
        # Устанавливаем текущий год и квартал по умолчанию для новых бюджетов
        if not self.instance.pk:
            today = date.today()
            self.fields['year'].initial = today.year
            self.fields['quarter'].initial = (today.month - 1) // 3 + 1

    def clean(self):
        """Проверка уникальности бюджета."""
        cleaned_data = super().clean()
        department = cleaned_data.get('department')
        year = cleaned_data.get('year')
        quarter = cleaned_data.get('quarter')

        if department and year and quarter:
            # Проверяем, нет ли уже такого бюджета
            existing = Budget.objects.filter(
                department=department,
                year=year,
                quarter=quarter
            )
            # Исключаем текущий объект при редактировании
            if self.instance.pk:
                existing = existing.exclude(pk=self.instance.pk)
            
            if existing.exists():
                raise forms.ValidationError(
                    f'Бюджет для отдела "{department}" на {year} год, '
                    f'{quarter} квартал уже существует.'
                )

        return cleaned_data
