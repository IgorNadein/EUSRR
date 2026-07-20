import type {
    PayrollAdminListPayload,
    PayrollAdminPermissions,
    PayrollAdminRun,
    PayrollApprovalStatus,
    PayrollPeriodSummary,
    PayrollPeriodWrite,
    PayrollPeriodStatus,
    PayrollRunStatus,
} from "@/lib/api/finance";

export const PAYROLL_DESKTOP_WIDE_MODE_STORAGE_PREFIX = "finances.payroll.desktop-wide-mode";
export const PAYROLL_SELECTED_PERIOD_STORAGE_PREFIX = "finances.payroll.selected-period";

export type PayrollAdminTab = "readiness" | "rates" | "work" | "inputs" | "summary" | "approval";

export const PAYROLL_ADMIN_TABS: Array<{ value: PayrollAdminTab; label: string }> = [
    { value: "readiness", label: "Готовность" },
    { value: "rates", label: "Ставки" },
    { value: "work", label: "Выработка" },
    { value: "inputs", label: "Начисления и выплаты" },
    { value: "summary", label: "Итоговая таблица" },
    { value: "approval", label: "Проверка" },
];

export const approvalStatusMeta: Record<PayrollApprovalStatus, { label: string; className: string }> = {
    draft: { label: "Черновик", className: "app-badge" },
    approved: { label: "Утверждено", className: "app-feedback-success" },
    voided: { label: "Аннулировано", className: "app-feedback-danger" },
};

export const periodStatusMeta: Record<PayrollPeriodStatus, { label: string; className: string }> = {
    open: { label: "Подготовка", className: "app-badge" },
    calculated: { label: "Рассчитан", className: "app-selected" },
    review: { label: "На проверке", className: "app-feedback-warning" },
    approved: { label: "Утверждён", className: "app-feedback-success" },
    published: { label: "Опубликован", className: "app-badge-accent" },
    closed: { label: "Закрыт", className: "app-badge" },
};

export const runStatusMeta: Record<PayrollRunStatus, { label: string; className: string }> = {
    calculated: { label: "Рассчитан", className: "app-selected" },
    review: { label: "На проверке", className: "app-feedback-warning" },
    approved: { label: "Утверждён", className: "app-feedback-success" },
    published: { label: "Опубликован", className: "app-badge-accent" },
    returned: { label: "На исправлении", className: "app-feedback-danger" },
    superseded: { label: "Заменён", className: "app-badge" },
};

export function normalizePayrollAdminList<T>(payload: PayrollAdminListPayload<T>): T[] {
    return Array.isArray(payload) ? payload : payload.results || [];
}

const RUSSIAN_MONTH_NAMES = [
    "Январь",
    "Февраль",
    "Март",
    "Апрель",
    "Май",
    "Июнь",
    "Июль",
    "Август",
    "Сентябрь",
    "Октябрь",
    "Ноябрь",
    "Декабрь",
];

function formatDateInput(year: number, monthIndex: number, day: number): string {
    const date = new Date(year, monthIndex, day);
    return [
        String(date.getFullYear()).padStart(4, "0"),
        String(date.getMonth() + 1).padStart(2, "0"),
        String(date.getDate()).padStart(2, "0"),
    ].join("-");
}

export function getDefaultPayrollPeriodForm(
    periods: PayrollPeriodSummary[],
    referenceDate = new Date(),
): PayrollPeriodWrite {
    let year = referenceDate.getFullYear();
    let monthIndex = referenceDate.getMonth();

    while (true) {
        const code = `${String(year).padStart(4, "0")}-${String(monthIndex + 1).padStart(2, "0")}`;
        const dateFrom = formatDateInput(year, monthIndex, 1);
        const dateTo = formatDateInput(year, monthIndex + 1, 0);
        const conflicts = periods.some((period) => (
            period.code === code
            || (period.date_from <= dateTo && period.date_to >= dateFrom)
        ));

        if (!conflicts) {
            return {
                code,
                name: `${RUSSIAN_MONTH_NAMES[monthIndex]} ${year}`,
                date_from: dateFrom,
                date_to: dateTo,
                pay_date: formatDateInput(year, monthIndex + 1, 5),
                currency: "RUB",
            };
        }

        const nextMonth = new Date(year, monthIndex + 1, 1);
        year = nextMonth.getFullYear();
        monthIndex = nextMonth.getMonth();
    }
}

type ParsedPayrollAdminError = {
    status: number | null;
    code: string | null;
    message: string | null;
};

