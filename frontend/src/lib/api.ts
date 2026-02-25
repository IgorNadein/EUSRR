/**
 * API Client для работы с Django Backend через Next.js API proxy
 * Все запросы идут на /api/* и проксируются на backend
 */

interface LoginCredentials {
    email?: string;
    phone?: string;
    password: string;
}

interface LoginResponse {
    access: string;
    refresh: string;
}

class ApiClient {
    private tokenKey = 'access_token';
    private refreshTokenKey = 'refresh_token';

    private getToken(): string | null {
        if (typeof window === 'undefined') return null;
        return localStorage.getItem(this.tokenKey);
    }

    private setToken(token: string): void {
        if (typeof window !== 'undefined') {
            localStorage.setItem(this.tokenKey, token);
        }
    }

    private setRefreshToken(token: string): void {
        if (typeof window !== 'undefined') {
            localStorage.setItem(this.refreshTokenKey, token);
        }
    }

    clearToken(): void {
        if (typeof window !== 'undefined') {
            localStorage.removeItem(this.tokenKey);
            localStorage.removeItem(this.refreshTokenKey);
        }
    }

    private async request<T>(
        endpoint: string,
        options: RequestInit = {}
    ): Promise<T> {
        const headers: Record<string, string> = {
            'Content-Type': 'application/json',
            ...(options.headers as Record<string, string>),
        };

        // Автоматически добавляем токен если он есть
        const token = this.getToken();
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(endpoint, {
            ...options,
            headers,
        });

        if (!response.ok) {
            // Попытка получить детали ошибки
            let errorDetails = '';
            try {
                const errorData = await response.json();
                errorDetails = errorData.detail || JSON.stringify(errorData);
            } catch {
                errorDetails = response.statusText;
            }
            throw new Error(`API Error: ${response.status} ${errorDetails}`);
        }

        // Для DELETE запросов может не быть тела ответа
        if (options.method === 'DELETE' && response.status === 204) {
            return undefined as T;
        }

        // Проверяем, есть ли контент в ответе
        const contentLength = response.headers.get('content-length');
        if (contentLength === '0' || response.status === 204) {
            return undefined as T;
        }

        return response.json();
    }

    // Авторизация
    async login(credentials: LoginCredentials): Promise<void> {
        const response = await fetch('/api/auth/token/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(credentials),
        });

        if (!response.ok) {
            throw new Error(`Login failed: ${response.status}`);
        }

