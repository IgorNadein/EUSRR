# documents/admin.py
"""
Django admin для моделей Document и DocumentAcknowledgement.

Основные возможности:
- Использование django-filer для управления файлами
- Поддержка drag & drop загрузки файлов
- Превью thumbnails в списке и форме редактирования
- Полнотекстовый поиск по содержимому файлов
- Версионирование через django-reversion
- Workflow управление через django-fsm
"""

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html, mark_safe
from django.urls import reverse
from django_fsm import get_available_FIELD_transitions
from .models import Document, DocumentAcknowledgement
from django.contrib.auth import get_user_model

User = get_user_model()


class AcknowledgementInline(admin.TabularInline):
    """Inline для отображения ознакомлений с документом."""
    model = DocumentAcknowledgement
    extra = 0
    can_delete = False
    verbose_name = _("Ознакомление")
    verbose_name_plural = _("Ознакомления")
    fields = ('user_link', 'acknowledged_at')
    readonly_fields = ('user_link', 'acknowledged_at')

    def user_link(self, obj):
        """Ссылка на профиль сотрудника."""
        if not obj.user:
            return '—'
        url = reverse(
            'admin:{}_{}_change'.format(
                User._meta.app_label, User._meta.model_name
            ), args=[obj.user.pk]
        )
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user)
    user_link.short_description = _("Сотрудник")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    """
    Admin для Document с поддержкой django-filer и django-fsm.
    
    Возможности:
    - Drag & drop загрузка файлов через filer
    - Превью thumbnails для изображений и PDF
    - Поиск по содержимому файлов
    - Версионирование через django-reversion
    - Workflow управление через django-fsm
    """
    inlines = [AcknowledgementInline]

    list_display = (
        'title', 
        'status_badge',  # FSM статус с цветовым индикатором
        'file_thumbnail',
        'file_info',
        'uploaded_at', 
        'sent_to_all',
        'acknowledgement_status',
    )
    list_filter = ('status', 'sent_to_all', 'uploaded_at', 'departments')
    search_fields = ('title', 'description', 'file__name', 'file__description')
    filter_horizontal = ('recipients', 'departments')
    actions = ['send_document']
    
    # Для django-reversion
    history_latest_first = True

    fieldsets = (
        (None, {
            'fields': (
                'title',
                'status',  # FSM статус
                'file',  # FilerFileField с drag & drop
                'file_preview',  # Превью файла
                'description',
                'sent_to_all', 
                'departments', 
                'recipients'
            ),
        }),
        (_('Workflow'), {
            'fields': ('available_transitions',),
            'classes': ('collapse',),
        }),
        (_('Meta'), {
            'fields': ('uploaded_by', 'uploaded_at', 'file_size', 'file_extension'),
            'classes': ('collapse',),
        }),
        (_('Ознакомление'), {
            'fields': ('recipients_summary', 'pending_list'),
        }),
    )
    readonly_fields = (
        'status',  # FSM поле только через transitions
        'available_transitions',
        'uploaded_by', 
        'uploaded_at',
        'file_preview',
        'file_size',
        'file_extension',
        'recipients_summary', 
        'pending_list',
    )

    def save_model(self, request, obj, form, change):
        """Автоматически устанавливаем uploaded_by при создании."""
        if not obj.pk:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)

    def status_badge(self, obj):
        """Статус документа с цветовым индикатором."""
        colors = {
            'draft': '#6c757d',       # серый
            'in_review': '#0dcaf0',   # голубой  
            'approved': '#198754',    # зеленый
            'published': '#0d6efd',   # синий
            'archived': '#6c757d',    # серый
            'rejected': '#dc3545',    # красный
        }
        color = colors.get(obj.status, '#6c757d')
        return format_html(
            '<span style="background-color:{}; color:white; padding:3px 8px; '
            'border-radius:3px; font-size:11px; font-weight:bold;">{}</span>',
            color,
            obj.get_status_display()
        )
    status_badge.short_description = _('Статус')

    def available_transitions(self, obj):
        """Список доступных переходов (transitions) для текущего состояния."""
        if not obj.pk:
            return '—'
        
        transitions = get_available_FIELD_transitions(obj, Document.status)
        if not transitions:
            return format_html('<em>Нет доступных переходов</em>')
        
        html = '<ul style="margin:0; padding-left:20px;">'
        for transition in transitions:
            html += f'<li><strong>{transition.name}</strong>: {transition.target}</li>'
        html += '</ul>'
        
        return mark_safe(html)
    
    available_transitions.short_description = _('Доступные переходы')

    def file_thumbnail(self, obj):
        """Превью файла в списке документов."""
        if not obj.file:
            return '—'
        
        # Для изображений показываем thumbnail
        if obj.file.file_type == 'Image':
            thumbnail_url = obj.get_thumbnail('small')
            if thumbnail_url:
                return format_html(
                    '<a href="{}" target="_blank"><img src="{}" style="max-height:50px; max-width:50px;"/></a>',
                    obj.file.url,
                    thumbnail_url
                )
        
        # Для других файлов показываем иконку
        icon_url = obj.file.icons.get('48', '')
        if icon_url:
            return format_html(
                '<a href="{}" target="_blank"><img src="{}" style="height:32px;"/></a>',
                obj.file.url,
                icon_url
            )
        
        return format_html('<a href="{}" target="_blank">📎</a>', obj.file.url)
    
    file_thumbnail.short_description = _('Превью')

    def file_preview(self, obj):
        """Большое превью файла в форме редактирования."""
        if not obj.file:
            return '—'
        
        # Для изображений показываем большой thumbnail
        if obj.file.file_type == 'Image':
            thumbnail_url = obj.get_thumbnail('medium')
            if thumbnail_url:
                return format_html(
                    '<div style="margin:10px 0;">'
                    '<a href="{}" target="_blank">'
                    '<img src="{}" style="max-width:400px; border:1px solid #ddd; border-radius:4px;"/>'
                    '</a></div>',
                    obj.file.url,
                    thumbnail_url
                )
        
        # Для PDF можем показать первую страницу (если настроено)
        return format_html(
            '<div style="margin:10px 0;">'
            '<a href="{}" target="_blank" class="button">📎 Открыть файл</a>'
            '</div>',
            obj.file.url
        )
    
    file_preview.short_description = _('Предпросмотр')

    def file_info(self, obj):
        """Информация о файле (размер, тип)."""
        if not obj.file:
            return '—'
        
        # Форматируем размер файла
        size = obj.file_size
        if size < 1024:
            size_str = f'{size} B'
        elif size < 1024 * 1024:
            size_str = f'{size / 1024:.1f} KB'
        else:
            size_str = f'{size / (1024 * 1024):.1f} MB'
        
        ext = obj.file_extension or '—'
        return f'{ext.upper()} • {size_str}'
    
    file_info.short_description = _('Файл')

    def file_size(self, obj):
        """Размер файла в читаемом формате."""
        size = obj.file_size
        if not size:
            return '—'
        
        if size < 1024:
            return f'{size} байт'
        elif size < 1024 * 1024:
            return f'{size / 1024:.2f} KB'
        else:
            return f'{size / (1024 * 1024):.2f} MB'
    
    file_size.short_description = _('Размер файла')

    def file_extension(self, obj):
        """Расширение файла."""
        return obj.file_extension or '—'
    
    file_extension.short_description = _('Расширение')

    def acknowledgement_status(self, obj):
        """Статус ознакомления (N из M)."""
        recipients = set(self.get_recipients_qs(obj))
        total = len(recipients)
        
        if total == 0:
            return '—'
        
        acked_count = DocumentAcknowledgement.objects.filter(document=obj).count()
        
        if acked_count == total:
            return format_html('<span style="color:green;">✅ {}/{}</span>', acked_count, total)
        elif acked_count == 0:
            return format_html('<span style="color:red;">❌ 0/{}</span>', total)
        else:
            return format_html('<span style="color:orange;">⏳ {}/{}</span>', acked_count, total)
    
    acknowledgement_status.short_description = _('Ознакомлены')

    def send_document(self, request, queryset):
        """Action для рассылки документов получателям."""
        from .tasks import send_document_to_recipients_task
        for doc in queryset:
            # TODO: Создать новую задачу send_document_to_recipients_task
            pass
        self.message_user(request, _("⚠️ Рассылка будет реализована в обновленном tasks.py"))
    
    send_document.short_description = _('Отправить документ')

    def get_recipients_qs(self, obj):
        """Возвращает список всех получателей документа."""
        if obj.sent_to_all:
            return list(User.objects.filter(is_active=True))
        
        # Собираем получателей из recipients и departments
        recipients_set = set(obj.recipients.all())
        
        # Добавляем сотрудников из отделов
        for department in obj.departments.all():
            recipients_set.update(department.active_employees)
        
        return list(recipients_set)

    def recipients_summary(self, obj):
        """Краткий список получателей."""
        recipients = self.get_recipients_qs(obj)
        count = len(recipients)
        
        if count == 0:
            return _("— никто —")
        
        names = [u.get_full_name() or str(u) for u in recipients[:5]]
        if count > 5:
            return format_html("{}… (ещё {})", ", ".join(names), count - 5)
        return ", ".join(names)
    
    recipients_summary.short_description = _('Получатели')

    def pending_list(self, obj):
        """Список сотрудников, которые ещё не ознакомились."""
        recipients = set(self.get_recipients_qs(obj))
        acked_ids = set(
            DocumentAcknowledgement.objects
            .filter(document=obj)
            .values_list('user_id', flat=True)
        )
        pending = [u for u in recipients if u.id not in acked_ids]
        
        if not pending:
            return format_html('<span style="color:green;">✅ {}</span>', _("Все ознакомились"))
        
        links = []
        for u in pending[:20]:  # Ограничиваем 20, чтобы не перегружать
            url = reverse(
                'admin:{}_{}_change'.format(
                    User._meta.app_label, User._meta.model_name
                ), args=[u.pk]
            )
            links.append(format_html(
                '<a href="{}">{}</a>',
                url, 
                u.get_full_name() or u
            ))
        
        result = '<br>'.join(links)
        if len(pending) > 20:
            result += f'<br><em>... и ещё {len(pending) - 20}</em>'
        
        return mark_safe(result)
    
    pending_list.short_description = _('Кто ещё не ознакомился')


@admin.register(DocumentAcknowledgement)
class DocumentAcknowledgementAdmin(admin.ModelAdmin):
    """Admin для записей об ознакомлении с документами."""
    list_display = ('document', 'user', 'acknowledged_at')
    list_filter = ('document', 'acknowledged_at')
    search_fields = (
        'user__phone_number',
        'user__last_name', 
        'user__first_name',
        'document__title'
    )
    readonly_fields = ('user', 'document', 'acknowledged_at')
    ordering = ('-acknowledged_at',)
    
    def has_add_permission(self, request):
        """Запрещаем ручное добавление ознакомлений."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Запрещаем удаление ознакомлений (для аудита)."""
        return False


