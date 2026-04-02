"use client";

import type React from "react";
import Image from "next/image";

import { getChatAvatar, getChatInitials } from "@/lib/messages/chatUtils";
import { resolveMediaUrl } from "@/lib/url";
import type { Chat } from "@/types/api";

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
  if (!open || !chat) return null;

  const avatar = getChatAvatar(chat, currentUserId);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <h2 className="mb-4 text-xl font-bold text-gray-900">Редактировать чат</h2>

        <div className="space-y-4">
          <div>
            <label className="mb-2 block text-sm font-medium text-gray-700">Аватар</label>
            <div className="flex items-center gap-4">
              <div className="flex h-16 w-16 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-lg font-semibold text-white">
                {editAvatarPreview ? (
                  <Image src={editAvatarPreview} alt="Preview" width={64} height={64} unoptimized className="h-full w-full object-cover" />
                ) : avatar ? (
                  <Image src={resolveMediaUrl(avatar)} alt="Avatar" width={64} height={64} unoptimized className="h-full w-full object-cover" />
                ) : (
                  getChatInitials(chat, currentUserId)
                )}
              </div>
              <label className="cursor-pointer rounded-lg border border-gray-300 bg-white px-4 py-2 text-sm font-medium text-gray-700 shadow-sm transition hover:bg-gray-50">
                <input type="file" accept="image/*" onChange={onAvatarChange} className="hidden" />
                Загрузить
              </label>
            </div>
            <p className="mt-1 text-xs text-gray-500">Максимальный размер: 5MB. Форматы: JPG, PNG, GIF</p>
          </div>

          <div>
            <label htmlFor="edit-name" className="mb-2 block text-sm font-medium text-gray-700">
              Название чата
            </label>
            <input
              id="edit-name"
              type="text"
              value={editName}
              onChange={(event) => onNameChange(event.target.value)}
              placeholder="Введите название чата"
              className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
              maxLength={100}
            />
          </div>

          <div>
            <label htmlFor="edit-description" className="mb-2 block text-sm font-medium text-gray-700">
              Описание
            </label>
            <textarea
              id="edit-description"
              value={editDescription}
              onChange={(event) => onDescriptionChange(event.target.value)}
              placeholder="Введите описание чата (необязательно)"
              rows={3}
              className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
              maxLength={500}
            />
          </div>
        </div>

        <div className="mt-6 flex gap-3">
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
            disabled={actionLoading === "edit" || !editName.trim()}
            className="flex-1 rounded-lg bg-sky-600 px-4 py-2 text-sm font-medium text-white shadow-sm transition hover:bg-sky-700 disabled:opacity-50"
          >
            {actionLoading === "edit" ? "Сохранение..." : "Сохранить"}
          </button>
        </div>
      </div>
    </div>
  );
}
