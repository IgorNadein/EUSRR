'use client';

import React, { useState, useEffect } from 'react';
import { Plus, Edit2, Trash2, Tag as TagIcon } from 'lucide-react';
import { toast } from 'sonner';
import { Modal } from '@/components/ui';
import { TagForm } from './TagForm';
import { apiClient } from '@/lib/api';
import type { DocumentTag } from '@/types/api';

interface TagManagementModalProps {
  isOpen: boolean;
  onClose: () => void;
  onTagsUpdated?: () => void;
}

type ViewMode = 'list' | 'create' | 'edit';

export const TagManagementModal: React.FC<TagManagementModalProps> = ({
  isOpen,
  onClose,
  onTagsUpdated,
}) => {
  const [tags, setTags] = useState<DocumentTag[]>([]);
  const [viewMode, setViewMode] = useState<ViewMode>('list');
  const [selectedTag, setSelectedTag] = useState<DocumentTag | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [isDeleting, setIsDeleting] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (isOpen) {
      loadTags();
    }
  }, [isOpen]);

  const loadTags = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const response = await apiClient.getDocumentTags();
      setTags(response.results || []);
    } catch (err) {
      setError('Не удалось загрузить теги');
      console.error('Error loading tags:', err);
    } finally {
      setIsLoading(false);
    }
  };

  const handleCreateTag = async (data: { name: string; color: string }) => {
    setIsLoading(true);
    setError(null);
    try {
      await apiClient.createDocumentTag(data);
      await loadTags();
      setViewMode('list');
      onTagsUpdated?.();
      toast.success('Тег успешно создан');
    } catch (err: any) {
      const errorMsg = err.response?.data?.name?.[0] || 'Не удалось создать тег';
      setError(errorMsg);
      toast.error(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleUpdateTag = async (data: { name: string; color: string }) => {
    if (!selectedTag) return;
    
    setIsLoading(true);
    setError(null);
    try {
      await apiClient.updateDocumentTag(selectedTag.id, data);
      await loadTags();
      setViewMode('list');
      setSelectedTag(null);
      onTagsUpdated?.();
      toast.success('Тег успешно обновлён');
    } catch (err: any) {
      const errorMsg = err.response?.data?.name?.[0] || 'Не удалось обновить тег';
      setError(errorMsg);
      toast.error(errorMsg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleDeleteTag = async (tagId: number, tagName: string) => {
    if (!confirm(`Вы уверены, что хотите удалить тег "${tagName}"?\n\nТег будет удалён у всех документов, где он используется.`)) {
      return;
    }

    setIsDeleting(tagId);
    setError(null);
    try {
      await apiClient.deleteDocumentTag(tagId);
      await loadTags();
      onTagsUpdated?.();
      toast.success('Тег успешно удалён');
    } catch (err) {
      const errorMsg = 'Не удалось удалить тег';
      setError(errorMsg);
      toast.error(errorMsg);
    } finally {
      setIsDeleting(null);
    }
  };

  const handleEditClick = (tag: DocumentTag) => {
    setSelectedTag(tag);
    setViewMode('edit');
  };

  const handleCancel = () => {
    setViewMode('list');
    setSelectedTag(null);
    setError(null);
  };

  const getTitle = () => {
    if (viewMode === 'list') return 'Управление тегами';
    if (viewMode === 'create') return 'Создание тега';
    return 'Редактирование тега';
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={getTitle()}
      size="lg"
    >
      <div className="space-y-4">
        {error && (
          <div className="app-feedback-danger rounded-md p-3 text-sm">
            {error}
          </div>
        )}

        {viewMode === 'list' && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <p className="app-text-muted text-sm">
                Всего тегов: <span className="font-semibold">{tags.length}</span>
              </p>
              <button
                onClick={() => setViewMode('create')}
                className="app-action-primary flex items-center gap-2 rounded-md px-4 py-2 text-sm"
              >
                <Plus className="h-4 w-4" />
                Создать тег
              </button>
            </div>

            {isLoading && tags.length === 0 ? (
              <div className="flex justify-center py-12">
                <div className="h-8 w-8 animate-spin rounded-full border-b-2 border-[var(--accent-primary)]"></div>
              </div>
            ) : tags.length === 0 ? (
              <div className="text-center py-12">
                <TagIcon className="app-text-muted mx-auto h-12 w-12" />
                <h3 className="mt-2 text-sm font-medium text-[var(--foreground)]">Нет тегов</h3>
                <p className="app-text-muted mt-1 text-sm">
                  Создайте первый тег для организации документов
                </p>
              </div>
            ) : (
              <div className="space-y-2 max-h-[60vh] overflow-y-auto">
                {tags.map((tag) => (
                  <div
                    key={tag.id}
                    className="app-surface-muted flex items-center justify-between rounded-md p-3 transition-colors hover:bg-[var(--surface-elevated)]"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className="h-8 w-8 flex-shrink-0 rounded-md border border-[var(--border-strong)]"
                        style={{ backgroundColor: tag.color }}
                        title={tag.color}
                      />
                      <div className="min-w-0">
                        <p className="truncate font-medium text-[var(--foreground)]">{tag.name}</p>
                        <p className="app-text-muted text-xs">
                          ID: {tag.id} • Цвет: {tag.color}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <button
                        onClick={() => handleEditClick(tag)}
                        disabled={isDeleting === tag.id}
                        className="app-selected app-accent-text rounded-md p-2 transition-colors hover:opacity-90 disabled:opacity-50"
                        title="Редактировать"
                      >
                        <Edit2 className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDeleteTag(tag.id, tag.name)}
                        disabled={isDeleting === tag.id}
                        className="app-action-danger rounded-md p-2 transition-colors disabled:opacity-50"
                        title="Удалить"
                      >
                        {isDeleting === tag.id ? (
                          <div className="h-4 w-4 animate-spin rounded-full border-2 border-[color:#dc2626] border-t-transparent" />
                        ) : (
                          <Trash2 className="h-4 w-4" />
                        )}
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}

        {viewMode === 'create' && (
          <TagForm
            onSubmit={handleCreateTag}
            onCancel={handleCancel}
            isLoading={isLoading}
            existingTags={tags}
          />
        )}

        {viewMode === 'edit' && selectedTag && (
          <TagForm
            tag={selectedTag}
            onSubmit={handleUpdateTag}
            onCancel={handleCancel}
            isLoading={isLoading}
            existingTags={tags}
          />
        )}
      </div>
    </Modal>
  );
};
