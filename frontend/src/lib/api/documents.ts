import type { RequestFn } from './utils';

export function createDocumentsApi(request: RequestFn) {
    return {
        getDocuments: (params?: { search?: string; type?: string; status?: string; page?: number; limit?: number; folder_id?: number }) => {
            const qp = new URLSearchParams();
            if (params?.search) qp.append('search', params.search);
            if (params?.type) qp.append('type', params.type);
            if (params?.status) qp.append('status', params.status);
            if (params?.page) qp.append('page', params.page.toString());
            if (params?.limit) qp.append('limit', params.limit.toString());
            if (params?.folder_id !== undefined) qp.append('folder_id', params.folder_id.toString());
            const qs = qp.toString();
            return request(`/api/v1/documents/${qs ? '?' + qs : ''}`);
        },
        getDocument: (id: number) => request(`/api/v1/documents/${id}/`),
        createDocument: (data: { title: string; description?: string; file: File | Blob; extracted_text?: string; sent_to_all?: boolean; recipient_ids?: number[]; department_ids?: number[]; folder_id?: number | null; acknowledgement_required?: boolean; tag_ids?: number[] }) => {
            const fd = new FormData();
            fd.append('title', data.title);
            if (data.description) fd.append('description', data.description);
            if (data.extracted_text) fd.append('extracted_text', data.extracted_text);
            if (data.folder_id) fd.append('folder', String(data.folder_id));
            fd.append('sent_to_all', String(data.sent_to_all ?? true));
            if (data.acknowledgement_required !== undefined) fd.append('acknowledgement_required', String(data.acknowledgement_required));
            data.recipient_ids?.forEach(id => fd.append('recipient_ids', String(id)));
            data.department_ids?.forEach(id => fd.append('department_ids', String(id)));
            data.tag_ids?.forEach(id => fd.append('tag_ids', String(id)));
            fd.append('file', data.file);
            return request('/api/v1/documents/', { method: 'POST', body: fd });
        },
        updateDocument: (id: number, data: { title?: string; description?: string; file?: File; tag_ids?: number[]; folder?: number | null }) => {
            const fd = new FormData();
            if (data.title !== undefined) fd.append('title', data.title);
            if (data.description !== undefined) fd.append('description', data.description);
            if (data.file) fd.append('file', data.file);
            if (data.folder !== undefined) fd.append('folder', data.folder === null ? '' : String(data.folder));
            data.tag_ids?.forEach(tagId => fd.append('tag_ids', String(tagId)));
            return request(`/api/v1/documents/${id}/`, { method: 'PATCH', body: fd });
        },
        deleteDocument: (id: number): Promise<void> => request(`/api/v1/documents/${id}/`, { method: 'DELETE' }),
        acknowledgeDocument: (id: number) => request(`/api/v1/documents/${id}/acknowledge/`, { method: 'POST', body: JSON.stringify({}) }),
        getDocumentAcknowledgements: (id: number, search?: string) => {
            const qp = new URLSearchParams();
            if (search) qp.append('search', search);
            const qs = qp.toString();
            return request(`/api/v1/documents/${id}/acknowledgements/${qs ? '?' + qs : ''}`);
        },
        // Folders
        getFolders: (params?: { parent_id?: number; root?: boolean }) => {
            const qp = new URLSearchParams();
            if (params?.parent_id !== undefined) qp.append('parent_id', params.parent_id.toString());
            if (params?.root) qp.append('root', 'true');
            const qs = qp.toString();
            return request(`/api/v1/folders/${qs ? '?' + qs : ''}`);
        },
        getFolder: (id: number) => request(`/api/v1/folders/${id}/`),
        createFolder: (data: { name: string; parent?: number | null }) => request('/api/v1/folders/', { method: 'POST', body: JSON.stringify(data) }),
        updateFolder: (id: number, data: { name?: string; parent?: number | null }) => request(`/api/v1/folders/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),
        deleteFolder: (id: number): Promise<void> => request(`/api/v1/folders/${id}/`, { method: 'DELETE' }),
        getFolderChildren: (id: number) => request(`/api/v1/folders/${id}/children/`),
        getFolderDocuments: (id: number) => request(`/api/v1/folders/${id}/documents/`),
        // Comments
        getDocumentComments: (documentId: number) => request(`/api/v1/document-comments/?document=${documentId}`),
        createDocumentComment: (data: { document: number; text: string; parent?: number }) =>
            request('/api/v1/document-comments/', { method: 'POST', body: JSON.stringify({ document_id: data.document, text: data.text, parent_id: data.parent }) }),
        updateDocumentComment: (id: number, text: string) => request(`/api/v1/document-comments/${id}/`, { method: 'PATCH', body: JSON.stringify({ text }) }),
        deleteDocumentComment: (id: number): Promise<void> => request(`/api/v1/document-comments/${id}/`, { method: 'DELETE' }),
        getCommentReplies: (commentId: number) => request(`/api/v1/document-comments/${commentId}/replies/`),
        // Tags
        getDocumentTags: () => request('/api/v1/document-tags/'),
        getDocumentTag: (id: number) => request(`/api/v1/document-tags/${id}/`),
        createDocumentTag: (data: { name: string; color?: string }) => request('/api/v1/document-tags/', { method: 'POST', body: JSON.stringify(data) }),
        updateDocumentTag: (id: number, data: { name?: string; color?: string }) => request(`/api/v1/document-tags/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),
        deleteDocumentTag: (id: number): Promise<void> => request(`/api/v1/document-tags/${id}/`, { method: 'DELETE' }),
        getDocumentsByTag: (tagId: number) => request(`/api/v1/document-tags/${tagId}/documents/`),
        // Related
        getRelatedDocuments: (id: number) => request(`/api/v1/documents/${id}/related/`),
        addRelatedDocument: (id: number, relatedId: number) => request(`/api/v1/documents/${id}/add_related/`, { method: 'POST', body: JSON.stringify({ related_document_id: relatedId }) }),
        removeRelatedDocument: (id: number, relatedId: number) => request(`/api/v1/documents/${id}/remove_related/`, { method: 'DELETE', body: JSON.stringify({ related_document_id: relatedId }) }),
        // Thumbnails
        getDocumentThumbnail: (id: number, size?: 'small' | 'medium' | 'large' | 'original'): string => {
            const sizeParam = size ? `?size=${size}` : '';
            return `/api/v1/documents/${id}/thumbnail/${sizeParam}`;
        },
    };
}
