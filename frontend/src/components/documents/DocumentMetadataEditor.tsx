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
          <div className="rounded-lg border border-red-200 bg-red-50 p-3">
            <p className="text-sm text-red-800">{error}</p>
          </div>
        )}

        {/* Document info */}
        <div className="rounded-lg bg-gray-50 p-3">
          <p className="text-sm font-medium text-gray-900">{document.title}</p>
          <p className="mt-1 text-xs text-gray-500">ID: {document.id}</p>
        </div>

        {/* Tags */}
        <div>
          <label className="mb-2 flex items-center gap-2 text-sm font-medium text-gray-700">
            <TagIcon className="h-4 w-4" />
            Теги
          </label>
          {loadingTags ? (
            <div className="flex items-center justify-center rounded-md border border-gray-200 py-8">
              <Loader2 className="h-5 w-5 animate-spin text-gray-400" />
            </div>
          ) : documentTags.length === 0 ? (
            <div className="rounded-md border border-gray-200 bg-gray-50 p-3 text-center text-sm text-gray-500">
              Нет доступных тегов
            </div>
          ) : (
            <div className="max-h-48 space-y-2 overflow-y-auto rounded-md border border-gray-200 bg-white p-3">
              {documentTags.map((tag) => (
                <label
                  key={tag.id}
                  className="flex cursor-pointer items-center gap-2 rounded p-2 transition hover:bg-gray-50"
                >
                  <input
                    type="checkbox"
                    checked={selectedTags.includes(tag.id)}
                    onChange={() => toggleTag(tag.id)}
                    disabled={isSaving}
                    className="h-4 w-4 rounded border-gray-300 text-blue-600 focus:ring-2 focus:ring-blue-100"
                  />
                  <span className="text-sm text-gray-900">{tag.name}</span>
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
          <p className="mt-1 text-xs text-gray-500">
            Выбрано: {selectedTags.length} {selectedTags.length === 1 ? 'тег' : 'тегов'}
          </p>
        </div>

        {/* Folder */}
        <div>
          <label className="mb-2 flex items-center gap-2 text-sm font-medium text-gray-700">
            <Folder className="h-4 w-4" />
            Папка
          </label>
          <select
            value={selectedFolder || ''}
            onChange={(e) => setSelectedFolder(e.target.value ? Number(e.target.value) : null)}
            disabled={loadingFolders || isSaving}
            className="w-full rounded-md border border-gray-300 px-3 py-2 text-sm focus:border-blue-500 focus:outline-none focus:ring-2 focus:ring-blue-100"
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
        <div className="flex items-center justify-end gap-3 border-t pt-4">
          <button
            type="button"
            onClick={onClose}
            disabled={isSaving}
            className="rounded-md border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 transition hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            Отмена
          </button>
          <button
            type="button"
            onClick={handleSave}
            disabled={isSaving}
            className="flex items-center gap-2 rounded-md bg-blue-600 px-4 py-2 text-sm font-medium text-white transition hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
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
