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
        acknowledgement_required?: boolean;
        tag_ids?: number[];
    }): Promise<any> {
        const formData = new FormData();
        formData.append('title', data.title);
        if (data.description) formData.append('description', data.description);
        if (data.extracted_text) formData.append('extracted_text', data.extracted_text);
        if (data.folder_id) formData.append('folder', String(data.folder_id));
        
        // Добавляем sent_to_all (по умолчанию true)
        formData.append('sent_to_all', String(data.sent_to_all ?? true));
        
        // Добавляем acknowledgement_required
        if (data.acknowledgement_required !== undefined) {
            formData.append('acknowledgement_required', String(data.acknowledgement_required));
        }
        
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
        
        // Добавляем теги, если указаны
        if (data.tag_ids && data.tag_ids.length > 0) {
            data.tag_ids.forEach(id => {
                formData.append('tag_ids', String(id));
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
        tag_ids?: number[];
        folder?: number | null;
    }): Promise<any> {
        const formData = new FormData();
        if (data.title !== undefined) formData.append('title', data.title);
        if (data.description !== undefined) formData.append('description', data.description);
        if (data.file) formData.append('file', data.file);
        
        // Добавляем папку (может быть null)
        if (data.folder !== undefined) {
            if (data.folder === null) {
                formData.append('folder', '');
            } else {
                formData.append('folder', String(data.folder));
            }
        }
        
        // Добавляем теги
        if (data.tag_ids !== undefined) {
            data.tag_ids.forEach(tagId => {
                formData.append('tag_ids', String(tagId));
            });
        }

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

    // Document acknowledgement
    async acknowledgeDocument(id: number): Promise<any> {
        return this.request(`/api/v1/documents/${id}/acknowledge/`, {
            method: 'POST',
            body: JSON.stringify({}),
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

    // Document Comments
    async getDocumentComments(documentId: number): Promise<any> {
        return this.request(`/api/v1/document-comments/?document=${documentId}`);
    }

    async createDocumentComment(data: { document: number; text: string; parent?: number }): Promise<any> {
        return this.request('/api/v1/document-comments/', {
            method: 'POST',
            body: JSON.stringify({
                document_id: data.document,
                text: data.text,
                parent_id: data.parent,
            }),
        });
    }

    async updateDocumentComment(id: number, text: string): Promise<any> {
        return this.request(`/api/v1/document-comments/${id}/`, {
            method: 'PATCH',
            body: JSON.stringify({ text }),
        });
    }

    async deleteDocumentComment(id: number): Promise<void> {
        return this.request(`/api/v1/document-comments/${id}/`, {
            method: 'DELETE',
        });
    }

    async getCommentReplies(commentId: number): Promise<any> {
        return this.request(`/api/v1/document-comments/${commentId}/replies/`);
    }

    // Document Tags
    async getDocumentTags(): Promise<any> {
        return this.request('/api/v1/document-tags/');
    }

    async getDocumentTag(id: number): Promise<any> {
        return this.request(`/api/v1/document-tags/${id}/`);
    }

    async createDocumentTag(data: { name: string; color?: string }): Promise<any> {
        return this.request('/api/v1/document-tags/', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    }

    async updateDocumentTag(id: number, data: { name?: string; color?: string }): Promise<any> {
        return this.request(`/api/v1/document-tags/${id}/`, {
            method: 'PATCH',
            body: JSON.stringify(data),
        });
    }

    async deleteDocumentTag(id: number): Promise<void> {
        return this.request(`/api/v1/document-tags/${id}/`, {
            method: 'DELETE',
        });
    }

    async getDocumentsByTag(tagId: number): Promise<any> {
        return this.request(`/api/v1/document-tags/${tagId}/documents/`);
    }

    // Related Documents
    async getRelatedDocuments(id: number): Promise<any> {
        return this.request(`/api/v1/documents/${id}/related/`);
    }

    async addRelatedDocument(id: number, relatedId: number): Promise<any> {
        return this.request(`/api/v1/documents/${id}/add_related/`, {
            method: 'POST',
            body: JSON.stringify({ related_document_id: relatedId }),
        });
    }

    async removeRelatedDocument(id: number, relatedId: number): Promise<any> {
        return this.request(`/api/v1/documents/${id}/remove_related/`, {
            method: 'DELETE',
            body: JSON.stringify({ related_document_id: relatedId }),
        });
    }

    // Document Thumbnails
    getDocumentThumbnail(id: number, size?: 'small' | 'medium' | 'large' | 'original'): string {
        const sizeParam = size ? `?size=${size}` : '';
        return `/api/v1/documents/${id}/thumbnail/${sizeParam}`;
    }

    // Заявки
    async getRequests(params?: { 
        status?: string; 
        type?: string; 
        search?: string; 
        page?: number; 
        limit?: number;
        view?: string;
        addressed_to_me?: string;
        employee_id?: string | number;
        date_from?: string;
        date_to?: string;
        [key: string]: any;
    }): Promise<any> {
        const queryParams = new URLSearchParams();
        if (params?.status) queryParams.append('status', params.status);
        if (params?.type) queryParams.append('type', params.type);
        if (params?.search) queryParams.append('search', params.search);
        if (params?.page) queryParams.append('page', params.page.toString());
        if (params?.limit) queryParams.append('limit', params.limit.toString());
        if (params?.view) queryParams.append('view', params.view);
        if (params?.addressed_to_me) queryParams.append('addressed_to_me', params.addressed_to_me);
        if (params?.employee_id) queryParams.append('employee_id', params.employee_id.toString());
        if (params?.date_from) queryParams.append('date_from', params.date_from);
        if (params?.date_to) queryParams.append('date_to', params.date_to);

        const url = `/api/v1/requests/${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
        return this.request(url);
    }

    async createRequest(data: any, saveAs?: 'draft' | 'submitted'): Promise<any> {
        const formData = new FormData();

        Object.keys(data).forEach((key) => {
            if (key === 'attachments' && Array.isArray(data[key])) {
                data[key].forEach((file: File) => {
                    formData.append('attachments', file);
                });
            } else if (key === 'attachment' && data[key] instanceof File) {
                formData.append('attachment', data[key]);
            } else if (Array.isArray(data[key])) {
                data[key].forEach((val: any) => {
                    formData.append(key, String(val));
                });
            } else if (data[key] !== null && data[key] !== undefined) {
                formData.append(key, String(data[key]));
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
            let detail = `${response.status} ${response.statusText}`;
            try {
                const body = await response.json();
                detail = JSON.stringify(body);
            } catch {}
            throw new Error(detail);
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
            } else if (key === 'attachment' && data[key] instanceof File) {
                formData.append('attachment', data[key]);
            } else if (Array.isArray(data[key])) {
                data[key].forEach((val: any) => {
                    formData.append(key, String(val));
                });
            } else if (data[key] !== null && data[key] !== undefined) {
                formData.append(key, String(data[key]));
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
            let detail = `${response.status} ${response.statusText}`;
            try {
                const body = await response.json();
                detail = JSON.stringify(body);
            } catch {}
            throw new Error(detail);
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
    async getNotifications(params?: { page?: number; page_size?: number; unread_only?: boolean }): Promise<any> {
        const queryParams = new URLSearchParams();
        if (params?.page) queryParams.append('page', String(params.page));
        if (params?.page_size) queryParams.append('page_size', String(params.page_size));
        if (params?.unread_only) queryParams.append('unread_only', 'true');
        
        const url = queryParams.toString() 
            ? `/api/v1/notifications/?${queryParams.toString()}`
            : '/api/v1/notifications/';
        return this.request(url);
    }

    async getUnreadNotificationsCount(): Promise<{ count: number }> {
        return this.request('/api/v1/notifications/count/');
    }

    async markNotificationAsRead(id: number): Promise<void> {
        await this.request(`/api/v1/notifications/${id}/read/`, {
            method: 'POST',
        });
    }

    async markAllNotificationsAsRead(): Promise<void> {
        await this.request('/api/v1/notifications/read-all/', {
            method: 'POST',
        });
    }

    async markCategoryAsRead(category: string): Promise<{ status: string; count: number }> {
        // Получаем список verb'ов для категории
        const { getVerbsByCategory } = await import('./verbTranslations');
        const verbs = getVerbsByCategory(category);
        
        return this.request('/api/v1/notifications/category/read/', {
            method: 'POST',
            body: JSON.stringify({ verbs, category }),
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

    // Дополнительные методы уведомлений
    async deleteNotification(id: number): Promise<void> {
        await this.request(`/api/v1/notifications/${id}/`, {
            method: 'DELETE',
        });
    }

    async deleteAllReadNotifications(): Promise<{ status: string; count: number }> {
        return this.request('/api/v1/notifications/delete-all-read/', {
            method: 'DELETE',
        });
    }

    async getNotificationPreferences(): Promise<any> {
        return this.request('/api/v1/notifications/preferences/');
    }

    async updateNotificationPreferences(data: {
        web_enabled?: boolean;
        email_enabled?: boolean;
        email_frequency?: 'instant' | 'daily' | 'weekly' | 'disabled';
        push_enabled?: boolean;
        dnd_enabled?: boolean;
        dnd_start_time?: string;
        dnd_end_time?: string;
        disabled_verbs?: string[];
    }): Promise<any> {
        return this.request('/api/v1/notifications/preferences/', {
            method: 'PUT',
            body: JSON.stringify(data),
        });
    }

    async getVerbTypes(): Promise<{ verb_types: any[] }> {
        return this.request('/api/v1/notifications/verb-types/');
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

    async getCalendarSubscriptions(): Promise<any> {
        return this.request('/api/v1/schedule/subscriptions/');
    }

    async subscribeToCalendar(calendarId: number): Promise<any> {
        return this.request('/api/v1/schedule/subscriptions/', {
            method: 'POST',
            body: JSON.stringify({ calendar: calendarId }),
        });
    }

    async unsubscribeFromCalendar(subscriptionId: number): Promise<any> {
        return this.request(`/api/v1/schedule/subscriptions/${subscriptionId}/`, {
            method: 'DELETE',
        });
    }

    async updateSubscription(subscriptionId: number, data: any): Promise<any> {
        return this.request(`/api/v1/schedule/subscriptions/${subscriptionId}/`, {
            method: 'PATCH',
            body: JSON.stringify(data),
        });
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
    async createPost(data: { 
        type?: 'company' | 'department' | 'employee'; 
        title?: string;
        body?: string;
        content?: string;
        department?: number;
        image?: File;
        attachment?: File;
        attachments?: File[];
    }): Promise<any> {
        const formData = new FormData();
        
        // API требует title и body как отдельные поля
        if (data.title) formData.append('title', data.title);
        if (data.body) formData.append('body', data.body);
        if (data.content) formData.append('content', data.content);
        
        // Опциональные поля
        if (data.type) formData.append('type', data.type);
        if (data.department) formData.append('department', String(data.department));
        if (data.image) formData.append('image', data.image);
        if (data.attachment) formData.append('attachment', data.attachment);
        
        // Вложения (attachments)
        if (data.attachments) {
            data.attachments.forEach((file: File) => {
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
            const errorText = await response.text();
            console.error('API Error Response:', errorText);
            throw new Error(`API Error: ${response.status} ${response.statusText}`);
        }

        return response.json();
    }

    async updatePost(postId: number, data: { 
        type?: 'company' | 'department' | 'employee';
        title?: string;
        body?: string;
        content?: string;
        department?: number;
        image?: File;
        attachment?: File;
        attachments?: File[];
    }): Promise<any> {
        const formData = new FormData();
        
        // API требует title и body как отдельные поля
        if (data.title) formData.append('title', data.title);
        if (data.body) formData.append('body', data.body);
        if (data.content) formData.append('content', data.content);
        
        // Опциональные поля
        if (data.type) formData.append('type', data.type);
        if (data.department !== undefined) formData.append('department', String(data.department));
        if (data.image) formData.append('image', data.image);
        if (data.attachment) formData.append('attachment', data.attachment);
        
        // Вложения (attachments)
        if (data.attachments) {
            data.attachments.forEach((file: File) => {
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
            const errorText = await response.text();
            console.error('API Error Response:', errorText);
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
        if (params.page) queryParams.append('page', params.page.toString());

        const url = `/api/v1/posts/${params.post}/comments/${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
        return this.request(url);
    }

    async createComment(postId: number, text: string, image?: File, attachment?: File): Promise<any> {
        if (image || attachment) {
            const formData = new FormData();
            formData.append('text', text);
            if (image) formData.append('image', image);
            if (attachment) formData.append('attachment', attachment);

            const token = this.getToken();
            const headers: HeadersInit = {};
            if (token) {
                headers['Authorization'] = `Bearer ${token}`;
            }

            const response = await fetch(`/api/v1/posts/${postId}/comments/`, {
                method: 'POST',
                headers,
                body: formData,
            });

            if (!response.ok) {
                const errorText = await response.text();
                console.error('API Error Response:', errorText);
                throw new Error(`API Error: ${response.status} ${response.statusText}`);
            }

            return response.json();
        }

        return this.request(`/api/v1/posts/${postId}/comments/`, {
            method: 'POST',
            body: JSON.stringify({ text }),
        });
    }

    async updateComment(commentId: number, text: string): Promise<any> {
        const response = await this.request<any>(`/api/v1/communications/messages/${commentId}/`, {
            method: 'PATCH',
            body: JSON.stringify({ content: text }),
        });
        
        // Конвертируем content -> text для совместимости
        return {
            ...response,
            text: response.content || text,
        };
    }

    async deleteComment(commentId: number): Promise<void> {
        await this.request(`/api/v1/communications/messages/${commentId}/`, {
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
        avatar?: File;
    }): Promise<any> {
        // Если есть файл, используем FormData
        if (data.avatar) {
            const formData = new FormData();
            formData.append('type', data.type);
            if (data.name) formData.append('name', data.name);
            if (data.description) formData.append('description', data.description);
            if (data.avatar) formData.append('avatar', data.avatar);
            if (data.participants) {
                data.participants.forEach(id => formData.append('participants', id.toString()));
            }
            if (data.department) formData.append('department', data.department.toString());
            if (data.include_all_employees !== undefined) {
                formData.append('include_all_employees', data.include_all_employees.toString());
            }
            
            return this.request('/api/v1/communications/chats/', {
                method: 'POST',
                body: formData,
            });
        }
        
        // Без файла - обычный JSON
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

    /**
     * Покинуть чат (для групповых чатов)
     */
    async leaveChat(chatId: number): Promise<any> {
        return this.request(`/api/v1/communications/chats/${chatId}/leave/`, {
            method: 'POST',
        });
    }

    /**
     * Удалить чат (требует прав администратора чата)
     */
    async deleteChat(chatId: number): Promise<any> {
        return this.request(`/api/v1/communications/chats/${chatId}/`, {
            method: 'DELETE',
        });
    }

    /**
     * Обновить информацию о чате (частичное обновление)
     */
    async updateChat(chatId: number, data: Partial<{
        name: string;
        description: string;
        type: string;
        can_reply: boolean;
        include_all_users: boolean;
        flags: Record<string, any>;
        extra_data: Record<string, any>;
    }>): Promise<any> {
        return this.request(`/api/v1/communications/chats/${chatId}/`, {
            method: 'PATCH',
            body: JSON.stringify(data),
        });
    }

    /**
     * Загрузить аватар чата
     */
    async uploadChatAvatar(chatId: number, file: File): Promise<any> {
        const formData = new FormData();
        formData.append('avatar', file);
        
        return this.request(`/api/v1/communications/chats/${chatId}/`, {
            method: 'PATCH',
            body: formData,
        });
    }

    /**
     * Добавить участника в чат
     */
    async addChatMember(chatId: number, userId: number): Promise<any> {
        return this.request(`/api/v1/communications/chats/${chatId}/add-member/`, {
            method: 'POST',
            body: JSON.stringify({ user_id: userId }),
        });
    }

    /**
     * Удалить участника из чата
     */
    async removeChatMember(chatId: number, userId: number): Promise<any> {
        return this.request(`/api/v1/communications/chats/${chatId}/remove-member/`, {
            method: 'POST',
            body: JSON.stringify({ user_id: userId }),
        });
    }

    /**
     * Изменить роль участника в чате
     */
    async changeChatMemberRole(chatId: number, userId: number, role: 'admin' | 'moderator' | 'member' | 'guest'): Promise<any> {
        return this.request(`/api/v1/communications/chats/${chatId}/change-role/`, {
            method: 'POST',
            body: JSON.stringify({ user_id: userId, role }),
        });
    }

    /**
     * Обновить пользовательские настройки чата
     */
    async updateChatUserSettings(chatId: number, data: Partial<{
        custom_name: string;
        is_hidden: boolean;
    }>): Promise<any> {
        // Примечание: может потребоваться отдельный endpoint на backend
        // Сейчас используем PATCH чата, но лучше создать /api/v1/communications/chats/{id}/user-settings/
        return this.request(`/api/v1/communications/chats/${chatId}/user-settings/`, {
            method: 'PATCH',
            body: JSON.stringify(data),
        });
    }

    // ==================== Оборудование ====================

    async getEquipmentCategories(params?: Record<string, string | number>): Promise<any> {
        const queryParams = new URLSearchParams();
        if (params) {
            Object.entries(params).forEach(([key, value]) => {
                if (value !== undefined && value !== null && value !== '') {
                    queryParams.append(key, String(value));
                }
            });
        }
        const url = `/api/v1/procurement/equipment-categories/${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
        return this.request(url);
    }

    async getEquipment(params?: Record<string, string | number>): Promise<any> {
        const queryParams = new URLSearchParams();
        if (params) {
            Object.entries(params).forEach(([key, value]) => {
                if (value !== undefined && value !== null && value !== '') {
                    queryParams.append(key, String(value));
                }
            });
        }
        const url = `/api/v1/procurement/equipment/${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
        return this.request(url);
    }

    async createEquipment(data: any): Promise<any> {
        const formData = new FormData();

        Object.keys(data).forEach((key) => {
            if (key === 'attachment' && data[key] instanceof File) {
                formData.append('attachment', data[key]);
            } else if (Array.isArray(data[key])) {
                data[key].forEach((val: any) => {
                    formData.append(key, String(val));
                });
            } else if (data[key] !== null && data[key] !== undefined) {
                formData.append(key, String(data[key]));
            }
        });

        const token = this.getToken();
        const headers: Record<string, string> = {};
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch('/api/v1/procurement/equipment/', {
            method: 'POST',
            headers,
            body: formData,
        });

        if (!response.ok) {
            let detail = `${response.status} ${response.statusText}`;
            try {
                const body = await response.json();
                detail = JSON.stringify(body);
            } catch {}
            throw new Error(detail);
        }

        return response.json();
    }

    async updateEquipment(equipmentId: number, data: any): Promise<any> {
        const formData = new FormData();

        Object.keys(data).forEach((key) => {
            if (key === 'attachment' && data[key] instanceof File) {
                formData.append('attachment', data[key]);
            } else if (Array.isArray(data[key])) {
                data[key].forEach((val: any) => {
                    formData.append(key, String(val));
                });
            } else if (data[key] !== null && data[key] !== undefined) {
                formData.append(key, String(data[key]));
            }
        });

        const token = this.getToken();
        const headers: Record<string, string> = {};
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(`/api/v1/procurement/equipment/${equipmentId}/`, {
            method: 'PATCH',
            headers,
            body: formData,
        });

        if (!response.ok) {
            let detail = `${response.status} ${response.statusText}`;
            try {
                const body = await response.json();
                detail = JSON.stringify(body);
            } catch {}
            throw new Error(detail);
        }

        return response.json();
    }

    async deleteEquipment(equipmentId: number): Promise<void> {
        await this.request(`/api/v1/procurement/equipment/${equipmentId}/`, {
            method: 'DELETE',
        });
    }

    async approveEquipment(equipmentId: number): Promise<any> {
        return this.request(`/api/v1/procurement/equipment/${equipmentId}/approve/`, {
            method: 'POST',
        });
    }

    async rejectEquipment(equipmentId: number): Promise<any> {
        return this.request(`/api/v1/procurement/equipment/${equipmentId}/reject/`, {
            method: 'POST',
        });
    }

    async cancelEquipment(equipmentId: number): Promise<any> {
        return this.request(`/api/v1/procurement/equipment/${equipmentId}/cancel/`, {
            method: 'POST',
        });
    }

    async getEquipmentComments(equipmentId: number): Promise<any> {
        return this.request(`/api/v1/procurement/equipment/${equipmentId}/comments/`);
    }

    async addEquipmentComment(equipmentId: number, text: string): Promise<any> {
        return this.request(`/api/v1/procurement/equipment/${equipmentId}/comments/`, {
            method: 'POST',
            body: JSON.stringify({ text }),
        });
    }

    async deleteEquipmentComment(equipmentId: number, commentId: number): Promise<void> {
        await this.request(`/api/v1/procurement/equipment/${equipmentId}/comments/${commentId}/`, {
            method: 'DELETE',
        });
    }

    // ==================== Закупки (Procurement Requests) ====================

    async getProcurementRequests(params?: Record<string, string | number>): Promise<any> {
        const queryParams = new URLSearchParams();
        if (params) {
            Object.entries(params).forEach(([key, value]) => {
                if (value !== undefined && value !== null && value !== '') {
                    queryParams.append(key, String(value));
                }
            });
        }
        const url = `/api/v1/procurement/requests/${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
        return this.request(url);
    }

    async getProcurementRequest(id: number): Promise<any> {
        return this.request(`/api/v1/procurement/requests/${id}/`);
    }

    async createProcurementRequest(data: any): Promise<any> {
        return this.request('/api/v1/procurement/requests/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
    }

    async updateProcurementRequest(id: number, data: any): Promise<any> {
        return this.request(`/api/v1/procurement/requests/${id}/`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
    }

    async deleteProcurementRequest(id: number): Promise<void> {
        await this.request(`/api/v1/procurement/requests/${id}/`, {
            method: 'DELETE',
        });
    }

    async submitProcurementRequest(id: number): Promise<any> {
        return this.request(`/api/v1/procurement/requests/${id}/submit/`, {
            method: 'POST',
        });
    }

    async approveProcurementRequest(id: number, comment?: string): Promise<any> {
        return this.request(`/api/v1/procurement/requests/${id}/approve/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ comment: comment || '' }),
        });
    }

    async rejectProcurementRequest(id: number, comment?: string): Promise<any> {
        return this.request(`/api/v1/procurement/requests/${id}/reject/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ comment: comment || '' }),
        });
    }

    async startWorkProcurementRequest(id: number): Promise<any> {
        return this.request(`/api/v1/procurement/requests/${id}/start_work/`, {
            method: 'POST',
        });
    }

    async completeProcurementRequest(id: number): Promise<any> {
        return this.request(`/api/v1/procurement/requests/${id}/complete/`, {
            method: 'POST',
        });
    }

    async cancelProcurementRequest(id: number, reason?: string): Promise<any> {
        return this.request(`/api/v1/procurement/requests/${id}/cancel/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ reason: reason || '' }),
        });
    }

    async getMyProcurementRequests(params?: Record<string, string | number>): Promise<any> {
        const queryParams = new URLSearchParams();
        if (params) {
            Object.entries(params).forEach(([key, value]) => {
                if (value !== undefined && value !== null && value !== '') {
                    queryParams.append(key, String(value));
                }
            });
        }
        const url = `/api/v1/procurement/requests/my_requests/${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
        return this.request(url);
    }

    async getPendingApprovals(params?: Record<string, string | number>): Promise<any> {
        const queryParams = new URLSearchParams();
        if (params) {
            Object.entries(params).forEach(([key, value]) => {
                if (value !== undefined && value !== null && value !== '') {
                    queryParams.append(key, String(value));
                }
            });
        }
        const url = `/api/v1/procurement/requests/pending_approvals/${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
        return this.request(url);
    }

    // ==================== Позиции закупок (Procurement Items) ====================

    async getProcurementItems(params?: Record<string, string | number>): Promise<any> {
        const queryParams = new URLSearchParams();
        if (params) {
            Object.entries(params).forEach(([key, value]) => {
                if (value !== undefined && value !== null && value !== '') {
                    queryParams.append(key, String(value));
                }
            });
        }
        const url = `/api/v1/procurement/items/${queryParams.toString() ? '?' + queryParams.toString() : ''}`;
        return this.request(url);
    }

    async createProcurementItem(data: any): Promise<any> {
        return this.request('/api/v1/procurement/items/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
    }

    async updateProcurementItem(id: number, data: any): Promise<any> {
        return this.request(`/api/v1/procurement/items/${id}/`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
    }

    async deleteProcurementItem(id: number): Promise<void> {
        await this.request(`/api/v1/procurement/items/${id}/`, {
            method: 'DELETE',
        });
    }
}

export const apiClient = new ApiClient();
export default apiClient;
