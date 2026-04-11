"use client";

import Image from "next/image";
import { Users } from "lucide-react";

import { getParticipantInitials, type MemberSearchResult } from "@/lib/messages/chatSettingsUtils";
import { getUserFullName } from "@/lib/messages/chatUtils";
import { resolveMediaUrl } from "@/lib/url";
import { Modal } from "@/components/ui";

type AddChatMemberModalProps = {
  open: boolean;
  memberSearchQuery: string;
  memberSearchResults: MemberSearchResult[];
  memberSearchLoading: boolean;
  actionLoading: string | null;
  onClose: () => void;
  onSearchChange: (value: string) => void;
  onAddMember: (userId: number) => void;
};

export default function AddChatMemberModal({
  open,
  memberSearchQuery,
  memberSearchResults,
  memberSearchLoading,
  actionLoading,
  onClose,
  onSearchChange,
  onAddMember,
}: AddChatMemberModalProps) {
  return (
    <Modal isOpen={open} onClose={onClose} title="Добавить участника" size="sm">
      <div className="mb-4">
        <input
          type="text"
          value={memberSearchQuery}
          onChange={(event) => onSearchChange(event.target.value)}
          placeholder="Введите имя или email..."
          className="app-input w-full rounded-lg px-4 py-2 text-sm"
          autoFocus
        />
        <p className="app-text-muted mt-1 text-xs">Минимум 2 символа для поиска</p>
      </div>

      <div className="max-h-96 overflow-y-auto">
        {memberSearchLoading ? (
          <div className="py-8 text-center">
            <div className="mx-auto mb-2 h-6 w-6 animate-spin rounded-full border-2 border-[var(--accent-primary)] border-t-transparent" />
            <p className="app-text-muted text-sm">Поиск...</p>
          </div>
        ) : memberSearchQuery.trim().length < 2 ? (
          <div className="py-8 text-center">
            <Users className="app-text-muted mx-auto mb-2 h-12 w-12 opacity-40" />
            <p className="app-text-muted text-sm">Начните вводить имя или email для поиска</p>
          </div>
        ) : memberSearchResults.length === 0 ? (
          <div className="py-8 text-center">
            <p className="app-text-muted text-sm">Пользователи не найдены</p>
          </div>
        ) : (
          <div className="space-y-2">
            {memberSearchResults.map((result) => (
              <div key={result.id} className="app-surface-elevated flex items-center gap-3 rounded-lg p-3 transition hover:bg-[var(--surface-secondary)]">
                <div className="app-avatar-fallback flex h-10 w-10 items-center justify-center overflow-hidden rounded-full text-sm font-semibold">
                  {result.avatar ? (
                    <Image
                      src={resolveMediaUrl(result.avatar)}
                      alt={result.name || getUserFullName(result.last_name, result.first_name)}
                      width={40}
                      height={40}
                      unoptimized
                      className="h-full w-full object-cover"
                    />
                  ) : (
                    <span>{getParticipantInitials(result.name || getUserFullName(result.last_name, result.first_name))}</span>
                  )}
                </div>
                <div className="flex-1">
                  <p className="text-sm font-medium text-[var(--foreground)]">{result.name || getUserFullName(result.last_name, result.first_name)}</p>
                  {result.email ? <p className="app-text-muted text-xs">{result.email}</p> : null}
                </div>
                <button
                  type="button"
                  onClick={() => onAddMember(result.id)}
                  disabled={actionLoading === `add-member-${result.id}`}
                  className="app-action-primary rounded-lg px-3 py-1.5 text-xs font-medium disabled:opacity-50"
                >
                  {actionLoading === `add-member-${result.id}` ? "..." : "Добавить"}
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </Modal>
  );
}
