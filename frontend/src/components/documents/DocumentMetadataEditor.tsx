'use client';

import React, { useState, useEffect } from 'react';
import { Modal } from '@/components/ui';
import { apiClient } from '@/lib/api';
import { toast } from 'sonner';
import { Folder, Tag as TagIcon, Loader2 } from 'lucide-react';
import type { Document } from '@/types/api';

interface DocumentMetadataEditorProps {
  isOpen: boolean;
  onClose: () => void;
  document: Document;
  onUpdate?: () => void;
}

export function DocumentMetadataEditor({
  isOpen,
  onClose,
  document,
  onUpdate,
}: DocumentMetadataEditorProps) {
  // Form state
  const [selectedTags, setSelectedTags] = useState<number[]>([]);
  const [selectedFolder, setSelectedFolder] = useState<number | null>(document.folder?.id || null);

  // Data lists
  const [documentTags, setDocumentTags] = useState<any[]>([]);
  const [folders, setFolders] = useState<any[]>([]);

  // Loading states
  const [loadingTags, setLoadingTags] = useState(false);
  const [loadingFolders, setLoadingFolders] = useState(false);
  const [isSaving, setIsSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Load current document tags
  useEffect(() => {
    if (isOpen && document) {
      // Load current tags
      if (document.tags && Array.isArray(document.tags)) {
        setSelectedTags(document.tags.map((t: any) => t.id));
      }
    }
  }, [isOpen, document]);

  // Load reference data
  useEffect(() => {
    if (isOpen) {
      loadAllData();
    }
  }, [isOpen]);

  const loadAllData = async () => {
    // Load tags
    try {
      setLoadingTags(true);
      const tagsResponse = await apiClient.getDocumentTags();
      setDocumentTags(tagsResponse.results || tagsResponse);
    } catch (err) {
      console.error('Error loading tags:', err);
    } finally {
      setLoadingTags(false);
    }

    // Load folders
    try {
      setLoadingFolders(true);
      const foldersResponse = await apiClient.getFolders({});
      setFolders(foldersResponse.results || foldersResponse);
    } catch (err) {
      console.error('Error loading folders:', err);
    } finally {
      setLoadingFolders(false);
    }
  };

  const handleSave = async () => {
    setIsSaving(true);
    setError(null);

    try {
      // Prepare update data
      const updateData: any = {};

      // Tags
      const currentTagIds = (document.tags || []).map((t: any) => t.id).sort();
      const newTagIds = [...selectedTags].sort();
      if (JSON.stringify(currentTagIds) !== JSON.stringify(newTagIds)) {
        updateData.tag_ids = selectedTags;
      }

      // Folder
      if (selectedFolder !== (document.folder?.id || null)) {
        updateData.folder = selectedFolder;
      }

      // If nothing changed
      if (Object.keys(updateData).length === 0) {
        toast.info('Нет изменений для сохранения');
        onClose();
        return;
      }

      // Send update request
      await apiClient.updateDocument(document.id, updateData);

      toast.success('Метаданные документа обновлены');
      onUpdate?.();
      onClose();
    } catch (err: any) {
      console.error('Error updating document metadata:', err);
      const errorMsg = err.response?.data?.detail || 'Не удалось обновить метаданные';
      setError(errorMsg);
      toast.error(errorMsg);
    } finally {
      setIsSaving(false);
    }
  };

  const toggleTag = (tagId: number) => {
    setSelectedTags((prev) =>
      prev.includes(tagId) ? prev.filter((id) => id !== tagId) : [...prev, tagId]
    );
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title="Редактирование метаданных"
      size="lg"
    >
      <div className="space-y-4">
        {error && (
          <div className="app-feedback-danger rounded-lg p-3">
            <p className="text-sm">{error}</p>
          </div>
        )}

        {/* Document info */}
        <div className="app-surface-muted rounded-lg p-3">
          <p className="text-sm font-medium text-[var(--foreground)]">{document.title}</p>
          <p className="app-text-muted mt-1 text-xs">ID: {document.id}</p>
        </div>

        {/* Tags */}
        <div>
          <label className="mb-2 flex items-center gap-2 text-sm font-medium text-[var(--foreground)]">
            <TagIcon className="h-4 w-4" />
            Теги
          </label>
          {loadingTags ? (
            <div className="app-surface flex items-center justify-center rounded-md py-8">
              <Loader2 className="app-text-muted h-5 w-5 animate-spin" />
            </div>
          ) : documentTags.length === 0 ? (
            <div className="app-surface-muted app-text-muted rounded-md p-3 text-center text-sm">
              Нет доступных тегов
            </div>
          ) : (
            <div className="app-surface max-h-48 space-y-2 overflow-y-auto rounded-md p-3">
              {documentTags.map((tag) => (
                <label
                  key={tag.id}
                  className="flex cursor-pointer items-center gap-2 rounded p-2 transition hover:bg-[var(--surface-secondary)]"
                >
                  <input
                    type="checkbox"
                    checked={selectedTags.includes(tag.id)}
                    onChange={() => toggleTag(tag.id)}
                    disabled={isSaving}
                    className="h-4 w-4 rounded border-[var(--border-strong)] text-[var(--accent-primary)]"
                  />
                  <span className="text-sm text-[var(--foreground)]">{tag.name}</span>
                  {tag.color && (
                    <span
                      className="ml-auto h-3 w-3 rounded-full"
                      style={{ backgroundColor: tag.color }}
                    />
                  )}
                </label>
              ))}
            </div>
          )}
          <p className="app-text-muted mt-1 text-xs">
            Выбрано: {selectedTags.length} {selectedTags.length === 1 ? 'тег' : 'тегов'}
          </p>
        </div>

        {/* Folder */}
        <div>
          <label className="mb-2 flex items-center gap-2 text-sm font-medium text-[var(--foreground)]">
            <Folder className="h-4 w-4" />
            Папка
          </label>
          <select
            value={selectedFolder || ''}
            onChange={(e) => setSelectedFolder(e.target.value ? Number(e.target.value) : null)}
            disabled={loadingFolders || isSaving}
            className="app-select w-full rounded-md px-3 py-2 text-sm"
          >
            <option value="">Без папки (корень)</option>
            {folders.map((folder) => (
              <option key={folder.id} value={folder.id}>
                {folder.name}
              </option>
            ))}
          </select>
        </div>

        {/* Actions */}
        <div className="app-divider flex items-center justify-end gap-3 border-t pt-4">
          <button
            type="button"
            onClick={onClose}
            disabled={isSaving}
            className="app-action-secondary rounded-md px-4 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50"
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={isSaving}
            className="app-action-primary flex items-center gap-2 rounded-md px-4 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSaving ? (
              <>
                <Loader2 className="h-4 w-4 animate-spin" />
                Сохранение...
              </>
            ) : (
              'Сохранить изменения'
            )}
          </button>
        </div>
      </div>
    </Modal>
  );
}
