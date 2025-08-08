# backend\employees\models.py
from django.contrib.auth.models import AbstractUser, BaseUserManager
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone

# from django.utils.translation import gettext_lazy as _
from phonenumber_field.modelfields import PhoneNumberField

from .constants import ACTION_CHOICES, ACTION_DISMISSED, GENDER_CHOICES


class EmployeeManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone_number, email, password=None, **extra_fields):
        if not phone_number:
            raise ValueError("Пользователь должен иметь номер телефона")
        if not email:
            raise ValueError("Пользователь должен иметь email")
        email = self.normalize_email(email)
        user = self.model(phone_number=phone_number, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        if not extra_fields.get("is_staff"):
            raise ValueError("Суперпользователь должен иметь is_staff=True")
        if not extra_fields.get("is_superuser"):
            raise ValueError("Суперпользователь должен иметь is_superuser=True")
        return self.create_user(phone_number, email, password, **extra_fields)


class Employee(AbstractUser):
    # Отключаем username
    username = None

    gender = models.PositiveSmallIntegerField(
        "Пол", choices=GENDER_CHOICES, default=0, blank=True
    )
    avatar = models.ImageField("Фото", upload_to="users/avatars", blank=True, null=True)
    phone_number = PhoneNumberField("Номер телефона", max_length=100, unique=True)
    patronymic = models.CharField("Отчество", max_length=100, blank=True)
    birth_date = models.DateField("Дата рождения", blank=True, null=True)
    email = models.EmailField("email address", unique=True)
    telegram = models.CharField("Telegram", max_length=100, blank=True)
    whatsapp = PhoneNumberField("WhatsApp", blank=True)
    wechat = models.CharField("WeChat", max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    skills = models.ManyToManyField("Skill", related_name="employees", blank=True)
    is_active = models.BooleanField(default=False)
    sms_activation_code = models.CharField(max_length=6, blank=True, null=True)

    objects = EmployeeManager()

    USERNAME_FIELD = "phone_number"
    REQUIRED_FIELDS = ["first_name", "last_name", "email"]

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"
        ordering = ("last_name", "first_name")
        indexes = [
            models.Index(fields=["last_name", "first_name"]),
            models.Index(fields=["email"]),
            models.Index(fields=["phone_number"]),
        ]

    def clean(self):
        super().clean()
        if not (self.whatsapp or self.telegram or self.wechat):
            raise ValidationError(
                "Заполните хотя бы одно из полей: WhatsApp, WeChat или Telegram",
                code="contact_required",
            )

    def __str__(self):
        return f"{self.last_name} {self.first_name}"

    @classmethod
    def get_active(cls):
        qs = cls.objects.prefetch_related("actions").order_by("-created_at")
        return [e for e in qs if e.is_actually_active]

    @property
    def employment_status(self):
        last_action = self.actions.order_by("-date").first()
        if last_action:
            return last_action.get_action_display()
        return "Нет данных"

    @property
    def departments(self):
        from employees.models import Department, EmployeeDepartment

        # Отделы, где сотрудник активен
        department_ids = EmployeeDepartment.objects.filter(
            employee=self, is_active=True
        ).values_list("department_id", flat=True)
        # Плюс отделы, где сотрудник начальник
        head_ids = Department.objects.filter(head=self).values_list("id", flat=True)
        return Department.objects.filter(
            models.Q(id__in=department_ids) | models.Q(id__in=head_ids)
        ).distinct()

    @property
    def is_actually_active(self):
        last_action = self.actions.order_by("-date").first()
        if not last_action:
            return False
        return last_action.action != ACTION_DISMISSED


class EmployeeAction(models.Model):

    employee = models.ForeignKey(
        Employee, related_name="actions", on_delete=models.CASCADE
    )
    action = models.CharField("Кадровое событие", max_length=32, choices=ACTION_CHOICES)
    date = models.DateTimeField("Дата действия")
    comment = models.TextField("Комментарий/причина", blank=True)
    extra = models.JSONField("Дополнительно", blank=True, null=True)

    class Meta:
        verbose_name = "Кадровое событие"
        verbose_name_plural = "Кадровые события"
        ordering = ["-date"]

    def __str__(self):
        return f"{self.employee} — {self.get_action_display()} — {self.date:%d.%m.%Y}"


class Department(models.Model):
    name = models.CharField("Название отдела", max_length=255, unique=True)
    description = models.TextField("Описание", blank=True)
    head = models.ForeignKey(
        "Employee",
        on_delete=models.SET_NULL,
        verbose_name="Руководитель отдела",
        related_name="headed_departments",
        null=True,
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Отдел"
        verbose_name_plural = "Отделы"

    def __str__(self):
        return self.name

    @property
    def active_employees(self):
        """
        Все активные сотрудники отдела (через EmployeeDepartment),
        включая руководителя, если он есть.
        """
        qs = self.employeedepartment.filter(is_active=True).select_related("employee")
        employees = [ed.employee for ed in qs]

        if self.head and self.head not in employees:
            employees.append(self.head)

        return employees

    @property
    def new_employees(self):
        """
        Новые сотрудники отдела за последний месяц (по дате присоединения).
        """
        month_ago = timezone.now() - timezone.timedelta(days=30)
        qs = self.employeedepartment.filter(
            is_active=True, date_from__gte=month_ago
        ).select_related("employee")

        employees = [ed.employee for ed in qs]

        # Добавляем руководителя, если он недавно назначен
        if self.head:
            head_joined = self.created_at >= month_ago
            if head_joined and self.head not in employees:
                employees.append(self.head)

        return employees


class EmployeeDepartment(models.Model):
    employee = models.ForeignKey(
        "Employee", on_delete=models.CASCADE, related_name="departments_links"
    )
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="employeedepartment"
    )
    role = models.CharField("Роль в отделе", max_length=100, blank=True)
    date_from = models.DateField("Дата начала работы", null=True, blank=True)
    date_to = models.DateField("Дата окончания работы", null=True, blank=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        unique_together = ("employee", "department", "date_from")
        verbose_name = "Принадлежность к отделу"
        verbose_name_plural = "Принадлежности к отделам"

    def __str__(self):
        return f"{self.employee} в {self.department} ({self.role or 'сотрудник'})"


class EmployeePosition(models.Model):
    """
    Опциональная модель для хранения названия должности.
    Не влияет на определение, в каком отделе сотрудник работает.
    """

    employee = models.ForeignKey(
        "Employee", on_delete=models.CASCADE, related_name="positions"
    )
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="positions"
    )
    title = models.CharField("Название должности", max_length=255)
    date_from = models.DateField("Дата начала должности")
    date_to = models.DateField("Дата окончания должности", null=True, blank=True)

    class Meta:
        verbose_name = "Должность сотрудника"
        verbose_name_plural = "Должности сотрудников"

    @property
    def is_active(self):
        return not self.date_to or self.date_to >= timezone.now().date()

    def __str__(self):
        return f"{self.employee} — {self.title} ({self.department})"


class Absence(models.Model):
    ABSENCE_TYPE_CHOICES = [
        ("vacation", "Отпуск"),
        ("sick_leave", "Больничный"),
        ("other", "Другое"),
    ]

    STATUS_CHOICES = [
        ("pending", "На рассмотрении"),
        ("approved", "Утверждено"),
        ("rejected", "Отклонено"),
    ]

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="absences"
    )
    type = models.CharField(
        "Тип отсутствия", choices=ABSENCE_TYPE_CHOICES, max_length=32
    )
    date_from = models.DateField("Дата начала")
    date_to = models.DateField("Дата окончания")
    comment = models.TextField("Комментарий", blank=True)
    status = models.CharField(
        "Статус", choices=STATUS_CHOICES, max_length=16, default="pending"
    )

    class Meta:
        verbose_name = "Отсутствие сотрудника"
        verbose_name_plural = "Отсутствия сотрудников"

    def __str__(self):
        return f"{self.employee} — {self.get_type_display()} ({self.date_from}–{self.date_to})"


class Skill(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Навык"
        verbose_name_plural = "Навыки"

    def __str__(self):
        return self.name


class Education(models.Model):
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name="educations"
    )
    institution = models.CharField(max_length=255)
    degree = models.CharField(max_length=100)
    graduation_year = models.IntegerField()

    class Meta:
        verbose_name = "Образование"
        verbose_name_plural = "Образование"

    def __str__(self):
        return f"{self.institution} ({self.degree}, {self.graduation_year})"
