"""Restricted operational admin for the first payroll backend slice."""

from django import forms
from django.contrib import admin, messages
from django.contrib.admin import helpers
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.template.response import TemplateResponse

from .enums import ApprovalStatus
from .models import (
    EmployeePayRate,
    PayrollAuditEvent,
    PayrollComponent,
    PayrollInputLine,
    PayrollPeriod,
    PayrollRun,
    PayrollStatement,
    PayrollStatementAcknowledgement,
    PayrollStatementLine,
    PayrollWorkRecord,
)
from .payroll.exceptions import PayrollOperationError
from .payroll.services import (
    approve_input_line,
    approve_pay_rate,
    approve_run,
    approve_work_record,
    calculate_period,
    publish_run,
    return_run_for_correction,
    submit_run_for_review,
)


def payroll_reason_action_response(
    model_admin,
    request,
    queryset,
    *,
    action_name,
    title,
    reason_required=True,
    error="",
):
    context = {
        **model_admin.admin_site.each_context(request),
        "title": title,
        "opts": model_admin.model._meta,
        "queryset": queryset,
        "action_name": action_name,
        "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
        "reason_required": reason_required,
        "error": error,
    }
    return TemplateResponse(
        request,
        "admin/finance/payroll_reason_action.html",
        context,
    )


def payroll_approval_action_response(
    model_admin,
    request,
    queryset,
    *,
    action_name,
    title,
    error="",
):
    context = {
        **model_admin.admin_site.each_context(request),
        "title": title,
        "opts": model_admin.model._meta,
        "queryset": queryset,
        "action_name": action_name,
        "action_checkbox_name": helpers.ACTION_CHECKBOX_NAME,
        "error": error,
    }
    return TemplateResponse(
        request,
        "admin/finance/payroll_approval_action.html",
        context,
    )


class VersionedDraftAdminForm(forms.ModelForm):
    """Carry the version seen on GET back to the locked admin POST."""

    expected_lock_version = forms.IntegerField(
        min_value=0,
        required=False,
        widget=forms.HiddenInput,
    )

    class Meta:
        fields = "__all__"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if not self.is_bound and self.instance and self.instance.pk:
            self.initial["expected_lock_version"] = self.instance.lock_version


class PayrollSensitiveAdminMixin:
    """Use explicit payroll roles instead of generic Django model access."""

    view_permissions = ()

    def _has_payroll_access(self, request):
        return any(
            request.user.has_perm(permission) for permission in self.view_permissions
        )

    def has_module_permission(self, request):
        return self._has_payroll_access(request)

    def has_view_permission(self, request, obj=None):
        return self._has_payroll_access(request)


class ImmutableApprovedAdminMixin(PayrollSensitiveAdminMixin):
    """Prevent editing approved/voided inputs through Django admin."""

    view_permissions = (
        "finance.manage_payroll_inputs",
        "finance.approve_payroll_inputs",
        "finance.view_all_payroll",
    )
    form = VersionedDraftAdminForm

    def get_readonly_fields(self, request, obj=None):
        readonly = list(super().get_readonly_fields(request, obj))
        if "lock_version" not in readonly:
            readonly.append("lock_version")
        if "status" not in readonly:
            readonly.append("status")
        if obj is not None and (
            not request.user.has_perm("finance.manage_payroll_inputs")
            or obj.status != ApprovalStatus.DRAFT
            or obj.created_by_id != request.user.pk
        ):
            readonly.extend(
                field.name
                for field in obj._meta.concrete_fields
                if field.name not in readonly
            )
        return readonly

    def has_delete_permission(self, request, obj=None):
        return False

    def has_add_permission(self, request):
        return request.user.has_perm("finance.manage_payroll_inputs")

    def has_change_permission(self, request, obj=None):
        return self._has_payroll_access(request)

    @transaction.atomic
    def save_model(self, request, obj, form, change):
        if not request.user.has_perm("finance.manage_payroll_inputs"):
            raise PermissionDenied("Нет права изменять входные данные зарплаты.")
        if change:
            if form is None or form.cleaned_data.get("expected_lock_version") is None:
                raise PermissionDenied(
                    "Версия открытого черновика потеряна; обновите страницу."
                )
            expected_lock_version = form.cleaned_data["expected_lock_version"]
            current = obj.__class__.objects.select_for_update().get(pk=obj.pk)
            if (
                current.created_by_id != request.user.pk
                or current.status != ApprovalStatus.DRAFT
            ):
                raise PermissionDenied("Изменять можно только собственный черновик.")
            if current.lock_version != expected_lock_version:
                raise PermissionDenied(
                    "Черновик уже изменён другой операцией; обновите страницу."
                )
            obj.status = current.status
            obj.lock_version = current.lock_version
            obj._expected_lock_version = expected_lock_version
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)


