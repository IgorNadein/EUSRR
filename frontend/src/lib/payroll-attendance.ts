import type {
    PayrollAttendanceWorkAction,
    PayrollAttendanceWorkApplyResult,
    PayrollAttendanceWorkIssue,
    PayrollAttendanceWorkMode,
    PayrollAttendanceWorkModeSummary,
    PayrollAttendanceWorkPreview,
} from "@/lib/api/finance";

export const payrollAttendanceActionMeta: Record<
    PayrollAttendanceWorkAction,
    { label: string; className: string }
> = {
    create: { label: "Новый черновик", className: "app-feedback-success" },
    update: { label: "Обновить черновик", className: "app-selected" },
    revise: { label: "Новая ревизия", className: "app-feedback-warning" },
    unchanged: { label: "Без изменений", className: "app-badge" },
    skip: { label: "Будет пропущено", className: "app-badge" },
    blocked: { label: "Требует исправления", className: "app-feedback-danger" },
};

export function getPayrollAttendanceModeSummary(
    preview: PayrollAttendanceWorkPreview,
    mode: PayrollAttendanceWorkMode,
): PayrollAttendanceWorkModeSummary {
    return preview.summary.modes[mode];
}

export function getPayrollAttendanceIssueMessage(issue: PayrollAttendanceWorkIssue): string {
    return issue.message;
}

export function isAttendancePayrollWorkRecord(source?: string | null): boolean {
    return source === "attendance";
}

export function formatPayrollWorkMetric(value: string, source?: string | null): string {
    return `${value}${isAttendancePayrollWorkRecord(source) ? " ч" : ""}`;
}

function pluralize(count: number, one: string, few: string, many: string): string {
    const normalized = Math.abs(count) % 100;
    const lastDigit = normalized % 10;
    if (normalized > 10 && normalized < 20) return many;
    if (lastDigit === 1) return one;
    if (lastDigit >= 2 && lastDigit <= 4) return few;
    return many;
}

export function formatPayrollAttendanceEmployeeCount(count: number): string {
    return `${count} ${pluralize(count, "сотрудника", "сотрудников", "сотрудников")}`;
}

export function buildPayrollAttendanceApplyNotice(
    result: PayrollAttendanceWorkApplyResult,
): string {
    const { summary } = result;
    const parts: string[] = [];
    if (summary.created) {
        parts.push(
            `создано ${summary.created} ${pluralize(summary.created, "черновик", "черновика", "черновиков")}`,
        );
    }
    if (summary.updated) parts.push(`обновлено ${summary.updated}`);
    if (summary.revised) {
        parts.push(
            `создано ${summary.revised} ${pluralize(summary.revised, "ревизия", "ревизии", "ревизий")}`,
        );
    }
    if (summary.unchanged) parts.push(`без изменений ${summary.unchanged}`);
    if (summary.skipped) parts.push(`пропущено ${summary.skipped}`);
    if (summary.blocked) parts.push(`требует исправления ${summary.blocked}`);

    const outcome = parts.length ? parts.join(", ") : "изменений нет";
    return `Данные посещаемости обработаны: ${outcome}. Проверьте и утвердите созданные черновики.`;
}
