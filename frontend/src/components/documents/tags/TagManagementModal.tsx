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
          <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-800 text-sm">
            {error}
          </div>
        )}

        {viewMode === 'list' && (
          <div className="space-y-4">
            <div className="flex justify-between items-center">
              <p className="text-sm text-gray-600">
                Всего тегов: <span className="font-semibold">{tags.length}</span>
              </p>
              <button
                onClick={() => setViewMode('create')}
                className="flex items-center gap-2 px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 transition-colors text-sm"
              >
                <Plus className="h-4 w-4" />
                Создать тег
              </button>
            </div>

            {isLoading && tags.length === 0 ? (
              <div className="flex justify-center py-12">
                <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div>
              </div>
            ) : tags.length === 0 ? (
              <div className="text-center py-12">
                <TagIcon className="mx-auto h-12 w-12 text-gray-400" />
                <h3 className="mt-2 text-sm font-medium text-gray-900">Нет тегов</h3>
                <p className="mt-1 text-sm text-gray-500">
                  Создайте первый тег для организации документов
                </p>
              </div>
            ) : (
              <div className="space-y-2 max-h-[60vh] overflow-y-auto">
                {tags.map((tag) => (
                  <div
                    key={tag.id}
                    className="flex items-center justify-between p-3 border border-gray-200 rounded-md hover:bg-gray-50 transition-colors"
                  >
                    <div className="flex items-center gap-3">
                      <div
                        className="w-8 h-8 rounded-md border border-gray-300 flex-shrink-0"
                        style={{ backgroundColor: tag.color }}
                        title={tag.color}
                      />
                      <div className="min-w-0">
                        <p className="font-medium text-gray-900 truncate">{tag.name}</p>
                        <p className="text-xs text-gray-500">
                          ID: {tag.id} • Цвет: {tag.color}
                        </p>
                      </div>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      <button
                        onClick={() => handleEditClick(tag)}
                        disabled={isDeleting === tag.id}
                        className="p-2 text-blue-600 hover:bg-blue-50 rounded-md transition-colors disabled:opacity-50"
                        title="Редактировать"
                      >
                        <Edit2 className="h-4 w-4" />
                      </button>
                      <button
                        onClick={() => handleDeleteTag(tag.id, tag.name)}
                        disabled={isDeleting === tag.id}
                        className="p-2 text-red-600 hover:bg-red-50 rounded-md transition-colors disabled:opacity-50"
                        title="Удалить"
                      >
                        {isDeleting === tag.id ? (
                          <div className="animate-spin h-4 w-4 border-2 border-red-600 border-t-transparent rounded-full" />
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
