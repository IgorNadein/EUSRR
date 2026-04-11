"use client";

import type React from "react";
import Image from "next/image";

import { getChatAvatar, getChatInitials } from "@/lib/messages/chatUtils";
import { resolveMediaUrl } from "@/lib/url";
import type { Chat } from "@/types/api";
import { Modal } from "@/components/ui";

type EditChatModalProps = {
  chat: Chat | null;
  open: boolean;
  currentUserId?: number;
  editName: string;
  editDescription: string;
  editAvatarPreview: string | null;
  actionLoading: string | null;
  onClose: () => void;
  onNameChange: (value: string) => void;
  onDescriptionChange: (value: string) => void;
  onAvatarChange: (event: React.ChangeEvent<HTMLInputElement>) => void;
  onSave: () => void;
};

export default function EditChatModal({
  chat,
  open,
  currentUserId,
  editName,
  editDescription,
  editAvatarPreview,
  actionLoading,
  onClose,
  onNameChange,
  onDescriptionChange,
  onAvatarChange,
  onSave,
}: EditChatModalProps) {
  const footerContent = (
    <div className="flex gap-3">
      <button
        type="button"
        onClick={onClose}
        disabled={actionLoading === "edit"}
        className="app-action-secondary flex-1 rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50"
      >
        Отмена
      </button>
      <button
        type="button"
        onClick={onSave}
        disabled={actionLoading === "edit" || !editName.trim()}
        className="app-action-primary flex-1 rounded-lg px-4 py-2 text-sm font-medium disabled:opacity-50"
      >
        {actionLoading === "edit" ? "Сохранение..." : "Сохранить"}
      </button>
    </div>
  );

  return (
    <Modal isOpen={open && !!chat} onClose={onClose} title="Редактировать чат" size="sm" closeOnEsc={actionLoading !== "edit"} footer={footerContent}>
      {chat && (
        <div className="space-y-4">
          <div>
            <label className="mb-2 block text-sm font-medium text-[var(--foreground)]">Аватар</label>
            <div className="flex items-center gap-4">
              <div className="app-avatar-fallback flex h-16 w-16 items-center justify-center overflow-hidden rounded-full text-lg font-semibold">
                {editAvatarPreview ? (
                  <Image src={editAvatarPreview} alt="Preview" width={64} height={64} unoptimized className="h-full w-full object-cover" />
                ) : getChatAvatar(chat, currentUserId) ? (
                  <Image src={resolveMediaUrl(getChatAvatar(chat, currentUserId)!)} alt="Avatar" width={64} height={64} unoptimized className="h-full w-full object-cover" />
                ) : (
                  getChatInitials(chat, currentUserId)
                )}
              </div>
              <label className="app-action-secondary cursor-pointer rounded-lg px-4 py-2 text-sm font-medium">
                <input type="file" accept="image/*" onChange={onAvatarChange} className="hidden" />
                Загрузить
              </label>
            </div>
            <p className="app-text-muted mt-1 text-xs">Максимальный размер: 5MB. Форматы: JPG, PNG, GIF</p>
          </div>

          <div>
            <label htmlFor="edit-name" className="mb-2 block text-sm font-medium text-[var(--foreground)]">
              Название чата
            </label>
            <input
              id="edit-name"
              type="text"
              value={editName}
              onChange={(event) => onNameChange(event.target.value)}
              placeholder="Введите название чата"
              className="app-input w-full rounded-lg px-4 py-2 text-sm"
              maxLength={100}
            />
          </div>

          <div>
            <label htmlFor="edit-description" className="mb-2 block text-sm font-medium text-[var(--foreground)]">
              Описание
            </label>
            <textarea
              id="edit-description"
              value={editDescription}
              onChange={(event) => onDescriptionChange(event.target.value)}
              placeholder="Введите описание чата (необязательно)"
              rows={3}
              className="app-input w-full rounded-lg px-4 py-2 text-sm"
              maxLength={500}
            />
          </div>
        </div>
      )}
    </Modal>
  );
}
