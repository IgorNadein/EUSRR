/* eslint-disable @typescript-eslint/no-explicit-any */
import type { RequestFn, GetTokenFn } from './utils';

export function createMessagesApi(request: RequestFn, getToken: GetTokenFn) {
    async function uploadMessage(chatId: number | string, text: string, files: File[], replyTo?: number) {
        const fd = new FormData();
        fd.append('content', text);
        fd.append('chat_id', chatId.toString());
        if (replyTo) fd.append('reply_to', replyTo.toString());
        files.forEach((file, i) => fd.append(`file_${i}`, file));
        const token = getToken();
        const headers: Record<string, string> = {};
        if (token) headers['Authorization'] = `Bearer ${token}`;
        const response = await fetch('/api/v1/communications/messages/upload/', { method: 'POST', headers, body: fd });
        if (!response.ok) {
            let d = ''; try { const e = await response.json(); d = e.detail || JSON.stringify(e); } catch { d = response.statusText; }
            throw new Error(`API Error: ${response.status} ${d}`);
        }
        const result = await response.json();
        return result.message || result;
    }

    function buildChatsQuery(params?: { search?: string; page?: number; page_size?: number }) {
        const qp = new URLSearchParams();
        if (params?.search) qp.append('search', params.search);
        if (params?.page) qp.append('page', params.page.toString());
        if (params?.page_size) qp.append('page_size', params.page_size.toString());
        const qs = qp.toString();
        return `/api/v1/communications/chats/${qs ? '?' + qs : ''}`;
    }

    return {
        getChats: (params?: { search?: string; page?: number; page_size?: number }) => request(buildChatsQuery(params)),
        getAllChats: async (params?: { search?: string; page_size?: number }) => {
            const pageSize = params?.page_size ?? 200;
            const chats: any[] = [];
            let page = 1;

            for (;;) {
                const response = await request(buildChatsQuery({
                    search: params?.search,
                    page,
                    page_size: pageSize,
                })) as { results?: any[]; next?: string | null } | any[];
                const results = Array.isArray(response) ? response : (response.results || []);
                chats.push(...results);

                if (Array.isArray(response) || !response.next) {
                    break;
                }

                page += 1;
            }

            return chats;
        },
        getChat: (chatId: number) => request(`/api/v1/communications/chats/${chatId}/`),
        createChat: (data: { type: string; participants?: number[]; name?: string; description?: string; department?: number; include_all_employees?: boolean; avatar?: File }) => {
            if (data.avatar) {
                const fd = new FormData();
                fd.append('type', data.type);
                if (data.name) fd.append('name', data.name);
                if (data.description) fd.append('description', data.description);
                if (data.avatar) fd.append('avatar', data.avatar);
                data.participants?.forEach(id => fd.append('participants', id.toString()));
                if (data.department) fd.append('department', data.department.toString());
                if (data.include_all_employees !== undefined) fd.append('include_all_employees', data.include_all_employees.toString());
                return request('/api/v1/communications/chats/', { method: 'POST', body: fd });
            }
            return request('/api/v1/communications/chats/', { method: 'POST', body: JSON.stringify(data) });
        },
        getChatMessages: (chatId: number, params?: { limit?: number; before_id?: number; after_id?: number; mark_read?: boolean; before?: string; after?: string }) => {
            const qp = new URLSearchParams();
            if (params?.limit) qp.append('limit', params.limit.toString());
            if (params?.before_id) qp.append('before_id', params.before_id.toString());
            if (params?.after_id) qp.append('after_id', params.after_id.toString());
            if (typeof params?.mark_read === 'boolean') qp.append('mark_read', String(params.mark_read));
            if (params?.before) qp.append('before', params.before);
            if (params?.after) qp.append('after', params.after);
            const qs = qp.toString();
            return request(`/api/v1/communications/chats/${chatId}/messages/${qs ? '?' + qs : ''}`);
        },
        getChatMessagesAround: (chatId: number | string, params?: { limit?: number; around_id?: number }) => {
            const qp = new URLSearchParams();
            if (params?.limit) qp.append('limit', params.limit.toString());
            if (params?.around_id) qp.append('around_id', params.around_id.toString());
            const qs = qp.toString();
            return request(`/api/v1/communications/chats/${chatId}/messages-around/${qs ? '?' + qs : ''}`);
        },
        sendMessage: (chatId: number | string, text: string, replyTo?: number) => uploadMessage(chatId, text, [], replyTo),
        sendMessageWithFiles: (chatId: number | string, text: string, files: File[], replyTo?: number) => uploadMessage(chatId, text, files, replyTo),
        updateMessage: (messageId: number, text: string) => request(`/api/v1/communications/messages/${messageId}/`, { method: 'PATCH', body: JSON.stringify({ content: text }) }),
        deleteMessage: (messageId: number): Promise<void> => request(`/api/v1/communications/messages/${messageId}/`, { method: 'DELETE' }),
        markChatAsRead: (chatId: number, lastReadMessageId?: number) => request(`/api/v1/communications/chats/${chatId}/mark-read/`, { method: 'POST', body: JSON.stringify({ message_id: lastReadMessageId }) }),
        togglePinChat: (chatId: number) => request(`/api/v1/communications/chats/${chatId}/pin/`, { method: 'POST' }),
        toggleChatNotifications: (chatId: number) => request(`/api/v1/communications/chats/${chatId}/notifications/`, { method: 'POST' }),
        leaveChat: (chatId: number) => request(`/api/v1/communications/chats/${chatId}/leave/`, { method: 'POST' }),
        deleteChat: (chatId: number) => request(`/api/v1/communications/chats/${chatId}/`, { method: 'DELETE' }),
        updateChat: (chatId: number, data: Record<string, any>) => request(`/api/v1/communications/chats/${chatId}/`, { method: 'PATCH', body: JSON.stringify(data) }),
        uploadChatAvatar: (chatId: number, file: File) => { const fd = new FormData(); fd.append('avatar', file); return request(`/api/v1/communications/chats/${chatId}/`, { method: 'PATCH', body: fd }); },
        addChatMember: (chatId: number, userId: number) => request(`/api/v1/communications/chats/${chatId}/add-member/`, { method: 'POST', body: JSON.stringify({ user_id: userId }) }),
        removeChatMember: (chatId: number, userId: number) => request(`/api/v1/communications/chats/${chatId}/remove-member/`, { method: 'POST', body: JSON.stringify({ user_id: userId }) }),
        changeChatMemberRole: (chatId: number, userId: number, role: 'admin' | 'moderator' | 'member' | 'guest') => request(`/api/v1/communications/chats/${chatId}/change-role/`, { method: 'POST', body: JSON.stringify({ user_id: userId, role }) }),
        updateChatUserSettings: (chatId: number, data: Record<string, any>) => request(`/api/v1/communications/chats/${chatId}/user-settings/`, { method: 'PATCH', body: JSON.stringify(data) }),
        reactToMessage: (messageId: number, emoji: string) => request(`/api/v1/communications/messages/${messageId}/react/`, { method: 'POST', body: JSON.stringify({ emoji }) }),
        unreactToMessage: (messageId: number, emoji: string) => request(`/api/v1/communications/messages/${messageId}/unreact/`, { method: 'POST', body: JSON.stringify({ emoji }) }),
    };
}
