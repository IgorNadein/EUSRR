# backend/employees/admin.py

from django import forms
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.forms import ReadOnlyPasswordHashField, AdminPasswordChangeForm
from django.contrib.auth.models import Group, Permission
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from simple_history.admin import SimpleHistoryAdmin

from .models import (
    Employee,
    EmployeeAction,
    Department,
    DepartmentRole,
    EmployeeDepartment,
    Position,
    Skill,
    LdapSyncState,
)

# =========================
#   Формы для кастомного User (Employee)
# =========================


class LdapSyncedFilter(admin.SimpleListFilter):
    """Фильтр для отображения сотрудников по состоянию LDAP синхронизации."""
    
    title = "Статус LDAP синхронизации"
    parameter_name = "ldap_synced"
    
    def lookups(self, request, model_admin):
        return (
            ("yes", "Есть запись синхронизации"),
            ("no", "Нет записи синхронизации"),
        )
    
    def queryset(self, request, queryset):
        from django.db.models import Exists, OuterRef
        
        if self.value() == "yes":
            # Показываем только тех, у кого есть запись синхронизации
            return queryset.filter(
                Exists(
                    LdapSyncState.objects.filter(
                        model="employee",
                        object_pk=OuterRef("pk")
                    )
                )
            )
        elif self.value() == "no":
            # Показываем только тех, у кого нет записи синхронизации
            return queryset.exclude(
                Exists(
                    LdapSyncState.objects.filter(
                        model="employee",
                        object_pk=OuterRef("pk")
                    )
                )
            )
        return queryset


class EmployeeCreationForm(forms.ModelForm):
    """
    Создание сотрудника в админке: логин — email, без username.
    """
    password1 = forms.CharField(label="Пароль", widget=forms.PasswordInput)
    password2 = forms.CharField(label="Подтверждение пароля", widget=forms.PasswordInput)

    class Meta:
        model = Employee
        fields = ("email", "first_name", "last_name", "phone_number")

    def clean_password2(self):
        p1 = self.cleaned_data.get("password1") or ""
        p2 = self.cleaned_data.get("password2") or ""
        if not p1:
            raise forms.ValidationError("Пароль обязателен")
        if p1 != p2:
            raise forms.ValidationError("Пароли не совпадают")
        return p2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data["password1"])
        # При создании через админку обычно активируем и помечаем e-mail подтверждённым
        if not user.is_active:
            user.is_active = True
        if not user.email_verified:
            user.email_verified = True
        if commit:
            user.save()
        return user


class EmployeeChangeForm(forms.ModelForm):
    """
    Редактирование сотрудника: пароль только для чтения (смена пароля — отдельной кнопкой).
    """
    password = ReadOnlyPasswordHashField(
        label="Хэш пароля",
        help_text=(
            "Пароль хранится в виде хэша — посмотреть его невозможно. "
            "Используйте кнопку «Изменить пароль» выше."
        ),
        required=False,
    )

    class Meta:
        model = Employee
        fields = (
            "email",
            "password",
            "first_name",
            "last_name",
            "patronymic",
            "gender",
            "birth_date",
            "avatar",
            "phone_number",
            "telegram",
            "whatsapp",
            "wechat",
            "position",
            "skills",
            "is_active",
            "email_verified",
            "is_staff",
            "is_superuser",
            "groups",
            "user_permissions",
            "last_login",
        )

    def clean_password(self):
        # Возвращаем исходное значение (хэш), даже если пользователь ничего не ввёл
        return self.initial.get("password")


# =========================
#   Инлайны
# =========================

class EmployeeDepartmentInline(admin.TabularInline):
    """
    Принадлежности сотрудника к отделам (видно из карточки сотрудника).
    """
    model = EmployeeDepartment
    fk_name = "employee"
    extra = 0
    autocomplete_fields = ("department", "role")
    fields = ("department", "role", "is_active", "date_from", "date_to")
    show_change_link = True



class DepartmentMembershipInline(admin.TabularInline):
    """
    Состав отдела — список участников прямо в карточке отдела.
    """
    model = EmployeeDepartment
    fk_name = "department"
    extra = 0
    autocomplete_fields = ("employee", "role")
    fields = ("employee", "role", "is_active", "date_from", "date_to")
    show_change_link = True


