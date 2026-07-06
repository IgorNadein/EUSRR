/* eslint-disable @typescript-eslint/no-explicit-any */
import type {
    TaskBoard,
    TaskCard,
    TaskColumn,
    TaskActivity,
    TaskComment,
    TaskLabel,
    TaskLinkedCalendarEvent,
    TaskLinkedDocument,
    TaskLinkedEmployee,
    TaskLinkedGuest,
    TaskLinkedGuestVisit,
    TaskLinkedMessage,
    TaskLinkedProcurementRequest,
    TaskLinkedRequest,
} from "@/types/api";
import { buildQuery, type RequestFn } from "./utils";

export function createTasksApi(request: RequestFn) {
    return {
        getTaskBoards: (params?: Record<string, string | number>) =>
            request(`/api/v1/tasks/boards/${buildQuery(params)}`),
        getDefaultTaskBoard: (): Promise<TaskBoard> =>
            request("/api/v1/tasks/boards/default/"),
        getTaskBoard: (id: number): Promise<TaskBoard> =>
            request(`/api/v1/tasks/boards/${id}/`),
        createTaskBoard: (data: Record<string, any>): Promise<TaskBoard> =>
            request("/api/v1/tasks/boards/", {
                method: "POST",
                body: JSON.stringify(data),
            }),
        updateTaskBoard: (id: number, data: Record<string, any>): Promise<TaskBoard> =>
            request(`/api/v1/tasks/boards/${id}/`, {
                method: "PATCH",
                body: JSON.stringify(data),
            }),
        deleteTaskBoard: (id: number): Promise<void> =>
            request(`/api/v1/tasks/boards/${id}/`, { method: "DELETE" }),
        createTaskColumn: (data: Record<string, any>): Promise<TaskColumn> =>
            request("/api/v1/tasks/columns/", {
                method: "POST",
                body: JSON.stringify(data),
            }),
        createTaskLabel: (data: Record<string, any>): Promise<TaskLabel> =>
            request("/api/v1/tasks/labels/", {
                method: "POST",
                body: JSON.stringify(data),
            }),
        createTask: (data: Record<string, any>): Promise<TaskCard> =>
            request("/api/v1/tasks/", {
                method: "POST",
                body: JSON.stringify(data),
            }),
        updateTask: (id: number, data: Record<string, any>): Promise<TaskCard> =>
            request(`/api/v1/tasks/${id}/`, {
                method: "PATCH",
                body: JSON.stringify(data),
            }),
        moveTask: (
            id: number,
            data: { column: number; position?: number },
        ): Promise<TaskCard> =>
            request(`/api/v1/tasks/${id}/move/`, {
                method: "POST",
                body: JSON.stringify(data),
            }),
        getTaskActivity: (id: number): Promise<TaskActivity[]> =>
            request(`/api/v1/tasks/${id}/activity/`),
        getTaskComments: (id: number): Promise<TaskComment[]> =>
            request(`/api/v1/tasks/${id}/comments/`),
        addTaskComment: (id: number, text: string): Promise<TaskComment> =>
            request(`/api/v1/tasks/${id}/comments/`, {
                method: "POST",
                body: JSON.stringify({ text }),
            }),
        deleteTaskComment: (id: number, commentId: number): Promise<void> =>
            request(`/api/v1/tasks/${id}/comments/${commentId}/`, {
                method: "DELETE",
            }),
        getCalendarEventLinkedTasks: (eventId: number): Promise<TaskCard[]> =>
            request(`/api/v1/tasks/linked-event-tasks/?event_id=${eventId}`),
        getDocumentLinkedTasks: (documentId: number): Promise<TaskCard[]> =>
            request(`/api/v1/tasks/linked-document-tasks/?document_id=${documentId}`),
        getRequestLinkedTasks: (requestId: number): Promise<TaskCard[]> =>
            request(`/api/v1/tasks/linked-request-tasks/?request_id=${requestId}`),
        getProcurementRequestLinkedTasks: (requestId: number): Promise<TaskCard[]> =>
            request(`/api/v1/tasks/linked-procurement-request-tasks/?procurement_request_id=${requestId}`),
        getEmployeeLinkedTasks: (employeeId: number): Promise<TaskCard[]> =>
            request(`/api/v1/tasks/linked-employee-tasks/?employee_id=${employeeId}`),
        getGuestLinkedTasks: (guestId: number): Promise<TaskCard[]> =>
            request(`/api/v1/tasks/linked-guest-tasks/?guest_id=${guestId}`),
        getGuestVisitLinkedTasks: (guestVisitId: number): Promise<TaskCard[]> =>
            request(`/api/v1/tasks/linked-guest-visit-tasks/?guest_visit_id=${guestVisitId}`),
        getTaskLinkedMessages: (id: number): Promise<TaskLinkedMessage[]> =>
            request(`/api/v1/tasks/${id}/linked-messages/`),
        linkTaskMessage: (id: number, messageId: number): Promise<TaskLinkedMessage> =>
            request(`/api/v1/tasks/${id}/linked-messages/`, {
                method: "POST",
                body: JSON.stringify({ message_id: messageId }),
            }),
        unlinkTaskMessage: (id: number, linkId: number): Promise<void> =>
            request(`/api/v1/tasks/${id}/linked-messages/${linkId}/`, {
                method: "DELETE",
            }),
        getTaskLinkedDocuments: (id: number): Promise<TaskLinkedDocument[]> =>
            request(`/api/v1/tasks/${id}/linked-documents/`),
        linkTaskDocument: (id: number, documentId: number): Promise<TaskLinkedDocument> =>
            request(`/api/v1/tasks/${id}/linked-documents/`, {
                method: "POST",
                body: JSON.stringify({ document_id: documentId }),
            }),
        unlinkTaskDocument: (id: number, linkId: number): Promise<void> =>
            request(`/api/v1/tasks/${id}/linked-documents/${linkId}/`, {
                method: "DELETE",
            }),
        getTaskLinkedRequests: (id: number): Promise<TaskLinkedRequest[]> =>
            request(`/api/v1/tasks/${id}/linked-requests/`),
        linkTaskRequest: (id: number, requestId: number): Promise<TaskLinkedRequest> =>
            request(`/api/v1/tasks/${id}/linked-requests/`, {
                method: "POST",
                body: JSON.stringify({ request_id: requestId }),
            }),
        unlinkTaskRequest: (id: number, linkId: number): Promise<void> =>
            request(`/api/v1/tasks/${id}/linked-requests/${linkId}/`, {
                method: "DELETE",
            }),
        getTaskLinkedProcurementRequests: (id: number): Promise<TaskLinkedProcurementRequest[]> =>
            request(`/api/v1/tasks/${id}/linked-procurement-requests/`),
        linkTaskProcurementRequest: (id: number, requestId: number): Promise<TaskLinkedProcurementRequest> =>
            request(`/api/v1/tasks/${id}/linked-procurement-requests/`, {
                method: "POST",
                body: JSON.stringify({ procurement_request_id: requestId }),
            }),
        unlinkTaskProcurementRequest: (id: number, linkId: number): Promise<void> =>
            request(`/api/v1/tasks/${id}/linked-procurement-requests/${linkId}/`, {
                method: "DELETE",
            }),
        getTaskLinkedEmployees: (id: number): Promise<TaskLinkedEmployee[]> =>
            request(`/api/v1/tasks/${id}/linked-employees/`),
        linkTaskEmployee: (id: number, employeeId: number): Promise<TaskLinkedEmployee> =>
            request(`/api/v1/tasks/${id}/linked-employees/`, {
                method: "POST",
                body: JSON.stringify({ employee_id: employeeId }),
            }),
        unlinkTaskEmployee: (id: number, linkId: number): Promise<void> =>
            request(`/api/v1/tasks/${id}/linked-employees/${linkId}/`, {
                method: "DELETE",
            }),
        getTaskLinkedGuests: (id: number): Promise<TaskLinkedGuest[]> =>
            request(`/api/v1/tasks/${id}/linked-guests/`),
        linkTaskGuest: (id: number, guestId: number): Promise<TaskLinkedGuest> =>
            request(`/api/v1/tasks/${id}/linked-guests/`, {
                method: "POST",
                body: JSON.stringify({ guest_id: guestId }),
            }),
        unlinkTaskGuest: (id: number, linkId: number): Promise<void> =>
            request(`/api/v1/tasks/${id}/linked-guests/${linkId}/`, {
                method: "DELETE",
            }),
        getTaskLinkedGuestVisits: (id: number): Promise<TaskLinkedGuestVisit[]> =>
            request(`/api/v1/tasks/${id}/linked-guest-visits/`),
        linkTaskGuestVisit: (id: number, guestVisitId: number): Promise<TaskLinkedGuestVisit> =>
            request(`/api/v1/tasks/${id}/linked-guest-visits/`, {
                method: "POST",
                body: JSON.stringify({ guest_visit_id: guestVisitId }),
            }),
        unlinkTaskGuestVisit: (id: number, linkId: number): Promise<void> =>
            request(`/api/v1/tasks/${id}/linked-guest-visits/${linkId}/`, {
                method: "DELETE",
            }),
        getTaskLinkedEvents: (id: number): Promise<TaskLinkedCalendarEvent[]> =>
            request(`/api/v1/tasks/${id}/linked-events/`),
        linkTaskCalendarEvent: (id: number, eventId: number): Promise<TaskLinkedCalendarEvent> =>
            request(`/api/v1/tasks/${id}/linked-events/`, {
                method: "POST",
                body: JSON.stringify({ event_id: eventId }),
            }),
        unlinkTaskCalendarEvent: (id: number, linkId: number): Promise<void> =>
            request(`/api/v1/tasks/${id}/linked-events/${linkId}/`, {
                method: "DELETE",
            }),
        deleteTask: (id: number): Promise<void> =>
            request(`/api/v1/tasks/${id}/`, { method: "DELETE" }),
    };
}
