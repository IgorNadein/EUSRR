"""Django Admin для LDAP ORM моделей.

Предоставляет интерфейс для:
- Просмотра LDAP-данных
- Ручного редактирования полей (с осторожностью)
- Синхронизации при рассинхроне (выбор источника истины)
"""

import base64
from urllib.parse import quote

from django.contrib import admin, messages
from django.utils.html import format_html
from django.urls import reverse

from employees.models import Employee, LdapSyncState
from .orm_models import (
    LdapUser,
    LdapGroup,
    LdapOrganizationalUnitGroup,
    LdapOrganizationalUnit,
)
from .utils.ldap_utils import get_ldap_str


class LdapSyncStateInline(admin.TabularInline):
    """Inline для просмотра состояния синхронизации."""

    model = LdapSyncState
    extra = 0
    can_delete = False

    fields = (
        "model",
        "object_pk",
        "last_sync_dir",
        "last_ldap_modify_ts",
        "last_django_modify_ts",
        "updated_at",
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

    def get_urls(self):
        """Добавляем URL для смены пароля конкретного пользователя."""
        from django.urls import re_path

        urls = [
            re_path(
                r"^(.+)/password/$",
                self.admin_site.admin_view(self.user_change_password),
                name="ldapuser_password_change",
            ),
        ]
        return urls + super().get_urls()

    list_display = (
        "cn_display",
        "sam_account_name",
        "mail",
        "django_employee_link",
        "sync_status",
        "account_status",
    )

    list_filter = ("user_account_control",)

    search_fields = (
        "cn",
        "sam_account_name",
        "mail",
        "employee_number",
        "given_name",
        "sn",
    )

    readonly_fields = (
        "dn_display",
        "member_of_display",
        "sync_info",
        "thumbnail_photo_display",
        "password_change_link",
    )

    fieldsets = (
        (
            "🔑 Идентификация",
            {
                "fields": (
                    "dn_display",
                    "cn",
                    "sam_account_name",
                    "user_principal_name",
                    "employee_number",
                )
            },
        ),
        (
            "👤 Персональные данные",
            {
                "fields": (
                    "given_name",
                    "sn",
                    "display_name",
                    "mail",
                )
            },
        ),
        (
            "📞 Контакты",
            {
                "fields": (
                    "telephone_number",
                    "mobile",
                )
            },
        ),
        (
            "⚙️ Управление учетной записью",
            {
                "fields": (
                    "user_account_control",
                    "description",
                    "password_change_link",
                )
            },
        ),
        (
            "🖼️ Дополнительно",
            {"classes": ("collapse",), "fields": ("thumbnail_photo_display",)},
        ),
        (
            "👥 Членство в группах",
            {"classes": ("collapse",), "fields": ("member_of_display",)},
        ),
        ("🔄 Статус синхронизации", {"fields": ("sync_info",)}),
    )

    actions = [
        "delete_selected_ldap",
        "sync_from_ldap_to_django",
        "sync_from_django_to_ldap",
        "show_sync_diff",
        "change_password_action",
    ]

    # Пагинация (LDAP может быть медленным)
    list_per_page = 100

    def _resolve_ldap_users(self, request):
        """Получает выбранные LDAP объекты по DN из POST данных.

        ldapdb не поддерживает dn__in lookup, поэтому
        получаем каждый объект по DN отдельно.
        """
        selected_dns = request.POST.getlist("_selected_action")
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
            return format_html("👤 {}", obj.cn)
        return "-"

    cn_display.short_description = "CN (Common Name)"

    def dn_display(self, obj):
        """DN с подсветкой компонентов."""
        if not obj.dn:
            return "-"

        # Разбиваем DN на части для читаемости
        parts = obj.dn.split(",")
        html_parts = []

        for part in parts:
            if part.startswith("CN="):
                html_parts.append(
                    format_html(
                        '<strong style="color: #0066cc;">{}</strong>', part
                    )
                )
            elif part.startswith("OU="):
                html_parts.append(
                    format_html('<span style="color: #666;">{}</span>', part)
                )
            elif part.startswith("DC="):
                html_parts.append(
                    format_html('<span style="color: #999;">{}</span>', part)
                )
            else:
                html_parts.append(part)

        return format_html(",".join(html_parts))

    dn_display.short_description = "Distinguished Name"

    def member_of_display(self, obj):
        """Список групп с форматированием."""
        if not obj.member_of:
            return format_html(
                '<em style="color: #999;">Не состоит в группах</em>'
            )

        groups_html = []
        for group_dn in obj.member_of[:10]:  # Ограничиваем первыми 10
            # Извлекаем CN из DN
            cn = group_dn.split(",")[0].replace("CN=", "")
            groups_html.append(format_html("• {}", cn))

        result = "<br>".join(groups_html)
        if len(obj.member_of) > 10:
            result += format_html(
                "<br><em>...и ещё {} групп</em>", len(obj.member_of) - 10
            )

        return format_html(result)

    member_of_display.short_description = "Членство в группах"

    def django_employee_link(self, obj):
        """Ссылка на Django Employee если есть."""
        if not obj.employee_number:
            return format_html('<em style="color: #999;">-</em>')

        try:
            emp = Employee.objects.get(pk=int(obj.employee_number))
            url = reverse("admin:employees_employee_change", args=[emp.pk])
            return format_html(
                '<a href="{}" style="color: #0066cc;">👤 {} {}</a>',
                url,
                emp.first_name,
                emp.last_name,
            )
        except (Employee.DoesNotExist, ValueError):
            return format_html(
                '<em style="color: #cc6600;">⚠️ ID {} (не найден)</em>',
                obj.employee_number,
            )

    django_employee_link.short_description = "Django Employee"

    def sync_status(self, obj):
        """Статус синхронизации с Django."""
        if not obj.employee_number:
            return format_html('<span style="color: #999;">❌ Не связан</span>')

        try:
            sync_state = LdapSyncState.objects.get(
                model="employee", object_pk=obj.employee_number
            )

            if sync_state.last_sync_dir == "django":
                icon = "⬆️"
                color = "#0066cc"
                text = "Django → LDAP"
            elif sync_state.last_sync_dir == "ldap":
                icon = "⬇️"
                color = "#00cc66"
                text = "LDAP → Django"
            else:
                icon = "❓"
                color = "#999"
                text = "Неизвестно"

            return format_html(
                '<span style="color: {};">{} {}</span><br>'
                '<small style="color: #666;">{}</small>',
                color,
                icon,
                text,
                sync_state.updated_at.strftime("%Y-%m-%d %H:%M"),
            )
        except LdapSyncState.DoesNotExist:
            return format_html(
                '<span style="color: #cc6600;">⚠️ Нет записи</span>'
            )

    sync_status.short_description = "Синхронизация"

    def account_status(self, obj):
        """Статус учетной записи (активна/заблокирована)."""
        # UAC флаг ACCOUNTDISABLE = 0x2 (2)
        is_disabled = bool(
            obj.user_account_control and (obj.user_account_control & 2)
        )

        if is_disabled:
            return format_html(
                '<span style="color: #cc0000;">🔒 Заблокирована</span>'
            )
        else:
            return format_html(
                '<span style="color: #00cc00;">✅ Активна</span>'
            )

    account_status.short_description = "Статус"

    def thumbnail_photo_display(self, obj):
        """Превью аватара из LDAP thumbnailPhoto."""
        data = obj.thumbnail_photo
        if not data or not isinstance(data, (bytes, bytearray)):
            return format_html('<em style="color:#999;">Нет фото</em>')
        b64 = base64.b64encode(data).decode("ascii")
        return format_html(
            '<img src="data:image/jpeg;base64,{}" '
            'style="max-width:150px;max-height:150px;'
            'border-radius:8px;" />',
            b64,
        )

    thumbnail_photo_display.short_description = "Фото"

    def sync_info(self, obj):
        """Подробная информация о синхронизации."""
        if not obj.employee_number:
            return format_html(
                '<div style="padding: 10px; background: #fff3cd; '
                'border-left: 4px solid #ffc107;">'
                "⚠️ <strong>Не связан с Django Employee</strong><br>"
                "<small>Этот LDAP-пользователь не привязан к записи "
                "в БД Django.</small>"
                "</div>"
            )

        try:
            emp = Employee.objects.get(pk=int(obj.employee_number))
            sync_state = LdapSyncState.objects.filter(
                model="employee", object_pk=obj.employee_number
            ).first()

            if not sync_state:
                return format_html(
                    '<div style="padding: 10px; background: #f8d7da; '
                    'border-left: 4px solid #dc3545;">'
                    "❌ <strong>Нет записи синхронизации</strong><br>"
                    "<small>Связь с Employee ID {} установлена, "
                    "но LdapSyncState отсутствует.</small>"
                    "</div>",
                    obj.employee_number,
                )

            return format_html(
                '<div style="padding: 10px; background: #d1ecf1; '
                'border-left: 4px solid #17a2b8;">'
                "✅ <strong>Синхронизирован</strong><br>"
                '<table style="margin-top: 5px;">'
                "<tr><td><strong>Employee ID:</strong></td><td>{}</td></tr>"
                "<tr><td><strong>LDAP DN:</strong></td>"
                "<td><code>{}</code></td></tr>"
                "<tr><td><strong>Последняя синхронизация:</strong></td>"
                "<td>{}</td></tr>"
                "<tr><td><strong>Направление:</strong></td><td>{}</td></tr>"
                "</table>"
                "</div>",
                emp.pk,
                sync_state.ldap_dn or "-",
                sync_state.updated_at.strftime("%Y-%m-%d %H:%M:%S"),
                sync_state.last_sync_dir or "не указано",
            )
        except Employee.DoesNotExist:
            return format_html(
                '<div style="padding: 10px; background: #f8d7da; '
                'border-left: 4px solid #dc3545;">'
                "❌ <strong>Employee не найден</strong><br>"
                "<small>employee_number={} указывает на "
                "несуществующую запись.</small>"
                "</div>",
                obj.employee_number,
            )

    sync_info.short_description = "Информация о синхронизации"

    def password_change_link(self, obj):
        """Ссылка на форму смены пароля (как в стандартной Django admin)."""
        if not obj.dn:
            return "-"

        # Кодируем DN для URL
        from urllib.parse import quote

        dn_encoded = quote(obj.dn, safe="")

        change_password_url = reverse(
            "admin:ldapuser_password_change",
            args=[dn_encoded],
        )

        return format_html(
            '<div style="margin: 10px 0;">'
            '<a href="{}" class="button" style="'
            "display: inline-block; "
            "padding: 10px 20px; "
            "background: #417690; "
            "color: white; "
            "text-decoration: none; "
            "border-radius: 4px; "
            "font-weight: bold;"
            '">'
            "🔑 Изменить пароль"
            "</a>"
            "</div>"
            '<p style="color: #666; margin-top: 10px;">'
            "Пароль будет изменён в LDAP и автоматически "
            "синхронизирован с Django БД."
            "</p>",
            change_password_url,
        )

    password_change_link.short_description = "Управление паролем"

    # Actions для синхронизации

    @admin.action(
        description=(
            "🔄 Синхронизировать LDAP → Django "
            "(LDAP как источник истины)"
        )
    )
    def sync_from_ldap_to_django(self, request, queryset):
        """Синхронизирует выбранных пользователей из LDAP в Django.

        LDAP считается источником истины - данные из Active Directory
        перезапишут данные в Django Employee.
        """
        success_count = 0
        error_count = 0
        warnings = []

        ldap_users = self._resolve_ldap_users(request)
        for ldap_user in ldap_users:
            if not ldap_user.employee_number:
                error_count += 1
                warnings.append(
                    f"⚠️ {
                        ldap_user.cn
                    }: отсутствует employeeNumber (связь с Django)"
                )
                continue

            # Проверка обязательных полей в LDAP
            missing_fields = []
            if not get_ldap_str(ldap_user.given_name):
                missing_fields.append("givenName (имя)")
            if not get_ldap_str(ldap_user.sn):
                missing_fields.append("sn (фамилия)")
            if not get_ldap_str(ldap_user.mail):
                missing_fields.append("mail (email)")

            if missing_fields:
                warnings.append(
                    f"⚠️ {ldap_user.cn}: отсутствуют поля в LDAP: {
                        ', '.join(missing_fields)
                    }"
                )

            try:
                emp = Employee.objects.get(pk=int(ldap_user.employee_number))

                # Обновляем Django из LDAP
                emp.first_name = (
                    get_ldap_str(ldap_user.given_name) or emp.first_name
                )
                emp.last_name = get_ldap_str(ldap_user.sn) or emp.last_name
                emp.email = get_ldap_str(ldap_user.mail) or emp.email
                ldap_phone = get_ldap_str(
                    ldap_user.telephone_number or ldap_user.mobile
                )
                emp.phone_number = ldap_phone or emp.phone_number
                emp.save()

                # Обновляем LdapSyncState
                LdapSyncState.objects.update_or_create(
                    model="employee",
                    object_pk=str(emp.pk),
                    defaults={
                        "ldap_dn": ldap_user.dn,
                        "last_sync_dir": "ldap",
                    },
                )

                success_count += 1
            except Exception as e:
                error_count += 1
                self.message_user(
                    request,
                    f"Ошибка синхронизации {ldap_user.cn}: {e}",
                    level=messages.ERROR,
                )

        if warnings:
            for warning in warnings[:10]:  # Первые 10 предупреждений
                self.message_user(request, warning, level=messages.WARNING)
            if len(warnings) > 10:
                self.message_user(
                    request,
                    f"...и ещё {len(warnings) - 10} предупреждений",
                    level=messages.WARNING,
                )

        if success_count:
            self.message_user(
                request,
                f"Успешно синхронизировано: {success_count} "
                "пользователей (LDAP → Django)",
                level=messages.SUCCESS,
            )
        if error_count:
            self.message_user(
                request, f"Ошибок: {error_count}", level=messages.WARNING
            )

    @admin.action(
        description=(
            "🔄 Синхронизировать Django → LDAP "
            "(Django как источник истины)"
        )
    )
    def sync_from_django_to_ldap(self, request, queryset):
        """Синхронизирует выбранных пользователей из Django в LDAP.

        Django считается источником истины - данные из БД
        перезапишут данные в Active Directory.
        """
        from employees.ldap.services import UserService

        success_count = 0
        error_count = 0
        warnings = []

        service = UserService()

        ldap_users = self._resolve_ldap_users(request)
        for ldap_user in ldap_users:
            if not ldap_user.employee_number:
                error_count += 1
                warnings.append(
                    f"⚠️ {
                        ldap_user.cn
                    }: отсутствует employeeNumber (связь с Django)"
                )
                continue

            try:
                emp = Employee.objects.get(pk=int(ldap_user.employee_number))

                # Проверка обязательных полей в Django
                missing_fields = []
                if not emp.first_name or not emp.first_name.strip():
                    missing_fields.append("first_name (имя)")
                if not emp.last_name or not emp.last_name.strip():
                    missing_fields.append("last_name (фамилия)")
                if not emp.email or not emp.email.strip():
                    missing_fields.append("email")

                if missing_fields:
                    warnings.append(
                        f"⚠️ Employee #{emp.pk}: отсутствуют поля: {
                            ', '.join(missing_fields)
                        }"
                    )

                # Обновляем LDAP из Django через сервис
                changes = {
                    "first_name": emp.first_name,
                    "last_name": emp.last_name,
                    "email": emp.email,
                    "phone_number": emp.phone_number,
                }

                service.update_user(emp, changes)

                success_count += 1
            except Exception as e:
                error_count += 1
                self.message_user(
                    request,
                    f"Ошибка синхронизации {ldap_user.cn}: {e}",
                    level=messages.ERROR,
                )

        if warnings:
            for warning in warnings[:10]:  # Первые 10 предупреждений
                self.message_user(request, warning, level=messages.WARNING)
            if len(warnings) > 10:
                self.message_user(
                    request,
                    f"...и ещё {len(warnings) - 10} предупреждений",
                    level=messages.WARNING,
                )

        if success_count:
            self.message_user(
                request,
                f"Успешно синхронизировано: {success_count} "
                "пользователей (Django → LDAP)",
                level=messages.SUCCESS,
            )
        if error_count:
            self.message_user(
                request, f"Ошибок: {error_count}", level=messages.WARNING
            )

    @admin.action(description="🔑 Изменить пароль выбранных пользователей")
    def change_password_action(self, request, queryset):
        """Изменяет пароль выбранных LDAP пользователей.

        Показывает форму для ввода нового пароля и применяет его
        к выбранным пользователям через AD extended operation.
        """
        ldap_users = self._resolve_ldap_users(request)

        if not ldap_users:
            self.message_user(
                request,
                "❌ Не удалось найти выбранных пользователей",
                level=messages.ERROR,
            )
            return

        # Если форма не отправлена - показываем её
        if "new_password" not in request.POST:
            from django import forms
            from django.template.response import TemplateResponse

            class PasswordForm(forms.Form):
                new_password = forms.CharField(
                    label="Новый пароль",
                    widget=forms.PasswordInput(
                        attrs={"autocomplete": "new-password"}
                    ),
                    min_length=7,
                    help_text=(
                        "Минимум 7 символов, должен соответствовать "
                        "политике AD"
                    ),
                )
                confirm_password = forms.CharField(
                    label="Подтверждение пароля",
                    widget=forms.PasswordInput(
                        attrs={"autocomplete": "new-password"}
                    ),
                )

                def clean(self):
                    cleaned = super().clean()
                    pwd1 = cleaned.get("new_password")
                    pwd2 = cleaned.get("confirm_password")
                    if pwd1 and pwd2 and pwd1 != pwd2:
                        raise forms.ValidationError("Пароли не совпадают")
                    return cleaned

            form = PasswordForm()

            context = {
                **self.admin_site.each_context(request),
                "title": "Изменение пароля LDAP пользователей",
                "form": form,
                "users": ldap_users,
                "users_count": len(ldap_users),
                "action_name": "change_password_action",
                "opts": self.model._meta,
                "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
                "media": self.media,
            }
            request.current_app = self.admin_site.name

            # Используем кастомный шаблон для смены пароля
            return TemplateResponse(
                request,
                "admin/ldap_change_password.html",
                context,
            )

        # Форма отправлена - обрабатываем
        new_password = request.POST.get("new_password", "").strip()
        confirm_password = request.POST.get("confirm_password", "").strip()

        if not new_password:
            self.message_user(
                request, "❌ Пароль не может быть пустым", level=messages.ERROR
            )
            return

        if new_password != confirm_password:
            self.message_user(
                request, "❌ Пароли не совпадают", level=messages.ERROR
            )
            return

        if len(new_password) < 7:
            self.message_user(
                request,
                "❌ Пароль должен содержать минимум 7 символов",
                level=messages.ERROR,
            )
            return

        # Применяем пароль ко всем выбранным пользователям
        success_count = 0
        error_count = 0

        for ldap_user in ldap_users:
            try:
                ldap_user.set_password(new_password)
                success_count += 1

                # Обновляем Django Employee если есть связь
                if ldap_user.employee_number:
                    try:
                        emp = Employee.objects.get(
                            pk=int(ldap_user.employee_number)
                        )
                        emp.set_password(new_password)
                        emp.save(update_fields=["password"])
                    except (Employee.DoesNotExist, ValueError):
                        pass  # Не критично

            except ValueError as e:
                error_count += 1
                self.message_user(
                    request, f"⚠️ {ldap_user.cn}: {e}", level=messages.WARNING
                )
            except Exception as e:
                error_count += 1
                self.message_user(
                    request,
                    f"❌ {ldap_user.cn}: ошибка - {e}",
                    level=messages.ERROR,
                )

        if success_count:
            self.message_user(
                request,
                f"✅ Пароль успешно изменён для {success_count} пользователей",
                level=messages.SUCCESS,
            )
        if error_count:
            self.message_user(
                request, f"❌ Ошибок: {error_count}", level=messages.WARNING
            )

    @admin.action(description="🔍 Показать различия LDAP ↔ Django")
    def show_sync_diff(self, request, queryset):
        """Показывает различия между LDAP и Django.

        Сравнение выполняется для выбранных пользователей.
        """
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
                    user_diffs.append(
                        (
                            f"Имя: LDAP='{ldap_first}' "
                            f"vs Django='{emp.first_name}'"
                        )
                    )

                ldap_last = get_ldap_str(ldap_user.sn)
                if ldap_last != emp.last_name:
                    user_diffs.append(
                        f"Фамилия: LDAP='{ldap_last}' vs Django='{
                            emp.last_name
                        }'"
                    )

                ldap_email = get_ldap_str(ldap_user.mail)
                if ldap_email != emp.email:
                    user_diffs.append(
                        f"Email: LDAP='{ldap_email}' vs Django='{emp.email}'"
                    )

                ldap_phone = get_ldap_str(
                    ldap_user.telephone_number or ldap_user.mobile
                )
                if ldap_phone and ldap_phone != emp.phone_number:
                    user_diffs.append(
                        f"Телефон: LDAP='{ldap_phone}' vs Django='{
                            emp.phone_number
                        }'"
                    )

                if user_diffs:
                    diffs.append(f"{ldap_user.cn}: " + ", ".join(user_diffs))
            except Employee.DoesNotExist:
                diffs.append(
                    f"{ldap_user.cn}: Employee ID "
                    f"{ldap_user.employee_number} не найден"
                )

        if diffs:
            self.message_user(
                request,
                "Найдены различия:\n" + "\n".join(diffs),
                level=messages.WARNING,
            )
        else:
            self.message_user(
                request,
                "Различий не найдено. Все выбранные пользователи "
                "синхронизированы.",
                level=messages.SUCCESS,
            )

    # Страница смены пароля для конкретного пользователя

    def user_change_password(self, request, dn_encoded):
        """Форма смены пароля для конкретного LDAP пользователя."""
        from django import forms
        from django.template.response import TemplateResponse
        from django.http import HttpResponseRedirect
        from urllib.parse import unquote

        # Декодируем DN
        dn = unquote(dn_encoded)

        # Находим пользователя
        try:
            user = LdapUser.objects.get(dn=dn)
        except LdapUser.DoesNotExist:
            self.message_user(
                request, "❌ Пользователь не найден", level=messages.ERROR
            )
            return HttpResponseRedirect("../../")  # Возврат на список

        # Форма для смены пароля
        class PasswordChangeForm(forms.Form):
            password1 = forms.CharField(
                label="Новый пароль",
                widget=forms.PasswordInput(
                    attrs={"autocomplete": "new-password"}
                ),
                min_length=7,
                help_text=(
                    "Минимум 7 символов, должен соответствовать "
                    "политике AD"
                ),
            )
            password2 = forms.CharField(
                label="Подтверждение пароля",
                widget=forms.PasswordInput(
                    attrs={"autocomplete": "new-password"}
                ),
            )

            def clean(self):
                cleaned = super().clean()
                pwd1 = cleaned.get("password1")
                pwd2 = cleaned.get("password2")
                if pwd1 and pwd2 and pwd1 != pwd2:
                    raise forms.ValidationError("Пароли не совпадают")
                return cleaned

        if request.method == "POST":
            form = PasswordChangeForm(request.POST)
            if form.is_valid():
                new_password = form.cleaned_data["password1"]

                try:
                    # Меняем пароль в LDAP
                    user.set_password(new_password)

                    # Синхронизируем с Django Employee
                    if user.employee_number:
                        try:
                            emp = Employee.objects.get(
                                pk=int(user.employee_number)
                            )
                            emp.set_password(new_password)
                            emp.save(update_fields=["password"])
                        except (Employee.DoesNotExist, ValueError):
                            pass  # Не критично

                    self.message_user(
                        request,
                        f"✅ Пароль успешно изменён для {user.cn}",
                        level=messages.SUCCESS,
                    )

                    # Перенаправляем на список пользователей.
                    # Избегаем проблем с кодировкой DN.
                    return HttpResponseRedirect("../../")

                except ValueError as e:
                    form.add_error(None, f"Ошибка валидации: {e}")
                except Exception as e:
                    form.add_error(None, f"Ошибка LDAP: {e}")
        else:
            form = PasswordChangeForm()

        context = {
            **self.admin_site.each_context(request),
            "title": f"Изменение пароля: {user.cn}",
            "form": form,
            "user": user,
            "opts": self.model._meta,
            "original": user,
            "media": self.media,
        }

        return TemplateResponse(
            request,
            "admin/ldap_user_password_change.html",
            context,
        )

    # Переопределение разрешений (опционально - можно разрешить редактирование)

    def has_add_permission(self, request):
        """Запрещаем создание через админку (используйте signals)."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Разрешаем удаление только суперпользователям."""
        return request.user.is_superuser

    def get_action_choices(self, request, default_choices=None):
        """Убираем стандартный delete_selected.

        ldapdb не поддерживает dn__in.
        """
        if default_choices is None:
            from django.db import models

            default_choices = models.BLANK_CHOICE_DASH
        choices = super().get_action_choices(request, default_choices)
        return [
            c
            for c in choices
            if not (isinstance(c[0], str) and c[0] == "delete_selected")
        ]

    @admin.action(description="🗑️ Удалить выбранных пользователей из LDAP")
    def delete_selected_ldap(self, request, queryset):
        """Кастомное удаление — обходит dn__in, читает DN из POST."""
        users = self._resolve_ldap_users(request)
        if not users:
            self.message_user(
                request,
                "Не удалось найти выбранных пользователей.",
                level=messages.WARNING,
            )
            return

        if request.POST.get("post") != "yes":
            # Показываем confirmation page
            from django.template.response import TemplateResponse

            context = {
                **self.admin_site.each_context(request),
                "title": "Подтверждение удаления",
                "objects_name": "LDAP пользователей",
                "deletable_objects": [str(u) for u in users],
                "queryset": users,
                "opts": self.model._meta,
                "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
                "media": self.media,
            }
            request.current_app = self.admin_site.name
            return TemplateResponse(
                request,
                "admin/ldap_delete_confirmation.html",
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
                    f"Ошибка удаления {user.cn}: {e}",
                    level=messages.ERROR,
                )
        if deleted:
            self.message_user(
                request,
                f"Удалено: {deleted} пользователей из LDAP.",
                level=messages.SUCCESS,
            )

    def get_queryset(self, request):
        """Базовый queryset без slice - пагинация через list_per_page."""
        return super().get_queryset(request)


