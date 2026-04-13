"use client";

import { Modal } from "@/components/ui";
import type {
  EmployeeActionField,
  EmployeeActionForm,
} from "@/lib/users/userDetailUtils";

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
  const isSaving = actionLoading === "action";

  const footerContent = (
    <div className="flex gap-3">
      <button
        type="button"
        onClick={onClose}
        disabled={isSaving}
        className="app-action-secondary flex-1 rounded-lg px-4 py-2.5 text-sm font-medium disabled:opacity-50"
      >
        Отмена
      </button>
      <button
        type="button"
        onClick={onSave}
        disabled={isSaving || !form.type || !form.date}
        className="app-action-primary flex-1 rounded-lg px-4 py-2.5 text-sm font-medium disabled:opacity-50"
      >
        {isSaving ? "Сохранение..." : "Сохранить"}
      </button>
    </div>
  );

  return (
    <Modal
      isOpen={isOpen}
      onClose={onClose}
      title={form.editingId ? "Редактировать событие" : "Кадровое событие"}
      size="sm"
      closeOnEsc={!isSaving}
      footer={footerContent}
    >
      <div className="space-y-4">
        <section className="app-surface-muted rounded-xl p-4">
          <label htmlFor="action-type" className="block">
            <span className="mb-2 block text-sm font-medium text-[var(--foreground)]">
              Тип события *
            </span>
            <select
              id="action-type"
              value={form.type}
              onChange={(event) => onFieldChange("type", event.target.value)}
              className="app-select w-full rounded-lg px-4 py-2.5 text-sm"
            >
              <option value="">Выберите тип события</option>
              {actionTypes.map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </label>
        </section>

        <section className="app-surface-muted rounded-xl p-4">
          <label htmlFor="action-date" className="block">
            <span className="mb-2 block text-sm font-medium text-[var(--foreground)]">
              Дата *
            </span>
            <input
              id="action-date"
              type="date"
              value={form.date}
              onChange={(event) => onFieldChange("date", event.target.value)}
              className="app-input w-full rounded-lg px-4 py-2.5 text-sm"
            />
          </label>
        </section>

        <section className="app-surface-muted rounded-xl p-4">
          <label htmlFor="action-comment" className="block">
            <span className="mb-2 block text-sm font-medium text-[var(--foreground)]">
              Комментарий
            </span>
            <textarea
              id="action-comment"
              value={form.comment}
              onChange={(event) => onFieldChange("comment", event.target.value)}
              placeholder="Дополнительная информация..."
              rows={4}
              className="app-input w-full rounded-xl px-4 py-2.5 text-sm"
            />
          </label>
        </section>
      </div>
    </Modal>
  );
}
