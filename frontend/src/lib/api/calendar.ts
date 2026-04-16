import type { RequestFn, GetTokenFn } from './utils';
import type {
    Calendar,
    CalendarEvent,
    CalendarOccurrence,
    CalendarParticipant,
    PaginatedResponse,
} from '@/types/api';

type CalendarScopeParam = { scope?: "all" };
type CalendarQueryParams = { start?: string; end?: string; calendar?: number; scope?: "all" };
type CalendarListResponse = PaginatedResponse<Calendar> | Calendar[];
type CalendarEventsResponse = PaginatedResponse<CalendarEvent> | CalendarEvent[];
type CalendarRulesParams = Record<string, unknown>;

export function createCalendarApi(request: RequestFn, getToken: GetTokenFn) {
    return {
        getCalendarEvents: (params?: CalendarQueryParams): Promise<CalendarEventsResponse> => {
            const qp = new URLSearchParams();
            if (params?.start) qp.append('start', params.start);
            if (params?.end) qp.append('end', params.end);
            if (params?.calendar) qp.append('calendar', params.calendar.toString());
            if (params?.scope) qp.append('scope', params.scope);
            const qs = qp.toString();
            return request(`/api/v1/schedule/events/${qs ? '?' + qs : ''}`);
        },
        getMyEvents: (params?: { start?: string; end?: string }) => {
            const qp = new URLSearchParams();
            if (params?.start) qp.append('start', params.start);
            if (params?.end) qp.append('end', params.end);
            const qs = qp.toString();
            return request(`/api/v1/schedule/events/my-events/${qs ? '?' + qs : ''}`);
        },
        getCalendars: (params?: CalendarScopeParam): Promise<CalendarListResponse> => {
            const qp = new URLSearchParams();
            if (params?.scope) qp.append('scope', params.scope);
            const qs = qp.toString();
            return request(`/api/v1/schedule/calendars/${qs ? '?' + qs : ''}`);
        },
        getCalendar: (id: number): Promise<Calendar> => request(`/api/v1/schedule/calendars/${id}/`),
        createCalendar: (data: { name: string; slug?: string }): Promise<Calendar> => request('/api/v1/schedule/calendars/', { method: 'POST', body: JSON.stringify(data) }),
        updateCalendar: (id: number, data: { name?: string; slug?: string }): Promise<Calendar> => request(`/api/v1/schedule/calendars/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),
        deleteCalendar: (id: number): Promise<void> => request(`/api/v1/schedule/calendars/${id}/`, { method: 'DELETE' }),
        // Subscriptions
        getCalendarSubscriptions: () => request('/api/v1/schedule/subscriptions/'),
        subscribeToCalendar: (calendarId: number) => request('/api/v1/schedule/subscriptions/', { method: 'POST', body: JSON.stringify({ calendar: calendarId }) }),
        unsubscribeFromCalendar: (subscriptionId: number) => request(`/api/v1/schedule/subscriptions/${subscriptionId}/`, { method: 'DELETE' }),
        updateSubscription: (subscriptionId: number, data: Record<string, unknown>) => request(`/api/v1/schedule/subscriptions/${subscriptionId}/`, { method: 'PATCH', body: JSON.stringify(data) }),
        // Events
        getEvent: (id: number): Promise<CalendarEvent> => request(`/api/v1/schedule/events/${id}/`),
        createEvent: (data: { title: string; description?: string; start: string; end: string; calendar: number; color_event?: string; rule?: number | null }): Promise<CalendarEvent> =>
            request('/api/v1/schedule/events/', { method: 'POST', body: JSON.stringify(data) }),
        updateEvent: (id: number, data: Record<string, unknown>): Promise<CalendarEvent> => request(`/api/v1/schedule/events/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),
        deleteEvent: (id: number): Promise<void> => request(`/api/v1/schedule/events/${id}/`, { method: 'DELETE' }),
        // Participants
        getCalendarParticipants: (calendarId: number): Promise<CalendarParticipant[]> => request(`/api/v1/schedule/calendars/${calendarId}/participants/`),
        addCalendarParticipant: (calendarId: number, userId: number, distinction: string = 'viewer') =>
            request(`/api/v1/schedule/calendars/${calendarId}/add-participant/`, { method: 'POST', body: JSON.stringify({ user_id: userId, distinction }) }),
        removeCalendarParticipant: (calendarId: number, userId: number): Promise<void> =>
            request(`/api/v1/schedule/calendars/${calendarId}/remove-participant/${userId}/`, { method: 'DELETE' }),
        getEventParticipants: (eventId: number) => request(`/api/v1/schedule/relations/?event=${eventId}`),
        addEventParticipant: (eventId: number, userId: number, distinction: string = 'attendee') =>
            request('/api/v1/schedule/relations/', { method: 'POST', body: JSON.stringify({ event: eventId, object_id: userId, distinction }) }),
        removeEventParticipant: (relationId: number) => request(`/api/v1/schedule/relations/${relationId}/`, { method: 'DELETE' }),
        // Export/Import
        exportCalendarToICS: async (calendarId: number): Promise<Blob> => {
            const response = await fetch(`/api/v1/schedule/calendars/${calendarId}/export-ical/`, { method: 'GET', headers: { 'Authorization': `Bearer ${getToken()}` } });
            if (!response.ok) throw new Error('Failed to export calendar');
            return response.blob();
        },
        importCalendarFromICS: async (calendarId: number, file: File) => {
            const fd = new FormData(); fd.append('file', file);
            const response = await fetch(`/api/v1/schedule/calendars/${calendarId}/import-ical/`, { method: 'POST', headers: { 'Authorization': `Bearer ${getToken()}` }, body: fd });
            if (!response.ok) { const e = await response.json(); throw new Error(e.error || 'Failed to import calendar'); }
            return response.json();
        },
        // Rules
        createRule: (data: { name: string; description?: string; frequency: string; params?: CalendarRulesParams }) =>
            request('/api/v1/schedule/rules/', { method: 'POST', body: JSON.stringify({ ...data, params: data.params ? JSON.stringify(data.params) : '{}' }) }),
        updateRule: (ruleId: number, data: { name: string; description?: string; frequency: string; params?: CalendarRulesParams }) =>
            request(`/api/v1/schedule/rules/${ruleId}/`, { method: 'PUT', body: JSON.stringify({ ...data, params: data.params ? JSON.stringify(data.params) : '{}' }) }),
        getRules: () => request('/api/v1/schedule/rules/'),
        getRule: (ruleId: number) => request(`/api/v1/schedule/rules/${ruleId}/`),
        getOccurrences: (params: { start: string; end: string; calendar?: number; scope?: "all" }): Promise<CalendarOccurrence[]> => {
            const qp = new URLSearchParams();
            qp.append('start', params.start);
            qp.append('end', params.end);
            if (params.calendar) qp.append('calendar', params.calendar.toString());
            if (params.scope) qp.append('scope', params.scope);
            return request(`/api/v1/schedule/events/occurrences/?${qp.toString()}`);
        },
    };
}