@admin.register(LdapOrganizationalUnit)
class LdapOrganizationalUnitAdmin(admin.ModelAdmin):
    """Админка для LDAP Organizational Units (отделов).

    Возможности:
    - Просмотр всех OU в Active Directory
    - Ручное редактирование (описание, managedBy)
    - Связь с Django Department
    - Actions для синхронизации и удаления
    """

    def get_urls(self):
        """Переопределяем URLs для корректной работы с DN как PK."""
        urls = super().get_urls()
        return urls

    list_display = (
        "ou_display",
        "description_short",
        "managed_by_display",
        "django_department_link",
        "when_changed",
    )

    search_fields = (
        "ou",
        "description",
        "managed_by",
    )

    readonly_fields = (
        "dn_display",
        "managed_by_link",
        "django_department_info",
    )

    fieldsets = (
        (
            "🔑 Идентификация",
            {
                "fields": (
                    "dn_display",
                    "ou",
                )
            },
        ),
        ("📝 Описание", {"fields": ("description",)}),
        (
            "👤 Руководитель (managedBy)",
            {
                "fields": (
                    "managed_by",
                    "managed_by_link",
                )
            },
        ),
        ("🔗 Связь с Django", {"fields": ("django_department_info",)}),
    )

    actions = [
        "delete_selected_ldap",
        "sync_from_ldap_to_django",
        "sync_from_django_to_ldap",
        "show_sync_diff",
    ]

    list_per_page = 100

    def _resolve_ldap_ous(self, request):
        """Получает выбранные LDAP OU по DN из POST данных.

        ldapdb не поддерживает dn__in lookup, поэтому
        получаем каждый объект по DN отдельно.
        """
        selected_dns = request.POST.getlist("_selected_action")
        ous = []
        for dn in selected_dns:
            try:
                ou = LdapOrganizationalUnit.objects.get(dn=dn)
                ous.append(ou)
            except LdapOrganizationalUnit.DoesNotExist:
                pass
        return ous

    def _find_django_department(self, ldap_ou):
        """Ищет Django Department по имени OU или по ldap_dn в SyncState."""
        from employees.models import Department

        # Сначала пробуем по LdapSyncState
        sync = LdapSyncState.objects.filter(
            model="department",
            ldap_dn=ldap_ou.dn,
        ).first()
        if sync:
            try:
                return Department.objects.get(pk=int(sync.object_pk))
            except (Department.DoesNotExist, ValueError):
                pass
        # Fallback: по совпадению имени
        try:
            return Department.objects.get(name=ldap_ou.ou)
        except Department.DoesNotExist:
            return None

    # --- Кастомные поля для отображения ---

    def ou_display(self, obj):
        """Имя OU с иконкой."""
        return format_html("🏢 {}", obj.ou) if obj.ou else "-"

    ou_display.short_description = "OU (Отдел)"
    ou_display.admin_order_field = "ou"

    def description_short(self, obj):
        """Сокращённое описание."""
        desc = get_ldap_str(obj.description) or ""
        if len(desc) > 80:
            return desc[:80] + "…"
        return desc or format_html('<em style="color:#999;">—</em>')

    description_short.short_description = "Описание"

    def dn_display(self, obj):
        """DN с подсветкой компонентов."""
        if not obj.dn:
            return "-"
        parts = obj.dn.split(",")
        html_parts = []
        for part in parts:
            if part.startswith("OU="):
                html_parts.append(
                    format_html(
                        '<strong style="color:#0066cc;">{}</strong>',
                        part,
                    )
                )
            elif part.startswith("DC="):
                html_parts.append(
                    format_html(
                        '<span style="color:#999;">{}</span>',
                        part,
                    )
                )
            else:
                html_parts.append(part)
        return format_html(",".join(html_parts))

    dn_display.short_description = "Distinguished Name"

    def managed_by_display(self, obj):
        """Сокращённое отображение managedBy в списке."""
        mb = get_ldap_str(obj.managed_by)
        if not mb:
            return format_html('<em style="color:#999;">—</em>')
        # Извлекаем CN из DN
        cn = mb.split(",")[0].replace("CN=", "")
        return format_html("👤 {}", cn)

    managed_by_display.short_description = "Руководитель"

    def managed_by_link(self, obj):
        """Подробная информация о руководителе с ссылкой."""
        mb = get_ldap_str(obj.managed_by)
        if not mb:
            return format_html('<em style="color:#999;">Не назначен</em>')
        # Пробуем найти LdapUser по DN
        try:
            ldap_user = LdapUser.objects.get(dn=mb)
            # Правильный URL pattern для LDAP моделей
            url = reverse(
                "admin:employees_ldapuser_change",
                args=[quote(ldap_user.dn, safe="")],
            )
            return format_html(
                '<a href="{}">👤 {} ({})</a><br>'
                '<code style="font-size:0.85em;color:#666;">{}</code>',
                url,
                ldap_user.display_name or ldap_user.cn,
                ldap_user.sam_account_name or "",
                mb,
            )
        except LdapUser.DoesNotExist:
            return format_html(
                '<code style="color:#666;">{}</code>',
                mb,
            )

    managed_by_link.short_description = "Руководитель (подробно)"

    def django_department_link(self, obj):
        """Ссылка на Django Department в списке."""
        dept = self._find_django_department(obj)
        if dept:
            url = reverse("admin:employees_department_change", args=[dept.pk])
            return format_html(
                '<a href="{}" style="color:#0066cc;">🏢 {}</a>',
                url,
                dept.name,
            )
        return format_html('<em style="color:#999;">—</em>')

    django_department_link.short_description = "Django Department"

    def django_department_info(self, obj):
        """Подробная информация о связи с Django Department."""
        dept = self._find_django_department(obj)
        if not dept:
            return format_html(
                '<div style="padding:10px;background:#fff3cd;'
                'border-left:4px solid #ffc107;">'
                "⚠️ <strong>Не связан с Django Department</strong><br>"
                "<small>Этот LDAP OU не привязан к записи в БД.</small>"
                "</div>"
            )
        sync_state = LdapSyncState.objects.filter(
            model="department",
            object_pk=str(dept.pk),
        ).first()
        return format_html(
            '<div style="padding:10px;background:#d1ecf1;'
            'border-left:4px solid #17a2b8;">'
            "✅ <strong>Связан с Django Department</strong><br>"
            '<table style="margin-top:5px;">'
            "<tr><td><strong>Department ID:</strong></td><td>{}</td></tr>"
            "<tr><td><strong>Название:</strong></td><td>{}</td></tr>"
            "<tr><td><strong>Руководитель:</strong></td><td>{}</td></tr>"
            "<tr><td><strong>Последняя синхронизация:</strong></td>"
            "<td>{}</td></tr>"
            "</table></div>",
            dept.pk,
            dept.name,
            dept.head or "—",
            sync_state.updated_at.strftime("%Y-%m-%d %H:%M:%S")
            if sync_state
            else "—",
        )

    django_department_info.short_description = "Связь с Django"

    # --- Actions ---

    @admin.action(
        description=(
            "🔄 Синхронизировать LDAP → Django "
            "(LDAP как источник истины)"
        )
    )
    def sync_from_ldap_to_django(self, request, queryset):
        """Синхронизирует выбранные OU из LDAP в Django Department."""
        from employees.models import Department

        success_count = 0
        error_count = 0
        warnings = []

        ldap_ous = self._resolve_ldap_ous(request)
        for ldap_ou in ldap_ous:
            ou_name = get_ldap_str(ldap_ou.ou)
            if not ou_name:
                error_count += 1
                warnings.append(f"⚠️ {ldap_ou.dn}: пустое имя OU")
                continue

            try:
                dept = self._find_django_department(ldap_ou)
                if not dept:
                    # Создаём Department
                    dept = Department(name=ou_name)

                dept.description = (
                    get_ldap_str(ldap_ou.description) or dept.description
                )

                # Пытаемся найти руководителя
                mb = get_ldap_str(ldap_ou.managed_by)
                if mb:
                    try:
                        mgr = LdapUser.objects.get(dn=mb)
                        if mgr.employee_number:
                            from employees.models import Employee

                            try:
                                dept.head = Employee.objects.get(
                                    pk=int(mgr.employee_number),
                                )
                            except (Employee.DoesNotExist, ValueError):
                                warnings.append(
                                    f"⚠️ {ou_name}: руководитель Employee #{
                                        mgr.employee_number
                                    } не найден",
                                )
                    except LdapUser.DoesNotExist:
                        warnings.append(
                            f"⚠️ {ou_name}: managedBy DN не найден в LDAP",
                        )

                dept._skip_ldap_sync = True
                dept.save()

                LdapSyncState.objects.update_or_create(
                    model="department",
                    object_pk=str(dept.pk),
                    defaults={
                        "ldap_dn": ldap_ou.dn,
                        "last_sync_dir": "ldap",
                    },
                )
                success_count += 1
            except Exception as e:
                error_count += 1
                self.message_user(
                    request,
                    f"Ошибка синхронизации {ou_name}: {e}",
                    level=messages.ERROR,
                )

        for w in warnings[:10]:
            self.message_user(request, w, level=messages.WARNING)
        if len(warnings) > 10:
            self.message_user(
                request,
                f"...и ещё {len(warnings) - 10} предупреждений",
                level=messages.WARNING,
            )
        if success_count:
            self.message_user(
                request,
                (
                    f"Успешно синхронизировано: {success_count} OU "
                    "(LDAP → Django)"
                ),
                level=messages.SUCCESS,
            )
        if error_count:
            self.message_user(
                request,
                f"Ошибок: {error_count}",
                level=messages.WARNING,
            )

    @admin.action(
        description=(
            "🔄 Синхронизировать Django → LDAP "
            "(Django как источник истины)"
        )
    )
    def sync_from_django_to_ldap(self, request, queryset):
        """Синхронизирует выбранные OU из Django Department в LDAP."""

        success_count = 0
        error_count = 0
        warnings = []

        ldap_ous = self._resolve_ldap_ous(request)
        for ldap_ou in ldap_ous:
            dept = self._find_django_department(ldap_ou)
            if not dept:
                error_count += 1
                warnings.append(
                    f"⚠️ {ldap_ou.dn}: не найден связанный Django Department",
                )
                continue

            missing_fields = []
            if not dept.name or not dept.name.strip():
                missing_fields.append("name (название)")
            if missing_fields:
                warnings.append(
                    f"⚠️ Department #{dept.pk}: отсутствуют поля: {
                        ', '.join(missing_fields)
                    }",
                )

            try:
                ldap_ou.description = dept.description or ""

                # Обновляем managedBy
                if dept.head:
                    sync = LdapSyncState.objects.filter(
                        model="employee",
                        object_pk=str(dept.head.pk),
                    ).first()
                    if sync and sync.ldap_dn:
                        ldap_ou.managed_by = sync.ldap_dn
                    else:
                        warnings.append(
                            f"⚠️ {dept.name}: руководитель не имеет LDAP DN",
                        )
                else:
                    ldap_ou.managed_by = ""

                ldap_ou.save()

                LdapSyncState.objects.update_or_create(
                    model="department",
                    object_pk=str(dept.pk),
                    defaults={
                        "ldap_dn": ldap_ou.dn,
                        "last_sync_dir": "django",
                    },
                )
                success_count += 1
            except Exception as e:
                error_count += 1
                self.message_user(
                    request,
                    f"Ошибка синхронизации {ldap_ou.ou}: {e}",
                    level=messages.ERROR,
                )

        for w in warnings[:10]:
            self.message_user(request, w, level=messages.WARNING)
        if len(warnings) > 10:
            self.message_user(
                request,
                f"...и ещё {len(warnings) - 10} предупреждений",
                level=messages.WARNING,
            )
        if success_count:
            self.message_user(
                request,
                (
                    f"Успешно синхронизировано: {success_count} OU "
                    "(Django → LDAP)"
                ),
                level=messages.SUCCESS,
            )
        if error_count:
            self.message_user(
                request,
                f"Ошибок: {error_count}",
                level=messages.WARNING,
            )

    @admin.action(description="🔍 Показать различия LDAP ↔ Django")
    def show_sync_diff(self, request, queryset):
        """Показывает различия между LDAP OU и Django Department."""
        diffs = []

        ldap_ous = self._resolve_ldap_ous(request)
        for ldap_ou in ldap_ous:
            dept = self._find_django_department(ldap_ou)
            if not dept:
                diffs.append(
                    f"{ldap_ou.ou}: не найден связанный Django Department"
                )
                continue

            ou_diffs = []
            ldap_desc = get_ldap_str(ldap_ou.description) or ""
            if ldap_desc != (dept.description or ""):
                ou_diffs.append(
                    "Описание: "
                    f"LDAP='{ldap_desc[:50]}' vs "
                    f"Django='{(dept.description or '')[:50]}'"
                )

            # Сравниваем руководителя
            mb = get_ldap_str(ldap_ou.managed_by)
            if dept.head:
                head_sync = LdapSyncState.objects.filter(
                    model="employee",
                    object_pk=str(dept.head.pk),
                ).first()
                head_dn = head_sync.ldap_dn if head_sync else None
                if mb != head_dn:
                    ou_diffs.append(
                        f"Руководитель: LDAP='{mb or '—'}' vs Django='{
                            dept.head
                        }'"
                    )
            elif mb:
                ou_diffs.append(
                    f"Руководитель: LDAP='{mb}' vs Django='не назначен'"
                )

            if ou_diffs:
                diffs.append(f"{ldap_ou.ou}: " + ", ".join(ou_diffs))

        if diffs:
            self.message_user(
                request,
                "Найдены различия:\n" + "\n".join(diffs),
                level=messages.WARNING,
            )
        else:
            self.message_user(
                request,
                "Различий не найдено. Все выбранные OU синхронизированы.",
                level=messages.SUCCESS,
            )

    # --- Permissions & overrides ---

    def has_add_permission(self, request):
        """Запрещаем создание OU через админку."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Удаление только суперпользователям."""
        return request.user.is_superuser

    def get_action_choices(self, request, default_choices=None):
        """Убираем стандартный delete_selected.

        ldapdb не поддерживает dn__in.
        """
        if default_choices is None:
            from django.db import models

            default_choices = models.BLANK_CHOICE_DASH
        choices = super().get_action_choices(request, default_choices)
        return [
            c
            for c in choices
            if not (isinstance(c[0], str) and c[0] == "delete_selected")
        ]

    @admin.action(description="🗑️ Удалить выбранные OU из LDAP")
    def delete_selected_ldap(self, request, queryset):
        """Кастомное удаление — обходит dn__in, читает DN из POST."""
        ous = self._resolve_ldap_ous(request)
        if not ous:
            self.message_user(
                request,
                "Не удалось найти выбранные OU.",
                level=messages.WARNING,
            )
            return

        if request.POST.get("post") != "yes":
            from django.template.response import TemplateResponse

            context = {
                **self.admin_site.each_context(request),
                "title": "Подтверждение удаления",
                "objects_name": "LDAP Organizational Units",
                "deletable_objects": [str(o) for o in ous],
                "queryset": ous,
                "opts": self.model._meta,
                "action_checkbox_name": admin.helpers.ACTION_CHECKBOX_NAME,
                "media": self.media,
            }
            request.current_app = self.admin_site.name
            return TemplateResponse(
                request,
                "admin/ldap_delete_confirmation.html",
                context,
            )

        deleted = 0
        for ou_obj in ous:
            try:
                ou_obj.delete()
                deleted += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Ошибка удаления {ou_obj.ou}: {e}",
                    level=messages.ERROR,
                )
        if deleted:
            self.message_user(
                request,
                f"Удалено: {deleted} OU из LDAP.",
                level=messages.SUCCESS,
            )

    def get_queryset(self, request):
        """Базовый queryset."""
        return super().get_queryset(request)

    def changelist_view(self, request, extra_context=None):
        """Переопределяем для фильтрации корневого контейнера."""
        from .orm_models import get_departments_base

        # Сохраняем base DN для использования в get_results
        self._exclude_base_dn = get_departments_base().lower()

        return super().changelist_view(request, extra_context)

    def get_changelist_instance(self, request):
        """Создаём кастомный changelist с фильтрацией."""
        from django.contrib.admin.views.main import ChangeList

        class FilteredChangeList(ChangeList):
            """ChangeList с фильтрацией base DN."""

            def get_results(self, request):
                super().get_results(request)

                # Фильтруем результаты после получения
                if hasattr(self.model_admin, "_exclude_base_dn"):
                    exclude = self.model_admin._exclude_base_dn
                    self.result_list = [
                        obj
                        for obj in self.result_list
                        if obj.dn and obj.dn.lower() != exclude
                    ]
                    self.result_count = len(self.result_list)
                    self.full_result_count = self.result_count

        list_display = self.get_list_display(request)
        list_display_links = self.get_list_display_links(request, list_display)
        list_filter = self.get_list_filter(request)
        search_fields = self.get_search_fields(request)
        list_select_related = self.get_list_select_related(request)

        return FilteredChangeList(
            request,
            self.model,
            list_display,
            list_display_links,
            list_filter,
            self.date_hierarchy,
            search_fields,
            list_select_related,
            self.list_per_page,
            self.list_max_show_all,
            self.list_editable,
            self,
            self.sortable_by,
            self.search_help_text,
        )


