"use client";

import { useState, useEffect } from "react";
import { X, Trash2 } from "lucide-react";
import { apiClient } from "@/lib/api";
import { useCalendar } from "@/contexts/CalendarContext";

type Calendar = {
  id?: number;
  name: string;
  slug?: string;
};

type CalendarModalProps = {
  isOpen: boolean;
  onClose: () => void;
  calendar?: Calendar | null;
};

export function CalendarModal({ isOpen, onClose, calendar }: CalendarModalProps) {
  const { reloadCalendars, setSelectedCalendarId } = useCalendar();
  const [name, setName] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (isOpen && calendar) {
      setName(calendar.name);
    } else if (isOpen) {
      setName("");
    }
  }, [isOpen, calendar]);

  if (!isOpen) return null;

  const handleSave = async () => {
    if (!name.trim()) return;

    try {
      setSaving(true);

      if (calendar?.id) {
        // Обновление
        await apiClient.updateCalendar(calendar.id, { name: name.trim() });
      } else {
        // Создание
        const newCal = await apiClient.createCalendar({ name: name.trim() });
        setSelectedCalendarId(newCal.id);
      }

      await reloadCalendars();
      onClose();
    } catch (err) {
      console.error("Ошибка сохранения календаря:", err);
      alert("Не удалось сохранить календарь");
    } finally {
      setSaving(false);
    }
  };

  const handleDelete = async () => {
    if (!calendar?.id || !confirm(`Удалить календарь "${calendar.name}"?`)) return;

    try {
      setSaving(true);
      console.log("Удаление календаря ID:", calendar.id);
      await apiClient.deleteCalendar(calendar.id);
      await reloadCalendars();
      onClose();
    } catch (err) {
      console.error("Ошибка удаления календаря:", err);
      const errorMessage = err instanceof Error ? err.message : "Неизвестная ошибка";
      alert(`Не удалось удалить календарь: ${errorMessage}`);
    } finally {
      setSaving(false);
    }
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSave();
    } else if (e.key === "Escape") {
      onClose();
    }
  };

  return (
    <div className="fixed inset-0 z-[200] flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-gray-900">
            {calendar?.id ? "Редактировать календарь" : "Создать календарь"}
          </h3>
          <button
            onClick={onClose}
            disabled={saving}
            className="rounded-full p-1 hover:bg-gray-100 disabled:opacity-50"
          >
            <X size={20} className="text-gray-600" />
          </button>
        </div>

        <div className="space-y-4">
          {!calendar?.id && (
            <p className="text-sm text-gray-600">
              Создайте календарь для организации событий. Вы сможете добавлять встречи, задачи и напоминания.
            </p>
          )}

          <div>
            <label className="mb-1 block text-sm font-medium text-gray-700">
              Название<span className="text-red-500">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={handleKeyDown}
              className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm outline-none focus:border-sky-500 focus:ring-2 focus:ring-sky-100"
              placeholder="Например: Рабочий календарь"
              autoFocus
              disabled={saving}
            />
          </div>

          <div className="flex gap-2">
            <button
              onClick={handleSave}
              disabled={!name.trim() || saving}
              className="flex-1 rounded-lg bg-sky-500 px-4 py-2.5 text-sm font-medium text-white transition hover:bg-sky-600 disabled:cursor-not-allowed disabled:opacity-50"
            >
              {saving ? "Сохранение..." : calendar?.id ? "Сохранить" : "Создать"}
            </button>

            {calendar?.id && (
              <button
                onClick={handleDelete}
                disabled={saving}
                className="rounded-lg border border-red-200 bg-red-50 px-4 py-2.5 text-sm font-medium text-red-600 transition hover:bg-red-100 disabled:opacity-50"
                title="Удалить календарь"
              >
                <Trash2 size={16} />
              </button>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
