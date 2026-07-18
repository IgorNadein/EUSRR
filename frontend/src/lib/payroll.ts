import type {
    PayrollPeriodSummary,
    PayrollStatementLine,
    PayrollStatementPage,
    PayrollStatementSummary,
} from "@/lib/api/finance";

const DATE_ONLY_PATTERN = /^(\d{4})-(\d{2})-(\d{2})$/;

export type PayrollLineGroupKey = "accruals" | "adjustments" | "deductions" | "payments";

export type PayrollLineGroup = {
    key: PayrollLineGroupKey;
    label: string;
    lines: PayrollStatementLine[];
};

function parseDateOnly(value: string): Date | null {
    const match = DATE_ONLY_PATTERN.exec(value);
    if (!match) return null;
    const date = new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
    return Number.isNaN(date.getTime()) ? null : date;
}

export function normalizePayrollStatements(
    payload: PayrollStatementPage | PayrollStatementSummary[],
): PayrollStatementSummary[] {
    return Array.isArray(payload) ? payload : payload.results || [];
}

export function formatPayrollMoney(value: string | number, currency = "RUB"): string {
    const amount = typeof value === "number" ? value : Number(value);
    if (!Number.isFinite(amount)) return "—";

    try {
        return new Intl.NumberFormat("ru-RU", {
            style: "currency",
            currency: currency || "RUB",
            minimumFractionDigits: 0,
            maximumFractionDigits: 2,
        }).format(amount);
    } catch {
        return `${new Intl.NumberFormat("ru-RU", { maximumFractionDigits: 2 }).format(amount)} ${currency}`.trim();
    }
}

export function formatPayrollDate(value: string | null | undefined): string {
    if (!value) return "—";
    const date = parseDateOnly(value) || new Date(value);
    if (Number.isNaN(date.getTime())) return "—";
    return new Intl.DateTimeFormat("ru-RU", {
        day: "2-digit",
        month: "long",
        year: "numeric",
    }).format(date);
}

export function formatPayrollDateTime(value: string | null | undefined): string {
    if (!value) return "—";
    const date = new Date(value);
    if (Number.isNaN(date.getTime())) return "—";
    return new Intl.DateTimeFormat("ru-RU", {
        day: "2-digit",
        month: "long",
        year: "numeric",
        hour: "2-digit",
        minute: "2-digit",
    }).format(date);
}

export function getPayrollPeriodLabel(period: PayrollPeriodSummary): string {
    if (period.name.trim()) return period.name.trim();
    const start = parseDateOnly(period.date_from);
    if (!start) return period.code;
    const label = new Intl.DateTimeFormat("ru-RU", {
        month: "long",
        year: "numeric",
    }).format(start);
    return label.charAt(0).toUpperCase() + label.slice(1);
}

export function getPayrollPeriodRange(period: PayrollPeriodSummary): string {
    return `${formatPayrollDate(period.date_from)} — ${formatPayrollDate(period.date_to)}`;
}

export function groupPayrollLines(lines: PayrollStatementLine[]): PayrollLineGroup[] {
    const groups: Record<PayrollLineGroupKey, PayrollStatementLine[]> = {
        accruals: [],
        adjustments: [],
        deductions: [],
        payments: [],
    };

    for (const line of lines) {
        if (line.kind === "earning") groups.accruals.push(line);
        else if (line.kind === "adjustment_credit" || line.kind === "adjustment_debit") {
            groups.adjustments.push(line);
        } else if (line.kind === "deduction") groups.deductions.push(line);
        else if (line.kind === "payment") groups.payments.push(line);
    }

    const labels: Record<PayrollLineGroupKey, string> = {
        accruals: "Начисления",
        adjustments: "Корректировки",
        deductions: "Удержания",
        payments: "Выплаты",
    };

    return (Object.keys(groups) as PayrollLineGroupKey[])
        .filter((key) => groups[key].length > 0)
        .map((key) => ({ key, label: labels[key], lines: groups[key] }));
}

export function getPayrollLineDirection(kind: PayrollStatementLine["kind"]): "positive" | "negative" {
    return kind === "adjustment_debit" || kind === "deduction" || kind === "payment"
        ? "negative"
        : "positive";
}
