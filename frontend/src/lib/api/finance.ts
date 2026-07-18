import type { RequestFn } from "./utils";

export type PayrollLineKind =
    | "earning"
    | "adjustment_credit"
    | "adjustment_debit"
    | "deduction"
    | "payment";

export type PayrollPeriodSummary = {
    code: string;
    name: string;
    date_from: string;
    date_to: string;
    pay_date: string | null;
};

export type PayrollAcknowledgement = {
    viewed_at: string | null;
    acknowledged_at: string | null;
    disputed_at: string | null;
};

export type PayrollStatementSummary = {
    public_id: string;
    period: PayrollPeriodSummary;
    revision: number;
    published_at: string;
    currency: string;
    payable: string;
    acknowledgement: PayrollAcknowledgement | null;
};

export type PayrollStatementLine = {
    code: string;
    label: string;
    kind: PayrollLineKind;
    amount: string;
    source_period_from: string | null;
    source_period_to: string | null;
    is_retro: boolean;
    calculated: boolean;
};

export type PayrollStatement = PayrollStatementSummary & {
    point_delta: string | null;
    gross_before_adjustments: string;
    adjustment_total: string;
    gross_total: string;
    deduction_total: string;
    net_pay: string;
    payment_total: string;
    lines: PayrollStatementLine[];
};

export type PayrollStatementPage = {
    count: number;
    next: string | null;
    previous: string | null;
    results: PayrollStatementSummary[];
};

export type PayrollApprovalStatus = "draft" | "approved" | "voided";
export type PayrollPeriodStatus = "open" | "calculated" | "review" | "approved" | "published" | "closed";
export type PayrollRunStatus = "calculated" | "review" | "approved" | "published" | "returned" | "superseded";

export type PayrollAdminUserRef = {
    id: number;
    display_name: string;
};

export type PayrollAdminEmployee = PayrollAdminUserRef & {
    position: string | null;
    department?: string | null;
};

export type PayrollAdminPeriod = PayrollPeriodSummary & {
    id: number;
    currency: string;
    status: PayrollPeriodStatus;
    lock_version: number;
    current_run_id: number | null;
};

export type PayrollAdminRun = {
    id: number;
    period_id: number;
    revision: number;
    status: PayrollRunStatus;
    employee_count: number;
    gross_total?: string | null;
    deduction_total?: string | null;
    payable_total?: string | null;
    requested_by: PayrollAdminUserRef;
    requested_at: string;
    approved_by: PayrollAdminUserRef | null;
    approved_at: string | null;
    published_by: PayrollAdminUserRef | null;
    published_at: string | null;
    recalculation_reason: string;
};

export type PayrollAdminPermissions = {
    full_access: boolean;
    manage_inputs: boolean;
    approve_inputs: boolean;
    override_approval: boolean;
    calculate: boolean;
    approve_run: boolean;
    publish: boolean;
    view_all: boolean;
    audit: boolean;
};

export type PayrollReadinessGroup = {
    ready: boolean;
    total: number;
    approved: number;
    draft: number;
    missing_employee_ids?: number[];
};

export type PayrollCalculationBlocker = {
    code: string;
    message: string;
    employee_id?: number;
};

export type PayrollAdminWorkspace = {
    permissions: PayrollAdminPermissions;
    employees: PayrollAdminEmployee[];
    components: PayrollComponent[];
    periods: PayrollAdminPeriod[];
    selected_period: PayrollAdminPeriod | null;
    readiness: {
        rates: PayrollReadinessGroup;
        work_records: PayrollReadinessGroup;
        input_lines: Pick<PayrollReadinessGroup, "approved" | "draft">;
        calculation: {
            ready: boolean;
            blockers: PayrollCalculationBlocker[];
        };
    };
    current_run: PayrollAdminRun | null;
    runs: PayrollAdminRun[];
    summary: {
        employee_count: number;
        gross_total: string | null;
        deduction_total: string | null;
        payable_total: string | null;
    } | null;
    pending_approvals: {
        rates: number;
        work_records: number;
        input_lines: number;
    };
};

export type PayrollComponent = {
    id: number;
    code: string;
    name: string;
    kind: PayrollLineKind;
    requires_reason: boolean;
    is_active: boolean;
    display_order: number;
};

