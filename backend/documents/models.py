# documents/models.py

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.utils import timezone

User = settings.AUTH_USER_MODEL  # 'users.Employee'


class Document(models.Model):
    """
    Документ, который нужно разослать сотрудникам.
    """
    title = models.CharField(_('Название'), max_length=255)
    file = models.FileField(_('Файл'), upload_to='documents/%Y/%m/%d/')
    description = models.TextField(_('Описание'), blank=True)

    uploaded_by = models.ForeignKey(
        User,
        verbose_name=_('Загрузил'),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_documents'  # <-- уникальный related_name
    )
    uploaded_at = models.DateTimeField(_('Дата загрузки'), auto_now_add=True)

    sent_to_all = models.BooleanField(
        _('Разослать всем'),
        default=False,
        help_text=_('Если включено — уведомление получат все активные сотрудники')
    )
    recipients = models.ManyToManyField(
        User,
        verbose_name=_('Получатели'),
        blank=True,
        help_text=_('Если `Разослать всем` отключено, документ пойдет только этим'),
        related_name='document_recipients'  # <-- уникальный related_name
    )

    class Meta:
        verbose_name = _('Документ')
        verbose_name_plural = _('Документы')
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.title


class DocumentAcknowledgement(models.Model):
    """
    Фиксация, что сотрудник ознакомился с документом.
    """
    document = models.ForeignKey(
        Document,
        verbose_name=_('Документ'),
        on_delete=models.CASCADE,
        related_name='acknowledgements'
    )
    user = models.ForeignKey(
        User,
        verbose_name=_('Сотрудник'),
        on_delete=models.CASCADE,
        related_name='document_acknowledgements'
    )
    acknowledged_at = models.DateTimeField(_('Время ознакомления'), auto_now_add=True)

    class Meta:
        verbose_name = _('Ознакомление с документом')
        verbose_name_plural = _('Ознакомления с документами')
        unique_together = ('document', 'user')
        ordering = ['-acknowledged_at']

    def __str__(self):
        return f'{self.user} — {self.document} @ {self.acknowledged_at:%d.%m.%Y %H:%M}'
