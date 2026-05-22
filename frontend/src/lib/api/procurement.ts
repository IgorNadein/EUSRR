/* eslint-disable @typescript-eslint/no-explicit-any */
import { buildQuery, type RequestFn } from './utils';

export function createProcurementApi(request: RequestFn) {
    return {
        getProcurementRequests: (params?: Record<string, string | number>) => request(`/api/v1/procurement/requests/${buildQuery(params)}`),
        getProcurementRequest: (id: number) => request(`/api/v1/procurement/requests/${id}/`),
        createProcurementRequest: (data: Record<string, any>) => request('/api/v1/procurement/requests/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }),
        updateProcurementRequest: (id: number, data: Record<string, any>) => request(`/api/v1/procurement/requests/${id}/`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }),
        deleteProcurementRequest: (id: number): Promise<void> => request(`/api/v1/procurement/requests/${id}/`, { method: 'DELETE' }),
        submitProcurementRequest: (id: number) => request(`/api/v1/procurement/requests/${id}/submit/`, { method: 'POST' }),
        approveProcurementRequest: (id: number, comment?: string) =>
            request(`/api/v1/procurement/requests/${id}/approve/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ comment: comment || '' }) }),
        rejectProcurementRequest: (id: number, comment?: string) =>
            request(`/api/v1/procurement/requests/${id}/reject/`, { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ comment: comment || '' }) }),
        startWorkProcurementRequest: (id: number) => request(`/api/v1/procurement/requests/${id}/start_work/`, { method: 'POST' }),
        completeProcurementRequest: (id: number) => request(`/api/v1/procurement/requests/${id}/complete/`, { method: 'POST' }),
        markAllReceivedProcurementRequest: (id: number) => request(`/api/v1/procurement/requests/${id}/mark_all_received/`, { method: 'POST' }),
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
        deleteProcurementItem: (id: number): Promise<void> => request(`/api/v1/procurement/items/${id}/`, { method: 'DELETE' }),
        getProcurementItemComments: (itemId: number) => request(`/api/v1/procurement/items/${itemId}/comments/`),
        addProcurementItemComment: (itemId: number, text: string) =>
            request(`/api/v1/procurement/items/${itemId}/comments/`, { method: 'POST', body: JSON.stringify({ text }) }),
        deleteProcurementItemComment: (itemId: number, commentId: number): Promise<void> =>
            request(`/api/v1/procurement/items/${itemId}/comments/${commentId}/`, { method: 'DELETE' }),
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
