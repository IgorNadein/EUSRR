import { buildQuery, type RequestFn } from './utils';

export type GuestVisitActionPayload = {
    comment?: string;
};

export type GuestDocumentMutationResponse = {
    guest: unknown;
    document: unknown;
};

export function createGuestsApi(request: RequestFn) {
    return {
        getGuestVisits: (params?: Record<string, string | number | boolean | undefined | null>) =>
            request(`/api/v1/guests/visits/${buildQuery(params)}`),
        getGuestVisit: (id: number) =>
            request(`/api/v1/guests/visits/${id}/`),
        createGuestVisit: (data: Record<string, unknown>) =>
            request('/api/v1/guests/visits/', {
                method: 'POST',
                body: JSON.stringify(data),
            }),
        updateGuestVisit: (id: number, data: Record<string, unknown>) =>
            request(`/api/v1/guests/visits/${id}/`, {
                method: 'PATCH',
                body: JSON.stringify(data),
            }),
        deleteGuestVisit: (id: number): Promise<void> =>
            request(`/api/v1/guests/visits/${id}/`, {
                method: 'DELETE',
            }),
        submitGuestVisit: (id: number) =>
            request(`/api/v1/guests/visits/${id}/submit/`, { method: 'POST' }),
        approveGuestVisit: (id: number, payload?: GuestVisitActionPayload) =>
            request(`/api/v1/guests/visits/${id}/approve/`, {
                method: 'POST',
                body: JSON.stringify({ comment: payload?.comment || '' }),
            }),
        rejectGuestVisit: (id: number, payload?: GuestVisitActionPayload) =>
            request(`/api/v1/guests/visits/${id}/reject/`, {
                method: 'POST',
                body: JSON.stringify({ comment: payload?.comment || '' }),
            }),
        requestGuestVisitInfo: (id: number, payload: GuestVisitActionPayload) =>
            request(`/api/v1/guests/visits/${id}/request-info/`, {
                method: 'POST',
                body: JSON.stringify({ comment: payload.comment || '' }),
            }),
        provideGuestVisitInfo: (id: number, payload: GuestVisitActionPayload) =>
            request(`/api/v1/guests/visits/${id}/provide-info/`, {
                method: 'POST',
                body: JSON.stringify({ comment: payload.comment || '' }),
            }),
        cancelGuestVisit: (id: number, payload?: GuestVisitActionPayload) =>
            request(`/api/v1/guests/visits/${id}/cancel/`, {
                method: 'POST',
                body: JSON.stringify({ comment: payload?.comment || '' }),
            }),
        revokeGuestVisit: (id: number, payload?: GuestVisitActionPayload) =>
            request(`/api/v1/guests/visits/${id}/revoke/`, {
                method: 'POST',
                body: JSON.stringify({ comment: payload?.comment || '' }),
            }),
        returnGuestVisitToWork: (id: number, payload?: GuestVisitActionPayload) =>
            request(`/api/v1/guests/visits/${id}/return-to-work/`, {
                method: 'POST',
                body: JSON.stringify({ comment: payload?.comment || '' }),
            }),
        syncGuestVisitLdap: (id: number) =>
            request(`/api/v1/guests/visits/${id}/sync-ldap/`, { method: 'POST' }),
        getGuestVisitComments: (visitId: number) =>
            request(`/api/v1/guests/visits/${visitId}/comments/`),
        addGuestVisitComment: (visitId: number, text: string) =>
            request(`/api/v1/guests/visits/${visitId}/comments/`, {
                method: 'POST',
                body: JSON.stringify({ text }),
            }),
        deleteGuestVisitComment: (visitId: number, commentId: number): Promise<void> =>
            request(`/api/v1/guests/visits/${visitId}/comments/${commentId}/`, {
                method: 'DELETE',
            }),
        attachGuestVisitDocument: (visitId: number, documentId: number) =>
            request(`/api/v1/guests/visits/${visitId}/documents/`, {
                method: 'POST',
                body: JSON.stringify({ document_id: documentId }),
            }),
        removeGuestVisitDocument: (visitId: number, documentId: number) =>
            request(`/api/v1/guests/visits/${visitId}/documents/${documentId}/`, {
                method: 'DELETE',
            }),

        getGuests: (params?: Record<string, string | number | boolean | undefined | null>) =>
            request(`/api/v1/guests/${buildQuery(params)}`),
        getGuest: (id: number | string) =>
            request(`/api/v1/guests/${id}/`),
        updateGuest: (id: number | string, data: Record<string, unknown>) =>
            request(`/api/v1/guests/${id}/`, {
                method: 'PATCH',
                body: JSON.stringify(data),
            }),
        getGuestComments: (id: number | string) =>
            request(`/api/v1/guests/${id}/comments/`),
        addGuestComment: (id: number | string, text: string) =>
            request(`/api/v1/guests/${id}/comments/`, {
                method: 'POST',
                body: JSON.stringify({ text }),
            }),
        deleteGuestComment: (id: number | string, commentId: number): Promise<void> =>
            request(`/api/v1/guests/${id}/comments/${commentId}/`, {
                method: 'DELETE',
            }),
        attachGuestDocument: (id: number | string, documentId: number) =>
            request(`/api/v1/guests/${id}/documents/`, {
                method: 'POST',
                body: JSON.stringify({ document_id: documentId }),
            }),
        uploadGuestDocument: (id: number | string, data: { file: File; title?: string; description?: string }) => {
            const fd = new FormData();
            fd.append('file', data.file);
            if (data.title?.trim()) fd.append('title', data.title.trim());
            if (data.description?.trim()) fd.append('description', data.description.trim());
            return request(`/api/v1/guests/${id}/documents/`, { method: 'POST', body: fd });
        },
        removeGuestDocument: (id: number | string, documentId: number) =>
            request(`/api/v1/guests/${id}/documents/${documentId}/`, {
                method: 'DELETE',
            }),
        searchGuests: (params?: Record<string, string | number | boolean | undefined | null>) =>
            request(`/api/v1/guests/search/${buildQuery(params)}`),
        blacklistGuest: (id: number | string) =>
            request(`/api/v1/guests/${id}/blacklist/`, { method: 'POST' }),
        unblacklistGuest: (id: number | string) =>
            request(`/api/v1/guests/${id}/unblacklist/`, { method: 'POST' }),
        syncGuestLdap: (id: number | string) =>
            request(`/api/v1/guests/${id}/sync-ldap/`, { method: 'POST' }),
    };
}
