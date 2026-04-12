/**
 * Base API Client — token management, auth, HTTP request logic.
 * Domain-specific methods live in separate modules.
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

export class ApiClientBase {
    private tokenKey = 'access_token';
    private refreshTokenKey = 'refresh_token';
    private isRefreshing = false;
    private refreshSubscribers: Array<(token: string) => void> = [];

    getToken(): string | null {
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

    private async refreshAccessToken(): Promise<string> {
        const refreshToken = this.getRefreshToken();
        if (!refreshToken) {
            throw new Error('No refresh token available');
        }

        const response = await fetch('/api/auth/token/refresh/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ refresh: refreshToken }),
        });

        if (!response.ok) {
            this.clearToken();
            throw new Error('Refresh token expired');
        }

        const data: LoginResponse = await response.json();
        this.setToken(data.access);
        if (data.refresh) {
            this.setRefreshToken(data.refresh);
        }
        return data.access;
    }

    async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
        const headers: Record<string, string> = {
            ...(options.headers as Record<string, string>),
        };

        if (!(options.body instanceof FormData) && !headers['Content-Type']) {
            headers['Content-Type'] = 'application/json';
        }

        const token = this.getToken();
        if (token) {
            headers['Authorization'] = `Bearer ${token}`;
        }

        const response = await fetch(endpoint, { ...options, headers });

        if (response.status === 401 && this.getRefreshToken()) {
            if (!this.isRefreshing) {
                this.isRefreshing = true;
                try {
                    const newToken = await this.refreshAccessToken();
                    this.isRefreshing = false;
                    this.onRefreshed(newToken);

                    headers['Authorization'] = `Bearer ${newToken}`;
                    const retryResponse = await fetch(endpoint, { ...options, headers });

                    if (!retryResponse.ok) {
                        let errorDetails = '';
                        try { const d = await retryResponse.json(); errorDetails = d.detail || JSON.stringify(d); } catch { errorDetails = retryResponse.statusText; }
                        throw new Error(`API Error: ${retryResponse.status} ${errorDetails}`);
                    }
                    if (options.method === 'DELETE' && retryResponse.status === 204) return undefined as T;
                    const cl = retryResponse.headers.get('content-length');
                    if (cl === '0' || retryResponse.status === 204) return undefined as T;
                    return retryResponse.json();
                } catch (refreshError) {
                    this.isRefreshing = false;
                    this.refreshSubscribers = [];
                    throw refreshError;
                }
            } else {
                return new Promise((resolve, reject) => {
                    this.addRefreshSubscriber((newToken: string) => {
                        headers['Authorization'] = `Bearer ${newToken}`;
                        fetch(endpoint, { ...options, headers })
                            .then((res) => {
                                if (!res.ok) { reject(new Error(`API Error: ${res.status}`)); return; }
                                if (options.method === 'DELETE' && res.status === 204) { resolve(undefined as T); return; }
                                return res.json();
                            })
                            .then((data) => resolve(data))
                            .catch(reject);
                    });
                });
            }
        }

        if (!response.ok) {
            let errorDetails = '';
            try { const d = await response.json(); errorDetails = d.detail || JSON.stringify(d); } catch { errorDetails = response.statusText; }
            throw new Error(`API Error: ${response.status} ${errorDetails}`);
        }

        if (options.method === 'DELETE' && response.status === 204) return undefined as T;
        const contentLength = response.headers.get('content-length');
        if (contentLength === '0' || response.status === 204) return undefined as T;
        return response.json();
    }

    // ── Auth ──────────────────────────────────────────

    async login(credentials: LoginCredentials): Promise<void> {
        const response = await fetch('/api/auth/token/', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(credentials),
        });
        if (!response.ok) throw new Error(`Login failed: ${response.status}`);
        const data: LoginResponse = await response.json();
        this.setToken(data.access);
        this.setRefreshToken(data.refresh);
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    async getCurrentUser(): Promise<any> {
        return this.request('/api/v1/employees/me/');
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    async search(query: string, limit?: number): Promise<any> {
        const queryParams = new URLSearchParams();
        queryParams.append('q', query);
        if (limit) queryParams.append('limit', limit.toString());
        return this.request(`/api/v1/search/?${queryParams.toString()}`);
    }

    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    async updateCurrentUserProfile(data: Record<string, any>): Promise<any> {
        const formData = new FormData();
        Object.keys(data).forEach((key) => {
            if (Array.isArray(data[key])) {
                data[key].forEach((value: any) => {
                    if (value !== null && value !== undefined) formData.append(key, String(value));
                });
            }
            else if (data[key] instanceof File) { formData.append(key, data[key]); }
            else if (data[key] !== null && data[key] !== undefined) { formData.append(key, data[key]); }
        });
        const token = this.getToken();
        const headers: Record<string, string> = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const response = await fetch('/api/v1/employees/me/', { method: 'PATCH', headers, body: formData });
        if (!response.ok) throw new Error(`API Error: ${response.status} ${response.statusText}`);
        return response.json();
    }
}