export type PayrollAdminPayRate = {
    id: number;
    employee_id?: number;
    employee: PayrollAdminEmployee;
    rate_code: string;
    amount: string;
    point_rate: string;
    currency: string;
    effective_from: string;
    revision: number;
    status: PayrollApprovalStatus;
    reason: string;
    lock_version: number;
    created_by: PayrollAdminUserRef;
    created_at: string;
    approved_by: PayrollAdminUserRef | null;
    approved_at: string | null;
};

export type PayrollAdminWorkRecord = {
    id: number;
    period_id: number;
    employee_id?: number;
    employee: PayrollAdminEmployee;
    target_points: string;
    actual_points: string;
    expected_point_amount: string | null;
    expected_gross: string | null;
    expected_recalculated_gross: string | null;
    expected_payable: string | null;
    revision: number;
    status: PayrollApprovalStatus;
    source?: string;
    replaces_id?: number | null;
    reason: string;
    lock_version: number;
    created_by: PayrollAdminUserRef;
    created_at: string;
    approved_by: PayrollAdminUserRef | null;
    approved_at: string | null;
};

export type PayrollAttendanceWorkMode = "missing_only" | "replace_existing";

export type PayrollAttendanceWorkAction =
    | "create"
    | "update"
    | "revise"
    | "unchanged"
    | "skip"
    | "blocked";

export type PayrollAttendanceWorkIssue = {
    code: string;
    message: string;
};

export type PayrollAttendanceWorkModeSummary = {
    create: number;
    update: number;
    revise: number;
    unchanged: number;
    skip: number;
    blocked: number;
    changes: number;
};

export type PayrollAttendanceExistingWorkRecord = {
    id: number;
    revision: number;
    status: PayrollApprovalStatus;
    source?: string;
    target_points: string;
    actual_points: string;
    created_by?: PayrollAdminUserRef;
};

export type PayrollAttendanceWorkPreviewItem = {
    employee: PayrollAdminEmployee;
    target_points: string;
    actual_points: string;
    expected_hours: string;
    worked_hours: string;
    attendance_days: number;
    effective_workdays: number;
    technical_issue_days: number;
    warnings: PayrollAttendanceWorkIssue[];
    blockers: PayrollAttendanceWorkIssue[];
    existing_record: PayrollAttendanceExistingWorkRecord | null;
    actions: Record<PayrollAttendanceWorkMode, PayrollAttendanceWorkAction>;
};

export type PayrollAttendanceWorkPreview = {
    period_id: number;
    generated_at: string;
    preview_token: string;
    policy: {
        code: string;
        label: string;
        description: string;
    };
    summary: {
        attendance_employees: number;
        existing: number;
        blocked: number;
        modes: Record<PayrollAttendanceWorkMode, PayrollAttendanceWorkModeSummary>;
    };
    items: PayrollAttendanceWorkPreviewItem[];
};

export type PayrollAttendanceWorkApplyPayload = {
    mode: PayrollAttendanceWorkMode;
    preview_token: string;
    expected_period_lock_version: number;
    reason: string;
};

export type PayrollAttendanceWorkApplyResult = {
    mode: PayrollAttendanceWorkMode;
    summary: {
        created: number;
        updated: number;
        revised: number;
        unchanged: number;
        skipped: number;
        blocked: number;
    };
    records: PayrollAdminWorkRecord[];
};

export type PayrollAdminInputLine = {
    id: number;
    period_id: number;
    employee: PayrollAdminEmployee;
    employee_id?: number;
    component: PayrollComponent;
    component_id?: number;
    amount: string;
    relates_to_period_id: number | null;
    reason: string;
    status: PayrollApprovalStatus;
    lock_version: number;
    created_by: PayrollAdminUserRef;
    created_at: string;
    approved_by: PayrollAdminUserRef | null;
    approved_at: string | null;
};

export type PayrollAdminPage<T> = {
    count: number;
    next: string | null;
    previous: string | null;
    results: T[];
};

export type PayrollAdminListPayload<T> = PayrollAdminPage<T> | T[];

export type PayrollPeriodWrite = {
    code: string;
    name: string;
    date_from: string;
    date_to: string;
    pay_date: string | null;
    currency: string;
};

