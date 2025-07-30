from django.db import models
from django.contrib.auth.models import AbstractUser
from django.contrib.auth.base_user import BaseUserManager
from phonenumber_field.modelfields import PhoneNumberField
from django.core.exceptions import ValidationError
from django.utils.translation import gettext_lazy as _
from django.utils import timezone
from .constants import GENDER_CHOICES


class EmployeeManager(BaseUserManager):
    use_in_migrations = True

    def create_user(self, phone_number, email, password=None, **extra_fields):
        """
        Создает и сохраняет обычного сотрудника с переданным номером телефона и email.
        """
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
        """
        Создает и сохраняет суперпользователя.
        """
        extra_fields.setdefault('is_staff', True)
        extra_fields.setdefault('is_superuser', True)
        extra_fields.setdefault('is_active', True)

        if extra_fields.get('is_staff') is not True:
            raise ValueError(_('Суперпользователь должен иметь is_staff=True'))
        if extra_fields.get('is_superuser') is not True:
            raise ValueError(
                _('Суперпользователь должен иметь is_superuser=True'))

        return self.create_user(phone_number, email, password, **extra_fields)


class Employee(AbstractUser):
    gender = models.PositiveSmallIntegerField(
        _('Пол'), choices=GENDER_CHOICES, default=0)
    avatar = models.ImageField(_('Фото'), upload_to='users/avatars')
    phone_number = PhoneNumberField(
        'Номер телефона', max_length=100, unique=True, blank=False)
    patronymic = models.CharField(_('Отчество'), max_length=100, blank=True)
    birth_date = models.DateField(_('Дата рождения'), blank=True, null=True)
    position = models.CharField(_('Должность'), max_length=255)
    email = models.EmailField(_('email address'), unique=True, blank=False)
    telegram = models.CharField(
        'Telegram', max_length=100, blank=True)
    whatsapp = PhoneNumberField('WhatsApp', blank=True)
    username = None
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = EmployeeManager()

    USERNAME_FIELD = 'phone_number'
    REQUIRED_FIELDS = ['first_name', 'last_name', 'email']

    class Meta:
        verbose_name = 'Сотрудник'
        verbose_name_plural = 'Сотрудники'
        ordering = ('last_name', 'first_name')

    def clean(self):
        super().clean()
        if not self.whatsapp and not self.telegram:
            raise ValidationError(
                'Заполните хотя бы одно из полей: WhatsApp или Telegram',
                code='contact_required'
            )

    def __str__(self):
        return f'{self.last_name} {self.first_name}'

    @property
    def employment_status(self):
        """Текущий статус сотрудника (последнее кадровое событие)"""
        last_action = self.actions.order_by('-date').first()
        if last_action:
            return last_action.get_action_display()
        return 'Нет данных'

    @property
    def is_actually_active(self):
        """Сотрудник считается работающим по последнему действию"""
        last_action = self.actions.order_by('-date').first()
        if not last_action:
            return False
        return last_action.action in [
            EmployeeAction.ACTION_HIRED,
            EmployeeAction.ACTION_REHIRED,
            EmployeeAction.ACTION_RETURNED_FROM_LEAVE,
            EmployeeAction.ACTION_RETURNED_FROM_MATERNITY,
            EmployeeAction.ACTION_TRANSFERRED,
        ]


class EmployeeAction(models.Model):
    ACTION_HIRED = 'hired'
    ACTION_DISMISSED = 'dismissed'
    ACTION_ON_LEAVE = 'on_leave'
    ACTION_RETURNED_FROM_LEAVE = 'returned_from_leave'
    ACTION_ON_MATERNITY = 'on_maternity'
    ACTION_RETURNED_FROM_MATERNITY = 'returned_from_maternity'
    ACTION_TRANSFERRED = 'transferred'
    ACTION_REHIRED = 'rehired'

    ACTION_CHOICES = [
        (ACTION_HIRED, 'Принят'),
        (ACTION_DISMISSED, 'Уволен'),
        (ACTION_ON_LEAVE, 'В отпуске'),
        (ACTION_RETURNED_FROM_LEAVE, 'Вернулся из отпуска'),
        (ACTION_ON_MATERNITY, 'В декрете'),
        (ACTION_RETURNED_FROM_MATERNITY, 'Вернулся из декрета'),
        (ACTION_TRANSFERRED, 'Переведен'),
        (ACTION_REHIRED, 'Восстановлен'),
    ]

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