# =========================
#   Админки моделей
# =========================

@admin.register(Employee)
class EmployeeAdmin(DjangoUserAdmin):
    """
    Кастомный UserAdmin для модели Employee.
    Включает стандартную кнопку «Изменить пароль».
    """
    add_form = EmployeeCreationForm
    form = EmployeeChangeForm
    model = Employee

    # Включаем стандартную форму смены пароля и шаблон,
    # который показывает ссылку «Изменить пароль» на форме изменения пользователя.
    change_password_form = AdminPasswordChangeForm
    change_form_template = "admin/employees/employee/change_form.html"

    list_display = (
        "email",
        "last_name",
        "first_name",
        "phone_number",
        "position",
        "is_active",
        "email_verified",
        "is_ldap_managed",
        "ldap_sync_status",
        "is_staff",
    )
    list_filter = (
        "is_active",
        "email_verified",
        "is_staff",
        "is_superuser",
        "is_ldap_managed",
        LdapSyncedFilter,
        "position",
        "groups",
    )
    search_fields = ("email", "first_name", "last_name", "phone_number")
    ordering = ("last_name", "first_name")
    list_select_related = ("position",)

    filter_horizontal = ("groups", "user_permissions", "skills")

    readonly_fields = (
        "last_login",
        "created_at",
        "updated_at",
        "ldap_sync_info",
        "email_activation_code",
        "sms_activation_code",
    )
    
    def ldap_sync_status(self, obj):
        """Краткий статус LDAP синхронизации для списка."""
        if not obj.pk:
            return "-"
        
        from django.utils.html import format_html
        import logging
        logger = logging.getLogger(__name__)
        
        # Если не управляется LDAP
        if not obj.is_ldap_managed:
            return format_html('<span style="color: gray;">Локальный</span>')
        
        try:
            # Логируем попытку поиска
            logger.debug(
                f"[ldap_sync_status] Searching for employee {obj.pk} "
                f"(email: {obj.email})"
            )
            
            sync_state = LdapSyncState.objects.filter(
                model="employee",
                object_pk=str(obj.pk)
            ).first()
            
            logger.debug(
                f"[ldap_sync_status] Employee {obj.pk}: "
                f"sync_state={'found' if sync_state else 'not found'}"
            )
            
            if not sync_state:
                # Попробуем найти любые записи для этого employee
                all_syncs = LdapSyncState.objects.filter(
                    model="employee"
                ).values_list("object_pk", flat=True)
                logger.warning(
                    f"[ldap_sync_status] No sync record for employee {obj.pk}. "
                    f"All employee object_pks in sync table: {list(all_syncs)}"
                )
                
                # Создаем ссылку для быстрого создания записи
                from django.urls import reverse
                create_url = reverse('admin:employees_ldapsyncstate_add')
                
                return format_html(
                    '<span style="color: red;" title="ID: {} - Нет записи синхронизации. Кликните для создания.">'
                    '<a href="{}?model=employee&object_pk={}" style="color: red;">❌ Нет записи (ID: {})</a>'
                    '</span>',
                    obj.pk,
                    create_url,
                    obj.pk,
                    obj.pk
                )
            
            # Проверяем полноту данных
            has_guid = bool(sync_state.ldap_guid)
            has_dn = bool(sync_state.ldap_dn)
            has_updated = bool(sync_state.updated_at)
            
            # Полные данные
            if has_guid and has_dn and has_updated:
                return format_html(
                    '✅ <span title="ID: {}\nGUID: {}\nDN: {}">{}</span>',
                    obj.pk,
                    sync_state.ldap_guid,
                    sync_state.ldap_dn[:80] + '...' if len(sync_state.ldap_dn) > 80 else sync_state.ldap_dn,
                    sync_state.updated_at.strftime("%d.%m.%Y %H:%M")
                )
            # Неполные данные
            elif has_updated:
                missing = []
                if not has_guid:
                    missing.append("GUID")
                if not has_dn:
                    missing.append("DN")
                
                return format_html(
                    '⚠️ <span title="ID: {}\nОтсутствует: {}">{}</span>',
                    obj.pk,
                    ", ".join(missing),
                    sync_state.updated_at.strftime("%d.%m.%Y %H:%M")
                )
            else:
                return format_html(
                    '<span style="color: orange;" title="ID: {} - Нет даты обновления">⚠️ Неполные данные</span>',
                    obj.pk
                )
        except Exception as e:
            logger.exception(
                f"[ldap_sync_status] Error for employee {obj.pk}: {e}"
            )
            return format_html(
                '<span style="color: red;" title="ID: {} - Ошибка: {}">❌ Ошибка</span>',
                obj.pk,
                str(e)
            )
    
    ldap_sync_status.short_description = "LDAP статус"
    ldap_sync_status.admin_order_field = "id"  # Сортировка по ID

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Личная информация", {
            "fields": (
                "first_name",
                "last_name",
                "patronymic",
                "gender",
                "birth_date",
                "avatar",
            )
        }),
        ("Контакты", {
            "fields": ("phone_number", "telegram", "whatsapp", "wechat")
        }),
        ("Работа", {
            "fields": ("position", "skills")
        }),
        ("Права и статусы", {
            "fields": (
                "is_active",
                "email_verified",
                "email_activation_code",
                "sms_activation_code",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            )
        }),
        ("LDAP", {
            "fields": ("is_ldap_managed", "ldap_sync_info"),
            "classes": ("collapse",),
        }),
        ("Служебное", {"fields": ("last_login", "created_at", "updated_at")}),
    )
    
    def ldap_sync_info(self, obj):
        """Отображает информацию о состоянии синхронизации LDAP."""
        if not obj.pk:
            return "-"
        
        try:
            sync_state = LdapSyncState.objects.filter(
                model="employee",
                object_pk=str(obj.pk)
            ).first()
            
            if not sync_state:
                return "Нет записи синхронизации"
            
            from django.utils.html import format_html
            from django.urls import reverse
            
            # Ссылка на запись синхронизации в админке
            sync_url = reverse(
                'admin:employees_ldapsyncstate_change',
                args=[sync_state.pk]
            )
            
            info = [
                format_html(
                    '<a href="{}" target="_blank">📋 Открыть запись синхронизации</a>',
                    sync_url
                )
            ]
            
            if sync_state.ldap_dn:
                info.append(f"<b>DN:</b> {sync_state.ldap_dn}")
            if sync_state.ldap_guid:
                info.append(f"<b>GUID:</b> {sync_state.ldap_guid}")
            if sync_state.last_sync_dir:
                info.append(f"<b>Направление:</b> {sync_state.last_sync_dir}")
            if sync_state.last_ldap_modify_ts:
                info.append(
                    f"<b>LDAP изменен:</b> {sync_state.last_ldap_modify_ts}"
                )
            if sync_state.last_django_modify_ts:
                info.append(
                    f"<b>Django изменен:</b> {sync_state.last_django_modify_ts}"
                )
            if sync_state.updated_at:
                info.append(f"<b>Обновлено:</b> {sync_state.updated_at}")
            
            return format_html("<br>".join(info)) if info else "-"
        except Exception as e:
            return f"Ошибка: {e}"
    
    ldap_sync_info.short_description = "Состояние LDAP синхронизации"

    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": (
                "email",
                "first_name",
                "last_name",
                "phone_number",
                "whatsapp",
                "position",
                "password1",
                "password2",
                "is_active",
                "email_verified",
                "is_staff",
                "is_superuser",
                "groups",
                "user_permissions",
            ),
        }),
    )

    inlines = [EmployeeDepartmentInline]
    
    actions = [
        "create_ldap_sync_records",
        "check_ldap_sync_status",
        "sync_from_django_to_ldap",
        "sync_from_ldap_to_django",
        "show_sync_diff",
    ]
    
    def create_ldap_sync_records(self, request, queryset):
        """Создать записи синхронизации для выбранных сотрудников."""
        created_count = 0
        already_exists = 0
        
        for employee in queryset:
            if not employee.is_ldap_managed:
                continue
            
            sync_state, created = LdapSyncState.objects.get_or_create(
                model="employee",
                object_pk=str(employee.pk),
                defaults={
                    "last_sync_dir": "django",
                }
            )
            
            if created:
                created_count += 1
            else:
                already_exists += 1
        
        if created_count:
            self.message_user(
                request,
                f"Создано {created_count} записей синхронизации",
                level="success"
            )
        if already_exists:
            self.message_user(
                request,
                f"У {already_exists} сотрудников уже есть записи синхронизации",
                level="info"
            )
        if created_count == 0 and already_exists == 0:
            self.message_user(
                request,
                "Выбраны только локальные пользователи (не управляются LDAP)",
                level="warning"
            )
    
    create_ldap_sync_records.short_description = "Создать записи LDAP синхронизации"
    
    def check_ldap_sync_status(self, request, queryset):
        """Проверить статус LDAP синхронизации для выбранных сотрудников."""
        ldap_managed = queryset.filter(is_ldap_managed=True)
        ldap_count = ldap_managed.count()
        
        if ldap_count == 0:
            self.message_user(
                request,
                "Среди выбранных нет пользователей, управляемых через LDAP",
                level="warning"
            )
            return
        
        # Проверяем наличие записей синхронизации
        sync_records = LdapSyncState.objects.filter(
            model="employee",
            object_pk__in=[str(e.pk) for e in ldap_managed]
        )
        
        has_sync = sync_records.count()
        missing_sync = ldap_count - has_sync
        
        # Проверяем полноту данных
        complete = sync_records.filter(
            ldap_guid__isnull=False,
            ldap_dn__isnull=False
        ).exclude(ldap_dn="").count()
        
        incomplete = has_sync - complete
        
        message = f"Статус LDAP синхронизации:\n"
        message += f"• Управляются LDAP: {ldap_count}\n"
        message += f"• Есть запись синхронизации: {has_sync}\n"
        message += f"• Нет записи синхронизации: {missing_sync}\n"
        message += f"• Полные данные: {complete}\n"
        message += f"• Неполные данные: {incomplete}"
        
        self.message_user(request, message, level="info")
    
    check_ldap_sync_status.short_description = "Проверить статус LDAP синхронизации"
    
    @admin.action(description='🔄 Синхронизировать Django → LDAP (создать/обновить в Active Directory)')
    def sync_from_django_to_ldap(self, request, queryset):
        """Создает или обновляет пользователей в LDAP из Django.
        
        Django считается источником истины - данные из БД будут
        записаны в Active Directory (создание или обновление).
        """
        import logging
        from employees.ldap.services import UserService
        from employees.ldap.orm_models import LdapUser
        from employees.ldap.utils.ldap_utils import get_ldap_str
        
        logger = logging.getLogger(__name__)
        
        success_count = 0
        created_count = 0
        updated_count = 0
        error_count = 0
        
        service = UserService()
        
        for employee in queryset:
            logger.info(f"[sync_from_django_to_ldap] Начинаем обработку employee ID={employee.pk}, email={employee.email}")
            try:
                # Ищем существующего LDAP пользователя
                ldap_user = None
                logger.info(f"[sync_from_django_to_ldap] Employee {employee.pk}: is_ldap_managed={employee.is_ldap_managed}")
                
                if employee.is_ldap_managed:
                    # Пробуем найти по employee_number
                    logger.info(f"[sync_from_django_to_ldap] Employee {employee.pk}: поиск в LDAP по employee_number={employee.pk}")
                    ldap_user = LdapUser.objects.filter(
                        employee_number=str(employee.pk)
                    ).first()
                    if ldap_user:
                        logger.info(f"[sync_from_django_to_ldap] Employee {employee.pk}: найден LDAP user с DN={ldap_user.dn}")
                    else:
                        logger.info(f"[sync_from_django_to_ldap] Employee {employee.pk}: не найден по employee_number")
                
                if ldap_user:
                    # ОБНОВЛЕНИЕ существующего LDAP пользователя
                    logger.info(f"[sync_from_django_to_ldap] Employee {employee.pk}: LDAP пользователь существует, начинаем проверку изменений")
                    try:
                        changes = {}
                        
                        ldap_first = get_ldap_str(ldap_user.given_name)
                        logger.debug(f"[sync_from_django_to_ldap] Employee {employee.pk}: сравнение given_name: LDAP='{ldap_first}' vs Django='{employee.first_name}'")
                        if ldap_first != employee.first_name:
                            changes['first_name'] = employee.first_name
                            
                        ldap_last = get_ldap_str(ldap_user.sn)
                        logger.debug(f"[sync_from_django_to_ldap] Employee {employee.pk}: сравнение sn: LDAP='{ldap_last}' vs Django='{employee.last_name}'")
                        if ldap_last != employee.last_name:
                            changes['last_name'] = employee.last_name
                            
                        ldap_email = get_ldap_str(ldap_user.mail)
                        logger.debug(f"[sync_from_django_to_ldap] Employee {employee.pk}: сравнение mail: LDAP='{ldap_email}' vs Django='{employee.email}'")
                        if ldap_email != employee.email:
                            changes['email'] = employee.email
                        
                        ldap_phone = get_ldap_str(ldap_user.telephone_number or ldap_user.mobile)
                        logger.debug(f"[sync_from_django_to_ldap] Employee {employee.pk}: сравнение phone: LDAP='{ldap_phone}' vs Django='{employee.phone_number}'")
                        if employee.phone_number and ldap_phone != employee.phone_number:
                            changes['phone_number'] = employee.phone_number
                        
                        logger.info(f"[sync_from_django_to_ldap] Employee {employee.pk}: обнаружено изменений: {len(changes)} -> {list(changes.keys())}")
                        
                        if changes:
                            logger.info(f"[sync_from_django_to_ldap] Employee {employee.pk}: вызов service.update_user с изменениями: {changes}")
                            service.update_user(employee, changes)
                            logger.info(f"[sync_from_django_to_ldap] Employee {employee.pk}: успешно обновлен в LDAP")
                            updated_count += 1
                            
                            # Обновляем sync state
                            logger.info(f"[sync_from_django_to_ldap] Employee {employee.pk}: обновление LdapSyncState")
                            LdapSyncState.objects.update_or_create(
                                model='employee',
                                object_pk=str(employee.pk),
                                defaults={
                                    'ldap_dn': ldap_user.dn,
                                    'last_sync_dir': 'django',
                                }
                            )
                            logger.info(f"[sync_from_django_to_ldap] Employee {employee.pk}: LdapSyncState обновлен")
                        else:
                            logger.info(f"[sync_from_django_to_ldap] Employee {employee.pk}: изменений не обнаружено, уже синхронизирован")
                            success_count += 1  # Уже синхронизирован
                    except Exception as e:
                        logger.exception(f"[sync_from_django_to_ldap] Employee {employee.pk}: ошибка обновления в LDAP")
                        error_count += 1
                        self.message_user(
                            request,
                            f'Ошибка обновления {employee.email} в LDAP: {e}',
                            level=messages.ERROR
                        )
                else:
                    # СОЗДАНИЕ нового LDAP пользователя
                    logger.info(f"[sync_from_django_to_ldap] Employee {employee.pk}: LDAP пользователь не найден, создаем новый")
                    try:
                        # Генерируем временный пароль
                        import secrets
                        from employees.ldap.domain.dtos import DirectoryUserDTO
                        from employees.ldap.utils.phone_utils import normalize_phone
                        
                        temp_password = secrets.token_urlsafe(16)
                        logger.info(f"[sync_from_django_to_ldap] Employee {employee.pk}: временный пароль сгенерирован")
                        
                        phone_e164 = None
                        if employee.phone_number:
                            phone_e164 = normalize_phone(employee.phone_number)
                            logger.info(f"[sync_from_django_to_ldap] Employee {employee.pk}: телефон нормализован: {phone_e164}")
                        
                        logger.info(f"[sync_from_django_to_ldap] Employee {employee.pk}: создание DirectoryUserDTO")
                        dto = DirectoryUserDTO(
                            first_name=employee.first_name,
                            last_name=employee.last_name,
                            email=employee.email,
                            phone_e164=phone_e164,
                            department_dn=None,
                            group_cns=[],
                            initial_password=temp_password,
                        )
                        logger.info(f"[sync_from_django_to_ldap] Employee {employee.pk}: DTO создан: {dto}")
                        
                        # Создаем через сервис
                        logger.info(f"[sync_from_django_to_ldap] Employee {employee.pk}: вызов service.create_user(dto)")
                        service.create_user(dto)
                        logger.info(f"[sync_from_django_to_ldap] Employee {employee.pk}: LDAP пользователь успешно создан")
                        
                        created_count += 1
                        employee.is_ldap_managed = True
                        employee.save(update_fields=['is_ldap_managed'])
                        logger.info(f"[sync_from_django_to_ldap] Employee {employee.pk}: is_ldap_managed установлен в True")
                        
                        self.message_user(
                            request,
                            f'✅ Создан LDAP пользователь для {employee.email}. '
                            f'Временный пароль: {temp_password}',
                            level=messages.SUCCESS
                        )
                    except Exception as e:
                        logger.exception(f"[sync_from_django_to_ldap] Employee {employee.pk}: ошибка создания в LDAP")
                        error_count += 1
                        self.message_user(
                            request,
                            f'Ошибка создания {employee.email} в LDAP: {e}',
                            level=messages.ERROR
                        )
            except Exception as e:
                logger.exception(f"[sync_from_django_to_ldap] Employee {employee.pk}: необработанное исключение на верхнем уровне")
                error_count += 1
                self.message_user(
                    request,
                    f'Ошибка обработки {employee.email}: {e}',
                    level=messages.ERROR
                )
        
        # Итоговое сообщение
        if created_count > 0:
            self.message_user(
                request,
                f'✅ Создано в LDAP: {created_count} пользователей',
                level=messages.SUCCESS
            )
        if updated_count > 0:
            self.message_user(
                request,
                f'🔄 Обновлено в LDAP: {updated_count} пользователей',
                level=messages.SUCCESS
            )
        if success_count > 0:
            self.message_user(
                request,
                f'✓ Уже синхронизировано: {success_count} пользователей',
                level=messages.INFO
            )
        if error_count > 0:
            self.message_user(
                request,
                f'❌ Ошибок: {error_count}',
                level=messages.WARNING
            )
    
    @admin.action(description='🔄 Синхронизировать LDAP → Django (обновить из Active Directory)')
    def sync_from_ldap_to_django(self, request, queryset):
        """Обновляет Django пользователей из LDAP.
        
        LDAP считается источником истины - данные из Active Directory
        перезапишут данные в Django Employee.
        """
        from employees.ldap.orm_models import LdapUser
        from employees.ldap.utils.ldap_utils import get_ldap_str
        
        success_count = 0
        error_count = 0
        not_in_ldap = 0
        
        for employee in queryset:
            if not employee.is_ldap_managed:
                not_in_ldap += 1
                continue
            
            try:
                # Ищем LDAP пользователя
                ldap_user = LdapUser.objects.filter(
                    employee_number=str(employee.pk)
                ).first()
                
                if not ldap_user:
                    # Попробуем по email
                    ldap_user = LdapUser.objects.filter(
                        mail=employee.email
                    ).first()
                
                if not ldap_user:
                    error_count += 1
                    self.message_user(
                        request,
                        f'❌ {employee.email}: не найден в LDAP',
                        level=messages.WARNING
                    )
                    continue
                
                # Обновляем Django из LDAP
                updated_fields = []
                
                ldap_first = get_ldap_str(ldap_user.given_name)
                if ldap_first and ldap_first != employee.first_name:
                    employee.first_name = ldap_first
                    updated_fields.append('first_name')
                
                ldap_last = get_ldap_str(ldap_user.sn)
                if ldap_last and ldap_last != employee.last_name:
                    employee.last_name = ldap_last
                    updated_fields.append('last_name')
                
                ldap_email = get_ldap_str(ldap_user.mail)
                if ldap_email and ldap_email != employee.email:
                    employee.email = ldap_email
                    updated_fields.append('email')
                
                ldap_phone = get_ldap_str(ldap_user.telephone_number or ldap_user.mobile)
                if ldap_phone and ldap_phone != employee.phone_number:
                    employee.phone_number = ldap_phone
                    updated_fields.append('phone_number')
                
                if updated_fields:
                    employee.save(update_fields=updated_fields)
                
                # Обновляем LdapSyncState
                LdapSyncState.objects.update_or_create(
                    model='employee',
                    object_pk=str(employee.pk),
                    defaults={
                        'ldap_dn': ldap_user.dn,
                        'ldap_guid': None,  # objectGUID удален из модели
                        'last_sync_dir': 'ldap',
                    }
                )
                
                success_count += 1
                
            except Exception as e:
                error_count += 1
                self.message_user(
                    request,
                    f'Ошибка синхронизации {employee.email}: {e}',
                    level=messages.ERROR
                )
        
        if success_count:
            self.message_user(
                request,
                f'✅ Успешно синхронизировано: {success_count} пользователей (LDAP → Django)',
                level=messages.SUCCESS
            )
        if not_in_ldap:
            self.message_user(
                request,
                f'ℹ️ Пропущено локальных пользователей: {not_in_ldap}',
                level=messages.INFO
            )
        if error_count:
            self.message_user(
                request,
                f'❌ Ошибок: {error_count}',
                level=messages.WARNING
            )
    
    @admin.action(description='🔍 Показать различия Django ↔ LDAP')
    def show_sync_diff(self, request, queryset):
        """Показывает различия между Django и LDAP для выбранных пользователей."""
        from employees.ldap.orm_models import LdapUser
        from employees.ldap.utils.ldap_utils import get_ldap_str
        
        diffs = []
        no_ldap_count = 0
        
        for employee in queryset:
            if not employee.is_ldap_managed:
                continue
            
            try:
                # Ищем LDAP пользователя
                ldap_user = LdapUser.objects.filter(
                    employee_number=str(employee.pk)
                ).first()
                
                if not ldap_user:
                    ldap_user = LdapUser.objects.filter(mail=employee.email).first()
                
                if not ldap_user:
                    no_ldap_count += 1
                    diffs.append(f"❌ {employee.email}: не найден в LDAP")
                    continue
                
                user_diffs = []
                
                # Сравниваем поля
                ldap_first = get_ldap_str(ldap_user.given_name)
                if ldap_first != employee.first_name:
                    user_diffs.append(
                        f"Имя: Django='{employee.first_name}' vs LDAP='{ldap_first}'"
                    )
                
                ldap_last = get_ldap_str(ldap_user.sn)
                if ldap_last != employee.last_name:
                    user_diffs.append(
                        f"Фамилия: Django='{employee.last_name}' vs LDAP='{ldap_last}'"
                    )
                
                ldap_email = get_ldap_str(ldap_user.mail)
                if ldap_email != employee.email:
                    user_diffs.append(
                        f"Email: Django='{employee.email}' vs LDAP='{ldap_email}'"
                    )
                
                ldap_phone = get_ldap_str(ldap_user.telephone_number or ldap_user.mobile)
                if employee.phone_number and ldap_phone and ldap_phone != employee.phone_number:
                    user_diffs.append(
                        f"Телефон: Django='{employee.phone_number}' vs LDAP='{ldap_phone}'"
                    )
                
                if user_diffs:
                    diffs.append(
                        f"⚠️ {employee.email}: " + " | ".join(user_diffs)
                    )
                else:
                    diffs.append(f"✅ {employee.email}: данные совпадают")
                    
            except Exception as e:
                diffs.append(f"❌ {employee.email}: ошибка сравнения - {e}")
        
        if diffs:
            message = "Результаты сравнения Django ↔ LDAP:\n\n" + "\n".join(diffs)
            self.message_user(request, message, level=messages.INFO)
        else:
            self.message_user(
                request,
                "Выбраны только локальные пользователи (не управляются LDAP)",
                level=messages.WARNING
            )


