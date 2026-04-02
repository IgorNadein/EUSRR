"use client";

import { ChevronDown } from "lucide-react";
import { useEffect, useRef, useState } from "react";

/* ── Single-select dropdown with search ── */
export function SearchableSelectSingle({
  label,
  items,
  selectedId,
  onSelect,
  placeholder,
  disabled = false,
}: {
  label: string;
  items: { id: number; name: string }[];
  selectedId: number | null;
  onSelect: (id: number | null) => void;
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
      <label className="mb-1 block text-xs font-medium text-gray-500">{label}</label>
      <button
        type="button"
        disabled={disabled}
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between rounded-lg border border-gray-300 bg-white px-3 py-2 text-left text-sm text-gray-800 disabled:cursor-not-allowed disabled:bg-gray-50 disabled:text-gray-400"
      >
        <span className="truncate">
          {selectedName || <span className="text-gray-400">{placeholder || "Выбрать..."}</span>}
        </span>
        <ChevronDown size={14} className={`ml-2 shrink-0 text-gray-400 transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="absolute z-50 mt-1 max-h-56 w-full overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg">
          <div className="border-b border-gray-100 p-2">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Поиск..."
              className="w-full rounded border border-gray-200 px-2 py-1.5 text-sm focus:border-sky-400 focus:outline-none"
              autoFocus
            />
          </div>
          <div className="max-h-40 overflow-y-auto p-1">
            {selectedId && (
              <button
                type="button"
                onClick={() => { onSelect(null); setOpen(false); }}
                className="flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm text-gray-400 hover:bg-gray-50"
              >
                Сбросить
              </button>
            )}
            {filtered.length === 0 ? (
              <p className="px-2 py-1.5 text-xs text-gray-400">Ничего не найдено</p>
            ) : (
              filtered.map((item) => (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => { onSelect(item.id); setOpen(false); }}
                  className={`flex w-full items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-gray-50 ${selectedId === item.id ? "bg-sky-50 font-medium text-sky-700" : ""}`}
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
export function SearchableSelectMulti({
  label,
  items,
  selectedIds,
  onToggle,
  placeholder,
}: {
  label: string;
  items: { id: number; name: string }[];
  selectedIds: number[];
  onToggle: (id: number) => void;
  placeholder?: string;
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
  const selectedNames = items.filter((i) => selectedIds.includes(i.id)).map((i) => i.name);

  return (
    <div ref={ref} className="relative">
      <label className="mb-1 block text-xs font-medium text-gray-500">{label}</label>
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full items-center justify-between rounded-lg border border-gray-300 bg-white px-3 py-2 text-left text-sm text-gray-800"
      >
        <span className="truncate">
          {selectedNames.length > 0 ? selectedNames.join(", ") : <span className="text-gray-400">{placeholder || "Выбрать..."}</span>}
        </span>
        <ChevronDown size={14} className={`ml-2 shrink-0 text-gray-400 transition ${open ? "rotate-180" : ""}`} />
      </button>
      {open && (
        <div className="absolute z-50 mt-1 max-h-56 w-full overflow-hidden rounded-lg border border-gray-200 bg-white shadow-lg">
          <div className="border-b border-gray-100 p-2">
            <input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="Поиск..."
              className="w-full rounded border border-gray-200 px-2 py-1.5 text-sm focus:border-sky-400 focus:outline-none"
              autoFocus
            />
          </div>
          <div className="max-h-40 overflow-y-auto p-1">
            {filtered.length === 0 ? (
              <p className="px-2 py-1.5 text-xs text-gray-400">Ничего не найдено</p>
            ) : (
              filtered.map((item) => (
                <label key={item.id} className="flex cursor-pointer items-center gap-2 rounded px-2 py-1.5 text-sm hover:bg-gray-50">
                  <input
                    type="checkbox"
                    checked={selectedIds.includes(item.id)}
                    onChange={() => onToggle(item.id)}
                    className="rounded border-gray-300"
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
