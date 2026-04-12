"use client";

import { useState, useEffect } from "react";
import { Link2, Plus, X, FileText, ExternalLink } from "lucide-react";
import { apiClient } from "@/lib/api";
import { toast } from "sonner";

interface RelatedDocument {
  id: number;
  title: string;
  created_at: string;
  file_name?: string;
}

interface DocumentRelatedProps {
  documentId: number;
  onNavigate?: (documentId: number) => void;
}

export function DocumentRelated({ documentId, onNavigate }: DocumentRelatedProps) {
  const [relatedDocs, setRelatedDocs] = useState<RelatedDocument[]>([]);
  const [loading, setLoading] = useState(true);
  const [showAddDialog, setShowAddDialog] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState<RelatedDocument[]>([]);
  const [searching, setSearching] = useState(false);
  const [adding, setAdding] = useState(false);

  useEffect(() => {
    loadRelatedDocuments();
  }, [documentId]);

  const loadRelatedDocuments = async () => {
    try {
      setLoading(true);
      const response = await apiClient.getRelatedDocuments(documentId);
      const data = Array.isArray(response) ? response : (response.results || []);
      setRelatedDocs(data);
    } catch (error) {
      console.error("Ошибка загрузки связанных документов:", error);
      toast.error("Не удалось загрузить связанные документы");
    } finally {
      setLoading(false);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) {
      setSearchResults([]);
      return;
    }

    setSearching(true);
    try {
      const response = await apiClient.getDocuments({ search: searchQuery });
      const results = (response.results || response || [])
        .filter((doc: RelatedDocument) => doc.id !== documentId)
        .filter((doc: RelatedDocument) => !relatedDocs.some(rd => rd.id === doc.id));
      setSearchResults(results);
    } catch (error) {
      console.error("Ошибка поиска:", error);
      toast.error("Не удалось выполнить поиск");
    } finally {
      setSearching(false);
    }
  };

  useEffect(() => {
    const timer = setTimeout(() => {
      if (showAddDialog) {
        handleSearch();
      }
    }, 300);
    return () => clearTimeout(timer);
  }, [searchQuery, showAddDialog]);

  const handleAdd = async (relatedId: number) => {
    setAdding(true);
    try {
      await apiClient.addRelatedDocument(documentId, relatedId);
      toast.success("Связь добавлена");
      await loadRelatedDocuments();
      setShowAddDialog(false);
      setSearchQuery("");
      setSearchResults([]);
    } catch (error) {
      console.error("Ошибка добавления связи:", error);
      toast.error("Не удалось добавить связь");
    } finally {
      setAdding(false);
    }
  };

  const handleRemove = async (relatedId: number) => {
    if (!window.confirm("Удалить связь с этим документом?")) return;

    try {
      await apiClient.removeRelatedDocument(documentId, relatedId);
      toast.success("Связь удалена");
      await loadRelatedDocuments();
    } catch (error) {
      console.error("Ошибка удаления связи:", error);
      toast.error("Не удалось удалить связь");
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center py-8">
        <div className="h-6 w-6 animate-spin rounded-full border-2 border-[var(--accent-primary)] border-t-transparent" />
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div className="flex items-center gap-2">
          <Link2 size={18} className="app-text-muted" />
          <h3 className="text-sm font-medium text-[var(--foreground)]">
            Связанные документы ({relatedDocs.length})
          </h3>
        </div>
        <button
          onClick={() => setShowAddDialog(true)}
          className="app-action-primary inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium"
        >
          <Plus size={14} />
          Добавить
        </button>
      </div>

      {/* Add Dialog */}
      {showAddDialog && (
        <div className="app-selected rounded-lg p-3">
          <div className="mb-3 flex items-center justify-between">
            <h4 className="text-sm font-medium text-[var(--foreground)]">Поиск документа</h4>
            <button
              onClick={() => {
                setShowAddDialog(false);
                setSearchQuery("");
                setSearchResults([]);
              }}
              className="app-text-muted hover:text-[var(--foreground)]"
            >
              <X size={16} />
            </button>
          </div>

          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="Введите название документа..."
            className="app-input w-full rounded-lg px-3 py-2 text-sm"
            autoFocus
          />

          {searching && (
            <div className="mt-3 text-center">
              <div className="inline-block h-4 w-4 animate-spin rounded-full border-2 border-[var(--accent-primary)] border-t-transparent" />
            </div>
          )}

          {searchResults.length > 0 && (
            <div className="mt-3 max-h-60 space-y-2 overflow-y-auto">
              {searchResults.map((doc) => (
                <div
                  key={doc.id}
                  className="app-surface flex items-center justify-between rounded-lg p-2"
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      <FileText size={14} className="app-text-muted shrink-0" />
                      <span className="truncate text-sm font-medium text-[var(--foreground)]">
                        {doc.title}
                      </span>
                    </div>
                  </div>
                  <button
                    onClick={() => handleAdd(doc.id)}
                    disabled={adding}
                    className="app-action-primary ml-2 rounded-lg px-3 py-1 text-xs font-medium disabled:opacity-50"
                  >
                    Добавить
                  </button>
                </div>
              ))}
            </div>
          )}

          {!searching && searchQuery && searchResults.length === 0 && (
            <p className="app-text-muted mt-3 text-center text-sm">
              Ничего не найдено
            </p>
          )}
        </div>
      )}

      {/* Related Documents List */}
      {relatedDocs.length === 0 ? (
        <p className="app-text-muted py-8 text-center text-sm">
          Нет связанных документов
        </p>
      ) : (
        <div className="space-y-2">
          {relatedDocs.map((doc) => (
            <div
              key={doc.id}
              className="app-surface flex items-center justify-between rounded-lg p-3 hover:bg-[var(--surface-secondary)]"
            >
              <div className="flex-1 min-w-0">
                <div className="flex items-center gap-2">
                  <FileText size={14} className="app-text-muted shrink-0" />
                  <button
                    onClick={() => onNavigate?.(doc.id)}
                    className="app-link-accent truncate text-sm font-medium hover:underline"
                  >
                    {doc.title}
                  </button>
                  {doc.file_name && (
                    <span className="app-text-muted shrink-0 text-xs">
                      ({doc.file_name})
                    </span>
                  )}
                </div>
                <div className="mt-1 flex items-center gap-2">
                  <span className="app-text-muted text-xs">
                    {new Date(doc.created_at).toLocaleDateString("ru-RU")}
                  </span>
                </div>
              </div>
              <button
                onClick={() => handleRemove(doc.id)}
                className="app-action-danger ml-2 rounded p-1"
                title="Удалить связь"
              >
                <X size={16} />
              </button>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