@admin.register(LdapOrganizationalUnitGroup)
class LdapOrganizationalUnitGroupAdmin(admin.ModelAdmin):
    """Админка для LDAP групп OU (DEP_*).

    Эти группы содержат всех активных сотрудников отделов.
    Автоматически создаются и синхронизируются при
    синхронизации Department → LDAP.

    Возможности:
    - Просмотр состава группы
    - Связь с Django Department и OU
    - Просмотр членов группы
    """

    def get_urls(self):
        """Переопределяем URLs для корректной работы с DN как PK."""
        urls = super().get_urls()
        return urls

    list_display = (
        "group_display",
        "description_short",
        "members_count",
        "ou_link",
        "django_department_link",
        "when_changed",
    )

    search_fields = (
        "cn",
        "description",
        "sam_account_name",
    )

    readonly_fields = (
        "dn_display",
        "cn",
        "sam_account_name",
        "members_list",
        "ou_info",
        "django_department_info",
    )

    fieldsets = (
        (
            "🔑 Идентификация",
            {
                "fields": (
                    "dn_display",
                    "cn",
                    "sam_account_name",
                )
            },
        ),
        ("📝 Описание", {"fields": ("description",)}),
        ("👥 Состав группы", {"fields": ("members_list",)}),
        ("🏢 Связь с OU", {"fields": ("ou_info",)}),
        ("🔗 Связь с Django", {"fields": ("django_department_info",)}),
    )

    list_per_page = 100

    actions = [
        "show_members_info",
        "sync_members_from_django",
    ]

    def has_add_permission(self, request):
        """Группы создаются автоматически через OU."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Удаление через LDAP OU admin."""
        return False

    def _resolve_ou_groups(self, request):
        """Получает выбранные OU группы по DN из POST данных."""
        selected_dns = request.POST.getlist("_selected_action")
        groups = []
        for dn in selected_dns:
            try:
                group = LdapOrganizationalUnitGroup.objects.get(dn=dn)
                groups.append(group)
            except LdapOrganizationalUnitGroup.DoesNotExist:
                pass
        return groups

    # --- Actions ---

    def show_members_info(self, request, queryset):
        """Показывает информацию об участниках."""
        groups = self._resolve_ou_groups(request)
        for group in groups:
            members = group.member or []
            self.message_user(
                request,
                f"👥 {group.cn}: {len(members)} участников",
                level=messages.INFO,
            )

    show_members_info.short_description = "📋 Показать состав"

    def sync_members_from_django(self, request, queryset):
        """Синхронизирует участников из Django EmployeeDepartment."""
        groups = self._resolve_ou_groups(request)
        if not groups:
            self.message_user(
                request,
                "Не удалось найти выбранные группы.",
                level=messages.WARNING,
            )
            return

        from employees.models import EmployeeDepartment, Department

        for group in groups:
            cn = get_ldap_str(group.cn) or ""
            if not cn.startswith("DEP_"):
                continue
            dept_name = cn[4:]
            try:
                dept = Department.objects.get(name=dept_name)
            except Department.DoesNotExist:
                self.message_user(
                    request,
                    f'⚠️ {cn}: Django Department "{dept_name}" не найден',
                    level=messages.WARNING,
                )
                continue

            active_links = EmployeeDepartment.objects.filter(
                department=dept,
                is_active=True,
            ).select_related("employee")

            member_dns = []
            for link in active_links:
                emp_sync = LdapSyncState.objects.filter(
                    model="employee",
                    object_pk=str(link.employee_id),
                ).first()
                if emp_sync and emp_sync.ldap_dn:
                    member_dns.append(emp_sync.ldap_dn)

            result = group.sync_members(member_dns)
            self.message_user(
                request,
                f"👥 {cn}: +{result['added']}/−{result['removed']} "
                f"(всего: {len(member_dns)})",
                level=messages.SUCCESS,
            )

    sync_members_from_django.short_description = (
        "🔄 Синхронизировать участников из Django"
    )

    def _find_django_department(self, ou_group):
        """Находит Department по имени группы DEP_*."""
        from employees.models import Department

        # Извлекаем имя отдела из CN группы
        cn = get_ldap_str(ou_group.cn) or ""
        if cn.startswith("DEP_"):
            dept_name = cn[4:]  # Убираем префикс DEP_
            try:
                return Department.objects.get(name=dept_name)
            except Department.DoesNotExist:
                pass
        return None

    def _find_ldap_ou(self, ou_group):
        """Находит LdapOrganizationalUnit по DN группы."""
        # DN группы: CN=DEP_IT,OU=IT,OU=Departments,...
        # OU DN: OU=IT,OU=Departments,...
        dn_parts = ou_group.dn.split(",", 1)
        if len(dn_parts) == 2:
            ou_dn = dn_parts[1]
            try:
                return LdapOrganizationalUnit.objects.get(dn=ou_dn)
            except LdapOrganizationalUnit.DoesNotExist:
                pass
        return None

    # --- Кастомные поля для отображения ---

    def group_display(self, obj):
        """Имя группы с иконкой."""
        cn = get_ldap_str(obj.cn) or ""
        return format_html("👥 {}", cn)

    group_display.short_description = "Группа OU"
    group_display.admin_order_field = "cn"

    def description_short(self, obj):
        """Сокращённое описание."""
        desc = get_ldap_str(obj.description) or ""
        if len(desc) > 60:
            return desc[:60] + "…"
        return desc or format_html('<em style="color:#999;">—</em>')

    description_short.short_description = "Описание"

    def members_count(self, obj):
        """Количество участников."""
        members = obj.member or []
        count = len(members)
        if count == 0:
            return format_html('<span style="color:#999;">0</span>')
        return format_html(
            '<strong style="color:#28a745;">{}</strong>',
            count,
        )

    members_count.short_description = "Участников"

    def dn_display(self, obj):
        """DN с подсветкой."""
        if not obj.dn:
            return "-"
        parts = obj.dn.split(",")
        html_parts = []
        for part in parts:
            if part.startswith("CN="):
                html_parts.append(
                    format_html(
                        '<strong style="color:#28a745;">{}</strong>',
                        part,
                    )
                )
            elif part.startswith("OU="):
                html_parts.append(
                    format_html(
                        '<span style="color:#0066cc;">{}</span>',
                        part,
                    )
                )
            elif part.startswith("DC="):
                html_parts.append(
                    format_html(
                        '<span style="color:#999;">{}</span>',
                        part,
                    )
                )
            else:
                html_parts.append(part)
        return format_html(",".join(html_parts))

    dn_display.short_description = "Distinguished Name"

    def members_list(self, obj):
        """Список участников группы с ссылками."""
        members = obj.member or []
        if not members:
            return format_html('<em style="color:#999;">Нет участников</em>')

        html = '<div style="max-height:400px;overflow-y:auto;">'
        html += '<ol style="margin:0;padding-left:20px;">'

        for member_dn in members[:50]:  # Первые 50
            try:
                ldap_user = LdapUser.objects.get(dn=member_dn)
                url = reverse(
                    "admin:employees_ldapuser_change",
                    args=[ldap_user.dn],
                )
                html += format_html(
                    '<li><a href="{}">{} ({})</a></li>',
                    url,
                    ldap_user.display_name or ldap_user.cn or "?",
                    ldap_user.sam_account_name or "",
                )
            except LdapUser.DoesNotExist:
                html += format_html(
                    '<li><code style="color:#dc3545;">{}</code> '
                    "<em>(не найден)</em></li>",
                    member_dn,
                )

        if len(members) > 50:
            html += format_html(
                "<li><em>...и ещё {} участников</em></li>",
                len(members) - 50,
            )

        html += "</ol></div>"
        return format_html(html)

    members_list.short_description = "Участники группы"

    def ou_link(self, obj):
        """Ссылка на родительскую OU."""
        ldap_ou = self._find_ldap_ou(obj)
        if ldap_ou:
            url = reverse(
                "admin:employees_ldaporganizationalunit_change",
                args=[ldap_ou.dn],
            )
            return format_html(
                '<a href="{}" style="color:#0066cc;">🏢 {}</a>',
                url,
                ldap_ou.ou,
            )
        return format_html('<em style="color:#999;">—</em>')

    ou_link.short_description = "OU"

    def ou_info(self, obj):
        """Информация о родительской OU."""
        ldap_ou = self._find_ldap_ou(obj)
        if not ldap_ou:
            return format_html(
                '<div style="padding:10px;background:#f8d7da;'
                'border-left:4px solid #dc3545;">'
                "❌ <strong>OU не найдена</strong><br>"
                "<small>Родительская Organizational Unit не существует "
                "или недоступна.</small>"
                "</div>"
            )

        url = reverse(
            "admin:employees_ldaporganizationalunit_change",
            args=[ldap_ou.dn],
        )
        return format_html(
            '<div style="padding:10px;background:#d1ecf1;'
            'border-left:4px solid #17a2b8;">'
            "✅ <strong>Связана с OU</strong><br>"
            '<table style="margin-top:5px;">'
            "<tr><td><strong>OU:</strong></td>"
            '<td><a href="{}">{}</a></td></tr>'
            "<tr><td><strong>DN:</strong></td>"
            "<td><code>{}</code></td></tr>"
            "</table></div>",
            url,
            ldap_ou.ou,
            ldap_ou.dn,
        )

    ou_info.short_description = "Информация об OU"

    def django_department_link(self, obj):
        """Ссылка на Django Department."""
        dept = self._find_django_department(obj)
        if dept:
            url = reverse(
                "admin:employees_department_change",
                args=[dept.pk],
            )
            return format_html(
                '<a href="{}" style="color:#0066cc;">🏢 {}</a>',
                url,
                dept.name,
            )
        return format_html('<em style="color:#999;">—</em>')

    django_department_link.short_description = "Django Department"

    def django_department_info(self, obj):
        """Информация о Django Department."""
        dept = self._find_django_department(obj)
        if not dept:
            return format_html(
                '<div style="padding:10px;background:#fff3cd;'
                'border-left:4px solid #ffc107;">'
                "⚠️ <strong>Department не найден</strong><br>"
                "<small>Эта группа не связана с отделом в БД.</small>"
                "</div>"
            )

        url = reverse(
            "admin:employees_department_change",
            args=[dept.pk],
        )
        return format_html(
            '<div style="padding:10px;background:#d4edda;'
            'border-left:4px solid #28a745;">'
            "✅ <strong>Связана с Department</strong><br>"
            '<table style="margin-top:5px;">'
            "<tr><td><strong>ID:</strong></td><td>{}</td></tr>"
            "<tr><td><strong>Название:</strong></td>"
            '<td><a href="{}">{}</a></td></tr>'
            "<tr><td><strong>Руководитель:</strong></td>"
            "<td>{}</td></tr>"
            "</table></div>",
            dept.pk,
            url,
            dept.name,
            dept.head or "—",
        )

    django_department_info.short_description = "Связь с Django"


