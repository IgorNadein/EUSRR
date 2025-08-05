
# backend\employees\models.py
from django.db import models
from django.contrib.auth.models import AbstractUser, BaseUserManager
from phonenumber_field.modelfields import PhoneNumberField
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .constants import GENDER_CHOICES, ACTION_CHOICES, ACTION_DISMISSED


class EmployeeManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone_number, email, password=None, **extra_fields):
        if not phone_number:
            raise ValueError(_('Пользователь должен иметь номер телефона'))
        if not email:
            raise ValueError(_('Пользователь должен иметь email'))
        email = self.normalize_email(email)
        user = self.model(phone_number=phone_number,
                          email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone_number, email, password=None, **extra_fields):
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)
        if not extra_fields.get('is_staff'):
            raise ValueError(_('Суперпользователь должен иметь is_staff=True'))
        if not extra_fields.get('is_superuser'):
            raise ValueError(
                _('Суперпользователь должен иметь is_superuser=True'))
        return self.create_user(phone_number, email, password, **extra_fields)


class Employee(AbstractUser):
    # Отключаем username
    username = None

    gender = models.PositiveSmallIntegerField(
        _('Пол'), choices=GENDER_CHOICES, default=0, blank=True)
    avatar = models.ImageField(
        # Теперь необязательное
        _('Фото'), upload_to='users/avatars', blank=True, null=True)
    phone_number = PhoneNumberField(
        _('Номер телефона'), max_length=100, unique=True)
    patronymic = models.CharField(_('Отчество'), max_length=100, blank=True)
    birth_date = models.DateField(_('Дата рождения'), blank=True, null=True)
    email = models.EmailField(_('email address'), unique=True)
    telegram = models.CharField('Telegram', max_length=100, blank=True)
    whatsapp = PhoneNumberField('WhatsApp', blank=True)
    wechat = PhoneNumberField('WeChat', blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    skills = models.ManyToManyField(
        'Skill', related_name='employees', blank=True)

    objects = EmployeeManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'email']

    class Meta:
        verbose_name = 'Сотрудник'
        verbose_name_plural = 'Сотрудники'
        ordering = ('last_name', 'first_name')
        indexes = [
            models.Index(fields=['last_name', 'first_name']),
            models.Index(fields=['email']),
            models.Index(fields=['phone_number']),
        ]

    def clean(self):
        super().clean()
        if not (self.whatsapp or self.telegram or self.wechat):
            raise ValidationError(
                'Заполните хотя бы одно из полей: WhatsApp, WeChat или Telegram',
                code='contact_required'
            )

    def __str__(self):
        return f'{self.last_name} {self.first_name}'
    
    @classmethod
    def get_active(cls):
        qs = cls.objects.prefetch_related('actions').order_by('-created_at')
        return [e for e in qs if e.is_actually_active]

    @property
    def employment_status(self):
        last_action = self.actions.order_by('-date').first()
        if last_action:
            return last_action.get_action_display()
        return 'Нет данных'

    @property
    def is_actually_active(self):
        last_action = self.actions.order_by('-date').first()
        if not last_action:
            return False
        return last_action.action != ACTION_DISMISSED


class EmployeeAction(models.Model):

    employee = models.ForeignKey(
        Employee, related_name='actions', on_delete=models.CASCADE)
    action = models.CharField(_('Кадровое событие'),
                              max_length=32, choices=ACTION_CHOICES)
    date = models.DateTimeField(_('Дата действия'))
    comment = models.TextField(_('Комментарий/причина'), blank=True)
    extra = models.JSONField(_('Дополнительно'), blank=True, null=True)

    class Meta:
        verbose_name = _('Кадровое событие')
        verbose_name_plural = _('Кадровые события')
        ordering = ['-date']

    def __str__(self):
        return f'{self.employee} — {self.get_action_display()} — {self.date:%d.%m.%Y}'


class Department(models.Model):
    name = models.CharField('Название отдела', max_length=255, unique=True)
    description = models.TextField('Описание', blank=True)
    head = models.ForeignKey(
        Employee, on_delete=models.SET_NULL,
        verbose_name='Руководитель отдела',
        related_name='headed_departments',
        null=True, blank=True
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = 'Отдел'
        verbose_name_plural = 'Отделы'

    def __str__(self):
        return self.name


class EmployeePosition(models.Model):
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='positions')
    department = models.ForeignKey(
        Department, on_delete=models.CASCADE, related_name='employees')
    title = models.CharField('Название должности', max_length=255)
    date_from = models.DateField('Дата начала должности')
    date_to = models.DateField(
        'Дата окончания должности', null=True, blank=True)

    class Meta:
        verbose_name = 'Должность сотрудника'
        verbose_name_plural = 'Должности сотрудников'

    @property
    def is_active(self):
        return not self.date_to or self.date_to >= timezone.now().date()

    def __str__(self):
        return f"{self.employee} — {self.title} ({self.department})"


class Absence(models.Model):
    ABSENCE_TYPE_CHOICES = [
        ('vacation', 'Отпуск'),
        ('sick_leave', 'Больничный'),
        ('other', 'Другое'),
    ]

    STATUS_CHOICES = [
        ('pending', 'На рассмотрении'),
        ('approved', 'Утверждено'),
        ('rejected', 'Отклонено'),
    ]

    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='absences')
    type = models.CharField(
        'Тип отсутствия', choices=ABSENCE_TYPE_CHOICES, max_length=32)
    date_from = models.DateField('Дата начала')
    date_to = models.DateField('Дата окончания')
    comment = models.TextField('Комментарий', blank=True)
    status = models.CharField(
        'Статус', choices=STATUS_CHOICES, max_length=16, default='pending')

    class Meta:
        verbose_name = 'Отсутствие сотрудника'
        verbose_name_plural = 'Отсутствия сотрудников'

    def __str__(self):
        return f'{self.employee} — {self.get_type_display()} ({self.date_from}–{self.date_to})'


class Skill(models.Model):
    name = models.CharField(max_length=100, unique=True)

    class Meta:
        verbose_name = 'Навык'
        verbose_name_plural = 'Навыки'

    def __str__(self):
        return self.name


class Education(models.Model):
    employee = models.ForeignKey(
        Employee, on_delete=models.CASCADE, related_name='educations')
    institution = models.CharField(max_length=255)
    degree = models.CharField(max_length=100)
    graduation_year = models.IntegerField()

    class Meta:
        verbose_name = 'Образование'
        verbose_name_plural = 'Образование'

    def __str__(self):
        return f'{self.institution} ({self.degree}, {self.graduation_year})'