@admin.register(PayrollComponent)
class PayrollComponentAdmin(PayrollSensitiveAdminMixin, admin.ModelAdmin):
    view_permissions = (
        "finance.manage_payroll_inputs",
        "finance.approve_payroll_inputs",
        "finance.view_all_payroll",
    )
    list_display = ["code", "name", "kind", "is_active", "display_order"]
    list_filter = ["kind", "is_active"]
    search_fields = ["code", "name"]
    ordering = ["display_order", "code"]

    def has_add_permission(self, request):
        return request.user.has_perm("finance.manage_payroll_inputs")

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return self._has_payroll_access(request)
        return request.user.has_perm("finance.manage_payroll_inputs")

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        if obj is None:
            return []
        return list(PayrollComponent.semantic_fields)


@admin.register(PayrollPeriod)
class PayrollPeriodAdmin(PayrollSensitiveAdminMixin, admin.ModelAdmin):
    view_permissions = (
        "finance.manage_payroll_inputs",
        "finance.calculate_payroll",
        "finance.approve_payroll",
        "finance.publish_payroll",
        "finance.view_all_payroll",
    )
    list_display = [
        "code",
        "name",
        "date_from",
        "date_to",
        "status",
        "current_run",
    ]
    list_filter = ["status", "currency"]
    search_fields = ["code", "name"]
    readonly_fields = [
        "status",
        "current_run",
        "lock_version",
        "created_by",
        "created_at",
        "updated_at",
    ]
    actions = ["calculate_selected"]

    def save_model(self, request, obj, form, change):
        if not change:
            obj.created_by = request.user
        super().save_model(request, obj, form, change)

    def has_add_permission(self, request):
        return request.user.has_perm("finance.manage_payroll_inputs")

    def has_change_permission(self, request, obj=None):
        if obj is None:
            return self._has_payroll_access(request)
        return request.user.has_perm("finance.manage_payroll_inputs")

    def has_delete_permission(self, request, obj=None):
        return False

    @admin.action(description="Рассчитать выбранные периоды")
    def calculate_selected(self, request, queryset):
        if not request.user.has_perm("finance.calculate_payroll"):
            self.message_user(request, "Недостаточно прав.", level=messages.ERROR)
            return
        reason_required = any(period.current_run_id for period in queryset)
        if "confirm_payroll_action" not in request.POST:
            return payroll_reason_action_response(
                self,
                request,
                queryset,
                action_name="calculate_selected",
                title="Расчёт зарплатного периода",
                reason_required=reason_required,
            )
        reason = request.POST.get("reason", "").strip()
        if reason_required and not reason:
            return payroll_reason_action_response(
                self,
                request,
                queryset,
                action_name="calculate_selected",
                title="Расчёт зарплатного периода",
                reason_required=True,
                error="Для повторного расчёта обязательно укажите основание.",
            )
        success_count = 0
        for period in queryset:
            try:
                calculate_period(
                    period.pk,
                    actor=request.user,
                    recalculation_reason=reason if period.current_run_id else "",
                )
            except PayrollOperationError as exc:
                self.message_user(
                    request,
                    f"{period}: {exc.message} ({exc.code})",
                    level=messages.ERROR,
                )
            else:
                success_count += 1
        if success_count:
            self.message_user(
                request,
                f"Рассчитано периодов: {success_count}",
                level=messages.SUCCESS,
            )


