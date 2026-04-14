"use client";

import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";

/* ── Single-select dropdown with search ── */
export function SearchableSelectSingle<T extends string | number>({
  label,
  items,
  selectedId,
  onSelect,
  placeholder,
  disabled = false,
}: {
  label: string;
  items: { id: T; name: string }[];
  selectedId: T | null;
  onSelect: (id: T | null) => void;
  placeholder?: string;
  disabled?: boolean;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = items.filter((i) => i.name.toLowerCase().includes(q.toLowerCase()));
  const selectedName = items.find((i) => i.id === selectedId)?.name;

  return (
    <div ref={ref} className="relative">
      <label className="app-text-muted mb-1 block text-xs font-medium">{label}</label>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className="app-select flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm disabled:cursor-not-allowed disabled:opacity-60"
      >
        <span className="truncate">
          {selectedName || <span className="app-text-muted">{placeholder || "Выбрать..."}</span>}
        </span>
        <ChevronDown size={14} className={`app-text-muted ml-2 shrink-0 transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="app-menu absolute z-50 mt-1 max-h-56 w-full overflow-hidden rounded-lg">
          <div className="app-divider border-b p-2">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Поиск..."
              className="app-input w-full rounded px-2 py-1.5 text-sm"
              autoFocus
            />
          </div>
          <div className="max-h-40 overflow-y-auto p-1">
            {selectedId !== null && (
              <button
                type="button"
                onClick={() => { onSelect(null); setOpen(false); }}
                className="app-text-muted hover:app-surface-muted flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm"
              >
                Сбросить
              </button>
            )}
            {filtered.length === 0 ? (
              <p className="app-text-muted px-2 py-1.5 text-xs">Ничего не найдено</p>
            ) : (
              filtered.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => { onSelect(item.id); setOpen(false); }}
                  className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm ${selectedId === item.id ? "app-selected app-accent-text font-medium" : "hover:bg-[var(--surface-secondary)]"}`}
                >
                  {item.name}
                </button>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}

/* ── Multi-select dropdown with search ── */
export function SearchableSelectMulti<T extends { id: number; name: string }>({
  label,
  items,
  selectedIds,
  onToggle,
  placeholder,
  layout = "stacked",
  className = "",
  renderSelectedItem,
}: {
  label: string;
  items: T[];
  selectedIds: number[];
  onToggle: (id: number) => void;
  placeholder?: string;
  layout?: "stacked" | "inline";
  className?: string;
  renderSelectedItem?: (item: T) => ReactNode;
}) {
  const [open, setOpen] = useState(false);
  const [q, setQ] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const filtered = items.filter((i) => i.name.toLowerCase().includes(q.toLowerCase()));
  const selectedItems = items.filter((i) => selectedIds.includes(i.id));
  const selectedNames = selectedItems.map((i) => i.name);
  const isInline = layout === "inline";

  return (
    <div ref={ref} className={`relative ${className}`}>
      {!isInline && <label className="app-text-muted mb-1 block text-xs font-medium">{label}</label>}
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className={isInline
          ? "app-input flex w-full items-start gap-3 rounded-2xl px-3 py-3 text-left text-sm"
          : "app-select flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm"}
      >
        {isInline ? (
          <>
            <span className="app-text-muted w-14 shrink-0 pt-0.5 text-sm font-medium">{label}</span>
            <span className="flex min-w-0 flex-1 flex-wrap gap-1.5">
              {selectedItems.length > 0 ? selectedItems.map((item) => (
                renderSelectedItem ? (
                  <span key={item.id} className="min-w-0 max-w-full">
                    {renderSelectedItem(item)}
                  </span>
                ) : (
                  <span key={item.id} className="app-badge inline-flex max-w-full items-center rounded-full px-2.5 py-1 text-xs font-medium">
                    <span className="truncate">{item.name}</span>
                  </span>
                )
              )) : <span className="app-text-muted py-0.5">{placeholder || "Выбрать..."}</span>}
            </span>
          </>
        ) : (
          <span className="truncate">
            {selectedNames.length > 0 ? selectedNames.join(", ") : <span className="app-text-muted">{placeholder || "Выбрать..."}</span>}
          </span>
        )}
        <ChevronDown size={14} className={`app-text-muted ${isInline ? "mt-1" : "ml-2"} shrink-0 transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className={`app-menu absolute z-50 mt-1 max-h-56 overflow-hidden rounded-lg ${isInline ? "inset-x-0" : "w-full"}`}>
          <div className="app-divider border-b p-2">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Поиск..."
              className="app-input w-full rounded px-2 py-1.5 text-sm"
              autoFocus
            />
          </div>
          <div className="max-h-40 overflow-y-auto p-1">
            {filtered.length === 0 ? (
              <p className="app-text-muted px-2 py-1.5 text-xs">Ничего не найдено</p>
            ) : (
              filtered.map((item) => (
                <label key={item.id} className={`flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm ${selectedIds.includes(item.id) ? "app-selected" : "hover:bg-[var(--surface-secondary)]"}`}>
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(item.id)}
                    onChange={() => onToggle(item.id)}
                    className="rounded border-[var(--border-strong)]"
                  />
                  <span className="truncate">{item.name}</span>
                </label>
              ))
            )}
          </div>
        </div>
      )}
    </div>
  );
}
