/* eslint-disable @typescript-eslint/no-explicit-any */
import type { ProcurementApprovalOptions, ProcurementApprovalStepSelection, ProcurementCreateOptions, ProcurementItemAttachment, ProcurementRequestActivity } from '@/types/api';
import { buildQuery, type RawRequestFn, type RequestFn } from './utils';

function parseDownloadFilename(response: Response, fallback: string): string {
    const disposition = response.headers.get('content-disposition') || '';
    const encodedMatch = disposition.match(/filename\*=UTF-8''([^;]+)/);
    const plainMatch = disposition.match(/filename="?([^";]+)"?/);
    return encodedMatch?.[1]
        ? decodeURIComponent(encodedMatch[1])
        : plainMatch?.[1] || fallback;
}

export function createProcurementApi(request: RequestFn, requestRaw: RawRequestFn) {
    return {
        getProcurementRequests: (params?: Record<string, string | number>) => request(`/api/v1/procurement/requests/${buildQuery(params)}`),
        getProcurementRequest: (id: number) => request(`/api/v1/procurement/requests/${id}/`),
        getProcurementRequestActivity: (id: number): Promise<ProcurementRequestActivity[]> =>
            request(`/api/v1/procurement/requests/${id}/activity/`),
        getProcurementRequestCreateOptions: (): Promise<ProcurementCreateOptions> => request('/api/v1/procurement/requests/create-options/'),
        createProcurementRequest: (data: Record<string, any>) => request('/api/v1/procurement/requests/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }),
        updateProcurementRequest: (id: number, data: Record<string, any>) => request(`/api/v1/procurement/requests/${id}/`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }),
        deleteProcurementRequest: (id: number): Promise<void> => request(`/api/v1/procurement/requests/${id}/`, { method: 'DELETE' }),
        getProcurementApprovalOptions: (id: number): Promise<ProcurementApprovalOptions> => request(`/api/v1/procurement/requests/${id}/approval-options/`),
        submitProcurementRequest: (id: number, approvalSteps?: ProcurementApprovalStepSelection[]) =>
            request(`/api/v1/procurement/requests/${id}/submit/`, {
                method: 'POST',
                headers: approvalSteps ? { 'Content-Type': 'application/json' } : undefined,
                body: approvalSteps ? JSON.stringify({ approval_steps: approvalSteps }) : undefined,
            }),
        approveProcurementRequest: (id: number, comment?: string) =>
            request(`/api/v1/procurement/requests/${id}/approve/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ comment: comment || '' }) }),
        rejectProcurementRequest: (id: number, comment?: string) =>
            request(`/api/v1/procurement/requests/${id}/reject/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ comment: comment || '' }) }),
        startWorkProcurementRequest: (id: number) => request(`/api/v1/procurement/requests/${id}/start_work/`, { method: 'POST' }),
        completeProcurementRequest: (id: number) => request(`/api/v1/procurement/requests/${id}/complete/`, { method: 'POST' }),
        markAllReceivedProcurementRequest: (id: number) => request(`/api/v1/procurement/requests/${id}/mark_all_received/`, { method: 'POST' }),
        notifyProcurementRequestArrival: (id: number) => request(`/api/v1/procurement/requests/${id}/notify_arrival/`, { method: 'POST' }),
        setProcurementRequestViewed: (id: number, isViewed: boolean) =>
            request(`/api/v1/procurement/requests/${id}/set_viewed/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ is_viewed: isViewed }) }),
        markProcurementRequestNotificationsRead: (id: number): Promise<{ status: string; count: number; notification_ids: number[] }> =>
            request(`/api/v1/procurement/requests/${id}/notifications/read/`, { method: 'POST' }),
        cancelProcurementRequest: (id: number, reason?: string) =>
            request(`/api/v1/procurement/requests/${id}/cancel/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ reason: reason || '' }) }),
        getProcurementComments: (requestId: number) => request(`/api/v1/procurement/requests/${requestId}/comments/`),
        addProcurementComment: (requestId: number, text: string) =>
            request(`/api/v1/procurement/requests/${requestId}/comments/`, { method: 'POST', body: JSON.stringify({ text }) }),
        deleteProcurementComment: (requestId: number, commentId: number): Promise<void> =>
            request(`/api/v1/procurement/requests/${requestId}/comments/${commentId}/`, { method: 'DELETE' }),
        getMyProcurementRequests: (params?: Record<string, string | number>) => request(`/api/v1/procurement/requests/my_requests/${buildQuery(params)}`),
        getPendingApprovals: (params?: Record<string, string | number>) => request(`/api/v1/procurement/requests/pending_approvals/${buildQuery(params)}`),
        // Items
        getProcurementItems: (params?: Record<string, string | number>) => request(`/api/v1/procurement/items/${buildQuery(params)}`),
        createProcurementItem: (data: Record<string, any>) => request('/api/v1/procurement/items/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }),
        updateProcurementItem: (id: number, data: Record<string, any>) => request(`/api/v1/procurement/items/${id}/`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }),
        reportProcurementItemIssue: (id: number, text?: string) =>
            request(`/api/v1/procurement/items/${id}/report_issue/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ text: text || '' }) }),
        cancelProcurementItemIssue: (id: number) => request(`/api/v1/procurement/items/${id}/cancel_issue/`, { method: 'POST' }),
        confirmProcurementItemReceived: (id: number, receivedQuantity?: number) =>
            request(`/api/v1/procurement/items/${id}/confirm_received/`, {
                method: 'POST',
                headers: receivedQuantity === undefined ? undefined : { 'Content-Type': 'application/json' },
                body: receivedQuantity === undefined ? undefined : JSON.stringify({ received_quantity: receivedQuantity }),
            }),
        cancelProcurementItemReceived: (id: number, cancelQuantity?: number) =>
            request(`/api/v1/procurement/items/${id}/cancel_received/`, {
                method: 'POST',
                headers: cancelQuantity === undefined ? undefined : { 'Content-Type': 'application/json' },
                body: cancelQuantity === undefined ? undefined : JSON.stringify({ cancel_quantity: cancelQuantity }),
            }),
        deleteProcurementItem: (id: number): Promise<void> => request(`/api/v1/procurement/items/${id}/`, { method: 'DELETE' }),
        getProcurementItemComments: (itemId: number) => request(`/api/v1/procurement/items/${itemId}/comments/`),
        addProcurementItemComment: (itemId: number, text: string) =>
            request(`/api/v1/procurement/items/${itemId}/comments/`, { method: 'POST', body: JSON.stringify({ text }) }),
        deleteProcurementItemComment: (itemId: number, commentId: number): Promise<void> =>
            request(`/api/v1/procurement/items/${itemId}/comments/${commentId}/`, { method: 'DELETE' }),
        getProcurementItemAttachments: (itemId: number): Promise<ProcurementItemAttachment[]> =>
            request(`/api/v1/procurement/items/${itemId}/attachments/`),
        uploadProcurementItemAttachments: (itemId: number, files: File[]): Promise<ProcurementItemAttachment[]> => {
            const formData = new FormData();
            files.forEach((file) => formData.append('files', file));
            return request(`/api/v1/procurement/items/${itemId}/attachments/`, {
                method: 'POST',
                body: formData,
            });
        },
        downloadProcurementItemAttachment: async (
            itemId: number,
            attachment: ProcurementItemAttachment,
        ): Promise<{ blob: Blob; filename: string }> => {
            const response = await requestRaw(
                attachment.download_url || `/api/v1/procurement/items/${itemId}/attachments/${attachment.id}/`,
            );
            return {
                blob: await response.blob(),
                filename: parseDownloadFilename(response, attachment.file_name),
            };
        },
        deleteProcurementItemAttachment: (itemId: number, attachmentId: number): Promise<void> =>
            request(`/api/v1/procurement/items/${itemId}/attachments/${attachmentId}/`, { method: 'DELETE' }),
        // Suppliers
        getProcurementSuppliers: (params?: Record<string, string | number>) => request(`/api/v1/procurement/suppliers/${buildQuery(params)}`),
        createProcurementSupplier: (data: Record<string, any>) => request('/api/v1/procurement/suppliers/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }),
        updateProcurementSupplier: (id: number, data: Record<string, any>) => request(`/api/v1/procurement/suppliers/${id}/`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }),
        deleteProcurementSupplier: (id: number): Promise<void> => request(`/api/v1/procurement/suppliers/${id}/`, { method: 'DELETE' }),
        getTopRatedProcurementSuppliers: () => request('/api/v1/procurement/suppliers/top_rated/'),
        // Stats
        getProcurementOverviewStats: () => request('/api/v1/procurement/stats/overview/'),
        getProcurementDepartmentStats: () => request('/api/v1/procurement/stats/by-department/'),
    };
}
