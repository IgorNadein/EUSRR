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
        <label htmlFor="tag-name" className="block text-sm font-medium text-gray-700 mb-1">
          Название тега <span className="text-red-500">*</span>
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
            w-full px-3 py-2 border rounded-md shadow-sm
            focus:outline-none focus:ring-2 focus:ring-blue-500
            ${errors.name ? 'border-red-500' : 'border-gray-300'}
          `}
          placeholder="Введите название тега"
          disabled={isLoading}
          maxLength={50}
          autoFocus
        />
        {errors.name && (
          <p className="mt-1 text-sm text-red-600">{errors.name}</p>
        )}
        <p className="mt-1 text-xs text-gray-500">
          {name.length}/50 символов
        </p>
      </div>

      <TagColorPicker value={color} onChange={setColor} />

      <div className="flex items-center gap-3 pt-4 border-t">
        <button
          type="submit"
          disabled={isLoading || !name.trim()}
          className="
            px-4 py-2 bg-blue-600 text-white rounded-md font-medium
            hover:bg-blue-700 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
            disabled:opacity-50 disabled:cursor-not-allowed
            transition-colors
          "
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
          className="
            px-4 py-2 bg-white border border-gray-300 text-gray-700 rounded-md font-medium
            hover:bg-gray-50 focus:outline-none focus:ring-2 focus:ring-blue-500 focus:ring-offset-2
            disabled:opacity-50 disabled:cursor-not-allowed
            transition-colors
          "
        >
          Отмена
        </button>
      </div>
    </form>
  );
};
