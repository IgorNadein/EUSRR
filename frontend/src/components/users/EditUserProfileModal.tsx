"use client";

import type { ChangeEvent } from "react";
import { Modal } from "@/components/ui";
import type { User } from "@/types/api";
import type { UserProfileEditForm, UserProfileTextField } from "@/lib/users/userDetailUtils";

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
  const footerContent = (
    <div className="flex gap-3">
      <button
        type="button"
        onClick={onClose}
        disabled={actionLoading === "edit"}
        className="flex-1 rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50 disabled:opacity-50"
      >
        Отмена
      </button>
      <button
        type="button"
        onClick={onSave}
        disabled={actionLoading === "edit" || !form.firstName.trim() || !form.lastName.trim() || !form.email.trim()}
        className="flex-1 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-sky-700 disabled:opacity-50"
      >
        {actionLoading === "edit" ? "Сохранение..." : "Сохранить"}
      </button>
    </div>
  );

  return (
    <Modal
      isOpen={isOpen && !!person}
      onClose={onClose}
      title="Редактировать профиль"
      size="lg"
      closeOnEsc={actionLoading !== "edit"}
      footer={footerContent}
    >
      {person && (
        <div className="space-y-4">
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">
              Аватар
            </label>
            <div className="flex items-center gap-4">
              <div className="flex h-20 w-20 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-xl font-semibold text-white">
                {form.avatarPreview ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={form.avatarPreview}
                    alt="Preview"
                    className="h-full w-full object-cover"
                  />
                ) : avatarUrl && !avatarFailed ? (
                  // eslint-disable-next-line @next/next/no-img-element
                  <img
                    src={avatarUrl}
                    alt="Avatar"
                    className="h-full w-full object-cover"
                  />
                ) : (
                  <span>{initials}</span>
                )}
              </div>
              <label className="cursor-pointer rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50">
                <input
                  type="file"
                  accept="image/*"
                  onChange={onAvatarChange}
                  className="hidden"
                />
                Загрузить
              </label>
            </div>
            <p className="mt-1 text-xs text-gray-500">
              Максимальный размер: 5MB. Форматы: JPG, PNG, GIF
            </p>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label htmlFor="edit-last-name" className="mb-2 block text-sm font-medium text-gray-700">
                Фамилия *
              </label>
              <input
                id="edit-last-name"
                type="text"
                value={form.lastName}
                onChange={(event) => onTextFieldChange("lastName", event.target.value)}
                placeholder="Иванов"
                className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                maxLength={150}
              />
            </div>

            <div>
              <label htmlFor="edit-first-name" className="mb-2 block text-sm font-medium text-gray-700">
                Имя *
              </label>
              <input
                id="edit-first-name"
                type="text"
                value={form.firstName}
                onChange={(event) => onTextFieldChange("firstName", event.target.value)}
                placeholder="Иван"
                className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                maxLength={150}
              />
            </div>

            <div>
              <label htmlFor="edit-patronymic" className="mb-2 block text-sm font-medium text-gray-700">
                Отчество
              </label>
              <input
                id="edit-patronymic"
                type="text"
                value={form.patronymic}
                onChange={(event) => onTextFieldChange("patronymic", event.target.value)}
                placeholder="Иванович"
                className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
                maxLength={150}
              />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div>
              <label htmlFor="edit-email" className="mb-2 block text-sm font-medium text-gray-700">
                Email *
              </label>
              <input
                id="edit-email"
                type="email"
                value={form.email}
                onChange={(event) => onTextFieldChange("email", event.target.value)}
                placeholder="ivan@example.com"
                className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
              />
            </div>

            <div>
              <label htmlFor="edit-phone" className="mb-2 block text-sm font-medium text-gray-700">
                Телефон
              </label>
              <input
                id="edit-phone"
                type="tel"
                value={form.phone}
                onChange={(event) => onTextFieldChange("phone", event.target.value)}
                placeholder="+7 999 123-45-67"
                className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
              />
            </div>
          </div>

          <div className="grid gap-4 sm:grid-cols-3">
            <div>
              <label htmlFor="edit-telegram" className="mb-2 block text-sm font-medium text-gray-700">
                Telegram
              </label>
              <input
                id="edit-telegram"
                type="text"
                value={form.telegram}
                onChange={(event) => onTextFieldChange("telegram", event.target.value)}
                placeholder="@username"
                className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
              />
            </div>

            <div>
              <label htmlFor="edit-whatsapp" className="mb-2 block text-sm font-medium text-gray-700">
                WhatsApp
              </label>
              <input
                id="edit-whatsapp"
                type="tel"
                value={form.whatsapp}
                onChange={(event) => onTextFieldChange("whatsapp", event.target.value)}
                placeholder="+7 999 123-45-67"
                className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
              />
            </div>

            <div>
              <label htmlFor="edit-wechat" className="mb-2 block text-sm font-medium text-gray-700">
                WeChat
              </label>
              <input
                id="edit-wechat"
                type="text"
                value={form.wechat}
                onChange={(event) => onTextFieldChange("wechat", event.target.value)}
                placeholder="username"
                className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
              />
            </div>
          </div>
        </div>
      )}
    </Modal>
  );
}