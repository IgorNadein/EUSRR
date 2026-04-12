/* eslint-disable @typescript-eslint/no-explicit-any */
import { type RequestFn } from './utils';

export function createEmployeesApi(request: RequestFn) {
    return {
        getDirectoryLogin: () =>
            request('/api/v1/directory/me/login/'),
        refreshDirectoryLogin: () =>
            request('/api/v1/directory/me/login/refresh/', { method: 'POST' }),
        getEmployees: (params?: { search?: string; department?: string; page?: number; limit?: number; is_active?: boolean }) => {
            const qp = new URLSearchParams();
            if (params?.search) qp.append('search', params.search);
            if (params?.department) qp.append('department', params.department);
            if (params?.page) qp.append('page', params.page.toString());
            if (params?.limit) qp.append('limit', params.limit.toString());
            if (params?.is_active !== undefined) qp.append('active', params.is_active.toString());
            const qs = qp.toString();
            return request(`/api/v1/employees/${qs ? '?' + qs : ''}`);
        },
        getEmployee: (id: number | string) => request(`/api/v1/employees/${id}/`),
        updateEmployee: (id: number | string, data: Record<string, any>) =>
            request(`/api/v1/employees/${id}/`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }),
        uploadEmployeeAvatar: (id: number | string, file: File) => {
            const fd = new FormData(); fd.append('avatar', file);
            return request(`/api/v1/employees/${id}/`, { method: 'PATCH', body: fd });
        },
        createEmployeeAction: (data: { employee: number; action: string; date: string; comment?: string }) =>
            request('/api/v1/employee-actions/', { method: 'POST', body: JSON.stringify(data) }),
        updateEmployeeAction: (actionId: number, data: { action?: string; date?: string; comment?: string }) =>
            request(`/api/v1/employee-actions/${actionId}/`, { method: 'PATCH', body: JSON.stringify(data) }),
        deleteEmployeeAction: (actionId: number) =>
            request(`/api/v1/employee-actions/${actionId}/`, { method: 'DELETE' }),
        getDepartments: (params?: { search?: string; page?: number; limit?: number }) => {
            const qp = new URLSearchParams();
            if (params?.search) qp.append('search', params.search);
            if (params?.page) qp.append('page', params.page.toString());
            if (params?.limit) qp.append('limit', params.limit.toString());
            const qs = qp.toString();
            return request(`/api/v1/departments/${qs ? '?' + qs : ''}`);
        },
        getDepartment: (id: number | string) => request(`/api/v1/departments/${id}/`),
    };
}
