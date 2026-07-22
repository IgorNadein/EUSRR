'use client';

import { useState } from 'react';
import type { FormEvent } from 'react';
import { Loader2, Plus, X } from 'lucide-react';
import { apiClient } from '@/lib/api';
import { toast } from 'sonner';

export interface QuickDocumentTag {
  id: number;
  name: string;
  color?: string;
}

interface DocumentTagQuickCreateProps {
  existingTags: QuickDocumentTag[];
  disabled?: boolean;
  onCreated: (tag: QuickDocumentTag) => void;
  className?: string;
  layout?: 'disclosure' | 'inline';
}

const TAG_COLORS = ['#3B82F6', '#10B981', '#F59E0B', '#EF4444', '#8B5CF6', '#64748B'];

export function DocumentTagQuickCreate({
  existingTags,
  disabled = false,
  onCreated,
  className = '',
  layout = 'disclosure',
}: DocumentTagQuickCreateProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [name, setName] = useState('');
  const [color, setColor] = useState(TAG_COLORS[0]);
  const [isCreating, setIsCreating] = useState(false);

  const resetForm = () => {
    setName('');
    setColor(TAG_COLORS[0]);
    setIsOpen(false);
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const normalizedName = name.trim();

    if (!normalizedName) {
      toast.error('Введите название тега');
      return;
    }

    const isDuplicate = existingTags.some(
      (tag) => tag.name.trim().toLowerCase() === normalizedName.toLowerCase()
    );
    if (isDuplicate) {
      toast.error('Тег с таким названием уже существует');
      return;
    }

    setIsCreating(true);
    try {
      const created = await apiClient.createDocumentTag({
        name: normalizedName,
        color,
      });
      onCreated(created);
      setName('');
      if (layout === 'disclosure') {
        setColor(TAG_COLORS[0]);
        setIsOpen(false);
      }
      toast.success('Тег создан');
    } catch (error) {
      console.error('Error creating document tag:', error);
      toast.error(error instanceof Error ? error.message : 'Не удалось создать тег');
    } finally {
      setIsCreating(false);
    }
  };

  if (layout === 'inline') {
    return (
      <form
        onSubmit={handleSubmit}
        className={`grid gap-2 md:grid-cols-[auto_1fr_auto] ${className}`}
      >
        <input
          type="color"
          value={color}
          onChange={(event) => setColor(event.target.value)}
          disabled={disabled || isCreating}
          className="h-10 w-14 cursor-pointer rounded-lg border border-[var(--border-subtle)] bg-transparent p-1 disabled:cursor-not-allowed disabled:opacity-50"
          aria-label="Цвет тега"
        />
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={disabled || isCreating}
          maxLength={100}
          className="app-input min-w-0 rounded-xl px-3 py-2 text-sm"
          placeholder="Новый тег"
          aria-label="Название нового тега"
        />
        <button
          type="submit"
          disabled={disabled || isCreating || !name.trim()}
          className="app-action-secondary inline-flex items-center justify-center gap-1.5 rounded-xl px-3 py-2 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isCreating ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
          Добавить
        </button>
      </form>
    );
  }

  if (!isOpen) {
    return (
      <div className={className}>
        <button
          type="button"
          onClick={() => setIsOpen(true)}
          disabled={disabled}
          className="app-action-secondary inline-flex items-center gap-1.5 rounded-lg px-3 py-1.5 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-50"
        >
          <Plus className="h-3.5 w-3.5" />
          Создать тег
        </button>
      </div>
    );
  }

  return (
    <form
      onSubmit={handleSubmit}
      className={`app-surface-muted grid grid-cols-1 gap-3 rounded-lg p-3 sm:grid-cols-[minmax(0,1fr)_auto] ${className}`}
    >
      <div className="min-w-0 space-y-2">
        <input
          value={name}
          onChange={(event) => setName(event.target.value)}
          disabled={disabled || isCreating}
          maxLength={100}
          className="app-input w-full rounded-lg px-3 py-2 text-sm"
          placeholder="Название нового тега"
          autoFocus
        />
        <div className="flex flex-wrap items-center gap-2">
          <input
            type="color"
            value={color}
            onChange={(event) => setColor(event.target.value)}
            disabled={disabled || isCreating}
            className="h-8 w-10 cursor-pointer rounded-lg border border-[var(--border-strong)] bg-transparent p-1 disabled:cursor-not-allowed disabled:opacity-50"
            title="Цвет тега"
          />
          {TAG_COLORS.map((tagColor) => (
            <button
              key={tagColor}
              type="button"
              onClick={() => setColor(tagColor)}
              disabled={disabled || isCreating}
              className={`h-7 w-7 rounded-full border transition disabled:cursor-not-allowed disabled:opacity-50 ${
                color.toLowerCase() === tagColor.toLowerCase()
                  ? 'border-[var(--accent-primary)] ring-2 ring-[color:var(--accent-soft-strong)]'
                  : 'border-[var(--border-strong)]'
              }`}
              style={{ backgroundColor: tagColor }}
              title={tagColor}
              aria-label={`Выбрать цвет ${tagColor}`}
            />
          ))}
        </div>
      </div>

      <div className="flex items-start justify-end gap-2">
        <button
          type="submit"
          disabled={disabled || isCreating || !name.trim()}
          className="app-action-primary inline-flex items-center gap-1.5 rounded-lg px-3 py-2 text-xs font-medium disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isCreating ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Plus className="h-3.5 w-3.5" />}
          Добавить
        </button>
        <button
          type="button"
          onClick={resetForm}
          disabled={isCreating}
          className="app-action-secondary inline-flex h-8 w-8 items-center justify-center rounded-lg disabled:cursor-not-allowed disabled:opacity-50"
          title="Отмена"
        >
          <X className="h-4 w-4" />
        </button>
      </div>
    </form>
  );
}
