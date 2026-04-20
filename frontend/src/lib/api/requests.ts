/* eslint-disable @typescript-eslint/no-explicit-any */
import type { RequestEmployeeStatistics } from '@/types/api';
import type { RequestFn, GetTokenFn } from './utils';

export function createRequestsApi(request: RequestFn, getToken: GetTokenFn) {
    async function formDataRequest(url: string, method: string, data: Record<string, any>, saveAs?: 'draft' | 'submit') {
        const fd = new FormData();
        Object.keys(data).forEach((key) => {
            if (key === 'attachments' && Array.isArray(data[key])) { data[key].forEach((f: File) => fd.append('attachments', f)); }
            else if (key === 'attachment' && data[key] instanceof File) { fd.append('attachment', data[key]); }
            else if (Array.isArray(data[key])) { data[key].forEach((v: any) => fd.append(key, String(v))); }
            else if (data[key] !== null && data[key] !== undefined) { fd.append(key, String(data[key])); }
        });
        if (saveAs) fd.append('save_as', saveAs);
        const token = getToken();
        const headers: Record<string, string> = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const response = await fetch(url, { method, headers, body: fd });
        if (!response.ok) { let d = `${response.status} ${response.statusText}`; try { d = JSON.stringify(await response.json()); } catch {} throw new Error(d); }
        return response.json();
    }

    return {
        getRequests: (params?: Record<string, any>) => {
            const qp = new URLSearchParams();
            if (params) {
                const keys = ['status','type','search','page','limit','view','addressed_to_me','employee_id','created_from','created_to','date_from','date_to'];
                keys.forEach(k => { if (params[k]) qp.append(k, String(params[k])); });
            }
            const qs = qp.toString();
            return request(`/api/v1/requests/${qs ? '?' + qs : ''}`);
        },
        getRequest: (requestId: number) => request(`/api/v1/requests/${requestId}/`),
        getRequestEmployeeStatistics: (requestId: number): Promise<RequestEmployeeStatistics> =>
            request(`/api/v1/requests/${requestId}/employee-statistics/`),
        createRequest: (data: Record<string, any>, saveAs?: 'draft' | 'submit') => formDataRequest('/api/v1/requests/', 'POST', data, saveAs),
        updateRequest: (requestId: number, data: Record<string, any>, saveAs?: 'draft' | 'submit') => formDataRequest(`/api/v1/requests/${requestId}/`, 'PATCH', data, saveAs),
        deleteRequest: (requestId: number): Promise<void> => request(`/api/v1/requests/${requestId}/`, { method: 'DELETE' }),
        getRequestComments: (requestId: number) => request(`/api/v1/requests/${requestId}/comments/`),
        deleteRequestComment: (requestId: number, commentId: number): Promise<void> => request(`/api/v1/requests/${requestId}/comments/${commentId}/`, { method: 'DELETE' }),
        approveRequest: (requestId: number) => request(`/api/v1/requests/${requestId}/approve/`, { method: 'POST' }),
        rejectRequest: (requestId: number) => request(`/api/v1/requests/${requestId}/reject/`, { method: 'POST' }),
        cancelRequest: (requestId: number) => request(`/api/v1/requests/${requestId}/cancel/`, { method: 'POST' }),
        addRequestComment: (requestId: number, text: string) => request(`/api/v1/requests/${requestId}/comments/`, { method: 'POST', body: JSON.stringify({ text }) }),
    };
}
