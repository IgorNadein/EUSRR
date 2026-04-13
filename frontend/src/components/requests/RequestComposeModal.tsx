"use client";

import { Modal } from "@/components/ui";
import { SearchableSelectMulti, SearchableSelectSingle } from "@/components/shared/SearchableSelect";
import {
  getRequestDateMode,
  requestTypeLabels,
  type RequestAttachmentPreview,
  type RequestFormState,
} from "@/hooks/useRequestsPage";
import { displayUserName } from "@/lib/shared";
import type { Request, User } from "@/types/api";
import { Paperclip, X } from "lucide-react";
import {
  useMemo,
  useRef,
  useState,
  type ChangeEvent,
  type Dispatch,
  type SetStateAction,
} from "react";

type RequestComposeModalProps = {
  actionError: string | null;
  busyKey: string | null;
  currentUserId?: number | null;
  editingRequest: Request | null;
  employees: User[];
  form: RequestFormState;
  mode: "create" | "edit";
  onClose: () => void;
  onPreviewAttachment: (preview: RequestAttachmentPreview) => void;
  onSubmit: (mode: "create" | "edit", saveAs: "draft" | "submit") => void | Promise<void>;
  setForm: Dispatch<SetStateAction<RequestFormState>>;
};

const allowedAttachmentExtensions = new Set(["pdf", "jpg", "jpeg", "png"]);

function FieldLabel({
  children,
  required = false,
}: {
  children: string;
  required?: boolean;
}) {
  return (
    <label className="app-text-muted mb-1.5 block text-xs font-medium">
      {children}
      {required ? <span className="app-accent-text"> *</span> : null}
    </label>
  );
}

