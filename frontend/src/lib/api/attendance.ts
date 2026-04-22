import { buildQuery, type GetTokenFn, type RequestFn } from './utils';
import type { User } from '@/types/api';

export type AttendanceDateOverridePayload = {
    date: string;
    is_workday: boolean;
    reason?: string;
    start_time?: string;
    end_time?: string;
    expected_hours?: number;
};

export type AttendanceSchedulePayload = {
    start_time: string;
    end_time: string;
    expected_hours: number;
    workdays: string[];
    date_overrides?: AttendanceDateOverridePayload[];
};

export type EmployeeWorkSchedule = AttendanceSchedulePayload & {
    id: number | null;
    employee_id: number;
    is_active: boolean;
    is_default: boolean;
    updated_by?: number | null;
    created_at?: string | null;
    updated_at?: string | null;
};

export type StandardWorkSchedule = AttendanceSchedulePayload & {
    id: number | null;
    is_default: boolean;
    updated_by?: number | null;
    created_at?: string | null;
    updated_at?: string | null;
};

export type AttendanceAnalyzePayload = {
    employee_id: number;
    period_start: string;
    period_end: string;
    schedule?: AttendanceSchedulePayload;
};

export type AttendanceRecord = {
    id?: number;
    date?: string;
    employee_id?: string;
    display_name?: string;
    arrival_time?: string | null;
    departure_time?: string | null;
    work_hours?: number | string | null;
    expected_hours?: number | string | null;
    is_workday?: boolean;
    effective_is_workday?: boolean;
    non_working_reason?: string;
    is_late?: boolean;
    late_minutes?: number | null;
    is_early_leave?: boolean;
    early_leave_minutes?: number | null;
    is_underwork?: boolean;
    underwork_hours?: number | string | null;
    is_overtime?: boolean;
    overtime_hours?: number | string | null;
    is_absent?: boolean;
    employee_issues?: string[];
    technical_issues?: string[];
    statuses?: string[];
    comments_count?: number;
    personnel_status?: string;
    personnel_status_label?: string;
    personnel_action?: number | null;
    is_manually_edited?: boolean;
    manual_edit_payload?: Record<string, unknown>;
    manual_edited_by?: number | null;
    manual_edited_at?: string | null;
    [key: string]: unknown;
};

export type AttendanceRecordComment = {
    id: number;
    record: number;
    author: User;
    text: string;
    created_at: string;
};

export type AttendanceDayEvent = {
    event_key: string;
    time: string;
    time_label: string;
    caption: string;
    device: string;
    device_name: string;
    serial_no: number;
    has_photo: boolean;
    photo_url: string | null;
};

export type AttendanceAnalysisResponse = {
    records?: AttendanceRecord[];
    [key: string]: unknown;
};

export type AttendanceRecordsQuery = {
    employee_id?: number | string;
    date_from?: string;
    date_to?: string;
    page?: number;
    limit?: number;
};

export type AttendanceRecordUpdatePayload = Partial<Pick<
    AttendanceRecord,
    | 'arrival_time'
    | 'departure_time'
    | 'work_hours'
    | 'expected_hours'
    | 'is_workday'
    | 'effective_is_workday'
    | 'is_late'
    | 'late_minutes'
    | 'is_early_leave'
    | 'early_leave_minutes'
    | 'is_underwork'
    | 'underwork_hours'
    | 'is_overtime'
    | 'overtime_hours'
    | 'is_absent'
>>;

export type PaginatedAttendanceRecords = {
    count: number;
    next: string | null;
    previous: string | null;
    results: AttendanceRecord[];
};

export type MonthlyAttendanceMatrixCell = {
    record_id: number | null;
    arrival_time: string | null;
    departure_time: string | null;
    work_hours: number | string | null;
    expected_hours: number | string | null;
    status: 'empty' | 'technical' | 'underwork' | 'late' | 'overtime' | 'absent' | 'non_working' | 'normal' | string;
    short_label?: string;
    display_text?: string;
    primary_label?: string;
    detail_lines?: string[];
    issues: string[];
    is_workday: boolean | null;
    effective_is_workday: boolean | null;
    non_working_reason?: string;
    is_late?: boolean;
    is_early_leave?: boolean;
    is_underwork?: boolean;
    is_overtime?: boolean;
    is_absent?: boolean;
    personnel_status?: string;
    personnel_status_label?: string;
    is_manually_edited?: boolean;
    manual_edited_at?: string | null;
    comments_count: number;
};

export type MonthlyAttendanceMatrixEmployee = {
    id: number;
    name: string;
    email: string;
};

export type MonthlyAttendanceMatrixRow = {
    date: string;
    label: string;
    weekday: string;
    is_weekend: boolean;
    cells: Record<string, MonthlyAttendanceMatrixCell>;
};

export type MonthlyAttendanceMatrixSummaryRow = {
    key: string;
    label: string;
    values: Record<string, number>;
};

export type MonthlyAttendanceMatrix = {
    month: string;
    month_label: string;
    employees: MonthlyAttendanceMatrixEmployee[];
    rows: MonthlyAttendanceMatrixRow[];
    summary: MonthlyAttendanceMatrixSummaryRow[];
};

export type MonthlyAttendanceMatrixQuery = {
    employee_ids: string;
    month: string;
};

