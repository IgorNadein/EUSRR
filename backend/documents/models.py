# documents/models.py
"""
Модели для управления документами с использованием django-filer.

Основные модели:
- Document: Документ с поддержкой filer для профессионального управления файлами
- DocumentAcknowledgement: Запись об ознакомлении сотрудника с документом
"""

from django.db import models
from django.utils.translation import gettext_lazy as _
from django.conf import settings
from django.utils import timezone
from filer.fields.file import FilerFileField
import reversion

User = settings.AUTH_USER_MODEL  # 'employees.Employee'


@reversion.register()  # Включаем версионирование для документов
class Document(models.Model):
    """
    Документ с использованием django-filer для управления файлами.
    
    Преимущества:
    - Поддержка папок и вложенной структуры
    - Автоматическая генерация thumbnails для изображений и PDF
    - Полнотекстовый поиск по содержимому файлов
    - Информация о размере, MIME-типе, метаданные
    - История версий через django-reversion
    """
    title = models.CharField(_('Название'), max_length=255)
    
    # Используем FilerFileField вместо FileField
    file = FilerFileField(
        verbose_name=_('Файл'),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='documents',
        help_text=_('Файл, загруженный через django-filer')
    )
    
    description = models.TextField(_('Описание'), blank=True)

    uploaded_by = models.ForeignKey(
        User,
        verbose_name=_('Загрузил'),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_documents'
    )
    uploaded_at = models.DateTimeField(_('Дата загрузки'), auto_now_add=True)

    # Логика распространения документов
    sent_to_all = models.BooleanField(
        _('Разослать всем'),
        default=True,
        help_text=_('Если включено — уведомление получат все активные сотрудники')
    )
    departments = models.ManyToManyField(
        'employees.Department',
        verbose_name=_('Отделы-получатели'),
        blank=True,
        help_text=_('Документ будет доступен всем сотрудникам выбранных отделов (включая будущих)'),
        related_name='documents'
    )
    recipients = models.ManyToManyField(
        User,
        verbose_name=_('Получатели'),
        blank=True,
        help_text=_('Если `Разослать всем` отключено, документ пойдет только этим'),
        related_name='document_recipients'
    )

    class Meta:
        verbose_name = _('Документ')
        verbose_name_plural = _('Документы')
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.title

    @property
    def file_size(self):
        """Размер файла в байтах (берется из filer)"""
        if self.file:
            return self.file.size
        return 0

    @property
    def file_extension(self):
        """Расширение файла"""
        if self.file:
            return self.file.extension
        return ''

    def get_thumbnail(self, size='medium'):
        """
        Получить thumbnail для файла (работает для изображений и PDF).
        
        Args:
            size: 'small' (200x200), 'medium' (400x400), 'large' (800x800)
        
        Returns:
            URL thumbnail или None
        """
        if not self.file:
            return None
        
        try:
            from easy_thumbnails.files import get_thumbnailer
            thumbnailer = get_thumbnailer(self.file)
            thumbnail = thumbnailer[size]
            return thumbnail.url
        except Exception:
            # Если thumbnail не удалось создать (не изображение), возвращаем иконку по типу
            return self.file.url


@reversion.register()
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


