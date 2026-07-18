/**
 * API Client — assembled from domain modules.
 * Import: import { apiClient } from "@/lib/api"
 */
import { ApiClientBase } from './client';
import { createEmployeesApi } from './employees';
import { createAuthApi } from './auth';
import { createDocumentsApi } from './documents';
import { createMessagesApi } from './messages';
import { createNotificationsApi } from './notifications';
import { createCalendarApi } from './calendar';
import { createFeedApi } from './feed';
import { createRequestsApi } from './requests';
import { createEquipmentApi } from './equipment';
import { createProcurementApi } from './procurement';
import { createAttendanceApi } from './attendance';
import { createGuestsApi } from './guests';
import { createTasksApi } from './tasks';
import { createFinanceApi } from './finance';

const base = new ApiClientBase();
const req = base.request.bind(base);
const tok = base.getToken.bind(base);
const raw = base.requestRaw.bind(base);

export const apiClient = Object.assign(base, {
    ...createAuthApi(req),
    ...createEmployeesApi(req),
    ...createDocumentsApi(req, tok, raw),
    ...createMessagesApi(req, tok),
    ...createNotificationsApi(req),
    ...createCalendarApi(req, tok),
    ...createFeedApi(req, tok),
    ...createRequestsApi(req, tok),
    ...createEquipmentApi(req, tok),
    ...createProcurementApi(req, raw),
    ...createAttendanceApi(req, tok),
    ...createGuestsApi(req),
    ...createTasksApi(req, raw),
    ...createFinanceApi(req),
});

export default apiClient;