@admin.register(LdapGroup)
class LdapGroupAdmin(admin.ModelAdmin):
    """Админка для LDAP групп (глобальные + роли отделов).

    Охватывает:
    - Глобальные группы: CN=GroupName,OU=Groups,...
    - Роли отделов: CN=ROLE_*,OU=<Dept>,OU=Departments,...

    НЕ охватывает группы отделов DEP_*.
    Для них используется LdapOrganizationalUnitGroupAdmin.

    Возможности:
    - Просмотр состава группы
    - Управление членством
    - Просмотр вложенности групп
    """

    def get_urls(self):
        """Переопределяем URLs для корректной работы с DN как PK."""
        urls = super().get_urls()
        return urls

    list_display = (
        "group_display",
        "sam_account_name",
        "description_short",
        "group_type_display",
        "members_count",
        "when_changed",
    )

    list_filter = (("cn", admin.EmptyFieldListFilter),)

    search_fields = (
        "cn",
        "sam_account_name",
        "description",
    )

    readonly_fields = (
        "dn_display",
        "cn",
        "sam_account_name",
        "when_created",
        "when_changed",
        "members_list",
        "member_of_list",
    )

    fieldsets = (
        (
            "🔑 Идентификация",
            {
                "fields": (
                    "dn_display",
                    "cn",
                    "sam_account_name",
                )
            },
        ),
        ("📝 Описание", {"fields": ("description",)}),
        ("👥 Участники группы", {"fields": ("members_list",)}),
        (
            "📊 Членство в группах",
            {"classes": ("collapse",), "fields": ("member_of_list",)},
        ),
        (
            "📅 Временные метки",
            {
                "classes": ("collapse",),
                "fields": (
                    "when_created",
                    "when_changed",
                ),
            },
        ),
    )

    list_per_page = 100

    actions = [
        "show_group_info",
        "sync_groups_from_ldap",
        "sync_groups_to_ldap",
        "delete_selected_ldap",
    ]

    def has_add_permission(self, request):
        """Группы создаются через GroupService или автоматически."""
        return False

    def has_delete_permission(self, request, obj=None):
        """Удаление через LDAP services."""
        return False

    def _resolve_ldap_groups(self, request):
        """Получает выбранные LDAP группы по DN из POST данных."""
        selected_dns = request.POST.getlist("_selected_action")
        groups = []
        for dn in selected_dns:
            try:
                group = LdapGroup.objects.get(dn=dn)
                groups.append(group)
            except LdapGroup.DoesNotExist:
                pass
        return groups

    # --- Actions ---

    def show_group_info(self, request, queryset):
        """Показывает информацию о выбранных группах."""
        groups = self._resolve_ldap_groups(request)
        if not groups:
            self.message_user(
                request,
                "Не удалось найти выбранные группы.",
                level=messages.WARNING,
            )
            return
        for group in groups:
            members = group.member or []
            member_of = group.member_of or []
            self.message_user(
                request,
                f"👥 {group.cn}: {len(members)} участников, "
                f"входит в {len(member_of)} групп | DN: {group.dn}",
                level=messages.INFO,
            )

    show_group_info.short_description = "📋 Показать информацию"

    def delete_selected_ldap(self, request, queryset):
        """Удаляет выбранные LDAP группы."""
        groups = self._resolve_ldap_groups(request)
        if not groups:
            self.message_user(
                request,
                "Не удалось найти выбранные группы.",
                level=messages.WARNING,
            )
            return

        deleted = 0
        for group in groups:
            try:
                group.delete()
                deleted += 1
            except Exception as e:
                self.message_user(
                    request,
                    f"Ошибка удаления {group.cn}: {e}",
                    level=messages.ERROR,
                )
        if deleted:
            self.message_user(
                request,
                f"Удалено: {deleted} групп из LDAP.",
                level=messages.SUCCESS,
            )

    delete_selected_ldap.short_description = "🗑️ Удалить из LDAP"

    def sync_groups_from_ldap(self, request, queryset):
        """Синхронизирует ВСЕ группы из OU=Groups в Django Group."""
        from employees.ldap.services.group_service import GroupService

        svc = GroupService()
        try:
            created = svc.sync_catalog(throttle_seconds=0)
            self.message_user(
                request,
                f"🔄 LDAP → Django: создано {created} новых Django Group",
                level=messages.SUCCESS,
            )
        except Exception as e:
            self.message_user(
                request,
                f"Ошибка синхронизации: {e}",
                level=messages.ERROR,
            )

    sync_groups_from_ldap.short_description = (
        "⬇️ LDAP → Django (создать Django Group)"
    )

    def sync_groups_to_ldap(self, request, queryset):
        """Синхронизирует Django Groups → LDAP.

        Отсутствующие группы создаются после проверки LDAP.
        """
        from django.contrib.auth.models import Group as DjangoGroup
        from employees.ldap.services.group_service import GroupService

        svc = GroupService()
        groups = self._resolve_ldap_groups(request)

        if not groups:
            # Если ничего не выбрано — синхронизируем все Django Groups
            django_groups = DjangoGroup.objects.all()
            created = 0
            already = 0
            for dg in django_groups:
                # Реальная проверка наличия в LDAP
                exists_in_ldap = LdapGroup.objects.filter(cn=dg.name).exists()
                if exists_in_ldap:
                    ldap_grp = LdapGroup.objects.filter(cn=dg.name).first()
                    LdapSyncState.objects.update_or_create(
                        model="group",
                        object_pk=str(dg.pk),
                        defaults={
                            "ldap_dn": ldap_grp.dn,
                            "last_sync_dir": "ldap",
                        },
                    )
                    already += 1
                    continue

                try:
                    dn = svc.create(cn=dg.name)
                    LdapSyncState.objects.update_or_create(
                        model="group",
                        object_pk=str(dg.pk),
                        defaults={
                            "ldap_dn": dn,
                            "last_sync_dir": "django",
                        },
                    )
                    created += 1
                except Exception as e:
                    self.message_user(
                        request,
                        f"⚠️ {dg.name}: {e}",
                        level=messages.WARNING,
                    )

            self.message_user(
                request,
                f"🔄 Django → LDAP: создано {created}, "
                f"уже существовало {already}",
                level=messages.SUCCESS,
            )
        else:
            # Показываем info о выбранных LDAP-группах
            for group in groups:
                sync = LdapSyncState.objects.filter(
                    model="group",
                    ldap_dn=group.dn,
                ).first()
                if sync:
                    self.message_user(
                        request,
                        f"✅ {group.cn}: связана с Django Group pk={
                            sync.object_pk
                        }",
                        level=messages.INFO,
                    )
                else:
                    self.message_user(
                        request,
                        f"⚠️ {group.cn}: нет связи с Django Group",
                        level=messages.WARNING,
                    )

    sync_groups_to_ldap.short_description = (
        "⬆️ Django → LDAP (создать LDAP Group)"
    )

    # --- Кастомные поля для отображения ---

    def group_display(self, obj):
        """Имя группы с иконкой."""
        cn = get_ldap_str(obj.cn) or ""

        # Определяем тип по DN
        if "OU=Groups" in obj.dn:
            icon = "🌐"  # Глобальная
        elif cn.startswith("ROLE_"):
            icon = "🎭"  # Роль
        elif cn.startswith("DEP_"):
            icon = "🏢"  # Отдел (хотя не должно быть здесь)
        else:
            icon = "👥"

        return format_html("{} {}", icon, cn)

    group_display.short_description = "Группа"
    group_display.admin_order_field = "cn"

    def group_type_display(self, obj):
        """Тип группы по расположению."""
        cn = get_ldap_str(obj.cn) or ""
        dn = obj.dn or ""

        if "OU=Groups" in dn:
            return format_html(
                '<span style="color:#0066cc;">🌐 Глобальная</span>'
            )
        elif cn.startswith("ROLE_"):
            # Извлекаем название отдела из DN
            parts = dn.split(",")
            dept = None
            for i, part in enumerate(parts):
                if part.startswith("OU=") and i > 0:
                    dept = part[3:]
                    break
            if dept:
                return format_html(
                    '<span style="color:#9c27b0;">🎭 Роль ({})</span>', dept
                )
            return format_html('<span style="color:#9c27b0;">🎭 Роль</span>')
        elif cn.startswith("DEP_"):
            return format_html(
                '<span style="color:#ff9800;">🏢 Группа отдела</span>'
            )
        else:
            return format_html('<span style="color:#999;">👥 Группа</span>')

    group_type_display.short_description = "Тип"

    def description_short(self, obj):
        """Сокращённое описание."""
        desc = get_ldap_str(obj.description) or ""
        if len(desc) > 60:
            return desc[:60] + "…"
        return desc or format_html('<em style="color:#999;">—</em>')

    description_short.short_description = "Описание"

    def members_count(self, obj):
        """Количество участников."""
        members = obj.member or []
        count = len(members)
        if count == 0:
            return format_html('<span style="color:#999;">0</span>')
        return format_html(
            '<strong style="color:#28a745;">{}</strong>',
            count,
        )

    members_count.short_description = "Участников"

    def dn_display(self, obj):
        """DN с подсветкой."""
        if not obj.dn:
            return "-"
        parts = obj.dn.split(",")
        html_parts = []
        for part in parts:
            if part.startswith("CN="):
                html_parts.append(
                    format_html(
                        '<strong style="color:#28a745;">{}</strong>',
                        part,
                    )
                )
            elif part.startswith("OU="):
                html_parts.append(
                    format_html(
                        '<span style="color:#0066cc;">{}</span>',
                        part,
                    )
                )
            elif part.startswith("DC="):
                html_parts.append(
                    format_html(
                        '<span style="color:#999;">{}</span>',
                        part,
                    )
                )
            else:
                html_parts.append(part)
        return format_html(",".join(html_parts))

    dn_display.short_description = "Distinguished Name"

    def members_list(self, obj):
        """Список участников группы с ссылками."""
        members = obj.member or []
        if not members:
            return format_html('<em style="color:#999;">Нет участников</em>')

        html = '<div style="max-height:400px;overflow-y:auto;">'
        html += '<ol style="margin:0;padding-left:20px;">'

        for member_dn in members[:100]:  # Первые 100
            # Определяем тип участника
            if member_dn.startswith("CN=") and ",OU=" in member_dn:
                # Пользователь
                try:
                    ldap_user = LdapUser.objects.get(dn=member_dn)
                    url = reverse(
                        "admin:employees_ldapuser_change",
                        args=[quote(ldap_user.dn, safe="")],
                    )
                    html += format_html(
                        '<li>👤 <a href="{}">{} ({})</a></li>',
                        url,
                        ldap_user.display_name or ldap_user.cn or "?",
                        ldap_user.sam_account_name or "",
                    )
                except LdapUser.DoesNotExist:
                    # Может быть группа
                    try:
                        ldap_group = LdapGroup.objects.get(dn=member_dn)
                        url = reverse(
                            "admin:employees_ldapgroup_change",
                            args=[quote(ldap_group.dn, safe="")],
                        )
                        html += format_html(
                            '<li>👥 <a href="{}">{}</a></li>',
                            url,
                            ldap_group.cn or "?",
                        )
                    except LdapGroup.DoesNotExist:
                        html += format_html(
                            '<li><code style="color:#dc3545;">{}</code> '
                            "<em>(не найден)</em></li>",
                            member_dn,
                        )
            else:
                html += format_html(
                    "<li><code>{}</code></li>",
                    member_dn,
                )

        if len(members) > 100:
            html += format_html(
                "<li><em>...и ещё {} участников</em></li>",
                len(members) - 100,
            )

        html += "</ol></div>"
        return format_html(html)

    members_list.short_description = "Участники группы"

    def member_of_list(self, obj):
        """Список групп, в которых состоит эта группа."""
        member_of = obj.member_of or []
        if not member_of:
            return format_html(
                '<em style="color:#999;">Не состоит в группах</em>'
            )

        html = '<div style="max-height:300px;overflow-y:auto;">'
        html += '<ul style="margin:0;padding-left:20px;">'

        for group_dn in member_of[:50]:
            # Извлекаем CN из DN
            cn = group_dn.split(",")[0].replace("CN=", "")
            try:
                parent_group = LdapGroup.objects.get(dn=group_dn)
                url = reverse(
                    "admin:employees_ldapgroup_change",
                    args=[quote(parent_group.dn, safe="")],
                )
                html += format_html(
                    '<li><a href="{}">👥 {}</a></li>',
                    url,
                    parent_group.cn or cn,
                )
            except LdapGroup.DoesNotExist:
                html += format_html(
                    "<li><code>{}</code></li>",
                    cn,
                )

        if len(member_of) > 50:
            html += format_html(
                "<li><em>...и ещё {} групп</em></li>",
                len(member_of) - 50,
            )

        html += "</ul></div>"
        return format_html(html)

    member_of_list.short_description = "Членство в группах"
