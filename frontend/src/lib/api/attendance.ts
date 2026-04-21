import { type RequestFn } from './utils';

export type LogStormDateOverridePayload = {
    date: string;
    is_workday: boolean;
    reason?: string;
    start_time?: string;
    end_time?: string;
    expected_hours?: number;
};

export type LogStormSchedulePayload = {
    start_time: string;
    end_time: string;
    expected_hours: number;
    workdays: string[];
    date_overrides?: LogStormDateOverridePayload[];
};

export type LogStormAttendanceAnalyzePayload = {
    employee_id: number;
    period_start: string;
    period_end: string;
    schedule?: LogStormSchedulePayload;
};

export type LogStormAttendanceRecord = {
    date?: string;
    employee_id?: string;
    display_name?: string;
    arrival_time?: string | null;
    departure_time?: string | null;
    work_hours?: number | string | null;
    expected_hours?: number | string | null;
    is_workday?: boolean;
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
    [key: string]: unknown;
};

export type LogStormAttendanceResponse = {
    records?: LogStormAttendanceRecord[];
    [key: string]: unknown;
};

export function createAttendanceApi(request: RequestFn) {
    return {
        analyzeLogStormAttendance: (data: LogStormAttendanceAnalyzePayload) =>
            request('/api/v1/attendance/logstorm/analyze/', {
                method: 'POST',
                body: JSON.stringify(data),
            }) as Promise<LogStormAttendanceResponse>,
    };
}