function extractJsonValue(raw: string): unknown {
    for (let start = 0; start < raw.length; start += 1) {
        const first = raw[start];
        if (first !== "{" && first !== "[") continue;

        const stack = [first === "{" ? "}" : "]"];
        let inString = false;
        let escaped = false;

        for (let index = start + 1; index < raw.length; index += 1) {
            const character = raw[index];
            if (inString) {
                if (escaped) escaped = false;
                else if (character === "\\") escaped = true;
                else if (character === '"') inString = false;
                continue;
            }
            if (character === '"') {
                inString = true;
                continue;
            }
            if (character === "{" || character === "[") {
                stack.push(character === "{" ? "}" : "]");
                continue;
            }
            if (character !== stack.at(-1)) continue;
            stack.pop();
            if (stack.length > 0) continue;

            try {
                return JSON.parse(raw.slice(start, index + 1));
            } catch {
                break;
            }
        }
    }
    return null;
}

function readErrorPayload(value: unknown): { code: string | null; message: string | null } {
    if (!value || typeof value !== "object" || Array.isArray(value)) {
        return { code: null, message: null };
    }
    const record = value as Record<string, unknown>;
    const code = typeof record.code === "string" && record.code.trim()
        ? record.code.trim()
        : null;
    const message = typeof record.message === "string" && record.message.trim()
        ? record.message.trim()
        : null;

    let detailPayload = { code: null, message: null } as {
        code: string | null;
        message: string | null;
    };
    if (record.detail && typeof record.detail === "object") {
        detailPayload = readErrorPayload(record.detail);
    } else if (typeof record.detail === "string" && record.detail.trim()) {
        const detail = record.detail.trim();
        const nested = extractJsonValue(detail);
        if (nested) {
            const parsedNested = readErrorPayload(nested);
            if (parsedNested.code || parsedNested.message) detailPayload = parsedNested;
            else detailPayload.message = detail;
        } else {
            detailPayload.message = detail;
        }
    }
    return {
        code: code || detailPayload.code,
        message: message || detailPayload.message,
    };
}

function parsePayrollAdminError(error: unknown, fallback = ""): ParsedPayrollAdminError {
    const raw = error instanceof Error ? error.message : String(error || fallback);
    const statusMatch = raw.match(/API Error:\s*(\d{3})\b/i);
    const payload = readErrorPayload(extractJsonValue(raw));
    return {
        status: statusMatch ? Number(statusMatch[1]) : null,
        code: payload.code,
        message: payload.message,
    };
}

export function getPayrollAdminError(error: unknown, fallback: string): string {
    const parsed = parsePayrollAdminError(error, fallback);
    if (parsed.message) return parsed.message;
    if (parsed.status === 409) return "Возник конфликт данных. Проверьте условия и повторите действие.";
    if (parsed.status === 403) return "Для этого действия недостаточно прав.";
    if (parsed.status === 401) return "Сессия истекла. Войдите в портал ещё раз.";
    return fallback;
}

export function isPayrollAdminStaleConflict(error: unknown): boolean {
    const { code } = parsePayrollAdminError(error);
    return code === "STALE_PERIOD"
        || code === "STALE_DRAFT"
        || code === "CONCURRENT_CALCULATION_CONFLICT";
}

export type PayrollRunAction = "calculate" | "submit_review" | "approve" | "publish" | "close" | null;

/**
 * TODO(payroll-access-hardening): restore maker-checker UI after the finance
 * role matrix has passed the pilot. Admins currently receive override=true.
 */
export function canApprovePayrollDraft(
    isAuthor: boolean,
    canApprove: boolean,
    canOverrideApproval: boolean,
): boolean {
    return canApprove && (!isAuthor || canOverrideApproval);
}

export function getPrimaryPayrollRunAction(
    run: PayrollAdminRun | null,
    periodStatus: PayrollPeriodStatus,
    permissions: PayrollAdminPermissions,
    calculationReady: boolean,
    currentUserId?: number,
): PayrollRunAction {
    if (periodStatus === "closed") return null;
    if (!run || run.status === "returned") {
        return permissions.calculate && calculationReady ? "calculate" : null;
    }
    if (run.status === "calculated") return permissions.calculate ? "submit_review" : null;
    if (run.status === "review") {
        const isRequester = currentUserId !== undefined && run.requested_by?.id === currentUserId;
        return canApprovePayrollDraft(isRequester, permissions.approve_run, permissions.override_approval)
            ? "approve"
            : null;
    }
    if (run.status === "approved") return permissions.publish ? "publish" : null;
    if (run.status === "published") return permissions.publish ? "close" : null;
    return null;
}

export const payrollRunActionLabels: Record<Exclude<PayrollRunAction, null>, string> = {
    calculate: "Запустить расчёт",
    submit_review: "Передать на проверку",
    approve: "Утвердить расчёт",
    publish: "Опубликовать листки",
    close: "Закрыть период",
};
