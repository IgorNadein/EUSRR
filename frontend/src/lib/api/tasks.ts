/* eslint-disable @typescript-eslint/no-explicit-any */
import type {
    TaskBoard,
    TaskCard,
    TaskColumn,
    TaskActivity,
    TaskAttachment,
    TaskChecklistItem,
    TaskComment,
    TaskLabel,
    TaskLinkedAttendanceRecord,
    TaskLinkedCalendarEvent,
    TaskLinkedDocument,
    TaskLinkedEmployee,
    TaskLinkedGuest,
    TaskLinkedGuestVisit,
    TaskLinkedMessage,
    TaskLinkedPost,
    TaskLinkedProcurementRequest,
    TaskLinkedRequest,
    TaskExternalLink,
} from "@/types/api";
import { buildQuery, type RawRequestFn, type RequestFn } from "./utils";

function parseDownloadFilename(response: Response, fallback: string): string {
    const disposition = response.headers.get("content-disposition") || "";
    const encodedMatch = disposition.match(/filename\*=UTF-8''([^;]+)/);
    const plainMatch = disposition.match(/filename="?([^";]+)"?/);
    return encodedMatch?.[1]
        ? decodeURIComponent(encodedMatch[1])
        : plainMatch?.[1] || fallback;
}

export function createTasksApi(request: RequestFn, requestRaw: RawRequestFn) {
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
        setDefaultTaskBoard: (id: number): Promise<TaskBoard> =>
            request(`/api/v1/tasks/boards/${id}/set-default/`, { method: "POST" }),
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
        completeTask: (id: number): Promise<TaskCard> =>
            request(`/api/v1/tasks/${id}/complete/`, {
                method: "POST",
            }),
        claimTask: (id: number): Promise<TaskCard> =>
            request(`/api/v1/tasks/${id}/claim/`, {
                method: "POST",
            }),
        getTaskActivity: (id: number): Promise<TaskActivity[]> =>
            request(`/api/v1/tasks/${id}/activity/`),
        getTaskAttachments: (id: number): Promise<TaskAttachment[]> =>
            request(`/api/v1/tasks/${id}/attachments/`),
        uploadTaskAttachments: (id: number, files: File[]): Promise<TaskAttachment[]> => {
            const formData = new FormData();
            files.forEach((file) => formData.append("files", file));
            return request(`/api/v1/tasks/${id}/attachments/`, {
                method: "POST",
                body: formData,
            });
        },
        downloadTaskAttachment: async (
            taskId: number,
            attachment: TaskAttachment,
        ): Promise<{ blob: Blob; filename: string }> => {
            const response = await requestRaw(
                attachment.download_url || `/api/v1/tasks/${taskId}/attachments/${attachment.id}/download/`,
            );
            return {
                blob: await response.blob(),
                filename: parseDownloadFilename(response, attachment.file_name),
            };
        },
        deleteTaskAttachment: (taskId: number, attachmentId: number): Promise<void> =>
            request(`/api/v1/tasks/${taskId}/attachments/${attachmentId}/`, {
                method: "DELETE",
            }),
        getTaskChecklist: (id: number): Promise<TaskChecklistItem[]> =>
            request(`/api/v1/tasks/${id}/checklist/`),
        addTaskChecklistItem: (
            id: number,
            data: { title: string; position?: number; is_completed?: boolean },
        ): Promise<TaskChecklistItem> =>
            request(`/api/v1/tasks/${id}/checklist/`, {
                method: "POST",
                body: JSON.stringify(data),
            }),
        updateTaskChecklistItem: (
            id: number,
            itemId: number,
            data: { title?: string; position?: number; is_completed?: boolean },
        ): Promise<TaskChecklistItem> =>
            request(`/api/v1/tasks/${id}/checklist/${itemId}/`, {
                method: "PATCH",
                body: JSON.stringify(data),
            }),
        deleteTaskChecklistItem: (id: number, itemId: number): Promise<void> =>
            request(`/api/v1/tasks/${id}/checklist/${itemId}/`, {
                method: "DELETE",
            }),
        getTaskComments: (id: number): Promise<TaskComment[]> =>
            request(`/api/v1/tasks/${id}/comments/`),
        addTaskComment: (id: number, text: string): Promise<TaskComment> =>
            request(`/api/v1/tasks/${id}/comments/`, {
                method: "POST",
                body: JSON.stringify({ text }),
            }),
        updateTaskComment: (id: number, commentId: number, text: string): Promise<TaskComment> =>
            request(`/api/v1/tasks/${id}/comments/${commentId}/`, {
                method: "PATCH",
                body: JSON.stringify({ text }),
            }),
        deleteTaskComment: (id: number, commentId: number): Promise<void> =>
            request(`/api/v1/tasks/${id}/comments/${commentId}/`, {
                method: "DELETE",
            }),
        getPostLinkedTasks: (postId: number): Promise<TaskCard[]> =>
            request(`/api/v1/tasks/linked-post-tasks/?post_id=${postId}`),
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
        getAttendanceRecordLinkedTasks: (attendanceRecordId: number): Promise<TaskCard[]> =>
            request(`/api/v1/tasks/linked-attendance-record-tasks/?attendance_record_id=${attendanceRecordId}`),
        getTaskLinkedPosts: (id: number): Promise<TaskLinkedPost[]> =>
            request(`/api/v1/tasks/${id}/linked-posts/`),
        linkTaskPost: (id: number, postId: number): Promise<TaskLinkedPost> =>
            request(`/api/v1/tasks/${id}/linked-posts/`, {
                method: "POST",
                body: JSON.stringify({ post_id: postId }),
            }),
        unlinkTaskPost: (id: number, linkId: number): Promise<void> =>
            request(`/api/v1/tasks/${id}/linked-posts/${linkId}/`, {
                method: "DELETE",
            }),
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
        getTaskLinkedAttendanceRecords: (id: number): Promise<TaskLinkedAttendanceRecord[]> =>
            request(`/api/v1/tasks/${id}/linked-attendance-records/`),
        linkTaskAttendanceRecord: (id: number, attendanceRecordId: number): Promise<TaskLinkedAttendanceRecord> =>
            request(`/api/v1/tasks/${id}/linked-attendance-records/`, {
                method: "POST",
                body: JSON.stringify({ attendance_record_id: attendanceRecordId }),
            }),
        unlinkTaskAttendanceRecord: (id: number, linkId: number): Promise<void> =>
            request(`/api/v1/tasks/${id}/linked-attendance-records/${linkId}/`, {
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
        getTaskExternalLinks: (id: number): Promise<TaskExternalLink[]> =>
            request(`/api/v1/tasks/${id}/external-links/`),
        addTaskExternalLink: (
            id: number,
            data: { url: string; title?: string },
        ): Promise<TaskExternalLink> =>
            request(`/api/v1/tasks/${id}/external-links/`, {
                method: "POST",
                body: JSON.stringify(data),
            }),
        deleteTaskExternalLink: (id: number, linkId: number): Promise<void> =>
            request(`/api/v1/tasks/${id}/external-links/${linkId}/`, {
                method: "DELETE",
            }),
        deleteTask: (id: number): Promise<void> =>
            request(`/api/v1/tasks/${id}/`, { method: "DELETE" }),
    };
}
