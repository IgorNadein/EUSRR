import type { GetTokenFn, RawRequestFn, RequestFn } from './utils';

function parseDownloadFilename(response: Response, fallback: string): string {
    const disposition = response.headers.get('content-disposition') || '';
    const encodedMatch = disposition.match(/filename\*=UTF-8''([^;]+)/);
    const plainMatch = disposition.match(/filename="?([^"]+)"?/);
    return encodedMatch?.[1]
        ? decodeURIComponent(encodedMatch[1])
        : plainMatch?.[1] || fallback;
}

async function fetchDownload(
    endpoint: string,
    options: RequestInit,
    fallbackFilename: string,
    requestRaw?: RawRequestFn,
    getToken?: GetTokenFn
): Promise<{ blob: Blob; filename: string }> {
    let response: Response;

    if (requestRaw) {
        response = await requestRaw(endpoint, options);
    } else {
        const headers: Record<string, string> = {
            ...(options.headers as Record<string, string>),
        };
        const token = getToken?.();
        if (token) headers.Authorization = `Bearer ${token}`;
        response = await fetch(endpoint, { ...options, headers });

        if (!response.ok) {
            let errorDetails = response.statusText;
            try {
                const data = await response.json();
                errorDetails = data.detail || JSON.stringify(data);
            } catch {}
            throw new Error(`API Error: ${response.status} ${errorDetails}`);
        }
    }

    return {
        blob: await response.blob(),
        filename: parseDownloadFilename(response, fallbackFilename),
    };
}

