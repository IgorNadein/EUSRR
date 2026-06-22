"use client";

import { ChevronDown } from "lucide-react";
import type { ReactNode } from "react";
import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";

type DropdownPosition = {
  left: number;
  maxHeight: number;
  top: number;
  width: number;
};

function getDropdownPosition(anchor: HTMLElement): DropdownPosition {
  const rect = anchor.getBoundingClientRect();
  const gap = 4;
  const viewportPadding = 8;
  const preferredHeight = 224;
  const belowSpace = window.innerHeight - rect.bottom - viewportPadding;
  const aboveSpace = rect.top - viewportPadding;
  const openUp = belowSpace < 180 && aboveSpace > belowSpace;
  const availableHeight = Math.max(120, openUp ? aboveSpace : belowSpace);
  const maxHeight = Math.min(preferredHeight, availableHeight);

  return {
    left: rect.left,
    maxHeight,
    top: openUp ? rect.top - maxHeight - gap : rect.bottom + gap,
    width: rect.width,
  };
}

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
  const [dropdownPosition, setDropdownPosition] = useState<DropdownPosition | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (ref.current?.contains(target) || menuRef.current?.contains(target)) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  useEffect(() => {
    if (!open) return;

    const updatePosition = () => {
      if (ref.current) {
        setDropdownPosition(getDropdownPosition(ref.current));
      }
    };

    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [open]);

  const filtered = items.filter((i) => i.name.toLowerCase().includes(q.toLowerCase()));
  const selectedName = items.find((i) => i.id === selectedId)?.name;
  const toggleOpen = () => {
    if (!open && ref.current) {
      setDropdownPosition(getDropdownPosition(ref.current));
    }
    setOpen((value) => !value);
  };

  return (
    <div ref={ref} className="relative">
      <label className="app-text-muted mb-1 block text-xs font-medium">{label}</label>
      <button
        type="button"
        disabled={disabled}
        onClick={toggleOpen}
        className="app-select flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm disabled:cursor-not-allowed disabled:opacity-60"
      >
        <span className="truncate">
          {selectedName || <span className="app-text-muted">{placeholder || "Выбрать..."}</span>}
        </span>
        <ChevronDown size={14} className={`app-text-muted ml-2 shrink-0 transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open && dropdownPosition && createPortal(
        <div
          ref={menuRef}
          className="app-menu fixed z-[130] overflow-hidden rounded-lg"
          style={{
            left: dropdownPosition.left,
            maxHeight: dropdownPosition.maxHeight,
            top: dropdownPosition.top,
            width: dropdownPosition.width,
          }}
        >
          <div className="app-divider border-b p-2">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Поиск..."
              className="app-input w-full rounded px-2 py-1.5 text-sm"
              autoFocus
            />
          </div>
          <div
            className="overflow-y-auto p-1"
            style={{ maxHeight: Math.max(72, dropdownPosition.maxHeight - 54) }}
          >
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
        </div>,
        document.body,
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
  const [dropdownPosition, setDropdownPosition] = useState<DropdownPosition | null>(null);
  const ref = useRef<HTMLDivElement>(null);
  const menuRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      const target = e.target as Node;
      if (ref.current?.contains(target) || menuRef.current?.contains(target)) return;
      setOpen(false);
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  useEffect(() => {
    if (!open) return;

    const updatePosition = () => {
      if (ref.current) {
        setDropdownPosition(getDropdownPosition(ref.current));
      }
    };

    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
    };
  }, [open]);

  const filtered = items.filter((i) => i.name.toLowerCase().includes(q.toLowerCase()));
  const selectedItems = items.filter((i) => selectedIds.includes(i.id));
  const selectedNames = selectedItems.map((i) => i.name);
  const isInline = layout === "inline";
  const toggleOpen = () => {
    if (!open && ref.current) {
      setDropdownPosition(getDropdownPosition(ref.current));
    }
    setOpen((value) => !value);
  };

  return (
    <div ref={ref} className={`relative ${className}`}>
      {!isInline && <label className="app-text-muted mb-1 block text-xs font-medium">{label}</label>}
      <button
        type="button"
        onClick={toggleOpen}
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
      {open && dropdownPosition && createPortal(
        <div
          ref={menuRef}
          className="app-menu fixed z-[130] overflow-hidden rounded-lg"
          style={{
            left: dropdownPosition.left,
            maxHeight: dropdownPosition.maxHeight,
            top: dropdownPosition.top,
            width: dropdownPosition.width,
          }}
        >
          <div className="app-divider border-b p-2">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Поиск..."
              className="app-input w-full rounded px-2 py-1.5 text-sm"
              autoFocus
            />
          </div>
          <div
            className="overflow-y-auto p-1"
            style={{ maxHeight: Math.max(72, dropdownPosition.maxHeight - 54) }}
          >
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
        </div>,
        document.body,
      )}
    </div>
  );
}
