# backend\employees\models.py
from django.contrib.auth.models import (AbstractUser, BaseUserManager, Group,
                                        Permission)
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.crypto import get_random_string
from phonenumber_field.modelfields import PhoneNumberField
from simple_history.models import HistoricalRecords

from common.emails import send_templated_mail
from .constants import ACTION_CHOICES, ACTION_DISMISSED, GENDER_CHOICES


class DateRangeMixin(models.Model):
    class Meta:
        abstract = True

    def clean(self):
        super().clean()
        if hasattr(self, "date_from") and hasattr(self, "date_to"):
            if self.date_from and self.date_to and self.date_from >= self.date_to:
                raise ValidationError("Дата начала должна быть раньше даты окончания")


class EmployeeManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, email, password=None, **extra_fields):
        send_activation_email = extra_fields.pop("send_activation_email", True)
        if not email:
            raise ValueError("Пользователь должен иметь email для подтверждения")
        email = self.normalize_email(email).lower()

        phone_number = extra_fields.pop("phone_number", None)
        if not phone_number:
            raise ValueError("Пользователь должен иметь номер телефона")

        # Явные проверки для дружелюбной ошибки + защита от гонок ниже
        if self.model.objects.filter(email__iexact=email).exists():
            raise ValidationError({"email": "Пользователь с таким email уже существует"})
        if self.model.objects.filter(phone_number=phone_number).exists():
            raise ValidationError({"phone_number": "Пользователь с таким номером уже существует"})

        try:
            with transaction.atomic():
                user = self.model(email=email, phone_number=phone_number, **extra_fields)
                user.set_password(password)
                # для обычного пользователя подтверждение по email
                user.email_verified = False
                user.email_activation_code = get_random_string(6, allowed_chars="0123456789")
                user.save(using=self._db)
        except IntegrityError as e:
            # fallback — на случай гонки: маппим в поле-специфичную ошибку
            msg = str(e).lower()
            if "email" in msg or "uniq" in msg and "email" in msg:
                raise ValidationError({"email": "Пользователь с таким email уже существует"})
            if "phone" in msg or "phone_number" in msg:
                raise ValidationError({"phone_number": "Пользователь с таким номером уже существует"})
            raise

        if send_activation_email:
            send_templated_mail(
                subject="Подтверждение регистрации",
                to=[user.email],
                template_base="emails/registration_verify_code",
                context={"code": user.email_activation_code, "user": user},
            )
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        extra_fields.setdefault("email_verified", True)  # суперюзер уже подтверждён

        if extra_fields.get("is_staff") is not True:
            raise ValueError("Суперпользователь должен иметь is_staff=True")
        if extra_fields.get("is_superuser") is not True:
            raise ValueError("Суперпользователь должен иметь is_superuser=True")

        # для суперпользователя не отправляем код, просто создаём
        user = self.model(
            email=self.normalize_email(email).lower(),
            phone_number=extra_fields.pop("phone_number", None)
            or "+70000000000",  # либо потребуйте явно
            **extra_fields,
        )
        if not user.phone_number:
            raise ValueError("Для суперпользователя также укажите phone_number")
        user.set_password(password)
        user.email_activation_code = None
        user.save(using=self._db)
        return user

    def get_active(self):
        """
        Возвращает list активных сотрудников, оптимизированный: предварительная фильтрация в DB по полям,
        затем Python-фильтр для сложной логики (actions).
        """
        qs = (
            self.get_queryset()
            .filter(email_verified=True, is_active=True)
            .prefetch_related("actions")
            .order_by("-id")
        )
        return [
            e for e in qs if e.is_actually_active
        ]  # Финальный фильтр по actions в Python