export function createDocumentsApi(request: RequestFn, getToken?: GetTokenFn, requestRaw?: RawRequestFn) {
    return {
        getDocuments: (params?: { search?: string; type?: string; status?: string; scope?: string; page?: number; page_size?: number; limit?: number; folder_id?: number; is_regulation?: boolean }) => {
            const qp = new URLSearchParams();
            if (params?.search) qp.append('search', params.search);
            if (params?.type) qp.append('type', params.type);
            if (params?.status) qp.append('status', params.status);
            if (params?.scope) qp.append('scope', params.scope);
            if (params?.page) qp.append('page', params.page.toString());
            const pageSize = params?.page_size ?? params?.limit;
            if (pageSize) qp.append('page_size', pageSize.toString());
            if (params?.folder_id !== undefined) qp.append('folder_id', params.folder_id.toString());
            if (params?.is_regulation !== undefined) qp.append('is_regulation', String(params.is_regulation));
            const qs = qp.toString();
            return request(`/api/v1/documents/${qs ? '?' + qs : ''}`);
        },
        getDocument: (id: number) => request(`/api/v1/documents/${id}/`),
        createDocument: (data: { title?: string; description?: string; file?: File | Blob; extracted_text?: string; sent_to_all?: boolean; is_regulation?: boolean; recipient_ids?: number[]; department_ids?: number[]; folder_id?: number | null; acknowledgement_required?: boolean; acknowledgement_for_all?: boolean; acknowledgement_recipient_ids?: number[]; acknowledgement_department_ids?: number[]; tag_ids?: number[] }) => {
            const fd = new FormData();
            if (data.title?.trim()) fd.append('title', data.title.trim());
            if (data.description) fd.append('description', data.description);
            if (data.extracted_text) fd.append('extracted_text', data.extracted_text);
            if (data.folder_id) fd.append('folder', String(data.folder_id));
            fd.append('sent_to_all', String(data.sent_to_all ?? true));
            fd.append('is_regulation', String(data.is_regulation ?? false));
            if (data.acknowledgement_required !== undefined) fd.append('acknowledgement_required', String(data.acknowledgement_required));
            if (data.acknowledgement_for_all !== undefined) fd.append('acknowledgement_for_all', String(data.acknowledgement_for_all));
            if (data.recipient_ids !== undefined) fd.append('recipient_ids', JSON.stringify(data.recipient_ids));
            if (data.department_ids !== undefined) fd.append('department_ids', JSON.stringify(data.department_ids));
            if (data.acknowledgement_recipient_ids !== undefined) fd.append('acknowledgement_recipient_ids', JSON.stringify(data.acknowledgement_recipient_ids));
            if (data.acknowledgement_department_ids !== undefined) fd.append('acknowledgement_department_ids', JSON.stringify(data.acknowledgement_department_ids));
            data.tag_ids?.forEach(id => fd.append('tag_ids', String(id)));
            if (data.file) fd.append('file', data.file);
            return request('/api/v1/documents/', { method: 'POST', body: fd });
        },
        updateDocument: (id: number, data: { title?: string; description?: string; extracted_text?: string; file?: File; tag_ids?: number[]; folder?: number | null; is_regulation?: boolean; sent_to_all?: boolean; acknowledgement_required?: boolean; acknowledgement_for_all?: boolean; recipient_ids?: number[]; department_ids?: number[]; acknowledgement_recipient_ids?: number[]; acknowledgement_department_ids?: number[] }) => {
            const fd = new FormData();
            if (data.title !== undefined) fd.append('title', data.title);
            if (data.description !== undefined) fd.append('description', data.description);
            if (data.extracted_text !== undefined) fd.append('extracted_text', data.extracted_text);
            if (data.file) fd.append('file', data.file);
            if (data.folder !== undefined) fd.append('folder', data.folder === null ? '' : String(data.folder));
            if (data.is_regulation !== undefined) fd.append('is_regulation', String(data.is_regulation));
            if (data.sent_to_all !== undefined) fd.append('sent_to_all', String(data.sent_to_all));
            if (data.acknowledgement_required !== undefined) fd.append('acknowledgement_required', String(data.acknowledgement_required));
            if (data.acknowledgement_for_all !== undefined) fd.append('acknowledgement_for_all', String(data.acknowledgement_for_all));
            if (data.department_ids !== undefined) fd.append('department_ids', JSON.stringify(data.department_ids));
            if (data.recipient_ids !== undefined) fd.append('recipient_ids', JSON.stringify(data.recipient_ids));
            if (data.acknowledgement_department_ids !== undefined) fd.append('acknowledgement_department_ids', JSON.stringify(data.acknowledgement_department_ids));
            if (data.acknowledgement_recipient_ids !== undefined) fd.append('acknowledgement_recipient_ids', JSON.stringify(data.acknowledgement_recipient_ids));
            data.tag_ids?.forEach(tagId => fd.append('tag_ids', String(tagId)));
            return request(`/api/v1/documents/${id}/`, { method: 'PATCH', body: fd });
        },
        deleteDocument: (id: number): Promise<void> => request(`/api/v1/documents/${id}/`, { method: 'DELETE' }),
        downloadDocumentsArchive: async (ids: number[]): Promise<{ blob: Blob; filename: string }> => {
            return fetchDownload(
                '/api/v1/documents/archive/',
                {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ document_ids: ids }),
                },
                'documents.zip',
                requestRaw,
                getToken
            );
        },
        acknowledgeDocument: (id: number) => request(`/api/v1/documents/${id}/acknowledge/`, { method: 'POST', body: JSON.stringify({}) }),
        getDocumentAcknowledgements: (id: number, search?: string) => {
            const qp = new URLSearchParams();
            if (search) qp.append('search', search);
            const qs = qp.toString();
            return request(`/api/v1/documents/${id}/acknowledgements/${qs ? '?' + qs : ''}`);
        },
        // Folders
        getFolders: (params?: { parent_id?: number; root?: boolean; page?: number; page_size?: number; limit?: number }) => {
            const qp = new URLSearchParams();
            if (params?.parent_id !== undefined) qp.append('parent_id', params.parent_id.toString());
            if (params?.root) qp.append('root', 'true');
            if (params?.page) qp.append('page', params.page.toString());
            const pageSize = params?.page_size ?? params?.limit;
            if (pageSize) qp.append('page_size', pageSize.toString());
            const qs = qp.toString();
            return request(`/api/v1/folders/${qs ? '?' + qs : ''}`);
        },
        getFolder: (id: number) => request(`/api/v1/folders/${id}/`),
        createFolder: (data: { name: string; parent?: number | null }) => request('/api/v1/folders/', { method: 'POST', body: JSON.stringify(data) }),
        updateFolder: (id: number, data: { name?: string; parent?: number | null }) => request(`/api/v1/folders/${id}/`, { method: 'PATCH', body: JSON.stringify(data) }),
        deleteFolder: (id: number): Promise<void> => request(`/api/v1/folders/${id}/`, { method: 'DELETE' }),
        downloadFolderArchive: async (id: number): Promise<{ blob: Blob; filename: string }> => {
            return fetchDownload(
                `/api/v1/folders/${id}/archive/`,
                {},
                `folder-${id}.zip`,
                requestRaw,
                getToken
            );
        },
        getFolderChildren: (id: number) => request(`/api/v1/folders/${id}/children/`),
        getFolderDocuments: (id: number) => request(`/api/v1/folders/${id}/documents/`),
        // Comments
        getDocumentComments: (documentId: number) => request(`/api/v1/documents/${documentId}/comments/`),
        createDocumentComment: (data: { document: number; text: string; parent?: number }) =>
            request(`/api/v1/documents/${data.document}/comments/`, { method: 'POST', body: JSON.stringify({ text: data.text, parent_id: data.parent }) }),
        updateDocumentComment: (documentId: number, id: number, text: string) => request(`/api/v1/documents/${documentId}/comments/${id}/`, { method: 'PATCH', body: JSON.stringify({ text }) }),
        deleteDocumentComment: (documentId: number, id: number): Promise<void> => request(`/api/v1/documents/${documentId}/comments/${id}/`, { method: 'DELETE' }),
        getCommentReplies: (commentId: number) => request(`/api/v1/document-comments/${commentId}/replies/`),
        // Tags
        getDocumentTags: (params?: { page?: number; page_size?: number; limit?: number }) => {
            const qp = new URLSearchParams();
            if (params?.page) qp.append('page', params.page.toString());
            const pageSize = params?.page_size ?? params?.limit;
            if (pageSize) qp.append('page_size', pageSize.toString());
            const qs = qp.toString();
            return request(`/api/v1/document-tags/${qs ? '?' + qs : ''}`);
        },
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