@admin.register(EmployeePayRate)
class EmployeePayRateAdmin(ImmutableApprovedAdminMixin, admin.ModelAdmin):
    list_display = [
        "employee",
        "rate_code",
        "amount",
        "currency",
        "effective_from",
        "revision",
        "status",
        "self_approval_overridden",
    ]
    list_filter = [
        "status",
        "self_approval_overridden",
        "currency",
        "source",
        "effective_from",
    ]
    search_fields = [
        "employee__last_name",
        "employee__first_name",
        "employee__email",
        "rate_code",
        "source_ref",
    ]
    readonly_fields = [
        "created_by",
        "created_at",
        "approved_by",
        "approved_at",
        "self_approval_overridden",
        "voided_by",
        "voided_at",
    ]
    actions = ["approve_selected"]

    @admin.action(description="Утвердить выбранные ставки")
    def approve_selected(self, request, queryset):
        return self._approve_records(
            request,
            queryset,
            approve_pay_rate,
            action_name="approve_selected",
            title="Утверждение ставок",
        )

    def _approve_records(
        self,
        request,
        queryset,
        service,
        *,
        action_name,
        title,
    ):
        if not request.user.has_perm("finance.approve_payroll_inputs"):
            self.message_user(request, "Недостаточно прав.", level=messages.ERROR)
            return
        if "confirm_payroll_approval" not in request.POST:
            return payroll_approval_action_response(
                self,
                request,
                queryset,
                action_name=action_name,
                title=title,
            )
        for record in queryset:
            try:
                expected_lock_version = int(request.POST[f"lock_version_{record.pk}"])
            except (KeyError, TypeError, ValueError):
                return payroll_approval_action_response(
                    self,
                    request,
                    queryset,
                    action_name=action_name,
                    title=title,
                    error="Версия черновика потеряна; проверьте данные ещё раз.",
                )
            try:
                service(
                    record.pk,
                    actor=request.user,
                    expected_lock_version=expected_lock_version,
                )
            except PayrollOperationError as exc:
                self.message_user(
                    request,
                    f"{record}: {exc.message} ({exc.code})",
                    level=messages.ERROR,
                )


@admin.register(PayrollWorkRecord)
class PayrollWorkRecordAdmin(ImmutableApprovedAdminMixin, admin.ModelAdmin):
    list_display = [
        "period",
        "employee",
        "target_points",
        "actual_points",
        "revision",
        "status",
        "self_approval_overridden",
    ]
    list_filter = ["period", "status", "self_approval_overridden", "source"]
    search_fields = [
        "employee__last_name",
        "employee__first_name",
        "employee__email",
        "source_ref",
    ]
    readonly_fields = [
        "created_by",
        "created_at",
        "updated_at",
        "approved_by",
        "approved_at",
        "self_approval_overridden",
        "voided_by",
        "voided_at",
    ]
    actions = ["approve_selected"]

    @admin.action(description="Утвердить выбранную выработку")
    def approve_selected(self, request, queryset):
        return EmployeePayRateAdmin._approve_records(
            self,
            request,
            queryset,
            approve_work_record,
            action_name="approve_selected",
            title="Утверждение выработки",
        )


@admin.register(PayrollInputLine)
class PayrollInputLineAdmin(ImmutableApprovedAdminMixin, admin.ModelAdmin):
    exclude = ["reversal_of"]
    list_display = [
        "period",
        "employee",
        "component",
        "amount",
        "relates_to_period",
        "status",
        "self_approval_overridden",
    ]
    list_filter = [
        "period",
        "status",
        "self_approval_overridden",
        "component",
        "source",
    ]
    search_fields = [
        "employee__last_name",
        "employee__first_name",
        "employee__email",
        "reason",
        "source_ref",
    ]
    readonly_fields = [
        "idempotency_key",
        "created_by",
        "created_at",
        "approved_by",
        "approved_at",
        "self_approval_overridden",
        "voided_by",
        "voided_at",
    ]
    actions = ["approve_selected"]

    @admin.action(description="Утвердить выбранные строки")
    def approve_selected(self, request, queryset):
        return EmployeePayRateAdmin._approve_records(
            self,
            request,
            queryset,
            approve_input_line,
            action_name="approve_selected",
            title="Утверждение начислений и удержаний",
        )


