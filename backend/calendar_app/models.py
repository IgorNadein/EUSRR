# backend\calendar_app\models.py
from django.db import models
from django.urls import reverse
from django.utils.translation import gettext_lazy as _
from django.contrib.auth import get_user_model

User = get_user_model()


class CompanyEvent(models.Model):
    ONE_TIME = 'one_time'
    ANNUAL = 'annual'
    RECURRENCE_CHOICES = [
        (ONE_TIME, _('Одноразовое')),
        (ANNUAL,   _('Ежегодно')),
    ]

    title = models.CharField(_('Название'), max_length=200)
    description = models.TextField(_('Описание'), blank=True)
    date = models.DateField(_('Дата события'))
    recurrence = models.CharField(
        _('Повторение'),
        max_length=20,
        choices=RECURRENCE_CHOICES,
        default=ONE_TIME
    )
    created_by = models.ForeignKey(
        User, verbose_name=_('Создал'),
        on_delete=models.SET_NULL, null=True, blank=True
    )

    class Meta:
        verbose_name = _('Событие компании')
        verbose_name_plural = _('События компании')
        ordering = ['recurrence', 'date']

    def __str__(self):
        return f'{self.title} — {self.date:%d.%m.%Y}'

    def get_absolute_url(self):
        return reverse('calendar:event_detail', args=[self.pk])
