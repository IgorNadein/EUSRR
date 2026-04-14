"use client";

import { Modal } from "@/components/ui";
import type { Position, User } from "@/types/api";

type ChangeUserPositionModalProps = {
  isOpen: boolean;
  onClose: () => void;
  onSave: () => void;
  onPositionChange: (value: string) => void;
  positions: Position[];
  positionsLoading: boolean;
  positionValue: string;
  actionLoading: string | null;
  person: User | null;
  error?: string | null;
};

export default function ChangeUserPositionModal({
  isOpen,
  onClose,
  onSave,
  onPositionChange,
  positions,
  positionsLoading,
  positionValue,
  actionLoading,
  person,
  error,
}: ChangeUserPositionModalProps) {
  const isSaving = actionLoading === "position";

  const footer = (
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
        disabled={isSaving || positionsLoading}
        className="app-action-primary flex-1 rounded-lg px-4 py-2.5 text-sm font-medium disabled:opacity-50"
      >
        {isSaving ? "Сохранение..." : "Сохранить"}
      </button>
    </div>
  );

  return (
    <Modal
      isOpen={isOpen && !!person}
      onClose={onClose}
      title="Изменить должность"
      size="sm"
      closeOnEsc={!isSaving}
      footer={footer}
    >
      <div className="space-y-4">
        <section className="app-surface-muted rounded-xl p-4">
          <div className="mb-3">
            <p className="text-sm font-semibold text-[var(--foreground)]">
              {person?.last_name} {person?.first_name} {person?.patronymic || ""}
            </p>
            <p className="app-text-muted mt-1 text-sm">
              Текущая должность: {person?.position?.name || "Не указана"}
            </p>
          </div>

          <label htmlFor="employee-position" className="block">
            <span className="mb-2 block text-sm font-medium text-[var(--foreground)]">
              Новая должность
            </span>
            <select
              id="employee-position"
              value={positionValue}
              onChange={(event) => onPositionChange(event.target.value)}
              className="app-select w-full rounded-lg px-4 py-2.5 text-sm"
              disabled={positionsLoading || isSaving}
            >
              <option value="">Без должности</option>
              {positions.map((position) => (
                <option key={position.id} value={String(position.id)}>
                  {position.name}
                </option>
              ))}
            </select>
          </label>

          {positionsLoading ? (
            <p className="app-text-muted mt-3 text-sm">Загрузка должностей...</p>
          ) : null}

          {error ? (
            <p className="mt-3 text-sm text-[var(--danger-foreground)]">{error}</p>
          ) : null}
        </section>
      </div>
    </Modal>
  );
}
