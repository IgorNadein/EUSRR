"""Django Admin для LDAP ORM моделей.

Предоставляет интерфейс для:
- Просмотра LDAP-данных
- Ручного редактирования полей (с осторожностью)
- Синхронизации при рассинхроне (выбор источника истины)
"""

import base64

from django.contrib import admin, messages
from django.utils.html import format_html
from django.urls import reverse
from django.db.models import OuterRef, Exists

from employees.models import Employee, LdapSyncState
from .orm_models import LdapUser, LdapGroup, LdapOrganizationalUnit
from .utils.ldap_utils import get_ldap_str


class LdapSyncStateInline(admin.TabularInline):
    """Inline для просмотра состояния синхронизации."""
    model = LdapSyncState
    extra = 0
    can_delete = False
    
    fields = (
        'model',
        'object_pk',
        'last_sync_dir',
        'last_ldap_modify_ts',
        'last_django_modify_ts',
        'updated_at',
    )
    readonly_fields = fields
    
    def has_add_permission(self, request, obj=None):
        return False


@admin.register(LdapUser)
class LdapUserAdmin(admin.ModelAdmin):
    """Админка для LDAP пользователей с поддержкой синхронизации.
    
    Возможности:
    - Просмотр всех LDAP-атрибутов
    - Ручное редактирование (для исправления рассинхрона)
    - Actions для синхронизации с выбором источника истины
    """
    
    list_display = (
        'cn_display',
        'sam_account_name',
        'mail',
        'django_employee_link',
        'sync_status',
        'account_status',
    )
    
    list_filter = (
        'user_account_control',
    )
    
    search_fields = (
        'cn',
        'sam_account_name',
        'mail',
        'employee_number',
        'given_name',
        'sn',
    )
    
    readonly_fields = (
        'dn_display',
        'member_of_display',
        'sync_info',
        'thumbnail_photo_display',
    )
    
    fieldsets = (
        ('🔑 Идентификация', {
            'fields': (
                'dn_display',
                'cn',
                'sam_account_name',
                'user_principal_name',
                'employee_number',
            )
        }),
        ('👤 Персональные данные', {
            'fields': (
                'given_name',
                'sn',
                'display_name',
                'mail',
            )
        }),
        ('📞 Контакты', {
            'fields': (
                'telephone_number',
                'mobile',
            )
        }),
        ('⚙️ Управление учетной записью', {
            'fields': (
                'user_account_control',
                'description',
            )
        }),
        ('🖼️ Дополнительно', {
            'classes': ('collapse',),
            'fields': (
                'thumbnail_photo_display',
            )
        }),
        ('👥 Членство в группах', {
            'classes': ('collapse',),
            'fields': (
                'member_of_display',
            )
        }),
        ('🔄 Статус синхронизации', {
            'fields': (
                'sync_info',
            )
        }),
    )
    
    actions = [
        'delete_selected_ldap',
        'sync_from_ldap_to_django',
        'sync_from_django_to_ldap',
        'show_sync_diff',
    ]
    
    # Пагинация (LDAP может быть медленным)
    list_per_page = 100
    
    def _resolve_ldap_users(self, request):
        """Получает выбранные LDAP объекты по DN из POST данных.
        
        ldapdb не поддерживает dn__in lookup, поэтому
        получаем каждый объект по DN отдельно.
        """
        selected_dns = request.POST.getlist('_selected_action')
        users = []
        for dn in selected_dns:
            try:
                user = LdapUser.objects.get(dn=dn)
                users.append(user)
            except LdapUser.DoesNotExist:
                pass
        return users
    
    # Кастомные поля для отображения
    
    def cn_display(self, obj):
        """CN с иконкой статуса."""
        if obj.cn:
            return format_html('👤 {}', obj.cn)
        return '-'
    cn_display.short_description = 'CN (Common Name)'
    
    def dn_display(self, obj):
        """DN с подсветкой компонентов."""
        if not obj.dn:
            return '-'
        
        # Разбиваем DN на части для читаемости
        parts = obj.dn.split(',')
        html_parts = []
        
        for part in parts:
            if part.startswith('CN='):
                html_parts.append(format_html('<strong style="color: #0066cc;">{}</strong>', part))
            elif part.startswith('OU='):
                html_parts.append(format_html('<span style="color: #666;">{}</span>', part))
            elif part.startswith('DC='):
                html_parts.append(format_html('<span style="color: #999;">{}</span>', part))
            else:
                html_parts.append(part)
        
        return format_html(','.join(html_parts))
    dn_display.short_description = 'Distinguished Name'
    
    def member_of_display(self, obj):
        """Список групп с форматированием."""
        if not obj.member_of:
            return format_html('<em style="color: #999;">Не состоит в группах</em>')
        
        groups_html = []
        for group_dn in obj.member_of[:10]:  # Ограничиваем первыми 10
            # Извлекаем CN из DN
            cn = group_dn.split(',')[0].replace('CN=', '')
            groups_html.append(format_html('• {}', cn))
        
        result = '<br>'.join(groups_html)
        if len(obj.member_of) > 10:
            result += format_html('<br><em>...и ещё {} групп</em>', len(obj.member_of) - 10)
        
        return format_html(result)
    member_of_display.short_description = 'Членство в группах'
    
    def django_employee_link(self, obj):
        """Ссылка на Django Employee если есть."""
        if not obj.employee_number:
            return format_html('<em style="color: #999;">-</em>')
        
        try:
            emp = Employee.objects.get(pk=int(obj.employee_number))
            url = reverse('admin:employees_employee_change', args=[emp.pk])
            return format_html(
                '<a href="{}" style="color: #0066cc;">👤 {} {}</a>',
                url,
                emp.first_name,
                emp.last_name
            )
        except (Employee.DoesNotExist, ValueError):
            return format_html(
                '<em style="color: #cc6600;">⚠️ ID {} (не найден)</em>',
                obj.employee_number
            )
    django_employee_link.short_description = 'Django Employee'
    
    def sync_status(self, obj):
        """Статус синхронизации с Django."""
        if not obj.employee_number:
            return format_html('<span style="color: #999;">❌ Не связан</span>')
        
        try:
            sync_state = LdapSyncState.objects.get(
                model='employee',
                object_pk=obj.employee_number
            )
            
            if sync_state.last_sync_dir == 'django':
                icon = '⬆️'
                color = '#0066cc'
                text = 'Django → LDAP'
            elif sync_state.last_sync_dir == 'ldap':
                icon = '⬇️'
                color = '#00cc66'
                text = 'LDAP → Django'
            else:
                icon = '❓'
                color = '#999'
                text = 'Неизвестно'
            
            return format_html(
                '<span style="color: {};">{} {}</span><br>'
                '<small style="color: #666;">{}</small>',
                color, icon, text,
                sync_state.updated_at.strftime('%Y-%m-%d %H:%M')
            )
        except LdapSyncState.DoesNotExist:
            return format_html('<span style="color: #cc6600;">⚠️ Нет записи</span>')
    sync_status.short_description = 'Синхронизация'
    
    def account_status(self, obj):
        """Статус учетной записи (активна/заблокирована)."""
        # UAC флаг ACCOUNTDISABLE = 0x2 (2)
        is_disabled = bool(obj.user_account_control and (obj.user_account_control & 2))
        
        if is_disabled:
            return format_html('<span style="color: #cc0000;">🔒 Заблокирована</span>')
        else:
            return format_html('<span style="color: #00cc00;">✅ Активна</span>')
    account_status.short_description = 'Статус'
    
    def thumbnail_photo_display(self, obj):
        """Превью аватара из LDAP thumbnailPhoto."""
        data = obj.thumbnail_photo
        if not data or not isinstance(data, (bytes, bytearray)):
            return format_html(
                '<em style="color:#999;">Нет фото</em>'
            )
        b64 = base64.b64encode(data).decode('ascii')
        return format_html(
            '<img src="data:image/jpeg;base64,{}" '
            'style="max-width:150px;max-height:150px;'
            'border-radius:8px;" />',
            b64,
        )
    thumbnail_photo_display.short_description = 'Фото'

    def sync_info(self, obj):
        """Подробная информация о синхронизации."""
        if not obj.employee_number:
            return format_html(
                '<div style="padding: 10px; background: #fff3cd; border-left: 4px solid #ffc107;">'
                '⚠️ <strong>Не связан с Django Employee</strong><br>'
                '<small>Этот LDAP-пользователь не привязан к записи в БД Django.</small>'
                '</div>'
            )
        
        try:
            emp = Employee.objects.get(pk=int(obj.employee_number))
            sync_state = LdapSyncState.objects.filter(
                model='employee',
                object_pk=obj.employee_number
            ).first()
            
            if not sync_state:
                return format_html(
                    '<div style="padding: 10px; background: #f8d7da; border-left: 4px solid #dc3545;">'
                    '❌ <strong>Нет записи синхронизации</strong><br>'
                    '<small>Связь с Employee ID {} установлена, но LdapSyncState отсутствует.</small>'
                    '</div>',
                    obj.employee_number
                )
            
            return format_html(
                '<div style="padding: 10px; background: #d1ecf1; border-left: 4px solid #17a2b8;">'
                '✅ <strong>Синхронизирован</strong><br>'
                '<table style="margin-top: 5px;">'
                '<tr><td><strong>Employee ID:</strong></td><td>{}</td></tr>'
                '<tr><td><strong>LDAP DN:</strong></td><td><code>{}</code></td></tr>'
                '<tr><td><strong>Последняя синхронизация:</strong></td><td>{}</td></tr>'
                '<tr><td><strong>Направление:</strong></td><td>{}</td></tr>'
                '</table>'
                '</div>',
                emp.pk,
                sync_state.ldap_dn or '-',
                sync_state.updated_at.strftime('%Y-%m-%d %H:%M:%S'),
                sync_state.last_sync_dir or 'не указано'
            )
        except Employee.DoesNotExist:
            return format_html(
                '<div style="padding: 10px; background: #f8d7da; border-left: 4px solid #dc3545;">'
                '❌ <strong>Employee не найден</strong><br>'
                '<small>employee_number={} указывает на несуществующую запись.</small>'
                '</div>',
                obj.employee_number
            )
    sync_info.short_description = 'Информация о синхронизации'
    
    # Actions для синхронизации
    
    @admin.action(description='🔄 Синхронизировать LDAP → Django (LDAP как источник истины)')
    def sync_from_ldap_to_django(self, request, queryset):
        """Синхронизирует выбранных пользователей из LDAP в Django.
        
        LDAP считается источником истины - данные из Active Directory
        перезапишут данные в Django Employee.
        """
        success_count = 0
        error_count = 0
        
        ldap_users = self._resolve_ldap_users(request)
        for ldap_user in ldap_users:
            if not ldap_user.employee_number:
                error_count += 1
                continue
            
            try:
                emp = Employee.objects.get(pk=int(ldap_user.employee_number))
                
                # Обновляем Django из LDAP
                emp.first_name = get_ldap_str(ldap_user.given_name) or emp.first_name
                emp.last_name = get_ldap_str(ldap_user.sn) or emp.last_name
                emp.email = get_ldap_str(ldap_user.mail) or emp.email
                ldap_phone = get_ldap_str(ldap_user.telephone_number or ldap_user.mobile)
                emp.phone_number = ldap_phone or emp.phone_number
                emp.save()
                
                # Обновляем LdapSyncState
                LdapSyncState.objects.update_or_create(
                    model='employee',
                    object_pk=str(emp.pk),
                    defaults={
                        'ldap_dn': ldap_user.dn,
                        'last_sync_dir': 'ldap',
                    }
                )
                
                success_count += 1
            except Exception as e:
                error_count += 1
                self.message_user(
                    request,
                    f'Ошибка синхронизации {ldap_user.cn}: {e}',
                    level=messages.ERROR
                )
        
        if success_count:
            self.message_user(
                request,
                f'Успешно синхронизировано: {success_count} пользователей (LDAP → Django)',
                level=messages.SUCCESS
            )
        if error_count:
            self.message_user(
                request,
                f'Ошибок: {error_count}',
                level=messages.WARNING
            )
    
    @admin.action(description='🔄 Синхронизировать Django → LDAP (Django как источник истины)')
    def sync_from_django_to_ldap(self, request, queryset):
        """Синхронизирует выбранных пользователей из Django в LDAP.
        
        Django считается источником истины - данные из БД
        перезапишут данные в Active Directory.
        """
        from employees.ldap.services import UserService
        
        success_count = 0
        error_count = 0
        
        service = UserService()
        
        ldap_users = self._resolve_ldap_users(request)
        for ldap_user in ldap_users:
            if not ldap_user.employee_number:
                error_count += 1
                continue
            
            try:
                emp = Employee.objects.get(pk=int(ldap_user.employee_number))
                
                # Обновляем LDAP из Django через сервис
                changes = {
                    'first_name': emp.first_name,
                    'last_name': emp.last_name,
                    'email': emp.email,
                    'phone_number': emp.phone_number,
                }
                
                service.update_user(emp, changes)
                
                success_count += 1
            except Exception as e:
                error_count += 1
                self.message_user(
                    request,
                    f'Ошибка синхронизации {ldap_user.cn}: {e}',
                    level=messages.ERROR
                )
        
        if success_count:
            self.message_user(
                request,
                f'Успешно синхронизировано: {success_count} пользователей (Django → LDAP)',
                level=messages.SUCCESS
            )
        if error_count:
            self.message_user(
                request,
                f'Ошибок: {error_count}',
                level=messages.WARNING
            )
    
    @admin.action(description='🔍 Показать различия LDAP ↔ Django')
    def show_sync_diff(self, request, queryset):
        """Показывает различия между LDAP и Django для выбранных пользователей."""
        diffs = []
        
        ldap_users = self._resolve_ldap_users(request)
        for ldap_user in ldap_users:
            if not ldap_user.employee_number:
                continue
            
            try:
                emp = Employee.objects.get(pk=int(ldap_user.employee_number))
                
                user_diffs = []
                
                # Сравниваем поля
                ldap_first = get_ldap_str(ldap_user.given_name)
                if ldap_first != emp.first_name:
                    user_diffs.append(f"Имя: LDAP='{ldap_first}' vs Django='{emp.first_name}'")
                
                ldap_last = get_ldap_str(ldap_user.sn)
                if ldap_last != emp.last_name:
                    user_diffs.append(f"Фамилия: LDAP='{ldap_last}' vs Django='{emp.last_name}'")
                
                ldap_email = get_ldap_str(ldap_user.mail)
                if ldap_email != emp.email:
                    user_diffs.append(f"Email: LDAP='{ldap_email}' vs Django='{emp.email}'")
                
                ldap_phone = get_ldap_str(ldap_user.telephone_number or ldap_user.mobile)
                if ldap_phone and ldap_phone != emp.phone_number:
                    user_diffs.append(f"Телефон: LDAP='{ldap_phone}' vs Django='{emp.phone_number}'")
                
                if user_diffs:
                    diffs.append(f"{ldap_user.cn}: " + ", ".join(user_diffs))
            except Employee.DoesNotExist:
                diffs.append(f"{ldap_user.cn}: Employee ID {ldap_user.employee_number} не найден")
        
        if diffs:
            self.message_user(
                request,
                "Найдены различия:\n" + "\n".join(diffs),
                level=messages.WARNING
            )
        else:
            self.message_user(
                request,
                "Различий не найдено. Все выбранные пользователи синхронизированы.",
                level=messages.SUCCESS
            )
    
    # Переопределение разрешений (опционально - можно разрешить редактирование)
    
    def has_add_permission(self, request):
        """Запрещаем создание через админку (используйте signals)."""
        return False
    
    def has_delete_permission(self, request, obj=None):
        """Разрешаем удаление только суперпользователям."""
        return request.user.is_superuser

    def get_action_choices(self, request, default_choices=admin.ModelAdmin.action_form):
        """Убираем стандартный delete_selected (ldapdb не поддерживает dn__in)."""
        choices = super().get_action_choices(request, default_choices)
        return [
            c for c in choices
            if not (isinstance(c[0], str) and c[0] == 'delete_selected')
        ]

    @admin.action(description='🗑️ Удалить выбранных пользователей из LDAP')
    def delete_selected_ldap(self, request, queryset):
        """Кастомное удаление — обходит dn__in, читает DN из POST."""
        users = self._resolve_ldap_users(request)
        if not users:
            self.message_user(
                request, 'Не удалось найти выбранных пользователей.',
                level=messages.WARNING,
            )
            return

        if request.POST.get('post') != 'yes':
            # Показываем confirmation page
            from django.template.response import TemplateResponse
            context = {
                **self.admin_site.each_context(request),
                'title': 'Подтверждение удаления',
                'objects_name': 'LDAP пользователей',
                'deletable_objects': [str(u) for u in users],
                'queryset': users,
                'opts': self.model._meta,
                'action_checkbox_name': admin.helpers.ACTION_CHECKBOX_NAME,
                'media': self.media,
            }
            request.current_app = self.admin_site.name
            return TemplateResponse(
                request,
                'admin/ldap_delete_confirmation.html',
                context,
            )

        deleted = 0
        for user in users:
            try:
                user.delete()
                deleted += 1
            except Exception as e:
                self.message_user(
                    request,
                    f'Ошибка удаления {user.cn}: {e}',
                    level=messages.ERROR,
                )
        if deleted:
            self.message_user(
                request,
                f'Удалено: {deleted} пользователей из LDAP.',
                level=messages.SUCCESS,
            )
    
    def get_queryset(self, request):
        """Базовый queryset без slice - пагинация через list_per_page."""
        return super().get_queryset(request)


# TODO: Добавить LdapGroupAdmin и LdapOrganizationalUnitAdmin аналогично