export type MonthlyAttendanceMatrixExportQuery = {
    employee_ids: string;
    period_start: string;
    period_end: string;
};

export type AttendanceMatrixExportFile = {
    blob: Blob;
    filename: string;
};

function filenameFromContentDisposition(value: string | null): string | null {
    if (!value) return null;
    const utfMatch = value.match(/filename\*=UTF-8''([^;]+)/i);
    if (utfMatch?.[1]) return decodeURIComponent(utfMatch[1].replace(/"/g, ''));
    const match = value.match(/filename="?([^";]+)"?/i);
    return match?.[1] || null;
}

export function createAttendanceApi(request: RequestFn, getToken: GetTokenFn) {
    return {
        analyzeAttendance: (data: AttendanceAnalyzePayload) =>
            request('/api/v1/attendance/logstorm/analyze/', {
                method: 'POST',
                body: JSON.stringify(data),
            }) as Promise<AttendanceAnalysisResponse>,
        getAttendanceRecords: (params?: AttendanceRecordsQuery) =>
            request(`/api/v1/attendance/records/${buildQuery(params)}`) as Promise<PaginatedAttendanceRecords>,
        getAttendanceRecord: (recordId: number) =>
            request(`/api/v1/attendance/records/${recordId}/`) as Promise<AttendanceRecord>,
        getMonthlyAttendanceMatrix: (params: MonthlyAttendanceMatrixQuery) =>
            request(`/api/v1/attendance/monthly-matrix/${buildQuery(params)}`) as Promise<MonthlyAttendanceMatrix>,
        downloadMonthlyAttendanceMatrix: async (
            params: MonthlyAttendanceMatrixExportQuery,
        ): Promise<AttendanceMatrixExportFile> => {
            const token = getToken();
            const headers: Record<string, string> = {};
            if (token) headers.Authorization = `Bearer ${token}`;
            const response = await fetch(`/api/v1/attendance/monthly-matrix/export/${buildQuery(params)}`, {
                method: 'GET',
                headers,
            });
            if (!response.ok) {
                let detail = response.statusText;
                try {
                    const payload = await response.json();
                    detail = payload.detail || JSON.stringify(payload);
                } catch {
                    detail = response.statusText;
                }
                throw new Error(`API Error: ${response.status} ${detail}`);
            }
            return {
                blob: await response.blob(),
                filename: filenameFromContentDisposition(
                    response.headers.get('content-disposition'),
                ) || `attendance-${params.period_start}_${params.period_end}.xlsx`,
            };
        },
        getStandardWorkSchedule: () =>
            request('/api/v1/attendance/standard-work-schedule/') as Promise<StandardWorkSchedule>,
        updateStandardWorkSchedule: (data: Partial<AttendanceSchedulePayload>) =>
            request('/api/v1/attendance/standard-work-schedule/', {
                method: 'PATCH',
                body: JSON.stringify(data),
            }) as Promise<StandardWorkSchedule>,
        getEmployeeWorkSchedule: (employeeId: number | string) =>
            request(`/api/v1/attendance/work-schedules/${employeeId}/`) as Promise<EmployeeWorkSchedule>,
        updateEmployeeWorkSchedule: (
            employeeId: number | string,
            data: Partial<AttendanceSchedulePayload & { is_active: boolean }>,
        ) =>
            request(`/api/v1/attendance/work-schedules/${employeeId}/`, {
                method: 'PATCH',
                body: JSON.stringify(data),
            }) as Promise<EmployeeWorkSchedule>,
        updateAttendanceRecord: (recordId: number, data: AttendanceRecordUpdatePayload) =>
            request(`/api/v1/attendance/records/${recordId}/`, {
                method: 'PATCH',
                body: JSON.stringify(data),
            }) as Promise<AttendanceRecord>,
        getAttendanceRecordComments: (recordId: number) =>
            request(`/api/v1/attendance/records/${recordId}/comments/`) as Promise<AttendanceRecordComment[]>,
        getAttendanceRecordDayEvents: (recordId: number) =>
            request(`/api/v1/attendance/records/${recordId}/day-events/`) as Promise<AttendanceDayEvent[]>,
        getAttendanceDayEventPhoto: async (photoUrl: string): Promise<Blob> => {
            const token = getToken();
            const headers: Record<string, string> = {};
            if (token) headers.Authorization = `Bearer ${token}`;
            const response = await fetch(photoUrl, { method: 'GET', headers });
            if (!response.ok) {
                let detail = response.statusText;
                try {
                    const payload = await response.json();
                    detail = payload.detail || payload.error || JSON.stringify(payload);
                } catch {
                    detail = response.statusText;
                }
                throw new Error(`API Error: ${response.status} ${detail}`);
            }
            return response.blob();
        },
        addAttendanceRecordComment: (recordId: number, text: string) =>
            request(`/api/v1/attendance/records/${recordId}/comments/`, {
                method: 'POST',
                body: JSON.stringify({ text }),
            }) as Promise<AttendanceRecordComment>,
        deleteAttendanceRecordComment: (recordId: number, commentId: number): Promise<void> =>
            request(`/api/v1/attendance/records/${recordId}/comments/${commentId}/`, {
                method: 'DELETE',
            }),
    };
}
