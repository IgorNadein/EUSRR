from django import forms

TYPE_COMPANY = "company"
TYPE_DEPARTMENT = "department"


class LoginForm(forms.Form):
    email = forms.EmailField(label="Email")
    password = forms.CharField(label="Пароль", widget=forms.PasswordInput)


class PostCreateForm(forms.Form):
    type = forms.ChoiceField(
        choices=[(TYPE_COMPANY, "Главная (компания)"), (TYPE_DEPARTMENT, "Отдел")]
    )
    department = forms.IntegerField(
        required=False, min_value=1, label="Отдел (для новостей отдела)"
    )
    title = forms.CharField(max_length=200, label="Заголовок")
    body = forms.CharField(widget=forms.Textarea, label="Текст")
    image = forms.ImageField(required=False, label="Изображение")
    attachment = forms.FileField(required=False, label="Вложение")


class CommentForm(forms.Form):
    post = forms.IntegerField(widget=forms.HiddenInput)
    text = forms.CharField(
        required=False, widget=forms.Textarea(attrs={"rows": 2}), label="Комментарий"
    )
    image = forms.ImageField(required=False, label="Изображение")
    attachment = forms.FileField(required=False, label="Файл")

    def clean(self):
        cleaned = super().clean()
        has_any = bool(
            (cleaned.get("text") or "").strip()
            or cleaned.get("image")
            or cleaned.get("attachment")
        )
        if not has_any:
            raise forms.ValidationError("Нужно указать текст, изображение или файл.")
        return cleaned
