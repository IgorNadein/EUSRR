/* eslint-disable @typescript-eslint/no-explicit-any */
import type { RequestFn, GetTokenFn } from './utils';

export function createFeedApi(request: RequestFn, getToken: GetTokenFn) {
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
        if (!response.ok) { const t = await response.text(); console.error('API Error Response:', t); throw new Error(`API Error: ${response.status} ${response.statusText}`); }
        return response.json();
    }

    return {
        getPosts: (params?: { page?: number; search?: string; limit?: number }) => {
            const qp = new URLSearchParams();
            if (params?.page) qp.append('page', params.page.toString());
            if (params?.search) qp.append('search', params.search);
            if (params?.limit) qp.append('limit', params.limit.toString());
            const qs = qp.toString();
            return request(`/api/v1/posts/${qs ? '?' + qs : ''}`);
        },
        createPost: (data: Record<string, any>) => formDataPost('/api/v1/posts/', 'POST', data),
        updatePost: (postId: number, data: Record<string, any>) => formDataPost(`/api/v1/posts/${postId}/`, 'PATCH', data),
        deletePost: (postId: number): Promise<void> => request(`/api/v1/posts/${postId}/`, { method: 'DELETE' }),
        pinPost: (postId: number) => request(`/api/v1/posts/${postId}/pin/`, { method: 'POST' }),
        unpinPost: (postId: number) => request(`/api/v1/posts/${postId}/unpin/`, { method: 'POST' }),
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
                if (!response.ok) { const t = await response.text(); console.error('API Error Response:', t); throw new Error(`API Error: ${response.status} ${response.statusText}`); }
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
