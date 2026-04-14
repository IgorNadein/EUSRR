/* eslint-disable @typescript-eslint/no-explicit-any */
import type { RequestFn, GetTokenFn } from './utils';

export function createFeedApi(request: RequestFn, getToken: GetTokenFn) {
    type PinScope = 'global' | 'department';

    async function extractErrorDetails(response: Response): Promise<string> {
        const contentType = response.headers.get('content-type') || '';
        try {
            if (contentType.includes('application/json')) {
                const data = await response.json();
                if (typeof data?.detail === 'string' && data.detail.trim()) return data.detail;
                const firstEntry = Object.entries(data || {})[0];
                if (firstEntry) {
                    const value = firstEntry[1];
                    if (Array.isArray(value) && value[0]) return JSON.stringify(data);
                    if (typeof value === 'string' && value.trim()) return JSON.stringify(data);
                }
                return JSON.stringify(data);
            }
            const text = await response.text();
            return text || response.statusText;
        } catch {
            return response.statusText;
        }
    }

    async function formDataPost(url: string, method: string, data: Record<string, any>) {
        const fd = new FormData();
        if (data.title) fd.append('title', data.title);
        if (data.body) fd.append('body', data.body);
        if (data.content) fd.append('content', data.content);
        if (data.type) fd.append('type', data.type);
        if (data.department !== undefined) fd.append('department', String(data.department));
        if (data.image) fd.append('image', data.image);
        if (data.attachment) fd.append('attachment', data.attachment);
        if (data.attachments) data.attachments.forEach((f: File) => fd.append('attachments', f));
        const token = getToken();
        const headers: HeadersInit = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const response = await fetch(url, { method, headers, body: fd });
        if (!response.ok) {
            const details = await extractErrorDetails(response);
            console.error('API Error Response:', details);
            throw new Error(`API Error: ${response.status} ${details}`);
        }
        return response.json();
    }

    return {
        getPosts: (params?: { page?: number; search?: string; limit?: number; type?: string; department?: number | string; author?: number | string; pinned?: boolean; pinScope?: PinScope }) => {
            const qp = new URLSearchParams();
            if (params?.page) qp.append('page', params.page.toString());
            if (params?.search) qp.append('search', params.search);
            if (params?.limit) qp.append('limit', params.limit.toString());
            if (params?.type) qp.append('type', params.type);
            if (params?.department !== undefined) qp.append('department', String(params.department));
            if (params?.author !== undefined) qp.append('author', String(params.author));
            if (params?.pinned !== undefined) qp.append('pinned', String(params.pinned));
            if (params?.pinScope) qp.append('pin_scope', params.pinScope);
            const qs = qp.toString();
            return request(`/api/v1/posts/${qs ? '?' + qs : ''}`);
        },
        createPost: (data: Record<string, any>) => formDataPost('/api/v1/posts/', 'POST', data),
        updatePost: (postId: number, data: Record<string, any>) => formDataPost(`/api/v1/posts/${postId}/`, 'PATCH', data),
        deletePost: (postId: number): Promise<void> => request(`/api/v1/posts/${postId}/`, { method: 'DELETE' }),
        pinPost: (postId: number, scope: PinScope = 'global') => request(`/api/v1/posts/${postId}/pin/?scope=${scope}`, { method: 'POST' }),
        unpinPost: (postId: number, scope: PinScope = 'global') => request(`/api/v1/posts/${postId}/unpin/?scope=${scope}`, { method: 'POST' }),
        likePost: (postId: number) => request(`/api/v1/posts/${postId}/like/`, { method: 'POST' }),
        unlikePost: (postId: number) => request(`/api/v1/posts/${postId}/unlike/`, { method: 'POST' }),
        getPostLikers: (postId: number) => request(`/api/v1/posts/${postId}/likers/`),
        getComments: (params: { post: number; page?: number }) => {
            const qp = new URLSearchParams();
            if (params.page) qp.append('page', params.page.toString());
            const qs = qp.toString();
            return request(`/api/v1/posts/${params.post}/comments/${qs ? '?' + qs : ''}`);
        },
        createComment: async (postId: number, text: string, image?: File, attachment?: File) => {
            if (image || attachment) {
                const fd = new FormData(); fd.append('text', text);
                if (image) fd.append('image', image);
                if (attachment) fd.append('attachment', attachment);
                const token = getToken();
                const headers: HeadersInit = {};
                if (token) headers['Authorization'] = `Bearer ${token}`;
                const response = await fetch(`/api/v1/posts/${postId}/comments/`, { method: 'POST', headers, body: fd });
                if (!response.ok) {
                    const details = await extractErrorDetails(response);
                    console.error('API Error Response:', details);
                    throw new Error(`API Error: ${response.status} ${details}`);
                }
                return response.json();
            }
            return request(`/api/v1/posts/${postId}/comments/`, { method: 'POST', body: JSON.stringify({ text }) });
        },
        updateComment: async (commentId: number, text: string) => {
            const response: any = await request(`/api/v1/communications/messages/${commentId}/`, { method: 'PATCH', body: JSON.stringify({ content: text }) });
            return { ...response, text: response.content || text };
        },
        deleteComment: (commentId: number): Promise<void> => request(`/api/v1/communications/messages/${commentId}/`, { method: 'DELETE' }),
    };
}
