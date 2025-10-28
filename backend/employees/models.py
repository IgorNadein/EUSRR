# backend\employees\models.py
from common.emails import send_templated_mail
from django.contrib.auth.models import AbstractUser, BaseUserManager, Group, Permission
from django.core.exceptions import ValidationError
from django.db import IntegrityError, models, transaction
from django.db.models.functions import Lower
from django.utils import timezone
from django.utils.crypto import get_random_string
from phonenumber_field.modelfields import PhoneNumberField
from simple_history.models import HistoricalRecords

from .constants import ACTION_CHOICES, ACTION_DISMISSED, GENDER_CHOICES, DeptPerm


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
            raise ValidationError(
                {"email": "Пользователь с таким email уже существует"}
            )
        if self.model.objects.filter(phone_number=phone_number).exists():
            raise ValidationError(
                {"phone_number": "Пользователь с таким номером уже существует"}
            )

        try:
            with transaction.atomic():
                user = self.model(
                    email=email, phone_number=phone_number, **extra_fields
                )
                user.set_password(password)
                # для обычного пользователя подтверждение по email
                user.email_verified = False
                user.email_activation_code = get_random_string(
                    6, allowed_chars="0123456789"
                )
                user.save(using=self._db)
        except IntegrityError as e:
            # fallback — на случай гонки: маппим в поле-специфичную ошибку
            msg = str(e).lower()
            if "email" in msg or "uniq" in msg and "email" in msg:
                raise ValidationError(
                    {"email": "Пользователь с таким email уже существует"}
                )
            if "phone" in msg or "phone_number" in msg:
                raise ValidationError(
                    {"phone_number": "Пользователь с таким номером уже существует"}
                )
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
        extra_fields.setdefault("email_verified", True)

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
    ldap_group_dn = models.CharField(
        "DN агрегаторной группы должности в AD (POS_*)",
        max_length=512,
        blank=True,
        default="",
        help_text="Напр.: CN=POS_engineer,OU=Position,OU=company,DC=robotail,DC=local",
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Должность"
        verbose_name_plural = "Должности"
        ordering = ["name"]
        permissions = [
            (
                "assign_position_groups",
                "Может назначать группы аутентификации для должностей",
            ),
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

    is_ldap_managed = models.BooleanField("Управляется LDAP", default=False)

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
        permissions = [
            ("manage_employee_skills", "Может управлять навыками сотрудников"),
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

    def mark_ldap_managed(self, guid: str, dn: str | None = None) -> None:
        if not guid:
            raise ValueError("ldap_guid обязателен")
        self.is_ldap_managed = True
        if hasattr(self, "set_unusable_password"):
            self.set_unusable_password()
        self.save(update_fields=["is_ldap_managed", "password"])

        st, _ = LdapSyncState.objects.get_or_create(
            model="employee", object_pk=str(self.pk)
        )
        st.touch(ldap_guid=guid, ldap_dn=dn, sync_dir="ldap")


class EmployeeAction(models.Model):
    employee = models.ForeignKey(
        Employee, related_name="actions", on_delete=models.CASCADE
    )
    action = models.CharField("Кадровое событие", max_length=50, choices=ACTION_CHOICES)
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

    ldap_group_dn = models.CharField(
        "DN агрегаторной группы отдела в AD (DEP_*)",
        max_length=512,
        blank=True,
        default="",
        help_text="Напр.: CN=DEP_it,OU=Department,OU=company,DC=robotail,DC=local",
    )

    class Meta:
        verbose_name = "Отдел"
        verbose_name_plural = "Отделы"
        permissions = [
            ("change_department_head", "Может изменять руководителя отдела"),
            ("assign_department_role", "Может назначать роли в рамках отдела"),
            ("manage_department", "Может управлять отделом"),
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
            self.head_appointed_at = timezone.now()

        super().save(*args, **kwargs)

        if self.head_id:
            try:
                link, created = EmployeeDepartment.objects.get_or_create(
                    employee_id=self.head_id,
                    department_id=self.pk,
                    defaults={
                        "is_active": True,
                        "date_from": timezone.now().date(),
                    },
                )
                updates = {}
                if not link.is_active:
                    updates["is_active"] = True
                if not link.date_from:
                    updates["date_from"] = timezone.now().date()
                if updates:
                    EmployeeDepartment.objects.filter(pk=link.pk).update(**updates)
            except IntegrityError:
                # На случай гонки
                EmployeeDepartment.objects.filter(
                    employee_id=self.head_id, department_id=self.pk
                ).update(is_active=True, date_from=timezone.now().date())

        # --- Обрабатываем бывшего руководителя ---
        if (not is_create) and head_changed and old_head_id:
            if self.head_id is None:
                # Руководителя сняли: деактивируем его принадлежность
                link, created = EmployeeDepartment.objects.get_or_create(
                    employee_id=old_head_id,
                    department_id=self.pk,
                    defaults={
                        "is_active": True,
                        "date_from": timezone.now().date(),
                        "date_to": timezone.now().date(),
                    },
                )
                if not created:
                    EmployeeDepartment.objects.filter(
                        employee_id=old_head_id, department_id=self.pk
                    ).update(is_active=True, date_to=timezone.now().date())
            else:
                # Смена A -> B: по текущей логике бывший остаётся сотрудником отдела (активным)
                # Если хотите наоборот — поменяйте is_active=True на False и добавьте date_to.
                EmployeeDepartment.objects.get_or_create(
                    employee_id=old_head_id,
                    department_id=self.pk,
                    defaults={
                        "is_active": True,
                        "date_from": timezone.now().date(),
                    },
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


class DepartmentPermission(models.Model):
    code = models.CharField(max_length=64, choices=DeptPerm.CHOICES, unique=True)
    name = models.CharField(max_length=150)

    def __str__(self):
        return self.name or self.code


class DepartmentRole(models.Model):
    """Роль внутри КОНКРЕТНОГО отдела, с правами, заданными начальником отдела."""

    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name="roles"
    )
    name = models.CharField(max_length=150)
    scoped_permissions = models.ManyToManyField(
        DepartmentPermission, blank=True, related_name="roles"
    )
    ldap_group_dn = models.CharField(
        "DN агрегаторной группы роли в AD (ROLE_*)",
        max_length=512,
        blank=True,
        default="",
        help_text="Напр.: CN=ROLE_it__oncall,OU=Role,OU=company,DC=robotail,DC=local",
    )

    class Meta:
        verbose_name = "Роль в отделе"
        verbose_name_plural = "Роли в отделе"
        unique_together = ("department", "name")
        ordering = ("name", "department", "id")

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
                fields=["department_id", "employee_id"],
                name="uniq_employee_per_department",
                deferrable=models.Deferrable.DEFERRED,
            ),
        ]
        indexes = [
            models.Index(fields=["department_id", "is_active", "employee_id"]),
            models.Index(fields=["employee_id", "department_id"]),
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


# --- LDAP sync state -------------------------------------------------


class LdapSyncState(models.Model):
    """Единое состояние синхронизации LDAP для любых объектов.

    Attributes:
        model (str): Имя модели в Django ('employee','department','group','dept_role','position').
        object_pk (str): Первичный ключ объекта (строкой, чтобы покрыть UUID/INT).
        ldap_dn (str): Последний известный DN в LDAP.
        ldap_guid (str | None): GUID из LDAP (objectGUID/entryUUID), если применимо.
        last_ldap_modify_ts (datetime | None): Последний modifyTimestamp/whenChanged из LDAP.
        last_django_modify_ts (datetime | None): Последний updated_at из Django на момент фиксации.
        last_sync_dir (str): 'ldap'|'django'|'auto' — направление последнего успешного синка.
        data_hash (str | None): Хэш значимых полей (опционально) для ускоренной детекции изменений.
        updated_at (datetime): Время обновления записи состояния.

    Raises:
        ValueError: При неверных значениях полей валидации (на уровне БД доп. ограничений нет).
    """

    model = models.CharField(max_length=32, db_index=True)
    object_pk = models.CharField(max_length=64, db_index=True)

    ldap_dn = models.TextField(blank=True, default="")
    ldap_guid = models.CharField(max_length=64, null=True, blank=True, db_index=True)

    last_ldap_modify_ts = models.DateTimeField(null=True, blank=True)
    last_django_modify_ts = models.DateTimeField(null=True, blank=True)

    last_sync_dir = models.CharField(max_length=8, default="ldap")
    data_hash = models.CharField(max_length=64, null=True, blank=True)

    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = "Состояние синхронизации LDAP"
        verbose_name_plural = "Состояния синхронизации LDAP"
        unique_together = (("model", "object_pk"),)

    def touch(
        self,
        *,
        ldap_dn: str | None = None,
        ldap_guid: str | None = None,
        last_ldap_modify_ts=None,
        last_django_modify_ts=None,
        sync_dir: str | None = None,
        data_hash: str | None = None,
    ) -> None:
        """Обновляет поля состояния для записи.

        Args:
            ldap_dn (str | None): Новый DN.
            ldap_guid (str | None): Новый GUID.
            last_ldap_modify_ts: Новый штамп LDAP (UTC).
            last_django_modify_ts: Новый штамп Django (UTC).
            sync_dir (str | None): Направление ('ldap'|'django'|'auto').
            data_hash (str | None): Хэш полезных данных.

        Raises:
            ValueError: Если sync_dir не из допустимого набора.
        """
        if sync_dir and sync_dir not in ("ldap", "django", "auto"):
            raise ValueError("sync_dir должен быть 'ldap'|'django'|'auto'")
        if ldap_dn is not None:
            self.ldap_dn = ldap_dn
        if ldap_guid is not None:
            self.ldap_guid = ldap_guid
        if last_ldap_modify_ts is not None:
            self.last_ldap_modify_ts = last_ldap_modify_ts
        if last_django_modify_ts is not None:
            self.last_django_modify_ts = last_django_modify_ts
        if sync_dir:
            self.last_sync_dir = sync_dir
        if data_hash is not None:
            self.data_hash = data_hash
        self.updated_at = timezone.now()
        self.save(
            update_fields=[
                "ldap_dn",
                "ldap_guid",
                "last_ldap_modify_ts",
                "last_django_modify_ts",
                "last_sync_dir",
                "data_hash",
                "updated_at",
            ]
        )
