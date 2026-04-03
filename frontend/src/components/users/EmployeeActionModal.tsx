"use client";

import { Modal } from "@/components/ui";
import type { EmployeeActionField, EmployeeActionForm } from "@/lib/users/userDetailUtils";

type EmployeeActionOption = {
  value: string;
  label: string;
};

type EmployeeActionModalProps = {
  actionLoading: string | null;
  actionTypes: readonly EmployeeActionOption[];
  form: EmployeeActionForm;
  isOpen: boolean;
  onClose: () => void;
  onFieldChange: (field: EmployeeActionField, value: string) => void;
  onSave: () => void;
};

export default function EmployeeActionModal({
  actionLoading,
  actionTypes,
  form,
  isOpen,
  onClose,
  onFieldChange,
  onSave,
}: EmployeeActionModalProps) {
  const footerContent = (
    <div className="flex gap-3">
      <button
        type="button"
        onClick={onClose}
        disabled={actionLoading === "action"}
        className="flex-1 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:opacity-50"
      >
        Отмена
      </button>
      <button
        type="button"
        onClick={onSave}
        disabled={actionLoading === "action" || !form.type || !form.date}
        className="flex-1 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-sky-700 disabled:opacity-50"
      >
        {actionLoading === "action" ? "Сохранение..." : "Сохранить"}
      </button>
    </div>
  );

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={form.editingId ? "Редактировать событие" : "Кадровое событие"}
      size="sm"
      closeOnEsc={actionLoading !== "action"}
      footer={footerContent}
    >
      <div className="space-y-4">
        <div>
          <label htmlFor="action-type" className="mb-2 block text-sm font-medium text-gray-700">
            Тип события *
          </label>
          <select
            id="action-type"
            value={form.type}
            onChange={(event) => onFieldChange("type", event.target.value)}
            className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
          >
            <option value="">Выберите тип события</option>
            {actionTypes.map((type) => (
              <option key={type.value} value={type.value}>
                {type.label}
              </option>
            ))}
          </select>
        </div>

        <div>
          <label htmlFor="action-date" className="mb-2 block text-sm font-medium text-gray-700">
            Дата *
          </label>
          <input
            id="action-date"
            type="date"
            value={form.date}
            onChange={(event) => onFieldChange("date", event.target.value)}
            className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
          />
        </div>

        <div>
          <label htmlFor="action-comment" className="mb-2 block text-sm font-medium text-gray-700">
            Комментарий
          </label>
          <textarea
            id="action-comment"
            value={form.comment}
            onChange={(event) => onFieldChange("comment", event.target.value)}
            placeholder="Дополнительная информация..."
            rows={3}
            className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
          />
        </div>
      </div>
    </Modal>
  );
}