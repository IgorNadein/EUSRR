"use client";

import Image from "next/image";
import type { ChangeEvent } from "react";

import { Modal } from "@/components/ui";
import type {
  UserProfileEditForm,
  UserProfileTextField,
} from "@/lib/users/userDetailUtils";
import type { User } from "@/types/api";

type EditUserProfileModalProps = {
  actionLoading: string | null;
  avatarFailed: boolean;
  avatarUrl: string | null;
  form: UserProfileEditForm;
  initials: string;
  isOpen: boolean;
  onAvatarChange: (event: ChangeEvent<HTMLInputElement>) => void;
  onClose: () => void;
  onSave: () => void;
  onTextFieldChange: (field: UserProfileTextField, value: string) => void;
  person: User | null;
};

type TextFieldProps = {
  id: string;
  label: string;
  onChange: (value: string) => void;
  placeholder?: string;
  required?: boolean;
  type?: "email" | "tel" | "text";
  value: string;
};

function TextField({
  id,
  label,
  onChange,
  placeholder,
  required = false,
  type = "text",
  value,
}: TextFieldProps) {
  return (
    <label htmlFor={id} className="block">
      <span className="mb-2 block text-sm font-medium text-[var(--foreground)]">
        {label}
        {required ? " *" : ""}
      </span>
      <input
        id={id}
        type={type}
        value={value}
        onChange={(event) => onChange(event.target.value)}
        placeholder={placeholder}
        className="app-input w-full rounded-lg px-4 py-2.5 text-sm"
        maxLength={150}
      />
    </label>
  );
}

export default function EditUserProfileModal({
  actionLoading,
  avatarFailed,
  avatarUrl,
  form,
  initials,
  isOpen,
  onAvatarChange,
  onClose,
  onSave,
  onTextFieldChange,
  person,
}: EditUserProfileModalProps) {
  const isSaving = actionLoading === "edit";

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
        disabled={
          isSaving ||
          !form.firstName.trim() ||
          !form.lastName.trim() ||
          !form.email.trim()
        }
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
      title="Редактировать профиль"
      size="lg"
      closeOnEsc={!isSaving}
      footer={footerContent}
    >
      {person ? (
        <div className="space-y-4">
          <section className="app-surface-muted rounded-xl p-4">
            <div className="flex flex-col gap-4 sm:flex-row sm:items-center">
              <div
                className={`flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-full text-xl font-semibold ${form.avatarPreview || (avatarUrl && !avatarFailed) ? "app-avatar-frame" : "app-avatar-fallback"}`}
              >
                {form.avatarPreview ? (
                  <Image
                    src={form.avatarPreview}
                    alt="Preview"
                    width={80}
                    height={80}
                    className="h-full w-full object-cover"
                    unoptimized
                  />
                ) : avatarUrl && !avatarFailed ? (
                  <Image
                    src={avatarUrl}
                    alt="Avatar"
                    width={80}
                    height={80}
                    className="h-full w-full object-cover"
                    unoptimized
                  />
                ) : (
                  initials
                )}
              </div>

              <div className="min-w-0 flex-1">
                <p className="text-sm font-medium text-[var(--foreground)]">
                  Аватар
                </p>
                <p className="app-text-muted mt-1 text-xs">
                  Максимальный размер: 5MB. Форматы: JPG, PNG, GIF
                </p>
              </div>

              <label className="app-action-secondary inline-flex cursor-pointer items-center justify-center rounded-lg px-4 py-2.5 text-sm font-medium">
                <input
                  type="file"
                  accept="image/*"
                  onChange={onAvatarChange}
                  className="hidden"
                />
                Загрузить
              </label>
            </div>
          </section>

          <section className="app-surface-muted rounded-xl p-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <TextField
                id="edit-last-name"
                label="Фамилия"
                required
                value={form.lastName}
                onChange={(value) => onTextFieldChange("lastName", value)}
                placeholder="Иванов"
              />
              <TextField
                id="edit-first-name"
                label="Имя"
                required
                value={form.firstName}
                onChange={(value) => onTextFieldChange("firstName", value)}
                placeholder="Иван"
              />
              <TextField
                id="edit-patronymic"
                label="Отчество"
                value={form.patronymic}
                onChange={(value) => onTextFieldChange("patronymic", value)}
                placeholder="Иванович"
              />
            </div>
          </section>

          <section className="app-surface-muted rounded-xl p-4">
            <div className="grid gap-4 sm:grid-cols-2">
              <TextField
                id="edit-email"
                label="Email"
                required
                type="email"
                value={form.email}
                onChange={(value) => onTextFieldChange("email", value)}
                placeholder="ivan@example.com"
              />
              <TextField
                id="edit-phone"
                label="Телефон"
                type="tel"
                value={form.phone}
                onChange={(value) => onTextFieldChange("phone", value)}
                placeholder="+7 999 123-45-67"
              />
            </div>
          </section>

          <section className="app-surface-muted rounded-xl p-4">
            <div className="grid gap-4 sm:grid-cols-3">
              <TextField
                id="edit-telegram"
                label="Telegram"
                value={form.telegram}
                onChange={(value) => onTextFieldChange("telegram", value)}
                placeholder="@username"
              />
              <TextField
                id="edit-whatsapp"
                label="WhatsApp"
                type="tel"
                value={form.whatsapp}
                onChange={(value) => onTextFieldChange("whatsapp", value)}
                placeholder="+7 999 123-45-67"
              />
              <TextField
                id="edit-wechat"
                label="WeChat"
                value={form.wechat}
                onChange={(value) => onTextFieldChange("wechat", value)}
                placeholder="username"
              />
            </div>
          </section>
        </div>
      ) : null}
    </Modal>
  );
}
