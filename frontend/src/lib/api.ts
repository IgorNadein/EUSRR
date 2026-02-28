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
    private isRefreshing = false;
    private refreshSubscribers: Array<(token: string) => void> = [];

    private getToken(): string | null {
        if (typeof window === 'undefined') return null;
        return localStorage.getItem(this.tokenKey);
    }

    private getRefreshToken(): string | null {
        if (typeof window === 'undefined') return null;
        return localStorage.getItem(this.refreshTokenKey);
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

    private onRefreshed(token: string): void {
        this.refreshSubscribers.forEach((callback) => callback(token));
        this.refreshSubscribers = [];
    }

    private addRefreshSubscriber(callback: (token: string) => void): void {
        this.refreshSubscribers.push(callback);
    }

    /**
     * Обновление access token с помощью refresh token
     */
    private async refreshAccessToken(): Promise<string> {
        const refreshToken = this.getRefreshToken();
        if (!refreshToken) {
            throw new Error('No refresh token available');
        }

        const response = await fetch('/api/auth/token/refresh/', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ refresh: refreshToken }),
        });

        if (!response.ok) {
            // Refresh token истёк или невалиден - нужно перелогиниться
            this.clearToken();
            throw new Error('Refresh token expired');
        }

        const data: LoginResponse = await response.json();
        this.setToken(data.access);
        
        // Если бэкенд вернул новый refresh token, сохраняем его
        if (data.refresh) {
            this.setRefreshToken(data.refresh);
        }

        return data.access;
    }

    private async request<T>(
        endpoint: string,
        options: RequestInit = {}
    ): Promise<T> {
        const headers: Record<string, string> = {
            ...(options.headers as Record<string, string>),
        };

        // Устанавливаем Content-Type только если это не FormData
        // Для FormData браузер сам установит правильный Content-Type с boundary
        if (!(options.body instanceof FormData) && !headers['Content-Type']) {
            headers['Content-Type'] = 'application/json';
        }

        // Автоматически добавляем токен если он есть
        const token = this.getToken();
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(endpoint, {
            ...options,
            headers,
        });

        // Если получили 401 и есть refresh token - пробуем обновить токен
        if (response.status === 401 && this.getRefreshToken()) {
            if (!this.isRefreshing) {
                this.isRefreshing = true;
                
                try {
                    const newToken = await this.refreshAccessToken();
                    this.isRefreshing = false;
                    this.onRefreshed(newToken);
                    
                    // Повторяем оригинальный запрос с новым токеном
                    headers['Authorization'] = `Bearer ${newToken}`;
                    const retryResponse = await fetch(endpoint, {
                        ...options,
                        headers,
                    });
                    
                    if (!retryResponse.ok) {
                        let errorDetails = '';
                        try {
                            const errorData = await retryResponse.json();
                            errorDetails = errorData.detail || JSON.stringify(errorData);
                        } catch {
                            errorDetails = retryResponse.statusText;
                        }
                        throw new Error(`API Error: ${retryResponse.status} ${errorDetails}`);
                    }
                    
                    // Обрабатываем успешный ответ
                    if (options.method === 'DELETE' && retryResponse.status === 204) {
                        return undefined as T;
                    }
                    
                    const contentLength = retryResponse.headers.get('content-length');
                    if (contentLength === '0' || retryResponse.status === 204) {
                        return undefined as T;
                    }
                    
                    return retryResponse.json();
                } catch (refreshError) {
                    this.isRefreshing = false;
                    this.refreshSubscribers = [];
                    throw refreshError;
                }
            } else {
                // Если уже идёт обновление токена, ждём его завершения
                return new Promise((resolve, reject) => {
                    this.addRefreshSubscriber((newToken: string) => {
                        headers['Authorization'] = `Bearer ${newToken}`;
                        fetch(endpoint, { ...options, headers })
                            .then((res) => {
                                if (!res.ok) {
                                    reject(new Error(`API Error: ${res.status}`));
                                    return;
                                }
                                if (options.method === 'DELETE' && res.status === 204) {
                                    resolve(undefined as T);
                                    return;
                                }
                                return res.json();
                            })
                            .then((data) => resolve(data))
                            .catch(reject);
                    });
                });
            }
        }

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

    // Глобальный поиск (django-watson)
    async search(query: string, limit?: number): Promise<any> {
        const queryParams = new URLSearchParams();
        queryParams.append('q', query);
        if (limit) queryParams.append('limit', limit.toString());

        const url = `/api/v1/search/?${queryParams.toString()}`;
        return this.request(url);
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
    async getDocuments(params?: { search?: string; type?: string; status?: string; page?: number; limit?: number; folder_id?: number }): Promise<any> {
        const queryParams = new URLSearchParams();
        if (params?.search) queryParams.append('search', params.search);
        if (params?.type) queryParams.append('type', params.type);
        if (params?.status) queryParams.append('status', params.status);
        if (params?.page) queryParams.append('page', params.page.toString());
        if (params?.limit) queryParams.append('limit', params.limit.toString());
        if (params?.folder_id !== undefined) queryParams.append('folder_id', params.folder_id.toString());

        const url = `/api/v1/documents/${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
        return this.request(url);
    }

    async getDocument(id: number): Promise<any> {
        return this.request(`/api/v1/documents/${id}/`);
    }

    async createDocument(data: { 
        title: string; 
        description?: string; 
        file: File | Blob;
        extracted_text?: string;
        sent_to_all?: boolean;
        recipient_ids?: number[];
        department_ids?: number[];
        folder_id?: number | null;
    }): Promise<any> {
        const formData = new FormData();
        formData.append('title', data.title);
        if (data.description) formData.append('description', data.description);
        if (data.extracted_text) formData.append('extracted_text', data.extracted_text);
        if (data.folder_id) formData.append('folder', String(data.folder_id));
        
        // Добавляем sent_to_all (по умолчанию true)
        formData.append('sent_to_all', String(data.sent_to_all ?? true));
        
        // Добавляем получателей, если указаны
        if (data.recipient_ids && data.recipient_ids.length > 0) {
            data.recipient_ids.forEach(id => {
                formData.append('recipient_ids', String(id));
            });
        }
        
        // Добавляем отделы, если указаны
        if (data.department_ids && data.department_ids.length > 0) {
            data.department_ids.forEach(id => {
                formData.append('department_ids', String(id));
            });
        }
        
        formData.append('file', data.file);

        return this.request('/api/v1/documents/', {
            method: 'POST',
            body: formData,
        });
    }

    async updateDocument(id: number, data: { 
        title?: string; 
        description?: string; 
        file?: File;
    }): Promise<any> {
        const formData = new FormData();
        if (data.title) formData.append('title', data.title);
        if (data.description) formData.append('description', data.description);
        if (data.file) formData.append('file', data.file);

        return this.request(`/api/v1/documents/${id}/`, {
            method: 'PATCH',
            body: formData,
        });
    }

    async deleteDocument(id: number): Promise<void> {
        return this.request(`/api/v1/documents/${id}/`, {
            method: 'DELETE',
        });
    }

    // FSM Workflow transitions
    async submitDocumentForReview(id: number): Promise<any> {
        return this.request(`/api/v1/documents/${id}/submit-for-review/`, {
            method: 'POST',
        });
    }

    async approveDocument(id: number): Promise<any> {
        return this.request(`/api/v1/documents/${id}/approve/`, {
            method: 'POST',
        });
    }

    async rejectDocument(id: number): Promise<any> {
        return this.request(`/api/v1/documents/${id}/reject/`, {
            method: 'POST',
        });
    }

    async publishDocument(id: number): Promise<any> {
        return this.request(`/api/v1/documents/${id}/publish/`, {
            method: 'POST',
        });
    }

    async returnDocumentToDraft(id: number): Promise<any> {
        return this.request(`/api/v1/documents/${id}/return-to-draft/`, {
            method: 'POST',
        });
    }

    async archiveDocument(id: number): Promise<any> {
        return this.request(`/api/v1/documents/${id}/archive/`, {
            method: 'POST',
        });
    }

    async unarchiveDocument(id: number): Promise<any> {
        return this.request(`/api/v1/documents/${id}/unarchive/`, {
            method: 'POST',
        });
    }

    // Document acknowledgement
    async acknowledgeDocument(id: number, notes?: string): Promise<any> {
        return this.request(`/api/v1/documents/${id}/acknowledge/`, {
            method: 'POST',
            body: JSON.stringify({ notes }),
        });
    }

    // Получить ведомость ознакомлений с документом (для начальника/автора)
    async getDocumentAcknowledgements(id: number, search?: string): Promise<any> {
        const queryParams = new URLSearchParams();
        if (search) queryParams.append('search', search);
        
        const url = `/api/v1/documents/${id}/acknowledgements/${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
        return this.request(url);
    }

    // Папки документов
    async getFolders(params?: { parent_id?: number; root?: boolean }): Promise<any> {
        const queryParams = new URLSearchParams();
        if (params?.parent_id !== undefined) queryParams.append('parent_id', params.parent_id.toString());
        if (params?.root) queryParams.append('root', 'true');

        const url = `/api/v1/folders/${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
        return this.request(url);
    }

    async getFolder(id: number): Promise<any> {
        return this.request(`/api/v1/folders/${id}/`);
    }

    async createFolder(data: { name: string; parent?: number | null }): Promise<any> {
        return this.request('/api/v1/folders/', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    async updateFolder(id: number, data: { name?: string; parent?: number | null }): Promise<any> {
        return this.request(`/api/v1/folders/${id}/`, {
            method: 'PATCH',
            body: JSON.stringify(data),
        });
    }

    async deleteFolder(id: number): Promise<void> {
        return this.request(`/api/v1/folders/${id}/`, {
            method: 'DELETE',
        });
    }

    async getFolderChildren(id: number): Promise<any> {
        return this.request(`/api/v1/folders/${id}/children/`);
    }

    async getFolderDocuments(id: number): Promise<any> {
        return this.request(`/api/v1/folders/${id}/documents/`);
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

    // Чаты (основные методы чатов ниже в файле)
    async getChatMessagesAround(chatId: number | string, params?: { limit?: number; around_id?: number }): Promise<any> {
        const queryParams = new URLSearchParams();
        if (params?.limit) queryParams.append('limit', params.limit.toString());
        if (params?.around_id) queryParams.append('around_id', params.around_id.toString());

        const url = `/api/v1/communications/chats/${chatId}/messages-around/${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
        return this.request(url);
    }

    async sendMessage(chatId: number | string, text: string, replyTo?: number): Promise<any> {
        const formData = new FormData();
        formData.append('content', text);
        formData.append('chat_id', chatId.toString());
        if (replyTo) {
            formData.append('reply_to', replyTo.toString());
        }

        const token = this.getToken();
        const headers: Record<string, string> = {};
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(`/api/v1/communications/messages/upload/`, {
            method: 'POST',
            headers,
            body: formData,
        });

        if (!response.ok) {
            let errorDetails = '';
            try {
                const errorData = await response.json();
                errorDetails = errorData.detail || JSON.stringify(errorData);
            } catch {
                errorDetails = response.statusText;
            }
            throw new Error(`API Error: ${response.status} ${errorDetails}`);
        }

        const result = await response.json();
        return result.message || result;
    }

    async sendMessageWithFiles(chatId: number | string, text: string, files: File[], replyTo?: number): Promise<any> {
        const formData = new FormData();
        formData.append('content', text);
        formData.append('chat_id', chatId.toString());
        if (replyTo) {
            formData.append('reply_to', replyTo.toString());
        }
        files.forEach((file, index) => {
            formData.append(`file_${index}`, file);
        });

        const token = this.getToken();
        const headers: Record<string, string> = {};
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(`/api/v1/communications/messages/upload/`, {
            method: 'POST',
            headers,
            body: formData,
        });

        if (!response.ok) {
            let errorDetails = '';
            try {
                const errorData = await response.json();
                errorDetails = errorData.detail || JSON.stringify(errorData);
            } catch {
                errorDetails = response.statusText;
            }
            throw new Error(`API Error: ${response.status} ${errorDetails}`);
        }

        const result = await response.json();
        return result.message || result;
    }

    async updateMessage(messageId: number, text: string): Promise<any> {
        return this.request(`/api/v1/communications/messages/${messageId}/`, {
            method: 'PATCH',
            body: JSON.stringify({ content: text }),
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

    // Web Push подписки
    async getVapidPublicKey(): Promise<{ vapid_public_key: string }> {
        return this.request('/api/v1/notifications/push/vapid-key/');
    }

    async subscribePush(data: {
        endpoint: string;
        keys: { p256dh: string; auth: string };
        device_name?: string;
    }): Promise<{ status: string; message: string; created: boolean }> {
        return this.request('/api/v1/notifications/push/subscribe/', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    async unsubscribePush(endpoint?: string): Promise<{ status: string; message: string }> {
        return this.request('/api/v1/notifications/push/unsubscribe/', {
            method: 'DELETE',
            body: JSON.stringify({ endpoint }),
        });
    }

    async getPushSubscriptions(): Promise<{ subscriptions: any[] }> {
        return this.request('/api/v1/notifications/push/subscriptions/');
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

    // ============= Communications (Chats & Messages) API =============

    /**
     * Получить список чатов пользователя
     */
    async getChats(params?: { search?: string; page?: number }): Promise<any> {
        const queryParams = new URLSearchParams();
        if (params?.search) queryParams.append('search', params.search);
        if (params?.page) queryParams.append('page', params.page.toString());
        
        const query = queryParams.toString();
        return this.request(`/api/v1/communications/chats/${query ? '?' + query : ''}`);
    }

    /**
     * Получить детали чата по ID
     */
    async getChat(chatId: number): Promise<any> {
        return this.request(`/api/v1/communications/chats/${chatId}/`);
    }

    /**
     * Создать новый чат
     * type: 'private' | 'group' | 'department' | 'general'
     */
    async createChat(data: { 
        type: string; 
        participants?: number[]; 
        name?: string; 
        description?: string;
        department?: number;
        include_all_employees?: boolean;
    }): Promise<any> {
        return this.request('/api/v1/communications/chats/', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    /**
     * Получить сообщения чата с пагинацией
     */
    async getChatMessages(
        chatId: number, 
        params?: { 
            limit?: number; 
            before_id?: number; 
            after_id?: number;
            before?: string;
            after?: string;
        }
    ): Promise<any> {
        const queryParams = new URLSearchParams();
        if (params?.limit) queryParams.append('limit', params.limit.toString());
        if (params?.before_id) queryParams.append('before_id', params.before_id.toString());
        if (params?.after_id) queryParams.append('after_id', params.after_id.toString());
        if (params?.before) queryParams.append('before', params.before);
        if (params?.after) queryParams.append('after', params.after);
        
        const query = queryParams.toString();
        return this.request(`/api/v1/communications/chats/${chatId}/messages/${query ? '?' + query : ''}`);
    }

    /**
     * Пометить чат как прочитанный
     */
    async markChatAsRead(chatId: number, lastReadMessageId?: number): Promise<any> {
        return this.request(`/api/v1/communications/chats/${chatId}/mark-read/`, {
            method: 'POST',
            body: JSON.stringify({ 
                message_id: lastReadMessageId 
            }),
        });
    }

    /**
     * Закрепить/открепить чат
     */
    async togglePinChat(chatId: number): Promise<any> {
        return this.request(`/api/v1/communications/chats/${chatId}/pin/`, {
            method: 'POST',
        });
    }

    /**
     * Включить/выключить уведомления для чата
     */
    async toggleChatNotifications(chatId: number): Promise<any> {
        return this.request(`/api/v1/communications/chats/${chatId}/notifications/`, {
            method: 'POST',
        });
    }
}

export const apiClient = new ApiClient();
export default apiClient;