@admin.register(Position)
class PositionAdmin(SimpleHistoryAdmin):
    list_display = ("name", "description")
    search_fields = ("name", "description", "ldap_group_dn")
    filter_horizontal = ("groups",)
    
    fieldsets = (
        (None, {"fields": ("name", "description")}),
        ("Права", {"fields": ("groups",)}),
        ("LDAP", {
            "fields": ("ldap_group_dn",),
            "classes": ("collapse",),
        }),
    )


@admin.register(EmployeeAction)
class EmployeeActionAdmin(SimpleHistoryAdmin):
    list_display = ("employee", "action", "date")
    list_filter = ("action",)
    search_fields = ("employee__first_name", "employee__last_name", "comment")
    autocomplete_fields = ("employee",)
    date_hierarchy = "date"


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    list_display = ("name", "head", "head_appointed_at", "created_at")
    list_filter = ("head",)
    search_fields = ("name", "description", "ldap_group_dn")
    autocomplete_fields = ("head",)
    readonly_fields = ("created_at", "head_appointed_at")
    inlines = [DepartmentMembershipInline]
    
    fieldsets = (
        (None, {"fields": ("name", "description")}),
        ("Руководство", {
            "fields": ("head", "head_appointed_at"),
        }),
        ("LDAP", {
            "fields": ("ldap_group_dn",),
            "classes": ("collapse",),
        }),
        ("Служебное", {"fields": ("created_at",)}),
    )


