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
    
    # Папка для организации документов (иерархическая структура)
    folder = models.ForeignKey(
        'filer.Folder',
        verbose_name=_('Папка'),
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='documents',
        help_text=_('Папка для организации документов в иерархической структуре')
    )
    
    description = models.TextField(_('Описание'), blank=True)
    
    # Full-text search - извлеченный текст (OCR или парсинг PDF/DOCX)
    extracted_text = models.TextField(
        _('Извлеченный текст'),
        blank=True,
        editable=False,
        help_text=_('Текст извлечен из файла для полнотекстового поиска')
    )
    
    # Audit trail
    uploaded_by = models.ForeignKey(
        User,
        verbose_name=_('Загрузил'),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='uploaded_documents'
    )
    uploaded_at = models.DateTimeField(_('Дата загрузки'), auto_now_add=True)
    
    modified_by = models.ForeignKey(
        User,
        verbose_name=_('Последнее изменение'),
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='modified_documents'
    )
    modified_at = models.DateTimeField(_('Дата изменения'), auto_now=True)

    # Логика распространения документов
    sent_to_all = models.BooleanField(
        _('Разослать всем'),
        default=True,
        help_text=_('Если включено — уведомление получат все активные сотрудники')
    )
    
    # Требование ознакомления
    acknowledgement_required = models.BooleanField(
        _('Требуется ознакомление'),
        default=False,
        help_text=_('Если включено — сотрудники должны подтвердить ознакомление')
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
    
    # Связанные документы
    related_documents = models.ManyToManyField(
        'self',
        verbose_name=_('Связанные документы'),
        blank=True,
        symmetrical=True,
        help_text=_('Документы, связанные с этим')
    )

    # -------------------------------------------------------------------------
    # ПУБЛИКАЦИЯ ДОКУМЕНТА
    # -------------------------------------------------------------------------

    class Meta:
        verbose_name = _('Документ')
        verbose_name_plural = _('Документы')
        ordering = ['-uploaded_at']

    def __str__(self):
        return self.title

    @property
    def created_by(self):
        """Алиас для uploaded_by (кто создал документ)."""
        return self.uploaded_by

    @property
    def created_at(self):
        """Алиас для uploaded_at (когда создан документ)."""
        return self.uploaded_at

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
    
    @property
    def folder_path(self):
        """
        Полный путь папки документа (breadcrumbs).
        
        Returns:
            str: Путь вида "Корень / Папка1 / Папка2" или пустая строка
        """
        if not self.folder:
            return ''
        
        # Собираем путь от корня до текущей папки
        path_parts = []
        current = self.folder
        while current:
            path_parts.insert(0, current.name)
            current = current.parent
        
        return ' / '.join(path_parts)
    
    def get_folder_hierarchy(self):
        """
        Получить иерархию папок от корня до текущей.
        
        Returns:
            list: Список словарей [{id, name}, ...] от корня к текущей папке
        """
        if not self.folder:
            return []
        
        hierarchy = []
        current = self.folder
        while current:
            hierarchy.insert(0, {'id': current.id, 'name': current.name})
            current = current.parent
        
        return hierarchy


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


# ============================================================================
# ТИПЫ ДОКУМЕНТОВ И МЕТАДАННЫЕ
# ============================================================================

class DocumentType(models.Model):
    """
    Типы документов (Договор, Приказ, Акт, Счет и т.д.).
    Определяет структуру метаданных и workflow для документов этого типа.
    """
    name = models.CharField(_('Название'), max_length=100)
    code = models.SlugField(_('Код'), unique=True, max_length=50)
    description = models.TextField(_('Описание'), blank=True)
    
    # JSON Schema для валидации метаданных этого типа
    metadata_schema = models.JSONField(
        _('Схема метаданных'),
        null=True,
        blank=True,
        help_text=_('JSON Schema для валидации метаданных документов этого типа')
    )
    
    # Иконка для UI
    icon = models.CharField(
        _('Иконка'),
        max_length=50,
        default='file-earmark-text',
        help_text=_('Bootstrap Icons класс')
    )
    
    # Цвет для UI
    color = models.CharField(
        _('Цвет'),
        max_length=7,
        default='#0d6efd',
        help_text=_('HEX цвет для UI')
    )
    
    is_active = models.BooleanField(_('Активен'), default=True)
    order = models.IntegerField(_('Порядок'), default=0)
    
    class Meta:
        verbose_name = _('Тип документа')
        verbose_name_plural = _('Типы документов')
        ordering = ['order', 'name']
        
    def __str__(self):
        return self.name


class DocumentMetadata(models.Model):
    """
    Динамические метаданные документа (key-value пары).
    Позволяет добавлять произвольные поля к документам.
    """
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='metadata_entries',
        verbose_name=_('Документ')
    )
    key = models.CharField(_('Ключ'), max_length=100)
    value = models.TextField(_('Значение'))
    
    # Тип значения для правильного отображения и валидации
    class ValueType(models.TextChoices):
        TEXT = 'text', _('Текст')
        NUMBER = 'number', _('Число')
        DATE = 'date', _('Дата')
        BOOLEAN = 'boolean', _('Да/Нет')
        URL = 'url', _('Ссылка')
    
    value_type = models.CharField(
        _('Тип значения'),
        max_length=20,
        choices=ValueType.choices,
        default=ValueType.TEXT
    )
    
    class Meta:
        verbose_name = _('Метаданные документа')
        verbose_name_plural = _('Метаданные документов')
        unique_together = ('document', 'key')
        ordering = ['key']
        
    def __str__(self):
        return f'{self.key}: {self.value}'


