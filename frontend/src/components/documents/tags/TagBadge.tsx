'use client';

import { DocumentTag } from '@/types/api';

interface TagBadgeProps {
  tag: DocumentTag;
  onRemove?: () => void;
  size?: 'sm' | 'md' | 'lg';
}

export default function TagBadge({ tag, onRemove, size = 'md' }: TagBadgeProps) {
  const bgColor = tag.color || '#6c757d';
  
  // Определяем, темный ли цвет (для выбора цвета текста)
  const isDark = (color: string) => {
    const hex = color.replace('#', '');
    const r = parseInt(hex.substr(0, 2), 16);
    const g = parseInt(hex.substr(2, 2), 16);
    const b = parseInt(hex.substr(4, 2), 16);
    const brightness = (r * 299 + g * 587 + b * 114) / 1000;
    return brightness < 128;
  };

  const textColor = isDark(bgColor) ? '#fff' : '#000';
  
  const fontSize = size === 'sm' ? '0.75rem' : size === 'lg' ? '1rem' : '0.875rem';
  const padding = size === 'sm' ? '0.25rem 0.5rem' : size === 'lg' ? '0.5rem 0.75rem' : '0.35rem 0.6rem';

  return (
    <span
      className="badge d-inline-flex align-items-center gap-1"
      style={{
        backgroundColor: bgColor,
        color: textColor,
        fontSize,
        padding,
      }}
    >
      {tag.name}
      {onRemove && (
        <button
          type="button"
          className="btn-close btn-close-white opacity-75"
          style={{ fontSize: '0.6rem' }}
          onClick={onRemove}
          aria-label="Удалить тег"
        />
      )}
    </span>
  );
}
