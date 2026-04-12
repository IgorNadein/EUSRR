"use client";

import { useState, useEffect } from "react";
import { Trash2 } from "lucide-react";
import { Modal } from "@/components/ui";
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
    }
  };

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={calendar?.id ? "Редактировать календарь" : "Создать календарь"}
      size="sm"
      footer={
        <div className="flex gap-2">
          <button
            onClick={handleSave}
            disabled={!name.trim() || saving}
            className="app-action-primary flex-1 rounded-lg px-4 py-2.5 text-sm font-medium disabled:cursor-not-allowed disabled:opacity-50"
          >
            {saving ? "Сохранение..." : calendar?.id ? "Сохранить" : "Создать"}
          </button>

          {calendar?.id && (
            <button
              onClick={handleDelete}
              disabled={saving}
              className="app-action-danger rounded-lg px-4 py-2.5 text-sm font-medium disabled:opacity-50"
              title="Удалить календарь"
            >
              <Trash2 size={16} />
            </button>
          )}
        </div>
      }
    >
      <div className="space-y-4">
          {!calendar?.id && (
            <p className="app-text-muted text-sm">
              Создайте календарь для организации событий. Вы сможете добавлять встречи, задачи и напоминания.
            </p>
          )}

          <div>
            <label className="mb-1 block text-sm font-medium text-[var(--foreground)]">
              Название<span className="app-accent-text">*</span>
            </label>
            <input
              type="text"
              value={name}
              onChange={(e) => setName(e.target.value)}
              onKeyDown={handleKeyDown}
              className="app-input w-full rounded-lg px-3 py-2 text-sm"
              placeholder="Например: Рабочий календарь"
              autoFocus
              disabled={saving}
            />
          </div>

      </div>
    </Modal>
  );
}