@admin.register(DepartmentRole)
class DepartmentRoleAdmin(admin.ModelAdmin):
    list_display = ("name", "department")
    list_filter = ("department",)
    search_fields = ("name", "department__name", "ldap_group_dn")
    autocomplete_fields = ("department",)
    filter_horizontal = ("scoped_permissions",)
    
    fieldsets = (
        (None, {"fields": ("department", "name")}),
        ("Права", {"fields": ("scoped_permissions",)}),
        ("LDAP", {
            "fields": ("ldap_group_dn",),
            "classes": ("collapse",),
        }),
    )

@admin.register(EmployeeDepartment)
class EmployeeDepartmentAdmin(admin.ModelAdmin):
    list_display = ("employee", "department", "role", "is_active", "date_from", "date_to")
    list_filter = ("is_active", "department", "role")
    search_fields = ("employee__first_name", "employee__last_name", "department__name")
    autocomplete_fields = ("employee", "department", "role")
    date_hierarchy = "date_from"


@admin.register(Skill)
class SkillAdmin(admin.ModelAdmin):
    list_display = ("name",)
    search_fields = ("name",)


# Полезно иметь Permission в админке
@admin.register(Permission)
class PermissionAdmin(admin.ModelAdmin):
    list_display = ("name", "codename", "content_type")
    list_filter = ("content_type",)
    search_fields = ("name", "codename")