export type PayrollPayRateWrite = {
    employee_id: number;
    rate_code: string;
    amount: string;
    point_rate: string;
    currency: string;
    effective_from: string;
    reason: string;
};

export type PayrollWorkRecordWrite = {
    period_id: number;
    employee_id: number;
    target_points: string;
    actual_points: string;
    expected_point_amount?: string | null;
    expected_gross?: string | null;
    expected_recalculated_gross?: string | null;
    expected_payable?: string | null;
    reason: string;
};

export type PayrollInputLineWrite = {
    period_id: number;
    employee_id: number;
    component_id: number;
    amount: string;
    relates_to_period_id?: number | null;
    reason: string;
};

type PayrollAdminListParams = {
    period_id?: number;
    search?: string;
    status?: PayrollApprovalStatus | "";
};

const adminPrefix = "/api/v1/finance/payroll/admin";

function buildQuery(params: Record<string, string | number | boolean | undefined | null>): string {
    const search = new URLSearchParams();
    Object.entries(params).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== "") search.set(key, String(value));
    });
    const query = search.toString();
    return query ? `?${query}` : "";
}

function jsonOptions(method: "POST" | "PATCH", payload: object = {}): RequestInit {
    return { method, body: JSON.stringify(payload) };
}

export function createFinanceApi(request: RequestFn) {
    return {
        getMyPayrollStatements: (): Promise<PayrollStatementPage | PayrollStatementSummary[]> =>
            request("/api/v1/finance/payroll/me/statements/?page_size=100"),
        getMyPayrollStatement: (publicId: string): Promise<PayrollStatement> =>
            request(`/api/v1/finance/payroll/me/statements/${encodeURIComponent(publicId)}/`),
        acknowledgeMyPayrollStatement: (publicId: string): Promise<PayrollAcknowledgement> =>
            request(
                `/api/v1/finance/payroll/me/statements/${encodeURIComponent(publicId)}/acknowledge/`,
                { method: "POST" },
            ),
        getPayrollAdminWorkspace: (periodId?: number): Promise<PayrollAdminWorkspace> =>
            request(`${adminPrefix}/workspace/${buildQuery({ period_id: periodId })}`),
        getPayrollAdminPeriods: (): Promise<PayrollAdminListPayload<PayrollAdminPeriod>> =>
            request(`${adminPrefix}/periods/`),
        createPayrollAdminPeriod: (payload: PayrollPeriodWrite): Promise<PayrollAdminPeriod> =>
            request(`${adminPrefix}/periods/`, jsonOptions("POST", payload)),
        updatePayrollAdminPeriod: (
            periodId: number,
            payload: Partial<PayrollPeriodWrite> & { expected_lock_version: number },
        ): Promise<PayrollAdminPeriod> =>
            request(`${adminPrefix}/periods/${periodId}/`, jsonOptions("PATCH", payload)),
        getPayrollAdminPayRates: (params: PayrollAdminListParams = {}): Promise<PayrollAdminListPayload<PayrollAdminPayRate>> =>
            request(`${adminPrefix}/pay-rates/${buildQuery({ ...params, page_size: 200 })}`),
        createPayrollAdminPayRate: (payload: PayrollPayRateWrite): Promise<PayrollAdminPayRate> =>
            request(`${adminPrefix}/pay-rates/`, jsonOptions("POST", payload)),
        updatePayrollAdminPayRate: (
            rateId: number,
            payload: Partial<Omit<PayrollPayRateWrite, "employee_id" | "rate_code" | "currency">> & { expected_lock_version: number },
        ): Promise<PayrollAdminPayRate> =>
            request(`${adminPrefix}/pay-rates/${rateId}/`, jsonOptions("PATCH", payload)),
        approvePayrollAdminPayRate: (rateId: number, expectedLockVersion: number): Promise<PayrollAdminPayRate> =>
            request(`${adminPrefix}/pay-rates/${rateId}/approve/`, jsonOptions("POST", { expected_lock_version: expectedLockVersion })),
        revisePayrollAdminPayRate: (rateId: number, reason: string): Promise<PayrollAdminPayRate> =>
            request(`${adminPrefix}/pay-rates/${rateId}/revise/`, jsonOptions("POST", { reason })),
        getPayrollAdminWorkRecords: (params: PayrollAdminListParams = {}): Promise<PayrollAdminListPayload<PayrollAdminWorkRecord>> =>
            request(`${adminPrefix}/work-records/${buildQuery({ ...params, page_size: 200 })}`),
        createPayrollAdminWorkRecord: (payload: PayrollWorkRecordWrite): Promise<PayrollAdminWorkRecord> =>
            request(`${adminPrefix}/work-records/`, jsonOptions("POST", payload)),
        updatePayrollAdminWorkRecord: (
            recordId: number,
            payload: Partial<Omit<PayrollWorkRecordWrite, "period_id" | "employee_id">> & { expected_lock_version: number },
        ): Promise<PayrollAdminWorkRecord> =>
            request(`${adminPrefix}/work-records/${recordId}/`, jsonOptions("PATCH", payload)),
        approvePayrollAdminWorkRecord: (recordId: number, expectedLockVersion: number): Promise<PayrollAdminWorkRecord> =>
            request(`${adminPrefix}/work-records/${recordId}/approve/`, jsonOptions("POST", { expected_lock_version: expectedLockVersion })),
        revisePayrollAdminWorkRecord: (recordId: number, reason: string): Promise<PayrollAdminWorkRecord> =>
            request(`${adminPrefix}/work-records/${recordId}/revise/`, jsonOptions("POST", { reason })),
        getPayrollAdminAttendanceWorkPreview: (periodId: number): Promise<PayrollAttendanceWorkPreview> =>
            request(`${adminPrefix}/periods/${periodId}/attendance-work-records/`),
        applyPayrollAdminAttendanceWork: (
            periodId: number,
            payload: PayrollAttendanceWorkApplyPayload,
        ): Promise<PayrollAttendanceWorkApplyResult> =>
            request(
                `${adminPrefix}/periods/${periodId}/attendance-work-records/`,
                jsonOptions("POST", payload),
            ),
        getPayrollAdminInputLines: (params: PayrollAdminListParams = {}): Promise<PayrollAdminListPayload<PayrollAdminInputLine>> =>
            request(`${adminPrefix}/input-lines/${buildQuery({ ...params, page_size: 200 })}`),
        createPayrollAdminInputLine: (payload: PayrollInputLineWrite): Promise<PayrollAdminInputLine> =>
            request(`${adminPrefix}/input-lines/`, jsonOptions("POST", payload)),
        updatePayrollAdminInputLine: (
            lineId: number,
            payload: Partial<Omit<PayrollInputLineWrite, "period_id" | "employee_id" | "component_id">> & { expected_lock_version: number },
        ): Promise<PayrollAdminInputLine> =>
            request(`${adminPrefix}/input-lines/${lineId}/`, jsonOptions("PATCH", payload)),
        approvePayrollAdminInputLine: (lineId: number, expectedLockVersion: number): Promise<PayrollAdminInputLine> =>
            request(`${adminPrefix}/input-lines/${lineId}/approve/`, jsonOptions("POST", { expected_lock_version: expectedLockVersion })),
        calculatePayrollAdminPeriod: (
            periodId: number,
            payload: { idempotency_key: string; recalculation_reason: string; expected_lock_version: number },
        ): Promise<PayrollAdminRun> =>
            request(`${adminPrefix}/periods/${periodId}/calculate/`, jsonOptions("POST", payload)),
        submitPayrollAdminRunForReview: (runId: number): Promise<PayrollAdminRun> =>
            request(`${adminPrefix}/runs/${runId}/submit-review/`, jsonOptions("POST")),
        returnPayrollAdminRun: (runId: number, reason: string): Promise<PayrollAdminRun> =>
            request(`${adminPrefix}/runs/${runId}/return/`, jsonOptions("POST", { reason })),
        approvePayrollAdminRun: (runId: number): Promise<PayrollAdminRun> =>
            request(`${adminPrefix}/runs/${runId}/approve/`, jsonOptions("POST")),
        publishPayrollAdminRun: (runId: number): Promise<PayrollAdminRun> =>
            request(`${adminPrefix}/runs/${runId}/publish/`, jsonOptions("POST")),
        closePayrollAdminPeriod: (periodId: number): Promise<PayrollAdminPeriod> =>
            request(`${adminPrefix}/periods/${periodId}/close/`, jsonOptions("POST")),
    };
}