class Position(models.Model):
    """
    Справочник должностей. Одну должность могут иметь много сотрудников.
    У каждой должности свой набор групп прав.
    """

    name = models.CharField("Название должности", max_length=255, unique=True)
    description = models.TextField("Описание", blank=True)
    groups = models.ManyToManyField(
        Group, blank=True, related_name="positions", verbose_name="Группы прав"
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Должность"
        verbose_name_plural = "Должности"
        ordering = ["name"]
        permissions = [
            ("assign_position_groups", "Can assign auth groups to positions"),
        ]

    def __str__(self) -> str:
        return self.name


class Employee(AbstractUser):
    username = None

    gender = models.PositiveSmallIntegerField(
        "Пол", choices=GENDER_CHOICES, default=0, blank=True
    )
    avatar = models.ImageField("Фото", upload_to="users/avatars", blank=True, null=True)
    phone_number = PhoneNumberField("Номер телефона", max_length=100, unique=True)
    patronymic = models.CharField("Отчество", max_length=100, blank=True)
    birth_date = models.DateField("Дата рождения", blank=True, null=True)
    position = models.ForeignKey(
        Position,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
        verbose_name="Должность",
    )
    email = models.EmailField("email address", unique=True)
    telegram = models.CharField("Telegram", max_length=100, blank=True)
    whatsapp = PhoneNumberField("WhatsApp", blank=True)
    wechat = models.CharField("WeChat", max_length=100, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    skills = models.ManyToManyField("Skill", related_name="employees", blank=True)
    is_active = models.BooleanField(default=False)
    sms_activation_code = models.CharField(
        max_length=6, blank=True, null=True
    )  # Для будущей SMS-активации в bots (fallback к email)
    email_verified = models.BooleanField("Email подтверждён", default=False)
    email_activation_code = models.CharField(max_length=6, blank=True, null=True)

    objects = EmployeeManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["first_name", "last_name", "phone_number"]

    class Meta:
        verbose_name = "Сотрудник"
        verbose_name_plural = "Сотрудники"
        ordering = ("last_name", "first_name")
        indexes = [
            models.Index(fields=["last_name", "first_name"]),
            models.Index(fields=["email"]),
            models.Index(fields=["phone_number"]),
            models.Index(Lower("email"), name="employee_email_lower_idx"),
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

    @property
    def employment_status(self):
        last_action = self.actions.order_by("-date").first()
        if last_action:
            return last_action.get_action_display()
        return "Нет данных"

    @property
    def departments(self):
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
        if not self.email_verified:
            return False  # Неактивен без подтверждения email
        last_action = self.actions.order_by("-date").first()
        if not last_action:
            return self.is_active
        return last_action.action != ACTION_DISMISSED

    def verify_email(self, code):
        if self.email_activation_code == code:
            self.email_verified = True
            self.email_activation_code = None
            self.is_active = True  # Активируем после подтверждения
            self.save()
            return True
        return False


class EmployeeAction(models.Model):
    employee = models.ForeignKey(
        Employee, related_name="actions", on_delete=models.CASCADE
    )
    action = models.CharField(
        "Кадровое событие", max_length=50, choices=ACTION_CHOICES
    )  # Увеличено для расширения
    date = models.DateTimeField("Дата действия")
    comment = models.TextField("Комментарий/причина", blank=True)
    extra = models.JSONField("Дополнительно", blank=True, null=True)
    history = HistoricalRecords()

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
        Employee,
        on_delete=models.SET_NULL,
        verbose_name="Руководитель отдела",
        related_name="headed_departments",
        null=True,
        blank=True,
    )
    head_appointed_at = models.DateTimeField(
        "Дата назначения руководителя", null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Отдел"
        verbose_name_plural = "Отделы"
        permissions = [
            ("change_department_head", "Can change department head"),
            ("assign_department_role", "Can assign role within department"),
            ("manage_department", "Can manage department"),
        ]

    def __str__(self):
        return self.name

    def save(self, *args, **kwargs):
        old_head_id = None
        is_create = self._state.adding
        if self.pk:
            old_head_id = (
                Department.objects.filter(pk=self.pk)
                .values_list("head_id", flat=True)
                .first()
            )

        head_changed = old_head_id != self.head_id
        if head_changed and self.head_id:
            # фиксируем момент назначения нового руководителя
            self.head_appointed_at = timezone.now()

        super().save(*args, **kwargs)

        if not is_create and head_changed:
            # 1) Новый глава: гарантируем активную ссылку
            if self.head_id:
                try:
                    link, created = EmployeeDepartment.objects.get_or_create(
                        employee_id=self.head_id,
                        department_id=self.pk,
                        defaults={"is_active": True, "date_from": timezone.now().date()},
                    )
                    updated = False
                    if not created and not link.is_active:
                        link.is_active = True
                        updated = True
                    if link.date_from is None:
                        link.date_from = timezone.now().date()
                        updated = True
                    if updated:
                        link.save(update_fields=["is_active", "date_from"])
                except IntegrityError:
                    EmployeeDepartment.objects.filter(
                        employee_id=self.head_id, department_id=self.pk
                    ).update(is_active=True)

            # 2) Старый глава:
            if old_head_id:
                if self.head_id is None:
                    # снимаем главу: если ссылки нет — создадим и сразу деактивируем; если есть — деактивируем
                    link, created = EmployeeDepartment.objects.get_or_create(
                        employee_id=old_head_id,
                        department_id=self.pk,
                        defaults={"is_active": False, "date_from": timezone.now().date(), "date_to": timezone.now().date()},
                    )
                    if not created:
                        EmployeeDepartment.objects.filter(
                            employee_id=old_head_id, department_id=self.pk
                        ).update(is_active=False, date_to=timezone.now().date())
                else:
                    # меняем A -> B: ссылка старого главы должна существовать и оставаться активной
                    EmployeeDepartment.objects.get_or_create(
                        employee_id=old_head_id,
                        department_id=self.pk,
                        defaults={"is_active": True, "date_from": timezone.now().date()},
                    )

    @property
    def active_employees(self):
        """
        Все активные сотрудники отдела (через EmployeeDepartment),
        включая руководителя, если он есть и активен.
        """
        qs = self.employeedepartment.filter(is_active=True).select_related("employee")
        employees = [ed.employee for ed in qs if ed.employee.is_actually_active]

        if self.head and self.head.is_actually_active and self.head not in employees:
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

        employees = [ed.employee for ed in qs if ed.employee.is_actually_active]

        # Добавляем руководителя, если он недавно назначен и активен
        if (
            self.head
            and self.head_appointed_at
            and self.head_appointed_at >= month_ago
            and self.head.is_actually_active
            and self.head not in employees
        ):
            employees.append(self.head)

        return employees


class DepartmentRole(models.Model):
    """Роль внутри КОНКРЕТНОГО отдела, с правами, заданными начальником отдела."""

    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="roles"
    )
    name = models.CharField(max_length=150)
    permissions = models.ManyToManyField(
        Permission, blank=True
    )  # права в рамках ЭТОГО отдела

    class Meta:
        verbose_name = "Роль в отделе"
        verbose_name_plural = "Роли в отделе"
        unique_together = ("department", "name")

    def __str__(self):
        return f"{self.department}: {self.name}"


class EmployeeDepartment(DateRangeMixin, models.Model):
    employee = models.ForeignKey(
        "Employee", on_delete=models.CASCADE, related_name="departments_links"
    )
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="employeedepartment"
    )
    date_from = models.DateField("Дата начала работы", null=True, blank=True)
    date_to = models.DateField("Дата окончания работы", null=True, blank=True)
    is_active = models.BooleanField(default=True)
    role = models.ForeignKey(
        DepartmentRole,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="members",
    )

    class Meta:
        verbose_name = "Принадлежность к отделу"
        verbose_name_plural = "Принадлежности к отделам"
        constraints = [
            models.UniqueConstraint(
                fields=["employee", "department"], name="uniq_employee_department"
            )
        ]
        indexes = [
            models.Index(fields=["department", "is_active"]),
            models.Index(fields=["employee", "is_active"]),
        ]

    def __str__(self):
        role_name = self.role.name if self.role else "сотрудник"
        return f"{self.employee} в {self.department} ({role_name})"


class Skill(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = "Навык"
        verbose_name_plural = "Навыки"

    def __str__(self):
        return self.name
