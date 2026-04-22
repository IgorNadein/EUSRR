import { buildQuery, type RequestFn } from './utils';
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

export function createAttendanceApi(request: RequestFn) {
    return {
        analyzeAttendance: (data: AttendanceAnalyzePayload) =>
            request('/api/v1/attendance/logstorm/analyze/', {
                method: 'POST',
                body: JSON.stringify(data),
            }) as Promise<AttendanceAnalysisResponse>,
        getAttendanceRecords: (params?: AttendanceRecordsQuery) =>
            request(`/api/v1/attendance/records/${buildQuery(params)}`) as Promise<PaginatedAttendanceRecords>,
        getMonthlyAttendanceMatrix: (params: MonthlyAttendanceMatrixQuery) =>
            request(`/api/v1/attendance/monthly-matrix/${buildQuery(params)}`) as Promise<MonthlyAttendanceMatrix>,
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
