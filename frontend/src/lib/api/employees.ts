/* eslint-disable @typescript-eslint/no-explicit-any */
import { type RequestFn } from './utils';

export function createEmployeesApi(request: RequestFn) {
    return {
        getSkills: () => request('/api/v1/skills/'),
        createSkill: (data: { name: string; description?: string }) =>
            request('/api/v1/skills/', {
                method: 'POST',
                body: JSON.stringify(data),
            }),
        getDirectoryLogin: () =>
            request('/api/v1/directory/me/login/'),
        refreshDirectoryLogin: () =>
            request('/api/v1/directory/me/login/refresh/', { method: 'POST' }),
        getEmployees: (params?: { search?: string; department?: string; page?: number; limit?: number; is_active?: boolean; ordering?: string }) => {
            const qp = new URLSearchParams();
            if (params?.search) qp.append('search', params.search);
            if (params?.department) qp.append('department', params.department);
            if (params?.page) qp.append('page', params.page.toString());
            if (params?.limit) qp.append('limit', params.limit.toString());
            if (params?.is_active !== undefined) qp.append('active', params.is_active.toString());
            if (params?.ordering) qp.append('ordering', params.ordering);
            const qs = qp.toString();
            return request(`/api/v1/employees/${qs ? '?' + qs : ''}`);
        },
        getEmployee: (id: number | string) => request(`/api/v1/employees/${id}/`),
        getPositions: () => request('/api/v1/positions/'),
        addEmployeeSkill: (
            id: number | string,
            data: { skill_id?: number; name?: string },
        ) =>
            request(`/api/v1/employees/${id}/add_skill/`, {
                method: 'POST',
                body: JSON.stringify(data),
            }),
        updateEmployee: (id: number | string, data: Record<string, any>) =>
            request(`/api/v1/employees/${id}/`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }),
        uploadEmployeeAvatar: (id: number | string, file: File) => {
            const fd = new FormData(); fd.append('avatar', file);
            return request(`/api/v1/employees/${id}/`, { method: 'PATCH', body: fd });
        },
        createEmployeeAction: (data: { employee: number; action: string; date: string; date_to?: string | null; comment?: string }) =>
            request('/api/v1/employee-actions/', { method: 'POST', body: JSON.stringify(data) }),
        updateEmployeeAction: (actionId: number, data: { action?: string; date?: string; date_to?: string | null; comment?: string }) =>
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
        createDepartment: (data: { name: string; description?: string }) =>
            request('/api/v1/departments/', {
                method: 'POST',
                body: JSON.stringify(data),
            }),
        deleteDepartment: (id: number | string) =>
            request(`/api/v1/departments/${id}/`, { method: 'DELETE' }),
        updateDepartment: (id: number | string, data: { name?: string; description?: string }) =>
            request(`/api/v1/departments/${id}/`, {
                method: 'PATCH',
                body: JSON.stringify(data),
            }),
        getDepartmentMembers: (id: number | string) =>
            request(`/api/v1/departments/${id}/members/`),
        getDepartmentDiscussionChat: (id: number | string) =>
            request(`/api/v1/departments/${id}/discussion-chat/`),
        getDepartmentCalendar: (id: number | string) =>
            request(`/api/v1/departments/${id}/calendar/`),
        getDepartmentUserPerms: (id: number | string) =>
            request(`/api/v1/departments/${id}/user-perms/`),
        setDepartmentHead: (id: number | string, head_id: number | null) =>
            request(`/api/v1/departments/${id}/set_head/`, {
                method: 'POST',
                body: JSON.stringify({ head_id }),
            }),
        addDepartmentMember: (id: number | string, employee_id: number) =>
            request(`/api/v1/departments/${id}/add_member/`, {
                method: 'POST',
                body: JSON.stringify({ employee_id }),
            }),
        removeDepartmentMember: (id: number | string, employee_id: number) =>
            request(`/api/v1/departments/${id}/remove_member/`, {
                method: 'POST',
                body: JSON.stringify({ employee_id }),
            }),
        setDepartmentMemberRole: (id: number | string, data: { employee_id: number; role_id: number | null }) =>
            request(`/api/v1/departments/${id}/set_member_role/`, {
                method: 'POST',
                body: JSON.stringify(data),
            }),
        getMyDepartments: () => request('/api/v1/departments/my-departments/'),
        getDepartmentRoles: (params?: { department?: number | string; page?: number; limit?: number; ordering?: string }) => {
            const qp = new URLSearchParams();
            if (params?.department) qp.append('department', String(params.department));
            if (params?.page) qp.append('page', params.page.toString());
            if (params?.limit) qp.append('limit', params.limit.toString());
            if (params?.ordering) qp.append('ordering', params.ordering);
            const qs = qp.toString();
            return request(`/api/v1/department-roles/${qs ? '?' + qs : ''}`);
        },
        createDepartmentRole: (data: { department: number; name: string }) =>
            request('/api/v1/department-roles/', {
                method: 'POST',
                body: JSON.stringify(data),
            }),
        updateDepartmentRole: (id: number | string, data: { name?: string }) =>
            request(`/api/v1/department-roles/${id}/`, {
                method: 'PATCH',
                body: JSON.stringify(data),
            }),
        deleteDepartmentRole: (id: number | string) =>
            request(`/api/v1/department-roles/${id}/`, { method: 'DELETE' }),
        getDepartmentRolePermChoices: () =>
            request('/api/v1/department-roles/perm_choices/'),
        getDepartmentRoleAssignments: (id: number | string, params?: { active?: boolean }) => {
            const qp = new URLSearchParams();
            if (params?.active !== undefined) qp.append('active', String(params.active));
            const qs = qp.toString();
            return request(`/api/v1/department-roles/${id}/assignments/${qs ? '?' + qs : ''}`);
        },
    };
}