class DocumentTag(models.Model):
    """
    Теги для категоризации документов.
    Аналог Mayan EDMS tags.
    """
    name = models.CharField(_('Название'), max_length=100, unique=True)
    slug = models.SlugField(_('Слаг'), unique=True)
    color = models.CharField(
        _('Цвет'),
        max_length=7,
        default='#0d6efd',
        help_text=_('HEX цвет для UI')
    )
    description = models.TextField(_('Описание'), blank=True)
    
    documents = models.ManyToManyField(
        Document,
        related_name='tags',
        blank=True,
        verbose_name=_('Документы')
    )
    
    created_at = models.DateTimeField(_('Создан'), auto_now_add=True)
    
    class Meta:
        verbose_name = _('Тег')
        verbose_name_plural = _('Теги')
        ordering = ['name']
        
    def __str__(self):
        return self.name


class Cabinet(models.Model):
    """
    Кабинеты - виртуальные хранилища документов.
    Аналог Mayan EDMS cabinets. Позволяет организовать документы
    в виртуальные коллекции независимо от физической структуры папок.
    """
    name = models.CharField(_('Название'), max_length=200)
    slug = models.SlugField(_('Слаг'), unique=True)
    description = models.TextField(_('Описание'), blank=True)
    
    # Иерархическая структура кабинетов
    parent = models.ForeignKey(
        'self',
        verbose_name=_('Родительский кабинет'),
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='children'
    )
    
    documents = models.ManyToManyField(
        Document,
        related_name='cabinets',
        blank=True,
        verbose_name=_('Документы')
    )
    
    # Иконка и цвет для UI
    icon = models.CharField(
        _('Иконка'),
        max_length=50,
        default='folder',
        help_text=_('Bootstrap Icons класс')
    )
    color = models.CharField(
        _('Цвет'),
        max_length=7,
        default='#6c757d',
        help_text=_('HEX цвет для UI')
    )
    
    created_by = models.ForeignKey(
        User,
        verbose_name=_('Создал'),
        on_delete=models.SET_NULL,
        null=True,
        related_name='created_cabinets'
    )
    created_at = models.DateTimeField(_('Создан'), auto_now_add=True)
    
    order = models.IntegerField(_('Порядок'), default=0)
    
    class Meta:
        verbose_name = _('Кабинет')
        verbose_name_plural = _('Кабинеты')
        ordering = ['order', 'name']
        
    def __str__(self):
        if self.parent:
            return f'{self.parent.name} / {self.name}'
        return self.name


# ============================================================================
# АУДИТ И ИСТОРИЯ
# ============================================================================

class DocumentAuditLog(models.Model):
    """
    Полный аудит всех действий с документами.
    Фиксирует кто, когда и что сделал с документом.
    """
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='audit_log',
        verbose_name=_('Документ')
    )
    user = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        verbose_name=_('Пользователь')
    )
    
    class Action(models.TextChoices):
        CREATED = 'created', _('Создан')
        VIEWED = 'viewed', _('Просмотрен')
        DOWNLOADED = 'downloaded', _('Скачан')
        EDITED = 'edited', _('Изменен')
        MOVED = 'moved', _('Перемещен')
        DELETED = 'deleted', _('Удален')
        STATUS_CHANGED = 'status_changed', _('Изменен статус')
        PERMISSIONS_CHANGED = 'permissions_changed', _('Изменены права')
        SIGNED = 'signed', _('Подписан')
    
    action = models.CharField(
        _('Действие'),
        max_length=50,
        choices=Action.choices
    )
    timestamp = models.DateTimeField(_('Время'), auto_now_add=True)
    ip_address = models.GenericIPAddressField(
        _('IP адрес'),
        null=True,
        blank=True
    )
    user_agent = models.TextField(_('User Agent'), blank=True)
    
    # Дополнительные данные о действии (JSON)
    metadata = models.JSONField(
        _('Метаданные'),
        null=True,
        blank=True,
        help_text=_('Дополнительная информация о действии')
    )
    
    class Meta:
        verbose_name = _('Запись аудита')
        verbose_name_plural = _('Записи аудита')
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['document', '-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['action', '-timestamp']),
        ]
        
    def __str__(self):
        return f'{self.user} {self.get_action_display()} {self.document} @ {self.timestamp:%d.%m.%Y %H:%M}'


class DocumentComment(models.Model):
    """
    Комментарии к документам.
    Поддерживает вложенные ответы (threading).
    """
    document = models.ForeignKey(
        Document,
        on_delete=models.CASCADE,
        related_name='comments',
        verbose_name=_('Документ')
    )
    author = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name='document_comments',
        verbose_name=_('Автор')
    )
    text = models.TextField(_('Текст комментария'))
    
    # Вложенные ответы
    parent = models.ForeignKey(
        'self',
        verbose_name=_('Родительский комментарий'),
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name='replies'
    )
    
    created_at = models.DateTimeField(_('Создан'), auto_now_add=True)
    updated_at = models.DateTimeField(_('Обновлен'), auto_now=True)
    
    # Редактирование
    is_edited = models.BooleanField(_('Отредактирован'), default=False)
    
    class Meta:
        verbose_name = _('Комментарий к документу')
        verbose_name_plural = _('Комментарии к документам')
        ordering = ['created_at']  # Старые сверху
        indexes = [
            models.Index(fields=['document', 'created_at']),
            models.Index(fields=['author', '-created_at']),
        ]
    
    def __str__(self):
        preview = self.text[:50] + '...' if len(self.text) > 50 else self.text
        return f'{self.author}: {preview}'
    
    @property
    def depth(self):
        """Возвращает уровень вложенности комментария."""
        depth = 0
        current = self.parent
        while current:
            depth += 1
            current = current.parent
        return depth
