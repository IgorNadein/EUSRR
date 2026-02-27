# documents/admin.py

from django.contrib import admin
from django.utils.translation import gettext_lazy as _
from django.utils.html import format_html, mark_safe
from django.urls import reverse
from .models import Document, DocumentAcknowledgement
from django.contrib.auth import get_user_model

User = get_user_model()


class AcknowledgementInline(admin.TabularInline):
    model = DocumentAcknowledgement
    extra = 0
    can_delete = False
    verbose_name = _("Ознакомление")
    verbose_name_plural = _("Ознакомления")
    fields = ('user_link', 'acknowledged_at')
    readonly_fields = ('user_link', 'acknowledged_at')

    def user_link(self, obj):
        url = reverse(
            'admin:{}_{}_change'.format(
                User._meta.app_label, User._meta.model_name
            ), args=[obj.user.pk]
        )
        return format_html('<a href="{}">{}</a>', url, obj.user.get_full_name() or obj.user)
    user_link.short_description = _("Сотрудник")


@admin.register(Document)
class DocumentAdmin(admin.ModelAdmin):
    inlines = [AcknowledgementInline]

    list_display = (
        'title', 'uploaded_at', 'sent_to_all',
        # убрали 'pending_summary'
    )
    list_filter = ('sent_to_all', 'uploaded_at')
    search_fields = ('title', 'description')
    filter_horizontal = ('recipients', 'departments')
    actions = ['send_document']

    fieldsets = (
        (None, {
            'fields': (
                'title', 'file', 'description',
                'sent_to_all', 'departments', 'recipients'
            ),
        }),
        (_('Meta'), {
            'fields': ('uploaded_by', 'uploaded_at'),
            'classes': ('collapse',),
        }),
        (_('Ознакомление'), {
            'fields': ('recipients_summary', 'pending_list'),
        }),
    )
    readonly_fields = (
        'uploaded_by', 'uploaded_at',
        'recipients_summary', 'pending_list',
    )

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.uploaded_by = request.user
        super().save_model(request, obj, form, change)

    def send_document(self, request, queryset):
        from .tasks import send_document_to_recipients
        for doc in queryset:
            send_document_to_recipients.delay(doc.id)
        self.message_user(request, _("Рассылка запущена."))
    send_document.short_description = _('Отправить документ')

    def get_recipients_qs(self, obj):
        """Возвращает всех получателей документа."""
        if obj.sent_to_all:
            return User.objects.filter(is_active=True)
        
        # Собираем получателей из recipients и departments
        recipients_set = set(obj.recipients.all())
        
        # Добавляем сотрудников из отделов
        for department in obj.departments.all():
            recipients_set.update(department.active_employees)
        
        return list(recipients_set)

    def recipients_summary(self, obj):
        qs = self.get_recipients_qs(obj)
        names = [u.get_full_name() or str(u) for u in qs[:5]]
        count = qs.count()
        if count > 5:
            return format_html("{}… (ещё {})", ", ".join(names), count - 5)
        return ", ".join(names) if names else _("— никто —")
    recipients_summary.short_description = _('Получатели')

    def pending_list(self, obj):
        recipients = set(self.get_recipients_qs(obj))
        acked_ids = set(
            DocumentAcknowledgement.objects
            .filter(document=obj)
            .values_list('user_id', flat=True)
        )
        pending = [u for u in recipients if u.id not in acked_ids]
        if not pending:
            return format_html('<span style="color:green;">{}</span>', _("Все ознакомились"))
        links = []
        for u in pending:
            url = reverse(
                'admin:{}_{}_change'.format(
                    User._meta.app_label, User._meta.model_name
                ), args=[u.pk]
            )
            links.append(format_html('<a href="{}">{}</a>',
                         url, u.get_full_name() or u))
        return mark_safe('<br>'.join(links))
    pending_list.short_description = _('Кто ещё не ознакомился')


@admin.register(DocumentAcknowledgement)
class DocumentAcknowledgementAdmin(admin.ModelAdmin):
    list_display = ('document', 'user', 'acknowledged_at')
    list_filter = ('document', 'acknowledged_at')
    search_fields = ('user__phone_number',
                     'user__last_name', 'document__title')
    readonly_fields = ('user', 'document', 'acknowledged_at')
    ordering = ('-acknowledged_at',)


# -----------------------------------------------------------------------------
# НОВЫЕ МОДЕЛИ V2 (с django-filer)
# -----------------------------------------------------------------------------

# Импортируем admin для новых моделей
from .admin_v2 import DocumentV2Admin, DocumentAcknowledgementV2Admin

