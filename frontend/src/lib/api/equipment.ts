/* eslint-disable @typescript-eslint/no-explicit-any */
import { buildQuery, type RequestFn, type GetTokenFn } from './utils';

export function createEquipmentApi(request: RequestFn, getToken: GetTokenFn) {
    return {
        getEquipmentCategories: (params?: Record<string, string | number>) => request(`/api/v1/procurement/equipment-categories/${buildQuery(params)}`),
        getEquipment: (params?: Record<string, string | number>) => request(`/api/v1/procurement/equipment/${buildQuery(params)}`),
        getEquipmentDetail: (id: number) => request(`/api/v1/procurement/equipment/${id}/`),
        getMyEquipment: (params?: Record<string, string | number>) => request(`/api/v1/procurement/equipment/my_equipment/${buildQuery(params)}`),
        getWarrantyExpiringEquipment: () => request('/api/v1/procurement/equipment/warranty_expiring/'),
        generateEquipmentInventoryNumber: (): Promise<{ inventory_number: string }> => request('/api/v1/procurement/equipment/generate-inventory-number/'),
        getEquipmentCreateOptions: () => request('/api/v1/procurement/equipment/create-options/'),
        createEquipment: (data: Record<string, any>) => request('/api/v1/procurement/equipment/', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }),
        updateEquipment: (id: number, data: Record<string, any>) => request(`/api/v1/procurement/equipment/${id}/`, { method: 'PATCH', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data) }),
        deleteEquipment: (id: number): Promise<void> => request(`/api/v1/procurement/equipment/${id}/`, { method: 'DELETE' }),
        transferEquipment: (id: number, data: { to_department?: number | null; to_person?: number | null; reason?: string }) =>
            request(`/api/v1/procurement/equipment/${id}/transfer/`, { method: 'POST', body: JSON.stringify(data) }),
        writeOffEquipment: (id: number, reason: string) =>
            request(`/api/v1/procurement/equipment/${id}/write_off/`, { method: 'POST', body: JSON.stringify({ reason }) }),
        addEquipmentMaintenance: (id: number, data: { type: string; description?: string; cost?: string | number; date?: string }) =>
            request(`/api/v1/procurement/equipment/${id}/add_maintenance/`, { method: 'POST', body: JSON.stringify(data) }),
        getEquipmentTransferHistory: (id: number) => request(`/api/v1/procurement/equipment/${id}/transfer_history/`),
        getMaintenanceRecords: (params?: Record<string, string | number>) => request(`/api/v1/procurement/maintenance/${buildQuery(params)}`),
        getEquipmentCategoryTree: () => request('/api/v1/procurement/equipment-categories/tree/'),
        getEquipmentCategoryChildren: (categoryId: number) => request(`/api/v1/procurement/equipment-categories/${categoryId}/children/`),
        getEquipmentQrCodeBlobUrl: async (equipmentId: number): Promise<string> => {
            const headers: Record<string, string> = {};
            const token = getToken();
            if (token) headers['Authorization'] = `Bearer ${token}`;
            const response = await fetch(`/api/v1/procurement/equipment/${equipmentId}/qr_code/`, { method: 'GET', headers });
            if (!response.ok) throw new Error(`API Error: ${response.status} ${response.statusText}`);
            const blob = await response.blob();
            return URL.createObjectURL(blob);
        },
        getEquipmentComments: (equipmentId: number) => request(`/api/v1/procurement/equipment/${equipmentId}/comments/`),
        addEquipmentComment: (equipmentId: number, text: string) => request(`/api/v1/procurement/equipment/${equipmentId}/comments/`, { method: 'POST', body: JSON.stringify({ text }) }),
        deleteEquipmentComment: (equipmentId: number, commentId: number): Promise<void> => request(`/api/v1/procurement/equipment/${equipmentId}/comments/${commentId}/`, { method: 'DELETE' }),
    };
}
