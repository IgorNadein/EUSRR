# backend\employees\forms_front.py
from django import forms

from .models import Department


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