@admin.register(LdapSyncState)
class LdapSyncStateAdmin(admin.ModelAdmin):
    """Админка для просмотра состояния синхронизации LDAP."""
    
    list_display = (
        "model",
        "object_pk",
        "ldap_dn_short",
        "ldap_guid",
        "last_sync_dir",
        "updated_at",
    )
    list_filter = ("model", "last_sync_dir")
    search_fields = ("object_pk", "ldap_dn", "ldap_guid")
    readonly_fields = ("updated_at",)
    
    fields = (
        "model",
        "object_pk",
        "ldap_dn",
        "ldap_guid",
        "last_ldap_modify_ts",
        "last_django_modify_ts",
        "last_sync_dir",
        "data_hash",
        "updated_at",
    )
    
    def ldap_dn_short(self, obj):
        """Показываем сокращенную версию DN для удобства."""
        if obj.ldap_dn:
            return obj.ldap_dn[:50] + "..." if len(obj.ldap_dn) > 50 else obj.ldap_dn
        return "-"
    ldap_dn_short.short_description = "LDAP DN"
    
    def has_add_permission(self, request):
        """Разрешаем создание записей для отсутствующих пользователей."""
        return True
    
    def has_delete_permission(self, request, obj=None):
        """Разрешаем удаление для очистки."""
        return True
