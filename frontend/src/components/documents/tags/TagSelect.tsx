'use client';

import { useState, useEffect } from 'react';
import { DocumentTag } from '@/types/api';
import { apiClient } from '@/lib/api';
import TagBadge from './TagBadge';

interface TagSelectProps {
  selectedTags: DocumentTag[];
  onChange: (tags: DocumentTag[]) => void;
  maxTags?: number;
}

export default function TagSelect({ selectedTags, onChange, maxTags }: TagSelectProps) {
  const [allTags, setAllTags] = useState<DocumentTag[]>([]);
  const [loading, setLoading] = useState(false);
  const [showDropdown, setShowDropdown] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadTags();
  }, []);

  const loadTags = async () => {
    try {
      setLoading(true);
      setError(null);
      const response = await apiClient.getDocumentTags();
      setAllTags(response.results || response);
    } catch (err: any) {
      setError(err.message || 'Ошибка загрузки тегов');
      console.error('Failed to load tags:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleAddTag = (tag: DocumentTag) => {
    if (maxTags && selectedTags.length >= maxTags) {
      alert(`Максимум ${maxTags} тегов`);
      return;
    }
    
    if (!selectedTags.find(t => t.id === tag.id)) {
      onChange([...selectedTags, tag]);
    }
    setSearchQuery('');
    setShowDropdown(false);
  };

  const handleRemoveTag = (tagId: number) => {
    onChange(selectedTags.filter(t => t.id !== tagId));
  };

  const filteredTags = allTags.filter(
    tag =>
      !selectedTags.find(t => t.id === tag.id) &&
      tag.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  return (
    <div className="tag-select">
      {/* Выбранные теги */}
      {selectedTags.length > 0 && (
        <div className="selected-tags mb-2 d-flex flex-wrap gap-2">
          {selectedTags.map(tag => (
            <TagBadge
              key={tag.id}
              tag={tag}
              onRemove={() => handleRemoveTag(tag.id)}
            />
          ))}
        </div>
      )}

      {/* Поле поиска */}
      <div className="position-relative">
        <input
          type="text"
          className="form-control"
          placeholder="Поиск или добавление тегов..."
          value={searchQuery}
          onChange={e => {
            setSearchQuery(e.target.value);
            setShowDropdown(true);
          }}
          onFocus={() => setShowDropdown(true)}
        />

        {/* Выпадающий список */}
        {showDropdown && (
          <>
            <div
              className="position-fixed top-0 start-0 w-100 h-100"
              style={{ zIndex: 1040 }}
              onClick={() => setShowDropdown(false)}
            />
            <div
              className="dropdown-menu show w-100 mt-1"
              style={{ maxHeight: '200px', overflowY: 'auto', zIndex: 1050 }}
            >
              {loading && (
                <div className="dropdown-item text-center">
                  <span className="spinner-border spinner-border-sm" role="status"></span>
                </div>
              )}

              {error && (
                <div className="dropdown-item text-danger">{error}</div>
              )}

              {!loading && !error && filteredTags.length === 0 && (
                <div className="dropdown-item text-muted">
                  {searchQuery ? 'Теги не найдены' : 'Нет доступных тегов'}
                </div>
              )}

              {!loading && !error && filteredTags.map(tag => (
                <button
                  key={tag.id}
                  type="button"
                  className="dropdown-item d-flex align-items-center justify-content-between"
                  onClick={() => handleAddTag(tag)}
                >
                  <span>{tag.name}</span>
                  <small className="text-muted">{tag.documents_count} док.</small>
                </button>
              ))}
            </div>
          </>
        )}
      </div>

      {maxTags && (
        <small className="text-muted">
          Выбрано {selectedTags.length} из {maxTags}
        </small>
      )}
    </div>
  );
}