export function RequestComposeModal({
  actionError,
  busyKey,
  currentUserId,
  editingRequest,
  employees,
  form,
  mode,
  onClose,
  onPreviewAttachment,
  onSubmit,
  setForm,
}: RequestComposeModalProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [showCcField, setShowCcField] = useState(() => form.cc_user_ids.length > 0);

  const selectableEmployees = useMemo(
    () => employees
      .filter((employee) => !currentUserId || employee.id !== currentUserId)
      .map((employee) => ({ id: employee.id, name: displayUserName(employee) })),
    [currentUserId, employees],
  );

  const dateMode = getRequestDateMode(form.type);
  const showOptionalDates = dateMode === "optional" && Boolean(form.date_from || form.date_to);
  const existingAttachmentUrl = editingRequest?.attachment_url || editingRequest?.attachment || "";
  const existingAttachmentName = existingAttachmentUrl
    ? decodeURIComponent(existingAttachmentUrl.split("/").pop() || "Вложение")
    : "";

  const toggleSelection = (field: "recipient_ids" | "cc_user_ids", id: number) => {
    setForm((prev) => ({
      ...prev,
      [field]: prev[field].includes(id)
        ? prev[field].filter((item) => item !== id)
        : [...prev[field], id],
    }));
  };

  const handleAttachmentChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0] || null;
    if (file) {
      const extension = file.name.split(".").pop()?.toLowerCase() || "";
      if (!allowedAttachmentExtensions.has(extension)) {
        event.target.value = "";
        return;
      }
    }
    setForm((prev) => ({ ...prev, attachment: file }));
  };

  return (
    <Modal
      isOpen
      onClose={onClose}
      title={mode === "create" ? "Новое заявление" : "Редактировать заявление"}
      size="lg"
      className="h-[100dvh] max-w-full rounded-none sm:h-auto sm:rounded-2xl"
      footer={(
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          
          <div className="flex flex-wrap items-center justify-end gap-2">
            <button
              type="button"
              onClick={onClose}
              className="app-action-secondary rounded-lg px-4 py-2.5 text-sm font-medium"
            >
              Отмена
            </button>
            <button
              type="button"
              onClick={() => void onSubmit(mode, "draft")}
              disabled={busyKey !== null}
              className="app-action-secondary rounded-lg px-4 py-2.5 text-sm font-medium disabled:opacity-60"
            >
              {mode === "create" ? "Сохранить черновик" : "Сохранить как черновик"}
            </button>
            <button
              type="button"
              onClick={() => void onSubmit(mode, "submit")}
              disabled={busyKey !== null}
              className="app-action-primary rounded-lg px-4 py-2.5 text-sm font-medium disabled:opacity-60"
            >
              Отправить
            </button>
          </div>
        </div>
      )}
    >
      {actionError && (
        <p className="app-feedback-danger mb-4 rounded-xl px-4 py-3 text-sm">
          {actionError}
        </p>
      )}

      <div className="space-y-4 pb-2">
        <section className="app-surface-muted rounded-xl p-3 sm:p-4">
          <div className="grid gap-3 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
            <SearchableSelectSingle
              label="Тип заявления *"
              placeholder="Выберите тип"
              items={Object.entries(requestTypeLabels).map(([value, label]) => ({ id: value, name: label }))}
              selectedId={form.type || null}
              onSelect={(value) => setForm((prev) => ({
                ...prev,
                type: typeof value === "string" ? value : "",
                date_from: "",
                date_to: "",
              }))}
            />

            <div className="space-y-1.5">
              <div className="flex items-center justify-between gap-2">
                <span className="app-text-muted block text-xs font-medium">
                  {dateMode === "range" ? "Период" : "Дата"}
                  {dateMode !== "optional" ? <span className="app-accent-text"> *</span> : null}
                </span>
                {dateMode === "optional" && !showOptionalDates && (
                  <span className="app-text-muted text-[11px]">Даты не обязательны для этого типа</span>
                )}
              </div>

              {dateMode === "range" ? (
                <div className="grid gap-2 sm:grid-cols-2">
                  <input
                    type="date"
                    value={form.date_from}
                    onChange={(event) => setForm((prev) => ({ ...prev, date_from: event.target.value }))}
                    className="app-input rounded-lg px-4 py-3 text-sm"
                  />
                  <input
                    type="date"
                    value={form.date_to}
                    onChange={(event) => setForm((prev) => ({ ...prev, date_to: event.target.value }))}
                    className="app-input rounded-lg px-4 py-3 text-sm"
                  />
                </div>
              ) : dateMode === "single" ? (
                <input
                  type="date"
                  value={form.date_from}
                  onChange={(event) => setForm((prev) => ({ ...prev, date_from: event.target.value }))}
                  className="app-input w-full rounded-lg px-4 py-3 text-sm"
                />
              ) : showOptionalDates ? (
                <div className="grid gap-2 sm:grid-cols-2">
                  <input
                    type="date"
                    value={form.date_from}
                    onChange={(event) => setForm((prev) => ({ ...prev, date_from: event.target.value }))}
                    className="app-input rounded-lg px-4 py-3 text-sm"
                  />
                  <input
                    type="date"
                    value={form.date_to}
                    onChange={(event) => setForm((prev) => ({ ...prev, date_to: event.target.value }))}
                    className="app-input rounded-lg px-4 py-3 text-sm"
                  />
                </div>
              ) : (
                <button
                  type="button"
                  onClick={() => setForm((prev) => ({
                    ...prev,
                    date_from: prev.date_from || new Date().toISOString().slice(0, 10),
                  }))}
                  className="app-action-secondary rounded-lg px-4 py-3 text-sm font-medium"
                >
                  Добавить дату
                </button>
              )}
            </div>
          </div>

          <div className="mt-3 rounded-lg border border-[var(--border-subtle)] bg-[var(--surface-primary)] p-3">
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-[var(--foreground)]">Вложение</p>
                <p className="app-text-muted mt-1 text-xs">
                  Прикрепите подтверждающий файл, если он нужен для заявления.
                </p>
              </div>
              <div className="flex flex-wrap items-center gap-2">
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".pdf,.jpg,.jpeg,.png"
                  className="hidden"
                  onChange={handleAttachmentChange}
                />
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className="app-action-secondary inline-flex items-center gap-2 rounded-lg px-3.5 py-2.5 text-sm font-medium"
                >
                  <Paperclip size={14} />
                  {form.attachment ? "Заменить файл" : "Прикрепить файл"}
                </button>
              </div>
            </div>

            {(form.attachment || existingAttachmentUrl) && (
              <div className="mt-3 flex flex-wrap items-center gap-2">
                {existingAttachmentUrl && !form.attachment && (
                  <button
                    type="button"
                    onClick={() => onPreviewAttachment({ url: existingAttachmentUrl, name: existingAttachmentName })}
                    className="app-badge app-badge-accent inline-flex max-w-full items-center gap-2 px-3 py-1.5 text-xs font-medium"
                  >
                    <Paperclip size={13} className="shrink-0" />
                    <span className="truncate">{existingAttachmentName}</span>
                  </button>
                )}

                {form.attachment && (
                  <span className="app-badge app-badge-accent inline-flex max-w-full items-center gap-2 px-3 py-1.5 text-xs font-medium">
                    <Paperclip size={13} className="shrink-0" />
                    <span className="truncate">{form.attachment.name}</span>
                    <button
                      type="button"
                      onClick={() => {
                        setForm((prev) => ({ ...prev, attachment: null }));
                        if (fileInputRef.current) fileInputRef.current.value = "";
                      }}
                      className="rounded-full p-0.5 transition hover:bg-[var(--accent-soft)]"
                      aria-label="Убрать файл"
                    >
                      <X size={12} />
                    </button>
                  </span>
                )}
              </div>
            )}
          </div>
        </section>

        <section className="app-surface-muted rounded-xl p-3 sm:p-4">
          <div className="mb-3 flex items-center justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-[var(--foreground)]">Адресация</p>
              <p className="app-text-muted text-xs">Решение принимает только пользователь из поля «Кому».</p>
            </div>
            {!showCcField && (
              <button
                type="button"
                onClick={() => setShowCcField(true)}
                className="app-link-accent text-xs font-medium"
              >
                Добавить копию
              </button>
            )}
          </div>

          <div className="space-y-2">
            <SearchableSelectMulti
              label="Кому *"
              layout="inline"
              placeholder="Добавьте получателей"
              items={selectableEmployees}
              selectedIds={form.recipient_ids}
              onToggle={(id) => toggleSelection("recipient_ids", id)}
            />
            {showCcField && (
              <SearchableSelectMulti
                label="Копия"
                layout="inline"
                placeholder="Добавьте пользователей в копию"
                items={selectableEmployees}
                selectedIds={form.cc_user_ids}
                onToggle={(id) => toggleSelection("cc_user_ids", id)}
              />
            )}
          </div>
        </section>

        <div className="space-y-3">
          <div>
            <FieldLabel>Тема</FieldLabel>
            <input
              value={form.title}
              onChange={(event) => setForm((prev) => ({ ...prev, title: event.target.value }))}
              placeholder="Например: Отпуск с 12 по 16 августа"
              className="app-input w-full rounded-lg px-4 py-3 text-sm"
            />
          </div>

          <div>
            <FieldLabel>Сообщение</FieldLabel>
            <textarea
              value={form.comment}
              onChange={(event) => setForm((prev) => ({ ...prev, comment: event.target.value }))}
              placeholder="Кратко опишите заявление. Для черновика можно оставить поле пустым."
              rows={8}
              className="app-input min-h-44 w-full rounded-lg px-4 py-3 text-sm leading-6"
            />
          </div>
        </div>
      </div>
    </Modal>
  );
}