class PayrollStatementLineInline(admin.TabularInline):
    model = PayrollStatementLine
    extra = 0
    can_delete = False
    fields = ["position", "code", "label", "kind", "amount", "reason"]
    readonly_fields = fields

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(PayrollRun)
class PayrollRunAdmin(PayrollSensitiveAdminMixin, admin.ModelAdmin):
    view_permissions = (
        "finance.calculate_payroll",
        "finance.approve_payroll",
        "finance.publish_payroll",
        "finance.view_all_payroll",
    )
    list_display = [
        "period",
        "revision",
        "status",
        "employee_count",
        "gross_total",
        "payable_total",
        "requested_by",
        "self_approval_overridden",
    ]
    list_filter = ["status", "self_approval_overridden", "period"]
    search_fields = ["period__code", "input_hash", "result_hash"]
    readonly_fields = [field.name for field in PayrollRun._meta.concrete_fields]
    actions = [
        "request_review",
        "return_selected",
        "approve_selected",
        "publish_selected",
    ]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return self._has_payroll_access(request)

    def _run_action(self, request, queryset, service):
        for run in queryset:
            try:
                service(run.pk, actor=request.user)
            except PayrollOperationError as exc:
                self.message_user(
                    request,
                    f"{run}: {exc.message} ({exc.code})",
                    level=messages.ERROR,
                )

    @admin.action(description="Передать на проверку")
    def request_review(self, request, queryset):
        self._run_action(request, queryset, submit_run_for_review)

    @admin.action(description="Вернуть расчёт на исправление")
    def return_selected(self, request, queryset):
        if "confirm_payroll_action" not in request.POST:
            return payroll_reason_action_response(
                self,
                request,
                queryset,
                action_name="return_selected",
                title="Возврат расчёта на исправление",
            )
        reason = request.POST.get("reason", "").strip()
        if not reason:
            return payroll_reason_action_response(
                self,
                request,
                queryset,
                action_name="return_selected",
                title="Возврат расчёта на исправление",
                error="Укажите причину возврата.",
            )
        for run in queryset:
            try:
                return_run_for_correction(
                    run.pk,
                    actor=request.user,
                    reason=reason,
                )
            except PayrollOperationError as exc:
                self.message_user(
                    request,
                    f"{run}: {exc.message} ({exc.code})",
                    level=messages.ERROR,
                )

    @admin.action(description="Утвердить расчёт")
    def approve_selected(self, request, queryset):
        self._run_action(request, queryset, approve_run)

    @admin.action(description="Опубликовать расчётные листки")
    def publish_selected(self, request, queryset):
        self._run_action(request, queryset, publish_run)


@admin.register(PayrollStatement)
class PayrollStatementAdmin(PayrollSensitiveAdminMixin, admin.ModelAdmin):
    view_permissions = ("finance.view_all_payroll",)
    list_display = [
        "run",
        "employee",
        "gross_total",
        "deduction_total",
        "payment_total",
        "payable",
    ]
    list_filter = ["run__period", "run__status", "currency"]
    search_fields = [
        "employee__last_name",
        "employee__first_name",
        "employee__email",
        "result_hash",
    ]
    readonly_fields = [field.name for field in PayrollStatement._meta.concrete_fields]
    inlines = [PayrollStatementLineInline]

    def has_add_permission(self, request):
        return False

    def has_delete_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return self._has_payroll_access(request)


@admin.register(PayrollStatementAcknowledgement)
class PayrollStatementAcknowledgementAdmin(
    PayrollSensitiveAdminMixin,
    admin.ModelAdmin,
):
    view_permissions = (
        "finance.view_all_payroll",
        "finance.audit_payroll",
    )
    list_display = [
        "statement",
        "employee",
        "viewed_at",
        "acknowledged_at",
        "disputed_at",
    ]
    list_filter = ["acknowledged_at", "disputed_at"]
    search_fields = [
        "employee__last_name",
        "employee__first_name",
        "statement__result_hash",
    ]
    readonly_fields = [
        field.name for field in PayrollStatementAcknowledgement._meta.concrete_fields
    ]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return self._has_payroll_access(request)

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(PayrollAuditEvent)
class PayrollAuditEventAdmin(PayrollSensitiveAdminMixin, admin.ModelAdmin):
    view_permissions = ("finance.audit_payroll",)
    list_display = [
        "created_at",
        "actor",
        "action",
        "object_type",
        "object_id",
        "period",
    ]
    list_filter = ["action", "object_type", "period"]
    search_fields = ["object_id", "before_hash", "after_hash"]
    readonly_fields = [field.name for field in PayrollAuditEvent._meta.concrete_fields]

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return request.user.has_perm("finance.audit_payroll")

    def has_delete_permission(self, request, obj=None):
        return False