        const data: LoginResponse = await response.json();
        this.setToken(data.access);
        this.setRefreshToken(data.refresh);
    }

    // Получение текущего пользователя
    async getCurrentUser(): Promise<any> {
        return this.request('/api/v1/employees/me/');
    }

    // Сотрудники
    async getEmployees(params?: { search?: string; department?: string; page?: number; limit?: number }): Promise<any> {
        const queryParams = new URLSearchParams();
        if (params?.search) queryParams.append('search', params.search);
        if (params?.department) queryParams.append('department', params.department);
        if (params?.page) queryParams.append('page', params.page.toString());
        if (params?.limit) queryParams.append('limit', params.limit.toString());

        const url = `/api/v1/employees/${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
        return this.request(url);
    }

    async getEmployee(id: number | string): Promise<any> {
        return this.request(`/api/v1/employees/${id}/`);
    }

    // Отделы
    async getDepartments(params?: { search?: string; page?: number; limit?: number }): Promise<any> {
        const queryParams = new URLSearchParams();
        if (params?.search) queryParams.append('search', params.search);
        if (params?.page) queryParams.append('page', params.page.toString());
        if (params?.limit) queryParams.append('limit', params.limit.toString());

        const url = `/api/v1/departments/${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
        return this.request(url);
    }

    async getDepartment(id: number | string): Promise<any> {
        return this.request(`/api/v1/departments/${id}/`);
    }

    // Посты (лента новостей)
    async getPosts(params?: { page?: number; search?: string; limit?: number }): Promise<any> {
        const queryParams = new URLSearchParams();
        if (params?.page) queryParams.append('page', params.page.toString());
        if (params?.search) queryParams.append('search', params.search);
        if (params?.limit) queryParams.append('limit', params.limit.toString());

        const url = `/api/v1/posts/${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
        return this.request(url);
    }

    // Документы
    async getDocuments(params?: { search?: string; type?: string; page?: number; limit?: number }): Promise<any> {
        const queryParams = new URLSearchParams();
        if (params?.search) queryParams.append('search', params.search);
        if (params?.type) queryParams.append('type', params.type);
        if (params?.page) queryParams.append('page', params.page.toString());
        if (params?.limit) queryParams.append('limit', params.limit.toString());

        const url = `/api/v1/documents/${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
        return this.request(url);
    }

    // Заявки
    async getRequests(params?: { status?: string; type?: string; search?: string; page?: number; limit?: number }): Promise<any> {
        const queryParams = new URLSearchParams();
        if (params?.status) queryParams.append('status', params.status);
        if (params?.type) queryParams.append('type', params.type);
        if (params?.search) queryParams.append('search', params.search);
        if (params?.page) queryParams.append('page', params.page.toString());
        if (params?.limit) queryParams.append('limit', params.limit.toString());

        const url = `/api/v1/requests/${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
        return this.request(url);
    }

    async createRequest(data: any, saveAs?: 'draft' | 'submitted'): Promise<any> {
        const formData = new FormData();

        // Добавляем все поля из data
        Object.keys(data).forEach((key) => {
            if (key === 'attachments' && Array.isArray(data[key])) {
                data[key].forEach((file: File) => {
                    formData.append('attachments', file);
                });
            } else if (data[key] !== null && data[key] !== undefined) {
                formData.append(key, data[key]);
            }
        });

        if (saveAs) {
            formData.append('save_as', saveAs);
        }

        const token = this.getToken();
        const headers: Record<string, string> = {};
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch('/api/v1/requests/', {
            method: 'POST',
            headers,
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`API Error: ${response.status} ${response.statusText}`);
        }

        return response.json();
    }

    async updateRequest(requestId: number, data: any, saveAs?: 'draft' | 'submitted'): Promise<any> {
        const formData = new FormData();

        Object.keys(data).forEach((key) => {
            if (key === 'attachments' && Array.isArray(data[key])) {
                data[key].forEach((file: File) => {
                    formData.append('attachments', file);
                });
            } else if (data[key] !== null && data[key] !== undefined) {
                formData.append(key, data[key]);
            }
        });

        if (saveAs) {
            formData.append('save_as', saveAs);
        }

        const token = this.getToken();
        const headers: Record<string, string> = {};
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(`/api/v1/requests/${requestId}/`, {
            method: 'PATCH',
            headers,
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`API Error: ${response.status} ${response.statusText}`);
        }

        return response.json();
    }

    async deleteRequest(requestId: number): Promise<void> {
        await this.request(`/api/v1/requests/${requestId}/`, {
            method: 'DELETE',
        });
    }

    async getRequestComments(requestId: number): Promise<any> {
        return this.request(`/api/v1/requests/${requestId}/comments/`);
    }

    async deleteRequestComment(requestId: number, commentId: number): Promise<void> {
        await this.request(`/api/v1/requests/${requestId}/comments/${commentId}/`, {
            method: 'DELETE',
        });
    }

    // Чаты
    async getChats(params?: { search?: string; page?: number; limit?: number }): Promise<any> {
        const queryParams = new URLSearchParams();
        if (params?.search) queryParams.append('search', params.search);
        if (params?.page) queryParams.append('page', params.page.toString());
        if (params?.limit) queryParams.append('limit', params.limit.toString());

        const url = `/api/v1/communications/chats/${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
        return this.request(url);
    }

    async getChat(chatId: number | string): Promise<any> {
        return this.request(`/api/v1/communications/chats/${chatId}/`);
    }

    async getChatMessages(chatId: number | string, params?: { limit?: number; before?: number; after?: number }): Promise<any> {
        const queryParams = new URLSearchParams();
        if (params?.limit) queryParams.append('limit', params.limit.toString());
        if (params?.before) queryParams.append('before', params.before.toString());
        if (params?.after) queryParams.append('after', params.after.toString());

        const url = `/api/v1/communications/chats/${chatId}/messages/${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
        return this.request(url);
    }

    async getChatMessagesAround(chatId: number | string, params?: { limit?: number; around_id?: number }): Promise<any> {
        const queryParams = new URLSearchParams();
        if (params?.limit) queryParams.append('limit', params.limit.toString());
        if (params?.around_id) queryParams.append('around_id', params.around_id.toString());

        const url = `/api/v1/communications/chats/${chatId}/messages-around/${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
        return this.request(url);
    }

    async sendMessage(chatId: number | string, text: string, replyTo?: number): Promise<any> {
        return this.request(`/api/v1/communications/chats/${chatId}/messages/`, {
            method: 'POST',
            body: JSON.stringify({ text, reply_to: replyTo }),
        });
    }

    async sendMessageWithFiles(chatId: number | string, text: string, files: File[], replyTo?: number): Promise<any> {
        const formData = new FormData();
        formData.append('text', text);
        if (replyTo) {
            formData.append('reply_to', replyTo.toString());
        }
        files.forEach((file) => {
            formData.append('attachments', file);
        });

        const token = this.getToken();
        const headers: Record<string, string> = {};
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(`/api/v1/communications/chats/${chatId}/messages/`, {
            method: 'POST',
            headers,
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`API Error: ${response.status} ${response.statusText}`);
        }

        return response.json();
    }

    async updateMessage(messageId: number, text: string): Promise<any> {
        return this.request(`/api/v1/communications/messages/${messageId}/`, {
            method: 'PATCH',
            body: JSON.stringify({ text }),
        });
    }

    async deleteMessage(messageId: number): Promise<void> {
        await this.request(`/api/v1/communications/messages/${messageId}/`, {
            method: 'DELETE',
        });
    }

    // Уведомления
    async getNotifications(): Promise<any> {
        return this.request('/api/v1/notifications/');
    }

    async markNotificationAsRead(id: number): Promise<void> {
        await this.request(`/api/v1/notifications/${id}/mark_read/`, {
            method: 'POST',
        });
    }

    async markAllNotificationsAsRead(): Promise<void> {
        await this.request('/api/v1/notifications/mark_all_read/', {
            method: 'POST',
        });
    }

    // Календарь (django-scheduler API)
    async getCalendarEvents(params?: { start?: string; end?: string; calendar?: number }): Promise<any> {
        const queryParams = new URLSearchParams();
        if (params?.start) queryParams.append('start', params.start);
        if (params?.end) queryParams.append('end', params.end);
        if (params?.calendar) queryParams.append('calendar', params.calendar.toString());

        const url = `/api/v1/schedule/events/${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
        return this.request(url);
    }

    async getMyEvents(params?: { start?: string; end?: string }): Promise<any> {
        const queryParams = new URLSearchParams();
        if (params?.start) queryParams.append('start', params.start);
        if (params?.end) queryParams.append('end', params.end);

        const url = `/api/v1/schedule/events/my-events/${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
        return this.request(url);
    }

    async getCalendars(): Promise<any> {
        return this.request('/api/v1/schedule/calendars/');
    }

    async getCalendar(id: number): Promise<any> {
        return this.request(`/api/v1/schedule/calendars/${id}/`);
    }

    async createCalendar(data: { name: string; slug?: string }): Promise<any> {
        return this.request('/api/v1/schedule/calendars/', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    async updateCalendar(id: number, data: { name?: string; slug?: string }): Promise<any> {
        return this.request(`/api/v1/schedule/calendars/${id}/`, {
            method: 'PATCH',
            body: JSON.stringify(data),
        });
    }

    async deleteCalendar(id: number): Promise<void> {
        await this.request(`/api/v1/schedule/calendars/${id}/`, {
            method: 'DELETE',
        });
    }

    async getEvent(id: number): Promise<any> {
        return this.request(`/api/v1/schedule/events/${id}/`);
    }

    async createEvent(data: {
        title: string;
        description?: string;
        start: string;
        end: string;
        calendar: number;
        color_event?: string;
        rule?: number | null;
    }): Promise<any> {
        return this.request('/api/v1/schedule/events/', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    async updateEvent(id: number, data: {
        title?: string;
        description?: string;
        start?: string;
        end?: string;
        calendar?: number;
        color_event?: string;
        rule?: number | null;
    }): Promise<any> {
        return this.request(`/api/v1/schedule/events/${id}/`, {
            method: 'PATCH',
            body: JSON.stringify(data),
        });
    }

    async deleteEvent(id: number): Promise<void> {
        await this.request(`/api/v1/schedule/events/${id}/`, {
            method: 'DELETE',
        });
    }

    // Calendar Participants (CalendarRelation)
    async getCalendarParticipants(calendarId: number): Promise<any> {
        return this.request(`/api/v1/schedule/calendars/${calendarId}/participants/`);
    }

    async addCalendarParticipant(calendarId: number, userId: number, distinction: string = 'viewer'): Promise<any> {
        return this.request(`/api/v1/schedule/calendars/${calendarId}/add-participant/`, {
            method: 'POST',
            body: JSON.stringify({ user_id: userId, distinction }),
        });
    }

    async removeCalendarParticipant(calendarId: number, userId: number): Promise<void> {
        await this.request(`/api/v1/schedule/calendars/${calendarId}/remove-participant/${userId}/`, {
            method: 'DELETE',
        });
    }

    // Calendar Export
    async exportCalendarToICS(calendarId: number): Promise<Blob> {
        const response = await fetch(`/api/v1/schedule/calendars/${calendarId}/export-ical/`, {
            method: 'GET',
            headers: {
                'Authorization': `Bearer ${this.getToken()}`,
            },
        });
        
        if (!response.ok) {
            throw new Error('Failed to export calendar');
        }
        
        return response.blob();
    }

    // Calendar Import
    async importCalendarFromICS(calendarId: number, file: File): Promise<any> {
        const formData = new FormData();
        formData.append('file', file);

        const response = await fetch(`/api/v1/schedule/calendars/${calendarId}/import-ical/`, {
            method: 'POST',
            headers: {
                'Authorization': `Bearer ${this.getToken()}`,
            },
            body: formData,
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Failed to import calendar');
        }
        
        return response.json();
    }

    // Recurring Events (Rules)
    async createRule(data: {
        name: string;
        description?: string;
        frequency: string;
        params?: any;
    }): Promise<any> {
        // Сериализуем params в JSON-строку для django-scheduler
        const payload = {
            ...data,
            params: data.params ? JSON.stringify(data.params) : '{}',
        };
        
        return this.request('/api/v1/schedule/rules/', {
            method: 'POST',
            body: JSON.stringify(payload),
        });
    }

    async updateRule(ruleId: number, data: {
        name: string;
        description?: string;
        frequency: string;
        params?: any;
    }): Promise<any> {
        // Сериализуем params в JSON-строку для django-scheduler
        const payload = {
            ...data,
            params: data.params ? JSON.stringify(data.params) : '{}',
        };
        
        return this.request(`/api/v1/schedule/rules/${ruleId}/`, {
            method: 'PUT',
            body: JSON.stringify(payload),
        });
    }

    async getRules(): Promise<any> {
        return this.request('/api/v1/schedule/rules/');
    }

    async getRule(ruleId: number): Promise<any> {
        return this.request(`/api/v1/schedule/rules/${ruleId}/`);
    }

    async getOccurrences(params: { start: string; end: string; calendar?: number }): Promise<any> {
        const queryParams = new URLSearchParams();
        queryParams.append('start', params.start);
        queryParams.append('end', params.end);
        if (params.calendar) queryParams.append('calendar', params.calendar.toString());

        return this.request(`/api/v1/schedule/events/occurrences/?${queryParams.toString()}`);
    }

    // Event Participants (EventRelation)
    async getEventParticipants(eventId: number): Promise<any> {
        return this.request(`/api/v1/schedule/relations/?event=${eventId}`);
    }

    async addEventParticipant(eventId: number, userId: number, distinction: string = 'attendee'): Promise<any> {
        return this.request('/api/v1/schedule/relations/', {
            method: 'POST',
            body: JSON.stringify({
                event: eventId,
                object_id: userId,
                distinction,
            }),
        });
    }

    async removeEventParticipant(relationId: number): Promise<any> {
        return this.request(`/api/v1/schedule/relations/${relationId}/`, {
            method: 'DELETE',
        });
    }

    // Посты - CRUD операции
    async createPost(data: { content: string; attachments?: File[] }): Promise<any> {
        const formData = new FormData();
        formData.append('content', data.content);
        if (data.attachments) {
            data.attachments.forEach((file) => {
                formData.append('attachments', file);
            });
        }

        const token = this.getToken();
        const headers: HeadersInit = {};
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch('/api/v1/posts/', {
            method: 'POST',
            headers,
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`API Error: ${response.status} ${response.statusText}`);
        }

        return response.json();
    }

    async updatePost(postId: number, data: { content: string; attachments?: File[] }): Promise<any> {
        const formData = new FormData();
        formData.append('content', data.content);
        if (data.attachments) {
            data.attachments.forEach((file) => {
                formData.append('attachments', file);
            });
        }

        const token = this.getToken();
        const headers: HeadersInit = {};
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(`/api/v1/posts/${postId}/`, {
            method: 'PATCH',
            headers,
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`API Error: ${response.status} ${response.statusText}`);
        }

        return response.json();
    }

    async deletePost(postId: number): Promise<void> {
        await this.request(`/api/v1/posts/${postId}/`, {
            method: 'DELETE',
        });
    }

    // Лайки
    async likePost(postId: number): Promise<any> {
        return this.request(`/api/v1/posts/${postId}/like/`, {
            method: 'POST',
        });
    }

    async unlikePost(postId: number): Promise<any> {
        return this.request(`/api/v1/posts/${postId}/unlike/`, {
            method: 'POST',
        });
    }

    async getPostLikers(postId: number): Promise<any> {
        return this.request(`/api/v1/posts/${postId}/likers/`);
    }

    // Комментарии
    async getComments(params: { post: number; page?: number }): Promise<any> {
        const queryParams = new URLSearchParams();
        queryParams.append('post', params.post.toString());
        if (params.page) queryParams.append('page', params.page.toString());

        const url = `/api/v1/comments/?${queryParams.toString()}`;
        return this.request(url);
    }

    async createComment(postId: number, text: string): Promise<any> {
        return this.request('/api/v1/comments/', {
            method: 'POST',
            body: JSON.stringify({ post: postId, text }),
        });
    }

    async updateComment(commentId: number, text: string): Promise<any> {
        return this.request(`/api/v1/comments/${commentId}/`, {
            method: 'PATCH',
            body: JSON.stringify({ text }),
        });
    }

    async deleteComment(commentId: number): Promise<void> {
        await this.request(`/api/v1/comments/${commentId}/`, {
            method: 'DELETE',
        });
    }

    // Управление заявками (approve/reject/cancel)
    async approveRequest(requestId: number): Promise<any> {
        return this.request(`/api/v1/requests/${requestId}/approve/`, {
            method: 'POST',
        });
    }

    async rejectRequest(requestId: number): Promise<any> {
        return this.request(`/api/v1/requests/${requestId}/reject/`, {
            method: 'POST',
        });
    }

    async cancelRequest(requestId: number): Promise<any> {
        return this.request(`/api/v1/requests/${requestId}/cancel/`, {
            method: 'POST',
        });
    }

    async addRequestComment(requestId: number, text: string): Promise<any> {
        return this.request(`/api/v1/requests/${requestId}/comments/`, {
            method: 'POST',
            body: JSON.stringify({ text }),
        });
    }

    // Профиль пользователя
    async updateCurrentUserProfile(data: any): Promise<any> {
        const formData = new FormData();

        Object.keys(data).forEach((key) => {
            if (data[key] instanceof File) {
                formData.append(key, data[key]);
            } else if (data[key] !== null && data[key] !== undefined) {
                formData.append(key, data[key]);
            }
        });

        const token = this.getToken();
        const headers: Record<string, string> = {};
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch('/api/v1/employees/me/', {
            method: 'PATCH',
            headers,
            body: formData,
        });

        if (!response.ok) {
            throw new Error(`API Error: ${response.status} ${response.statusText}`);
        }

        return response.json();
    }

    // Реакции на сообщения
    async reactToMessage(messageId: number, emoji: string): Promise<any> {
        return this.request(`/api/v1/communications/messages/${messageId}/react/`, {
            method: 'POST',
            body: JSON.stringify({ emoji }),
        });
    }

    async unreactToMessage(messageId: number, emoji: string): Promise<any> {
        return this.request(`/api/v1/communications/messages/${messageId}/unreact/`, {
            method: 'POST',
            body: JSON.stringify({ emoji }),
        });
    }
}

export const apiClient = new ApiClient();
export default apiClient;
