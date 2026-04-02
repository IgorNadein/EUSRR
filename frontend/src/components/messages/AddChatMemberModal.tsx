"use client";

import Image from "next/image";
import { Users } from "lucide-react";

import { getParticipantInitials, type MemberSearchResult } from "@/lib/messages/chatSettingsUtils";
import { getUserFullName } from "@/lib/messages/chatUtils";
import { resolveMediaUrl } from "@/lib/url";

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
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-xl font-bold text-gray-900">Добавить участника</h2>
          <button type="button" onClick={onClose} className="text-gray-400 hover:text-gray-600">
            <svg className="h-6 w-6" fill="none" viewBox="0 0 24 24" stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
            </svg>
          </button>
        </div>

        <div className="mb-4">
          <input
            type="text"
            value={memberSearchQuery}
            onChange={(event) => onSearchChange(event.target.value)}
            placeholder="Введите имя или email..."
            className="w-full rounded-lg border border-gray-300 px-4 py-2 text-sm focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/20"
            autoFocus
          />
          <p className="mt-1 text-xs text-gray-500">Минимум 2 символа для поиска</p>
        </div>

        <div className="max-h-96 overflow-y-auto">
          {memberSearchLoading ? (
            <div className="py-8 text-center">
              <div className="mx-auto mb-2 h-6 w-6 animate-spin rounded-full border-2 border-sky-400 border-t-transparent" />
              <p className="text-sm text-gray-500">Поиск...</p>
            </div>
          ) : memberSearchQuery.trim().length < 2 ? (
            <div className="py-8 text-center">
              <Users className="mx-auto mb-2 h-12 w-12 text-gray-300" />
              <p className="text-sm text-gray-500">Начните вводить имя или email для поиска</p>
            </div>
          ) : memberSearchResults.length === 0 ? (
            <div className="py-8 text-center">
              <p className="text-sm text-gray-500">Пользователи не найдены</p>
            </div>
          ) : (
            <div className="space-y-2">
              {memberSearchResults.map((result) => (
                <div key={result.id} className="flex items-center gap-3 rounded-lg border border-gray-200 p-3 transition hover:bg-gray-50">
                  <div className="flex h-10 w-10 items-center justify-center overflow-hidden rounded-full bg-sky-400 text-sm font-semibold text-white">
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
                    <p className="text-sm font-medium text-gray-900">{result.name || getUserFullName(result.last_name, result.first_name)}</p>
                    {result.email ? <p className="text-xs text-gray-500">{result.email}</p> : null}
                  </div>
                  <button
                    type="button"
                    onClick={() => onAddMember(result.id)}
                    disabled={actionLoading === `add-member-${result.id}`}
                    className="rounded-lg bg-sky-600 px-3 py-1.5 text-xs font-medium text-white transition hover:bg-sky-700 disabled:opacity-50"
                  >
                    {actionLoading === `add-member-${result.id}` ? "..." : "Добавить"}
                  </button>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
