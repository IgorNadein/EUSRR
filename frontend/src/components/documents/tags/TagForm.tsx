'use client';

import React, { useState, useEffect } from 'react';
import { TagColorPicker } from './TagColorPicker';
import type { DocumentTag } from '@/types/api';

interface TagFormProps {
  tag?: DocumentTag | null;
  onSubmit: (data: { name: string; color: string }) => void;
  onCancel: () => void;
  isLoading?: boolean;
  existingTags?: DocumentTag[];
}

export const TagForm: React.FC<TagFormProps> = ({
  tag,
  onSubmit,
  onCancel,
  isLoading = false,
  existingTags = [],
}) => {
  const [name, setName] = useState(tag?.name || '');
  const [color, setColor] = useState(tag?.color || '#3B82F6');
  const [errors, setErrors] = useState<{ name?: string }>({});

  useEffect(() => {
    if (tag) {
      setName(tag.name);
      setColor(tag.color || '#3B82F6');
    }
  }, [tag]);

  const validate = (): boolean => {
    const newErrors: { name?: string } = {};

    if (!name.trim()) {
      newErrors.name = 'Название тега обязательно';
    } else if (name.trim().length < 2) {
      newErrors.name = 'Название должно содержать минимум 2 символа';
    } else if (name.trim().length > 50) {
      newErrors.name = 'Название не должно превышать 50 символов';
    } else {
      // Проверка уникальности (исключая текущий тег при редактировании)
      const isDuplicate = existingTags.some(
        (t) => t.name.toLowerCase() === name.trim().toLowerCase() && t.id !== tag?.id
      );
      if (isDuplicate) {
        newErrors.name = 'Тег с таким названием уже существует';
      }
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (validate()) {
      onSubmit({ name: name.trim(), color });
    }
  };

  return (
    <form onSubmit={handleSubmit} className="space-y-4">
      <div>
        <label htmlFor="tag-name" className="mb-1 block text-sm font-medium text-[var(--foreground)]">
          Название тега <span className="app-accent-text">*</span>
        </label>
        <input
          id="tag-name"
          type="text"
          value={name}
          onChange={(e) => {
            setName(e.target.value);
            if (errors.name) setErrors({ ...errors, name: undefined });
          }}
          className={`
            app-input w-full rounded-md px-3 py-2
            ${errors.name ? 'border-[color:#dc2626]' : ''}
          `}
          placeholder="Введите название тега"
          disabled={isLoading}
          maxLength={50}
          autoFocus
        />
        {errors.name && (
          <p className="mt-1 text-sm text-[color:#dc2626]">{errors.name}</p>
        )}
        <p className="app-text-muted mt-1 text-xs">
          {name.length}/50 символов
        </p>
      </div>

      <TagColorPicker value={color} onChange={setColor} />

      <div className="app-divider flex items-center gap-3 border-t pt-4">
        <button
          type="submit"
          disabled={isLoading || !name.trim()}
          className="app-action-primary rounded-md px-4 py-2 font-medium disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isLoading ? (
            <span className="flex items-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" fill="none" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z" />
              </svg>
              Сохранение...
            </span>
          ) : tag ? (
            'Сохранить изменения'
          ) : (
            'Создать тег'
          )}
        </button>
        <button
          type="button"
          onClick={onCancel}
          disabled={isLoading}
          className="app-action-secondary rounded-md px-4 py-2 font-medium disabled:cursor-not-allowed disabled:opacity-50"
        >
          Отмена
        </button>
      </div>
    </form>
  );
};
