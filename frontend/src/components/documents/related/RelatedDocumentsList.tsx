'use client';

import { useState, useEffect } from 'react';
import { X } from 'lucide-react';
import { RelatedDocument, Document } from '@/types/api';
import { apiClient } from '@/lib/api';

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
      {showAddModal && (
        <div 
          className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-2 sm:p-4" 
          onClick={() => {
            setShowAddModal(false);
            setSearchQuery('');
            setSearchResults([]);
          }}
        >
          <div 
            className="w-full max-w-[95vw] sm:max-w-md rounded-xl sm:rounded-2xl bg-white shadow-xl max-h-[95vh] sm:max-h-[90vh] overflow-y-auto" 
            onClick={(e) => e.stopPropagation()}
          >
            <div className="flex items-center justify-between border-b border-gray-200 px-4 sm:px-6 py-3 sm:py-4">
              <h5 className="text-base sm:text-lg font-semibold text-gray-900">Добавить связанный документ</h5>
              <button
                type="button"
                className="rounded-full p-1 hover:bg-gray-100"
                onClick={() => {
                  setShowAddModal(false);
                  setSearchQuery('');
                  setSearchResults([]);
                }}
              >
                <X size={20} className="text-gray-600" />
              </button>
            </div>
            
            <div className="px-4 sm:px-6 py-4">
              <div className="mb-4">
                <input
                  type="text"
                  className="w-full px-3 py-2 border border-gray-300 rounded-lg text-sm sm:text-base focus:outline-none focus:ring-2 focus:ring-sky-500"
                  placeholder="Поиск документов..."
                  value={searchQuery}
                  onChange={e => setSearchQuery(e.target.value)}
                />
              </div>

              {searching && (
                <div className="text-center py-4">
                  <div className="inline-block h-6 w-6 animate-spin rounded-full border-2 border-gray-300 border-t-sky-600"></div>
                </div>
              )}

              {!searching && searchQuery && searchResults.length === 0 && (
                <div className="text-gray-500 text-center py-4 text-sm">
                  Документы не найдены
                </div>
              )}

              {!searching && searchResults.length > 0 && (
                <div className="space-y-2 max-h-[50vh] overflow-y-auto">
                  {searchResults.map(doc => (
                    <button
                      key={doc.id}
                      type="button"
                      className="w-full text-left p-3 border border-gray-200 rounded-lg hover:bg-gray-50 transition"
                      onClick={() => handleAdd(doc.id)}
                    >
                      <div className="flex justify-between items-start gap-2 mb-1">
                        <h6 className="font-medium text-sm text-gray-900 flex-1 min-w-0 truncate">{doc.title}</h6>
                        <small className="text-xs text-gray-500 shrink-0">{doc.file_name}</small>
                      </div>
                      <small className="text-xs text-gray-500">
                        {doc.uploaded_by?.first_name} {doc.uploaded_by?.last_name}
                      </small>
                    </button>
                  ))}
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
