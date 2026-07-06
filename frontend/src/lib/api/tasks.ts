/* eslint-disable @typescript-eslint/no-explicit-any */
import type {
    TaskBoard,
    TaskCard,
    TaskColumn,
    TaskActivity,
    TaskLabel,
    TaskLinkedCalendarEvent,
    TaskLinkedMessage,
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
        getCalendarEventLinkedTasks: (eventId: number): Promise<TaskCard[]> =>
            request(`/api/v1/tasks/linked-event-tasks/?event_id=${eventId}`),
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
