'use client';

import { useState, useEffect } from 'react';
import { RelatedDocument, Document } from '@/types/api';
import { apiClient } from '@/lib/api';
import { Modal } from "@/components/ui";

interface RelatedDocumentsListProps {
  documentId: number;
}

export default function RelatedDocumentsList({ documentId }: RelatedDocumentsListProps) {
  const [relatedDocuments, setRelatedDocuments] = useState<RelatedDocument[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [searchResults, setSearchResults] = useState<Document[]>([]);
  const [searching, setSearching] = useState(false);
  const [removing, setRemoving] = useState<number | null>(null);

  useEffect(() => {
    loadRelatedDocuments();
  }, [documentId]);

  const loadRelatedDocuments = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.getRelatedDocuments(documentId);
      setRelatedDocuments(response.results || response);
    } catch (err: any) {
      setError(err.message || 'Ошибка загрузки связанных документов');
      console.error('Failed to load related documents:', err);
    } finally {
      setLoading(false);
    }
  };

  const searchDocuments = async (query: string) => {
    if (!query.trim()) {
      setSearchResults([]);
      return;
    }

    try {
      setSearching(true);
      const response = await apiClient.getDocuments({ search: query, limit: 10 });
      const results = (response.results || response).filter(
        (doc: Document) =>
          doc.id !== documentId &&
          !relatedDocuments.find(rd => rd.id === doc.id)
      );
      setSearchResults(results);
    } catch (err: any) {
      console.error('Failed to search documents:', err);
    } finally {
      setSearching(false);
    }
  };

  const handleAdd = async (relatedId: number) => {
    try {
      await apiClient.addRelatedDocument(documentId, relatedId);
      await loadRelatedDocuments();
      setShowAddModal(false);
      setSearchQuery('');
      setSearchResults([]);
    } catch (err: any) {
      alert(err.message || 'Ошибка при добавлении связи');
    }
  };

  const handleRemove = async (relatedId: number) => {
    if (!confirm('Удалить связь с документом?')) return;

    try {
      setRemoving(relatedId);
      await apiClient.removeRelatedDocument(documentId, relatedId);
      await loadRelatedDocuments();
    } catch (err: any) {
      alert(err.message || 'Ошибка при удалении связи');
    } finally {
      setRemoving(null);
    }
  };

  useEffect(() => {
    if (searchQuery) {
      const timeoutId = setTimeout(() => searchDocuments(searchQuery), 300);
      return () => clearTimeout(timeoutId);
    } else {
      setSearchResults([]);
    }
  }, [searchQuery]);

  return (
    <div className="related-documents-list">
      <div className="d-flex justify-content-between align-items-center mb-3">
        <h5 className="mb-0">
          Связанные документы
          {relatedDocuments.length > 0 && (
            <span className="badge bg-secondary ms-2">{relatedDocuments.length}</span>
          )}
        </h5>
        <button
          className="btn btn-primary btn-sm"
          onClick={() => setShowAddModal(true)}
        >
          <i className="bi bi-plus-lg"></i> Добавить
        </button>
      </div>

      {loading && (
        <div className="text-center py-3">
          <div className="spinner-border spinner-border-sm" role="status">
            <span className="visually-hidden">Загрузка...</span>
          </div>
        </div>
      )}

      {error && (
        <div className="alert alert-danger" role="alert">
          {error}
        </div>
      )}

      {!loading && !error && relatedDocuments.length === 0 && (
        <div className="text-muted text-center py-3">
          Нет связанных документов
        </div>
      )}

      {!loading && !error && relatedDocuments.length > 0 && (
        <div className="list-group">
          {relatedDocuments.map(doc => (
            <div key={doc.id} className="list-group-item">
              <div className="d-flex justify-content-between align-items-start">
                <div className="flex-grow-1">
                  <h6 className="mb-1">
                    <a href={`/documents/${doc.id}`} className="text-decoration-none">
                      {doc.title}
                    </a>
                  </h6>
                  <div className="small text-muted">
                    <span className="badge bg-light text-dark me-2">{doc.file_type}</span>
                    <i className="bi bi-person"></i> {doc.uploaded_by}
                    <span className="mx-2">·</span>
                    <i className="bi bi-calendar"></i> {new Date(doc.created_at).toLocaleDateString('ru-RU')}
                  </div>
                </div>

                <button
                  type="button"
                  className="btn btn-sm btn-outline-danger"
                  onClick={() => handleRemove(doc.id)}
                  disabled={removing === doc.id}
                  title="Удалить связь"
                >
                  {removing === doc.id ? (
                    <span className="spinner-border spinner-border-sm"></span>
                  ) : (
                    <i className="bi bi-x-lg"></i>
                  )}
                </button>
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Модальное окно добавления */}
      <Modal
        isOpen={showAddModal}
        onClose={() => {
          setShowAddModal(false);
          setSearchQuery('');
          setSearchResults([]);
        }}
        title="Добавить связанный документ"
        size="sm"
      >
              <div className="mb-4">
                <input
                  type="text"
                  className="app-input w-full rounded-lg px-3 py-2 text-sm sm:text-base"
                  placeholder="Поиск документов..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                />
              </div>

              {searching && (
                <div className="text-center py-4">
                  <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-[var(--border-strong)] border-t-[var(--accent-primary)]"></div>
                </div>
              )}

              {!searching && searchQuery && searchResults.length === 0 && (
                <div className="app-text-muted py-4 text-center text-sm">
                  Документы не найдены
                </div>
              )}

              {!searching && searchResults.length > 0 && (
                <div className="space-y-2 max-h-[50vh] overflow-y-auto">
                  {searchResults.map(doc => (
                    <button
                      key={doc.id}
                      type="button"
                      className="app-surface w-full rounded-lg p-3 text-left transition hover:bg-[var(--surface-secondary)]"
                      onClick={() => handleAdd(doc.id)}
                    >
                      <div className="flex justify-between items-start gap-2 mb-1">
                        <h6 className="flex-1 min-w-0 truncate text-sm font-medium text-[var(--foreground)]">{doc.title}</h6>
                        <small className="app-text-muted shrink-0 text-xs">{doc.file_name}</small>
                      </div>
                      <small className="app-text-muted text-xs">
                        {doc.uploaded_by?.first_name} {doc.uploaded_by?.last_name}
                      </small>
                    </button>
                  ))}
                </div>
              )}
      </Modal>
    </div>
  );
}
