'use client';

import React from 'react';

interface TagColorPickerProps {
  value: string;
  onChange: (color: string) => void;
  label?: string;
}

const PRESET_COLORS = [
  { name: 'Красный', value: '#EF4444' },
  { name: 'Оранжевый', value: '#F97316' },
  { name: 'Желтый', value: '#EAB308' },
  { name: 'Зеленый', value: '#22C55E' },
  { name: 'Бирюзовый', value: '#14B8A6' },
  { name: 'Голубой', value: '#3B82F6' },
  { name: 'Синий', value: '#6366F1' },
  { name: 'Фиолетовый', value: '#A855F7' },
  { name: 'Розовый', value: '#EC4899' },
  { name: 'Серый', value: '#6B7280' },
  { name: 'Темно-серый', value: '#374151' },
  { name: 'Черный', value: '#1F2937' },
];

export const TagColorPicker: React.FC<TagColorPickerProps> = ({
  value,
  onChange,
  label = 'Цвет тега',
}) => {
  return (
    <div className="space-y-2">
      <label className="block text-sm font-medium text-[var(--foreground)]">
        {label}
      </label>
      <div className="grid grid-cols-6 gap-2">
        {PRESET_COLORS.map((color) => (
          <button
            key={color.value}
            type="button"
            onClick={() => onChange(color.value)}
            className={`
              w-10 h-10 rounded-md border-2 transition-all
              hover:scale-110 focus:outline-none focus:shadow-[0_0_0_2px_var(--accent-soft-strong)]
              ${value === color.value ? 'border-[var(--accent-primary)] ring-2 ring-[var(--accent-primary)]' : 'border-[var(--border-strong)]'}
            `}
            style={{ backgroundColor: color.value }}
            title={color.name}
            aria-label={color.name}
          />
        ))}
      </div>
      <div className="flex items-center gap-2 mt-3">
        <label className="app-text-muted text-sm">Свой цвет:</label>
        <input
          type="color"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          className="app-input h-8 w-16 cursor-pointer rounded p-1"
        />
        <span className="app-text-muted font-mono text-xs">{value}</span>
      </div>
    </div>
  );
};
